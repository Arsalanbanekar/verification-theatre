"""Run the study: dispatch, rate limits, cost, retries and resumption. One worker thread per model.

  python src/runner.py --dry-run            build every prompt, count calls, project cost; no calls, no writes
  python src/runner.py                      the main run: shows projected cost, asks y/n, then runs
  python src/runner.py --yes                the same without the question
  python src/runner.py --models gpt-oss-120b,gemini-3.5-flash-lite
  python src/runner.py --check-models       confirm the configured model IDs exist (lists models only)

Subsets: --claims real-01-t,inv-01 (claim or pair ids)  --conditions C0,C1  --reps 1  --limit 30

Data. data/raw/{model}.jsonl is append-only, one line per model response, flushed and fsynced
after each. A cell (model, claim_id, condition, interpreter, rep) is done once it has a line
with status "ok" or "parse_failed"; re-running skips done cells. Events (rate limits, errors,
stops) go to data/logs/{model}.events.jsonl; the randomised cell order to data/logs/.

Cost. Every response's USD cost is computed from its measured token usage and the prices in
models.yaml, and written to its raw line. All spend on disk (data/raw and data/pilot) counts
against budget.hard_stop_usd; each call reserves its worst-case cost before it is sent, so the
cap holds even with several models running at once.

Keys come from the environment or a .env file: GROQ_API_KEY, GEMINI_API_KEY.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import yaml

if __package__ in (None, ""):  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import build_documents as B
from src.output_schema import SCHEMA, parse_response
from src.providers import PROVIDERS

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
SPEND_DIRS = (DATA / "raw", DATA / "pilot")   # every response here counts against the budget
DONE_STATUSES = ("ok", "parse_failed")
CHARS_PER_TOKEN = 3.6           # rough prompt-size estimate, calibrated against measured usage when available
INPUT_MARGIN = 1.5              # worst-case factor on the prompt estimate when reserving budget
TRANSIENT_STATUSES = {408, 409, 498}   # plus every 5xx; 498 is Groq "capacity exceeded"
MAX_TRANSIENT_RETRIES = 5
MAX_UNCLASSIFIED_429 = 6        # consecutive unclassifiable 429s are treated as a daily stop
PRINT_LOCK = threading.Lock()


def SLEEP(stop: threading.Event, seconds: float) -> None:
    """Interruptible sleep; tests replace it."""
    if seconds > 0:
        stop.wait(seconds)


def say(msg: str) -> None:
    with PRINT_LOCK:
        print(msg, flush=True)


# ---------------------------------------------------------------- time

try:
    from zoneinfo import ZoneInfo
    _PACIFIC = ZoneInfo("America/Los_Angeles")
except Exception:  # no tz database: fall back to the US daylight-saving rule
    _PACIFIC = None


def _us_pacific_offset(t_utc: dt.datetime) -> dt.timedelta:
    y = t_utc.year
    mar1, nov1 = dt.date(y, 3, 1), dt.date(y, 11, 1)
    second_sun_mar = mar1 + dt.timedelta(days=(6 - mar1.weekday()) % 7 + 7)
    first_sun_nov = nov1 + dt.timedelta(days=(6 - nov1.weekday()) % 7)
    start = dt.datetime.combine(second_sun_mar, dt.time(10), dt.timezone.utc)  # 02:00 PST
    end = dt.datetime.combine(first_sun_nov, dt.time(9), dt.timezone.utc)      # 02:00 PDT
    return dt.timedelta(hours=-7 if start <= t_utc < end else -8)


def to_pacific(t_utc: dt.datetime) -> dt.datetime:
    if _PACIFIC is not None:
        return t_utc.astimezone(_PACIFIC)
    off = _us_pacific_offset(t_utc)
    return (t_utc + off).replace(tzinfo=dt.timezone(off))


def next_pacific_midnight(t_utc: dt.datetime) -> dt.datetime:
    """The next midnight in US Pacific time, as an aware UTC datetime."""
    local = to_pacific(t_utc)
    midnight = dt.datetime.combine(local.date() + dt.timedelta(days=1), dt.time(0))
    if _PACIFIC is not None:
        return midnight.replace(tzinfo=_PACIFIC).astimezone(dt.timezone.utc)
    return (midnight - local.utcoffset()).replace(tzinfo=dt.timezone.utc)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def resume_message(t_utc: dt.datetime) -> str:
    r = next_pacific_midnight(t_utc)
    return (f"resume after {to_pacific(r):%Y-%m-%d %H:%M} Pacific = {r:%H:%M} UTC = "
            f"{r.astimezone():%Y-%m-%d %H:%M} local")


# ---------------------------------------------------------------- config, env, plan

def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for name, m in cfg["models"].items():
        if m["provider"] not in PROVIDERS:
            raise ValueError(f"{name}: unknown provider {m['provider']!r}")
    cfg.setdefault("budget", {})
    return cfg


def load_env(path: Path) -> None:
    """Set variables from a .env file without overriding ones already in the environment.
    Values are never printed."""
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def setting(cfg: dict, name: str, key: str):
    m = cfg["models"][name]
    return m[key] if key in m else cfg["defaults"][key]


@dataclass(frozen=True)
class Cell:
    model: str
    claim_id: str
    condition: str
    interpreter: bool
    rep: int

    def key(self):
        return (self.model, self.claim_id, self.condition, self.interpreter, self.rep)


def plan_cells(cfg: dict, name: str, claims: list[dict], *, reps=None, claim_filter=None,
               cond_filter=None) -> list[Cell]:
    m = cfg["models"][name]
    reps = range(reps if reps is not None else setting(cfg, name, "reps"))
    cells = []
    if m["design"] == "full":
        for c in claims:
            cells += [Cell(name, c["id"], cond, False, r) for cond in B.CONDITIONS for r in reps]
        if m.get("interpreter_arm"):
            for c in claims:
                cells += [Cell(name, c["id"], cond, True, r) for cond in ("C1", "C2") for r in reps]
    elif m["design"] == "spot_check":
        spot = m["spot_check"]
        for c in claims:
            if c["pair_id"] in spot["pairs"]:
                cells += [Cell(name, c["id"], cond, False, r) for cond in spot["conditions"] for r in reps]
    else:
        raise ValueError(f"{name}: unknown design {m['design']!r}")
    if claim_filter:
        cells = [x for x in cells if x.claim_id in claim_filter or x.claim_id[:-2] in claim_filter]
    if cond_filter:
        cells = [x for x in cells if x.condition in cond_filter]
    return cells


def _int_seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) % (2 ** 31)


def order_cells(cells: list[Cell], base_seed: int, model: str) -> tuple[list[Cell], int]:
    """Randomised per model, reproducibly: same plan and seed, same order."""
    seed = _int_seed(base_seed, "order", model)
    ordered = sorted(cells, key=lambda c: c.key())
    random.Random(seed).shuffle(ordered)
    return ordered, seed


def call_seed(base_seed: int, cell: Cell, attempt: int) -> int:
    return _int_seed(base_seed, *cell.key()) + attempt - 1


def plan_hash(cells: list[Cell]) -> str:
    return hashlib.sha256(json.dumps([list(c.key()) for c in cells]).encode()).hexdigest()[:8]


def read_raw(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # a torn final line from a crash; never rewritten, simply ignored
    return out


def done_keys(records: list[dict]) -> set:
    return {(r["model"], r["claim_id"], r["condition"], r["interpreter"], r["rep"])
            for r in records if r.get("status") in DONE_STATUSES}


def git_commit() -> str:
    try:
        h = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                           timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return (h or "unknown") + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def append_jsonl(path: Path, obj: dict) -> None:
    line = json.dumps(obj, ensure_ascii=False)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def estimate_tokens(messages: list[dict]) -> int:
    return int(sum(len(m["content"]) for m in messages) / CHARS_PER_TOKEN)


def unique_dirs(*dirs) -> list[Path]:
    seen, out = set(), []
    for d in dirs:
        p = Path(d).resolve()
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ---------------------------------------------------------------- cost and budget

def unit_prices(m: dict) -> tuple[float, float]:
    """USD per input token and per output token."""
    p = m.get("price_usd_per_mtok") or {}
    return float(p.get("input", 0.0)) / 1e6, float(p.get("output", 0.0)) / 1e6


def usage_cost(m: dict, usage: dict) -> tuple[int, int, float]:
    tin, tout = PROVIDERS[m["provider"]].token_split(usage or {})
    pin, pout = unit_prices(m)
    return tin, tout, tin * pin + tout * pout


def spend_on_disk(cfg: dict, dirs) -> dict[str, float]:
    spent = {}
    for name, m in cfg["models"].items():
        for d in dirs:
            for r in read_raw(Path(d) / f"{name}.jsonl"):
                spent[name] = spent.get(name, 0.0) + usage_cost(m, r.get("usage") or {})[2]
    return spent


class Budget:
    """Shared spend tracker. reserve() before a call, settle() after it."""

    def __init__(self, cap_usd, spent_by_model):
        self.cap = cap_usd
        self.lock = threading.Lock()
        self.spent = dict(spent_by_model)
        self.reserved = 0.0
        self._announced = False

    def total(self) -> float:
        with self.lock:
            return sum(self.spent.values())

    def reserve(self, amount: float) -> bool:
        with self.lock:
            if amount > 0 and self.cap is not None and sum(self.spent.values()) + self.reserved + amount > self.cap:
                return False
            self.reserved += amount
            return True

    def settle(self, model: str, reserved: float, actual: float) -> None:
        with self.lock:
            self.reserved -= reserved
            self.spent[model] = self.spent.get(model, 0.0) + actual

    def announce_once(self) -> bool:
        with self.lock:
            first, self._announced = not self._announced, True
            return first


def calibration(cfg: dict, name: str, dirs) -> tuple[float, float, int]:
    """(measured/estimated prompt-token ratio, mean output tokens, responses measured) on disk."""
    m = cfg["models"][name]
    prov = PROVIDERS[m["provider"]]
    est_sum = meas_sum = 0
    outs = []
    for d in dirs:
        for r in read_raw(Path(d) / f"{name}.jsonl"):
            tin, tout = prov.token_split(r.get("usage") or {})
            if r.get("prompt_tokens_est") and tin:
                est_sum += r["prompt_tokens_est"]
                meas_sum += tin
            if tout:
                outs.append(tout)
    ratio = meas_sum / est_sum if est_sum else 1.0
    out = sum(outs) / len(outs) if outs else float(setting(cfg, name, "expected_output_tokens"))
    return ratio, out, len(outs)


def projection(cfg, plans, ctx, claims_by_id, out_dir, spend_dirs) -> tuple[list[dict], dict]:
    """Per-model calls and USD still to spend, from measured token usage where it exists."""
    spent = spend_on_disk(cfg, spend_dirs)
    today = dt.date.today()
    rows = []
    for name, (cells, _seed) in plans.items():
        m = cfg["models"][name]
        done = done_keys(read_raw(Path(out_dir) / f"{name}.jsonl"))
        ratio, out_tok, n_meas = calibration(cfg, name, spend_dirs)
        pin, pout = unit_prices(m)
        hashes, est_in = set(), []
        for c in cells:  # build every prompt, not only the remaining ones
            msgs = B.build_messages(ctx, claims_by_id[c.claim_id], c.condition, c.interpreter, today)
            hashes.add(B.prompt_hash(msgs))
            if c.key() not in done:
                est_in.append(estimate_tokens(msgs) * ratio)
        todo = len(est_in)
        rows.append(dict(model=name, planned=len(cells), done=len(cells) - todo, todo=todo,
                         in_per_call=(sum(est_in) / todo) if todo else 0.0, out_per_call=out_tok,
                         usd_left=sum(e * pin + out_tok * pout for e in est_in), spent=spent.get(name, 0.0),
                         basis=f"measured ({n_meas} responses)" if n_meas else "estimate",
                         distinct_prompts=len(hashes), limits=m.get("limits") or {}))
    return rows, spent


def print_projection(cfg, rows, spent) -> float:
    cap = cfg["budget"].get("hard_stop_usd")
    header = (f"{'model':22} {'planned':>7} {'done':>6} {'to run':>6} {'~tok/call':>9} {'~days':>6} "
              f"{'spent $':>8} {'~$ left':>8}  basis")
    say(header)
    say("-" * (len(header) + 12))
    for r in rows:
        per_call = r["in_per_call"] + r["out_per_call"]
        lim = r["limits"]
        caps = [lim["rpd"]] if lim.get("rpd") else []
        if lim.get("tpd") and per_call:
            caps.append(lim["tpd"] / per_call)
        if lim.get("rpm"):
            caps.append(lim["rpm"] * 60 * 24)
        if lim.get("tpm") and per_call:
            caps.append(lim["tpm"] * 60 * 24 / per_call)
        days = r["todo"] / min(caps) if caps else 0.0
        say(f"{r['model']:22} {r['planned']:7} {r['done']:6} {r['todo']:6} {per_call:9.0f} {days:6.2f} "
            f"{r['spent']:8.3f} {r['usd_left']:8.3f}  {r['basis']}")
    other = sum(v for k, v in spent.items() if k not in {r["model"] for r in rows})
    total_spent = sum(spent.values())
    total = total_spent + sum(r["usd_left"] for r in rows)
    say("-" * (len(header) + 12))
    say(f"{'TOTAL':22} {sum(r['planned'] for r in rows):7} {sum(r['done'] for r in rows):6} "
        f"{sum(r['todo'] for r in rows):6} {'':9} {'':6} {total_spent:8.3f} {total - total_spent:8.3f}")
    say(f"Projected total spend ${total:.2f} (already spent ${total_spent:.3f}"
        f"{f', of which ${other:.3f} on models not in this run' if other else ''}); hard stop ${cap:.2f}."
        if cap is not None else f"Projected total spend ${total:.2f}.")
    say("~tok/call = prompt (chars/3.6, scaled by measured usage when available) + output. "
        "Parse retries add calls.")
    return total


# ---------------------------------------------------------------- progress

class Progress:
    def __init__(self):
        self.lock = threading.Lock()
        self.rows: dict[str, dict] = {}

    def init(self, name, total, done, ok, failed, usd=0.0):
        with self.lock:
            self.rows[name] = dict(total=total, done=done, ok=ok, failed=failed, this_run=0, usd=usd,
                                   started=time.time(), state="starting")

    def bump(self, name, status, cell_done, cost=0.0):
        with self.lock:
            r = self.rows[name]
            r["this_run"] += 1
            r["usd"] += cost
            if cell_done:
                r["done"] += 1
                r["ok" if status == "ok" else "failed"] += 1

    def state(self, name, text):
        with self.lock:
            self.rows[name]["state"] = text

    def render(self) -> str:
        with self.lock:
            lines = [f"[{dt.datetime.now():%H:%M:%S}] progress"]
            for name, r in self.rows.items():
                mins = max((time.time() - r["started"]) / 60, 1e-9)
                lines.append(f"  {name:22} {r['done']:4}/{r['total']:<4} done (ok {r['ok']}, parse_failed {r['failed']}), "
                             f"{r['total'] - r['done']} left | ${r['usd']:.3f} | this run {r['this_run']} calls, "
                             f"{r['this_run'] / mins:.1f}/min | {r['state']}")
            lines.append(f"  total spend on disk ${sum(r['usd'] for r in self.rows.values()):.3f}")
            return "\n".join(lines)


# ---------------------------------------------------------------- worker

class Stop(Exception):
    pass


class Pacer:
    """Requests-per-minute spacing plus a 60-second sliding token window."""

    def __init__(self, rpm, tpm, stop, clock=time.monotonic):
        self.interval = 60.0 / rpm if rpm else 0.0
        self.tpm, self.stop, self.clock = tpm, stop, clock
        self.last = float("-inf")
        self.window = deque()

    def wait(self, est_tokens):
        while True:
            now = self.clock()
            while self.window and now - self.window[0][0] > 60:
                self.window.popleft()
            gap = self.interval - (now - self.last)
            used = sum(t for _, t in self.window)
            if self.tpm and self.window and used + est_tokens > self.tpm:
                gap = max(gap, 60 - (now - self.window[0][0]) + 0.1)
            if gap <= 0:
                self.last = now
                return
            SLEEP(self.stop, gap)
            if self.stop.is_set():
                raise Stop("stopped")

    def record(self, tokens):
        self.window.append((self.clock(), tokens))


class Worker(threading.Thread):
    def __init__(self, *, name, cfg, ctx, claims_by_id, cells, plan_id, out_dir, logs_dir, api_key,
                 limit, progress, stop, provider_stop, budget, run_id, commit, records):
        super().__init__(name=f"worker-{name}", daemon=True)
        self.model, self.cfg, self.ctx = name, cfg, ctx
        self.m = cfg["models"][name]
        self.provider = PROVIDERS[self.m["provider"]]
        self.claims_by_id, self.cells, self.plan_id = claims_by_id, cells, plan_id
        self.raw_path = Path(out_dir) / f"{name}.jsonl"
        self.events_path = Path(logs_dir) / f"{name}.events.jsonl"
        self.api_key, self.limit = api_key, limit
        self.progress, self.stop, self.provider_stop, self.budget = progress, stop, provider_stop, budget
        self.run_id, self.commit = run_id, commit
        lim = self.m.get("limits") or {}
        self.rpd, self.tpd = lim.get("rpd"), lim.get("tpd")
        self.pacer = Pacer(lim.get("rpm"), lim.get("tpm"), stop)
        self.prices = unit_prices(self.m)
        self.temperature = setting(cfg, name, "temperature")
        self.max_out = setting(cfg, name, "max_output_tokens")
        self.expected_out = setting(cfg, name, "expected_output_tokens")
        self.timeout = setting(cfg, name, "request_timeout_s")
        self.base_seed = cfg["defaults"]["base_seed"]
        self.done = done_keys(records)
        self.day = to_pacific(utcnow()).date()
        today = [r for r in records if r.get("pacific_date") == self.day.isoformat()]
        self.calls_today = len(today)
        self.tokens_today = sum((self.provider.total_tokens(r.get("usage") or {}) or 0) for r in today)
        self.calls_this_run = 0
        self.last_cost = 0.0

    # -- logging

    def event(self, kind, cell=None, **fields):
        rec = {"timestamp_utc": utcnow().isoformat(), "run_id": self.run_id, "model": self.model, "event": kind}
        if cell is not None:
            rec.update(claim_id=cell.claim_id, condition=cell.condition, interpreter=cell.interpreter, rep=cell.rep)
        rec.update(fields)
        append_jsonl(self.events_path, rec)

    def stop_for_day(self, reason, cell=None, hint=None):
        msg = resume_message(utcnow())
        if hint:
            msg += f" (provider hint: retry after {hint:.0f}s)"
        self.event("daily_limit", cell, reason=reason, resume=msg)
        self.progress.state(self.model, f"STOPPED for today: {reason}; {msg}")
        say(f"[{self.model}] daily limit reached ({reason}). Stopping this model; {msg}.")
        raise Stop(reason)

    def stop_for_budget(self, cell):
        cap, total = self.budget.cap, self.budget.total()
        if self.budget.announce_once():
            say(f"BUDGET HARD STOP: ${total:.4f} spent of the ${cap:.2f} cap (models.yaml budget.hard_stop_usd); "
                "the next call could pass it. Stopping every paid model. Completed cells are kept.")
        self.event("budget_stop", cell, spent_usd=round(total, 6), cap_usd=cap)
        self.progress.state(self.model, f"STOPPED: budget cap ${cap:.2f} reached (spent ${total:.4f})")
        raise Stop("budget")

    # -- main loop

    def run(self):
        try:
            todo = [(i, c) for i, c in enumerate(self.cells) if c.key() not in self.done]
            for index, cell in todo:
                if self.stop.is_set():
                    self.progress.state(self.model, "stopped (interrupted)")
                    return
                if self.limit is not None and self.calls_this_run >= self.limit:
                    self.progress.state(self.model, f"stopped: --limit {self.limit} reached")
                    return
                self.progress.state(self.model, "running")
                self.do_cell(index, cell)
            self.progress.state(self.model, "finished: every planned cell is done")
        except Stop:
            pass
        except Exception as e:  # keep other models running; leave a trace
            self.event("crash", error=repr(e), traceback=traceback.format_exc())
            self.progress.state(self.model, f"CRASHED: {e!r} (see events log)")

    def do_cell(self, index, cell):
        claim = self.claims_by_id[cell.claim_id]
        run_date = dt.date.today()
        messages = B.build_messages(self.ctx, claim, cell.condition, cell.interpreter, run_date)
        phash = B.prompt_hash(messages)
        est_in = estimate_tokens(messages)
        for attempt in (1, 2):
            seed = call_seed(self.base_seed, cell, attempt)
            payload = self.provider.build_payload(self.m, messages, temperature=self.temperature, seed=seed,
                                                  max_output_tokens=self.max_out, schema=SCHEMA)
            started = utcnow()
            res = self.send(cell, payload, est_in)
            if res is None:
                return  # transient failures; the cell stays undone for the next run
            comp = self.provider.extract(res.body)
            parsed, err = parse_response(comp.text)
            status = "ok" if parsed else ("parse_retry" if attempt == 1 else "parse_failed")
            tin, tout, cost = usage_cost(self.m, comp.usage)
            append_jsonl(self.raw_path, {
                "schema": 1, "run_id": self.run_id, "git_commit": self.commit,
                "timestamp_utc": started.isoformat(), "pacific_date": to_pacific(started).date().isoformat(),
                "model": self.model, "provider": self.provider.NAME, "model_id": self.m["model_id"],
                "claim_id": cell.claim_id, "pair_id": claim["pair_id"], "claim_type": claim["claim_type"],
                "truth_value": claim["truth_value"], "condition": cell.condition,
                "interpreter": cell.interpreter, "rep": cell.rep, "attempt": attempt,
                "plan": self.plan_id, "order_index": index, "run_date": run_date.isoformat(),
                "prompt_hash": phash, "prompt_tokens_est": est_in, "seed": seed, "temperature": self.temperature,
                "max_output_tokens": self.max_out, "reasoning_setting": self.provider.reasoning_setting(self.m),
                "request": {"endpoint": self.provider.endpoint(self.m), "body": payload},
                "http_status": res.status, "latency_s": round(res.latency_s, 3),
                "rate_headers": {h: res.headers[h] for h in self.provider.RATE_HEADERS if h in res.headers},
                "raw_text": comp.text, "reasoning_text": comp.reasoning, "finish_reason": comp.finish_reason,
                "usage": comp.usage, "input_tokens": tin, "output_tokens": tout, "cost_usd": round(cost, 8),
                "response_meta": comp.extra, "response_body": res.body,
                "parsed": parsed, "parse_error": err, "status": status,
            })
            cell_done = status in DONE_STATUSES
            self.progress.bump(self.model, status, cell_done, cost)
            if cell_done:
                self.done.add(cell.key())
                return

    def send(self, cell, payload, est_in):
        est = est_in + self.expected_out
        pin, pout = self.prices
        worst = est_in * INPUT_MARGIN * pin + self.max_out * pout
        transient = unclassified = 0
        while True:
            if self.stop.is_set():
                raise Stop("interrupted")
            if self.provider_stop.is_set():
                self.progress.state(self.model, f"STOPPED: {self.provider.NAME} blocked API access (see message above)")
                raise Stop("provider blocked")
            today = to_pacific(utcnow()).date()
            if today != self.day:
                self.day, self.calls_today, self.tokens_today = today, 0, 0
            if self.rpd and self.calls_today >= self.rpd:
                self.stop_for_day(f"{self.calls_today} calls today reaches the configured RPD {self.rpd}", cell)
            if self.tpd and self.tokens_today + est > self.tpd:
                self.stop_for_day(f"~{self.tokens_today} tokens today; the next call would pass the configured TPD {self.tpd}", cell)
            self.pacer.wait(est)
            if not self.budget.reserve(worst):
                self.stop_for_budget(cell)
            res = self.provider.send(self.m, payload, self.api_key, self.timeout)
            self.calls_this_run += 1
            if res.status == 200 and isinstance(res.body, dict):
                usage = self.provider.extract(res.body).usage
                used = self.provider.total_tokens(usage) or est
                self.last_cost = usage_cost(self.m, usage)[2]
                self.budget.settle(self.model, worst, self.last_cost)
                self.pacer.record(used)
                self.calls_today += 1
                self.tokens_today += used
                return res
            self.budget.settle(self.model, worst, 0.0)
            if res.status == 429:
                rl = self.provider.classify_429(res)
                self.event("http_429", cell, scope=rl.scope, wait_s=rl.wait_s, detail=rl.detail,
                           headers={h: res.headers[h] for h in self.provider.RATE_HEADERS if h in res.headers})
                if rl.scope == "day":
                    self.stop_for_day("provider reports the daily quota is exhausted", cell, rl.wait_s)
                unclassified = unclassified + 1 if rl.scope == "unknown" else 0
                if unclassified >= MAX_UNCLASSIFIED_429:
                    self.stop_for_day(f"{unclassified} consecutive 429s that could not be classified; "
                                      "assuming a daily quota", cell, rl.wait_s)
                wait = rl.wait_s if rl.wait_s is not None else min(300.0, 15.0 * 2 ** min(unclassified, 4))
                wait += random.uniform(0, 2)
                self.progress.state(self.model, f"waiting {wait:.0f}s (per-minute limit)")
                SLEEP(self.stop, wait)
                continue
            if res.status == 400 and "blocked_api_access" in (res.text or ""):
                self.provider_stop.set()
                self.event("blocked_api_access", cell, status=res.status, body=res.text[:2000])
                say(f"[{self.model}] HTTP 400 blocked_api_access: {self.provider.NAME} has blocked API access for "
                    f"this key's organisation. Stopping ALL {self.provider.NAME} models. Check the account "
                    "(console.groq.com for Groq: billing, spend limit, account status), then re-run the same "
                    "command; completed cells are kept.")
                self.progress.state(self.model, f"STOPPED: {self.provider.NAME} blocked_api_access")
                raise Stop("blocked_api_access")
            if (res.status is None or res.status in TRANSIENT_STATUSES or res.status >= 500
                    or res.status == 200):
                transient += 1
                self.event("transient_error", cell, status=res.status, error=res.error, body=res.text[:500],
                           attempt=transient)
                if transient > MAX_TRANSIENT_RETRIES:
                    self.progress.state(self.model, "skipping a cell after repeated transient errors")
                    return None
                SLEEP(self.stop, min(120.0, 5.0 * 2 ** transient) + random.uniform(0, 3))
                continue
            # any other 4xx is a request or configuration problem: stop this model, keep the evidence
            self.event("fatal_http_error", cell, status=res.status, body=res.text[:2000])
            self.progress.state(self.model, f"STOPPED: HTTP {res.status} (see events log): {res.text[:160]}")
            say(f"[{self.model}] HTTP {res.status}; stopping this model. {res.text[:300]}")
            raise Stop(f"http {res.status}")


# ---------------------------------------------------------------- commands

def dry_run(cfg, plans, ctx, claims_by_id, out_dir) -> int:
    say("DRY RUN: builds every prompt and projects cost; makes no API calls and writes nothing.\n")
    rows, spent = projection(cfg, plans, ctx, claims_by_id, out_dir, unique_dirs(out_dir, *SPEND_DIRS))
    print_projection(cfg, rows, spent)
    return 0


def check_models(cfg, names) -> int:
    load_env(REPO / ".env")
    status = 0
    for prov_name in sorted({cfg["models"][n]["provider"] for n in names}):
        prov = PROVIDERS[prov_name]
        key = os.environ.get(prov.KEY_ENV)
        if not key:
            say(f"{prov_name}: {prov.KEY_ENV} not set")
            status = 1
            continue
        available = set(prov.list_models(key))
        for n in names:
            if cfg["models"][n]["provider"] == prov_name:
                mid = cfg["models"][n]["model_id"]
                ok = mid in available
                status |= 0 if ok else 1
                say(f"{prov_name}: {mid:28} {'available' if ok else 'NOT LISTED'}")
    return status


def confirm(question: str) -> bool:
    try:
        return input(question).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def start_workers(cfg, plans, ctx, claims_by_id, out_dir, logs_dir, limit, progress, stop) -> list[Worker]:
    load_env(REPO / ".env")
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_id, commit = uuid.uuid4().hex[:12], git_commit()
    budget = Budget(cfg["budget"].get("hard_stop_usd"), spend_on_disk(cfg, unique_dirs(out_dir, *SPEND_DIRS)))
    provider_stops = {p: threading.Event() for p in PROVIDERS}
    workers = []
    for name, (cells, order_seed) in plans.items():
        m = cfg["models"][name]
        prov = PROVIDERS[m["provider"]]
        key = os.environ.get(prov.KEY_ENV)
        if not key:
            say(f"[{name}] {prov.KEY_ENV} is not set; skipping this model.")
            continue
        pid = plan_hash(cells)
        order_path = logs_dir / f"{name}.order.{pid}.json"
        if not order_path.exists():
            order_path.write_text(json.dumps({"model": name, "plan": pid, "order_seed": order_seed,
                                              "cells": [list(c.key()[1:]) for c in cells]}, indent=1),
                                  encoding="utf-8", newline="\n")
        records = read_raw(out_dir / f"{name}.jsonl")
        planned = {c.key() for c in cells}
        mine = [r for r in records if r.get("status") in DONE_STATUSES
                and (r["model"], r["claim_id"], r["condition"], r["interpreter"], r["rep"]) in planned]
        progress.init(name, len(cells), len(planned & done_keys(records)),
                      sum(r["status"] == "ok" for r in mine), sum(r["status"] == "parse_failed" for r in mine),
                      usd=sum(usage_cost(m, r.get("usage") or {})[2] for r in records))
        workers.append(Worker(name=name, cfg=cfg, ctx=ctx, claims_by_id=claims_by_id, cells=cells, plan_id=pid,
                              out_dir=out_dir, logs_dir=logs_dir, api_key=key, limit=limit,
                              progress=progress, stop=stop, provider_stop=provider_stops[m["provider"]],
                              budget=budget, run_id=run_id, commit=commit, records=records))
    if workers:
        append_jsonl(logs_dir / "runs.jsonl", {"run_id": run_id, "started_utc": utcnow().isoformat(),
                                               "git_commit": commit, "models": [w.model for w in workers],
                                               "argv": sys.argv[1:]})
        say(f"run {run_id} at {commit}: {', '.join(w.model for w in workers)}. Ctrl+C stops cleanly.")
        for w in workers:
            w.start()
    return workers


def wait_for(workers, progress, stop, progress_every, grace) -> None:
    try:
        last = time.time()
        while any(w.is_alive() for w in workers):
            next(w for w in workers if w.is_alive()).join(timeout=0.5)
            if time.time() - last >= progress_every:
                say(progress.render())
                last = time.time()
    except KeyboardInterrupt:
        say("Interrupted: finishing the calls in flight, then stopping.")
        stop.set()
        for w in workers:
            w.join(timeout=grace)
    say(progress.render())


def live(cfg, plans, ctx, claims_by_id, args) -> int:
    out_dir, logs_dir = Path(args.out_dir), Path(args.logs_dir)
    rows, spent = projection(cfg, plans, ctx, claims_by_id, out_dir, unique_dirs(out_dir, *SPEND_DIRS))
    total = print_projection(cfg, rows, spent)
    cap = cfg["budget"].get("hard_stop_usd")
    if cap is not None and total > cap:
        say(f"WARNING: the projection (${total:.2f}) is above the hard stop (${cap:.2f}); "
            "the run will stop when spend reaches it.")
    if not args.yes and not confirm(f"Start the run? Projected total spend ${total:.2f}. [y/N] "):
        say("Not started; nothing was sent.")
        return 1
    progress, stop = Progress(), threading.Event()
    workers = start_workers(cfg, plans, ctx, claims_by_id, out_dir, logs_dir, args.limit, progress, stop)
    if not workers:
        say("No model has an API key; nothing to do.")
        return 1
    wait_for(workers, progress, stop, args.progress_every, args.request_grace)
    return 0


# ---------------------------------------------------------------- pilot

PILOT_CLAIM = "real-01-t"
PILOT_CONDITIONS = ("C0", "C1", "C2", "C5")
PILOT_JUDGE_CALLS = 10
PILOT_JUDGE_PASS = 9


def pilot_cells(cfg: dict, name: str) -> list[Cell]:
    """C0, C1, C2, C5, plus C2 with the interpreter (interpreter-arm models) or C4 (the rest)."""
    extra = ("C2", True) if cfg["models"][name].get("interpreter_arm") else ("C4", False)
    return [Cell(name, PILOT_CLAIM, c, i, 0) for c, i in [(c, False) for c in PILOT_CONDITIONS] + [extra]]


def pilot_judge(cfg, names, ctx, claims_by_id, pilot_dir: Path):
    """Judge PILOT_JUDGE_CALLS pilot responses from C1-C4, round-robin over models. Each response is
    judged once; re-running reuses earlier judgements rather than asking again."""
    from src.judge import JudgeClient, JudgeStop, credential_facts, response_id
    jcfg = cfg.get("judge")
    if not jcfg:
        return [], "skipped: no judge section in models.yaml"
    queues = []
    for name in names:
        recs = [r for r in read_raw(pilot_dir / f"{name}.jsonl")
                if r.get("status") == "ok" and r["condition"] in ("C1", "C2", "C3", "C4")]
        queues.append(sorted(recs, key=lambda r: (r["condition"], r["interpreter"])))
    cands = []
    while len(cands) < PILOT_JUDGE_CALLS and any(queues):
        for q in queues:
            if q and len(cands) < PILOT_JUDGE_CALLS:
                cands.append(q.pop(0))
    jpath = pilot_dir / "judge.jsonl"
    earlier = {r["response_id"]: r for r in read_raw(jpath)}
    load_env(REPO / ".env")
    key = os.environ.get(PROVIDERS[jcfg["provider"]].KEY_ENV)
    if not key and any(response_id(r) not in earlier for r in cands):
        return [earlier[response_id(r)] for r in cands if response_id(r) in earlier], \
            f"stopped: {PROVIDERS[jcfg['provider']].KEY_ENV} not set"
    client = JudgeClient(jcfg, key or "", sleep=lambda s: SLEEP(threading.Event(), s))
    rows, status = [], "done"
    for rec in cands:
        rid = response_id(rec)
        if rid in earlier:
            rows.append(earlier[rid])
            continue
        claim = claims_by_id[rec["claim_id"]]
        try:
            j = client.judge(credential_facts(ctx, claim, rec["condition"]), claim["text"],
                             rec["parsed"]["justification"], seed=_int_seed(jcfg.get("seed", 0), rid))
        except JudgeStop as e:
            status = f"stopped: {e}"
            break
        row = {"response_id": rid, "timestamp_utc": utcnow().isoformat(), "judge_model_id": jcfg["model_id"],
               "model": rec["model"], "claim_id": rec["claim_id"], "condition": rec["condition"],
               "interpreter": rec["interpreter"], "rep": rec["rep"], **j}
        append_jsonl(jpath, row)
        rows.append(row)
    return rows, status


def pilot_report(cfg, names, ctx, claims_by_id, pilot_dir: Path, judge_rows, judge_status) -> tuple[str, dict]:
    warn_at = cfg["budget"].get("pilot_warn_usd")
    lines = ["# Pilot report", "", f"Generated {utcnow():%Y-%m-%d %H:%M} UTC. Pilot data lives in `{pilot_dir}` "
             "and is excluded from analysis.", "", "## Study calls", "",
             "| model | condition | interpreter | attempt | status | result | in tok | out tok | $ | s |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    pilot_spend = 0.0
    n_calls = 0
    for name in names:
        m = cfg["models"][name]
        for r in read_raw(pilot_dir / f"{name}.jsonl"):
            tin, tout, cost = usage_cost(m, r.get("usage") or {})
            pilot_spend += cost
            n_calls += 1
            p = r.get("parsed")
            result = f"accept={p['accept']} conf={p['confidence']}" if p else f"PARSE FAIL: {(r.get('parse_error') or '')[:40]}"
            lines.append(f"| {name} | {r['condition']} | {'yes' if r['interpreter'] else 'no'} | {r['attempt']} | "
                         f"{r['status']} | {result} | {tin} | {tout} | {cost:.5f} | {r.get('latency_s', 0):.1f} |")
    lines += ["", f"{n_calls} study responses; pilot spend ${pilot_spend:.4f}.", ""]

    valid = sum(1 for j in judge_rows if j.get("valid"))
    passed = len(judge_rows) >= PILOT_JUDGE_CALLS and valid >= PILOT_JUDGE_PASS
    lines += ["## Judge", "",
              f"{cfg.get('judge', {}).get('model_id', '-')}: {valid}/{len(judge_rows)} calls returned a valid score "
              f"(pass rule: at least {PILOT_JUDGE_PASS}/{PILOT_JUDGE_CALLS}). **{'PASS' if passed else 'FAIL'}**. "
              f"Status: {judge_status}.", ""]
    if not passed:
        lines += ["Per PREREGISTRATION.md §5, scope accuracy must then come from the author's hand-labels on 150 "
                  "stratified responses: `python src/grade.py --human-sample 150`.", ""]
    lines += ["| response | score | valid | reason or error |", "|---|---|---|---|"]
    for j in judge_rows:
        why = (j.get("reason") or j.get("parse_error") or "").replace("|", "/")[:80]
        lines.append(f"| {j['response_id']} | {j.get('score')} | {j.get('valid')} | {why} |")

    claims = list(claims_by_id.values())
    plans_full = {n: order_cells(plan_cells(cfg, n, claims), cfg["defaults"]["base_seed"], n) for n in names}
    rows, spent = projection(cfg, plans_full, ctx, claims_by_id, SPEND_DIRS[0], unique_dirs(*SPEND_DIRS, pilot_dir))
    total = sum(spent.values()) + sum(r["usd_left"] for r in rows)
    lines += ["", "## Projected full run (calibrated on the pilot's measured tokens)", "",
              "| model | calls left | input tok/call | output tok/call | projected $ |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['todo']} | {r['in_per_call']:.0f} | {r['out_per_call']:.0f} | {r['usd_left']:.3f} |")
    lines += ["", f"Projected total including spend so far: **${total:.2f}** "
              f"(hard stop ${cfg['budget'].get('hard_stop_usd', 0):.2f})."]
    over = warn_at is not None and total > warn_at
    if over:
        lines += ["", f"**WARNING: projected total ${total:.2f} is above ${warn_at:.2f}.** "
                  "Apply the CLAUDE.md cut order or reduce qwen's share before the main run."]
    summary = {"generated_utc": utcnow().isoformat(), "study_responses": n_calls, "pilot_spend_usd": round(pilot_spend, 6),
               "judge_model_id": cfg.get("judge", {}).get("model_id"), "judge_calls": len(judge_rows),
               "judge_valid": valid, "judge_passed": passed, "judge_status": judge_status,
               "projected_total_usd": round(total, 4), "projection_over_warning": over,
               "projection": [{k: r[k] for k in ("model", "todo", "in_per_call", "out_per_call", "usd_left")} for r in rows]}
    return "\n".join(lines) + "\n", summary


def run_pilot(cfg, names, ctx, claims_by_id, args) -> int:
    pilot_dir, logs_dir = Path(args.out_dir), Path(args.logs_dir)
    plans = {n: (pilot_cells(cfg, n), 0) for n in names}
    say(f"PILOT: {sum(len(c) for c, _ in plans.values())} study calls on {PILOT_CLAIM}, then up to "
        f"{PILOT_JUDGE_CALLS} judge calls. Output: {pilot_dir}")
    progress, stop = Progress(), threading.Event()
    workers = start_workers(cfg, plans, ctx, claims_by_id, pilot_dir, logs_dir, None, progress, stop)
    if workers:
        wait_for(workers, progress, stop, args.progress_every, args.request_grace)
    judge_rows, judge_status = pilot_judge(cfg, names, ctx, claims_by_id, pilot_dir)
    report, summary = pilot_report(cfg, names, ctx, claims_by_id, pilot_dir, judge_rows, judge_status)
    pilot_dir.mkdir(parents=True, exist_ok=True)
    (pilot_dir / "pilot_report.md").write_text(report, encoding="utf-8", newline="\n")
    (pilot_dir / "pilot_report.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    say("\n" + report)
    say(f"Saved {pilot_dir / 'pilot_report.md'} and pilot_report.json.")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pilot", action="store_true",
                    help="5 calls per model on real-01-t, then 10 judge calls; output to data/pilot")
    ap.add_argument("--config", type=Path, default=REPO / "models.yaml")
    ap.add_argument("--models", default="all", help="comma-separated model names from the config, or 'all'")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check-models", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip the projected-cost question before the main run")
    ap.add_argument("--claims", help="comma-separated claim or pair ids")
    ap.add_argument("--conditions", help="comma-separated conditions, e.g. C0,C1")
    ap.add_argument("--reps", type=int, help="override the number of reps")
    ap.add_argument("--limit", type=int, help="max API calls per model in this run")
    ap.add_argument("--out-dir", default=None, help="default data/raw (data/pilot with --pilot)")
    ap.add_argument("--logs-dir", default=None, help="default data/logs (data/pilot/logs with --pilot)")
    ap.add_argument("--progress-every", type=float, default=30.0, help="seconds between progress prints")
    ap.add_argument("--request-grace", type=float, default=150.0, help="seconds to wait for calls in flight on Ctrl+C")
    return ap


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.out_dir is None:
        args.out_dir = str(SPEND_DIRS[1] if args.pilot else SPEND_DIRS[0])
    if args.logs_dir is None:
        args.logs_dir = str(Path(args.out_dir) / "logs" if args.pilot else DATA / "logs")
    cfg = load_config(args.config)
    names = list(cfg["models"]) if args.models == "all" else [n.strip() for n in args.models.split(",")]
    unknown = [n for n in names if n not in cfg["models"]]
    if unknown:
        ap.error(f"unknown models: {unknown}")
    if args.check_models:
        return check_models(cfg, names)

    ctx, claims = B.load_context(), B.load_claims()
    claims_by_id = {c["id"]: c for c in claims}
    if args.pilot:
        return run_pilot(cfg, names, ctx, claims_by_id, args)
    claim_filter = set(args.claims.split(",")) if args.claims else None
    cond_filter = set(args.conditions.split(",")) if args.conditions else None
    plans = {}
    for n in names:
        cells = plan_cells(cfg, n, claims, reps=args.reps, claim_filter=claim_filter, cond_filter=cond_filter)
        plans[n] = order_cells(cells, cfg["defaults"]["base_seed"], n)
    if args.dry_run:
        return dry_run(cfg, plans, ctx, claims_by_id, args.out_dir)
    return live(cfg, plans, ctx, claims_by_id, args)


if __name__ == "__main__":
    sys.exit(main())
