"""Ollama HTTP client for the F3 night work (spec v2.1 §4).

HTTP API only — NEVER `ollama run` subprocess (VEXPEDIA v1 lesson: ANSI/
reasoning corruption). One shared wall-clock LlmBudget bounds ALL F3 LLM
work (importance + dreams + judge, both collections): per-call timeouts do
not bound a stage of N sequential calls (spec triage T4)."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request


class OllamaError(RuntimeError):
    """Any failure the night must survive fail-open."""


class LlmBudget:
    def __init__(self, seconds: float):
        self._deadline = time.monotonic() + float(seconds)

    def remaining(self) -> float:
        return self._deadline - time.monotonic()

    def exhausted(self) -> bool:
        return self.remaining() <= 0.0


def _default_opener(url, body, timeout):
    req = urllib.request.Request(
        url, data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


_FENCE = re.compile(r"^```[a-z]*\n?|\n?```$", re.MULTILINE)


class OllamaClient:
    def __init__(self, base_url=None, budget=None, opener=None):
        self.base_url = (base_url or os.environ.get("F3_OLLAMA_URL")
                         or "http://localhost:11434").rstrip("/")
        self.budget = budget or LlmBudget(
            float(os.environ.get("F3_LLM_BUDGET_SEC", "900")))
        self._opener = opener or _default_opener
        self._warm_models = set()
        self._cold_timeout = float(os.environ.get("F3_LLM_COLD_TIMEOUT_SEC", "180"))

    def generate(self, model, prompt, timeout_s, temperature=0.0) -> str:
        if self.budget.exhausted():
            raise OllamaError("llm budget exhausted")
        timeout = timeout_s
        if model not in self._warm_models:
            timeout = max(timeout_s, self._cold_timeout)
        body = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": temperature},
        })
        try:
            raw = self._opener(self.base_url + "/api/generate", body, timeout)
            reply = json.loads(raw)
        except OllamaError:
            raise
        except Exception as exc:
            raise OllamaError(f"ollama call failed ({model}): {exc}") from exc
        self._warm_models.add(model)
        text = reply.get("response")
        if not isinstance(text, str):
            raise OllamaError(f"ollama reply missing 'response' ({model})")
        return text.strip()

    def generate_json(self, model, prompt, timeout_s, required_keys=()) -> dict:
        text = self.generate(model, prompt, timeout_s, temperature=0.0)
        cleaned = _FENCE.sub("", text).strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise OllamaError(f"no JSON object in reply ({model})")
        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise OllamaError(f"invalid JSON from {model}: {exc}") from exc
        if not isinstance(data, dict):
            raise OllamaError(f"JSON reply is not an object ({model})")
        for key in required_keys:
            if key not in data:
                raise OllamaError(f"JSON reply missing '{key}' ({model})")
        return data
