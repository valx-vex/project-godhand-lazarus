import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "mcp_server"))

import lazarus_mcp
import salience


class FakeHit:
    def __init__(self, id, score, payload):
        self.id, self.score, self.payload = id, score, payload


class FakeResponse:
    def __init__(self, points):
        self.points = points


class FakeClient:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.hits)


class FakeModel:
    def encode(self, text):
        import numpy as np
        return np.zeros(4)


def _wire(monkeypatch, tmp_path, hits):
    client = FakeClient(hits)
    monkeypatch.setattr(lazarus_mcp, "get_client", lambda: client)
    monkeypatch.setattr(lazarus_mcp, "get_model", lambda: FakeModel())
    monkeypatch.setenv("LAZARUS_RETRIEVAL_LOG", str(tmp_path / "log.jsonl"))
    return client


def test_rerank_orders_by_adjusted(monkeypatch, tmp_path):
    # B: lower cosine but pinned -> adjusted 0.8*f(>=0.95) ~ 0.98 beats A's 0.9*1.0
    hits = [FakeHit(1, 0.9, {"user_input": "a", "ai_response": "ra"}),
            FakeHit(2, 0.8, {"user_input": "b", "ai_response": "rb",
                             "salience_pinned": True})]
    _wire(monkeypatch, tmp_path, hits)
    result = lazarus_mcp.search_memories("q", "murphy", limit=2)
    assert [m["point_id"] for m in result["memories"]] == [2, 1]
    top = result["memories"][0]
    assert top["cosine"] == 0.8
    assert top["score"] > 0.9
    assert top["salience_multiplier"] >= salience.f(salience.PIN_FLOOR) - 1e-9


def test_overfetch_filter_and_cut(monkeypatch, tmp_path):
    hits = [FakeHit(i, 1.0 - i * 0.01, {"user_input": str(i), "ai_response": "r"})
            for i in range(15)]
    client = _wire(monkeypatch, tmp_path, hits)
    result = lazarus_mcp.search_memories("q", "murphy", limit=5)
    assert len(result["memories"]) == 5
    call = client.calls[0]
    assert call["limit"] == 15                      # max(5*3, 15)
    assert call["query_filter"] is not None         # invalidation filter passed


def test_retrieval_logged_with_tool_name(monkeypatch, tmp_path):
    hits = [FakeHit(7, 0.5, {"user_input": "x", "ai_response": "y"})]
    _wire(monkeypatch, tmp_path, hits)
    lazarus_mcp.search_memories("q", "murphy", limit=1, tool_name="lazarus_remember")
    lines = (tmp_path / "log.jsonl").read_text().strip().splitlines()
    record = json.loads(lines[0])
    assert record["tool"] == "lazarus_remember"
    assert record["results"][0]["id"] == 7
    assert record["collection"] == "murphy_eternal"


def test_unknown_persona_unchanged(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, [])
    result = lazarus_mcp.search_memories("q", "nobody", limit=1)
    assert "error" in result
