"""Scope-accuracy judge (PREREGISTRATION.md §5): one blind call per response.

The judge sees what the credential certified (rendered from the manifest by the same code as
the interpreter), the statement and the model's justification. It never sees the study model,
the condition label or the truth value. JSON mode is undocumented for Gemma on the Gemini API,
so the reply is parsed from plain text; Gemma 4 can emit a thought-channel block even with
thinking off, and that block is stripped first.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time

from src import build_documents as B
from src.output_schema import _extract_object
from src.providers import PROVIDERS

SCORES = ("2", "1", "0", "NA")
_THOUGHT = re.compile(r"<\|channel>.*?<channel\|>", re.S)

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
    """Return (score, reason, None) or (None, None, error)."""
    if not text or not text.strip():
        return None, None, "empty reply"
    cleaned = _THOUGHT.sub("", text).replace("<|channel>", "").replace("<channel|>", "").strip()
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


class JudgeStop(Exception):
    pass


class JudgeClient:
    """Paced, retrying calls to the judge model. Every attempt that does not return HTTP 200 is
    appended in full (status, transport error, body) to events_path, if given, and announced."""

    def __init__(self, judge_cfg: dict, api_key: str, sleep=None, clock=time.monotonic,
                 events_path=None, say=None):
        from src.runner import Pacer  # shared pacing logic
        self.cfg = judge_cfg
        self.provider = PROVIDERS[judge_cfg["provider"]]
        self.api_key = api_key
        lim = judge_cfg.get("limits") or {}
        self.stop = threading.Event()
        self.pacer = Pacer(lim.get("rpm"), lim.get("tpm"), self.stop, clock=clock)
        self.sleep = sleep or (lambda s: time.sleep(s))
        self.events_path = events_path
        self.say = say or (lambda msg: None)

    def _log_failure(self, res, attempt: int, context: dict | None, action: str) -> None:
        detail = res.error or (res.text or "")[:200].replace("\n", " ")
        self.say(f"  [judge] HTTP {res.status}: {detail}; {action}")
        if self.events_path is not None:
            from src.runner import append_jsonl, utcnow
            append_jsonl(self.events_path, {
                "timestamp_utc": utcnow().isoformat(), "event": "judge_http_error", "model_id": self.cfg["model_id"],
                **(context or {}), "attempt": attempt, "status": res.status, "error": res.error,
                "body": res.text, "headers": dict(res.headers or {}), "latency_s": round(res.latency_s or 0.0, 3),
                "action": action})

    def judge(self, facts: str, statement: str, justification: str, seed: int, context: dict | None = None) -> dict:
        messages = judge_messages(facts, statement, justification)
        payload = self.provider.build_payload(self.cfg, messages, temperature=self.cfg.get("temperature", 0.0),
                                              seed=seed, max_output_tokens=self.cfg.get("max_output_tokens", 400),
                                              schema=None)
        est = int(len(messages[0]["content"]) / 3.6) + 150
        transient = attempt = 0
        while True:
            self.pacer.wait(est)
            res = self.provider.send(self.cfg, payload, self.api_key, 120)
            attempt += 1
            if res.status == 200 and isinstance(res.body, dict):
                comp = self.provider.extract(res.body)
                self.pacer.record(self.provider.total_tokens(comp.usage) or est)
                score, reason, err = parse_judgement(comp.text)
                return {"messages": messages, "request": {"endpoint": self.provider.endpoint(self.cfg), "body": payload},
                        "raw_text": comp.text, "score": score, "reason": reason, "valid": score is not None,
                        "parse_error": err, "usage": comp.usage, "finish_reason": comp.finish_reason,
                        "latency_s": round(res.latency_s, 3), "http_status": res.status}
            if res.status == 429:
                rl = self.provider.classify_429(res)
                if rl.scope == "day":
                    self._log_failure(res, attempt, context, "daily quota: stopping")
                    raise JudgeStop("judge daily quota exhausted: " + rl.detail[:200])
                wait = (rl.wait_s or 30.0) + random.uniform(0, 2)
                self._log_failure(res, attempt, context, f"per-minute limit: retrying in {wait:.0f}s")
                self.sleep(wait)
                continue
            if res.status is None or res.status >= 500 or res.status in (408, 409, 498):
                transient += 1
                if transient > 5:
                    self._log_failure(res, attempt, context, "failing repeatedly: stopping")
                    raise JudgeStop(f"judge failing repeatedly: HTTP {res.status} {res.error or res.text[:200]}")
                wait = min(120.0, 5.0 * 2 ** transient) + random.uniform(0, 3)
                self._log_failure(res, attempt, context, f"retry {transient} of 5 in {wait:.0f}s")
                self.sleep(wait)
                continue
            self._log_failure(res, attempt, context, "request rejected: stopping")
            raise JudgeStop(f"judge request rejected: HTTP {res.status} {res.text[:300]}")
