"""analyse.py on synthetic data: recovers injected effects, reports nulls as nulls, fills every
REPORT_DRAFT.md slot, and its statistics match reference implementations."""
import json
import re
import shutil

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps
from statsmodels.stats.multitest import multipletests

from src import analyse as A
from src import grade as G
from src import runner as R
from src import synthetic as S

MODELS = ["gpt-oss-120b", "gpt-oss-20b", "qwen3.8-27b", "gemini-3.5-flash-lite"]
DRAFT = R.REPO / "REPORT_DRAFT.md"
# Any single synthetic data set can show a chance false positive (about 5% per Holm family; null
# seeds 0 and 1 do, for H4). This seed has none; test_null_false_positive_rate checks calibration
# over many seeds, so a structural bias cannot hide behind the choice.
SEED = 2


def run(root, raw, graded, pilot=None, draft=DRAFT, source="auto"):
    return A.analyse(raw, graded, root / "results", pilot or root / "no_pilot", draft, R.REPO / "models.yaml", source)


@pytest.fixture(scope="module")
def scenario(tmp_path_factory):
    cache = {}

    def get(name):
        if name not in cache:
            root = tmp_path_factory.mktemp(name)
            S.generate(root / "raw", name, seed=SEED)
            S.grade_with_fake_judge(root / "raw", root / "graded", name, seed=SEED)
            cache[name] = (root, run(root, root / "raw", root / "graded"))
        return cache[name]
    return get


def headline(res):
    real, allp = res["fam"][("pooled", "real_obscure")], res["fam"][("pooled", "all")]
    return {"H1": A.find(real, "H1", "C1 vs C0"), "C32": A.find(real, "H2", "C3 vs C2"),
            "C32conf": A.find(real, "H2", "C3 vs C2", "confidence"),
            "C41": A.find(real, "H2", "C4 vs C1"), "C43": A.find(real, "H2", "C4 vs C3"),
            "H2b": A.find(real, "H2b", "C5 vs C0", "discrimination index"),
            "flat": A.find(real, "H2b", "C1-C4 mean vs C0", "discrimination index", primary=False),
            "H3": A.find(real, "H3", "C1-C4 vs 50%", "share of credential mentions scored 2"),
            "H4": A.find(allp, "H4", "interpreter vs none (C1, C2)")}


# ---------------------------------------------------------------- recovery and nulls

def test_injected_effects_are_recovered(scenario):
    _, res = scenario("effect")
    h = headline(res)
    assert h["H1"]["delta"] > 0.15 and h["H1"]["p_holm"] < 0.05            # INFLATION = 0.30
    assert h["H2b"]["delta"] > 0.3 and h["H2b"]["p_holm"] < 0.05           # C5 separates the twins
    assert h["H4"]["delta"] < -0.1 and h["H4"]["p_holm"] < 0.05            # INTERPRETER_CUT = 0.20
    assert h["H3"]["delta"] < 0.5 and h["H3"]["p_holm"] < 0.05             # fake judge: mostly 0
    assert h["flat"]["p"] >= 0.05                                          # C1-C4 inflate both twins alike
    for k in ("C32", "C41", "C43"):                                        # no C2-C4 differences injected
        assert h[k]["p_holm"] >= 0.05, k
    h5 = res["h5"]
    assert h5["invented_delta"] > h5["real_delta"] > 0                     # INVENTED_EXTRA = 0.10
    s = res["slots"]
    assert "raised acceptance by" in s["HEADLINE"] and "did not reliably differ" in s["HEADLINE"]
    assert s["H4_SENTENCE"].startswith("A plain-language interpreter stating each credential's scope reduced")
    assert "rose by" in s["DISCRIMINATION"] and "did not reliably move" in s["DISCRIMINATION"]
    assert s["H2_SENTENCE"].startswith("No reliable difference")
    assert s["H3_SENTENCE"].endswith("so H3 is supported.") and "mentioned the credential" in s["H3_SENTENCE"]
    assert A.h3_verdict(h["H3"])[0] and h["H3"]["ci_high"] < 0.5
    assert s["RESULT_PHRASE"].startswith("that credentials certifying nothing")


