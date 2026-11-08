"""Run the study: dispatch, rate limits, retries and resumption. One worker thread per model.

  python src/runner.py --dry-run            build every prompt and count calls; no API calls, no writes
  python src/runner.py                      run every configured model until done or out of quota
  python src/runner.py --models gpt-oss-120b,gemini-3.1-flash-lite
  python src/runner.py --check-models       confirm the configured model IDs exist (lists models only)

Subsets, e.g. for the pilot:
  --claims real-01-t,inv-01 (claim or pair ids)  --conditions C0,C1  --reps 1  --limit 30
  --out-dir data/pilot  (keep pilot data out of data/raw)

Data. data/raw/{model}.jsonl is append-only, one line per model response, flushed and fsynced
after each. A cell (model, claim_id, condition, interpreter, rep) is done once it has a line
with status "ok" or "parse_failed"; re-running skips done cells. Rate-limit and error events go
to data/logs/{model}.events.jsonl, the randomised cell order to data/logs/{model}.order.*.json.

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
DONE_STATUSES = ("ok", "parse_failed")
CHARS_PER_TOKEN = 3.6           # rough prompt-size estimate, used only for pacing and the dry run
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
    return cfg


def load_env(path: Path) -> None:
    """Set variables from a .env file without overriding ones already in the environment."""
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
    if not path.exists():
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


# ---------------------------------------------------------------- progress

class Progress:
    def __init__(self):
        self.lock = threading.Lock()
        self.rows: dict[str, dict] = {}

    def init(self, name, total, done, ok, failed):
        with self.lock:
            self.rows[name] = dict(total=total, done=done, ok=ok, failed=failed, this_run=0,
                                   started=time.time(), state="starting")

    def bump(self, name, status, cell_done):
        with self.lock:
            r = self.rows[name]
            r["this_run"] += 1
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
                lines.append(f"  {name:24} {r['done']:4}/{r['total']:<4} done (ok {r['ok']}, parse_failed {r['failed']}), "
                             f"{r['total'] - r['done']} left | this run {r['this_run']} calls, "
                             f"{r['this_run'] / mins:.1f}/min | {r['state']}")
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
                 limit, progress, stop, run_id, commit, records):
        super().__init__(name=f"worker-{name}", daemon=True)
        self.model, self.cfg, self.ctx = name, cfg, ctx
        self.m = cfg["models"][name]
        self.provider = PROVIDERS[self.m["provider"]]
        self.claims_by_id, self.cells, self.plan_id = claims_by_id, cells, plan_id
        self.raw_path = Path(out_dir) / f"{name}.jsonl"
        self.events_path = Path(logs_dir) / f"{name}.events.jsonl"
        self.api_key, self.limit = api_key, limit
        self.progress, self.stop, self.run_id, self.commit = progress, stop, run_id, commit
        lim = self.m.get("limits") or {}
        self.rpd, self.tpd = lim.get("rpd"), lim.get("tpd")
        self.pacer = Pacer(lim.get("rpm"), lim.get("tpm"), stop)
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
        est = estimate_tokens(messages) + self.expected_out
        for attempt in (1, 2):
            seed = call_seed(self.base_seed, cell, attempt)
            payload = self.provider.build_payload(self.m, messages, temperature=self.temperature, seed=seed,
                                                  max_output_tokens=self.max_out, schema=SCHEMA)
            started = utcnow()
            res = self.send(cell, payload, est)
            if res is None:
                return  # transient failures; the cell stays undone for the next run
            comp = self.provider.extract(res.body)
            parsed, err = parse_response(comp.text)
            status = "ok" if parsed else ("parse_retry" if attempt == 1 else "parse_failed")
            append_jsonl(self.raw_path, {
                "schema": 1, "run_id": self.run_id, "git_commit": self.commit,
                "timestamp_utc": started.isoformat(), "pacific_date": to_pacific(started).date().isoformat(),
                "model": self.model, "provider": self.provider.NAME, "model_id": self.m["model_id"],
                "claim_id": cell.claim_id, "pair_id": claim["pair_id"], "claim_type": claim["claim_type"],
                "truth_value": claim["truth_value"], "condition": cell.condition,
                "interpreter": cell.interpreter, "rep": cell.rep, "attempt": attempt,
                "plan": self.plan_id, "order_index": index, "run_date": run_date.isoformat(),
                "prompt_hash": phash, "seed": seed, "temperature": self.temperature,
                "max_output_tokens": self.max_out, "reasoning_setting": self.provider.reasoning_setting(self.m),
                "request": {"endpoint": self.provider.endpoint(self.m), "body": payload},
                "http_status": res.status, "latency_s": round(res.latency_s, 3),
                "rate_headers": {h: res.headers[h] for h in self.provider.RATE_HEADERS if h in res.headers},
                "raw_text": comp.text, "reasoning_text": comp.reasoning, "finish_reason": comp.finish_reason,
                "usage": comp.usage, "response_meta": comp.extra, "response_body": res.body,
                "parsed": parsed, "parse_error": err, "status": status,
            })
            cell_done = status in DONE_STATUSES
            self.progress.bump(self.model, status, cell_done)
            if cell_done:
                self.done.add(cell.key())
                return

    def send(self, cell, payload, est):
        transient = unclassified = 0
        while True:
            if self.stop.is_set():
                raise Stop("interrupted")
            today = to_pacific(utcnow()).date()
            if today != self.day:
                self.day, self.calls_today, self.tokens_today = today, 0, 0
            if self.rpd and self.calls_today >= self.rpd:
                self.stop_for_day(f"{self.calls_today} calls today reaches the configured RPD {self.rpd}", cell)
            if self.tpd and self.tokens_today + est > self.tpd:
                self.stop_for_day(f"~{self.tokens_today} tokens today; the next call would pass the configured TPD {self.tpd}", cell)
            self.pacer.wait(est)
            res = self.provider.send(self.m, payload, self.api_key, self.timeout)
            self.calls_this_run += 1
            if res.status == 200 and isinstance(res.body, dict):
                used = self.provider.total_tokens(self.provider.extract(res.body).usage) or est
                self.pacer.record(used)
                self.calls_today += 1
                self.tokens_today += used
                return res
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
            if res.status is None or res.status in (408, 409) or res.status >= 500 or res.status == 200:
                transient += 1
                self.event("transient_error", cell, status=res.status, error=res.error, body=res.text[:500],
                           attempt=transient)
                if transient > MAX_TRANSIENT_RETRIES:
                    self.progress.state(self.model, "skipping a cell after repeated transient errors")
                    return None
                SLEEP(self.stop, min(120.0, 5.0 * 2 ** transient) + random.uniform(0, 2))
                continue
            # any other 4xx is a request or configuration problem: stop this model, keep the evidence
            self.event("fatal_http_error", cell, status=res.status, body=res.text[:2000])
            self.progress.state(self.model, f"STOPPED: HTTP {res.status} (see events log): {res.text[:160]}")
            say(f"[{self.model}] HTTP {res.status}; stopping this model. {res.text[:300]}")
            raise Stop(f"http {res.status}")


# ---------------------------------------------------------------- commands

def dry_run(cfg, plans, ctx, claims_by_id, out_dir) -> int:
    say("DRY RUN: builds every prompt; makes no API calls and writes nothing.\n")
    today = dt.date.today()
    header = (f"{'model':24} {'planned':>7} {'on disk':>7} {'to run':>6} {'~tok/call':>9} "
              f"{'~tokens left':>12} {'limits (rpm/rpd/tpm/tpd)':>26} {'~days':>6}")
    say(header)
    say("-" * len(header))
    totals = [0, 0, 0]
    for name, (cells, _seed) in plans.items():
        m = cfg["models"][name]
        done = done_keys(read_raw(Path(out_dir) / f"{name}.jsonl"))
        todo = [c for c in cells if c.key() not in done]
        expected_out = setting(cfg, name, "expected_output_tokens")
        hashes = set()
        est = []
        for c in cells:  # build every prompt, not only the remaining ones
            msgs = B.build_messages(ctx, claims_by_id[c.claim_id], c.condition, c.interpreter, today)
            hashes.add(B.prompt_hash(msgs))
            if c.key() not in done:
                est.append(estimate_tokens(msgs) + expected_out)
        per_call = sum(est) / len(est) if est else 0
        lim = m.get("limits") or {}
        caps = [lim[k] for k in ("rpd",) if lim.get(k)]
        if lim.get("tpd") and per_call:
            caps.append(lim["tpd"] / per_call)
        if lim.get("rpm"):
            caps.append(lim["rpm"] * 60 * 24)
        if lim.get("tpm") and per_call:
            caps.append(lim["tpm"] * 60 * 24 / per_call)
        per_day = min(caps) if caps else float("inf")
        days = len(todo) / per_day if per_day else float("inf")
        limits = "/".join(str(lim.get(k, "-")) for k in ("rpm", "rpd", "tpm", "tpd"))
        say(f"{name:24} {len(cells):7} {len(cells) - len(todo):7} {len(todo):6} {per_call:9.0f} "
            f"{sum(est):12.0f} {limits:>26} {days:6.1f}")
        say(f"{'':24} {len(hashes)} distinct prompts (reps share a prompt)")
        totals[0] += len(cells)
        totals[1] += len(cells) - len(todo)
        totals[2] += len(todo)
    say("-" * len(header))
    say(f"{'TOTAL':24} {totals[0]:7} {totals[1]:7} {totals[2]:6}")
    say("\n~days = calls left / the tightest daily cap implied by the configured limits, at the estimated "
        f"tokens per call (prompt chars / {CHARS_PER_TOKEN} + expected output). Parse retries add calls.")
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


def live(cfg, plans, ctx, claims_by_id, args) -> int:
    load_env(REPO / ".env")
    out_dir, logs_dir = Path(args.out_dir), Path(args.logs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_id, commit = uuid.uuid4().hex[:12], git_commit()
    progress, stop = Progress(), threading.Event()
    workers = []
    for name, (cells, order_seed) in plans.items():
        prov = PROVIDERS[cfg["models"][name]["provider"]]
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
                      sum(r["status"] == "ok" for r in mine), sum(r["status"] == "parse_failed" for r in mine))
        workers.append(Worker(name=name, cfg=cfg, ctx=ctx, claims_by_id=claims_by_id, cells=cells, plan_id=pid,
                              out_dir=out_dir, logs_dir=logs_dir, api_key=key, limit=args.limit,
                              progress=progress, stop=stop, run_id=run_id, commit=commit, records=records))
    if not workers:
        say("No model has an API key; nothing to do.")
        return 1
    append_jsonl(logs_dir / "runs.jsonl", {"run_id": run_id, "started_utc": utcnow().isoformat(), "git_commit": commit,
                                           "models": [w.model for w in workers], "argv": sys.argv[1:]})
    say(f"run {run_id} at {commit}: {', '.join(w.model for w in workers)}. Ctrl+C stops cleanly.")
    for w in workers:
        w.start()
    try:
        last = time.time()
        while any(w.is_alive() for w in workers):
            next(w for w in workers if w.is_alive()).join(timeout=0.5)
            if time.time() - last >= args.progress_every:
                say(progress.render())
                last = time.time()
    except KeyboardInterrupt:
        say("Interrupted: finishing the calls in flight, then stopping.")
        stop.set()
        for w in workers:
            w.join(timeout=args.request_grace)
    say(progress.render())
    return 0


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=REPO / "models.yaml")
    ap.add_argument("--models", default="all", help="comma-separated model names from the config, or 'all'")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check-models", action="store_true")
    ap.add_argument("--claims", help="comma-separated claim or pair ids")
    ap.add_argument("--conditions", help="comma-separated conditions, e.g. C0,C1")
    ap.add_argument("--reps", type=int, help="override the number of reps")
    ap.add_argument("--limit", type=int, help="max API calls per model in this run")
    ap.add_argument("--out-dir", default=str(REPO / "data" / "raw"))
    ap.add_argument("--logs-dir", default=str(REPO / "data" / "logs"))
    ap.add_argument("--progress-every", type=float, default=30.0, help="seconds between progress prints")
    ap.add_argument("--request-grace", type=float, default=150.0, help="seconds to wait for calls in flight on Ctrl+C")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    names = list(cfg["models"]) if args.models == "all" else [n.strip() for n in args.models.split(",")]
    unknown = [n for n in names if n not in cfg["models"]]
    if unknown:
        ap.error(f"unknown models: {unknown}")
    if args.check_models:
        return check_models(cfg, names)

    ctx, claims = B.load_context(), B.load_claims()
    claims_by_id = {c["id"]: c for c in claims}
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
