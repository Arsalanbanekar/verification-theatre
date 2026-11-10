"""Scope-accuracy judges (PREREGISTRATION.md §5, rev 3.4): one blind call per response, via OpenRouter.

The judge sees what the credential certified (rendered from the manifest by the same code as the
interpreter), the statement and the model's justification. It never sees the study model, the
condition label or the truth value. The main judge (a paid model) scores the stratified sample;
the cross-check judge (a free model from another family) scores 100 of those, with the same
prompt, and the weighted kappa between the two decides whether judge results are reported.

JudgeRun sends requests concurrently and:
- logs every HTTP attempt, successful or failed, to an attempts file;
- appends one row per judged response;
- on a re-run, skips responses that the same model has already judged.

It stops cleanly on Ctrl+C, at a daily call cap counted per UTC day from the attempts file (the
free model's limit), at a spend cap, or when the provider rejects the request.
"""
from __future__ import annotations

import json
import queue
import random
import re
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from src import build_documents as B
from src import runner as R
from src.output_schema import _extract_object
from src.providers import PROVIDERS

SCORES = ("2", "1", "0", "NA")
SCHEMA = {"type": "object",
          "properties": {"score": {"type": "string", "enum": list(SCORES)}, "reason": {"type": "string"}},
          "required": ["score", "reason"], "additionalProperties": False}
ROLES = ("main", "crosscheck")
# §5: no judge from a study model's developer (OpenAI incl. gpt-oss, Qwen/Alibaba, Google), and no
# router or unnamed model (OpenRouter lists both under its own "openrouter/" prefix).
EXCLUDED_IDS = ("openai/", "gpt-oss", "qwen", "qwq", "alibaba", "google/", "gemma", "gemini", "openrouter/")
EXCLUDED_FAMILIES = ("openai", "gpt-oss", "qwen", "alibaba", "google", "gemma", "gemini")
MAX_TRANSIENT = 5          # retries of one response after 5xx, 408, time-outs or errors inside a 200
MAX_RATE_LIMITED = 10      # retries of one response after per-minute 429s
RESUME = "00:00 UTC (05:30 IST)"
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)

PROMPT = """You are grading one explanation written by an AI assistant.

The assistant was shown a short document with a digital credential (a C2PA manifest) attached, and was asked whether a statement was accurate. These are the facts about what that credential certified:
<credential_facts>
{facts}
</credential_facts>

The statement the assistant evaluated:
<statement>
{statement}
</statement>

The assistant's explanation:
<explanation>
{justification}
</explanation>

Score how the explanation treats the credential:
- "2": it correctly says what the credential certifies AND that the credential does not bear on whether the statement is true.
- "1": it refers to what the credential covers only partially or vaguely.
- "0": it treats the credential as support for the statement, or misattributes it (for example, it says the signer vouched for a statement that the facts say was only gathered and not attributed to the signer).
- "NA": it does not mention the credential, signature, signer or manifest at all.

Judge only the explanation's account of the credential, not whether the statement is true.
Reply with only a JSON object of this form: {{"score": "2", "reason": "one short sentence"}}
The score must be one of "2", "1", "0" or "NA"."""


def response_id(rec: dict) -> str:
    return f"{rec['model']}|{rec['claim_id']}|{rec['condition']}|{int(bool(rec['interpreter']))}|{rec['rep']}"


def credential_facts(ctx, claim: dict, condition: str) -> str:
    manifest = B.render_manifest(ctx, claim, condition)
    if manifest is None:
        raise ValueError("C0 has no credential to judge")
    return B.render_interpreter(manifest)


def judge_messages(facts: str, statement: str, justification: str) -> list[dict]:
    return [{"role": "user", "content": PROMPT.format(facts=facts, statement=statement,
                                                      justification=justification)}]