def test_null_data_reports_nulls(scenario):
    _, res = scenario("null")
    h = headline(res)
    for k in ("H1", "C32", "C32conf", "C41", "C43", "H2b", "H4"):
        assert h[k]["p_holm"] >= 0.05, k
    s = res["slots"]
    assert "did not reliably change acceptance" in s["HEADLINE"]
    assert "did not reliably change acceptance" in s["H4_SENTENCE"]
    assert "did not reliably rise" in s["DISCRIMINATION"]
    assert s["H5_46"].startswith("No clear evidence")
    assert s["RESULT_PHRASE"].startswith("how far credentials moved")
    assert "raised" not in s["HEADLINE"] and "reduced" not in s["H4_SENTENCE"]


def test_null_false_positive_rate(tmp_path):
    """Over 20 null data sets each Holm family should rarely reject anything (about 1 in 20)."""
    empty = pd.DataFrame(columns=["response_id", "score"])
    hits = {"real_obscure": 0, "all": 0}
    for seed in range(20):
        S.generate(tmp_path / str(seed), "null", seed=seed)
        df = A.load_responses(tmp_path / str(seed), MODELS)
        for ctype in hits:
            rows = A.primary_family(df, empty, MODELS, A.TYPE_SETS[ctype], np.random.default_rng(seed))
            hits[ctype] += any(r["primary"] and r["p_holm"] < 0.05 for r in rows)
    assert hits["real_obscure"] <= 3 and hits["all"] <= 3, hits


def test_slot_text_has_no_nan_and_no_nested_parentheses(scenario):
    for name in ("effect", "null"):
        _, res = scenario(name)
        for slot, text in res["slots"].items():
            assert not re.search(r"\bnan\b|\binf\b", text), (slot, text)
            depth = 0
            for ch in text:
                depth += (ch == "(") - (ch == ")")
                assert depth <= 1, (slot, text)
            assert depth == 0, (slot, text)


# ---------------------------------------------------------------- outputs

