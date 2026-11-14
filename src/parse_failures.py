"""Parse failures: where they fall, and what the failed generations look like. Read-only.

A parse failure is a cell whose answer failed to parse on both attempts (status parse_failed). The
analysis treats it as missing data, with no imputation. Its acceptance, confidence and reasons are
empty, so every rate, pair value and test uses the parsed responses only: a claim's value in a
condition is its mean over the reps that parsed.

  python src/parse_failures.py                       every model with failures
  python src/parse_failures.py --model qwen3.8-27b   one model, in detail

It reads data/raw and writes nothing. analyse.py uses it for parse_failures_by_condition.csv,
parse_failure_types.csv and the "Parse failures" section of results_summary.md.

Concentration (a descriptive check, not pre-registered) asks two things: whether any condition's
failure rate is more than double the model's overall rate, and whether a chi-squared test rejects
equal rates across conditions.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import grade as G
from src import runner as R

ARMS = ("C0", "C1", "C2", "C3", "C4", "C5", "C1+I", "C2+I")
REASONS = ("prior_knowledge", "internal_plausibility", "document_signature", "document_source_identity",
           "cited_evidence", "cannot_determine", "other")
# The fine types, and the coarse family each belongs to.
TYPES = {
    "wrong key instead of reasons": "wrong field name",
    "reasons missing": "wrong field name",
    "invalid reason code": "other",
    "repetition loop": "repetition loop",
    "cut off inside the justification": "truncation",
    "derailed at the start": "other",
    "other": "other",
}
_LOOP = re.compile(r"(.{2,40}?)\1{7,}", re.S)
_START = re.compile(r'^\{\s*"accept"\s*:\s*"(true|false|uncertain)"', re.S)
_STRING_FIELD = r'"%s"\s*:\s*"(?:[^"\\]|\\.)*"'


def arm(rec: dict) -> str:
    return rec["condition"] + ("+I" if rec.get("interpreter") in (True, "True", 1, "1") else "")


def classify(text: str | None) -> str:
    """The failure type of one failed generation (the text the model produced).

    Types, checked in this order:
    - repetition loop: a 2-40 character unit repeated 8 or more times in a row;
    - derailed at the start: the text does not open with a valid "accept" field;
    - complete JSON objects: reasons missing, invalid reason code, or a wrong key in place of reasons;
    - cut-off text, by where it stops:
      - cut off inside the justification: the justification string never closes;
      - reasons missing: the text stops, or the object closes, right after the justification;
      - invalid reason code: the reasons list holds a value outside the closed list;
      - wrong key instead of reasons: anything else follows the justification;
    - other: anything else.

    Groq returns a generation only up to the point where it failed schema validation, so most
    texts stop at the first invalid token rather than at the token limit.
    """
    t = (text or "").strip()
    m = _LOOP.search(t)
    if m and len(m.group(0)) >= 30:
        return "repetition loop"
    if not _START.match(t):
        return "derailed at the start"
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        obj = None
    if isinstance(obj, dict):
        if "reasons" not in obj:
            return "wrong key instead of reasons" if set(obj) - {"accept", "confidence", "justification"} \
                else "reasons missing"
        bad = [x for x in obj["reasons"] if x not in REASONS] if isinstance(obj["reasons"], list) else [1]
        return "invalid reason code" if bad else "other"
    j = re.search(_STRING_FIELD % "justification", t, re.S)
    if not j:
        return "cut off inside the justification" if re.search(r'"justification"\s*:\s*"', t) else "other"
    rest = t[j.end():].lstrip()
    if rest in ("", ",") or rest.startswith("}"):
        return "reasons missing"
    if re.match(r',\s*"reasons"\s*:', rest):
        return "invalid reason code"
    return "wrong key instead of reasons"


def cell_frame(raw_dir: Path, models) -> pd.DataFrame:
    """One row per completed cell (its final line), with failed = parse_failed."""
    rows = [{"model": r["model"], "claim_id": r["claim_id"], "pair_id": r["pair_id"], "claim_type": r["claim_type"],
             "truth_value": bool(r["truth_value"]), "condition": r["condition"],
             "interpreter": bool(r["interpreter"]), "arm": arm(r), "failed": r["status"] == "parse_failed",
             "text": r.get("raw_text") or ""}
            for r in G.final_responses(raw_dir, models)]
    return pd.DataFrame(rows, columns=["model", "claim_id", "pair_id", "claim_type", "truth_value", "condition",
                                       "interpreter", "arm", "failed", "text"])


def attempt_frame(raw_dir: Path, models) -> pd.DataFrame:
    """Every attempt that failed to parse (parse_retry and parse_failed lines)."""
    rows = [{"model": r["model"], "arm": arm(r), "final": r["status"] == "parse_failed", "text": r.get("raw_text") or ""}
            for m in models for r in R.read_raw(Path(raw_dir) / f"{m}.jsonl")
            if r.get("status") in ("parse_retry", "parse_failed")]
    return pd.DataFrame(rows, columns=["model", "arm", "final", "text"])


def by_arm(cells: pd.DataFrame) -> pd.DataFrame:
    """Per model and condition (arm): cells, failed, rate, and whether the rate is over double the
    model's overall rate."""
    out = []
    for m, g in cells.groupby("model", sort=False):
        overall = g["failed"].mean()
        for a in [x for x in ARMS if x in set(g["arm"])]:
            s = g[g["arm"] == a]["failed"]
            out.append({"model": m, "arm": a, "cells": len(s), "failed": int(s.sum()), "rate": float(s.mean()),
                        "model_rate": float(overall), "over_double": bool(overall > 0 and s.mean() > 2 * overall)})
    return pd.DataFrame(out, columns=["model", "arm", "cells", "failed", "rate", "model_rate", "over_double"])


