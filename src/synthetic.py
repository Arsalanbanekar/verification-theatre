"""Synthetic study data in the runner's raw-line format, for testing grade.py and analyse.py
before real data exists (CLAUDE.md: write the analysis against fake data first).

  python src/synthetic.py --out data/synthetic/raw --scenario effect   (or null)
  python src/synthetic.py --graded-dir data/synthetic/graded           (also grade it, with fake judge scores)

Every line carries "synthetic": true. Scenarios:
- null:   acceptance depends on claim type and truth only; marks, conditions and the interpreter
          change nothing.
- effect: C1-C4 raise acceptance by INFLATION for both twins (more on invented claims), C5 raises
          true twins and lowers false ones, and the interpreter removes part of the C1/C2 rise.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import build_documents as B
from src import runner as R
from src.providers import PROVIDERS

INFLATION = 0.30          # C1-C4 rise in P(accept) in the effect scenario (real-obscure)
INVENTED_EXTRA = 0.10     # extra rise on invented items (H5 direction)
INTERPRETER_CUT = 0.20    # how much of the C1/C2 rise the interpreter removes
C5_TRUE, C5_FALSE = 0.35, -0.25
BASE = {("real_obscure", True): 0.45, ("real_obscure", False): 0.40,
        ("invented", True): 0.15, ("invented", False): 0.15}
PARSE_FAIL_RATE = 0.01


def p_accept(scenario: str, claim: dict, condition: str, interpreter: bool) -> float:
    p = BASE[(claim["claim_type"], claim["truth_value"])]
    if scenario == "effect":
        if condition in ("C1", "C2", "C3", "C4"):
            p += INFLATION + (INVENTED_EXTRA if claim["claim_type"] == "invented" else 0.0)
            if interpreter:
                p -= INTERPRETER_CUT
        if condition == "C5":
            p += C5_TRUE if claim["truth_value"] else C5_FALSE
    return min(0.97, max(0.03, p))


def justification(rng, condition: str, accepted: bool) -> str:
    if condition == "C0":
        return "I have no specific knowledge of this and the document gives no supporting evidence."
    options = ["The document is signed by a trusted signer, so the statement is likely accurate.",
               "The credentials only show who produced the file and that it is unchanged; they do not "
               "establish whether the statement is true.",
               "The manifest is valid, but I cannot verify the specific figure."]
    return options[0] if accepted and rng.random() < 0.7 else rng.choice(options[1:])


def generate(out_dir: Path, scenario: str = "effect", seed: int = 0, cfg: dict | None = None) -> dict:
    cfg = cfg or R.load_config(R.REPO / "models.yaml")
    claims = B.load_claims()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for k, name in enumerate(cfg["models"]):
        rng = random.Random(f"{seed}|{scenario}|{name}")
        model_shift = (k - 1.5) * 0.03  # small, fixed differences between models
        lines = []
        for cell in R.plan_cells(cfg, name, claims):
            claim = next(c for c in claims if c["id"] == cell.claim_id)
            p = min(0.97, max(0.03, p_accept(scenario, claim, cell.condition, cell.interpreter) + model_shift))
            failed = rng.random() < PARSE_FAIL_RATE
            if failed:
                parsed = None
            else:
                accepted = rng.random() < p
                accept = "true" if accepted else rng.choice(["false", "uncertain"])
                marked = cell.condition != "C0"
                reasons = ["prior_knowledge" if rng.random() < 0.3 else "internal_plausibility"]
                if marked and rng.random() < (0.6 if accepted else 0.3):
                    reasons.append("document_signature")
                if accept == "uncertain":
                    reasons.append("cannot_determine")
                parsed = {"accept": accept, "confidence": int(min(100, max(0, rng.gauss(55 + 25 * accepted, 12)))),
                          "reasons": reasons, "justification": justification(rng, cell.condition, accepted)}
            usage = {"prompt_tokens": 1400, "completion_tokens": 150, "total_tokens": 1550}
            lines.append({
                "schema": 1, "synthetic": True, "model": name, "provider": cfg["models"][name]["provider"],
                "model_id": cfg["models"][name]["model_id"], "claim_id": cell.claim_id, "pair_id": claim["pair_id"],
                "claim_type": claim["claim_type"], "truth_value": claim["truth_value"], "condition": cell.condition,
                "interpreter": cell.interpreter, "rep": cell.rep, "attempt": 2 if failed else 1,
                "temperature": R.setting(cfg, name, "temperature"),
                "reasoning_setting": PROVIDERS[cfg["models"][name]["provider"]].reasoning_setting(cfg["models"][name]),
                "raw_text": json.dumps(parsed) if parsed else "not json", "parsed": parsed,
                "parse_error": "synthetic parse failure" if failed else None,
                "status": "parse_failed" if failed else "ok", "usage": usage,
                "input_tokens": 1400, "output_tokens": 150, "cost_usd": 0.0, "latency_s": 1.0, "finish_reason": "stop",
                "pacific_date": "2026-11-13", "timestamp_utc": "2026-11-13T12:00:00+00:00"})
        with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        counts[name] = len(lines)
    return counts


def synthetic_judgements(graded_dir: Path, scenario: str = "effect", seed: int = 0) -> int:
    """Judge scores for the responses in graded_dir/judge_sample.csv: mostly 0 when the mark is read
    as support (effect), evenly spread in the null scenario."""
    import csv
    graded_dir = Path(graded_dir)
    rng = random.Random(f"{seed}|judge|{scenario}")
    with open(graded_dir / "judge_sample.csv", encoding="utf-8") as f:
        sample = list(csv.DictReader(f))
    with open(graded_dir / "judgements.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for s in sample:
            weights = [0.5, 0.25, 0.1, 0.15] if scenario == "effect" else [0.25, 0.25, 0.25, 0.25]
            score = rng.choices(["0", "1", "2", "NA"], weights)[0]
            f.write(json.dumps({"response_id": s["response_id"], "synthetic": True, "score": score,
                                "valid": True, "reason": "synthetic"}) + "\n")
    return len(sample)


def grade_with_fake_judge(raw_dir: Path, graded_dir: Path, scenario: str = "effect", seed: int = 0) -> int:
    """Grade synthetic raw data and add fake judge scores, drawing the judge sample exactly as
    grade.py --judge would. No API call is made."""
    from src import grade as G
    cfg = R.load_config(R.REPO / "models.yaml")
    rows = G.grade_metrics(cfg, Path(raw_dir), Path(graded_dir))
    jcfg = cfg["judge"]
    sample = G.stratified_sample(G.judge_pool(rows), int(jcfg.get("sample_size", 600)), int(jcfg.get("seed", 0)))
    G.write_csv(Path(graded_dir) / "judge_sample.csv",
                [{"response_id": r["response_id"], "model": r["model"], "condition": r["condition"],
                  "claim_type": r["claim_type"]} for r in sample], ["response_id", "model", "condition", "claim_type"])
    return synthetic_judgements(graded_dir, scenario, seed)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=R.DATA / "synthetic" / "raw")
    ap.add_argument("--scenario", choices=("effect", "null"), default="effect")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--graded-dir", type=Path, help="also grade it there and add fake judge scores (rehearsal)")
    a = ap.parse_args(argv)
    counts = generate(a.out, a.scenario, a.seed)
    print(f"synthetic {a.scenario} data -> {a.out}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if a.graded_dir:
        n = grade_with_fake_judge(a.out, a.graded_dir, a.scenario, a.seed)
        print(f"fake judge scores for {n} sampled responses -> {a.graded_dir / 'judgements.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
