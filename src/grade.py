"""Grading: deterministic metrics, the scope-accuracy judge, and human labels (PREREGISTRATION.md §5).

  python src/grade.py                          deterministic metrics -> data/graded/responses.csv
  python src/grade.py --judge                  judge the stratified C1-C4 sample (resumable, paced, blind)
  python src/grade.py --human-sample 30        blind CSV for hand-labelling -> data/human/
  python src/grade.py --import-human data/human/human_sample_30.csv   weighted kappa vs the judge

Reads data/raw only; pilot data is never graded. Raw files are never modified.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import random
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import build_documents as B
from src import runner as R
from src.judge import JudgeClient, JudgeStop, credential_facts, response_id

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


# ---------------------------------------------------------------- judge

def judge_pool(rows):
    return [r for r in rows if r["status"] == "ok" and str(r["interpreter"]) in ("False", "0", "false")
            and r["condition"] in JUDGED_CONDITIONS]


def pilot_judge_passed(pilot_dir: Path):
    """True or False once the pilot's 10 judge calls have returned; None if there is no pilot report
    or its judge check is incomplete (interrupted, quota, server errors)."""
    p = Path(pilot_dir) / "pilot_report.json"
    if not p.exists():
        return None
    v = json.loads(p.read_text(encoding="utf-8")).get("judge_passed")
    return None if v is None else bool(v)


def run_judge(cfg, graded_dir: Path, limit=None, force=False, pilot_dir: Path = DATA / "pilot") -> int:
    jcfg = cfg["judge"]
    passed = pilot_judge_passed(pilot_dir)
    if passed is False and not force:
        print("The judge FAILED the pilot (data/pilot/pilot_report.json). Per PREREGISTRATION.md §5, scope "
              "accuracy comes from hand-labels instead: python src/grade.py --human-sample 150. "
              "Use --force only to collect judge scores as secondary data.")
        return 1
    if passed is None:
        print("Note: the pilot's judge check is missing or incomplete, so the pre-registered pass rule has not "
              "been applied. Finish it first: python src/runner.py --pilot")
    rows = read_csv(graded_dir / "responses.csv")
    sample_path = graded_dir / "judge_sample.csv"
    if sample_path.exists():  # fixed once drawn, so re-runs judge the same responses
        sample_ids = [r["response_id"] for r in read_csv(sample_path)]
    else:
        sample = stratified_sample(judge_pool(rows), int(jcfg.get("sample_size", 600)), int(jcfg.get("seed", 0)))
        write_csv(sample_path, [{"response_id": r["response_id"], "model": r["model"], "condition": r["condition"],
                                 "claim_type": r["claim_type"]} for r in sample],
                  ["response_id", "model", "condition", "claim_type"])
        sample_ids = [r["response_id"] for r in sample]
    by_id = {r["response_id"]: r for r in rows}
    jpath = graded_dir / "judgements.jsonl"
    done = {j["response_id"] for j in R.read_raw(jpath)}
    todo = [i for i in sample_ids if i not in done]
    print(f"judge sample {len(sample_ids)}; already judged {len(sample_ids) - len(todo)}; to judge {len(todo)}")
    if not todo:
        return 0
    R.load_env(REPO / ".env")
    from src.providers import PROVIDERS
    key = os.environ.get(PROVIDERS[jcfg["provider"]].KEY_ENV)
    if not key:
        print(f"{PROVIDERS[jcfg['provider']].KEY_ENV} is not set.")
        return 1
    ctx = B.load_context()
    claims = {c["id"]: c for c in B.load_claims()}
    graded_dir.mkdir(parents=True, exist_ok=True)
    client = JudgeClient(jcfg, key, sleep=lambda s: R.SLEEP(client.stop, s),
                         events_path=graded_dir / "judge.events.jsonl", say=print)
    calls_today = sum(1 for j in R.read_raw(jpath)
                      if str(j.get("timestamp_utc", ""))[:10] == dt.datetime.now(dt.timezone.utc).date().isoformat())
    rpd = (jcfg.get("limits") or {}).get("rpd")
    batch = todo[:limit] if limit else todo
    done_now = 0
    try:
        for k, rid in enumerate(batch, 1):
            if rpd and calls_today >= rpd:
                print(f"Judge RPD {rpd} reached; {R.resume_message(R.utcnow())}. Re-run to continue.")
                return 0
            r = by_id[rid]
            claim = claims[r["claim_id"]]
            try:
                j = client.judge(credential_facts(ctx, claim, r["condition"]), claim["text"], r["justification"],
                                 seed=R._int_seed(jcfg.get("seed", 0), rid), context={"stage": "main", "response_id": rid})
            except JudgeStop as e:
                print(f"Judge stopped: {e}. Re-run to continue; finished judgements are kept.")
                return 1
            calls_today += 1
            R.append_jsonl(jpath, {"response_id": rid, "timestamp_utc": R.utcnow().isoformat(),
                                   "judge_model_id": jcfg["model_id"], **j})
            done_now = k
            if k % 25 == 0 or k == len(batch):
                print(f"  judged {k}/{len(batch)}")
    except KeyboardInterrupt:
        print(f"Interrupted: {done_now} judged in this run, {len(sample_ids) - len(todo) + done_now} of "
              f"{len(sample_ids)} in all, saved in {jpath}. Re-run the same command to continue.")
        return 1
    return 0


def latest_judgements(graded_dir: Path) -> dict[str, dict]:
    out = {}
    for j in R.read_raw(Path(graded_dir) / "judgements.jsonl"):
        out[j["response_id"]] = j
    return out


# ---------------------------------------------------------------- human labels

HOW_TO = """# Hand-labelling scope accuracy

