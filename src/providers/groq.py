"""Groq (OpenAI-compatible chat completions). Docs read 2026-11-08: console.groq.com/docs."""
from __future__ import annotations

import json
import re

from .common import Completion, HttpResult, RateLimit, get_json, parse_seconds, post_json

NAME = "groq"
KEY_ENV = "GROQ_API_KEY"
URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"
RATE_HEADERS = ("retry-after", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
                "x-ratelimit-reset-requests", "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens",
                "x-ratelimit-reset-tokens")


def build_payload(cfg: dict, messages: list[dict], *, temperature, seed, max_output_tokens, schema) -> dict:
    p = {"model": cfg["model_id"], "messages": messages}
    if temperature is not None:
        p["temperature"] = temperature
    if seed is not None:
        p["seed"] = seed
    p["max_completion_tokens"] = max_output_tokens
    p["response_format"] = {"type": "json_schema",
                            "json_schema": {"name": "answer", "strict": True, "schema": schema}}
    p.update(cfg.get("reasoning") or {})  # reasoning_effort, include_reasoning / reasoning_format
    return p


def reasoning_setting(cfg: dict) -> dict:
    return dict(cfg.get("reasoning") or {})


def endpoint(cfg: dict) -> str:
    return URL


def send(cfg: dict, payload: dict, api_key: str, timeout: float) -> HttpResult:
    return post_json(URL, {"Authorization": f"Bearer {api_key}"}, payload, timeout)


def extract(body: dict) -> Completion:
    choice = (body.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    return Completion(text=msg.get("content"), reasoning=msg.get("reasoning"),
                      usage=body.get("usage") or {}, finish_reason=choice.get("finish_reason"),
                      extra={"id": body.get("id"), "model": body.get("model"),
                             "system_fingerprint": body.get("system_fingerprint")})


def total_tokens(usage: dict) -> int | None:
    return usage.get("total_tokens")


def token_split(usage: dict) -> tuple[int, int]:
    """(billed input tokens, billed output tokens); output includes reasoning tokens."""
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def classify_429(res: HttpResult) -> RateLimit:
    """Groq does not document how to tell limits apart; its error messages name the limit
    ("... on tokens per minute (TPM) ...", "... requests per day (RPD) ..."), which is used
    first, then the RPD header, then the size of retry-after."""
    msg = json.dumps(res.body) if res.body is not None else res.text
    low = msg.lower()
    wait = parse_seconds(res.headers.get("retry-after"))
    if re.search(r"per day|\((rpd|tpd)\)", low):
        return RateLimit("day", wait, msg[:400])
    if re.search(r"per minute|\((rpm|tpm)\)", low):
        return RateLimit("minute", wait, msg[:400])
    if res.headers.get("x-ratelimit-remaining-requests") == "0":
        return RateLimit("day", wait, "x-ratelimit-remaining-requests (RPD) is 0; " + msg[:300])
    if wait is not None and wait > 600:
        return RateLimit("day", wait, f"retry-after {wait:.0f}s; " + msg[:300])
    return RateLimit("unknown", wait, msg[:400])


def list_models(api_key: str, timeout: float = 30) -> list[str]:
    res = get_json(MODELS_URL, {"Authorization": f"Bearer {api_key}"}, timeout)
    if res.status != 200 or not isinstance(res.body, dict):
        raise RuntimeError(f"Groq model list failed: {res.status} {res.error or res.text[:200]}")
    return sorted(m["id"] for m in res.body.get("data", []))
