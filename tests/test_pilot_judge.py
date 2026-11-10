"""--pilot and its judge check, offline: providers' send() is replaced by scripted fakes."""
import json
import re
import threading

import pytest
import yaml

from src import grade as G
from src import judge as J
from src import runner as R
from src.providers import gemini, groq, openrouter
from src.providers.common import HttpResult
from tests.test_runner import FakeSend, env, gemini_ok, groq_ok  # noqa: F401  (env is a fixture)

MODELS = ("gpt-oss-120b", "gpt-oss-20b", "qwen3.8-27b", "gemini-3.5-flash-lite")
MAIN_ID, CROSS_ID = "test-lab/judge-1", "other-lab/check-1:free"
REPLY_OK = '{"score": "1", "reason": "Mentions the signature only vaguely."}'


def judge_ok(content=REPLY_OK, cost=0.0004):
    b = {"id": "gen-1", "model": MAIN_ID, "provider": "TestProvider",
         "choices": [{"message": {"content": content, "reasoning": "brief"}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 700, "completion_tokens": 30, "total_tokens": 730, "cost": cost}}
    return HttpResult(200, {}, b, json.dumps(b), 0.2)


def judges_config(tmp_path, main=None, cross=None):
    """models.yaml with both judges chosen (test values), plus any overrides."""
    cfg = yaml.safe_load((R.REPO / "models.yaml").read_text(encoding="utf-8"))
    cfg["judges"]["main"].update({"model_id": MAIN_ID, "family": "test-lab",
                                  "route": {"order": ["test-provider"], "allow_fallbacks": False,
                                            "require_parameters": True}, **(main or {})})
    cfg["judges"]["crosscheck"].update({"model_id": CROSS_ID, "family": "other-lab",
                                        "route": {"order": ["free-provider"], "allow_fallbacks": False,
                                                  "require_parameters": True}, **(cross or {})})
    path = tmp_path / "judged.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


class FakeJudge:
    """openrouter.send for the judges: scripted replies (an HttpResult, or an exception to raise), then
    the default. Thread-safe: the judges call it from several threads."""

    def __init__(self, *script, default=judge_ok):
        self.script, self.default, self.calls, self.lock = list(script), default, [], threading.Lock()

    def __call__(self, cfg, payload, api_key, timeout):
        with self.lock:
            self.calls.append(payload)
            item = self.script.pop(0) if self.script else None
        if isinstance(item, BaseException):
            raise item
        return item if item is not None else self.default()


@pytest.fixture
def judged(env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(groq, "send", FakeSend(default=groq_ok))
    monkeypatch.setattr(gemini, "send", FakeSend(default=gemini_ok))
    return judges_config(env["tmp"])


def pilot(*extra):
    return R.main(["--pilot", "--progress-every", "999", *extra])


def report(env):
    return json.loads((env["tmp"] / "pilot" / "pilot_report.json").read_text(encoding="utf-8"))


def test_pilot_runs_20_study_calls_then_10_blind_judge_calls(judged, env, monkeypatch, capsys):
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    assert pilot("--config", str(judged)) == 0
    pdir = env["tmp"] / "pilot"
    per_model = {m: R.read_raw(pdir / f"{m}.jsonl") for m in MODELS}
    assert {m: len(v) for m, v in per_model.items()} == {m: 5 for m in MODELS}
    assert {(r["condition"], r["interpreter"]) for r in per_model["gpt-oss-120b"]} == \
        {("C0", False), ("C1", False), ("C2", False), ("C5", False), ("C2", True)}
    assert {(r["condition"], r["interpreter"]) for r in per_model["gemini-3.5-flash-lite"]} == \
        {("C0", False), ("C1", False), ("C2", False), ("C5", False), ("C4", False)}
    assert len(fake.calls) == 10
    assert not env["out"].exists()                       # nothing in data/raw: pilot is excluded from analysis
    rep = report(env)
    assert rep["judge_passed"] and rep["judge_valid"] == 10 and rep["judge_verdict"] == "PASS"
    assert rep["judge_model_id"] == MAIN_ID and rep["study_cells_done"] == rep["study_cells_planned"] == 20
    out = capsys.readouterr().out
    assert "PILOT: 20 study cells on real-01-t, 20 still to run; then up to 10 judge calls." in out
    assert "**PASS**" in out and "Projected total including spend so far" in out
    rows = R.read_raw(pdir / "judge_check.jsonl")
    assert {r["model"] for r in rows} == set(MODELS)      # round-robin covers every model
    assert all(r["judge_model_id"] == MAIN_ID and r["served_by"] == "TestProvider" for r in rows)
    attempts = R.read_raw(pdir / "logs" / "judge_check.attempts.jsonl")
    assert len(attempts) == 10 and {a["outcome"] for a in attempts} == {"ok"} and all(a["utc_date"] for a in attempts)
    for p in fake.calls:
        text = p["messages"][0]["content"]
        assert p["model"] == MAIN_ID and p["temperature"] == 0.0 and p["response_format"]["type"] == "json_schema"
        assert p["provider"]["order"] == ["test-provider"] and p["provider"]["allow_fallbacks"] is False
        for leak in ("gpt-oss", "qwen", "gemini-3.5", "flash-lite", "truth", "invented", "real_obscure", "real-01"):
            assert leak not in text, leak
        assert not re.search(r"\bC[0-5]\b", text)          # no condition labels ("C2PA" is fine)
    assert pilot("--config", str(judged)) == 0           # re-run: everything reused, nothing re-asked
    assert len(fake.calls) == 10


def test_skip_judge_runs_the_study_calls_only(env, monkeypatch, capsys):
    monkeypatch.setattr(groq, "send", FakeSend(default=groq_ok))
    monkeypatch.setattr(gemini, "send", FakeSend(default=gemini_ok))
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    assert pilot("--skip-judge") == 0                     # the real models.yaml: no judge chosen yet
    pdir = env["tmp"] / "pilot"
    assert fake.calls == [] and sum(len(R.read_raw(pdir / f"{m}.jsonl")) for m in MODELS) == 20
    rep = report(env)
    assert rep["judge_verdict"] == "SKIPPED" and rep["judge_passed"] is None and rep["judge_skipped"]
    assert not (pdir / "judge_check.jsonl").exists()
    out = capsys.readouterr().out
    assert "then no judge calls (--skip-judge)" in out and "Judge check skipped" in out


def test_skip_judge_finishes_only_the_missing_cells(env, monkeypatch, capsys):
    groq_fake = FakeSend(default=groq_ok)
    monkeypatch.setattr(groq, "send", groq_fake)
    monkeypatch.setattr(gemini, "send", FakeSend(default=gemini_ok))
    assert pilot("--skip-judge", "--models", "gpt-oss-120b,gpt-oss-20b,gemini-3.5-flash-lite") == 0
    assert len(groq_fake.calls) == 10
    capsys.readouterr()
    assert pilot("--skip-judge") == 0                     # like finishing qwen after its first stop
    assert len(groq_fake.calls) == 15 and {p["model"] for p in groq_fake.calls[10:]} == {"qwen/qwen3.8-27b"}
    assert "PILOT: 20 study cells on real-01-t, 5 still to run" in capsys.readouterr().out
    assert report(env)["study_cells_done"] == 20


def test_pilot_refuses_before_any_call_while_the_judge_is_not_chosen(env, monkeypatch, capsys):
    groq_fake, gemini_fake = FakeSend(), FakeSend()      # no default: any call fails the test
    monkeypatch.setattr(groq, "send", groq_fake)
    monkeypatch.setattr(gemini, "send", gemini_fake)
    assert pilot() == 2
    assert groq_fake.calls == [] and gemini_fake.calls == []
    out = capsys.readouterr().out
    assert "has not been chosen yet" in out and "python src/runner.py --pilot --skip-judge" in out


def test_skip_judge_needs_pilot(env):
    with pytest.raises(SystemExit):
        R.main(["--skip-judge", "--dry-run"])


def test_pilot_fails_the_judge_check_below_9_of_10(judged, env, monkeypatch, capsys):
    fake = FakeJudge(*[judge_ok() for _ in range(8)], judge_ok("I think it is fine."), judge_ok('{"score": "3"}'))
    monkeypatch.setattr(openrouter, "send", fake)
    pilot("--config", str(judged))
    rep = report(env)
    assert rep["judge_valid"] == 8 and rep["judge_passed"] is False and rep["judge_verdict"] == "FAIL"
    out = capsys.readouterr().out
    assert "**FAIL**" in out and "choose the next candidate" in out
    assert G.pilot_judge_check(env["tmp"] / "pilot", MAIN_ID) == "FAIL"
    assert G.pilot_judge_check(env["tmp"] / "pilot", "another/model") is None


def test_judgements_by_another_judge_model_are_never_read(judged, env, monkeypatch):
    pdir = env["tmp"] / "pilot"
    pdir.mkdir(parents=True)
    old = "".join(json.dumps({"response_id": f"{m}|real-01-t|C1|0|0", "judge_model_id": "gemma-4-31b-it",
                              "score": "0", "valid": True}) + "\n" for m in MODELS)
    (pdir / "judge.jsonl").write_text(old, encoding="utf-8")
    before = (pdir / "judge.jsonl").read_bytes()
    (pdir / "judge_check.jsonl").write_text(json.dumps({"response_id": "gpt-oss-120b|real-01-t|C1|0|0",
                                                        "judge_model_id": "gemma-4-31b-it", "score": "0",
                                                        "valid": True}) + "\n", encoding="utf-8")
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    assert pilot("--config", str(judged)) == 0
    assert len(fake.calls) == 10                          # nothing reused from another judge model
    assert report(env)["judge_valid"] == 10
    assert (pdir / "judge.jsonl").read_bytes() == before  # kept on disk, untouched


OVERLOADED = '{"error": {"code": 503, "message": "No available provider", "metadata": {"provider_name": "TestProvider"}}}'


def test_judge_attempts_are_logged_in_full_and_announced(judged, env, monkeypatch, capsys):
    cfg_path = judges_config(env["tmp"], main={"concurrency": 1})   # one worker: script order is attempt order
    in_200 = {"error": {"code": 502, "message": "Provider returned error"}}
    fake = FakeJudge(HttpResult(503, {}, json.loads(OVERLOADED), OVERLOADED, 31.0),
                     HttpResult(None, {}, None, "", 180.0, error="ReadTimeout: read timed out"),
                     HttpResult(200, {}, in_200, json.dumps(in_200), 2.0))
    monkeypatch.setattr(openrouter, "send", fake)
    assert pilot("--config", str(cfg_path)) == 0
    ev = R.read_raw(env["tmp"] / "pilot" / "logs" / "judge_check.attempts.jsonl")
    assert [(e["status"], e["attempt"], e["outcome"]) for e in ev[:4]] == \
        [(503, 1, "failed"), (None, 2, "failed"), (200, 3, "failed"), (200, 4, "ok")]
    assert ev[0]["body"] == OVERLOADED and ev[0]["stage"] == "pilot" and ev[0]["response_id"].endswith("|C1|0|0")
    assert ev[1]["error"] == "ReadTimeout: read timed out" and ev[1]["action"].startswith("retry 2 of 5")
    assert ev[2]["error"] == "Provider returned error"    # an error inside an HTTP 200 is a failed attempt
    assert ev[3]["served_by"] == "TestProvider" and ev[3]["generation_id"] == "gen-1"
    assert len(ev) == len(fake.calls) == 13
    out = capsys.readouterr().out
    assert "[main judge] HTTP 503" in out and "[main judge] HTTP None: ReadTimeout" in out and "**PASS**" in out


def test_ctrl_c_in_the_judge_stage_stops_cleanly_and_resumes(judged, env, monkeypatch, capsys):
    cfg_path = judges_config(env["tmp"], main={"concurrency": 1})
    release, calls = threading.Event(), []

    def send(cfg, payload, api_key, timeout):
        calls.append(payload)
        if len(calls) == 3:
            release.wait(10)                              # the third call is in flight when Ctrl+C arrives
        return judge_ok()
    monkeypatch.setattr(openrouter, "send", send)
    real_tick = J.JudgeRun._join_tick

    def tick(self, thread):
        if not release.is_set() and len(self.new_rows) >= 2:
            release.set()
            raise KeyboardInterrupt                       # what Ctrl+C does in the waiting main thread
        real_tick(self, thread)
    monkeypatch.setattr(J.JudgeRun, "_join_tick", tick)
    assert pilot("--config", str(cfg_path)) == 1         # returns: no KeyboardInterrupt traceback
    out = capsys.readouterr().out
    assert "Interrupted in the judge stage: 3 of 10 judgements are saved" in out   # the call in flight is kept
    assert "INCOMPLETE" in out and "Re-run `python src/runner.py --pilot`" in out
    pdir = env["tmp"] / "pilot"
    rep = report(env)
    assert rep["judge_passed"] is None and rep["judge_verdict"] == "INCOMPLETE" and not rep["judge_complete"]
    assert G.pilot_judge_check(pdir, MAIN_ID) == "INCOMPLETE"   # not read as a FAIL by grade.py
    assert pilot("--config", str(cfg_path)) == 0         # finishing: 7 more judge calls, no study call
    assert len(calls) == 10 and report(env)["judge_passed"] is True


def test_an_interrupted_study_stage_does_not_start_the_judge(judged, env, monkeypatch, capsys):
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)

    def interrupted(workers, progress, stop, every, grace):
        stop.set()                                        # what Ctrl+C does inside wait_for
        for w in workers:
            w.join()
    monkeypatch.setattr(R, "wait_for", interrupted)
    assert pilot("--config", str(judged)) == 1
    assert fake.calls == [] and not (env["tmp"] / "pilot" / "pilot_report.json").exists()
    assert "interrupted before the judge stage" in capsys.readouterr().out


def test_pilot_warns_when_projection_is_over_4_dollars(env, monkeypatch, capsys):
    cfg = yaml.safe_load((R.REPO / "models.yaml").read_text(encoding="utf-8"))
    cfg["models"]["qwen3.8-27b"]["price_usd_per_mtok"] = {"input": 80.0, "output": 400.0}
    cfg["budget"]["hard_stop_usd"] = 100.0
    path = env["tmp"] / "pricey.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setattr(groq, "send", FakeSend(default=groq_ok))
    monkeypatch.setattr(gemini, "send", FakeSend(default=gemini_ok))
    pilot("--config", str(path), "--skip-judge")
    assert report(env)["projection_over_warning"] and "WARNING: projected total" in capsys.readouterr().out


@pytest.mark.parametrize("text,score", [
    ('{"score": "2", "reason": "ok"}', "2"),
    ('```json\n{"score": 0, "reason": "x"}\n```', "0"),
    ('{"score": "N/A", "reason": "x"}', "NA"),
    ('{"score": "na"}', "NA"),
    (REPLY_OK, "1"),
    ('<think>let me think {"score": "0"}</think>{"score": "2", "reason": "r"}', "2"),
    ('reasoning without its opening tag {"score": "0"}</think>\n{"score": "1", "reason": "r"}', "1"),
    ('{"score": 2.0}', "2"),
    ('{"score": "3"}', None),
    ('{"grade": "2"}', None),
    ("no json here", None),
    ("", None),
])
def test_parse_judgement(text, score):
    assert J.parse_judgement(text)[0] == score


def test_judge_prompt_is_blind_and_complete():
    ctx, claims = J.B.load_context(), {c["id"]: c for c in J.B.load_claims()}
    c = claims["inv-04-f"]
    facts = J.credential_facts(ctx, c, "C2")
    msg = J.judge_messages(facts, c["text"], "The signer vouched for this.")[0]["content"]
    assert "gathered assertion" in msg and c["text"] in msg and "The signer vouched for this." in msg
    assert "inv-04" not in msg and not re.search(r"\bC[0-5]\b", msg) and "False" not in msg
    with pytest.raises(ValueError):
        J.credential_facts(ctx, c, "C0")