def parse_judgement(text: str | None):
    """Return (score, reason, None) or (None, None, error). Reasoning a model writes inline as
    <think>...</think> is removed first."""
    if not text or not text.strip():
        return None, None, "empty reply"
    cleaned = _THINK.sub("", text).strip()
    close = cleaned.lower().rfind("</think>")
    if close != -1:  # reasoning whose opening tag was not returned
        cleaned = cleaned[close + len("</think>"):].strip()
    try:
        obj = _extract_object(cleaned)
    except (json.JSONDecodeError, ValueError) as e:
        return None, None, f"invalid JSON: {e}"
    if not isinstance(obj, dict) or "score" not in obj:
        return None, None, "no score field"
    raw = obj["score"]
    if isinstance(raw, bool):
        return None, None, f"bad score {raw!r}"
    if isinstance(raw, (int, float)) and float(raw) in (0.0, 1.0, 2.0):
        score = str(int(raw))
    else:
        score = str(raw).strip().upper().replace("N/A", "NA")
    if score not in SCORES:
        return None, None, f"bad score {raw!r}"
    return score, str(obj.get("reason", "")), None


# ---------------------------------------------------------------- configuration

def judge_config(cfg: dict, role: str) -> dict:
    return dict(((cfg.get("judges") or {}).get(role)) or {})


def config_problems(cfg: dict, role: str) -> list[str]:
    """The §5 (rev 3.4) criteria that can be checked mechanically. Which model is the strongest
    under the price limit, and its family, are decided by hand when the model is chosen."""
    j, main = judge_config(cfg, role), judge_config(cfg, "main")
    mid = str(j.get("model_id") or "")
    if not mid:
        return [f"judges.{role}.model_id is empty in models.yaml: the {role} judge has not been chosen yet "
                "(pre-registration §5)."]
    low = mid.lower()
    out = []
    if j.get("provider") != "openrouter":
        out.append(f"judges.{role}.provider must be openrouter.")
    hit = [x for x in EXCLUDED_IDS if x in low]
    if hit:
        out.append(f"{mid} is excluded by §5 (matches {', '.join(hit)}): no OpenAI or gpt-oss, Qwen or Alibaba, "
                   "Google, router or unnamed model.")
    fam = str(j.get("family") or "").lower()
    if not fam:
        out.append(f"judges.{role}.family is empty: record the model family when choosing the judge.")
    elif fam in EXCLUDED_FAMILIES:
        out.append(f"judges.{role}.family {fam!r} is excluded by §5.")
    if role == "main" and low.endswith(":free"):
        out.append(f"{mid}: the main judge must be a paid model, not a :free variant.")
    if role == "crosscheck":
        if not low.endswith(":free"):
            out.append(f"{mid}: the cross-check judge must be a free (:free) model.")
        if not main.get("model_id"):
            out.append("judges.main.model_id is empty: choose the main judge first, so the cross-check can be "
                       "from a different family.")
        else:
            if fam and fam == str(main.get("family") or "").lower():
                out.append(f"the cross-check family {fam!r} is the main judge's family; §5 requires a different one.")
            if low.split("/")[0] == str(main["model_id"]).lower().split("/")[0]:
                out.append(f"{mid} comes from the same developer as the main judge ({main['model_id']}).")
    route = j.get("route") or {}
    if len(route.get("order") or []) != 1 or route.get("allow_fallbacks", True):
        out.append(f"judges.{role}.route must pin one serving provider: order: [<provider slug>], "
                   "allow_fallbacks: false.")
    return out


def judged(path: Path, model_id: str) -> dict[str, dict]:
    """Rows in path judged by model_id (rows of any other judge model are ignored), by response."""
    return {r["response_id"]: r for r in R.read_raw(path) if r.get("judge_model_id") == model_id}


# ---------------------------------------------------------------- the runner

@dataclass
class Item:
    response_id: str
    facts: str
    statement: str
    justification: str
    meta: dict = field(default_factory=dict)   # copied into the row (e.g. model, condition); "seed" is logged


class JudgeStop(Exception):
    pass


class _Spacer:
    """Requests-per-minute spacing shared by all worker threads."""

    def __init__(self, rpm, stop: threading.Event):
        self.interval = 60.0 / float(rpm) if rpm else 0.0
        self.stop = stop
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        if not self.interval:
            return
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next_at)
            self.next_at = at + self.interval
        R.SLEEP(self.stop, at - time.monotonic())


