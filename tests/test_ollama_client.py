# tests/test_ollama_client.py
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ollama_client import LlmBudget, OllamaClient, OllamaError


def make_opener(replies):
    """replies: list of (payload_dict | Exception). Records calls."""
    calls = []

    def opener(url, body, timeout):
        calls.append({"url": url, "body": json.loads(body), "timeout": timeout})
        reply = replies[min(len(calls) - 1, len(replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply)

    opener.calls = calls
    return opener


def test_generate_returns_response_text():
    opener = make_opener([{"response": "  hello  "}])
    client = OllamaClient(base_url="http://x", budget=LlmBudget(60), opener=opener)
    assert client.generate("m1", "prompt", timeout_s=5) == "hello"
    body = opener.calls[0]["body"]
    assert body["model"] == "m1" and body["stream"] is False
    assert body["keep_alive"] == "30m"


def test_first_call_per_model_uses_cold_timeout(monkeypatch):
    monkeypatch.setenv("F3_LLM_COLD_TIMEOUT_SEC", "180")
    opener = make_opener([{"response": "a"}, {"response": "b"}])
    client = OllamaClient(base_url="http://x", budget=LlmBudget(600), opener=opener)
    client.generate("m1", "p", timeout_s=30)
    client.generate("m1", "p", timeout_s=30)
    assert opener.calls[0]["timeout"] == 180
    assert opener.calls[1]["timeout"] == 30


def test_budget_exhausted_raises_without_calling():
    opener = make_opener([{"response": "never"}])
    budget = LlmBudget(0)
    time.sleep(0.01)
    client = OllamaClient(base_url="http://x", budget=budget, opener=opener)
    with pytest.raises(OllamaError):
        client.generate("m", "p", timeout_s=5)
    assert opener.calls == []


def test_http_error_wrapped():
    opener = make_opener([OSError("connection refused")])
    client = OllamaClient(base_url="http://x", budget=LlmBudget(60), opener=opener)
    with pytest.raises(OllamaError):
        client.generate("m", "p", timeout_s=5)


def test_generate_json_parses_and_validates():
    opener = make_opener([{"response": '{"importance": 7}'}])
    client = OllamaClient(base_url="http://x", budget=LlmBudget(60), opener=opener)
    assert client.generate_json("m", "p", 5, required_keys=("importance",)) == {"importance": 7}


def test_generate_json_missing_key_raises():
    opener = make_opener([{"response": '{"other": 1}'}])
    client = OllamaClient(base_url="http://x", budget=LlmBudget(60), opener=opener)
    with pytest.raises(OllamaError):
        client.generate_json("m", "p", 5, required_keys=("importance",))


def test_generate_json_tolerates_fenced_output():
    opener = make_opener([{"response": '```json\n{"score": 0.8, "why": "ok"}\n```'}])
    client = OllamaClient(base_url="http://x", budget=LlmBudget(60), opener=opener)
    out = client.generate_json("m", "p", 5, required_keys=("score", "why"))
    assert out["score"] == 0.8
