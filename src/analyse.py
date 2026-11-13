"""Analysis per PREREGISTRATION.md §7 (rev 3.3). Reads data/raw and data/graded; never data/pilot.

  python src/analyse.py                         -> data/results/
  python src/analyse.py --raw-dir data/synthetic/raw --graded-dir data/synthetic/graded       --out data/synthetic/results              (rehearsal on fake data)

Outputs: CSV tables, four figures, results_summary.md (ready-to-paste text for every {PLACEHOLDER}
in REPORT_DRAFT.md) and REPORT_DRAFT.filled.md (the draft with those slots substituted, to check).

The tests and decision rules are specified in PREREGISTRATION.md §7 ("Tests and decision rules",
rev 3.3). This file implements them:
- Pair values: claim mean over reps; pair = mean of twins (or true minus false for the
  discrimination index); pooled results weight models equally.
- Paired t-tests over pairs with 95% t-intervals (one-sample for H3, Welch for H5); sign-flip
  permutation p-values over the same differences as a robustness check (exact for <= 16 pairs,
  else 20,000 seeded flips), Holm-adjusted the same way and flagged where they disagree.
- Holm over the eight tests of the six primary comparisons, within each reporting scope and
  claim-type set. Inflation tests drop pairs at C0 ceiling in that scope.
- H3 is supported only if the upper bound of the 95% CI for the share of credential-mentioning
  justifications scored 2 is below 0.5 and its p_holm < .05. The full 0/1/2 distribution and the
  share mentioning the credential are reported with CIs.
- Judge results (rev 3.4) are used only if the two judges' linear-weighted kappa on the 100
  cross-checked responses is at least 0.6. Until then, or if it is lower, they are withheld: H3
  is not tested and enters Holm with p = 1, so the family stays at eight.
- Descriptive 95% CIs (acceptance by condition, discrimination index, scope shares): t-intervals
  over claims or pairs, clipped to the possible range.
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import grade as G
from src import judge as J
from src import runner as R

REPO = R.REPO
DATA = REPO / "data"
CONDITIONS = ("C0", "C1", "C2", "C3", "C4", "C5")
MARKED = ("C1", "C2", "C3", "C4")
TYPES = ("real_obscure", "invented")
TYPE_SETS = {"all": TYPES, "real_obscure": ("real_obscure",), "invented": ("invented",)}
TYPE_LABEL = {"real_obscure": "real-obscure", "invented": "invented", "all": "all pairs"}
B_PERM, EXACT_MAX, SEED, ALPHA = 20000, 16, 20261113, 0.05
MINUS = "−"
NO_VALUE = "NO AUTOMATIC VALUE: fill by hand from the tables below."

# Chart tokens: the dataviz reference palette on a light surface (categorical blue/orange; the
# ordinal blue ramp for scores 0-2). Checked with the palette validator: all checks pass.
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
SCORE_COLORS = {"0": "#86b6ef", "1": "#2a78d6", "2": "#104281", "NA": "#c8c7c0"}


# ---------------------------------------------------------------- loading

def load_responses(raw_dir: Path, models) -> pd.DataFrame:
    rows = [{**G.metrics_row(r), "synthetic": bool(r.get("synthetic")), "timestamp_utc": r.get("timestamp_utc") or ""}
            for r in G.final_responses(raw_dir, models)]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col_name in ("accepted", "confidence", "mark_cited", "abstained", "rep"):
        df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
    df["truth_value"] = df["truth_value"].astype(bool)
    df["interpreter"] = df["interpreter"].astype(bool)
    return df


def scope_source(graded_dir: Path, cfg: dict, requested: str = "auto") -> tuple[str, dict]:
    """(source, gate). Sources:
    - "judge": the main judge's scores, used because the judges agree (§5, rev 3.4: kappa >= 0.6);
    - "withheld": scores exist, but the cross-check is unfinished or kappa is below 0.6;
    - "none": no scores.
    requested="judge" uses the scores whatever the gate says; the summary flags that."""
    gate = G.judge_agreement(cfg, graded_dir)
    has_scores = any(j.get("valid") for j in G.judge_rows(graded_dir, "main", cfg).values())
    if requested == "none" or not has_scores:
        return "none", gate
    if requested == "judge" or gate["status"] == "passed":
        return "judge", gate
    return "withheld", gate


def load_scope(graded_dir: Path, source: str, cfg: dict) -> pd.DataFrame:
    rows = []
    if source == "judge":
        rows = [{"response_id": k, "score": str(j["score"])} for k, j in G.judge_rows(graded_dir, "main", cfg).items()
                if j.get("valid")]
    return pd.DataFrame(rows, columns=["response_id", "score"])


# ---------------------------------------------------------------- pair-level values

def pair_values(df: pd.DataFrame, models, interpreter: bool, which, measure: str = "accepted") -> pd.DataFrame:
    """Index (pair_id, claim_type); one column per condition.
    which: 'both' (mean of twins), True / False (one twin), or 'disc' (true minus false)."""
    d = df[df["model"].isin(models) & (df["interpreter"] == interpreter)].dropna(subset=[measure])
    if d.empty:
        return pd.DataFrame()
    claim = d.groupby(["model", "pair_id", "claim_type", "truth_value", "condition"])[measure].mean()
    keys = ["model", "pair_id", "claim_type", "condition"]
    if which == "both":
        v = claim.groupby(keys).mean()
    elif which == "disc":
        c = claim.unstack("truth_value")
        if True not in c.columns or False not in c.columns:
            return pd.DataFrame()
        v = (c[True] - c[False]).dropna()
    else:
        try:
            v = claim.xs(which, level="truth_value")
        except KeyError:
            return pd.DataFrame()
    if v.empty:
        return pd.DataFrame()
    return v.groupby(["pair_id", "claim_type", "condition"]).mean().unstack("condition")


def ceiling_pairs(df, models) -> set:
    """Pairs whose twins were both accepted in every C0 response (in this model scope)."""
    w = pair_values(df, models, False, "both")
    if w.empty or "C0" not in w:
        return set()
    return {idx[0] for idx, v in w["C0"].items() if v >= 1 - 1e-12}


def subset(wide: pd.DataFrame, types, drop=()) -> pd.DataFrame:
    if wide.empty:
        return wide
    return wide.loc[[i for i in wide.index if i[1] in types and i[0] not in drop]]


def col(w: pd.DataFrame, c) -> pd.Series:
    return w[c] if (not w.empty and c in w) else pd.Series(dtype=float)


# ---------------------------------------------------------------- statistics

def signflip_p(x, rng, center: float = 0.0) -> float:
    x = np.asarray(x, float) - center
    n = len(x)
    if n == 0:
        return float("nan")
    obs = abs(x.mean())
    if n <= EXACT_MAX:
        signs = np.array(list(itertools.product((-1.0, 1.0), repeat=n)))
        return float(np.mean(np.abs(signs @ x / n) >= obs - 1e-12))
    signs = rng.choice((-1.0, 1.0), size=(B_PERM, n))
    return float((np.sum(np.abs(signs @ x / n) >= obs - 1e-12) + 1) / (B_PERM + 1))


def min_p(n: int) -> float:
    """Smallest two-sided p the sign-flip test can return with n pairs."""
    if n == 0:
        return float("nan")
    return 2 / 2 ** n if n <= EXACT_MAX else 1 / (B_PERM + 1)


def t_ci(x, lo_bound=-np.inf, hi_bound=np.inf) -> tuple[float, float]:
    """95% t-interval for a mean, clipped to the possible range."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return float("nan"), float("nan")
    half = sps.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n)
    m = x.mean()
    return float(max(lo_bound, m - half)), float(min(hi_bound, m + half))


def t_test(x, center: float = 0.0) -> tuple[float, float, float, float]:
    """mean, CI low, CI high, two-sided p for H0: mean == center."""
    x = np.asarray(x, float)
    n, m = len(x), float(np.mean(x)) if len(x) else float("nan")
    if n < 2:
        return m, float("nan"), float("nan"), float("nan")
    se = x.std(ddof=1) / np.sqrt(n)
    lo, hi = t_ci(x)
    if se <= 1e-12:  # every pair moved by the same amount (up to rounding)
        return m, lo, hi, (1.0 if abs(m - center) <= 1e-12 else 0.0)
    return m, lo, hi, float(2 * sps.t.sf(abs((m - center) / se), n - 1))


EMPTY = {"n_pairs": 0, "delta": np.nan, "ci_low": np.nan, "ci_high": np.nan, "p": np.nan,
         "p_perm": np.nan, "p_perm_min": np.nan, "sd": np.nan}


def one_sample(x, center: float, rng) -> dict:
    x = pd.Series(x, dtype=float).dropna()
    if x.empty:
        return dict(EMPTY)
    m, lo, hi, p = t_test(x.values, center)
    return {"n_pairs": len(x), "delta": m, "ci_low": lo, "ci_high": hi, "p": p,
            "p_perm": signflip_p(x.values, rng, center), "p_perm_min": min_p(len(x)),
            "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan}


def minus(b: pd.Series, a: pd.Series) -> pd.Series:
    """b - a over pairs present in both (empty if either side has no data)."""
    if len(a) == 0 or len(b) == 0:
        return pd.Series(dtype=float)
    return (b - a).dropna()


def paired(a: pd.Series, b: pd.Series, rng) -> dict:
    """b minus a over pairs present in both."""
    return one_sample(minus(b, a), 0.0, rng)


def holm(ps) -> list[float]:
    idx = [i for i, p in enumerate(ps) if p == p]  # NaN (no data) takes no part
    order = sorted(idx, key=lambda i: ps[i])
    out, running, m = [float("nan")] * len(ps), 0.0, len(order)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * ps[i]))
        out[i] = running
    return out


# ---------------------------------------------------------------- the primary family

def scope_pairs(df, scope, models, types) -> pd.Series:
    """Per pair: share of credential-mentioning C1-C4 justifications scored 2 (main arm)."""
    if scope.empty:
        return pd.Series(dtype=float)
    d = df[df["model"].isin(models) & ~df["interpreter"] & df["condition"].isin(MARKED)
           & df["claim_type"].isin(types)].merge(scope, on="response_id")
    d = d[d["score"] != "NA"]
    if d.empty:
        return pd.Series(dtype=float)
    d = d.assign(correct=(d["score"] == "2").astype(float))
    return d.groupby(["model", "pair_id", "claim_type"])["correct"].mean().groupby(["pair_id", "claim_type"]).mean()


