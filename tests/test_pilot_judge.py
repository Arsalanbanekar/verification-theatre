"""--pilot and the judge, offline: providers' send() is replaced by scripted fakes."""
import json
import re

import pytest
import yaml

from src import grade as G
from src import judge as J
from src import runner as R
from src.providers import gemini, groq
from src.providers.common import HttpResult
from tests.test_runner import FakeSend, env, gemini_ok, groq_ok  # noqa: F401  (env is a fixture)

MODELS = ("gpt-oss-120b", "gpt-oss-20b", "qwen3.8-27b", "gemini-3.5-flash-lite")
JUDGE_OK = '<|channel>thought\n<channel|>{"score": "1", "reason": "Mentions the signature only vaguely."}'


def fake_gemini(judge_replies):
    calls = {"judge": [], "study": []}

    def send(cfg, payload, api_key, timeout):
        if cfg["model_id"].startswith("gemma"):
            calls["judge"].append(payload)
            return gemini_ok(judge_replies[(len(calls["judge"]) - 1) % len(judge_replies)])
        calls["study"].append(payload)
        return gemini_ok()
    return send, calls


def pilot(*extra):
    return R.main(["--pilot", "--progress-every", "999", *extra])


def test_pilot_runs_20_study_calls_then_10_blind_judge_calls(env, monkeypatch, capsys):
    gsend, calls = fake_gemini([JUDGE_OK])
    groq_fake = FakeSend(default=groq_ok)
    monkeypatch.setattr(groq, "send", groq_fake)
    monkeypatch.setattr(gemini, "send", gsend)
    assert pilot() == 0
    pdir = env["tmp"] / "pilot"
    per_model = {m: R.read_raw(pdir / f"{m}.jsonl") for m in MODELS}
    assert {m: len(v) for m, v in per_model.items()} == {m: 5 for m in MODELS}
    assert {(r["condition"], r["interpreter"]) for r in per_model["gpt-oss-120b"]} == \
        {("C0", False), ("C1", False), ("C2", False), ("C5", False), ("C2", True)}
    assert {(r["condition"], r["interpreter"]) for r in per_model["gemini-3.5-flash-lite"]} == \
        {("C0", False), ("C1", False), ("C2", False), ("C5", False), ("C4", False)}
    assert all(r["claim_id"] == "real-01-t" for v in per_model.values() for r in v)
    assert len(calls["judge"]) == 10
    assert not env["out"].exists()                       # nothing in data/raw: pilot is excluded from analysis
    rep = json.loads((pdir / "pilot_report.json").read_text(encoding="utf-8"))
    assert rep["judge_passed"] and rep["judge_valid"] == 10 and rep["study_responses"] == 20
    out = capsys.readouterr().out
    assert "**PASS**" in out and "Projected total including spend so far" in out
    judged_models = {json.loads(l)["model"] for l in (pdir / "judge.jsonl").read_text(encoding="utf-8").splitlines()}
    assert judged_models == set(MODELS)                  # round-robin covers every model
    for p in calls["judge"]:
        text = p["contents"][0]["parts"][0]["text"]
        assert "responseMimeType" not in p["generationConfig"]   # plain text: JSON mode undocumented for Gemma
        for leak in ("gpt-oss", "qwen", "gemini-3.5", "flash-lite", "truth", "invented", "real_obscure", "real-01"):
            assert leak not in text, leak
        assert not re.search(r"\bC[0-5]\b", text)          # no condition labels ("C2PA" is fine)
    assert pilot() == 0                                  # re-run: everything reused, nothing re-asked
    assert len(calls["judge"]) == 10 and len(groq_fake.calls) == 15


def test_pilot_fails_judge_below_9_of_10(env, monkeypatch, capsys):
    gsend, calls = fake_gemini([JUDGE_OK] * 8 + ["I think it is fine.", '{"score": "3"}'])
    monkeypatch.setattr(groq, "send", FakeSend(default=groq_ok))
    monkeypatch.setattr(gemini, "send", gsend)
    pilot()
    rep = json.loads((env["tmp"] / "pilot" / "pilot_report.json").read_text(encoding="utf-8"))
    assert rep["judge_valid"] == 8 and not rep["judge_passed"]
    out = capsys.readouterr().out
    assert "**FAIL**" in out and "--human-sample 150" in out


def test_pilot_warns_when_projection_is_over_4_dollars(env, monkeypatch, capsys):
    cfg = yaml.safe_load((R.REPO / "models.yaml").read_text(encoding="utf-8"))
    cfg["models"]["qwen3.8-27b"]["price_usd_per_mtok"] = {"input": 80.0, "output": 400.0}
    cfg["budget"]["hard_stop_usd"] = 100.0
    path = env["tmp"] / "pricey.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    gsend, _ = fake_gemini([JUDGE_OK])
    monkeypatch.setattr(groq, "send", FakeSend(default=groq_ok))
    monkeypatch.setattr(gemini, "send", gsend)
    pilot("--config", str(path))
    rep = json.loads((env["tmp"] / "pilot" / "pilot_report.json").read_text(encoding="utf-8"))
    assert rep["projection_over_warning"] and "WARNING: projected total" in capsys.readouterr().out


