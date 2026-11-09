"""Runner behaviour without network access: providers' send() is replaced by scripted fakes."""
import datetime as dt
import json

import pytest
import yaml

from src import runner as R
from src.providers import gemini, groq
from src.providers.common import HttpResult

GOOD = '{"accept": "true", "confidence": 80, "reasons": ["prior_knowledge"], "justification": "Known."}'


def groq_ok(content=GOOD):
    return HttpResult(200, {"x-ratelimit-remaining-requests": "999"},
                      {"id": "x", "model": "openai/gpt-oss-120b", "system_fingerprint": "fp",
                       "choices": [{"message": {"content": content, "reasoning": "brief reasoning"},
                                    "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 1500, "completion_tokens": 200, "total_tokens": 1700}},
                      "{}", 0.42)


def gemini_ok(content=GOOD):
    return HttpResult(200, {}, {"candidates": [{"content": {"parts": [{"text": content}]}, "finishReason": "STOP"}],
                                "usageMetadata": {"promptTokenCount": 1500, "candidatesTokenCount": 80,
                                                  "thoughtsTokenCount": 20, "totalTokenCount": 1600},
                                "modelVersion": "gemini-3.1-flash-lite"}, "{}", 0.3)


def groq_429(limit_text, retry_after="2"):
    body = {"error": {"message": f"Rate limit reached for model `openai/gpt-oss-120b` on {limit_text}: "
                                 "Limit 1000, Used 1000, Requested 1. Please try again later.",
                      "type": "requests", "code": "rate_limit_exceeded"}}
    return HttpResult(429, {"retry-after": retry_after}, body, json.dumps(body), 0.1)


def gemini_429(quota_id, delay="41s"):
    body = {"error": {"code": 429, "message": "You exceeded your current quota.", "status": "RESOURCE_EXHAUSTED",
                      "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                   "violations": [{"quotaMetric": "generativelanguage.googleapis.com/x",
                                                   "quotaId": quota_id}]},
                                  {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay}]}}
    return HttpResult(429, {}, body, json.dumps(body), 0.1)


class FakeSend:
    def __init__(self, *responses, default=None):
        self.queue, self.default, self.calls = list(responses), default, []

    def __call__(self, cfg, payload, api_key, timeout):
        self.calls.append(payload)
        if self.queue:
            return self.queue.pop(0)
        if self.default is None:
            raise AssertionError("unexpected API call")
        return self.default()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "SLEEP", lambda stop, s: None)
    monkeypatch.setattr(R.Pacer, "wait", lambda self, est: None)  # pacing has its own test below
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    out, logs = tmp_path / "raw", tmp_path / "logs"
    return {"out": out, "logs": logs, "tmp": tmp_path,
            "args": ["--out-dir", str(out), "--logs-dir", str(logs), "--progress-every", "999"]}


def run(env, *extra):
    return R.main(list(extra) + env["args"])


def raw(env, model="gpt-oss-120b"):
    return R.read_raw(env["out"] / f"{model}.jsonl")


def events(env, model="gpt-oss-120b"):
    return R.read_raw(env["logs"] / f"{model}.events.jsonl")


# ---- planning

def test_plan_counts():
    cfg, claims = R.load_config(R.REPO / "models.yaml"), R.B.load_claims()
    n = {m: len(R.plan_cells(cfg, m, claims)) for m in cfg["models"]}
    assert n == {"gpt-oss-120b": 960, "gpt-oss-20b": 960, "qwen3.8-27b": 960, "gemini-3.5-flash-lite": 720}
    spot_cfg = {"defaults": cfg["defaults"], "models": {"s": {
        "provider": "gemini", "model_id": "x", "design": "spot_check",
        "spot_check": {"pairs": ["real-01", "inv-06"], "conditions": ["C0", "C1"]}}}}
    spot = R.plan_cells(spot_cfg, "s", claims)
    assert {c.condition for c in spot} == {"C0", "C1"} and len({c.claim_id for c in spot}) == 4
    keys = [c.key() for c in R.plan_cells(cfg, "gpt-oss-120b", claims)]
    assert len(keys) == len(set(keys))


def test_order_is_reproducible_and_shuffled():
    cfg, claims = R.load_config(R.REPO / "models.yaml"), R.B.load_claims()
    cells = R.plan_cells(cfg, "gpt-oss-120b", claims)
    a, sa = R.order_cells(cells, 20261113, "gpt-oss-120b")
    b, sb = R.order_cells(list(reversed(cells)), 20261113, "gpt-oss-120b")
    c, _ = R.order_cells(cells, 20261113, "gpt-oss-20b")
    assert a == b and sa == sb
    assert a != sorted(cells, key=lambda x: x.key()) and [x.key()[1:] for x in a] != [x.key()[1:] for x in c]


# ---- dry run

def test_dry_run_makes_no_calls_and_writes_nothing(env, monkeypatch, capsys):
    monkeypatch.setattr(groq, "send", FakeSend())
    monkeypatch.setattr(gemini, "send", FakeSend())
    assert run(env, "--dry-run") == 0
    out = capsys.readouterr().out
    assert "TOTAL" in out and "3600" in out
    assert not env["out"].exists() and not env["logs"].exists()


