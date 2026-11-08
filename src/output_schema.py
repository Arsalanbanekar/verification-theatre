"""The model output contract (PREREGISTRATION.md §5): one schema for both providers, one parser.

The provider schema avoids keywords that Groq's strict mode does not document (minimum,
maximum, minItems). Those constraints are enforced here, in parse_response, so a reply that
breaks them counts as a parse failure exactly as malformed JSON does.
"""
from __future__ import annotations

import json
import re

try:
    from .prompt_text import REASONS
except ImportError:
    from prompt_text import REASONS

ACCEPT_VALUES = ("true", "false", "uncertain")
REASON_CODES = tuple(code for code, _ in REASONS)

SCHEMA = {
    "type": "object",
    "properties": {
        "accept": {"type": "string", "enum": list(ACCEPT_VALUES)},
        "confidence": {"type": "integer"},
        "reasons": {"type": "array", "items": {"type": "string", "enum": list(REASON_CODES)}},
        "justification": {"type": "string"},
    },
    "required": ["accept", "confidence", "reasons", "justification"],
    "additionalProperties": False,
}

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def _extract_object(text: str):
    s = text.strip()
    m = _FENCE.match(s)
    if m:
        s = m.group(1)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start, end = s.find("{"), s.rfind("}")  # tolerate a stray preamble or trailer
    if start != -1 and end > start:
        return json.loads(s[start:end + 1])
    raise json.JSONDecodeError("no JSON object found", s, 0)


def parse_response(text: str | None):
    """Return (parsed, None) for a valid reply, or (None, error message).

    `parsed` is normalised: accept lower-cased, confidence an int, reasons de-duplicated in
    order. Nothing else is changed; the raw text is always kept by the caller.
    """
    if not text or not text.strip():
        return None, "empty response"
    try:
        obj = _extract_object(text)
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"invalid JSON: {e}"
    if not isinstance(obj, dict):
        return None, "top level is not an object"
    missing = [k for k in SCHEMA["required"] if k not in obj]
    if missing:
        return None, f"missing fields: {missing}"
    extra = sorted(set(obj) - set(SCHEMA["properties"]))
    if extra:
        return None, f"unexpected fields: {extra}"

    accept = obj["accept"]
    if isinstance(accept, bool):
        accept = "true" if accept else "false"
    if not isinstance(accept, str) or accept.strip().lower() not in ACCEPT_VALUES:
        return None, f"bad accept: {obj['accept']!r}"
    conf = obj["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float, str)):
        return None, f"bad confidence: {conf!r}"
    try:
        conf_f = float(conf)
    except ValueError:
        return None, f"bad confidence: {conf!r}"
    if conf_f != int(conf_f) or not 0 <= conf_f <= 100:
        return None, f"confidence not an integer in 0-100: {conf!r}"
    reasons = obj["reasons"]
    if not isinstance(reasons, list) or not reasons:
        return None, "reasons must be a non-empty list"
    if any(r not in REASON_CODES for r in reasons):
        return None, f"unknown reason code in {reasons!r}"
    just = obj["justification"]
    if not isinstance(just, str) or not just.strip():
        return None, "justification must be a non-empty string"

    return {"accept": accept.strip().lower(), "confidence": int(conf_f),
            "reasons": list(dict.fromkeys(reasons)), "justification": just}, None