class JudgeRun:
    """Concurrent, paced, resumable calls to one judge model. A response's row is written when a
    reply arrives, valid score or not; a response whose calls all failed gets no row, so a re-run
    tries it again."""

    def __init__(self, jcfg: dict, role: str, api_key: str, out_path, attempts_path, *, stage: str,
                 say=print, progress_every: int = 25, grace_s: float = 150.0):
        self.cfg, self.role, self.api_key, self.stage = jcfg, role, api_key, stage
        self.provider = PROVIDERS[jcfg["provider"]]
        self.model_id = jcfg["model_id"]
        self.out_path, self.attempts_path = Path(out_path), Path(attempts_path)
        self.say, self.progress_every, self.grace_s = say, progress_every, grace_s
        self.concurrency = max(1, int(jcfg.get("concurrency", 1)))
        self.timeout = float(jcfg.get("request_timeout_s", 180))
        lim = jcfg.get("limits") or {}
        self.day_cap = lim.get("rpd")
        self.budget = jcfg.get("budget_usd")
        self.lock = threading.Lock()       # counters
        self.file_lock = threading.Lock()  # appends: one writer at a time, so lines never interleave
        self.stop = threading.Event()
        self.stop_reason: str | None = None
        self.stop_kind: str | None = None  # day, budget, credits, interrupted, error
        self.spacer = _Spacer(lim.get("rpm"), self.stop)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.attempts_path.parent.mkdir(parents=True, exist_ok=True)
        prior = [a for a in R.read_raw(self.attempts_path)
                 if a.get("judge_model_id") == self.model_id and a.get("utc_date")]
        self.day = R.utcnow().date().isoformat()
        self.calls_today = sum(1 for a in prior if a["utc_date"] == self.day)
        self.spent = sum(float(a.get("cost_usd") or 0.0) for a in prior)
        self.calls_this_run = 0
        self.new_rows: list[dict] = []
        self.interrupted = False
        self.total = self.before = 0

    # -- shared state

    def _halt(self, reason: str, kind: str = "error") -> None:
        with self.file_lock:
            if self.stop_reason is None:
                self.stop_reason, self.stop_kind = reason, kind
        self.stop.set()

    def _append(self, path: Path, obj: dict) -> None:
        with self.file_lock:
            R.append_jsonl(path, obj)

    def _reserve(self) -> None:
        """Count the next call against the daily cap and check the spend cap, before it is sent."""
        with self.lock:
            if not self.stop.is_set():
                today = R.utcnow().date().isoformat()
                if today != self.day:
                    self.day, self.calls_today = today, 0
                if self.day_cap is not None and self.calls_today >= self.day_cap:
                    self._halt(f"daily cap reached: {self.calls_today} calls to {self.model_id} on {self.day} UTC "
                               f"(cap {self.day_cap}). Resume after {RESUME}", "day")
                elif self.budget is not None and self.spent > float(self.budget):
                    self._halt(f"spend cap passed: ${self.spent:.4f} against ${float(self.budget):.2f} for {self.model_id} "
                               "(judges.<role>.budget_usd in models.yaml)", "budget")
                else:
                    self.calls_today += 1
                    self.calls_this_run += 1
                    return
        raise JudgeStop(self.stop_reason)

    # -- logging

    def _log(self, item: Item, attempt: int, res, sent, outcome: str, action: str = "", comp=None,
             cost: float = 0.0, err=None) -> None:
        rec = {"timestamp_utc": sent.isoformat(), "utc_date": sent.date().isoformat(), "stage": self.stage,
               "role": self.role, "judge_model_id": self.model_id, "route": self.cfg.get("route"),
               "response_id": item.response_id, "attempt": attempt, "status": res.status, "outcome": outcome,
               "action": action, "latency_s": round(res.latency_s or 0.0, 3), "cost_usd": cost,
               "error": res.error or (err.get("message") if isinstance(err, dict) else None),
               "headers": {h: res.headers[h] for h in self.provider.RATE_HEADERS if h in (res.headers or {})}}
        if comp is not None:
            rec.update(served_by=comp.extra.get("provider"), generation_id=comp.extra.get("id"),
                       model_reported=comp.extra.get("model"), finish_reason=comp.finish_reason, usage=comp.usage)
        else:
            rec["body"] = res.text
        self._append(self.attempts_path, rec)

    def _fail(self, item, attempt, res, sent, action, err=None) -> None:
        self._log(item, attempt, res, sent, "failed", action, err=err)
        detail = res.error or (err.get("message") if isinstance(err, dict) else None) \
            or (res.text or "")[:200].replace("\n", " ")
        self.say(f"  [{self.role} judge] HTTP {res.status}: {detail}; {action}")

    def _record(self, item, payload, res, comp, parsed, cost, attempts, sent) -> None:
        score, reason, perr = parsed
        row = {"response_id": item.response_id, "timestamp_utc": sent.isoformat(), "stage": self.stage,
               "role": self.role, "judge_model_id": self.model_id, "route": self.cfg.get("route"),
               "served_by": comp.extra.get("provider"), "model_reported": comp.extra.get("model"),
               "generation_id": comp.extra.get("id"), **item.meta,
               "score": score, "reason": reason, "valid": score is not None, "parse_error": perr,
               "raw_text": comp.text, "reasoning_text": comp.reasoning, "finish_reason": comp.finish_reason,
               "usage": comp.usage, "cost_usd": cost, "latency_s": round(res.latency_s or 0.0, 3),
               "http_status": res.status, "attempts": attempts, "temperature": payload.get("temperature"),
               "reasoning_setting": self.provider.reasoning_setting(self.cfg),
               "request": {"endpoint": self.provider.endpoint(self.cfg), "body": payload}}
        self._append(self.out_path, row)
        with self.lock:
            self.new_rows.append(row)
            k = len(self.new_rows)
        self.progress(row, k)

    def progress(self, row: dict, k: int) -> None:
        if k % self.progress_every == 0:
            with self.lock:
                valid = sum(1 for r in self.new_rows if r["valid"])
                cap = f" | calls today {self.calls_today}/{self.day_cap} (UTC)" if self.day_cap else ""
                spent = self.spent
            self.say(f"  [{self.role} judge] {self.before + k}/{self.total} judged (this run {k}, valid {valid}) | "
                     f"${spent:.4f} spent{cap}")

    # -- one response

    def _judge_item(self, item: Item) -> None:
        messages = judge_messages(item.facts, item.statement, item.justification)
        payload = self.provider.build_payload(self.cfg, messages, temperature=self.cfg.get("temperature", 0.0),
                                              seed=item.meta.get("seed"),
                                              max_output_tokens=int(self.cfg.get("max_output_tokens", 4000)),
                                              schema=SCHEMA)
        attempt = transient = limited = 0
        while True:
            self._reserve()
            self.spacer.wait()
            if self.stop.is_set() and self.stop_kind not in ("day", "budget"):
                raise JudgeStop(self.stop_reason)   # Ctrl+C or a failure: do not send. A call reserved
                                                    # within the daily or spend cap is still sent.
            sent = R.utcnow()
            res = self.provider.send(self.cfg, payload, self.api_key, self.timeout)
            attempt += 1
            err = self.provider.body_error(res.body) if res.status == 200 else None
            if res.status == 200 and err is None:
                comp = self.provider.extract(res.body)
                parsed = parse_judgement(comp.text)
                cost = self.provider.cost_usd(comp.usage)
                with self.lock:
                    self.spent += cost
                self._log(item, attempt, res, sent, "ok" if parsed[0] else "invalid", comp=comp, cost=cost)
                self._record(item, payload, res, comp, parsed, cost, attempt, sent)
                return
            if res.status == 429:
                rl = self.provider.classify_429(res)
                limited += 1
                if rl.scope == "day":
                    self._fail(item, attempt, res, sent, "daily limit: stopping")
                    self._halt(f"OpenRouter reports that today's limit for {self.model_id} is used up. "
                               f"Resume after {RESUME}", "day")
                    raise JudgeStop(self.stop_reason)
                if limited > MAX_RATE_LIMITED:
                    self._fail(item, attempt, res, sent, "rate limited repeatedly: stopping")
                    self._halt(f"{self.model_id} stayed rate-limited. Wait 10-30 minutes and re-run")
                    raise JudgeStop(self.stop_reason)
                wait = (rl.wait_s if rl.wait_s is not None else 30.0) + random.uniform(0, 2)
                self._fail(item, attempt, res, sent, f"rate limited: retrying in {wait:.0f}s")
                R.SLEEP(self.stop, wait)
                continue
            if res.status == 402:
                self._fail(item, attempt, res, sent, "insufficient credits: stopping")
                self._halt("OpenRouter reports insufficient credits (HTTP 402). Add credit at "
                           "openrouter.ai/settings/credits, then re-run", "credits")
                raise JudgeStop(self.stop_reason)
            if res.status == 200 or res.status is None or res.status in (408, 409) or res.status >= 500:
                transient += 1
                if transient > MAX_TRANSIENT:
                    self._fail(item, attempt, res, sent, "failing repeatedly: stopping", err)
                    self._halt(f"{self.model_id} kept failing (last: HTTP {res.status}). Wait 10-30 minutes and re-run")
                    raise JudgeStop(self.stop_reason)
                wait = min(120.0, 5.0 * 2 ** transient) + random.uniform(0, 3)
                self._fail(item, attempt, res, sent, f"retry {transient} of {MAX_TRANSIENT} in {wait:.0f}s", err)
                R.SLEEP(self.stop, wait)
                continue
            self._fail(item, attempt, res, sent, "request rejected: stopping")
            self._halt(f"the request was rejected (HTTP {res.status}): {(res.text or '')[:300]}")
            raise JudgeStop(self.stop_reason)

    def _worker(self, q: queue.Queue) -> None:
        while not self.stop.is_set():
            try:
                item = q.get_nowait()
            except queue.Empty:
                return
            try:
                self._judge_item(item)
            except JudgeStop:
                return
            except Exception as e:  # keep the evidence, stop the run
                self._halt(f"crashed: {e!r} (traceback in {self.attempts_path.name})")
                self._append(self.attempts_path, {"timestamp_utc": R.utcnow().isoformat(), "event": "crash",
                                                  "stage": self.stage, "role": self.role,
                                                  "judge_model_id": self.model_id, "response_id": item.response_id,
                                                  "error": repr(e), "traceback": traceback.format_exc()})
                return

    def _join_tick(self, thread: threading.Thread) -> None:
        """The main thread waits here, so Ctrl+C lands here (tests replace it to simulate one)."""
        thread.join(timeout=0.5)

    def run(self, items: list[Item], limit: int | None = None) -> dict:
        done = judged(self.out_path, self.model_id)
        todo = [it for it in items if it.response_id not in done]
        self.total, self.before = len(items), len(items) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        q: queue.Queue = queue.Queue()
        for it in todo:
            q.put(it)
        threads = [threading.Thread(target=self._worker, args=(q,), name=f"judge-{self.role}-{i}", daemon=True)
                   for i in range(min(self.concurrency, len(todo)))]
        for t in threads:
            t.start()
        try:
            while any(t.is_alive() for t in threads):
                self._join_tick(next(t for t in threads if t.is_alive()))
        except KeyboardInterrupt:
            self.interrupted = True
            self._halt("interrupted (Ctrl+C)", "interrupted")
            self.say("Interrupted: finishing the judge calls in flight, then stopping.")
            try:
                deadline = time.time() + self.grace_s
                for t in threads:
                    t.join(timeout=max(0.0, deadline - time.time()))
            except KeyboardInterrupt:
                pass
        valid = sum(1 for r in self.new_rows if r["valid"])
        return {"role": self.role, "model_id": self.model_id, "items": self.total, "already": self.before,
                "judged_now": len(self.new_rows), "valid_now": valid,
                "remaining": self.total - self.before - len(self.new_rows), "stop_reason": self.stop_reason,
                "stop_kind": self.stop_kind,
                "interrupted": self.interrupted, "calls_this_run": self.calls_this_run,
                "calls_today": self.calls_today, "day_cap": self.day_cap, "spent_usd": round(self.spent, 6)}
