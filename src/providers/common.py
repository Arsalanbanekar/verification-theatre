"""Shared HTTP plumbing and result types for the provider modules."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests


@dataclass
class HttpResult:
    status: int | None          # None when the request never got a response
    headers: dict               # lower-cased header names
    body: dict | list | None    # parsed JSON body, if any
    text: str                   # raw body text
    latency_s: float
    error: str | None = None    # transport error (timeout, connection reset, ...)


@dataclass
class Completion:
    text: str | None            # the answer text the parser sees
    reasoning: str | None       # reasoning/thought text, if the provider returned any
    usage: dict
    finish_reason: str | None
    extra: dict = field(default_factory=dict)


@dataclass
class RateLimit:
    scope: str                  # "minute", "day" or "unknown"
    wait_s: float | None        # provider's own retry hint, if any
    detail: str


def post_json(url: str, headers: dict, payload: dict, timeout: float) -> HttpResult:
    t0 = time.perf_counter()
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as e:
        return HttpResult(None, {}, None, "", time.perf_counter() - t0, f"{type(e).__name__}: {e}")
    latency = time.perf_counter() - t0
    try:
        body = r.json()
    except ValueError:
        body = None
    return HttpResult(r.status_code, {k.lower(): v for k, v in r.headers.items()}, body, r.text, latency)


def get_json(url: str, headers: dict, timeout: float) -> HttpResult:
    t0 = time.perf_counter()
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return HttpResult(None, {}, None, "", time.perf_counter() - t0, f"{type(e).__name__}: {e}")
    try:
        body = r.json()
    except ValueError:
        body = None
    return HttpResult(r.status_code, {k.lower(): v for k, v in r.headers.items()}, body, r.text,
                      time.perf_counter() - t0)


def parse_seconds(value) -> float | None:
    """'33s', '1.5s', '2m59.56s', '7' -> seconds."""
    if value is None:
        return None
    s = str(value).strip()
    try:
        return float(s)
    except ValueError:
        pass
    total, num = 0.0, ""
    for ch in s:
        if ch.isdigit() or ch == ".":
            num += ch
        elif ch in "hms" and num:
            total += float(num) * {"h": 3600, "m": 60, "s": 1}[ch]
            num = ""
        else:
            return None
    return total if not num else None