GEMMA_503 = ('{\n  "error": {\n    "code": 503,\n    "message": "This model is currently experiencing high demand. '
             'Spikes in demand are usually temporary. Please try again later.",\n    "status": "UNAVAILABLE"\n  }\n}\n')


def scripted_gemini(judge_script):
    """Judge calls take their reply from judge_script (an HttpResult, or an exception to raise), then succeed."""
    calls = {"judge": [], "study": []}

    def send(cfg, payload, api_key, timeout):
        if cfg["model_id"].startswith("gemma"):
            calls["judge"].append(payload)
            if judge_script:
                item = judge_script.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item
            return gemini_ok(JUDGE_OK)
        calls["study"].append(payload)
        return gemini_ok()
    return send, calls


def test_judge_failures_are_logged_in_full_and_announced(env, monkeypatch, capsys):
    gsend, calls = scripted_gemini([HttpResult(503, {}, json.loads(GEMMA_503), GEMMA_503, 31.0),
                                    HttpResult(None, {}, None, "", 120.0, error="ReadTimeout: read timed out")])
    monkeypatch.setattr(groq, "send", FakeSend(default=groq_ok))
    monkeypatch.setattr(gemini, "send", gsend)
    assert pilot() == 0
    ev = R.read_raw(env["tmp"] / "pilot" / "logs" / "judge.events.jsonl")
    assert [(e["status"], e["attempt"]) for e in ev] == [(503, 1), (None, 2)]
    assert ev[0]["body"] == GEMMA_503 and ev[0]["stage"] == "pilot" and ev[0]["response_id"].endswith("|C1|0|0")
    assert ev[1]["error"] == "ReadTimeout: read timed out" and ev[1]["action"].startswith("retry 2 of 5")
    out = capsys.readouterr().out
    assert "[judge] HTTP 503" in out and "[judge] HTTP None: ReadTimeout" in out and "**PASS**" in out


def test_ctrl_c_in_the_judge_stage_stops_cleanly_and_resumes(env, monkeypatch, capsys):
    gsend, calls = scripted_gemini([gemini_ok(JUDGE_OK), gemini_ok(JUDGE_OK), KeyboardInterrupt()])
    groq_fake = FakeSend(default=groq_ok)
    monkeypatch.setattr(groq, "send", groq_fake)
    monkeypatch.setattr(gemini, "send", gsend)
    assert pilot() == 1                                   # returns: no KeyboardInterrupt traceback
    out = capsys.readouterr().out
    assert "Interrupted in the judge stage: 2 of 10 judgements are saved" in out
    assert "INCOMPLETE" in out and "Re-run `python src/runner.py --pilot`" in out
    pdir = env["tmp"] / "pilot"
    rep = json.loads((pdir / "pilot_report.json").read_text(encoding="utf-8"))
    assert rep["judge_passed"] is None and rep["judge_verdict"] == "INCOMPLETE" and not rep["judge_complete"]
    assert G.pilot_judge_passed(pdir) is None             # not read as a FAIL by grade.py or analyse.py
    study_calls = len(groq_fake.calls) + len(calls["study"])
    assert pilot() == 0                                   # finishing: 8 more judge calls, no study calls
    assert len(calls["judge"]) == 3 + 8 and len(groq_fake.calls) + len(calls["study"]) == study_calls
    assert json.loads((pdir / "pilot_report.json").read_text(encoding="utf-8"))["judge_passed"] is True


def test_an_interrupted_study_stage_does_not_start_the_judge(env, monkeypatch, capsys):
    gsend, calls = scripted_gemini([])
    monkeypatch.setattr(groq, "send", FakeSend(default=groq_ok))
    monkeypatch.setattr(gemini, "send", gsend)

    def interrupted(workers, progress, stop, every, grace):
        stop.set()                                        # what Ctrl+C does inside wait_for
        for w in workers:
            w.join()
    monkeypatch.setattr(R, "wait_for", interrupted)
    assert pilot() == 1
    assert calls["judge"] == [] and not (env["tmp"] / "pilot" / "pilot_report.json").exists()
    assert "interrupted before the judge stage" in capsys.readouterr().out


@pytest.mark.parametrize("text,score", [
    ('{"score": "2", "reason": "ok"}', "2"),
    ('```json\n{"score": 0, "reason": "x"}\n```', "0"),
    ('{"score": "N/A", "reason": "x"}', "NA"),
    ('{"score": "na"}', "NA"),
    (JUDGE_OK, "1"),
    ('<|channel>thought\nlet me think {"score": "0"}<channel|>{"score": "2", "reason": "r"}', "2"),
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
