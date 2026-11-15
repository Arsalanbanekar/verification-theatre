"""Provider registry: each module exposes the same small interface.

NAME, KEY_ENV, RATE_HEADERS, build_payload(), reasoning_setting(), endpoint(), send(),
extract(), total_tokens(), token_split(), classify_429(), list_models().
groq and gemini serve the study models. The scope-accuracy judges were planned on openrouter;
since 15 Nov 2026 (DEVIATIONS.md) the judge runs on adaption. Judge providers also expose
LABEL, COST_UNIT, CREDITS_HINT, body_error() and cost_usd(usage, cfg), in COST_UNIT.
"""
from . import adaption, gemini, groq, openrouter

PROVIDERS = {groq.NAME: groq, gemini.NAME: gemini, openrouter.NAME: openrouter, adaption.NAME: adaption}
