"""grade.py: metrics, stratified samples, the two judges (faked), their agreement and the §5 gate."""
import csv
import datetime as dt
import json
import re
import threading
from collections import Counter

import pytest
from statsmodels.stats.inter_rater import cohens_kappa

from src import grade as G
from src import judge as J
from src import runner as R
from src import synthetic as S
from src.providers import openrouter
from src.providers.common import HttpResult
from tests.test_pilot_judge import CROSS_ID, MAIN_ID, FakeJudge, judge_ok, judges_config


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "SLEEP", lambda stop, s: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    d = {k: tmp_path / k for k in ("raw", "graded", "pilot")}
    d["tmp"] = tmp_path
    S.generate(d["raw"], "effect", seed=1)
    d["cfg"] = judges_config(tmp_path)
    return d


def grade(d, *extra, config=None):
    return G.main(["--raw-dir", str(d["raw"]), "--graded-dir", str(d["graded"]), "--pilot-dir", str(d["pilot"]),
                   "--config", str(config or d["cfg"]), *extra])


def rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def free_ok():
    return judge_ok(cost=0.0)


# ---------------------------------------------------------------- metrics and samples

def test_metrics(dirs):
    assert grade(dirs) == 0
    r = rows(dirs["graded"] / "responses.csv")
    assert len(r) == 3600 and len({x["response_id"] for x in r}) == 3600
    ok = [x for x in r if x["status"] == "ok"]
    failed = [x for x in r if x["status"] == "parse_failed"]
    assert failed and all(x["accept"] == "" and x["accepted"] == "" for x in failed)
    for x in ok:
        assert x["accepted"] == str(int(x["accept"] == "true"))
        assert x["mark_cited"] == str(int("document_signature" in x["reasons"] or "document_source_identity" in x["reasons"]))
        assert x["abstained"] == str(int(x["accept"] == "uncertain" or "cannot_determine" in x["reasons"]))
    assert {x["family"] for x in r} == {"gpt-oss", "qwen", "gemini"}
    pf = {x["model"]: x for x in rows(dirs["graded"] / "parse_failures.csv")}
    assert pf["gemini-3.5-flash-lite"]["cells"] == "720" and pf["qwen3.8-27b"]["cells"] == "960"


def test_final_line_supersedes_parse_retry(tmp_path):
    base = {"model": "gpt-oss-20b", "claim_id": "inv-01-t", "condition": "C1", "interpreter": False, "rep": 0}
    p = tmp_path / "gpt-oss-20b.jsonl"
    p.write_text(json.dumps({**base, "status": "parse_retry", "attempt": 1}) + "\n" +
                 json.dumps({**base, "status": "ok", "attempt": 2}) + "\n", encoding="utf-8")
    final = G.final_responses(tmp_path, ["gpt-oss-20b"])
    assert len(final) == 1 and final[0]["attempt"] == 2


def test_stratified_sample_is_balanced_and_deterministic(dirs):
    grade(dirs)
    pool = G.judge_pool(rows(dirs["graded"] / "responses.csv"))
    s1 = G.stratified_sample(pool, 600, seed=7)
    s2 = G.stratified_sample(list(reversed(pool)), 600, seed=7)
    assert len(s1) == 600 and [x["response_id"] for x in s1] == [x["response_id"] for x in s2]
    counts = Counter((x["model"], x["condition"], x["claim_type"]) for x in s1)
    assert len(counts) == 32 and set(counts.values()) <= {18, 19}
    assert all(x["condition"] in ("C1", "C2", "C3", "C4") and x["interpreter"] == "False" for x in s1)
    assert [x["response_id"] for x in G.stratified_sample(pool, 600, seed=8)] != [x["response_id"] for x in s1]


def test_crosscheck_sample_is_a_stratified_subset_of_the_main_sample(dirs):
    grade(dirs)
    cfg = R.load_config(dirs["cfg"])
    r = rows(dirs["graded"] / "responses.csv")
    main = G.judge_sample_ids(cfg, dirs["graded"], r)
    cross = G.crosscheck_sample_ids(cfg, dirs["graded"], r)
    assert len(main) == 600 and len(cross) == 100 and set(cross) <= set(main)
    strata = Counter(tuple(i.split("|")[k] for k in (0, 2)) for i in cross)   # model x condition
    assert len(strata) == 16 and max(strata.values()) - min(strata.values()) <= 2
    assert G.crosscheck_sample_ids(cfg, dirs["graded"], []) == cross          # fixed once drawn


# ---------------------------------------------------------------- the main judge