# ---- live runs with fake providers

def test_writes_one_line_per_response_and_resumes(env, monkeypatch):
    fake = FakeSend(default=groq_ok)
    monkeypatch.setattr(groq, "send", fake)
    sel = ("--models", "gpt-oss-120b", "--claims", "real-01-t", "--conditions", "C0,C1", "--reps", "2")
    assert run(env, *sel) == 0
    lines = raw(env)
    # C0 and C1 x 2 reps, plus the interpreter arm (C1 with the interpreter) x 2 reps
    assert len(lines) == 6 and len(fake.calls) == 6 and all(r["status"] == "ok" for r in lines)
    assert sum(r["interpreter"] for r in lines) == 2
    r = lines[0]
    for field in ("prompt_hash", "request", "raw_text", "parsed", "latency_s", "timestamp_utc", "seed",
                  "temperature", "reasoning_setting", "usage", "response_body", "run_date", "git_commit"):
        assert field in r
    assert r["request"]["body"]["messages"][1]["content"].startswith("Document:")
    assert r["reasoning_setting"] == {"reasoning_effort": "low", "include_reasoning": True}
    assert r["parsed"]["accept"] == "true" and r["truth_value"] is True
    before = (env["out"] / "gpt-oss-120b.jsonl").read_bytes()
    assert run(env, *sel) == 0           # everything is done: no calls, no rewrite
    assert len(fake.calls) == 6
    assert (env["out"] / "gpt-oss-120b.jsonl").read_bytes() == before
    assert run(env, *sel[:5], "C0,C1,C2", "--reps", "2") == 0   # widen the plan: only new cells run
    assert len(fake.calls) == 10       # + C2 x 2 and C2 with the interpreter x 2
    assert (env["out"] / "gpt-oss-120b.jsonl").read_bytes().startswith(before)


def test_pacer_spacing_and_token_window():
    import threading
    clock = {"t": 1000.0}
    pacer = R.Pacer(rpm=30, tpm=8000, stop=threading.Event(), clock=lambda: clock["t"])
    real_sleep = R.SLEEP
    try:
        R.SLEEP = lambda stop, s: clock.__setitem__("t", clock["t"] + s)
        pacer.wait(1000)
        t0 = clock["t"]
        pacer.record(3000)
        pacer.wait(1000)
        assert clock["t"] - t0 >= 2.0                 # 30 RPM -> 2 s apart
        pacer.record(3000)
        pacer.wait(3000)                              # 6000 used + 3000 > 8000 TPM
        assert clock["t"] >= t0 + 60                  # waits for the first record to leave the window
    finally:
        R.SLEEP = real_sleep


def test_parse_failure_retries_once_then_records_parse_failed(env, monkeypatch):
    fake = FakeSend(default=lambda: groq_ok("not json"))
    monkeypatch.setattr(groq, "send", fake)
    sel = ("--models", "gpt-oss-120b", "--claims", "inv-02-f", "--conditions", "C3", "--reps", "1")
    run(env, *sel)
    lines = raw(env)
    assert [r["status"] for r in lines] == ["parse_retry", "parse_failed"]
    assert lines[1]["seed"] == lines[0]["seed"] + 1 and lines[0]["raw_text"] == "not json"
    run(env, *sel)
    assert len(fake.calls) == 2           # parse_failed counts as done


def test_parse_retry_then_ok(env, monkeypatch):
    monkeypatch.setattr(groq, "send", FakeSend(groq_ok("```json\n{oops"), default=groq_ok))
    run(env, "--models", "gpt-oss-120b", "--claims", "inv-02-t", "--conditions", "C0", "--reps", "1")
    assert [r["status"] for r in raw(env)] == ["parse_retry", "ok"]


def test_per_minute_429_backs_off_then_succeeds(env, monkeypatch):
    monkeypatch.setattr(groq, "send", FakeSend(groq_429("tokens per minute (TPM)"), default=groq_ok))
    run(env, "--models", "gpt-oss-120b", "--claims", "real-02-t", "--conditions", "C0", "--reps", "1")
    assert [r["status"] for r in raw(env)] == ["ok"]
    ev = events(env)
    assert ev[0]["event"] == "http_429" and ev[0]["scope"] == "minute" and ev[0]["wait_s"] == 2.0


def test_per_day_429_stops_the_model_with_resume_time(env, monkeypatch, capsys):
    fake = FakeSend(groq_429("requests per day (RPD)", retry_after="3600"))
    monkeypatch.setattr(groq, "send", fake)
    run(env, "--models", "gpt-oss-120b", "--claims", "real-02-t", "--reps", "1")
    assert raw(env) == [] and len(fake.calls) == 1
    kinds = [e["event"] for e in events(env)]
    assert kinds == ["http_429", "daily_limit"]
    assert "Pacific" in capsys.readouterr().out


