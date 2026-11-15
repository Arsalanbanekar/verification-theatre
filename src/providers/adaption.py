"""Adaption Responses API, through the `adaption` SDK: the scope-accuracy judge from 15 Nov 2026
(DEVIATIONS.md), glm-5.2 on sponsor credits.

Docs read 2026-11-15 (docs.adaptionlabs.ai: getting started, inference quickstart, models, generate a
model response, the Python SDK reference for responses.create and models.list) and the SDK itself
(adaption 0.19.0):
- `client.responses.create(model=, input=, instructions=, temperature=, max_output_tokens=, store=)`
  answers with `output_text` (reasoning excluded), `status`, `model` (the public name of the model
  that generated the response), `incomplete_details` and `usage` (input, output and total tokens;
  reasoning tokens inside `output_tokens_details`);
- it has no JSON mode, no seed and no reasoning parameter. The judge prompt asks for JSON and
  src/judge.py's parser validates every reply; the model's own reasoning default applies and is
  logged as "provider default";
- a response is stored only if `store` is true; this module always sends false;
- prices are in credits per million tokens (models page), so the cost computed here is in credits;
- rate limits are not documented: a 429 is retried after the server's Retry-After, if it sends one.

The SDK's own retries are switched off (max_retries=0), so every HTTP attempt is one the judge
makes and logs.
"""
from __future__ import annotations

import json
import os
import threading
import time

from .common import Completion, HttpResult, RateLimit, parse_seconds

NAME = "adaption"
LABEL = "Adaption"
KEY_ENV = "ADAPTION_API_KEY"
COST_UNIT = "credits"
CREDITS_HINT = "Check the organisation's credit balance with Adaption, then re-run"
DEFAULT_BASE_URL = "https://api.prod.adaptionlabs.ai"    # the SDK's default; ADAPTION_BASE_URL overrides it
PATH = "/api/v1/responses"
RATE_HEADERS = ("retry-after", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
                "x-ratelimit-reset-requests", "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens",
                "x-ratelimit-reset-tokens", "x-request-id")
REASONING = "provider default"   # Adaption has no reasoning parameter

_clients: dict = {}
_lock = threading.Lock()


def _make_client(api_key: str, timeout: float):
    import adaption   # imported here: the study code never needs the SDK
    return adaption.Adaption(api_key=api_key, max_retries=0, timeout=timeout)


def _client(api_key: str, timeout: float):
    """One SDK client per key and time-out, shared by the judge's worker threads."""
    with _lock:
        c = _clients.get((api_key, timeout))
        if c is None:
            c = _clients[(api_key, timeout)] = _make_client(api_key, timeout)
        return c


def build_payload(cfg: dict, messages: list[dict], *, temperature, seed, max_output_tokens, schema) -> dict:
    """Keyword arguments for responses.create. The seed and the schema are not sent: the API takes
    neither, so the prompt's JSON instruction and the parser stand in for a JSON mode."""
    system = [m["content"] for m in messages if m["role"] == "system"]
    rest = [m for m in messages if m["role"] != "system"]
    single = len(rest) == 1 and rest[0]["role"] == "user"
    p = {"model": cfg["model_id"],
         "input": rest[0]["content"] if single else [{"role": m["role"], "content": m["content"]} for m in rest],
         "max_output_tokens": max_output_tokens, "store": False}
    if system:
        p["instructions"] = "\n\n".join(system)
    if temperature is not None:
        p["temperature"] = temperature
    return p


def reasoning_setting(cfg: dict) -> dict:
    return {"reasoning": REASONING}


def endpoint(cfg: dict) -> str:
    return (os.environ.get("ADAPTION_BASE_URL") or DEFAULT_BASE_URL).rstrip("/") + PATH


def _headers(h) -> dict:
    return {k.lower(): v for k, v in (h or {}).items()}