def test_main_judge_is_concurrent_resumable_and_blind(dirs, monkeypatch, capsys):
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    assert grade(dirs, "--judge", "--limit", "40") == 0
    assert grade(dirs, "--judge", "--limit", "40") == 0
    judged = R.read_raw(dirs["graded"] / "judge_main.jsonl")
    sample = [s["response_id"] for s in rows(dirs["graded"] / "judge_sample.csv")]
    assert len(fake.calls) == 80 and len(judged) == 80 and {j["response_id"] for j in judged} == set(sample[:80])
    assert all(j["judge_model_id"] == MAIN_ID and j["served_by"] == "TestProvider" and j["stage"] == "main"
               for j in judged)
    attempts = R.read_raw(dirs["graded"] / "judge_main.attempts.jsonl")
    assert len(attempts) == 80 and all(a["outcome"] == "ok" and a["judge_model_id"] == MAIN_ID for a in attempts)
    for p in fake.calls:
        text = p["messages"][0]["content"]
        assert p["temperature"] == 0.0 and p["provider"]["order"] == ["test-provider"]
        assert not re.search(r"\bC[0-5]\b|gpt-oss|qwen|flash-lite|truth_value|real-\d|inv-\d", text)
    assert "Note: the pilot has no passed judge check" in capsys.readouterr().out


def test_judges_refuse_until_they_are_chosen(dirs, monkeypatch, capsys):
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    assert grade(dirs, "--judge", config=R.REPO / "models.yaml") == 1
    assert grade(dirs, "--crosscheck", config=R.REPO / "models.yaml") == 1
    assert fake.calls == [] and "has not been chosen yet" in capsys.readouterr().out


GOOD_ROUTE = {"order": ["p"], "allow_fallbacks": False}


def judges(main=None, cross=None):
    base = {"main": {"provider": "openrouter", "model_id": MAIN_ID, "family": "test-lab", "route": GOOD_ROUTE},
            "crosscheck": {"provider": "openrouter", "model_id": CROSS_ID, "family": "other-lab", "route": GOOD_ROUTE}}
    base["main"].update(main or {})
    base["crosscheck"].update(cross or {})
    return {"judges": base}


@pytest.mark.parametrize("role,main,cross,fragment", [
    ("main", {}, {}, None),
    ("crosscheck", {}, {}, None),
    ("main", {"model_id": None}, {}, "has not been chosen yet"),
    ("main", {"model_id": "openai/gpt-5.4-mini"}, {}, "excluded by §5"),
    ("main", {"model_id": "openai/gpt-oss-120b"}, {}, "excluded by §5"),
    ("main", {"model_id": "qwen/qwen3-max"}, {}, "excluded by §5"),
    ("main", {"model_id": "google/gemini-3-pro"}, {}, "excluded by §5"),
    ("main", {"model_id": "openrouter/auto"}, {}, "excluded by §5"),
    ("main", {"model_id": "test-lab/judge-1:free"}, {}, "must be a paid model"),
    ("main", {"family": "google"}, {}, "is excluded by §5"),
    ("main", {"family": None}, {}, "family is empty"),
    ("main", {"route": {"order": ["p"], "allow_fallbacks": True}}, {}, "must pin one serving provider"),
    ("main", {"route": {"order": [], "allow_fallbacks": False}}, {}, "must pin one serving provider"),
    ("crosscheck", {}, {"model_id": "other-lab/check-1"}, "must be a free"),
    ("crosscheck", {}, {"family": "test-lab"}, "is the main judge's family"),
    ("crosscheck", {}, {"model_id": "test-lab/other:free"}, "same developer"),
    ("crosscheck", {"model_id": None}, {}, "choose the main judge first"),
])
def test_judge_criteria_are_enforced(role, main, cross, fragment):
    problems = J.config_problems(judges(main, cross), role)
    if fragment is None:
        assert problems == []
    else:
        assert any(fragment in p for p in problems), problems


def test_main_judge_refuses_after_a_failed_pilot_check(dirs, monkeypatch, capsys):
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    dirs["pilot"].mkdir(parents=True)
    rep = dirs["pilot"] / "pilot_report.json"
    rep.write_text(json.dumps({"judge_model_id": MAIN_ID, "judge_verdict": "FAIL"}), encoding="utf-8")
    assert grade(dirs, "--judge", "--limit", "5") == 1 and fake.calls == []
    assert "choose the next candidate" in capsys.readouterr().out
    rep.write_text(json.dumps({"judge_model_id": "another/model", "judge_verdict": "FAIL"}), encoding="utf-8")
    assert grade(dirs, "--judge", "--limit", "5") == 0 and len(fake.calls) == 5   # another model's check
    rep.write_text(json.dumps({"judge_model_id": MAIN_ID, "judge_verdict": "FAIL"}), encoding="utf-8")
    assert grade(dirs, "--judge", "--limit", "5", "--force") == 0 and len(fake.calls) == 10


