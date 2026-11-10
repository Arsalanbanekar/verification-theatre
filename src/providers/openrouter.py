"""OpenRouter chat completions: the two scope-accuracy judges (PREREGISTRATION.md §5, rev 3.4).

Docs read 2026-11-10 (openrouter.ai/docs: api-reference overview, errors and limits; features
provider-routing and structured-outputs; use-cases reasoning-tokens and usage-accounting):
- usage, including `cost` in USD credits, comes with every non-streaming response;
- an error can arrive inside an HTTP 200: a body with `error` and no `choices`, or a choice with
  finish_reason "error". Both are failed attempts, not replies;
- `provider: {order: [slug], allow_fallbacks: false}` pins the serving provider, and
  `require_parameters: true` routes only to providers that support every parameter sent;
- `:free` models allow 20 requests a minute and 50 a day (1000 a day once 10 credits have been
  bought), counted per UTC day.
"""
from __future__ import annotations

import json
import time

from .common import Completion, HttpResult, RateLimit, get_json, parse_seconds, post_json

NAME = "openrouter"
KEY_ENV = "OPENROUTER_API_KEY"
URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
RATE_HEADERS = ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")


def build_payload(cfg: dict, messages: list[dict], *, temperature, seed, max_output_tokens, schema) -> dict:
    p = {"model": cfg["model_id"], "messages": messages, "max_tokens": max_output_tokens}
    if temperature is not None:
        p["temperature"] = temperature
    if seed is not None and cfg.get("send_seed"):  # off by default: with require_parameters, an
        p["seed"] = seed                            # unsupported seed would exclude the pinned provider
    if schema is not None:
        if cfg.get("json_mode", "json_schema") == "json_object":
            p["response_format"] = {"type": "json_object"}
        else:
            p["response_format"] = {"type": "json_schema",
                                    "json_schema": {"name": "judgement", "strict": True, "schema": schema}}
    if cfg.get("reasoning"):
        p["reasoning"] = dict(cfg["reasoning"])
    if cfg.get("route"):
        p["provider"] = dict(cfg["route"])
    return p


def reasoning_setting(cfg: dict) -> dict:
    return {"reasoning": cfg.get("reasoning")}


def endpoint(cfg: dict) -> str:
    return URL


def send(cfg: dict, payload: dict, api_key: str, timeout: float) -> HttpResult:
    return post_json(URL, {"Authorization": f"Bearer {api_key}"}, payload, timeout)


def failed_generation(res: HttpResult) -> str | None:
    return None


def body_error(body) -> dict | None:
    """The error carried by an HTTP 200 body, or None if the body is a usable reply."""
    if not isinstance(body, dict):
        return {"message": "the response body is not JSON"}
    choices = body.get("choices") or []
    if body.get("error") and not choices:
        err = body["error"]
        return err if isinstance(err, dict) else {"message": str(err)}
    if not choices:
        return {"message": "the response has no choices"}
    c = choices[0] or {}
    if c.get("error") or c.get("finish_reason") == "error":
        err = c.get("error")
        return err if isinstance(err, dict) else {"message": "finish_reason error"}
    return None


def extract(body: dict) -> Completion:
    choice = (body.get("choices") or [{}])[0] or {}
    msg = choice.get("message") or {}
    return Completion(text=msg.get("content"), reasoning=msg.get("reasoning"), usage=body.get("usage") or {},
                      finish_reason=choice.get("finish_reason"),
                      extra={"id": body.get("id"), "model": body.get("model"), "provider": body.get("provider"),
                             "native_finish_reason": choice.get("native_finish_reason"),
                             "system_fingerprint": body.get("system_fingerprint")})


def total_tokens(usage: dict) -> int | None:
    return usage.get("total_tokens")


def token_split(usage: dict) -> tuple[int, int]:
    """(input tokens, output tokens); output includes reasoning tokens, which are billed as output."""
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def cost_usd(usage: dict) -> float:
    """OpenRouter's own charge for the call, in USD credits (0 for :free models)."""
    try:
        return float(usage.get("cost") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _reset_wait(value) -> float | None:
    """x-ratelimit-reset: epoch milliseconds, epoch seconds, or seconds from now."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v > 1e12:
        v = v / 1000.0 - time.time()
    elif v > 1e9:
        v = v - time.time()
    return max(0.0, v)


def classify_429(res: HttpResult) -> RateLimit:
    """Free-model limits name themselves ("free-models-per-day", "free-models-per-min"); an upstream
    provider's own limit says "rate-limited upstream" and clears within minutes."""
    err = res.body.get("error", {}) if isinstance(res.body, dict) else {}
    text = json.dumps(err) if err else (res.text or "")
    low = text.lower()
    wait = parse_seconds(res.headers.get("retry-after"))
    if wait is None:
        wait = _reset_wait(res.headers.get("x-ratelimit-reset"))
    if "per-day" in low or "per_day" in low or "per day" in low or "daily" in low:
        return RateLimit("day", wait, text[:400])
    if "per-min" in low or "per_min" in low or "per minute" in low or "upstream" in low:
        return RateLimit("minute", wait, text[:400])
    if res.headers.get("x-ratelimit-remaining") == "0" and wait is not None and wait > 600:
        return RateLimit("day", wait, text[:400])
    return RateLimit("unknown", wait, text[:400])


def list_models(api_key: str, timeout: float = 30) -> list[str]:
    res = get_json(MODELS_URL, {"Authorization": f"Bearer {api_key}"}, timeout)
    if res.status != 200 or not isinstance(res.body, dict):
        raise RuntimeError(f"OpenRouter model list failed: {res.status} {res.error or res.text[:200]}")
    return sorted(m["id"] for m in res.body.get("data", []))
