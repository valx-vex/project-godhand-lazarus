# tests/test_reflection_importance.py
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import reflection
from f3_fakes import FakeOllama
from ollama_client import LlmBudget

NOW = 1783500000.0
DAY = 86400.0


def _payload(created_offset_days=0.5, kind=None, summarized_by=None,
             importance=None, full_text="User: x\nMurphy: y"):
    p = {"full_text": full_text, "user_input": "x", "ai_response": "y"}
    if kind:
        p["kind"] = kind
    if summarized_by is not None:
        p["summarized_by"] = summarized_by
    if importance is not None:
        p["importance"] = importance
    return p, NOW - created_offset_days * DAY


def test_dreamable_excludes_reflections_summarized_and_old():
    rows = [_payload(0.5), _payload(0.5, kind="reflection"),
            _payload(0.5, summarized_by=42), _payload(9.0), _payload(0.5)]
    payloads = [r[0] for r in rows]
    epochs = [r[1] for r in rows]
    epochs[4] = None                       # undated -> not dreamable
    idx = reflection.dreamable_indexes(payloads, epochs, NOW)
    assert idx == [0]


def test_context_is_recent_reflections_only():
    rows = [_payload(0.5), _payload(0.5, kind="reflection"), _payload(9.0, kind="reflection")]
    payloads = [r[0] for r in rows]
    epochs = [r[1] for r in rows]
    assert reflection.context_indexes(payloads, epochs, NOW) == [1]


def test_importance_pass_scores_caches_and_marks_dirty():
    rows = [_payload(0.5), _payload(0.5, importance=7)]
    payloads = [r[0] for r in rows]
    epochs = [r[1] for r in rows]
    dirty = [False, False]
    report = {}
    ollama = FakeOllama(responses=['{"importance": 9}'])
    ok = reflection.importance_pass(payloads, epochs, dirty, NOW, ollama,
                                    report, "murphy_eternal")
    assert ok is True
    assert payloads[0]["importance"] == 9
    assert payloads[0]["importance_model"] == "qwen2.5:7b"
    assert dirty == [True, False]          # cached point untouched
    assert len(ollama.calls) == 1
    assert report["importance_scored"] == 1


def test_importance_input_is_redacted():
    p, e = _payload(0.5, full_text="key was AKIAABCDEFGHIJKLMNOP ok")
    report = {}
    ollama = FakeOllama(responses=['{"importance": 3}'])
    reflection.importance_pass([p], [e], [False], NOW, ollama, report, "c")
    assert "AKIA" not in ollama.calls[0]["prompt"]


def test_importance_llm_down_fails_open():
    p, e = _payload(0.5)
    report = {}
    ok = reflection.importance_pass([p], [e], [False], NOW,
                                    FakeOllama(fail=True), report, "c")
    assert ok is False
    assert "importance" not in p
    assert report["importance_skipped"] == 1


def test_importance_reflections_never_scored():
    p, e = _payload(0.5, kind="reflection")
    ollama = FakeOllama(responses=['{"importance": 9}'])
    ok = reflection.importance_pass([p], [e], [False], NOW, ollama, {}, "c")
    assert ok is True and ollama.calls == [] and "importance" not in p


def test_importance_stops_on_budget():
    rows = [_payload(0.5), _payload(0.6)]
    budget = LlmBudget(0); time.sleep(0.01)
    ollama = FakeOllama(responses=['{"importance": 5}'], budget=budget)
    report = {}
    reflection.importance_pass([r[0] for r in rows], [r[1] for r in rows],
                               [False, False], NOW, ollama, report, "c")
    assert report["importance_scored"] == 0
    assert report.get("importance_note") == "llm budget exhausted"


from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

import sleep_salience
from f3_fakes import fake_embed


def _mem_client(points):
    client = QdrantClient(":memory:")
    client.create_collection(
        "scratch_f3", vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    if points:
        client.upsert(collection_name="scratch_f3", points=points)
    return client


def _pt(pid, created_at, **extra):
    payload = {"user_input": f"u{pid}", "ai_response": f"a{pid}",
               "full_text": f"User: u{pid}\nMurphy: a{pid}",
               "source_file": f"s{pid}", "created_at": created_at}
    payload.update(extra)
    return PointStruct(id=pid, vector=[0.1, 0.2, 0.3, 0.4], payload=payload)


def test_run_scores_importance_and_it_rides_stage7(monkeypatch):
    monkeypatch.delenv("F3_DREAMS_DISABLE", raising=False)
    client = _mem_client([_pt(1, "2026-07-11T01:00:00+0200")])
    ollama = FakeOllama(responses=['{"importance": 8}'])
    sleep_salience.run(client=client, embed_fn=fake_embed,
                       now=1783500000.0, collection="scratch_f3",
                       ollama_client=ollama)
    stored = client.retrieve("scratch_f3", ids=[1], with_payload=True)[0]
    assert stored.payload["importance"] == 8


def test_run_importance_crash_never_breaks_pass(monkeypatch):
    monkeypatch.delenv("F3_DREAMS_DISABLE", raising=False)
    client = _mem_client([_pt(1, "2026-07-11T01:00:00+0200")])

    class Bomb:
        budget = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

    report = sleep_salience.run(client=client, embed_fn=fake_embed,
                                now=1783500000.0, collection="scratch_f3",
                                ollama_client=Bomb())
    assert report is not None
    assert "importance_error" in report


def test_kill_switch_disables_f3(monkeypatch):
    monkeypatch.setenv("F3_DREAMS_DISABLE", "1")
    client = _mem_client([_pt(1, "2026-07-11T01:00:00+0200")])
    ollama = FakeOllama(responses=['{"importance": 8}'])
    sleep_salience.run(client=client, embed_fn=fake_embed, now=1783500000.0,
                       collection="scratch_f3", ollama_client=ollama)
    assert ollama.calls == []