def concentration(cells: pd.DataFrame, model: str) -> dict:
    """Overall rate, the range across conditions, conditions over double the rate, a chi-squared test
    of equal rates across conditions, and the interpreter arm against the same conditions without it."""
    g = cells[cells["model"] == model]
    n, k = len(g), int(g["failed"].sum())
    out = {"model": model, "cells": n, "failed": k, "rate": k / n if n else float("nan")}
    if not k:
        return out
    t = by_arm(g)
    hi, lo = t.loc[t["rate"].idxmax()], t.loc[t["rate"].idxmin()]
    out.update(max_arm=hi["arm"], max_rate=float(hi["rate"]), min_arm=lo["arm"], min_rate=float(lo["rate"]),
               over_double=list(t[t["over_double"]]["arm"]))
    table = pd.crosstab(g["arm"], g["failed"])
    if table.shape == (len(t), 2) and len(t) > 1:
        chi2, p, dof, _ = stats.chi2_contingency(table)
        out.update(chi2=float(chi2), dof=int(dof), p=float(p))
    arm_cells = g[g["condition"].isin(["C1", "C2"])]
    if arm_cells["interpreter"].any():
        w, wo = arm_cells[arm_cells["interpreter"]]["failed"], arm_cells[~arm_cells["interpreter"]]["failed"]
        _, p_i = stats.fisher_exact([[int(w.sum()), len(w) - int(w.sum())], [int(wo.sum()), len(wo) - int(wo.sum())]])
        out.update(interp_rate=float(w.mean()), no_interp_rate=float(wo.mean()), interp_p=float(p_i))
    return out


def _pct(v) -> str:
    return f"{v * 100:.1f}%"


def concentration_text(c: dict) -> str:
    if not c["failed"]:
        return f"{c['model']}: no parse failures in {c['cells']} cells."
    flagged = (f"{', '.join(c['over_double'])} exceeded twice the model's rate ({_pct(2 * c['rate'])})"
               if c["over_double"] else f"no condition exceeded twice the model's rate ({_pct(2 * c['rate'])})")
    s = (f"{c['model']}: {c['failed']} of {c['cells']} cells failed to parse ({_pct(c['rate'])}). By condition, "
         f"rates ranged from {_pct(c['min_rate'])} ({c['min_arm']}) to {_pct(c['max_rate'])} ({c['max_arm']}); "
         f"{flagged}.")
    if "p" in c:
        verdict = "differ across conditions" if c["p"] < 0.05 else "do not differ reliably across conditions"
        s += f" Rates {verdict} (χ²({c['dof']}) = {c['chi2']:.1f}, p = {c['p']:.3f})."
    if "interp_rate" in c:
        s += (f" On C1 and C2, {_pct(c['interp_rate'])} of cells with the interpreter failed against "
              f"{_pct(c['no_interp_rate'])} without it (Fisher p = {c['interp_p']:.3f}).")
    return s


def type_table(raw_dir: Path, models) -> pd.DataFrame:
    """Failure types per model: for the final attempt of each failed cell, and for every failed attempt."""
    att = attempt_frame(raw_dir, models)
    if att.empty:
        return pd.DataFrame(columns=["model", "type", "family", "failed_cells", "all_failed_attempts"])
    att = att.assign(type=att["text"].map(classify))
    out = []
    for m, g in att.groupby("model", sort=False):
        for t in TYPES:
            final, every = int(((g["type"] == t) & g["final"]).sum()), int((g["type"] == t).sum())
            if every:
                out.append({"model": m, "type": t, "family": TYPES[t], "failed_cells": final,
                            "all_failed_attempts": every})
    return pd.DataFrame(out).sort_values(["model", "failed_cells", "all_failed_attempts"], ascending=[True, False, False])