def test_outputs_are_written(scenario):
    root, res = scenario("effect")
    out = root / "results"
    for f in ("fig1_acceptance.png", "fig2_discrimination.png", "fig3_scope_accuracy.png", "fig4_interpreter.png"):
        assert (out / f).stat().st_size > 20_000, f
    tests = pd.read_csv(out / "primary_tests.csv")
    assert set(tests["model_scope"]) == {"pooled", *MODELS}
    assert set(tests["claim_type"]) == {"all", "real_obscure", "invented"}
    for (scope, ctype), g in tests[tests["primary"]].groupby(["model_scope", "claim_type"]):
        assert len(g) == 8, (scope, ctype)                                 # the Holm family
    acc = pd.read_csv(out / "acceptance_by_condition.csv")
    assert len(acc[acc["model"] == "pooled"]) == 2 * 2 * 6
    assert ((acc["ci_low"] >= 0) & (acc["ci_high"] <= 1)).all()
    for f in ("discrimination_by_condition.csv", "citation_abstention_confidence.csv", "confidence_delta.csv",
              "scope_accuracy.csv", "h5_unrecognised_sources.csv", "rep_variance.csv", "per_model.csv"):
        assert len(pd.read_csv(out / f)) > 0, f
    dist = pd.read_csv(out / "scope_distribution.csv")
    assert len(dist) == 5 * 3 * 5                                          # scopes x claim types x condition sets
    shares = dist[["share_0", "share_1", "share_2"]].sum(axis=1)
    assert np.allclose(shares[dist["n_mentions"] > 0], 1.0)
    assert ((dist["mention_ci_low"] <= dist["mention"]) & (dist["mention"] <= dist["mention_ci_high"])).all()
    examples = (out / "example_justifications.md").read_text(encoding="utf-8")
    assert examples.count("\n- `") == 12 and "Score 0 in C2" in examples
    summary = (out / "results_summary.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in summary and "## Robustness" in summary and "Scale within family" in summary
    assert "Responses collected from 2026-11-13 12:00 to 2026-11-13 12:00 UTC" in summary
    filled = (out / "REPORT_DRAFT.filled.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in filled.splitlines()[0]
    assert re.findall(r"\{[^{}]*\}", filled) == ["{PLACEHOLDER}"]           # only the instruction line is left
    assert ("Four models (3,600 of 3,600 planned cells completed: " in filled
            and "): GPT-OSS-120B, GPT-OSS-20B and Qwen3.8-27B via Groq" in filled)   # §3.3 lead-in + model list
    assert DRAFT.read_text(encoding="utf-8") != filled                     # the draft itself is never written


def test_draft_states_the_current_facts():
    text = " ".join(DRAFT.read_text(encoding="utf-8").split())           # independent of line wrapping
    for stale in ("Gemini 3.1", "Gemini 3.6", "spot check", "Spot check", "rev 3.1", "data/results_summary.md",
                  "Gemma", "hand-label", "9 of 10 pilot calls", "judge–human", "human labels,"):
        assert stale not in text, stale
    for fact in ("rev 3.3", "rev 3.4", "Gemini 3.5 Flash-Lite", "weighted kappa is at least 0.6", "no human labels",
                 "paired t-tests over pairs", "Holm correction over the eight", "upper bound of the 95% CI",
                 "data/results/results_summary.md"):
        assert fact in text, fact


def test_draft_notes_flag_a_stale_prereg_commit():
    latest = A.git_out("log", "-1", "--format=%h", "--", "PREREGISTRATION.md")
    assert A.draft_notes(f"(`PREREGISTRATION.md`, rev 3.3, commit `{latest}`)") == []
    note = A.draft_notes("(`PREREGISTRATION.md`, rev 3.1, commit `62535a8`)")
    assert len(note) == 1 and "62535a8" in note[0] and latest in note[0]


def test_every_draft_placeholder_maps_to_a_slot():
    text = DRAFT.read_text(encoding="utf-8")
    entries = A.placeholder_entries(text, {})
    assert entries[0]["slot"] == "_INSTRUCTION"
    slots = [e["slot"] for e in entries[1:]]
    assert None not in slots and len(slots) == 27
    assert slots == ["N_MODELS", "HEADLINE", "DISC_ABSTRACT", "H4_SENTENCE", "H5_ABSTRACT", "RESULT_PHRASE",
                     "MODELS_PARAGRAPH", "SETTINGS", "JUDGE_MODEL", "N_JUDGED", "KAPPA",
                     "C0_real_true", "C0_real_false", "C0_inv_true", "C0_inv_false", "C0_SENTENCE",
                     "H1_STAT", "C32_STAT", "C41_STAT", "H2_SENTENCE", "DISCRIMINATION",
                     "SCOPE_TABLE", "CITATION_TABLE", "H5_DELTA", "H5_46", "H4_STAT", "N_STUDY_MODELS"]
    # robust to re-wrapping: one line per paragraph gives the same mapping
    unwrapped = re.sub(r"(?<=\S)\n(?=[^\n#>|\-\d])", " ", text)
    assert unwrapped != text
    assert [e["slot"] for e in A.placeholder_entries(unwrapped, {})] == ["_INSTRUCTION"] + slots


def test_every_slot_resolves_with_data(scenario):
    _, res = scenario("effect")
    missing = [e["placeholder"] for e in res["entries"] if e["text"] == A.NO_VALUE]
    assert missing == []
    assert {e["slot"] for e in res["entries"]} - {"_INSTRUCTION"} <= set(res["slots"])


def test_unknown_placeholder_is_flagged_for_hand_fill():
    entries = A.placeholder_entries("Intro {SOMETHING NEW} and {X}.", {})
    assert [e["text"] for e in entries] == [A.NO_VALUE, A.NO_VALUE]


# ---------------------------------------------------------------- statistics

def test_holm_matches_statsmodels():
    rng = np.random.default_rng(0)
    for _ in range(20):
        p = list(rng.uniform(0, 0.2, 8))
        assert np.allclose(A.holm(p), multipletests(p, method="holm")[1])
    p = [0.01, float("nan"), 0.04, 0.03]                                   # NaN = no data, not a test
    out = A.holm(p)
    assert np.isnan(out[1]) and np.allclose([out[0], out[2], out[3]], multipletests([0.01, 0.04, 0.03], method="holm")[1])


def test_t_test_matches_scipy():
    rng = np.random.default_rng(1)
    for n in (3, 10, 20):
        x = rng.normal(0.1, 0.2, n)
        m, lo, hi, p = A.t_test(x)
        ref = sps.ttest_1samp(x, 0.0)
        ci = ref.confidence_interval(0.95)
        assert p == pytest.approx(ref.pvalue) and lo == pytest.approx(ci.low) and hi == pytest.approx(ci.high)
        assert A.t_test(x, 0.05)[3] == pytest.approx(sps.ttest_1samp(x, 0.05).pvalue)
    assert A.t_test([0.2, 0.2, 0.2])[3] == 0.0 and A.t_test([0.0, 0.0])[3] == 1.0
    assert np.isnan(A.t_test([0.3])[3])


def test_signflip_is_exact_for_small_n():
    rng = np.random.default_rng(0)
    assert A.signflip_p([1.0, 1.0, 1.0], rng) == pytest.approx(2 / 8)
    assert A.signflip_p([1.0] * 10, rng) == pytest.approx(2 / 1024) == A.min_p(10)
    assert A.signflip_p([0.5, -0.5], rng) == 1.0


def tiny(cells):
    """cells: (pair, truth, condition, accepted list) -> response-level frame for one model."""
    rows = []
    for pair, truth, cond, acc in cells:
        for rep, a in enumerate(acc):
            rows.append({"model": "m", "pair_id": pair, "claim_type": "real_obscure", "truth_value": truth,
                         "claim_id": f"{pair}-{'t' if truth else 'f'}", "condition": cond, "interpreter": False,
                         "rep": rep, "accepted": float(a), "confidence": 50.0 + 10 * a,
                         "response_id": f"m|{pair}|{truth}|{cond}|{rep}"})
    return pd.DataFrame(rows)


def test_ceiling_pairs_leave_inflation_tests_only():
    cells = []
    for pair, c0 in (("p1", [1, 1, 1]), ("p2", [0, 1, 0]), ("p3", [0, 0, 1])):
        for truth in (True, False):
            cells += [(pair, truth, "C0", c0), (pair, truth, "C1", [1, 1, 1]), (pair, truth, "C5", c0)]
    df = tiny(cells)
    assert A.ceiling_pairs(df, ["m"]) == {"p1"}
    rows = A.primary_family(df, pd.DataFrame(columns=["response_id", "score"]), ["m"], ("real_obscure",),
                            np.random.default_rng(0))
    h1 = A.find(rows, "H1", "C1 vs C0")
    full = A.find(rows, "H1", "C1 vs C0", primary=False)
    assert (h1["n_pairs"], h1["n_ceiling_dropped"], full["n_pairs"]) == (2, 1, 3)
    assert A.find(rows, "H2b", "C5 vs C0", "discrimination index")["n_pairs"] == 3   # H2b keeps every pair


def test_discrimination_index_is_true_minus_false():
    df = tiny([("p1", True, "C0", [1, 1, 0]), ("p1", False, "C0", [0, 0, 1]),
               ("p2", True, "C0", [1, 1, 1]), ("p2", False, "C0", [0, 0, 0])])
    disc = A.pair_values(df, ["m"], False, "disc")
    assert disc["C0"].to_dict() == {("p1", "real_obscure"): pytest.approx(1 / 3), ("p2", "real_obscure"): 1.0}
    both = A.pair_values(df, ["m"], False, "both")
    assert both["C0"].to_dict() == {("p1", "real_obscure"): pytest.approx(0.5), ("p2", "real_obscure"): 0.5}


def test_scope_shares_are_pair_level_among_mentions():
    df = tiny([("p1", True, "C1", [1, 1, 0, 0]), ("p2", True, "C2", [1, 0, 1, 0])])
    scores = {"m|p1|True|C1|0": "2", "m|p1|True|C1|1": "0", "m|p1|True|C1|2": "NA", "m|p1|True|C1|3": "1",
              "m|p2|True|C2|0": "2", "m|p2|True|C2|1": "2", "m|p2|True|C2|2": "NA", "m|p2|True|C2|3": "NA"}
    scope = pd.DataFrame({"response_id": list(scores), "score": list(scores.values())})
    d = A.scope_shares(df, scope, ["m"], ("real_obscure",))
    assert (d["n_judged"], d["n_mentions"], d["n_pairs"]) == (8, 5, 2)
    assert d["mention"] == pytest.approx((3 / 4 + 2 / 4) / 2)              # mean over pairs, not over responses
    assert d["share_2"] == pytest.approx((1 / 3 + 1) / 2)
    assert d["share_0"] == pytest.approx((1 / 3 + 0) / 2) and d["share_1"] == pytest.approx((1 / 3 + 0) / 2)
    assert 0 <= d["share_2_ci_low"] <= d["share_2"] <= d["share_2_ci_high"] <= 1
    assert A.scope_shares(df, scope, ["m"], ("real_obscure",), ("C2",))["share_2"] == 1.0


@pytest.mark.parametrize("row,supported,phrase", [
    ({"n_pairs": 10, "ci_high": 0.31, "p_holm": 0.004}, True, "so H3 is supported"),
    ({"n_pairs": 10, "ci_high": 0.47, "p_holm": 0.09}, False, "after Holm correction"),   # CI alone is not enough
    ({"n_pairs": 10, "ci_high": 0.52, "p_holm": 0.30}, False, "is not below 50%"),
    ({"n_pairs": 10, "ci_high": 0.50, "p_holm": 0.01}, False, "is not below 50%"),        # the bound must be below
    ({}, False, "could not be evaluated"),
])
def test_h3_rule(row, supported, phrase):
    ok, text = A.h3_verdict(row)
    assert ok is supported and phrase in text


# ---------------------------------------------------------------- inputs

def test_scope_source_follows_the_judge_gate(scenario, tmp_path):
    root, _ = scenario("effect")
    cfg = R.load_config(R.REPO / "models.yaml")
    graded = tmp_path / "graded"
    shutil.copytree(root / "graded", graded)
    source, gate = A.scope_source(graded, cfg)
    assert (source, gate["status"]) == ("judge", "passed") and gate["kappa"] >= 0.6   # the fake judges agree
    path = graded / "judge_crosscheck.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:50]), encoding="utf-8")
    source, gate = A.scope_source(graded, cfg)
    assert (source, gate["status"]) == ("withheld", "pending") and A.load_scope(graded, source, cfg).empty
    assert A.scope_source(graded, cfg, "judge")[0] == "judge"             # forced; the summary flags it
    (graded / "judge_main.jsonl").unlink()
    assert A.scope_source(graded, cfg)[0] == "none"


def test_withheld_judge_results_are_not_reported_and_holm_keeps_eight(tmp_path):
    raw, graded = tmp_path / "raw", tmp_path / "graded"
    S.generate(raw, "effect", seed=SEED)
    S.grade_with_fake_judge(raw, graded, "effect", seed=SEED, crosscheck_agree=0.1)
    res = run(tmp_path, raw, graded)
    assert res["source"] == "withheld" and res["gate"]["status"] == "failed" and not res["forced"]
    h3_text = res["slots"]["H3_SENTENCE"]
    assert h3_text.startswith("Scope accuracy is not reported") and "below the pre-registered 0.6" in h3_text
    rows = res["fam"][("pooled", "real_obscure")]
    h3 = A.find(rows, "H3", "C1-C4 vs 50%", "share of credential mentions scored 2")
    assert np.isnan(h3["p"]) and np.isnan(h3["p_holm"])
    others = [r for r in rows if r["primary"] and r["hypothesis"] != "H3"]
    assert len(others) == 7
    assert np.allclose([r["p_holm"] for r in others], A.holm([r["p"] for r in others] + [1.0])[:-1])
    summary = (tmp_path / "results" / "results_summary.md").read_text(encoding="utf-8")
    assert "Scope-accuracy source: **withheld**" in summary and "Judge results are withheld" in summary
    forced = A.analyse(raw, graded, tmp_path / "forced", tmp_path / "no_pilot", DRAFT, R.REPO / "models.yaml", "judge")
    assert forced["forced"] and "JUDGE RESULTS FORCED" in (tmp_path / "forced" / "results_summary.md").read_text(
        encoding="utf-8")


def test_partial_data_runs_and_pilot_files_are_ignored(scenario, tmp_path):
    root, _ = scenario("effect")
    raw = tmp_path / "raw"
    raw.mkdir()
    lines = (root / "raw" / "gpt-oss-20b.jsonl").read_text(encoding="utf-8").splitlines()
    (raw / "gpt-oss-20b.jsonl").write_text("\n".join(lines[:300]) + "\n", encoding="utf-8")
    shutil.copy(root / "raw" / "qwen3.8-27b.jsonl", raw / "qwen3.8-27b.jsonl")
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    shutil.copy(root / "raw" / "gpt-oss-120b.jsonl", pilot / "gpt-oss-120b.jsonl")   # must not be read
    G.grade_metrics(R.load_config(R.REPO / "models.yaml"), raw, tmp_path / "graded")
    res = run(tmp_path, raw, tmp_path / "graded", pilot=pilot)
    summary = (tmp_path / "results" / "results_summary.md").read_text(encoding="utf-8")
    assert "1260 completed cells" in summary and "gpt-oss-120b" not in summary.split("## Paste")[0]
    assert res["source"] == "none" and res["slots"]["H3_SENTENCE"] == "Scope scores were not available."
    assert not re.search(r"\bnan\b", " ".join(res["slots"].values()))


def test_parse_failures_are_missing_and_reported_by_condition(scenario):
    root, res = scenario("effect")
    df = A.load_responses(root / "raw", MODELS)
    failed = df[df["status"] == "parse_failed"]
    assert len(failed) > 0
    for col_name in ("accepted", "confidence", "mark_cited", "abstained"):
        assert failed[col_name].isna().all(), col_name
    ok = df[df["status"] == "ok"]
    acc = A.acceptance_table(df)
    assert acc[acc["model"] != "pooled"]["n_responses"].sum() == len(ok)       # failures in no denominator
    rng = lambda: np.random.default_rng(0)                                     # noqa: E731
    with_f = A.primary_family(df, pd.DataFrame(columns=["response_id", "score"]), MODELS, A.TYPES, rng())
    without = A.primary_family(ok, pd.DataFrame(columns=["response_id", "score"]), MODELS, A.TYPES, rng())
    for a, b in zip(with_f, without):                                         # the same as dropping them
        assert (a["n_pairs"], a["comparison"]) == (b["n_pairs"], b["comparison"])
        assert a["delta"] == pytest.approx(b["delta"], nan_ok=True)
    table = pd.read_csv(root / "results" / "parse_failures_by_condition.csv")
    assert table["failed"].sum() == len(failed) and set(table["arm"]) == set(A.PF.ARMS)
    assert table.groupby("model")["cells"].sum().to_dict() == df.groupby("model").size().to_dict()
    summary = (root / "results" / "results_summary.md").read_text(encoding="utf-8")
    section = summary.split("## Parse failures")[1].split("## Files")[0]
    assert "| Model | C0 | C1 | C2 | C3 | C4 | C5 | C1+I | C2+I | all |" in section
    assert "nothing is imputed" in section and all(m in section for m in MODELS)
    assert "twice the model's rate" in section or "no parse failures" in section


# ---------------------------------------------------------------- exploratory checks (DEVIATIONS.md)

def test_conclusion_and_outcome():
    assert A.conclusion({}) == "n/a" and A.conclusion({"hypothesis": "H1", "n_pairs": 0}) == "n/a"
    base = {"hypothesis": "H1", "n_pairs": 9, "delta": 0.2}
    assert A.conclusion({**base, "p_holm": 0.01}) == "higher"
    assert A.conclusion({**base, "delta": -0.2, "p_holm": 0.01}) == "lower"
    assert A.conclusion({**base, "p_holm": 0.2}) == "no reliable difference"
    assert A.conclusion({"hypothesis": "H3", "n_pairs": 9, "ci_high": 0.3, "p_holm": 0.01}) == "supported"
    assert A.outcome(["lower", "lower"]) == "same" and A.outcome(["lower", "no reliable difference"]) == "changes"
    assert A.outcome(["lower", "n/a", "lower"]) == "testable only in some" and A.outcome(["n/a", "n/a"]) == "not testable"
    assert A.brief({"n_pairs": 0, "n_ceiling_dropped": 10}) == "n/a: every pair at the C0 ceiling"


def test_bounds_change_only_that_models_failed_cells(scenario):
    root, _ = scenario("effect")
    df = A.load_responses(root / "raw", MODELS)
    hit = (df["model"] == "qwen3.8-27b") & (df["status"] == "parse_failed")
    assert hit.any()
    for v in (0.0, 1.0):
        d = A.with_failed_set(df, "qwen3.8-27b", v)
        assert (d.loc[hit, "accepted"] == v).all() and d.loc[hit, "confidence"].isna().all()
        assert d.loc[~hit, "accepted"].equals(df.loc[~hit, "accepted"])           # nothing else moves
    assert df.loc[hit, "accepted"].isna().all()                                 # the original is untouched


def test_exploratory_robustness_checks_are_written_and_labelled(scenario):
    root, res = scenario("effect")
    out = root / "results"
    w, b = pd.read_csv(out / "robustness_without_qwen.csv"), pd.read_csv(out / "robustness_qwen_bounds.csv")
    assert len(w) == len(b) == 24                                              # 8 primary tests x 3 claim-type sets
    outcomes = {"same", "changes", "testable only in some", "not testable"}
    assert set(w["outcome"]) <= outcomes and set(b["outcome"]) <= outcomes
    df = A.load_responses(root / "raw", MODELS)
    scope = pd.DataFrame(columns=["response_id", "score"])
    kept = [m for m in MODELS if m != "qwen3.8-27b"]
    h4 = A.find(A.primary_family(df, A.load_scope(root / "graded", res["source"], R.load_config(R.REPO / "models.yaml")),
                                 kept, A.TYPES, np.random.default_rng(0)), "H4", "interpreter vs none (C1, C2)")
    row = w[(w["hypothesis"] == "H4") & (w["claim_type"] == "all")].iloc[0]
    assert row["delta_without"] == pytest.approx(h4["delta"])                  # really without qwen
    low = A.primary_family(A.with_failed_set(df, "qwen3.8-27b", 0.0), scope, ["qwen3.8-27b"], ("real_obscure",),
                           np.random.default_rng(0))
    for (h, comp, meas), r in ((k, A.find(low, *k)) for k in (("H1", "C1 vs C0", "acceptance"),
                                                              ("H4", "interpreter vs none (C1, C2)", "acceptance"))):
        got = b[(b["test"] == A.label_of({"hypothesis": h, "comparison": comp, "measure": meas}))
                & (b["claim_type"] == "real_obscure")].iloc[0]
        assert got["delta_false"] == pytest.approx(r["delta"], nan_ok=True)    # the bound really sets them false
    summary = (out / "results_summary.md").read_text(encoding="utf-8")
    section = summary.split("## Exploratory robustness checks (not pre-registered)")[1].split("## Files")[0]
    assert "**Exploratory.**" in section and "DEVIATIONS.md" in section and "treats parse failures as missing" in section
    assert "### 1. Pooled, without qwen3.8-27b" in section and "### 2. Bounds for qwen3.8-27b" in section
    assert section.count("Across all three claim-type sets (24 tests):") == 2
    assert "exploratory" in summary.split("## Other text in REPORT_DRAFT.md to check")[1].split("##")[0]


def test_h4_caveat_when_the_interpreter_arm_fails_more_often(scenario, tmp_path):
    root, res = scenario("effect")
    assert res["caveats"] == []                                                 # failures spread evenly: no caveat
    assert "does not differ reliably" in (root / "results" / "results_summary.md").read_text(encoding="utf-8")
    raw = tmp_path / "raw"
    shutil.copytree(root / "raw", raw)
    path = raw / "qwen3.8-27b.jsonl"
    recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    for interp, target in ((True, 38), (False, 19)):                            # the real pattern: 15.8% vs 7.9%
        arm = [r for r in recs if r["interpreter"] == interp and r["condition"] in ("C1", "C2")]
        for r in [r for r in arm if r["status"] == "ok"][:target - sum(r["status"] == "parse_failed" for r in arm)]:
            r.update(status="parse_failed", parsed=None, raw_text="not json", parse_error="synthetic", attempt=2)
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    G.grade_metrics(R.load_config(R.REPO / "models.yaml"), raw, tmp_path / "graded")
    res2 = run(tmp_path, raw, tmp_path / "graded")
    (caveat,) = res2["caveats"]
    assert caveat.startswith("qwen3.8-27b's interpreter arm had twice the parse-failure rate of the same conditions "
                             "without it (15.8% vs 7.9%), so its own H4 result (interpreter − none = ")
    assert caveat.endswith(") carries that caveat")
    assert res2["slots"]["H4_STAT"].endswith(". " + caveat)                    # §4.7, the report's H4 section
    h4_text = (tmp_path / "results" / "results_summary.md").read_text(encoding="utf-8").split(
        "## Interpreter arm (H4)")[1].split("## Per model")[0]
    assert caveat in h4_text and "Per model: " in h4_text
    depth = 0
    for ch in res2["slots"]["H4_STAT"]:
        depth += (ch == "(") - (ch == ")")
        assert depth <= 1
    filled = (tmp_path / "results" / "REPORT_DRAFT.filled.md").read_text(encoding="utf-8")
    assert caveat + "." in filled.split("**4.7 Countermeasure (H4).**")[1].split("**4.8")[0]


def test_a_model_logging_two_reasoning_settings_is_flagged(scenario, tmp_path):
    root, _ = scenario("null")
    raw = tmp_path / "raw"
    shutil.copytree(root / "raw", raw)
    path = raw / "qwen3.8-27b.jsonl"
    recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    recs[5]["reasoning_setting"] = {"reasoning_effort": "default"}
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    res = run(tmp_path, raw, root / "graded")
    assert res["problems"] and "qwen3.8-27b" in res["problems"][0]
    assert "PROTOCOL CHECK FAILED" in (tmp_path / "results" / "results_summary.md").read_text(encoding="utf-8")
