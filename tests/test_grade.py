"""grade.py: metrics, stratified sampling, the judge (faked), human labels and kappa."""
import csv
import json
import re
from collections import Counter

import pytest
from statsmodels.stats.inter_rater import cohens_kappa

from src import grade as G
from src import runner as R
from src import synthetic as S
from src.providers import gemini
from src.providers.common import HttpResult


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "SLEEP", lambda stop, s: None)
    monkeypatch.setattr(R.Pacer, "wait", lambda self, est: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    d = {k: tmp_path / k for k in ("raw", "graded", "human", "pilot")}
    S.generate(d["raw"], "effect", seed=1)
    return d


def grade(d, *extra):
    return G.main(["--raw-dir", str(d["raw"]), "--graded-dir", str(d["graded"]), "--human-dir", str(d["human"]),
                   "--pilot-dir", str(d["pilot"]), *extra])


def rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def judge_reply(cfg, payload, api_key, timeout, calls):
    calls.append(payload)
    return HttpResult(200, {}, {"candidates": [{"content": {"parts": [{"text": '{"score": "0", "reason": "x"}'}]},
                                                "finishReason": "STOP"}],
                                "usageMetadata": {"promptTokenCount": 600, "candidatesTokenCount": 20,
                                                  "totalTokenCount": 620}}, "{}", 0.2)


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


def test_judge_is_resumable_and_blind(dirs, monkeypatch):
    calls = []
    monkeypatch.setattr(gemini, "send", lambda *a: judge_reply(*a, calls))
    assert grade(dirs, "--judge", "--limit", "40") == 0
    assert grade(dirs, "--judge", "--limit", "40") == 0
    judged = R.read_raw(dirs["graded"] / "judgements.jsonl")
    assert len(calls) == 80 and len({j["response_id"] for j in judged}) == 80
    sample = rows(dirs["graded"] / "judge_sample.csv")
    assert len(sample) == 600 and [j["response_id"] for j in judged] == [s["response_id"] for s in sample[:80]]
    for p in calls:
        text = p["contents"][0]["parts"][0]["text"]
        assert p["generationConfig"]["temperature"] == 0.0 and "responseMimeType" not in p["generationConfig"]
        assert not re.search(r"\bC[0-5]\b|gpt-oss|qwen|flash-lite|truth_value|real-\d|inv-\d", text)


def test_judge_refuses_after_a_failed_pilot(dirs, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(gemini, "send", lambda *a: judge_reply(*a, calls))
    dirs["pilot"].mkdir(parents=True)
    (dirs["pilot"] / "pilot_report.json").write_text(json.dumps({"judge_passed": False}), encoding="utf-8")
    assert grade(dirs, "--judge", "--limit", "5") == 1 and calls == []
    assert "--human-sample 150" in capsys.readouterr().out
    assert grade(dirs, "--judge", "--limit", "5", "--force") == 0 and len(calls) == 5


def label(d, n, scores):
    path = d["human"] / f"human_sample_{n}.csv"
    items = rows(path)
    for it, s in zip(items, scores):
        it["score"] = s
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(items[0]))
        w.writeheader()
        w.writerows(items)
    return path


def test_human_sample_is_blind_and_kappa_is_reported(dirs, capsys):
    grade(dirs)
    sample = G.stratified_sample(G.judge_pool(rows(dirs["graded"] / "responses.csv")), 600, 0)
    G.write_csv(dirs["graded"] / "judge_sample.csv", [{"response_id": s["response_id"]} for s in sample], ["response_id"])
    S.synthetic_judgements(dirs["graded"], "effect", seed=2)
    assert grade(dirs, "--human-sample", "30") == 0
    items = rows(dirs["human"] / "human_sample_30.csv")
    assert list(items[0]) == ["item", "credential_facts", "statement", "explanation", "score", "notes"]
    assert len(items) == 30 and (dirs["human"] / "HOW_TO_LABEL.md").exists()
    key = {k["item"]: k for k in rows(dirs["human"] / "human_key_30.csv")}
    judged = G.latest_judgements(dirs["graded"])
    assert all(key[i["item"]]["response_id"] in judged for i in items)   # drawn from judged responses
    assert grade(dirs, "--human-sample", "30") == 1                      # never overwrites labels by default

    truth = [judged[key[i["item"]]["response_id"]]["score"] for i in items]
    path = label(dirs, 30, truth)
    assert grade(dirs, "--import-human", str(path)) == 0
    agree = json.loads((dirs["graded"] / "agreement_30.json").read_text(encoding="utf-8"))
    assert agree["overall"]["exact_agreement"] == 1.0
    assert set(agree["by_family"]) == {"gpt-oss", "qwen", "gemini"}

    flipped = ["NA" if t == "NA" else str((int(t) + 1) % 3) if k % 4 == 0 else t for k, t in enumerate(truth)]
    label(dirs, 30, flipped)
    grade(dirs, "--import-human", str(path))
    o = json.loads((dirs["graded"] / "agreement_30.json").read_text(encoding="utf-8"))["overall"]
    assert o["exact_agreement"] < 1.0
    label(dirs, 30, [""] + truth[1:])
    assert grade(dirs, "--import-human", str(path)) == 1               # unlabelled items are refused


@pytest.mark.parametrize("a,b", [
    (list("0011220"), list("0111200")),
    (list("012012012"), list("012012012")),
    (list("0000112222"), list("0101122221")),
])
def test_weighted_kappa_matches_statsmodels(a, b):
    table = [[sum(1 for x, y in zip(a, b) if x == str(i) and y == str(j)) for j in range(3)] for i in range(3)]
    ref = cohens_kappa(table, wt="linear").kappa
    assert G.weighted_kappa(a, b) == pytest.approx(ref)