def primary_family(df, scope, models, types, rng) -> list[dict]:
    rows = []
    both = pair_values(df, models, False, "both")
    conf = pair_values(df, models, False, "both", "confidence")
    disc = pair_values(df, models, False, "disc")
    drop = ceiling_pairs(df, models)

    def add(h, comparison, measure, unit, res, sample, primary=True):
        dropped = len(drop & set(i[0] for i in subset(both, types).index)) if "dropped" in sample else 0
        rows.append({"hypothesis": h, "comparison": comparison, "measure": measure, "unit": unit,
                     "sample": sample, "primary": primary, "n_ceiling_dropped": dropped, **res})

    strat, full = subset(both, types, drop), subset(both, types)
    for h, a, b in (("H1", "C0", "C1"), ("H2", "C2", "C3"), ("H2", "C1", "C4"), ("H2", "C3", "C4")):
        add(h, f"{b} vs {a}", "acceptance", "pp", paired(col(strat, a), col(strat, b), rng), "C0-ceiling pairs dropped")
        add(h, f"{b} vs {a}", "acceptance", "pp", paired(col(full, a), col(full, b), rng), "all pairs", primary=False)
        if (a, b) == ("C2", "C3"):
            sc, fc = subset(conf, types, drop), subset(conf, types)
            add(h, "C3 vs C2", "confidence", "conf", paired(col(sc, "C2"), col(sc, "C3"), rng), "C0-ceiling pairs dropped")
            add(h, "C3 vs C2", "confidence", "conf", paired(col(fc, "C2"), col(fc, "C3"), rng), "all pairs", primary=False)
    ds = subset(disc, types)
    add("H2b", "C5 vs C0", "discrimination index", "pp", paired(col(ds, "C0"), col(ds, "C5"), rng), "all pairs")
    marked = ds[[c for c in MARKED if c in ds]].mean(axis=1) if not ds.empty else pd.Series(dtype=float)
    add("H2b", "C1-C4 mean vs C0", "discrimination index", "pp", paired(col(ds, "C0"), marked, rng), "all pairs",
        primary=False)
    add("H3", "C1-C4 vs 50%", "share of credential mentions scored 2", "share",
        one_sample(scope_pairs(df, scope, models, types), 0.5, rng), "all pairs")
    interp_models = [m for m in models if ((df["model"] == m) & df["interpreter"]).any()]
    res = dict(EMPTY)
    if interp_models:
        none = subset(pair_values(df, interp_models, False, "both"), types)
        withi = subset(pair_values(df, interp_models, True, "both"), types)
        arm = [c for c in ("C1", "C2") if c in none and c in withi]  # like with like, e.g. after a cut to C1 only
        a = none[arm].mean(axis=1) if arm else pd.Series(dtype=float)
        b = withi[arm].mean(axis=1) if arm else pd.Series(dtype=float)
        res = paired(a, b, rng)
        gap = minus(a, col(none, "C0"))
        res["gap_without_interpreter"] = float(gap.mean()) if len(gap) else np.nan
    add("H4", "interpreter vs none (C1, C2)", "acceptance", "pp", res, "all pairs")
    prim = [r for r in rows if r["primary"]]
    for key in ("p", "p_perm"):
        # rev 3.4: an untested H3 (judge results withheld) keeps its place in the family with p = 1
        untested = [r["hypothesis"] == "H3" and isnan(r[key]) for r in prim]
        for r, ph, u in zip(prim, holm([1.0 if u else r[key] for r, u in zip(prim, untested)]), untested):
            r[f"{key}_holm"] = np.nan if u else ph
    for r in rows:
        r.setdefault("p_holm", np.nan)
        r.setdefault("p_perm_holm", np.nan)
    return rows


def h5(df, models, rng) -> dict:
    """Exploratory: C1 - C0 acceptance on invented pairs minus the same on real-obscure pairs."""
    w = subset(pair_values(df, models, False, "both"), TYPES, ceiling_pairs(df, models))
    if w.empty or "C1" not in w or "C0" not in w:
        return {}
    d = (w["C1"] - w["C0"]).dropna()
    inv = d[[i[1] == "invented" for i in d.index]].values
    real = d[[i[1] == "real_obscure" for i in d.index]].values
    if len(inv) == 0 or len(real) == 0:
        return {}
    obs = float(inv.mean() - real.mean())
    va = inv.var(ddof=1) / len(inv) if len(inv) > 1 else np.nan
    vb = real.var(ddof=1) / len(real) if len(real) > 1 else np.nan
    se = np.sqrt(va + vb)
    if se > 0:  # Welch
        dof = (va + vb) ** 2 / ((va ** 2 / (len(inv) - 1) if va else 0) + (vb ** 2 / (len(real) - 1) if vb else 0))
        half, p = sps.t.ppf(0.975, dof) * se, float(2 * sps.t.sf(abs(obs) / se, dof))
    else:
        half, p = (0.0, 1.0 if obs == 0 else 0.0) if se == 0 else (np.nan, np.nan)
    pooled, n_perm = np.concatenate([inv, real]), B_PERM // 4
    perm = np.empty(n_perm)
    for k in range(n_perm):
        s = rng.permutation(pooled)
        perm[k] = s[:len(inv)].mean() - s[len(inv):].mean()
    i, r = one_sample(inv, 0.0, rng), one_sample(real, 0.0, rng)
    return {"n_invented": len(inv), "n_real": len(real),
            "invented_delta": i["delta"], "invented_ci_low": i["ci_low"], "invented_ci_high": i["ci_high"],
            "invented_p": i["p"], "invented_p_perm": i["p_perm"],
            "real_delta": r["delta"], "real_ci_low": r["ci_low"], "real_ci_high": r["ci_high"], "real_p": r["p"],
            "difference": obs, "ci_low": obs - half, "ci_high": obs + half, "p": p,
            "p_perm": float((np.sum(np.abs(perm) >= abs(obs) - 1e-12) + 1) / (n_perm + 1))}


# ---------------------------------------------------------------- descriptive tables

def acceptance_table(df) -> pd.DataFrame:
    d = df.dropna(subset=["accepted"])
    keys = ["claim_type", "truth_value", "condition"]
    cols = ["model", "interpreter"] + keys + ["n_responses", "n_claims", "acceptance", "ci_low", "ci_high"]
    out = []
    claim = d.groupby(["model", "interpreter"] + keys + ["claim_id"])["accepted"].mean()
    n_resp = d.groupby(["model", "interpreter"] + keys).size()
    for k, s in claim.groupby(level=[0, 1, 2, 3, 4]):
        lo, hi = t_ci(s.values, 0.0, 1.0)
        out.append(dict(zip(["model", "interpreter"] + keys, k), n_responses=int(n_resp[k]), n_claims=len(s),
                        acceptance=float(s.mean()), ci_low=lo, ci_high=hi))
    main = d[~d["interpreter"]]
    if len(main):
        pooled = main.groupby(["model"] + keys + ["claim_id"])["accepted"].mean().groupby(keys + ["claim_id"]).mean()
        n_main = main.groupby(keys).size()
        for k, s in pooled.groupby(level=[0, 1, 2]):
            lo, hi = t_ci(s.values, 0.0, 1.0)
            out.append(dict(zip(keys, k), model="pooled", interpreter=False, n_responses=int(n_main[k]),
                            n_claims=len(s), acceptance=float(s.mean()), ci_low=lo, ci_high=hi))
    return pd.DataFrame(out, columns=cols)


def discrimination_table(df, models) -> pd.DataFrame:
    out = []
    for scope_name, ms in [("pooled", models)] + [(m, [m]) for m in models]:
        w = pair_values(df, ms, False, "disc")
        t, f = pair_values(df, ms, False, True), pair_values(df, ms, False, False)
        for ctype, types in TYPE_SETS.items():
            s, st, sf = subset(w, types), subset(t, types), subset(f, types)
            for cond in CONDITIONS:
                x = col(s, cond).dropna()
                if x.empty:
                    continue
                lo, hi = t_ci(x.values, -1.0, 1.0)
                tt = col(st, cond)
                ff = col(sf, cond).reindex(tt.index)
                out.append({"scope": scope_name, "claim_type": ctype, "condition": cond, "n_pairs": len(x),
                            "discrimination": float(x.mean()), "ci_low": lo, "ci_high": hi,
                            "pairs_both_twins_at_floor": int(((tt <= 0) & (ff <= 0)).sum()),
                            "pairs_both_twins_at_ceiling": int(((tt >= 1) & (ff >= 1)).sum())})
    return pd.DataFrame(out)


def rates_table(df) -> pd.DataFrame:
    d = df[~df["interpreter"]].dropna(subset=["accepted"])
    groups = [((m, c), g) for (m, c), g in d.groupby(["model", "condition"])]
    groups += [(("pooled", c), d[d["condition"] == c]) for c in CONDITIONS if (d["condition"] == c).any()]
    return pd.DataFrame([{"scope": s, "condition": c, "n": len(g),
                          "credential_citation_rate": g["mark_cited"].mean(), "abstention_rate": g["abstained"].mean(),
                          "mean_confidence": g["confidence"].mean()} for (s, c), g in groups])


def confidence_delta_table(df) -> pd.DataFrame:
    d = df[~df["interpreter"]].dropna(subset=["confidence"])
    base = d[d["condition"] == "C0"].groupby(["model", "claim_id"])["confidence"].mean().rename("c0_mean")
    d = d.join(base, on=["model", "claim_id"])
    d = d.assign(delta=d["confidence"] - d["c0_mean"]).dropna(subset=["delta"])
    return pd.DataFrame([{"condition": c, "claim_type": t, "truth_value": v, "n": len(g),
                          "confidence_delta": g["delta"].mean()}
                         for (c, t, v), g in d.groupby(["condition", "claim_type", "truth_value"])])


