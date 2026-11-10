"""Google Gemini API, REST generateContent. Docs read 2026-11-08 (ai.google.dev, now aistudio.google.com)."""
from __future__ import annotations

import json

from .common import Completion, HttpResult, RateLimit, get_json, parse_seconds, post_json

NAME = "gemini"
KEY_ENV = "GEMINI_API_KEY"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"
RATE_HEADERS = ("retry-after",)


def build_payload(cfg: dict, messages: list[dict], *, temperature, seed, max_output_tokens, schema) -> dict:
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                for m in messages if m["role"] != "system"]
    gc = {}
    if temperature is not None:
        gc["temperature"] = temperature
    if seed is not None:
        gc["seed"] = seed
    gc["maxOutputTokens"] = max_output_tokens
    if schema is not None:  # None: plain text (the Gemma judge; JSON mode is undocumented for Gemma)
        gc["responseMimeType"] = "application/json"
        gc["responseJsonSchema"] = schema
    gc.update(cfg.get("generation_config") or {})  # thinkingConfig
    return {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gc}


def reasoning_setting(cfg: dict) -> dict:
    return {"thinkingConfig": (cfg.get("generation_config") or {}).get("thinkingConfig")}


def endpoint(cfg: dict) -> str:
    return URL.format(model=cfg["model_id"])  # the key travels in a header, never in the URL


def send(cfg: dict, payload: dict, api_key: str, timeout: float) -> HttpResult:
    return post_json(URL.format(model=cfg["model_id"]), {"x-goog-api-key": api_key}, payload, timeout)


def failed_generation(res: HttpResult) -> str | None:
    """Groq's json_validate_failed has no Gemini counterpart: schema mode returns 200 or an error."""
    return None


def extract(body: dict) -> Completion:
    usage = body.get("usageMetadata") or {}
    extra = {"modelVersion": body.get("modelVersion"), "responseId": body.get("responseId")}
    candidates = body.get("candidates") or []
    if not candidates:  # e.g. the prompt was blocked
        block = (body.get("promptFeedback") or {}).get("blockReason")
        return Completion(None, None, usage, f"no candidates ({block})" if block else "no candidates", extra)
    c = candidates[0]
    parts = (c.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")) or None
    thoughts = "".join(p.get("text", "") for p in parts if p.get("thought")) or None
    return Completion(text, thoughts, usage, c.get("finishReason"), extra)


def total_tokens(usage: dict) -> int | None:
    return usage.get("totalTokenCount")


def token_split(usage: dict) -> tuple[int, int]:
    """(input tokens, output tokens); output includes thinking tokens, which are billed as output."""
    return (int(usage.get("promptTokenCount") or 0),
            int(usage.get("candidatesTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0))


def classify_429(res: HttpResult) -> RateLimit:
    """Not documented for generateContent. Reads google.rpc QuotaFailure quotaId/quotaMetric
    ("...PerDay..." vs "...PerMinute...") and RetryInfo.retryDelay when present, then the
    message text, including the Interactions API codes quota_exceeded / rate_limit_exceeded."""
    err = res.body.get("error", {}) if isinstance(res.body, dict) else {}
    scope, wait = "unknown", parse_seconds(res.headers.get("retry-after"))
    for d in err.get("details") or []:
        kind = str(d.get("@type", ""))
        if kind.endswith("RetryInfo"):
            wait = parse_seconds(d.get("retryDelay")) or wait
        if kind.endswith("QuotaFailure"):
            for v in d.get("violations") or []:
                q = f"{v.get('quotaId', '')} {v.get('quotaMetric', '')}".lower()
                if "perday" in q or "per_day" in q or "per day" in q:
                    scope = "day"
                elif scope != "day" and ("perminute" in q or "per_minute" in q or "per minute" in q):
                    scope = "minute"
    text = json.dumps(err) if err else res.text
    low = text.lower()
    if scope == "unknown":
        if "quota_exceeded" in low or "per day" in low or "daily" in low:
            scope = "day"
        elif "rate_limit_exceeded" in low or "per minute" in low or "per second" in low:
            scope = "minute"
    return RateLimit(scope, wait, text[:400])


def list_models(api_key: str, timeout: float = 30) -> list[str]:
    res = get_json(MODELS_URL, {"x-goog-api-key": api_key}, timeout)
    if res.status != 200 or not isinstance(res.body, dict):
        raise RuntimeError(f"Gemini model list failed: {res.status} {res.error or res.text[:200]}")
    return sorted(m["name"].removeprefix("models/") for m in res.body.get("models", []))
