"""The OpenRouter provider used by the judges: request shape, replies, errors inside a 200, 429s."""
import json
import time

import pytest

from src import judge as J
from src.providers import PROVIDERS, openrouter as O
from src.providers.common import HttpResult

CFG = {"provider": "openrouter", "model_id": "test-lab/judge-1", "temperature": 0.0, "reasoning": {"effort": "low"},
       "route": {"order": ["test-provider"], "allow_fallbacks": False, "require_parameters": True}}
MSGS = [{"role": "user", "content": "grade this"}]


def body(content='{"score": "2", "reason": "ok"}', **extra):
    return {"id": "gen-1", "model": "test-lab/judge-1", "provider": "TestProvider",
            "choices": [{"message": {"content": content, "reasoning": "thinking"}, "finish_reason": "stop",
                         "native_finish_reason": "stop"}],
            "usage": {"prompt_tokens": 600, "completion_tokens": 40, "total_tokens": 640, "cost": 0.00042}, **extra}


def test_registered():
    assert PROVIDERS["openrouter"] is O and O.KEY_ENV == "OPENROUTER_API_KEY"


def test_payload_pins_the_provider_and_asks_for_the_schema():
    p = O.build_payload(CFG, MSGS, temperature=0.0, seed=7, max_output_tokens=4000, schema=J.SCHEMA)
    assert p["model"] == "test-lab/judge-1" and p["messages"] == MSGS and p["max_tokens"] == 4000
    assert p["temperature"] == 0.0 and p["reasoning"] == {"effort": "low"}
    assert p["provider"] == {"order": ["test-provider"], "allow_fallbacks": False, "require_parameters": True}
    assert p["response_format"] == {"type": "json_schema",
                                    "json_schema": {"name": "judgement", "strict": True, "schema": J.SCHEMA}}
    assert "seed" not in p                              # off unless send_seed: it could exclude the pinned provider
    assert O.build_payload({**CFG, "send_seed": True}, MSGS, temperature=0.0, seed=7, max_output_tokens=10,
                           schema=None)["seed"] == 7
    assert O.build_payload({**CFG, "json_mode": "json_object"}, MSGS, temperature=0.0, seed=None, max_output_tokens=10,
                           schema=J.SCHEMA)["response_format"] == {"type": "json_object"}


def test_extract_and_cost():
    c = O.extract(body())
    assert c.text == '{"score": "2", "reason": "ok"}' and c.reasoning == "thinking" and c.finish_reason == "stop"
    assert c.extra["provider"] == "TestProvider" and c.extra["id"] == "gen-1"
    assert O.cost_usd(c.usage) == pytest.approx(0.00042) and O.cost_usd({}) == 0.0
    assert O.token_split(c.usage) == (600, 40) and O.total_tokens(c.usage) == 640


@pytest.mark.parametrize("b,is_error", [
    (body(), False),
    ({"error": {"code": 502, "message": "upstream died"}}, True),                       # 200 with only an error
    ({"choices": [{"message": {"content": "partial"}, "finish_reason": "error",
                   "error": {"code": 502, "message": "mid-stream"}}]}, True),            # error inside the choice
    ({"id": "x"}, True),                                                                 # no choices at all
    ("not json", True),
])
def test_errors_inside_a_200_are_recognised(b, is_error):
    assert (O.body_error(b) is not None) is is_error


def res429(message, headers=None):
    b = {"error": {"code": 429, "message": message}}
    return HttpResult(429, headers or {}, b, json.dumps(b), 0.1)


@pytest.mark.parametrize("message,headers,scope", [
    ("Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day", {}, "day"),
    ("Rate limit exceeded: free-models-per-min.", {}, "minute"),
    ("test-lab/judge-1:free is temporarily rate-limited upstream. Please retry shortly.", {}, "minute"),
    ("Rate limit exceeded", {"x-ratelimit-remaining": "0",
                             "x-ratelimit-reset": str(int((time.time() + 7200) * 1000))}, "day"),
    ("Rate limit exceeded", {"retry-after": "12"}, "unknown"),
])
def test_classify_429(message, headers, scope):
    rl = O.classify_429(res429(message, headers))
    assert rl.scope == scope
    if "retry-after" in headers:
        assert rl.wait_s == 12.0
