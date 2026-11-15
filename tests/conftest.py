"""Shared test guard: no test may reach the Adaption API.

The tests load the real .env (runner.load_env), which holds ADAPTION_API_KEY, and the real
models.yaml names an Adaption judge. Every SDK client the adaption provider would build is
replaced here by one that fails the test; tests of the provider install their own fake client.
"""
import pytest

from src.providers import adaption


class _NoNetwork:
    def __getattr__(self, name):
        raise AssertionError("a test tried to call the Adaption API")


@pytest.fixture(autouse=True)
def no_adaption_calls(monkeypatch):
    monkeypatch.setattr(adaption, "_clients", {})
    monkeypatch.setattr(adaption, "_make_client", lambda api_key, timeout: _NoNetwork())