def test_the_judge_sample_waits_for_the_main_run(dirs, monkeypatch, capsys):
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    path = dirs["raw"] / "gemini-3.5-flash-lite.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:500]), encoding="utf-8")
    assert grade(dirs, "--judge") == 1 and fake.calls == [] and not (dirs["graded"] / "judge_sample.csv").exists()
    assert "gemini-3.5-flash-lite 220" in capsys.readouterr().out
    assert grade(dirs, "--judge", "--limit", "3", "--force") == 0 and len(fake.calls) == 3


def test_rows_by_another_judge_model_are_ignored(dirs, monkeypatch):
    fake = FakeJudge()
    monkeypatch.setattr(openrouter, "send", fake)
    cfg = R.load_config(dirs["cfg"])
    G.grade_metrics(cfg, dirs["raw"], dirs["graded"])
    first = G.judge_sample_ids(cfg, dirs["graded"], rows(dirs["graded"] / "responses.csv"))[0]
    (dirs["graded"] / "judge_main.jsonl").write_text(json.dumps(
        {"response_id": first, "judge_model_id": "gemma-4-31b-it", "score": "0", "valid": True}) + "\n", encoding="utf-8")
    assert G.judge_rows(dirs["graded"], "main", cfg) == {}
    assert grade(dirs, "--judge", "--limit", "1") == 0 and len(fake.calls) == 1   # judged again by this model
    assert first in G.judge_rows(dirs["graded"], "main", cfg)


def test_out_of_credits_stops_with_a_message(dirs, monkeypatch, capsys):
    b = {"error": {"code": 402, "message": "Insufficient credits"}}
    fake = FakeJudge(HttpResult(402, {}, b, json.dumps(b), 0.1))
    monkeypatch.setattr(openrouter, "send", fake)
    cfg = judges_config(dirs["tmp"], main={"concurrency": 1})
    assert grade(dirs, "--judge", config=cfg) == 1 and len(fake.calls) == 1
    out = capsys.readouterr().out
    assert "insufficient credits (HTTP 402)" in out and "openrouter.ai/settings/credits" in out
    (a,) = R.read_raw(dirs["graded"] / "judge_main.attempts.jsonl")
    assert a["status"] == 402 and a["body"] == json.dumps(b) and a["outcome"] == "failed"


def test_the_spend_cap_stops_the_main_judge(dirs, monkeypatch, capsys):
    fake = FakeJudge(default=lambda: judge_ok(cost=0.02))
    monkeypatch.setattr(openrouter, "send", fake)
    cfg = judges_config(dirs["tmp"], main={"concurrency": 1, "budget_usd": 0.05})
    assert grade(dirs, "--judge", config=cfg) == 1
    assert len(fake.calls) == 3 and "spend cap passed" in capsys.readouterr().out   # $0.06 > $0.05: no 4th call


def test_ctrl_c_stops_the_main_judge_cleanly(dirs, monkeypatch, capsys):
    cfg = judges_config(dirs["tmp"], main={"concurrency": 1})
    release, calls = threading.Event(), []

    def send(cfg_, payload, api_key, timeout):
        calls.append(payload)
        if len(calls) == 4:
            release.wait(10)
        return judge_ok()
    monkeypatch.setattr(openrouter, "send", send)
    real_tick = J.JudgeRun._join_tick

    def tick(self, thread):
        if not release.is_set() and len(self.new_rows) >= 3:
            release.set()
            raise KeyboardInterrupt
        real_tick(self, thread)
    monkeypatch.setattr(J.JudgeRun, "_join_tick", tick)
    assert grade(dirs, "--judge", config=cfg) == 1                      # returns instead of raising
    out = capsys.readouterr().out
    assert "Interrupted: finishing the judge calls in flight" in out and "Stopped: interrupted (Ctrl+C)" in out
    assert len(R.read_raw(dirs["graded"] / "judge_main.jsonl")) == 4    # the call in flight is kept


# ---------------------------------------------------------------- the cross-check