def partial_accept(cells: pd.DataFrame, model: str) -> dict:
    """Descriptive only: the accept value a failed cell's final attempt had already written, against
    the parsed cells. A hint about whether the missing cells differ; it is never used as data."""
    g = cells[cells["model"] == model]
    acc = g[g["failed"]]["text"].map(lambda t: (m.group(1) if (m := _START.match(t.strip())) else "none"))
    ok = g[~g["failed"]]["text"].map(lambda t: json.loads(t).get("accept", "none") if t.strip().startswith("{") else "none")
    return {"failed": acc.value_counts().to_dict(), "parsed": ok.value_counts().to_dict()}


def report(raw_dir: Path, model: str) -> str:
    cells = cell_frame(raw_dir, [model])
    if cells.empty:
        return f"No data for {model}."
    c = concentration(cells, model)
    lines = [f"# Parse failures: {model}", "", concentration_text(c), ""]
    if not c["failed"]:
        return "\n".join(lines)
    avg = c["rate"]

    def table(col, labels=None):
        g = cells.groupby(col)["failed"].agg(["sum", "count", "mean"]).reset_index()
        rows = [f"| {labels.get(r[col], r[col]) if labels else r[col]} | {int(r['sum'])} | {int(r['count'])} | "
                f"{_pct(r['mean'])}{' **over double**' if r['mean'] > 2 * avg else ''} |" for _, r in g.iterrows()]
        return [f"| {col} | failed | cells | rate |", "|---|---|---|---|"] + rows + [""]
    lines += ["## By condition (+I: with the interpreter)", "", "| condition | failed | cells | rate |", "|---|---|---|---|"]
    lines += [f"| {r['arm']} | {r['failed']} | {r['cells']} | {_pct(r['rate'])}"
              f"{' **over double**' if r['over_double'] else ''} |" for _, r in by_arm(cells).iterrows()]
    lines += ["", "## By interpreter, claim type and truth value", ""]
    lines += table("interpreter", {True: "with interpreter (C1, C2)", False: "without (C0–C5)"})
    lines += table("claim_type") + table("truth_value", {True: "true twin", False: "false twin"})
    cross = cells.groupby(["arm", "claim_type", "truth_value"])["failed"].agg(["sum", "count", "mean"]).reset_index()
    over = cross[cross["mean"] > 2 * avg]
    lines += ["## Condition × claim type × truth value", "",
              f"{len(cross)} cells of about {int(cross['count'].median())} responses each. Over double the model's rate "
              f"({_pct(2 * avg)}): " + ("; ".join(f"{r['arm']} × {r['claim_type']} × {'true' if r['truth_value'] else 'false'}"
                                          f" {int(r['sum'])}/{int(r['count'])} ({_pct(r['mean'])})"
                                          for _, r in over.iterrows()) or "none") + ".", ""]
    full = cells.groupby(["claim_id", "arm"])["failed"].agg(["sum", "count"])
    lost = full[full["sum"] == full["count"]]
    lines += [f"Claim × condition cells with every rep failed (the claim drops out of that condition): {len(lost)}.", ""]
    types = type_table(raw_dir, [model])
    lines += ["## Failure types", "", "| type | family | failed cells (final attempt) | all failed attempts |",
              "|---|---|---|---|"]
    lines += [f"| {r['type']} | {r['family']} | {r['failed_cells']} | {r['all_failed_attempts']} |" for _, r in types.iterrows()]
    pa = partial_accept(cells, model)
    lines += ["", "## What the failed generations had already said (descriptive; never used as data)", "",
              f"accept in the final attempt of failed cells: {pa['failed']}; in parsed cells: {pa['parsed']}.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=R.REPO / "models.yaml")
    ap.add_argument("--raw-dir", type=Path, default=R.DATA / "raw")
    ap.add_argument("--model", help="one model in detail (default: every model, summary lines)")
    a = ap.parse_args(argv)
    if a.model:
        print(report(a.raw_dir, a.model))
        return 0
    models = list(R.load_config(a.config)["models"])
    cells = cell_frame(a.raw_dir, models)
    for m in models:
        if (cells["model"] == m).any():
            print(concentration_text(concentration(cells, m)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