def send(cfg: dict, payload: dict, api_key: str, timeout: float) -> HttpResult:
    import adaption
    t0 = time.perf_counter()
    try:
        raw = _client(api_key, timeout).responses.with_raw_response.create(**payload)
    except adaption.APIStatusError as e:
        r = e.response
        try:
            body = r.json()
        except ValueError:
            body = None
        return HttpResult(r.status_code, _headers(r.headers), body, r.text, time.perf_counter() - t0)
    except adaption.APIConnectionError as e:     # includes APITimeoutError
        return HttpResult(None, {}, None, "", time.perf_counter() - t0, f"{type(e).__name__}: {e}")
    latency = time.perf_counter() - t0
    text = raw.http_response.text
    try:
        body = json.loads(text)
    except ValueError:
        body = None
    return HttpResult(raw.status_code, _headers(raw.headers), body, text, latency)


def failed_generation(res: HttpResult) -> str | None:
    return None


def body_error(body) -> dict | None:
    """The error carried by an HTTP 200 body, or None if the body is a reply. A response that stopped
    at max_output_tokens ("incomplete") is a reply: the parser decides whether it holds a score."""
    if not isinstance(body, dict):
        return {"message": "the response body is not JSON"}
    if body.get("error"):
        err = body["error"]
        return err if isinstance(err, dict) else {"message": str(err)}
    if body.get("status") in ("completed", "incomplete"):
        return None
    return {"message": f"response status {body.get('status')!r}"}


def extract(body: dict) -> Completion:
    items = [i for i in (body.get("output") or []) if isinstance(i, dict)]
    text = body.get("output_text")
    if text is None:
        text = "".join(c.get("text") or "" for i in items if i.get("type") == "message"
                       for c in (i.get("content") or []) if isinstance(c, dict) and c.get("type") == "output_text") or None
    reasoning = [p.get("text") for i in items if i.get("type") == "reasoning"
                 for p in (i.get("summary") or []) + (i.get("content") or []) if isinstance(p, dict) and p.get("text")]
    inc = (body.get("incomplete_details") or {}).get("reason")
    return Completion(text=text, reasoning="\n\n".join(reasoning) or None, usage=body.get("usage") or {},
                      finish_reason=f"incomplete: {inc}" if inc else body.get("status"),
                      extra={"id": body.get("id"), "model": body.get("model"), "provider": NAME,
                             "status": body.get("status"), "output_types": [i.get("type") for i in items]})


def total_tokens(usage: dict) -> int | None:
    return usage.get("total_tokens")


def token_split(usage: dict) -> tuple[int, int]:
    """(input tokens, output tokens); output includes reasoning tokens."""
    return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)


def cost_usd(usage: dict, cfg: dict | None = None) -> float:
    """The call's cost in COST_UNIT (credits, not dollars), from models.yaml's
    judges.<role>.price_credits_per_mtok: input, cached_input and output per million tokens."""
    price = (cfg or {}).get("price_credits_per_mtok") or {}
    tin, tout = token_split(usage or {})
    cached = int(((usage or {}).get("input_tokens_details") or {}).get("cached_tokens") or 0)
    p_in = float(price.get("input") or 0.0)
    return ((tin - cached) * p_in + cached * float(price.get("cached_input", p_in) or 0.0)
            + tout * float(price.get("output") or 0.0)) / 1e6


def classify_429(res: HttpResult) -> RateLimit:
    """Adaption documents no rate limits. A message naming a daily limit stops the judge for the day;
    anything else is retried after Retry-After (or the judge's default wait)."""
    err = res.body.get("error", {}) if isinstance(res.body, dict) else {}
    text = json.dumps(err) if err else (res.text or "")
    low = text.lower()
    wait = parse_seconds((res.headers or {}).get("retry-after"))
    if "per day" in low or "per-day" in low or "per_day" in low or "daily" in low:
        return RateLimit("day", wait, text[:400])
    return RateLimit("minute" if wait is not None and wait <= 600 else "unknown", wait, text[:400])


def list_models(api_key: str, timeout: float = 30) -> list[str]:
    return sorted(m.id for m in _client(api_key, timeout).models.list().data)
