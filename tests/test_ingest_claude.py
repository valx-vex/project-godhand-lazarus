# tests/test_ingest_claude.py
"""F2 refactor contract for the claude-m ingester: lazy client/model, two-pass
skip-existing, report line returned (printed last by __main__)."""
import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ingest_claude
from ingest_ids import memory_point_id


def _session(tmp_path, turns):
    path = tmp_path / "session.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for user, assistant in turns:
            fh.write(json.dumps({"type": "user",
                                 "message": {"content": user}}) + "\n")
            fh.write(json.dumps({"type": "assistant",
                                 "message": {"content": assistant}}) + "\n")
    return path


def _env(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest_claude, "CLAUDE_PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(ingest_claude, "COLLECTION_NAME", "f2_scratch_claude")
    # F2 gap (Tasks 3/4 adjudication): tests use 4-dim fake embeddings but the
    # source hard-codes VECTOR_SIZE=384 (prod MiniLM); resize only the sandbox.
    monkeypatch.setattr(ingest_claude, "VECTOR_SIZE", 4)


def _fake_embed_factory():
    return lambda texts: [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _forbidden_embed_factory():
    raise AssertionError("embed factory must not be called")


def test_import_constructs_no_client_or_model():
    """The reviewed refactor: module import must be side-effect-free."""
    assert not hasattr(ingest_claude, "client")
    assert not hasattr(ingest_claude, "model")


def test_first_run_then_skip_preserves_marks(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    path = _session(tmp_path, [("q1", "a" * 30)])
    client = QdrantClient(":memory:")
    code, line = ingest_claude.process_sessions(client=client,
                                                embed_factory=_fake_embed_factory)
    assert code == 0
    pid = memory_point_id(str(path), "q1", "a" * 30)
    client.set_payload(collection_name="f2_scratch_claude",
                       payload={"salience": 0.5, "invalid_from_ts": 3.0},
                       points=[pid])
    code, line = ingest_claude.process_sessions(
        client=client, embed_factory=_forbidden_embed_factory)
    assert code == 0
    assert line == ("🦷 claude ingest: 1 pairs seen, 1 already present (skipped), "
                    "0 new → f2_scratch_claude")
    got = client.retrieve(collection_name="f2_scratch_claude", ids=[pid],
                          with_payload=True, with_vectors=False)[0]
    assert got.payload["salience"] == 0.5
    assert got.payload["invalid_from_ts"] == 3.0


def test_lookup_failure_aborts(monkeypatch, tmp_path, capsys):
    _env(monkeypatch, tmp_path)
    _session(tmp_path, [("q1", "a" * 30)])

    class Raising:
        def __init__(self):
            self.upserts = 0

        def get_collection(self, name):
            return object()

        def retrieve(self, *a, **k):
            raise RuntimeError("blip")

        def upsert(self, **k):
            self.upserts += 1

    client = Raising()
    code, line = ingest_claude.process_sessions(
        client=client, embed_factory=_forbidden_embed_factory)
    assert code == 1
    assert client.upserts == 0
    assert line is None
    assert "aborting without writes" in capsys.readouterr().err


def test_parse_patterns_unchanged(tmp_path):
    """Regression pin: pattern-4 outer type user/assistant still parses."""
    path = _session(tmp_path, [("hello there", "world answer that is long")])
    pairs = list(ingest_claude.parse_jsonl_file(path))
    assert pairs == [{"user_input": "hello there",
                      "ai_response": "world answer that is long",
                      "source_file": str(path)}]


def test_eligible_pairs_filters(tmp_path):
    path = _session(tmp_path, [("q", "short"), ("q2", "b" * 30)])
    pairs = list(ingest_claude.eligible_pairs([path]))
    assert [p["user_input"] for p in pairs] == ["q2"]
