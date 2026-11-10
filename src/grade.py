"""Grading: deterministic metrics and the two scope-accuracy judges (PREREGISTRATION.md §5, rev 3.4).

  python src/grade.py                  deterministic metrics -> data/graded/responses.csv
  python src/grade.py --judge          main judge on the stratified C1-C4 sample of 600 (concurrent, resumable)
  python src/grade.py --crosscheck     free cross-check judge on 100 of those (at most 48 calls a UTC day)
  python src/grade.py --agreement      weighted kappa between the two judges; no API calls

Reads data/raw only; pilot data is never graded. Raw files are never modified. Judgements go to
data/graded/judge_main.jsonl and judge_crosscheck.jsonl, and every HTTP attempt to the matching
.attempts.jsonl file. Rows by any judge model other than the one in models.yaml are ignored.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import build_documents as B
from src import judge as J
from src import runner as R
from src.judge import response_id
from src.providers import PROVIDERS

REPO = R.REPO
DATA = REPO / "data"
MARK_REASONS = ("document_signature", "document_source_identity")
JUDGED_CONDITIONS = ("C1", "C2", "C3", "C4")
FIELDS = ["response_id", "model", "family", "claim_id", "pair_id", "claim_type", "truth_value", "condition",
          "interpreter", "rep", "status", "accept", "accepted", "abstained", "confidence", "reasons",
          "mark_cited", "justification", "input_tokens", "output_tokens", "cost_usd", "latency_s", "finish_reason"]


def family(model: str) -> str:
    return "gpt-oss" if model.startswith("gpt-oss") else model.split("-")[0].split(".")[0].rstrip("0123456789")


# ---------------------------------------------------------------- deterministic metrics

def final_responses(raw_dir: Path, models) -> list[dict]:
    """One record per completed cell: its ok or parse_failed line (parse_retry lines are kept on disk
    but superseded by the cell's final attempt)."""
    out = []
    for m in models:
        best = {}
        for r in R.read_raw(Path(raw_dir) / f"{m}.jsonl"):
            if r.get("status") in R.DONE_STATUSES:
                best[response_id(r)] = r
        out.extend(best.values())
    return out


def metrics_row(r: dict) -> dict:
    p = r.get("parsed") or {}
    ok = r["status"] == "ok"
    reasons = p.get("reasons") or []
    return {
        "response_id": response_id(r), "model": r["model"], "family": family(r["model"]),
        "claim_id": r["claim_id"], "pair_id": r["pair_id"], "claim_type": r["claim_type"],
        "truth_value": r["truth_value"], "condition": r["condition"], "interpreter": r["interpreter"],
        "rep": r["rep"], "status": r["status"],
        "accept": p.get("accept", "") if ok else "",
        "accepted": int(p["accept"] == "true") if ok else "",
        "abstained": int(p["accept"] == "uncertain" or "cannot_determine" in reasons) if ok else "",
        "confidence": p.get("confidence", "") if ok else "",
        "reasons": ";".join(reasons),
        "mark_cited": int(any(x in reasons for x in MARK_REASONS)) if ok else "",
        "justification": p.get("justification", ""),
        "input_tokens": r.get("input_tokens", ""), "output_tokens": r.get("output_tokens", ""),
        "cost_usd": r.get("cost_usd", ""), "latency_s": r.get("latency_s", ""), "finish_reason": r.get("finish_reason", ""),
    }


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def grade_metrics(cfg, raw_dir: Path, graded_dir: Path) -> list[dict]:
    models = list(cfg["models"])
    rows = [metrics_row(r) for r in final_responses(raw_dir, models)]
    rows.sort(key=lambda x: (x["model"], x["claim_id"], x["condition"], x["interpreter"], x["rep"]))
    write_csv(graded_dir / "responses.csv", rows, FIELDS)
    pf = []
    for m in models:
        lines = R.read_raw(Path(raw_dir) / f"{m}.jsonl")
        cells = [x for x in rows if x["model"] == m]
        failed = sum(x["status"] == "parse_failed" for x in cells)
        pf.append({"model": m, "cells": len(cells), "parse_failed": failed,
                   "parse_failed_rate": round(failed / len(cells), 4) if cells else "",
                   "parse_retries": sum(r.get("status") == "parse_retry" for r in lines),
                   "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in lines), 6)})
    write_csv(graded_dir / "parse_failures.csv", pf, ["model", "cells", "parse_failed", "parse_failed_rate",
                                                      "parse_retries", "cost_usd"])
    print(f"{len(rows)} completed cells -> {graded_dir / 'responses.csv'}")
    for p in pf:
        print(f"  {p['model']:22} cells {p['cells']:4}  parse_failed {p['parse_failed']:3} "
              f"({p['parse_failed_rate'] if p['cells'] else '-'})  retries {p['parse_retries']}  ${p['cost_usd']}")
    return rows


# ---------------------------------------------------------------- stratified sampling

def stratified_sample(rows: list[dict], n: int, seed: int, keys=("model", "condition", "claim_type")) -> list[dict]:
    """Equal allocation across strata (largest remainder, seeded), shortfalls topped up from strata
    with spare items. Deterministic for a given input and seed."""
    rng = random.Random(seed)
    strata: dict[tuple, list[dict]] = {}
    for r in sorted(rows, key=lambda r: r["response_id"]):
        strata.setdefault(tuple(r[k] for k in keys), []).append(r)
    names = sorted(strata)
    if not names or n <= 0:
        return []
    for s in names:
        rng.shuffle(strata[s])
    base, extra = divmod(n, len(names))
    bonus = set(rng.sample(names, extra)) if extra else set()
    take = {s: min(len(strata[s]), base + (s in bonus)) for s in names}
    short = n - sum(take.values())
    while short > 0:
        spare = [s for s in names if take[s] < len(strata[s])]
        if not spare:
            break
        for s in spare:
            if short == 0:
                break
            take[s] += 1
            short -= 1
    return [r for s in names for r in strata[s][:take[s]]]


# ---------------------------------------------------------------- judges (§5, rev 3.4)

KAPPA_THRESHOLD = 0.6
FILES = {"main": ("judge_main.jsonl", "judge_main.attempts.jsonl"),
         "crosscheck": ("judge_crosscheck.jsonl", "judge_crosscheck.attempts.jsonl")}
LABEL = {"main": "main judge", "crosscheck": "cross-check judge"}
SAMPLE_FIELDS = ["response_id", "model", "condition", "claim_type"]


def judge_pool(rows):
    return [r for r in rows if r["status"] == "ok" and str(r["interpreter"]) in ("False", "0", "false")
            and r["condition"] in JUDGED_CONDITIONS]


def judge_rows(graded_dir: Path, role: str, cfg: dict) -> dict[str, dict]:
    """The role's judgements by the model configured in models.yaml, by response. Rows by any other
    judge model are ignored; synthetic rehearsal rows always count."""
    mid = J.judge_config(cfg, role).get("model_id")
    out = {}
    for j in R.read_raw(Path(graded_dir) / FILES[role][0]):
        if j.get("synthetic") or (mid and j.get("judge_model_id") == mid):
            out[j["response_id"]] = j
    return out


def cells_missing(cfg: dict, rows: list[dict]) -> dict[str, int]:
    """Planned main-run cells that have no completed response yet, per model."""
    claims = B.load_claims()
    done = Counter(r["model"] for r in rows)
    out = {}
    for m in cfg["models"]:
        left = len(R.plan_cells(cfg, m, claims)) - done.get(m, 0)
        if left > 0:
            out[m] = left
    return out


def _fixed_sample(path: Path, draw) -> list[str]:
    if path.exists():  # drawn once, so re-runs judge the same responses
        return [r["response_id"] for r in read_csv(path)]
    sample = draw()
    write_csv(path, [{k: r[k] for k in SAMPLE_FIELDS} for r in sample], SAMPLE_FIELDS)
    return [r["response_id"] for r in sample]


def judge_sample_ids(cfg: dict, graded_dir: Path, rows: list[dict]) -> list[str]:
    """The main judge's sample: C1-C4 main-arm responses, stratified by model, condition and claim type."""
    jcfg = J.judge_config(cfg, "main")
    return _fixed_sample(Path(graded_dir) / "judge_sample.csv", lambda: stratified_sample(
        judge_pool(rows), int(jcfg.get("sample_size", 600)), int(jcfg.get("seed", 0))))


def crosscheck_sample_ids(cfg: dict, graded_dir: Path, rows: list[dict]) -> list[str]:
    """The cross-check's 100: a subset of the main judge's sample, stratified the same way."""
    main_ids = set(judge_sample_ids(cfg, graded_dir, rows))
    jcfg = J.judge_config(cfg, "crosscheck")
    return _fixed_sample(Path(graded_dir) / "crosscheck_sample.csv", lambda: stratified_sample(
        [r for r in rows if r["response_id"] in main_ids], int(jcfg.get("sample_size", 100)),
        int(jcfg.get("seed", 1))))


def pilot_judge_check(pilot_dir: Path, model_id) -> str | None:
    """The pilot report's judge-check verdict for this judge model (PASS, FAIL, INCOMPLETE or
    SKIPPED); None if there is no report, or it checked a different model."""
    p = Path(pilot_dir) / "pilot_report.json"
    if not p.exists():
        return None
    rep = json.loads(p.read_text(encoding="utf-8"))
    return rep.get("judge_verdict") if rep.get("judge_model_id") == model_id else None


def run_judge(cfg, graded_dir: Path, role: str = "main", limit=None, force=False,
              pilot_dir: Path = DATA / "pilot", say=print) -> int:
    """Judge the role's sample: the main judge's 600, or the cross-check's 100 of them."""
    graded_dir = Path(graded_dir)
    problems = J.config_problems(cfg, role)
    if problems:
        say(f"The {LABEL[role]} cannot run:")
        for p in problems:
            say(f"  - {p}")
        say("Choosing the judges: RUNBOOK.md section 9.")
        return 1
    jcfg = J.judge_config(cfg, role)
    if role == "main":
        verdict = pilot_judge_check(pilot_dir, jcfg["model_id"])
        if verdict == "FAIL" and not force:
            say(f"{jcfg['model_id']} failed the pilot judge check (data/pilot/pilot_report.md). Pre-registration "
                "§5: correct the request or choose the next candidate before any main-data judging. --force "
                "overrides; record that in DEVIATIONS.md.")
            return 1
        if verdict != "PASS":
            say(f"Note: the pilot has no passed judge check for {jcfg['model_id']} ({verdict or 'none found'}). "
                "Run it first: python src/runner.py --pilot")
    rows = read_csv(graded_dir / "responses.csv")
    missing = cells_missing(cfg, rows)
    if missing and not (graded_dir / "judge_sample.csv").exists() and not force:
        say("The judge sample is drawn once, across every model, so it waits for the main run to finish. "
            "Cells still to run: " + ", ".join(f"{m} {n}" for m, n in missing.items())
            + ". --force draws it now; record that in DEVIATIONS.md.")
        return 1
    ids = judge_sample_ids(cfg, graded_dir, rows) if role == "main" else crosscheck_sample_ids(cfg, graded_dir, rows)
    R.load_env(REPO / ".env")
    key_env = PROVIDERS[jcfg["provider"]].KEY_ENV
    key = os.environ.get(key_env)
    if not key:
        say(f"{key_env} is not set. Add it to .env (RUNBOOK.md section 2).")
        return 1
    ctx = B.load_context()
    claims = {c["id"]: c for c in B.load_claims()}
    by_id = {r["response_id"]: r for r in rows}
    items = []
    for rid in ids:
        r = by_id[rid]
        claim = claims[r["claim_id"]]
        items.append(J.Item(rid, J.credential_facts(ctx, claim, r["condition"]), claim["text"], r["justification"],
                            meta={"seed": R._int_seed(jcfg.get("seed", 0), rid)}))
    out, attempts = (graded_dir / name for name in FILES[role])
    run = J.JudgeRun(jcfg, role, key, out, attempts, stage=role, say=say)
    already = len(set(ids) & set(J.judged(out, jcfg["model_id"])))
    cap = f"; calls so far today {run.calls_today} of {run.day_cap} (UTC day)" if run.day_cap else ""
    say(f"{LABEL[role]} {jcfg['model_id']} via {jcfg['route']['order'][0]}: sample {len(ids)}; already judged "
        f"{already}; to judge {len(ids) - already}{cap}. Ctrl+C stops cleanly.")
    s = run.run(items, limit)
    say(f"{LABEL[role]}: {s['judged_now']} judged in this run ({s['valid_now']} valid); "
        f"{s['items'] - s['remaining']} of {s['items']} in all; ${s['spent_usd']:.4f} spent on this model.")
    if s["stop_reason"]:
        say(f"Stopped: {s['stop_reason']}. Re-run the same command to continue; judged responses are kept.")
    elif s["remaining"] == 0:
        say(f"Every response in the {LABEL[role]}'s sample is judged.")
    report_agreement(cfg, graded_dir, say, quiet_if_none=True)
    return 0 if s["stop_kind"] in (None, "day") else 1


# ---------------------------------------------------------------- agreement between the judges

def weighted_kappa(a, b, categories=("0", "1", "2"), weights="linear") -> float:
    idx = {c: i for i, c in enumerate(categories)}
    k = len(categories)
    obs = np.zeros((k, k))
    for x, y in zip(a, b):
        obs[idx[x], idx[y]] += 1
    n = obs.sum()
    if n == 0:
        return float("nan")
    i, j = np.indices((k, k))
    w = np.abs(i - j) / (k - 1) if weights == "linear" else ((i - j) / (k - 1)) ** 2
    exp = np.outer(obs.sum(1), obs.sum(0)) / n
    denom = (w * exp).sum()
    return float("nan") if denom == 0 else float(1 - (w * obs).sum() / denom)


def cohen_kappa(a, b) -> float:
    cats = sorted(set(a) | set(b))
    if not a:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / len(a)
    pe = sum((a.count(c) / len(a)) * (b.count(c) / len(b)) for c in cats)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def agreement(pairs) -> dict:
    """pairs: (main judge, cross-check judge) scores in {"0","1","2","NA"}, both valid. The weighted
    kappa is over the responses both judges scored 0-2 (§5)."""
    both = [(h, j) for h, j in pairs if h != "NA" and j != "NA"]
    return {"n_items": len(pairs), "n_both_scored": len(both),
            "weighted_kappa_linear": weighted_kappa([h for h, _ in both], [j for _, j in both]),
            "cohen_kappa_4cat": cohen_kappa([h for h, _ in pairs], [j for _, j in pairs]),
            "exact_agreement": (sum(h == j for h, j in pairs) / len(pairs)) if pairs else float("nan"),
            "na_agreement": (sum((h == "NA") == (j == "NA") for h, j in pairs) / len(pairs)) if pairs else float("nan")}


def judge_agreement(cfg: dict, graded_dir: Path) -> dict:
    """Weighted kappa between the two judges on the cross-check sample, overall and per study-model
    family, and the §5 gate: "passed" (kappa >= 0.6), "failed", "pending" (the cross-check, or the
    main judge on the same responses, is unfinished) or "none" (no main-judge scores)."""
    graded_dir = Path(graded_dir)
    main, cross = judge_rows(graded_dir, "main", cfg), judge_rows(graded_dir, "crosscheck", cfg)
    path = graded_dir / "crosscheck_sample.csv"
    ids = [r["response_id"] for r in read_csv(path)] if path.exists() else []
    pairs, fams = [], {}
    for i in ids:
        a, b = main.get(i), cross.get(i)
        if a and b and a.get("valid") and b.get("valid"):
            pair = (str(a["score"]), str(b["score"]))
            pairs.append(pair)
            fams.setdefault(family(i.split("|")[0]), []).append(pair)
    overall = agreement(pairs)
    kappa = overall["weighted_kappa_linear"]
    complete = bool(ids) and all(i in main and i in cross for i in ids)
    status = ("none" if not main else "pending" if not complete
              else "passed" if kappa == kappa and kappa >= KAPPA_THRESHOLD else "failed")
    return {"main_model": J.judge_config(cfg, "main").get("model_id"),
            "crosscheck_model": J.judge_config(cfg, "crosscheck").get("model_id"),
            "threshold": KAPPA_THRESHOLD, "status": status, "kappa": kappa, "complete": complete,
            "n_sample": len(ids), "n_crosschecked": sum(1 for i in ids if i in cross), "n_main_judged": len(main),
            "overall": overall, "by_family": {f: agreement(p) for f, p in sorted(fams.items())}}


def _two(v) -> str:
    return "n/a" if v is None or v != v else f"{float(v):.2f}"


def report_agreement(cfg: dict, graded_dir: Path, say=print, quiet_if_none=False) -> dict:
    graded_dir = Path(graded_dir)
    a = judge_agreement(cfg, graded_dir)
    if quiet_if_none and not a["n_crosschecked"]:
        return a
    graded_dir.mkdir(parents=True, exist_ok=True)
    (graded_dir / "judge_agreement.json").write_text(json.dumps(a, indent=1), encoding="utf-8", newline="\n")
    o = a["overall"]
    say(f"Judges' agreement on the cross-check sample ({a['n_crosschecked']} of {a['n_sample']} cross-checked): "
        f"weighted kappa (linear, responses both scored 0-2) {_two(o['weighted_kappa_linear'])} "
        f"(n={o['n_both_scored']}); Cohen's kappa over 4 categories {_two(o['cohen_kappa_4cat'])}; "
        f"exact agreement {_two(o['exact_agreement'])}; N/A agreement {_two(o['na_agreement'])}")
    for fam, x in a["by_family"].items():
        say(f"  {fam:8} n={x['n_both_scored']:3}  weighted kappa {_two(x['weighted_kappa_linear'])}")
    say({"passed": f"Pre-registered gate (§5): weighted kappa {_two(a['kappa'])} is at least 0.6. PASSED: judge "
                   "results are reported.",
         "failed": f"Pre-registered gate (§5): weighted kappa {_two(a['kappa'])} is below 0.6 or not computable. "
                   "FAILED: judge results are not reported; the paper gives the kappa.",
         "pending": f"Pre-registered gate (§5): PENDING until both judges have scored all {a['n_sample'] or 100} "
                    "cross-check responses.",
         "none": "Pre-registered gate (§5): no main-judge scores yet."}[a["status"]])
    return a


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=REPO / "models.yaml")
    ap.add_argument("--raw-dir", type=Path, default=DATA / "raw")
    ap.add_argument("--graded-dir", type=Path, default=DATA / "graded")
    ap.add_argument("--pilot-dir", type=Path, default=DATA / "pilot")
    ap.add_argument("--judge", action="store_true", help="main judge on the stratified sample (concurrent, resumable)")
    ap.add_argument("--crosscheck", action="store_true",
                    help="free cross-check judge on 100 of the sample (at most 48 calls a UTC day; resumable)")
    ap.add_argument("--agreement", action="store_true", help="weighted kappa between the two judges; no API calls")
    ap.add_argument("--limit", type=int, help="at most this many responses judged in this run")
    ap.add_argument("--force", action="store_true",
                    help="override a refusal: a failed pilot judge check, or drawing the judge sample before the "
                         "main run is complete (record either in DEVIATIONS.md)")
    a = ap.parse_args(argv)
    cfg = R.load_config(a.config)
    if a.agreement and not (a.judge or a.crosscheck):
        report_agreement(cfg, a.graded_dir)
        return 0
    grade_metrics(cfg, a.raw_dir, a.graded_dir)
    status = 0
    if a.judge:
        status = run_judge(cfg, a.graded_dir, "main", a.limit, a.force, a.pilot_dir)
    if a.crosscheck and status == 0:
        status = run_judge(cfg, a.graded_dir, "crosscheck", a.limit, a.force, a.pilot_dir)
    return status


if __name__ == "__main__":
    sys.exit(main())
