"""Provider registry: each module exposes the same small interface.

NAME, KEY_ENV, RATE_HEADERS, build_payload(), reasoning_setting(), endpoint(), send(),
extract(), total_tokens(), token_split(), classify_429(), list_models().
"""
from . import gemini, groq

PROVIDERS = {groq.NAME: groq, gemini.NAME: gemini}