def test_gemini_429s_are_classified(env, monkeypatch):
    day = gemini.classify_429(gemini_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier"))
    minute = gemini.classify_429(gemini_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "7s"))
    assert (day.scope, day.wait_s) == ("day", 41.0) and (minute.scope, minute.wait_s) == ("minute", 7.0)
    monkeypatch.setattr(gemini, "send", FakeSend(gemini_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"),
                                                 default=gemini_ok))
    run(env, "--models", "gemini-3.5-flash-lite", "--claims", "real-04-t", "--conditions", "C1", "--reps", "1")
    assert [r["status"] for r in raw(env, "gemini-3.5-flash-lite")] == ["ok"]


def test_fatal_http_error_stops_the_model(env, monkeypatch):
    bad = HttpResult(400, {}, {"error": {"message": "unsupported parameter"}}, '{"error": "bad"}', 0.1)
    fake = FakeSend(bad)
    monkeypatch.setattr(groq, "send", fake)
    run(env, "--models", "gpt-oss-120b", "--claims", "real-01", "--reps", "1")
    assert raw(env) == [] and len(fake.calls) == 1
    assert events(env)[-1]["event"] == "fatal_http_error"


def test_local_daily_cap_stops_before_the_provider_does(env, monkeypatch):
    cfg = yaml.safe_load((R.REPO / "models.yaml").read_text(encoding="utf-8"))
    cfg["models"]["gpt-oss-120b"]["limits"]["rpd"] = 2
    path = env["tmp"] / "models.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    fake = FakeSend(default=groq_ok)
    monkeypatch.setattr(groq, "send", fake)
    run(env, "--config", str(path), "--models", "gpt-oss-120b", "--claims", "real-01-t", "--reps", "1")
    assert len(fake.calls) == 2 and events(env)[-1]["event"] == "daily_limit"


def test_limit_flag_caps_calls(env, monkeypatch):
    fake = FakeSend(default=gemini_ok)
    monkeypatch.setattr(gemini, "send", fake)
    run(env, "--models", "gemini-3.5-flash-lite", "--claims", "inv-05", "--limit", "3")
    assert len(fake.calls) == 3


# ---- payloads

def _payloads(env, monkeypatch, model, provider):
    fake = FakeSend(default=groq_ok if provider is groq else gemini_ok)
    monkeypatch.setattr(provider, "send", fake)
    run(env, "--models", model, "--claims", "real-05-t", "--conditions", "C1", "--reps", "1")
    return fake.calls[0]


def test_groq_payloads(env, monkeypatch):
    p = _payloads(env, monkeypatch, "gpt-oss-120b", groq)
    assert p["model"] == "openai/gpt-oss-120b" and p["temperature"] == 0.7 and isinstance(p["seed"], int)
    assert p["reasoning_effort"] == "low" and p["include_reasoning"] is True and "reasoning_format" not in p
    assert p["response_format"]["type"] == "json_schema" and p["response_format"]["json_schema"]["strict"] is True
    assert p["max_completion_tokens"] == 2048
    q = _payloads(env, monkeypatch, "qwen3.8-27b", groq)
    assert q["model"] == "qwen/qwen3.8-27b" and q["reasoning_effort"] == "none" and q["reasoning_format"] == "parsed"
    assert "include_reasoning" not in q and q["max_completion_tokens"] == 600
    assert "service_tier" not in p and "service_tier" not in q


def test_gemini_payloads(env, monkeypatch):
    p = _payloads(env, monkeypatch, "gemini-3.5-flash-lite", gemini)
    gc = p["generationConfig"]
    assert gc["temperature"] == 0.7 and isinstance(gc["seed"], int) and gc["responseMimeType"] == "application/json"
    assert gc["thinkingConfig"] == {"thinkingLevel": "MINIMAL", "includeThoughts": False}
    assert p["systemInstruction"]["parts"][0]["text"].startswith("You are assisting with a research task.")
    assert [c["role"] for c in p["contents"]] == ["user"]
    cfg = yaml.safe_load((R.REPO / "models.yaml").read_text(encoding="utf-8"))
    cfg["models"]["gemini-3.5-flash-lite"]["temperature"] = None   # a model whose provider ignores temperature
    path = env["tmp"] / "nulltemp.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    fake = FakeSend(default=gemini_ok)
    monkeypatch.setattr(gemini, "send", fake)
    run(env, "--config", str(path), "--models", "gemini-3.5-flash-lite", "--claims", "real-01-t",
        "--conditions", "C1", "--reps", "1")
    assert "temperature" not in fake.calls[0]["generationConfig"]


# ---- time

def test_next_pacific_midnight():
    t = dt.datetime(2026, 11, 13, 12, 0, tzinfo=dt.timezone.utc)          # PST, UTC-8
    assert R.next_pacific_midnight(t) == dt.datetime(2026, 11, 14, 8, 0, tzinfo=dt.timezone.utc)
    assert R._us_pacific_offset(dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)) == dt.timedelta(hours=-7)
    assert R._us_pacific_offset(t) == dt.timedelta(hours=-8)
    assert "Pacific" in R.resume_message(t)