def test_crosscheck_stops_at_48_calls_a_utc_day_and_resumes_the_next_day(dirs, monkeypatch, capsys):
    fake = FakeJudge(default=free_ok)
    monkeypatch.setattr(openrouter, "send", fake)
    day1 = dt.datetime(2026, 11, 12, 10, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(R, "utcnow", lambda: day1)
    assert grade(dirs, "--crosscheck") == 0                              # a daily stop is a normal stop
    assert len(fake.calls) == 48 and len(R.read_raw(dirs["graded"] / "judge_crosscheck.jsonl")) == 48
    out = capsys.readouterr().out
    assert "daily cap reached: 48 calls" in out and "00:00 UTC (05:30 IST)" in out
    assert grade(dirs, "--crosscheck") == 0 and len(fake.calls) == 48   # same UTC day: nothing is sent
    monkeypatch.setattr(R, "utcnow", lambda: day1 + dt.timedelta(days=1))
    assert grade(dirs, "--crosscheck") == 0 and len(fake.calls) == 96   # the cap holds every UTC day
    monkeypatch.setattr(R, "utcnow", lambda: day1 + dt.timedelta(days=2))
    assert grade(dirs, "--crosscheck") == 0 and len(fake.calls) == 100
    assert "Every response in the cross-check judge's sample is judged." in capsys.readouterr().out
    judged = R.read_raw(dirs["graded"] / "judge_crosscheck.jsonl")
    sample = {s["response_id"] for s in rows(dirs["graded"] / "crosscheck_sample.csv")}
    assert len(judged) == 100 and {j["response_id"] for j in judged} == sample
    assert all(j["judge_model_id"] == CROSS_ID and j["stage"] == "crosscheck" for j in judged)
    days = Counter(a["utc_date"] for a in R.read_raw(dirs["graded"] / "judge_crosscheck.attempts.jsonl"))
    assert days == {"2026-11-12": 48, "2026-11-13": 48, "2026-11-14": 4}


def test_failed_attempts_count_against_the_daily_cap(dirs, monkeypatch):
    err = '{"error": {"code": 503, "message": "busy"}}'
    fake = FakeJudge(*[HttpResult(503, {}, json.loads(err), err, 1.0)] * 3, default=free_ok)
    monkeypatch.setattr(openrouter, "send", fake)
    assert grade(dirs, "--crosscheck") == 0
    attempts = R.read_raw(dirs["graded"] / "judge_crosscheck.attempts.jsonl")
    assert len(fake.calls) == len(attempts) == 48 and sum(a["outcome"] == "failed" for a in attempts) == 3
    assert len(R.read_raw(dirs["graded"] / "judge_crosscheck.jsonl")) == 45


def test_openrouter_daily_limit_stops_the_crosscheck(dirs, monkeypatch, capsys):
    b = {"error": {"code": 429, "message": "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock "
                                           "1000 free model requests per day"}}
    fake = FakeJudge(*[free_ok() for _ in range(5)], HttpResult(429, {}, b, json.dumps(b), 0.1))
    monkeypatch.setattr(openrouter, "send", fake)
    cfg = judges_config(dirs["tmp"], cross={"concurrency": 1})
    assert grade(dirs, "--crosscheck", config=cfg) == 0 and len(fake.calls) == 6
    assert len(R.read_raw(dirs["graded"] / "judge_crosscheck.jsonl")) == 5
    assert "today's limit" in capsys.readouterr().out
    last = R.read_raw(dirs["graded"] / "judge_crosscheck.attempts.jsonl")[-1]
    assert last["status"] == 429 and last["action"] == "daily limit: stopping" and "free-models-per-day" in last["body"]


# ---------------------------------------------------------------- agreement and the gate

@pytest.mark.parametrize("agree,status", [(0.9, "passed"), (0.1, "failed")])
def test_agreement_gate(dirs, agree, status):
    S.grade_with_fake_judge(dirs["raw"], dirs["graded"], "effect", seed=3, crosscheck_agree=agree)
    a = G.judge_agreement(R.load_config(R.REPO / "models.yaml"), dirs["graded"])
    assert a["status"] == status and a["complete"] and a["n_sample"] == a["n_crosschecked"] == 100
    assert set(a["by_family"]) == {"gpt-oss", "qwen", "gemini"}
    assert (a["kappa"] >= 0.6) is (status == "passed")
    assert a["overall"]["n_items"] == 100 and a["overall"]["n_both_scored"] < 100   # N/A takes no part in kappa


def test_agreement_is_pending_until_both_judges_finish(dirs, capsys):
    S.grade_with_fake_judge(dirs["raw"], dirs["graded"], "effect", seed=3)
    cfg = R.load_config(R.REPO / "models.yaml")
    path = dirs["graded"] / "judge_crosscheck.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:60]), encoding="utf-8")
    a = G.judge_agreement(cfg, dirs["graded"])
    assert a["status"] == "pending" and a["n_crosschecked"] == 60
    assert grade(dirs, "--agreement") == 0
    assert "PENDING" in capsys.readouterr().out and (dirs["graded"] / "judge_agreement.json").exists()
    (dirs["graded"] / "judge_main.jsonl").unlink()
    assert G.judge_agreement(cfg, dirs["graded"])["status"] == "none"


@pytest.mark.parametrize("a,b", [
    (list("0011220"), list("0111200")),
    (list("012012012"), list("012012012")),
    (list("0000112222"), list("0101122221")),
])
def test_weighted_kappa_matches_statsmodels(a, b):
    table = [[sum(1 for x, y in zip(a, b) if x == str(i) and y == str(j)) for j in range(3)] for i in range(3)]
    ref = cohens_kappa(table, wt="linear").kappa
    assert G.weighted_kappa(a, b) == pytest.approx(ref)