def scope_table(df, scope) -> pd.DataFrame:
    cols = ["condition", "n", "pct_0", "pct_1", "pct_2", "pct_NA", "share_2_of_mentions", "mean_score"]
    if scope.empty:
        return pd.DataFrame(columns=cols)
    d = df[~df["interpreter"]].merge(scope, on="response_id")
    out = []
    for cond, g in d.groupby("condition"):
        scored = pd.to_numeric(g["score"].where(g["score"] != "NA"), errors="coerce").dropna()
        out.append({"condition": cond, "n": len(g), **{f"pct_{s}": float((g["score"] == s).mean()) for s in SCORE_COLORS},
                    "share_2_of_mentions": float((scored == 2).mean()) if len(scored) else np.nan,
                    "mean_score": float(scored.mean()) if len(scored) else np.nan})
    return pd.DataFrame(out, columns=cols)


def rep_variance_table(df) -> pd.DataFrame:
    d = df.dropna(subset=["accepted"])
    cells = d.groupby(["model", "claim_id", "condition", "interpreter"])["accepted"]
    s = pd.DataFrame({"n_reps": cells.size(), "var": cells.var(ddof=0), "split": cells.nunique() > 1}).reset_index()
    return s.groupby(["model", "condition", "interpreter"]).agg(
        cells=("n_reps", "size"), mean_within_cell_variance=("var", "mean"),
        share_cells_where_reps_disagree=("split", "mean")).reset_index()


SCOPE_SETS = {"C1–C4": MARKED, "C1": ("C1",), "C2": ("C2",), "C3": ("C3",), "C4": ("C4",)}


def scope_shares(df, scope, models, types, conds=MARKED) -> dict:
    """Pair-level scope distribution (main arm), as pre-registered for H3 (§7, rev 3.3): the share of
    judged justifications that mention the credential, and among those the shares scored 0, 1 and 2.
    Each share is computed per model within a pair, averaged over models, then over pairs, with a 95%
    t-interval over pairs clipped to [0, 1]."""
    out = {"n_judged": 0, "n_mentions": 0, "n_pairs": 0}
    keys = ["mention"] + [f"share_{k}" for k in ("0", "1", "2")]
    for k in keys:
        out.update({k: np.nan, f"{k}_ci_low": np.nan, f"{k}_ci_high": np.nan})
    if scope.empty:
        return out
    d = df[df["model"].isin(models) & ~df["interpreter"] & df["condition"].isin(conds)
           & df["claim_type"].isin(types)].merge(scope, on="response_id")
    if d.empty:
        return out
    d = d.assign(mention=(d["score"] != "NA").astype(float))
    out["n_judged"], out["n_mentions"] = len(d), int(d["mention"].sum())

    def per_pair(frame, col_name):
        return frame.groupby(["model", "pair_id"])[col_name].mean().groupby("pair_id").mean()

    def put(key, x):
        out[key] = float(x.mean()) if len(x) else np.nan
        out[f"{key}_ci_low"], out[f"{key}_ci_high"] = t_ci(x.values, 0.0, 1.0)

    m = per_pair(d, "mention")
    out["n_pairs"] = len(m)
    put("mention", m)
    dm = d[d["mention"] == 1]
    for k in ("0", "1", "2"):
        put(f"share_{k}", per_pair(dm.assign(x=(dm["score"] == k).astype(float)), "x") if len(dm)
            else pd.Series(dtype=float))
    return out


def scope_distribution_table(df, scope, models) -> pd.DataFrame:
    rows = []
    for scope_name, ms in [("pooled", models)] + [(m, [m]) for m in models]:
        for ctype, types in TYPE_SETS.items():
            for label, conds in SCOPE_SETS.items():
                rows.append({"scope": scope_name, "claim_type": ctype, "conditions": label,
                             **scope_shares(df, scope, ms, types, conds)})
    return pd.DataFrame(rows)


def h3_verdict(h3: dict) -> tuple[bool, str]:
    """The rev 3.3 rule: supported only if the 95% CI's upper bound for the share scored 2 is below
    0.5 and the Holm-adjusted p is below .05."""
    if not h3 or not h3.get("n_pairs") or isnan(h3.get("ci_high")):
        return False, "H3 could not be evaluated (no scope scores)."
    hi = pct(min(1.0, h3["ci_high"]))
    if h3["ci_high"] < 0.5 and not isnan(h3.get("p_holm")) and h3["p_holm"] < ALPHA:
        return True, (f"The upper bound of the CI for score 2 ({hi}) is below 50% and "
                      f"{p_is('p_holm', h3['p_holm'])}, so H3 is supported.")
    if h3["ci_high"] < 0.5:
        return False, (f"The upper bound of the CI for score 2 ({hi}) is below 50%, but after Holm correction "
                       f"{p_is('p_holm', h3.get('p_holm'))}, so H3 is not supported.")
    return False, f"The upper bound of the CI for score 2 ({hi}) is not below 50%, so H3 is not supported."


def share_ci(r: dict, key: str) -> str:
    """'15% (95% CI 10–19%)'"""
    return f"{pct(r.get(key))} (95% CI {pct(r.get(key + '_ci_low'))}–{pct(r.get(key + '_ci_high'))})"


def example_justifications(df, scope, n=6) -> str:
    """Candidates for the two verbatim examples in §4.5: misattribution in C2 (score 0) and correct
    scope (score 2). Picked deterministically; the author reads them and chooses."""
    lines = ["# Example justifications (candidates for §4.5)", "",
             "Read each one before quoting it: a score of 0 also covers 'treats the credential as support', "
             "so check that the C2 example really attributes the gathered statement to the signer.", ""]
    if scope.empty:
        return "\n".join(lines + ["_No scope scores yet._"]) + "\n"
    d = df[~df["interpreter"]].merge(scope, on="response_id").sort_values("response_id")
    for title, sel in (("Score 0 in C2 (statement only gathered, not attributed to the signer)",
                        (d["condition"] == "C2") & (d["score"] == "0")),
                       ("Score 2 (scope described correctly), C1-C4", d["score"] == "2")):
        pick = d[sel]
        lines += [f"## {title}", "", f"{len(pick)} in total; the first {min(n, len(pick))} by response id:", ""]
        for _, r in pick.head(n).iterrows():
            lines += [f"- `{r['response_id']}` ({r['claim_type']}, {'true' if r['truth_value'] else 'false'} claim, "
                      f"accept={r['accept']}): \"{str(r['justification']).strip()}\""]
        lines += [""]
    return "\n".join(lines) + "\n"


def model_scope_correct(df, scope, model) -> float:
    if scope.empty:
        return np.nan
    d = df[(df["model"] == model) & ~df["interpreter"] & df["condition"].isin(MARKED)].merge(scope, on="response_id")
    d = d[d["score"] != "NA"]
    return float((d["score"] == "2").mean()) if len(d) else np.nan


# ---------------------------------------------------------------- figures

