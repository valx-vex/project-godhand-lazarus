# tests/f3_fakes.py
"""Shared F3 test fakes — no network, no models, ever."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ollama_client import LlmBudget, OllamaError


class FakeOllama:
    """Scripted Ollama. responses: list of str (generate) — cycled; or raise
    OllamaError when fail=True. Records every prompt."""

    def __init__(self, responses=("ok",), fail=False, budget=None):
        self.responses = list(responses)
        self.fail = fail
        self.budget = budget or LlmBudget(600)
        self.calls = []

    def generate(self, model, prompt, timeout_s, temperature=0.0):
        self.calls.append({"model": model, "prompt": prompt,
                           "timeout": timeout_s, "temperature": temperature})
        if self.budget.exhausted():
            raise OllamaError("llm budget exhausted")
        if self.fail:
            raise OllamaError("fake failure")
        return self.responses[(len(self.calls) - 1) % len(self.responses)]

    def generate_json(self, model, prompt, timeout_s, required_keys=()):
        import json
        text = self.generate(model, prompt, timeout_s)
        data = json.loads(text)
        for key in required_keys:
            if key not in data:
                raise OllamaError(f"missing {key}")
        return data


def fake_embed(texts):
    """Deterministic tiny embeddings (4-dim) from text hash."""
    out = []
    for t in texts:
        h = abs(hash(t))
        out.append([((h >> (8 * k)) % 100) / 100.0 for k in range(4)])
    return out
