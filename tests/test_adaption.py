"""The Adaption provider used by the judge from 15 Nov 2026 (DEVIATIONS.md): request shape, replies,
errors, cost in credits, and a judge run on it. Offline: a fake SDK client stands in for the API."""
import json
import threading

import httpx
import pytest

import adaption as sdk
from src import judge as J
from src import runner as R
from src.providers import PROVIDERS, adaption as A
from src.providers.common import HttpResult

CFG = {"provider": "adaption", "model_id": "glm-5.2", "family": "zhipu",
       "route": {"order": ["adaption"], "allow_fallbacks": False}, "temperature": 0.0, "concurrency": 2,
       "max_output_tokens": 4000, "price_credits_per_mtok": {"input": 1.40, "cached_input": 0.26, "output": 4.40}}
MSGS = [{"role": "user", "content": "grade this"}]
REQ = httpx.Request("POST", "https://api.prod.adaptionlabs.ai/api/v1/responses")


def body(text='{"score": "2", "reason": "ok"}', status="completed", **extra):
    b = {"id": "resp_1", "object": "response", "status": status, "model": "glm-5.2",
         "output": [{"type": "reasoning", "summary": [{"type": "summary_text", "text": "thinking"}]},
                    {"type": "message", "role": "assistant",
                     "content": [{"type": "output_text", "text": text}]}],
         "output_text": text, "error": None, "incomplete_details": None,
         "usage": {"input_tokens": 700, "output_tokens": 300, "total_tokens": 1000,
                   "input_tokens_details": {"cached_tokens": 100}, "output_tokens_details": {"reasoning_tokens": 250}}}
    b.update(extra)
    return b


class FakeRaw:
    def __init__(self, b, status=200, headers=None):
        self.status_code, self.headers = status, headers or {"x-request-id": "req-1"}
        self.http_response = httpx.Response(status, text=json.dumps(b), request=REQ)


class FakeClient:
    """responses.with_raw_response.create: scripted replies (a body dict, or an exception to raise)."""

    def __init__(self, *script, default=body):
        self.script, self.default, self.calls, self.lock = list(script), default, [], threading.Lock()
        self.responses = self
        self.with_raw_response = self

    def create(self, **kwargs):
        with self.lock:
            self.calls.append(kwargs)
            item = self.script.pop(0) if self.script else None
        if isinstance(item, BaseException):
            raise item
        return FakeRaw(item if item is not None else self.default())


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(A, "_make_client", lambda api_key, timeout: fake)
    return fake


def status_error(code, payload):
    r = httpx.Response(code, json=payload, request=REQ, headers={"retry-after": "7"})
    return sdk.APIStatusError(f"HTTP {code}", response=r, body=payload)


def test_registered():
    assert PROVIDERS["adaption"] is A and A.KEY_ENV == "ADAPTION_API_KEY" and A.COST_UNIT == "credits"
    assert A.endpoint(CFG) == "https://api.prod.adaptionlabs.ai/api/v1/responses"


def test_payload_sends_temperature_and_no_unsupported_parameter():
    p = A.build_payload(CFG, MSGS, temperature=0.0, seed=7, max_output_tokens=4000, schema=J.SCHEMA)
    assert p == {"model": "glm-5.2", "input": "grade this", "max_output_tokens": 4000, "store": False,
                 "temperature": 0.0}                         # no seed, schema or reasoning: the API takes none
    two = A.build_payload(CFG, [{"role": "system", "content": "be brief"}] + MSGS, temperature=None, seed=None,
                          max_output_tokens=10, schema=None)
    assert two["instructions"] == "be brief" and two["input"] == "grade this" and "temperature" not in two
    assert A.reasoning_setting(CFG) == {"reasoning": "provider default"}


def test_send_returns_the_raw_body_and_headers(client):
    res = A.send(CFG, {"model": "glm-5.2", "input": "x"}, "key", 30)
    assert res.status == 200 and res.body["output_text"] == '{"score": "2", "reason": "ok"}'
    assert res.headers["x-request-id"] == "req-1" and json.loads(res.text) == res.body
    assert client.calls == [{"model": "glm-5.2", "input": "x"}]


def test_send_turns_sdk_errors_into_results(client):
    client.script = [status_error(429, {"error": {"code": "rate_limited", "message": "slow down"}}),
                     sdk.APITimeoutError(REQ), sdk.APIConnectionError(request=REQ)]
    r429 = A.send(CFG, {}, "key", 30)
    assert r429.status == 429 and r429.body["error"]["message"] == "slow down" and r429.headers["retry-after"] == "7"
    assert A.classify_429(r429).scope == "minute" and A.classify_429(r429).wait_s == 7
    for _ in range(2):
        r = A.send(CFG, {}, "key", 30)
        assert r.status is None and r.body is None and r.error


def test_sdk_client_is_built_without_retries():
    c = sdk.Adaption(api_key="test-key", max_retries=0)
    assert c.max_retries == 0 and str(c.base_url).rstrip("/") == A.DEFAULT_BASE_URL