def _style(ax, title, ylabel):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def _spread(values, gap):
    """Nudge label y-positions apart (order kept) so end-of-line labels do not overlap."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    pos = list(values)
    for a, b in zip(order, order[1:]):
        if pos[b] - pos[a] < gap:
            pos[b] = pos[a] + gap
    return pos


def figures(out: Path, acc: pd.DataFrame, disc: pd.DataFrame, scope_tab: pd.DataFrame, df: pd.DataFrame) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import PercentFormatter
    paths, x = [], np.arange(len(CONDITIONS))

    # 1. acceptance by condition. Hue = claim type; solid line and filled marker = true twin.
    fig, ax = plt.subplots(figsize=(7.5, 4.2), facecolor=SURFACE)
    pooled = acc[acc["model"] == "pooled"]
    ends = []
    for ctype, color in (("real_obscure", BLUE), ("invented", ORANGE)):
        for truth, ls, face in ((True, "-", color), (False, "--", SURFACE)):
            s = pooled[(pooled["claim_type"] == ctype) & (pooled["truth_value"] == truth)]
            s = s.set_index("condition").reindex(CONDITIONS)
            ax.errorbar(x, s["acceptance"], yerr=[s["acceptance"] - s["ci_low"], s["ci_high"] - s["acceptance"]],
                        color=color, ls=ls, lw=2, marker="o", ms=8, mfc=face, mec=color, mew=2, elinewidth=1, capsize=0)
            last = s["acceptance"].dropna()
            if len(last):
                ends.append((float(last.iloc[-1]), CONDITIONS.index(last.index[-1]),
                             f"{TYPE_LABEL[ctype]}, {'true' if truth else 'false'}"))
    for (y, xe, label), yl in zip(ends, _spread([e[0] for e in ends], 0.065)):
        ax.annotate(label, (xe, y), xytext=(xe + 0.3, yl), textcoords="data", va="center", fontsize=8, color=INK2)
    ax.set_xticks(x, CONDITIONS)
    ax.set_ylim(0, 1.08)
    ax.set_xlim(-0.3, len(CONDITIONS) + 1.2)
    _style(ax, "Figure 1. Acceptance by condition (pooled models; 95% CI over claims)", "share accepted")
    ax.legend(handles=[Line2D([], [], color=BLUE, lw=2, label="real-obscure"),
                       Line2D([], [], color=ORANGE, lw=2, label="invented"),
                       Line2D([], [], color=INK2, lw=2, marker="o", ms=7, label="true twin"),
                       Line2D([], [], color=INK2, lw=2, ls="--", marker="o", ms=7, mfc=SURFACE, label="false twin")],
              frameon=False, fontsize=8, loc="upper left", ncol=2)
    paths.append(_save(fig, out / "fig1_acceptance.png"))

    # 2. discrimination index by condition
    fig, ax = plt.subplots(figsize=(7.5, 4.2), facecolor=SURFACE)
    d = disc[disc["scope"] == "pooled"] if not disc.empty else disc
    ends = []
    for k, (ctype, color) in enumerate((("real_obscure", BLUE), ("invented", ORANGE))):
        if d.empty:
            break
        s = d[d["claim_type"] == ctype].set_index("condition").reindex(CONDITIONS)
        off = (k - 0.5) * 0.2
        ax.errorbar(x + off, s["discrimination"],
                    yerr=[s["discrimination"] - s["ci_low"], s["ci_high"] - s["discrimination"]],
                    color=color, lw=0, elinewidth=1.5, marker="o", ms=8, mfc=color, mec=SURFACE, mew=1.5,
                    label=TYPE_LABEL[ctype])
        last = s["discrimination"].dropna()
        if len(last):
            ends.append((float(last.iloc[-1]), CONDITIONS.index(last.index[-1]), TYPE_LABEL[ctype]))
    for (y, xe, label), yl in zip(ends, _spread([e[0] for e in ends], 0.07)):
        ax.annotate(label, (xe + 0.1, y), xytext=(xe + 0.3, yl), textcoords="data", va="center", fontsize=8, color=INK2)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(x, CONDITIONS)
    ax.set_xlim(-0.4, len(CONDITIONS) + 0.9)
    _style(ax, "Figure 2. Discrimination index: true-twin minus false-twin acceptance (95% CI over pairs)",
           "difference in share accepted")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    paths.append(_save(fig, out / "fig2_discrimination.png"))

    # 3. scope accuracy: 100% stacked bars per condition
    fig, ax = plt.subplots(figsize=(7.5, 3.4), facecolor=SURFACE)
    st = scope_tab.set_index("condition").reindex(list(MARKED)) if not scope_tab.empty else None
    if st is not None and st["n"].notna().any():
        y, left = np.arange(len(st)), np.zeros(len(st))
        names = {"0": "0: support or misattribution", "1": "1: partial", "2": "2: correct scope",
                 "NA": "credential not mentioned"}
        for s in SCORE_COLORS:
            vals = st[f"pct_{s}"].astype(float).fillna(0).values
            ax.barh(y, vals, left=left, color=SCORE_COLORS[s], edgecolor=SURFACE, linewidth=2, label=names[s], height=0.6)
            for yi, (l, v) in enumerate(zip(left, vals)):
                if v >= 0.045:
                    ax.text(l + v / 2, yi, f"{v:.0%}", ha="center", va="center", fontsize=8,
                            color="#ffffff" if s in ("1", "2") else INK)
            left += vals
        ax.set_yticks(y, [f"{c} (n={int(n)})" if n == n else c for c, n in zip(st.index, st["n"])])
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    else:
        ax.text(0.5, 0.5, "No scope scores yet", ha="center", va="center", color=INK2, transform=ax.transAxes)
    _style(ax, "Figure 3. Scope accuracy of justifications by condition", "")
    ax.grid(False)
    paths.append(_save(fig, out / "fig3_scope_accuracy.png"))

    # 4. countermeasure: per interpreter-arm model, C1 and C2 with and without the interpreter
    fig, ax = plt.subplots(figsize=(7.5, 4.2), facecolor=SURFACE)
    im = sorted(df.loc[df["interpreter"], "model"].unique())
    if im:
        groups = [(m, c) for m in im for c in ("C1", "C2")]
        xs = np.arange(len(groups))
        for k, (interp, color, name) in enumerate(((False, BLUE, "no interpreter"), (True, ORANGE, "with interpreter"))):
            vals = [df[(df["model"] == m) & (df["condition"] == c) & (df["interpreter"] == interp)]["accepted"].mean()
                    for m, c in groups]
            ax.bar(xs + (k - 0.5) * 0.38, vals, width=0.36, color=color, edgecolor=SURFACE, linewidth=2, label=name)
        c0 = [df[(df["model"] == m) & (df["condition"] == "C0") & ~df["interpreter"]]["accepted"].mean() for m, _ in groups]
        ax.scatter(xs, c0, marker="_", s=500, color=INK, linewidths=2, label="C0 (no credential)", zorder=3)
        ax.set_xticks(xs, [f"{m}\n{c}" for m, c in groups], fontsize=8)
        ax.set_ylim(0, 1.08)
        ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=3)
    else:
        ax.text(0.5, 0.5, "No interpreter-arm data yet", ha="center", va="center", color=INK2, transform=ax.transAxes)
    _style(ax, "Figure 4. Countermeasure: acceptance with and without the scope interpreter", "share accepted")
    paths.append(_save(fig, out / "fig4_interpreter.png"))
    return paths


def _save(fig, path: Path) -> Path:
    import matplotlib.pyplot as plt
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


# ---------------------------------------------------------------- text

def isnan(v) -> bool:
    try:
        return v is None or float(v) != float(v)
    except (TypeError, ValueError):
        return True


def signed(v, scale=100.0, d=1) -> str:
    """+29.8 / −3.3 (a true minus sign); fractions are shown as points by default."""
    if isnan(v):
        return "n/a"
    x = round(float(v) * scale, d)
    return ("+" if x > 0 else MINUS if x < 0 else "") + f"{abs(x):.{d}f}"


def plain(v, scale=100.0, d=1) -> str:
    if isnan(v):
        return "n/a"
    x = round(float(v) * scale, d)
    return (MINUS if x < 0 else "") + f"{abs(x):.{d}f}"


def pct(v, d=0) -> str:
    return "n/a" if isnan(v) else f"{float(v) * 100:.{d}f}%"


def num(v, d=3) -> str:
    return "n/a" if isnan(v) else f"{float(v):.{d}f}"


def p_is(name, p) -> str:
    if isnan(p):
        return f"{name} n/a"
    return f"{name} < 0.001" if p < 0.001 else f"{name} = {p:.3f}"


def fmt_p(p) -> str:
    return "n/a" if isnan(p) else ("< 0.001" if p < 0.001 else f"{p:.3f}")


SCALE = {"pp": 100.0, "conf": 1.0, "share": 100.0}
UNIT = {"pp": " points", "conf": " confidence points", "share": ""}


def value(r: dict, key="delta") -> str:
    unit = r.get("unit", "pp")
    return pct(r.get(key)) if unit == "share" else signed(r.get(key), SCALE[unit])


def p_part(r, adjusted=True) -> str:
    return p_is("p_holm", r.get("p_holm")) if adjusted else p_is("p", r.get("p")) + ", unadjusted"


def inner(r, adjusted=True) -> str:
    return f"95% CI {value(r, 'ci_low')} to {value(r, 'ci_high')}; {p_part(r, adjusted)}; {r['n_pairs']} pairs"


def stat(r: dict, adjusted=True) -> str:
    """+29.8 points (95% CI +22.7 to +37.1; p_holm = 0.016; 10 pairs)"""
    if not r or not r.get("n_pairs"):
        return "not available (no data for this comparison)"
    return f"{value(r)}{UNIT[r.get('unit', 'pp')]} ({inner(r, adjusted)})"


def by(r, adjusted=True, short=False) -> str:
    """'by 29.8 points (95% CI 22.7 to 37.1; ...)': the size, with the direction carried by the verb."""
    unit = r.get("unit", "pp")
    sc = SCALE[unit]
    lo, hi = (r["ci_low"], r["ci_high"]) if r["delta"] >= 0 else (-r["ci_high"], -r["ci_low"])
    tail = f", {p_part(r, adjusted)}" if short else f"; {p_part(r, adjusted)}; {r['n_pairs']} pairs"
    return f"by {plain(abs(r['delta']), sc)}{UNIT[unit]} (95% CI {plain(lo, sc)} to {plain(hi, sc)}{tail})"


def unchanged(r, adjusted=True) -> str:
    """(Δ = +2.0 points; 95% CI −3.0 to +7.0; p_holm = 0.512; 10 pairs)"""
    return f"(Δ = {value(r)}{UNIT[r.get('unit', 'pp')]}; {inner(r, adjusted)})"


def sig(r) -> bool:
    return bool(r) and not isnan(r.get("p_holm")) and r["p_holm"] < ALPHA


def find(rows, h, comparison, measure="acceptance", primary=True) -> dict:
    for r in rows:
        if (r["hypothesis"], r["comparison"], r["measure"], r["primary"]) == (h, comparison, measure, primary):
            return r
    return {}


def ci_bound(r) -> str:
    """The largest difference, in points, that the 95% CI leaves open."""
    if not r or not r.get("n_pairs") or isnan(r.get("ci_low")):
        return "n/a"
    return f"{max(abs(r['ci_low']), abs(r['ci_high'])) * SCALE[r.get('unit', 'pp')]:.0f}"


def build_slots(ctx: dict) -> dict:
    """Ready-to-paste text for each slot. Verbs follow the data: a change is reported as a change only
    when p_holm < .05 (p < .05 for the exploratory H5); otherwise the text says what the CI leaves open."""
    real, allp = ctx["fam"][("pooled", "real_obscure")], ctx["fam"][("pooled", "all")]
    h1, h1f = find(real, "H1", "C1 vs C0"), ctx["h1_false"]
    c32, c32c = find(real, "H2", "C3 vs C2"), find(real, "H2", "C3 vs C2", "confidence")
    c41, c43 = find(real, "H2", "C4 vs C1"), find(real, "H2", "C4 vs C3")
    d50 = find(real, "H2b", "C5 vs C0", "discrimination index")
    dflat = find(real, "H2b", "C1-C4 mean vs C0", "discrimination index", primary=False)
    h3 = find(real, "H3", "C1-C4 vs 50%", "share of credential mentions scored 2")
    h4 = find(allp, "H4", "interpreter vs none (C1, C2)")
    h5r, disc = ctx["h5"], ctx["disc_real"]
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    s = {"N_MODELS": words.get(len(ctx["models"]), str(len(ctx["models"])))}
    s["N_STUDY_MODELS"] = s["N_MODELS"]
    h1_up = sig(h1) and h1["delta"] > 0

    # H1 (abstract headline and 4.2)
    if h1.get("n_pairs"):
        false_note = (f"; false versions alone: {plain(abs(h1f['delta']))} points"
                      if h1f.get("n_pairs") and sig(h1) and np.sign(h1f["delta"]) == np.sign(h1["delta"]) else "")
        if sig(h1):
            b = by(h1, short=True)
            h1_core = f"{'raised' if h1['delta'] > 0 else 'lowered'} acceptance {b[:-1]}{false_note})"
        else:
            h1_core = f"did not reliably change acceptance {unchanged(h1)}"
        lead = f"On claims about real organisations, a credential that certified nothing about the claim {h1_core}"
    else:
        lead = "C1 vs C0 was not available"
    s["H1_STAT"] = (f"{signed(h1f.get('delta'))} points on real-obscure false claims (95% CI {signed(h1f.get('ci_low'))} "
                    f"to {signed(h1f.get('ci_high'))}; {p_is('p', h1f.get('p'))}, unadjusted; {h1f.get('n_pairs', 0)} "
                    f"pairs). Pre-registered test, both twins: {stat(h1)}")

    # H2 (4.3 and the abstract)
    s["C32_STAT"] = f"C3 − C2 = {stat(c32)}; confidence, C3 − C2 = {stat(c32c)}"
    s["C41_STAT"] = f"C4 − C1 = {stat(c41)}. C4 vs C3: C4 − C3 = {stat(c43)}"
    names = ((c32, "moving the statement from gathered to created assertions (C3 vs C2)"),
             (c41, "removing the signer from the trust list (C4 vs C1)"), (c43, "C4 vs C3"))
    moved = [(r, n) for r, n in names if sig(r)]
    if not any(r.get("n_pairs") for r, _ in names):
        s["H2_SENTENCE"] = "C2–C4 comparisons were not available."
    elif not moved:
        s["H2_SENTENCE"] = ("No reliable difference: acceptance did not reliably differ whether the signer asserted the "
                            f"statement (C3) or merely recorded it (C2), with the 95% CI excluding differences larger "
                            f"than {ci_bound(c32)} points, nor whether the signer was on a trust list (C4 vs C1; larger "
                            f"than {ci_bound(c41)} points).")
    else:
        s["H2_SENTENCE"] = ("Partly: " + "; ".join(f"{n} {'raised' if r['delta'] > 0 else 'lowered'} acceptance {by(r)}"
                                                   for r, n in moved)
                            + ("; the other contrasts did not reliably differ." if len(moved) < 3 else "."))
    if c32.get("n_pairs"):
        c32_phrase = (f"acceptance did not reliably differ between a signer who asserted the statement and one who "
                      f"merely recorded it (C3 − C2 = {value(c32)} points, 95% CI {value(c32, 'ci_low')} to "
                      f"{value(c32, 'ci_high')})" if not sig(c32) else
                      f"acceptance was {'higher' if c32['delta'] > 0 else 'lower'} {by(c32, short=True)} when the "
                      f"signer asserted the statement than when it merely recorded it")
        s["HEADLINE"] = f"{lead}, and {c32_phrase}."
    else:
        s["HEADLINE"] = lead + "."

    # H2b (4.4 and the abstract)
    flat = bool(dflat.get("n_pairs")) and not (dflat.get("p", 1.0) < ALPHA)
    rose = sig(d50) and d50["delta"] > 0
    if d50.get("n_pairs"):
        c5 = (f"rose {by(d50)}" if rose else f"{'fell' if sig(d50) else 'did not reliably rise'} "
              f"{by(d50) if sig(d50) else unchanged(d50)}")
        s["DISCRIMINATION"] = (
            f"On real-obscure pairs the discrimination index was {signed(disc.get('C0'))} points at C0. Averaged over "
            f"C1–C4 it {'did not reliably move' if flat else 'moved'} (Δ = {value(dflat)} points vs C0; "
            f"{inner(dflat, adjusted=False)}), and at C5 it {c5}.")
        if h1_up and flat:
            s["DISC_ABSTRACT"] = ("These credentials raised acceptance of true and false versions alike, leaving the "
                                  "ability to tell them apart unchanged; " +
                                  ("only a credential binding the claim to a checkable source improved it." if rose else
                                   "even a credential binding the claim to a checkable source did not reliably "
                                   "improve it."))
        else:
            s["DISC_ABSTRACT"] = s["DISCRIMINATION"]
    else:
        s["DISCRIMINATION"] = s["DISC_ABSTRACT"] = "The discrimination index was not available."
    s["RESULT_PHRASE"] = ("that credentials certifying nothing about a claim raised belief in its true and false "
                          "versions alike without improving accuracy" if (h1_up and flat) else
                          "how far credentials moved belief and accuracy separately (Section 4.4)")

    # H3 (4.5)
    dist = ctx["h3_dist"]
    if ctx.get("scope_withheld"):
        s["H3_SENTENCE"] = ctx["scope_withheld"]
    elif h3.get("n_pairs") and dist.get("n_judged"):
        s["H3_SENTENCE"] = (
            f"Of the {dist['n_judged']} judged C1–C4 justifications on real-obscure pairs, {share_ci(dist, 'mention')} "
            f"mentioned the credential. Of those, {share_ci(dist, 'share_2')} described its scope correctly "
            f"(score 2), {share_ci(dist, 'share_1')} did so partially (1), and {share_ci(dist, 'share_0')} treated "
            f"it as support for the claim or misattributed it (0); CIs over {dist['n_pairs']} pairs. "
            + h3_verdict(h3)[1])
    else:
        s["H3_SENTENCE"] = "Scope scores were not available."
    s["SCOPE_TABLE"] = s["H3_SENTENCE"] + "\n\n" + ctx["scope_md"]
    s["CITATION_TABLE"] = ctx["citation_md"]

    # H4 (abstract and 4.7)
    if h4.get("n_pairs"):
        gap = h4.get("gap_without_interpreter", np.nan)
        reduced = sig(h4) and h4["delta"] < 0
        closed = ""
        if reduced and not isnan(gap) and gap > 0.02:
            closed = f", closing {min(100.0, -h4['delta'] / gap * 100):.0f}% of the rise over the no-credential baseline"
        if sig(h4):
            core = f"{'reduced' if reduced else 'increased'} acceptance under C1 and C2 {by(h4)}{closed}"
        else:
            core = f"did not reliably change acceptance under C1 and C2 {unchanged(h4)}"
        s["H4_SENTENCE"] = f"A plain-language interpreter stating each credential's scope {core}."
        s["H4_STAT"] = (f"interpreter − none = {stat(h4)}, across the three interpreter-arm models; without the "
                        f"interpreter, their C1/C2 acceptance was {signed(gap)} points relative to C0")
    else:
        s["H4_SENTENCE"] = s["H4_STAT"] = "The interpreter arm was not available."

    # H5 (exploratory: abstract and 4.6)
    if h5r:
        d, pi = h5r["invented_delta"], h5r["invented_p"]
        moved5 = not isnan(pi) and pi < ALPHA
        change = (f"{'raised' if d > 0 else 'lowered'} acceptance by {plain(abs(d))} points" if moved5
                  else f"changed acceptance by {signed(d)} points")
        compare = (f"against {signed(h5r['real_delta'])} points for claims about real organisations (difference "
                   f"{signed(h5r['difference'])} points; 95% CI {signed(h5r['ci_low'])} to {signed(h5r['ci_high'])}; "
                   f"{p_is('p', h5r['p'])}, exploratory)")
        s["H5_DELTA"] = (f"{signed(d)} points (95% CI {signed(h5r['invented_ci_low'])} to "
                         f"{signed(h5r['invented_ci_high'])}; {p_is('p', pi)}, unadjusted, exploratory; "
                         f"{h5r['n_invented']} pairs)")
        s["H5_ABSTRACT"] = f"For organisations the models did not recognise, the same credential {change}, {compare}."
        more = h5r["difference"] > 0 and h5r["p"] < ALPHA
        answer = "Yes" if (moved5 and d > 0 and more) else "Partly" if (moved5 and d > 0) else "No clear evidence"
        s["H5_46"] = (f"{answer}: on claims about organisations the models did not recognise, the credential {change}, "
                      f"{compare}.")
    else:
        s["H5_DELTA"] = s["H5_ABSTRACT"] = s["H5_46"] = "H5 was not available."

    # 4.1 baseline
    base = ctx["c0"]
    for key in ("real_true", "real_false", "inv_true", "inv_false"):
        v = base.get(key)
        s[f"C0_{key}"] = "n/a" if not v else f"{pct(v[0])} (95% CI {pct(v[1])}–{pct(v[2])})"
    if all(base.get(k) for k in ("real_true", "real_false", "inv_true", "inv_false")):
        real_mean = (base["real_true"][0] + base["real_false"][0]) / 2
        inv_mean = (base["inv_true"][0] + base["inv_false"][0]) / 2
        gap = real_mean - inv_mean
        how = "much less often than" if gap > 0.10 else "more often than" if gap < -0.10 else "about as often as"
        s["C0_SENTENCE"] = (f"At baseline, claims about invented organisations were accepted {how} claims about real "
                            f"ones ({pct(inv_mean)} vs {pct(real_mean)})" +
                            (", consistent with non-recognition being read as evidence of fabrication." if gap > 0.10
                             else "."))
    else:
        s["C0_SENTENCE"] = "C0 data were not available."

    for k in ("SETTINGS", "MODELS_PARAGRAPH", "JUDGE_MODEL", "N_JUDGED", "KAPPA"):
        s[k] = ctx[k.lower()]
    return s


# (pattern for the placeholder's own text, pattern the text just before it must end with, slot)
SLOT_RULES = [
    (r"PLACEHOLDER$", None, "_INSTRUCTION"),
    (r"N_MODELS$", None, "N_MODELS"),
    (r"HEADLINE RESULT\b", None, "HEADLINE"),
    (r"DISCRIMINATION RESULT\b", None, "DISC_ABSTRACT"),
    (r"INTERPRETER RESULT\b", None, "H4_SENTENCE"),
    (r"UNRECOGNISED-SOURCE RESULT\b", None, "H5_ABSTRACT"),
    (r"RESULT$", r"showing $", "RESULT_PHRASE"),
    (r"FILL FROM MODELS\.YAML\b", None, "MODELS_PARAGRAPH"),
    (r"SETTINGS$", None, "SETTINGS"),
    (r"JUDGE MODEL$", None, "JUDGE_MODEL"),
    (r"N$", r"sample of $", "N_JUDGED"),
    (r"N$", r"evaluations of $", "N_STUDY_MODELS"),
    (r"KAPPA$", None, "KAPPA"),
    (r"X$", r"real-obscure true $", "C0_real_true"),
    (r"X$", r"real-obscure true \{X\}, false $", "C0_real_false"),
    (r"X$", r"invented true $", "C0_inv_true"),
    (r"X$", r"invented true \{X\}, false $", "C0_inv_false"),
    (r"ONE SENTENCE ON WHETHER INVENTED\b", None, "C0_SENTENCE"),
    (r"Δ, CI, P_HOLM$", r"C1 vs C0 on false claims: $", "H1_STAT"),
    (r"Δ, CI, P_HOLM$", r"C2 vs C3: $", "C32_STAT"),
    (r"Δ, CI, P_HOLM$", r"C4 vs C1: $", "C41_STAT"),
    (r"Δ, CI, P_HOLM$", r"C1/C2: $", "H4_STAT"),
    (r"ONE SENTENCE: DID MODELS DISTINGUISH\b", None, "H2_SENTENCE"),
    (r"DID THE INDEX STAY FLAT\b", None, "DISCRIMINATION"),
    (r"TABLE$", r"Scope accuracy by condition $", "SCOPE_TABLE"),
    (r"TABLE$", r"Credential-citation rate $", "CITATION_TABLE"),
    (r"Δ$", r"invented items: $", "H5_DELTA"),
    (r"DID A CREDENTIAL RESCUE\b", None, "H5_46"),
]


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"(?m)^\s*>\s?", "", text))


def placeholder_entries(draft_text: str, slots: dict) -> list[dict]:
    """Every {...} in the draft, in order: where it is, which slot it maps to, and the text."""
    entries, section, heading = [], {}, ""
    for i, line in enumerate(draft_text.splitlines()):
        if line.startswith("#"):
            heading = line.lstrip("# ").strip()
        section[i] = heading
    for m in re.finditer(r"\{[^{}]*\}", draft_text):
        inner = _flat(m.group(0)[1:-1]).strip()
        before = _flat(draft_text[max(0, m.start() - 300):m.start()])
        slot = next((name for own, ctx_pat, name in SLOT_RULES
                     if re.match(own, inner.upper()) and (ctx_pat is None or re.search(ctx_pat, before))), None)
        line_no = draft_text.count("\n", 0, m.start())
        text = ("(instruction text, not a slot to fill)" if slot == "_INSTRUCTION"
                else slots.get(slot, NO_VALUE) if slot else NO_VALUE)
        entries.append({"placeholder": "{" + inner + "}", "start": m.start(), "end": m.end(), "line": line_no + 1,
                        "section": section.get(line_no, ""), "slot": slot, "text": text})
    return entries


def filled_draft(draft_text: str, entries) -> str:
    out, pos = [], 0
    for e in entries:
        if e["slot"] in (None, "_INSTRUCTION"):
            continue
        out.append(draft_text[pos:e["start"]])
        text, end = e["text"], e["end"]
        if "\n|" in text:  # a table needs its own block
            text = "\n\n" + text + "\n\n"
        out.append(text)
        pos = end
    out.append(draft_text[pos:])
    return "".join(out)


def table_md(df: pd.DataFrame, cols, headers, fmt=None) -> str:
    if df is None or df.empty:
        return "_Not available yet._"
    fmt = fmt or {}
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(fmt[c](r[c]) if c in fmt else str(r[c]) for c in cols) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------- driver

def git_out(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def reasoning_settings(raw_dir: Path, models, cfg) -> tuple[str, list[str]]:
    """The reasoning setting each model actually logged, and any model that logged more than one."""
    groups, problems = {}, []
    for m in models:
        logged = {json.dumps(r["reasoning_setting"], sort_keys=True) for r in R.read_raw(Path(raw_dir) / f"{m}.jsonl")
                  if r.get("status") in R.DONE_STATUSES and "reasoning_setting" in r}
        if len(logged) > 1:
            problems.append(f"{m} logged {len(logged)} different reasoning settings: {sorted(logged)}")
        mc = cfg["models"][m]
        setting = json.loads(sorted(logged)[0]) if logged else (
            mc.get("reasoning") or {"thinkingConfig": (mc.get("generation_config") or {}).get("thinkingConfig")})
        flat = (setting or {}).get("thinkingConfig") or setting or {}
        shown = ", ".join(f"{k}: {v}" for k, v in flat.items() if k in ("reasoning_effort", "thinkingLevel"))
        key = f"`{shown or json.dumps(setting)}`" + ("" if logged else " (from models.yaml: not in the logs)")
        groups.setdefault(key, []).append(m)
    parts = [" and ".join(ms) + " " + k + (", the lowest gpt-oss allows" if "reasoning_effort: low" in k else "")
             for k, ms in groups.items()]
    return "; ".join(parts) + "; logged with every call", problems


def judge_text(cfg: dict) -> str:
    """The main judge as §3.4 names it: model, provider and the blinding."""
    j = J.judge_config(cfg, "main")
    if not j.get("model_id"):
        return "[the judges are not chosen yet: judges.main.model_id in models.yaml]"
    route = ((j.get("route") or {}).get("order") or ["?"])[0]
    return (f"`{j['model_id']}` via OpenRouter, served by {route} (temperature {j.get('temperature', 0.0):g}, blind to "
            "model, condition and truth)")


def kappa_text(gate: dict, cfg: dict) -> str:
    """Agreement between the two judges (§5, rev 3.4), for the KAPPA slot."""
    o = gate.get("overall") or {}
    if not o.get("n_items"):
        return "not computed yet: the cross-check judge has not scored any response"
    c = J.judge_config(cfg, "crosscheck")
    who = f"`{c['model_id']}`" if c.get("model_id") else "the cross-check judge"
    fams = ", ".join(f"{k} {num(v.get('weighted_kappa_linear'), 2)} (n = {v.get('n_both_scored')})"
                     for k, v in gate.get("by_family", {}).items())
    return (f"linear-weighted κ = {num(o.get('weighted_kappa_linear'), 2)} between the judge and {who} on the "
            f"{o.get('n_both_scored')} responses both scored 0–2, of {gate.get('n_crosschecked')} cross-checked; "
            f"exact agreement {pct(o.get('exact_agreement'))}; by study-model family: {fams}")


def withheld_text(gate: dict) -> str:
    """The H3 sentence when judge results may not be reported (§5, rev 3.4)."""
    if gate.get("status") == "failed":
        return (f"Scope accuracy is not reported: the two judges' linear-weighted kappa was "
                f"{num(gate.get('kappa'), 2)} on {gate['overall'].get('n_both_scored', 0)} responses both scored 0–2, "
                "below the pre-registered 0.6, so H3 was not tested.")
    return (f"Scope accuracy is not reported yet: the cross-check judge has scored {gate.get('n_crosschecked', 0)} of "
            f"{gate.get('n_sample') or 100} responses, and judge results are reported only once the judges' "
            "weighted kappa is known to be at least 0.6.")


def analyse(raw_dir: Path, graded_dir: Path, out: Path, pilot_dir: Path, draft: Path, config: Path,
            scope_req: str = "auto") -> dict:
    """pilot_dir is never read: pilot data, including the pilot's judge files, is excluded."""
    cfg = R.load_config(config)
    df = load_responses(raw_dir, list(cfg["models"]))
    if df.empty:
        raise SystemExit(f"No responses in {raw_dir}. Run the study (or src/synthetic.py for a rehearsal) first.")
    models = [m for m in cfg["models"] if m in set(df["model"])]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    source, gate = scope_source(graded_dir, cfg, scope_req)
    forced = source == "judge" and gate["status"] != "passed"
    scope = load_scope(graded_dir, source, cfg)

    fam, all_rows = {}, []
    for scope_name, ms in [("pooled", models)] + [(m, [m]) for m in models]:
        for ctype, types in TYPE_SETS.items():
            rows = primary_family(df, scope, ms, types, rng)
            for r in rows:
                r.update(model_scope=scope_name, claim_type=ctype)
            fam[(scope_name, ctype)] = rows
            all_rows += rows
    lead = ["model_scope", "claim_type", "hypothesis", "comparison", "measure", "unit", "sample", "primary",
            "n_pairs", "delta", "ci_low", "ci_high", "p", "p_holm", "p_perm", "p_perm_holm", "p_perm_min", "sd",
            "n_ceiling_dropped"]
    tests = pd.DataFrame(all_rows)
    tests = tests[lead + [c for c in tests.columns if c not in lead]]
    tests.to_csv(out / "primary_tests.csv", index=False)

    wf = subset(pair_values(df, models, False, False), ("real_obscure",), ceiling_pairs(df, models))
    h1_false = paired(col(wf, "C0"), col(wf, "C1"), rng)
    h5r = h5(df, models, rng)
    pd.DataFrame([h5r] if h5r else []).to_csv(out / "h5_unrecognised_sources.csv", index=False)

    acc = acceptance_table(df)
    acc.to_csv(out / "acceptance_by_condition.csv", index=False)
    disc = discrimination_table(df, models)
    disc.to_csv(out / "discrimination_by_condition.csv", index=False)
    rates = rates_table(df)
    rates.to_csv(out / "citation_abstention_confidence.csv", index=False)
    confidence_delta_table(df).to_csv(out / "confidence_delta.csv", index=False)
    stab = scope_table(df, scope)
    stab.to_csv(out / "scope_accuracy.csv", index=False)
    sdist = scope_distribution_table(df, scope, models)
    sdist.to_csv(out / "scope_distribution.csv", index=False)
    rep_variance_table(df).to_csv(out / "rep_variance.csv", index=False)
    (out / "example_justifications.md").write_text(example_justifications(df, scope), encoding="utf-8", newline="\n")

    pf_path = Path(graded_dir) / "parse_failures.csv"
    pf = {r["model"]: r for r in G.read_csv(pf_path)} if pf_path.exists() else {}
    per_model = []
    for m in models:
        r, a = fam[(m, "real_obscure")], fam[(m, "all")]
        per_model.append({
            "model": m, "cells": int((df["model"] == m).sum()),
            "c0_acceptance": df[(df["model"] == m) & (df["condition"] == "C0") & ~df["interpreter"]]["accepted"].mean(),
            "h1_c1_vs_c0_real": find(r, "H1", "C1 vs C0").get("delta", np.nan),
            "h2_c3_vs_c2_real": find(r, "H2", "C3 vs C2").get("delta", np.nan),
            "h2_c4_vs_c1_real": find(r, "H2", "C4 vs C1").get("delta", np.nan),
            "h2b_disc_c5_vs_c0_real": find(r, "H2b", "C5 vs C0", "discrimination index").get("delta", np.nan),
            "h4_interpreter_all": find(a, "H4", "interpreter vs none (C1, C2)").get("delta", np.nan),
            "scope_correct_share": model_scope_correct(df, scope, m),
            "parse_failed_rate": pf.get(m, {}).get("parse_failed_rate", ""),
            "cost_usd": pf.get(m, {}).get("cost_usd", "")})
    per_model_df = pd.DataFrame(per_model)
    per_model_df.to_csv(out / "per_model.csv", index=False)
    fig_paths = figures(out, acc, disc, stab, df)

    pooled_acc = acc[acc["model"] == "pooled"]
    c0 = {}
    for key, (ct, tv) in {"real_true": ("real_obscure", True), "real_false": ("real_obscure", False),
                          "inv_true": ("invented", True), "inv_false": ("invented", False)}.items():
        r = pooled_acc[(pooled_acc["claim_type"] == ct) & (pooled_acc["truth_value"] == tv)
                       & (pooled_acc["condition"] == "C0")]
        if len(r):
            c0[key] = (float(r["acceptance"].iloc[0]), float(r["ci_low"].iloc[0]), float(r["ci_high"].iloc[0]))
    dreal = (disc[(disc["scope"] == "pooled") & (disc["claim_type"] == "real_obscure")]
             .set_index("condition")["discrimination"].to_dict()) if not disc.empty else {}
    settings_text, setting_problems = reasoning_settings(raw_dir, models, cfg)
    counts = df.groupby("model").size().to_dict()
    pf_text = ", ".join(f"{m} {float(pf[m]['parse_failed_rate']):.1%}" for m in models
                        if m in pf and pf[m].get("parse_failed_rate") not in ("", None)) or "see parse_failures.csv"
    # §3.3 reads "{slot}: GPT-OSS-120B, ... (the model list)", so the slot is a lead-in with the run facts
    n_planned = sum(len(R.plan_cells(cfg, m, R.B.load_claims())) for m in cfg["models"])
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}
    models_paragraph = (f"{words.get(len(models), str(len(models)))} models ({len(df):,} of {n_planned:,} planned "
                        "cells completed: " + ", ".join(f"{m} {n}" for m, n in counts.items())
                        + f"; parse-failure rates: {pf_text})")
    in_df = set(df["response_id"])
    n_scored = sum(1 for k, j in G.judge_rows(graded_dir, "main", cfg).items() if j.get("valid") and k in in_df)
    scope_md = dist_table_md(sdist, "real_obscure")
    citation_md = table_md(rates[rates["scope"] == "pooled"] if not rates.empty else rates,
                           ["condition", "n", "credential_citation_rate", "abstention_rate", "mean_confidence"],
                           ["Condition", "n", "credential-citation rate", "abstention rate", "mean confidence"],
                           {"credential_citation_rate": pct, "abstention_rate": pct, "mean_confidence": lambda v: num(v, 0)})
    ctx = {"fam": fam, "h1_false": h1_false, "h5": h5r, "disc_real": dreal, "models": models, "c0": c0,
           "settings": settings_text, "models_paragraph": models_paragraph, "judge_model": judge_text(cfg),
           "n_judged": str(n_scored), "kappa": kappa_text(gate, cfg), "scope_md": scope_md, "citation_md": citation_md,
           "h3_dist": dist_row(sdist, "pooled", "real_obscure", "C1–C4"),
           "scope_withheld": withheld_text(gate) if source == "withheld" else ""}
    slots = build_slots(ctx)
    draft_text = Path(draft).read_text(encoding="utf-8") if Path(draft).exists() else ""
    entries = placeholder_entries(draft_text, slots)
    synthetic = bool(df["synthetic"].any())
    notes = draft_notes(draft_text)
    summary = render_summary(entries, fam, per_model_df, raw_dir, source, df, synthetic, setting_problems, sdist, notes,
                             gate=gate, forced=forced)
    (out / "results_summary.md").write_text(summary, encoding="utf-8", newline="\n")
    if draft_text:
        banner = ("<!-- AUTO-FILLED PREVIEW written by src/analyse.py"
                  + (" from SYNTHETIC DATA: NOT RESULTS" if synthetic else "")
                  + ". Check every sentence against results_summary.md before pasting. -->\n\n")
        (out / "REPORT_DRAFT.filled.md").write_text(banner + filled_draft(draft_text, entries), encoding="utf-8",
                                                     newline="\n")
    return {"entries": entries, "slots": slots, "tests": tests, "out": out, "h5": h5r, "fam": fam,
            "source": source, "gate": gate, "forced": forced, "figures": fig_paths, "problems": setting_problems}