Open the human_sample CSV in a spreadsheet. For each row, read the credential facts, the statement
and the explanation, and put one of 2, 1, 0 or NA in the `score` column:

- **2**: the explanation correctly says what the credential certifies AND that it does not bear on
  whether the statement is true.
- **1**: it refers to what the credential covers only partially or vaguely.
- **0**: it treats the credential as support for the statement, or misattributes it (for example,
  says the signer vouched for a statement the facts say was only gathered, not attributed).
- **NA**: it does not mention the credential, signature, signer or manifest at all.

Judge only the explanation's account of the credential, not whether the statement is true. Do not
open the human_key file until you have finished: it reveals model, condition and truth value.
Save as CSV (keep the columns), then run:
    python src/grade.py --import-human data/human/human_sample_<N>.csv
"""


def human_sample(cfg, graded_dir: Path, human_dir: Path, n: int, overwrite=False) -> int:
    out = human_dir / f"human_sample_{n}.csv"
    key = human_dir / f"human_key_{n}.csv"
    if out.exists() and not overwrite:
        print(f"{out} already exists (it may hold your labels). Use --overwrite to replace it.")
        return 1
    rows = read_csv(graded_dir / "responses.csv")
    judged = {k for k, j in latest_judgements(graded_dir).items() if j.get("valid")}
    pool = [r for r in judge_pool(rows) if r["response_id"] in judged] if judged else judge_pool(rows)
    source = "judged responses (for agreement)" if judged else "all C1-C4 responses"
    sample = stratified_sample(pool, n, seed=int(cfg["judge"].get("seed", 0)) + n, keys=("model", "condition"))
    random.Random(n).shuffle(sample)
    ctx = B.load_context()
    claims = {c["id"]: c for c in B.load_claims()}
    items, keys = [], []
    for i, r in enumerate(sample, 1):
        claim = claims[r["claim_id"]]
        items.append({"item": i, "credential_facts": credential_facts(ctx, claim, r["condition"]),
                      "statement": claim["text"], "explanation": r["justification"], "score": "", "notes": ""})
        keys.append({"item": i, "response_id": r["response_id"], "model": r["model"], "family": r["family"],
                     "condition": r["condition"], "claim_type": r["claim_type"], "truth_value": r["truth_value"]})
    write_csv(out, items, ["item", "credential_facts", "statement", "explanation", "score", "notes"])
    write_csv(key, keys, ["item", "response_id", "model", "family", "condition", "claim_type", "truth_value"])
    (human_dir / "HOW_TO_LABEL.md").write_text(HOW_TO, encoding="utf-8", newline="\n")
    print(f"{len(items)} items from {source} -> {out}\nkey (do not open while labelling) -> {key}\n"
          f"instructions -> {human_dir / 'HOW_TO_LABEL.md'}")
    return 0


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
    """pairs: list of (human, judge) scores in {"0","1","2","NA"}."""
    both = [(h, j) for h, j in pairs if h != "NA" and j != "NA"]
    return {"n_items": len(pairs), "n_both_scored": len(both),
            "weighted_kappa_linear": weighted_kappa([h for h, _ in both], [j for _, j in both]),
            "cohen_kappa_4cat": cohen_kappa([h for h, _ in pairs], [j for _, j in pairs]),
            "exact_agreement": (sum(h == j for h, j in pairs) / len(pairs)) if pairs else float("nan"),
            "na_agreement": (sum((h == "NA") == (j == "NA") for h, j in pairs) / len(pairs)) if pairs else float("nan")}


def import_human(graded_dir: Path, path: Path, key_path: Path | None = None) -> int:
    labels = read_csv(path)
    key_path = key_path or path.with_name(path.name.replace("human_sample_", "human_key_"))
    key = {r["item"]: r for r in read_csv(key_path)}
    bad, scored = [], []
    for r in labels:
        s = (r.get("score") or "").strip().upper().replace("N/A", "NA")
        if s not in ("0", "1", "2", "NA"):
            bad.append(r["item"])
        else:
            scored.append({**key[r["item"]], "human_score": s})
    if bad:
        print(f"{len(bad)} items have no valid score (need 2, 1, 0 or NA): {bad[:20]}{' ...' if len(bad) > 20 else ''}")
        return 1
    judged = latest_judgements(graded_dir)
    for s in scored:
        j = judged.get(s["response_id"])
        s["judge_score"] = j["score"] if j and j.get("valid") else ""
    n = len(scored)
    write_csv(graded_dir / f"human_labels_{n}.csv", scored,
              ["item", "response_id", "model", "family", "condition", "claim_type", "truth_value", "human_score", "judge_score"])
    pairs = [(s["human_score"], s["judge_score"]) for s in scored if s["judge_score"]]
    result = {"labels_file": str(path), "n_labelled": n, "overall": agreement(pairs), "by_family": {}}
    for fam in sorted({s["family"] for s in scored}):
        result["by_family"][fam] = agreement([(s["human_score"], s["judge_score"]) for s in scored
                                              if s["family"] == fam and s["judge_score"]])
    (graded_dir / f"agreement_{n}.json").write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
    o = result["overall"]
    print(f"{n} labels imported -> {graded_dir / f'human_labels_{n}.csv'}")
    if pairs:
        print(f"judge-human agreement on {o['n_items']} items: weighted kappa (linear, items both scored 0-2) "
              f"{o['weighted_kappa_linear']:.2f} (n={o['n_both_scored']}); exact {o['exact_agreement']:.2f}; "
              f"NA agreement {o['na_agreement']:.2f}")
        for fam, a in result["by_family"].items():
            print(f"  {fam:8} n={a['n_items']:3}  weighted kappa {a['weighted_kappa_linear']:.2f}")
    else:
        print("No judge scores for these items: agreement not computed (labels saved for analysis).")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=REPO / "models.yaml")
    ap.add_argument("--raw-dir", type=Path, default=DATA / "raw")
    ap.add_argument("--graded-dir", type=Path, default=DATA / "graded")
    ap.add_argument("--human-dir", type=Path, default=DATA / "human")
    ap.add_argument("--pilot-dir", type=Path, default=DATA / "pilot")
    ap.add_argument("--judge", action="store_true", help="judge the stratified sample (resumable)")
    ap.add_argument("--limit", type=int, help="max judge calls this run")
    ap.add_argument("--force", action="store_true", help="run the judge even though it failed the pilot")
    ap.add_argument("--human-sample", type=int, metavar="N", help="write a blind CSV of N items to hand-label")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--import-human", type=Path, metavar="CSV", help="import hand-labels; report weighted kappa")
    ap.add_argument("--key", type=Path, help="key file for --import-human (default: matching human_key_N.csv)")
    a = ap.parse_args(argv)
    cfg = R.load_config(a.config)
    if a.import_human:
        return import_human(a.graded_dir, a.import_human, a.key)
    grade_metrics(cfg, a.raw_dir, a.graded_dir)
    if a.judge:
        return run_judge(cfg, a.graded_dir, a.limit, a.force, a.pilot_dir)
    if a.human_sample:
        return human_sample(cfg, a.graded_dir, a.human_dir, a.human_sample, a.overwrite)
    return 0


if __name__ == "__main__":
    sys.exit(main())