@pytest.mark.parametrize("b,is_error", [
    (body(), False),
    (body(text="", status="incomplete", incomplete_details={"reason": "max_output_tokens"}), False),  # a reply
    (body(status="failed", error={"code": "server_error", "message": "The model provider could not complete"}), True),
    (body(status="in_progress"), True),
    ("not json", True),
])
def test_errors_inside_a_200_are_recognised(b, is_error):
    assert (A.body_error(b) is not None) is is_error


def test_extract_cost_and_tokens():
    c = A.extract(body())
    assert c.text == '{"score": "2", "reason": "ok"}' and c.reasoning == "thinking" and c.finish_reason == "completed"
    assert c.extra["model"] == "glm-5.2" and c.extra["provider"] == "adaption" and c.extra["id"] == "resp_1"
    assert A.token_split(c.usage) == (700, 300) and A.total_tokens(c.usage) == 1000
    assert A.cost_usd(c.usage, CFG) == pytest.approx((600 * 1.40 + 100 * 0.26 + 300 * 4.40) / 1e6)
    assert A.cost_usd(c.usage) == 0.0                                    # no prices, no cost
    no_text = body()
    del no_text["output_text"]
    assert A.extract(no_text).text == '{"score": "2", "reason": "ok"}'   # rebuilt from the message item
    cut = A.extract(body(text="", status="incomplete", incomplete_details={"reason": "max_output_tokens"}))
    assert cut.finish_reason == "incomplete: max_output_tokens" and J.parse_judgement(cut.text)[0] is None


@pytest.mark.parametrize("text,headers,scope", [
    ('{"error": {"message": "daily request limit reached"}}', {}, "day"),
    ('{"error": {"message": "too many requests"}}', {"retry-after": "12"}, "minute"),
    ('{"error": {"message": "too many requests"}}', {}, "unknown"),
])
def test_classify_429(text, headers, scope):
    assert A.classify_429(HttpResult(429, headers, json.loads(text), text, 0.1)).scope == scope


@pytest.mark.parametrize("override,fragment", [
    ({}, None),
    ({"model_id": "stack:my-stack"}, "inference stack"),
    ({"model_id": "gemma-4-31b-it"}, "excluded by §5"),
    ({"model_id": "qwen3.5-397b"}, "excluded by §5"),
    ({"provider": "elsewhere"}, "provider must be one of"),
    ({"family": None}, "family is empty"),
])
def test_config_problems_for_an_adaption_judge(override, fragment):
    problems = J.config_problems({"judges": {"main": {**CFG, **override}}}, "main")
    assert (problems == []) if fragment is None else any(fragment in p for p in problems)


def test_models_yaml_names_glm_5_2_on_adaption():
    cfg = R.load_config(R.REPO / "models.yaml")
    j = J.judge_config(cfg, "main")
    assert (j["provider"], j["model_id"], j["temperature"]) == ("adaption", "glm-5.2", 0.0)
    assert J.config_problems(cfg, "main") == []
    assert j["max_output_tokens"] == 4000 and j["rejudge"]["max_output_tokens"] == 12000   # DEVIATIONS.md, 16 Nov


def test_judge_run_logs_credits_and_stops_at_its_credit_budget(client, tmp_path, monkeypatch):
    monkeypatch.setattr(R, "SLEEP", lambda stop, s: None)
    client.script = [body(text="no json at all")]
    items = [J.Item(f"r{i}", "facts", "statement", "justification", meta={"seed": i}) for i in range(6)]
    run = J.JudgeRun({**CFG, "concurrency": 1, "budget_credits": 0.003}, "main", "key", tmp_path / "j.jsonl",
                     tmp_path / "a.jsonl", stage="main", say=lambda *a: None)
    s = run.run(items)
    rows, attempts = R.read_raw(tmp_path / "j.jsonl"), R.read_raw(tmp_path / "a.jsonl")
    per_call = (600 * 1.40 + 100 * 0.26 + 300 * 4.40) / 1e6                  # 0.002186 credits
    assert s["cost_unit"] == "credits" and s["stop_kind"] == "budget" and "credits" in s["stop_reason"]
    assert len(rows) == 2 and s["spent"] == pytest.approx(2 * per_call) and s["spent_text"].endswith(" credits")
    assert [r["valid"] for r in rows] == [False, True] and rows[0]["parse_error"].startswith("invalid JSON")
    assert all(r["cost_credits"] == pytest.approx(per_call) and "cost_usd" not in r for r in rows)
    assert all(r["served_by"] == "adaption" and r["model_reported"] == "glm-5.2" for r in rows)
    assert rows[1]["reasoning_setting"] == {"reasoning": "provider default"} and rows[1]["temperature"] == 0.0
    assert rows[1]["request"]["body"]["store"] is False and "seed" not in rows[1]["request"]["body"]
    assert len(attempts) == 2 and all(a["cost_credits"] == pytest.approx(per_call) for a in attempts)
    again = J.JudgeRun({**CFG, "budget_credits": 0.003}, "main", "key", tmp_path / "j.jsonl", tmp_path / "a.jsonl",
                       stage="main", say=lambda *a: None)
    assert again.spent == pytest.approx(2 * per_call)                      # resumes the spend from the attempts


def test_no_test_can_reach_the_api():
    with pytest.raises(AssertionError, match="Adaption API"):
        A.send(CFG, {"model": "glm-5.2", "input": "x"}, "key", 30)