def dist_row(sdist: pd.DataFrame, scope_name: str, ctype: str, conds: str) -> dict:
    if sdist.empty:
        return {}
    r = sdist[(sdist["scope"] == scope_name) & (sdist["claim_type"] == ctype) & (sdist["conditions"] == conds)]
    return r.iloc[0].to_dict() if len(r) else {}


def dist_table_md(sdist: pd.DataFrame, ctype: str) -> str:
    """Scope distribution by condition (pooled models) with 95% CIs over pairs."""
    rows = sdist[(sdist["scope"] == "pooled") & (sdist["claim_type"] == ctype)] if not sdist.empty else sdist
    if rows is None or rows.empty or not rows["n_judged"].any():
        return "_Not available yet._"
    cell = {k: (lambda key: lambda r: f"{pct(r[key])} ({pct(r[key + '_ci_low'])}–{pct(r[key + '_ci_high'])})")(k)
            for k in ("mention", "share_0", "share_1", "share_2")}
    caption = {"real_obscure": "Real-obscure pairs", "invented": "Invented pairs", "all": "All pairs"}[ctype]
    out = [f"{caption}, pooled models. Shares of 0, 1 and 2 are among justifications that mention the credential; "
           "95% CIs over pairs.", "",
           "| Conditions | judged | mention the credential | 0: support or misattribution | 1: partial | "
           "2: correct scope |", "|---|---|---|---|---|---|"]
    for _, r in rows.iterrows():
        out.append(f"| {r['conditions']} | {int(r['n_judged'])} | {cell['mention'](r)} | {cell['share_0'](r)} | "
                   f"{cell['share_1'](r)} | {cell['share_2'](r)} |")
    return "\n".join(out)


def draft_notes(draft_text: str) -> list[str]:
    """Checks on draft text that no slot covers: the cited pre-registration commit."""
    notes = []
    cited = re.search(r"rev (\d+(?:\.\d+)*), commit `([0-9a-f]{7,40})`", draft_text)
    latest = git_out("log", "-1", "--format=%h", "--", "PREREGISTRATION.md")
    if cited and latest and not (latest.startswith(cited.group(2)) or cited.group(2).startswith(latest)):
        notes.append(f"- §3 cites pre-registration rev {cited.group(1)}, commit `{cited.group(2)}`, but the latest "
                     f"commit touching PREREGISTRATION.md is `{latest}`. Cite the version in force when data "
                     "collection began, and list any later change in DEVIATIONS.md.")
    return notes


def gate_line(gate: dict | None) -> str:
    """The §5 (rev 3.4) judge-agreement gate in one phrase."""
    g = gate or {}
    k, n = num(g.get("kappa"), 2), (g.get("overall") or {}).get("n_both_scored", 0)
    return {"passed": f"the judges' weighted kappa is {k} on {n} responses, at least 0.6: judge results are reported",
            "failed": f"the judges' weighted kappa is {k} on {n} responses, below 0.6: judge results are withheld",
            "pending": f"the cross-check has {g.get('n_crosschecked', 0)} of {g.get('n_sample') or 100} responses: judge "
                       "results are withheld until the kappa is known",
            "none": "no main-judge scores yet"}[g.get("status", "none")]


def render_summary(entries, fam, per_model_df, raw_dir, source, df, synthetic, problems, sdist, notes=(),
                   gate=None, forced=False) -> str:
    lines = ["# Results summary", ""]
    if synthetic:
        lines += ["> **SYNTHETIC DATA. Nothing here is a result.**", ""]
    lines += [f"Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by `src/analyse.py` at commit "
              f"`{R.git_commit()}` from `{raw_dir}`: {len(df)} completed cells; models "
              f"{', '.join(sorted(df['model'].unique()))}. Scope-accuracy source: **{source}** ({gate_line(gate)}).", ""]
    if forced:
        lines += ["> **JUDGE RESULTS FORCED (`--scope-source judge`).** The pre-registered gate (§5, rev 3.4) has not "
                  "passed, so none of the scope-accuracy numbers below may be reported as results.", ""]
    stamps = sorted(t for t in df["timestamp_utc"] if t)
    if stamps:
        lines += [f"Responses collected from {stamps[0][:16].replace('T', ' ')} to {stamps[-1][:16].replace('T', ' ')} "
                  "UTC (first and last `timestamp_utc` among the analysed responses).", ""]
    for p in problems:
        lines += [f"> **PROTOCOL CHECK FAILED:** {p}. Reasoning must be fixed per model (CLAUDE.md); record this "
                  "in DEVIATIONS.md.", ""]
    lines += ["Headline numbers: real-obscure pairs for H1–H3 and H2b (pre-registration rev 3), all pairs for H4, "
              "invented minus real-obscure for H5 (exploratory). Differences are in percentage points unless marked; "
              "p_holm is Holm-adjusted over the eight primary tests. The tests and decision rules are those of "
              "PREREGISTRATION.md §7 (rev 3.3). Check every sentence against the tables below before pasting it.", "",
              "## Paste into REPORT_DRAFT.md", "",
              "`REPORT_DRAFT.filled.md` in this folder is the draft with these substituted, for checking.", ""]
    for k, e in enumerate(entries, 1):
        ph = e["placeholder"] if len(e["placeholder"]) <= 90 else e["placeholder"][:88] + "…}"
        lines += [f"### {k}. `{ph}`", "", f"Line {e['line']} ({e['section'] or 'top'})", "", e["text"], ""]
    lines += ["## Other text in REPORT_DRAFT.md to check", "",
              "- §4.2: the slot reports real-obscure false claims plus the pre-registered both-twin test; invented "
              "items are in §4.6.",
              "- §3 cites `DEVIATIONS.md`: list any deviations there, or state that there were none.",
              "- README and Appendix A: give the collection dates above. They should fall within the sprint "
              "(13–15 Nov 2026); only the pilot (10–11 Nov, excluded from analysis) came before it.",
              "- §4.8: use the per-model table and the scale comparison below.", *notes]
    if source == "withheld":
        lines += ["- §3.4 and §4.5: judge results are withheld (" + gate_line(gate) + "). Give the kappa, say that H3 "
                  "was not tested, and leave out the scope-accuracy table and examples."]
    lines += [""]
    flags = []
    for key, hyps in ((("pooled", "real_obscure"), ("H1", "H2", "H2b", "H3")), (("pooled", "all"), ("H4",))):
        for r in fam[key]:
            if r["primary"] and r["hypothesis"] in hyps and not isnan(r["p_holm"]) and not isnan(r["p_perm_holm"]) \
                    and (r["p_holm"] < ALPHA) != (r["p_perm_holm"] < ALPHA):
                flags.append(f"{r['hypothesis']} {r['comparison']} ({r['measure']}, {TYPE_LABEL[key[1]]}): t-test "
                             f"{p_is('p_holm', r['p_holm'])}, permutation {p_is('p_holm', r['p_perm_holm'])}")
    lines += ["## Robustness: t-test vs permutation test", ""]
    lines += (["The two tests disagree about significance for these headline tests. Report the t-test (the "
               "pre-specified primary) and give the permutation result alongside:", ""] + [f"- {f}" for f in flags]
              if flags else ["The sign-flip permutation test agrees with the t-test about significance on every "
                             "headline test."])
    lines += [""]
    for label, key in (("pooled models, real-obscure pairs (headline)", ("pooled", "real_obscure")),
                       ("pooled models, invented pairs", ("pooled", "invented")),
                       ("pooled models, all pairs", ("pooled", "all"))):
        rows = pd.DataFrame(fam[key])
        rows["Δ"] = [value(r) for r in fam[key]]
        rows["95% CI"] = [f"{value(r, 'ci_low')} to {value(r, 'ci_high')}" for r in fam[key]]
        lines += [f"## Tests: {label}", "",
                  table_md(rows, ["hypothesis", "comparison", "measure", "sample", "primary", "n_pairs", "Δ", "95% CI",
                                  "p", "p_holm", "p_perm_holm"],
                           ["H", "comparison", "measure", "sample", "primary", "pairs", "Δ", "95% CI", "p", "p_holm",
                            "p_holm (permutation)"],
                           {"p": fmt_p, "p_holm": fmt_p, "p_perm_holm": fmt_p}), ""]
    lines += ["Acceptance and discrimination-index differences are in percentage points; confidence in points on the "
              "0–100 scale; H3 is a share. Tests are paired t-tests over pairs. The permutation column is the "
              "robustness check: with n pairs its smallest possible p is 2/2^n, so it needs at least 9 pairs to reach "
              "p_holm < 0.05 over eight tests. `primary_tests.csv` has every model and claim type.", ""]
    h3 = find(fam[("pooled", "real_obscure")], "H3", "C1-C4 vs 50%", "share of credential mentions scored 2")
    verdict = (f"Judge results are withheld: {withheld_text(gate or {})}" if source == "withheld" else
               f"Real-obscure pairs: **{'SUPPORTED' if h3_verdict(h3)[0] else 'NOT SUPPORTED'}**. {h3_verdict(h3)[1]}")
    lines += ["## Scope accuracy (H3)", "",
              "Rule (§7, rev 3.3): H3 is supported only if the upper bound of the 95% CI for the share of "
              "credential-mentioning justifications scored 2 is below 50% and its p_holm is below .05. Rev 3.4 (§5): "
              "judge results are reported only if the two judges' weighted kappa is at least 0.6; otherwise H3 is "
              f"not tested and enters Holm with p = 1. Now: {gate_line(gate)}. {verdict}", ""]
    if gate and (gate.get("overall") or {}).get("n_items"):
        o = gate["overall"]
        lines += [f"Judges' agreement on the cross-check sample: linear-weighted kappa {num(o['weighted_kappa_linear'], 2)} "
                  f"(n = {o['n_both_scored']} both scored 0–2); Cohen's kappa over four categories "
                  f"{num(o['cohen_kappa_4cat'], 2)}; exact agreement {pct(o['exact_agreement'])}; N/A agreement "
                  f"{pct(o['na_agreement'])}. By study-model family: "
                  + ", ".join(f"{f} {num(v['weighted_kappa_linear'], 2)} (n = {v['n_both_scored']})"
                              for f, v in gate.get("by_family", {}).items()) + ".", ""]
    for ctype in ("real_obscure", "invented", "all"):
        lines += [dist_table_md(sdist, ctype), ""]
    lines += ["Per model: `scope_distribution.csv`. Figure 3 shows raw shares of all judged justifications, "
              "including those that do not mention the credential.", ""]
    shown = pd.DataFrame({
        "Model": per_model_df["model"], "cells": per_model_df["cells"],
        "C0 acceptance": per_model_df["c0_acceptance"].map(pct),
        "H1 C1−C0": per_model_df["h1_c1_vs_c0_real"].map(signed),
        "H2 C3−C2": per_model_df["h2_c3_vs_c2_real"].map(signed),
        "H2 C4−C1": per_model_df["h2_c4_vs_c1_real"].map(signed),
        "H2b index C5−C0": per_model_df["h2b_disc_c5_vs_c0_real"].map(signed),
        "H4 interpreter−none": per_model_df["h4_interpreter_all"].map(signed),
        "scope: share scored 2": per_model_df["scope_correct_share"].map(pct),
        "parse failures": per_model_df["parse_failed_rate"].map(lambda v: pct(v, 1)),
        "cost USD": per_model_df["cost_usd"].map(lambda v: num(v, 2))})
    lines += ["## Per model", "",
              "Differences in points; H1, H2 and H2b on real-obscure pairs, H4 on all pairs.", "",
              table_md(shown, list(shown.columns), list(shown.columns)), ""]
    pm = per_model_df.set_index("model")
    if {"gpt-oss-120b", "gpt-oss-20b"} <= set(pm.index):
        lines += [f"**Scale within family (§6).** Share of credential mentions scored 2: "
                  f"{pct(pm.loc['gpt-oss-120b', 'scope_correct_share'])} for gpt-oss-120b vs "
                  f"{pct(pm.loc['gpt-oss-20b', 'scope_correct_share'])} for gpt-oss-20b. C1 − C0 on real-obscure pairs: "
                  f"{signed(pm.loc['gpt-oss-120b', 'h1_c1_vs_c0_real'])} vs "
                  f"{signed(pm.loc['gpt-oss-20b', 'h1_c1_vs_c0_real'])} points.", ""]
    lines += ["## Files", "", "| File | Contents |", "|---|---|",
              "| `fig1_acceptance.png` | Figure 1 (§4.2): acceptance by condition, claim type and truth |",
              "| `fig2_discrimination.png` | Figure 2 (§4.4): discrimination index by condition |",
              "| `fig3_scope_accuracy.png` | Scope scores by condition (§4.5) |",
              "| `fig4_interpreter.png` | Interpreter arm (§4.7) |",
              "| `primary_tests.csv` | Every primary test per model scope and claim type, with Holm |",
              "| `acceptance_by_condition.csv` | Acceptance per model, claim type, truth and condition, plus pooled |",
              "| `discrimination_by_condition.csv` | Discrimination index, with floor and ceiling pair counts |",
              "| `citation_abstention_confidence.csv` | Credential-citation rate, abstention rate, mean confidence |",
              "| `confidence_delta.csv` | Confidence minus the same item's C0 mean |",
              "| `scope_accuracy.csv` | Raw scope score counts per condition (Figure 3) |",
              "| `scope_distribution.csv` | H3: mention share and 0/1/2 shares with 95% CIs, per scope and claim type |",
              "| `h5_unrecognised_sources.csv` | H5 (exploratory) |",
              "| `rep_variance.csv` | Repetition variance (§7) |",
              "| `per_model.csv` | Per-model summary (§4.8) |",
              "| `example_justifications.md` | Candidate verbatim examples for §4.5 |",
              "| `REPORT_DRAFT.filled.md` | The draft with every slot substituted, for checking |"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=REPO / "models.yaml")
    ap.add_argument("--raw-dir", type=Path, default=DATA / "raw")
    ap.add_argument("--graded-dir", type=Path, default=DATA / "graded")
    ap.add_argument("--pilot-dir", type=Path, default=DATA / "pilot")
    ap.add_argument("--out", type=Path, default=DATA / "results")
    ap.add_argument("--draft", type=Path, default=REPO / "REPORT_DRAFT.md")
    ap.add_argument("--scope-source", choices=("auto", "judge", "none"), default="auto",
                    help="auto follows the §5 gate; judge forces the judge's scores in (flagged as not reportable)")
    a = ap.parse_args(argv)
    res = analyse(a.raw_dir, a.graded_dir, a.out, a.pilot_dir, a.draft, a.config, a.scope_source)
    slots = [e for e in res["entries"] if e["slot"] != "_INSTRUCTION"]
    missing = [e for e in slots if e["text"] == NO_VALUE]
    print(f"results -> {a.out}")
    print(f"  scope-accuracy source: {res['source']} ({gate_line(res['gate'])}); {len(slots)} draft slots filled "
          f"automatically, {len(missing)} need a hand fill")
    if res["forced"]:
        print("  JUDGE RESULTS FORCED: the pre-registered gate has not passed; do not report them")
    for e in missing:
        print(f"  by hand: {e['placeholder'][:70]} (line {e['line']})")
    for p in res["problems"]:
        print(f"  PROTOCOL CHECK FAILED: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
