# tests/test_ingest_hermes.py
"""Two-pass skip-existing ingest (F2 D1) for the hermes journal ingester."""
import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ingest_hermes
from ingest_ids import memory_point_id


def _journal(tmp_path, name, turns):
    path = tmp_path / name
    with open(path, "w", encoding="utf-8") as fh:
        for user, assistant in turns:
            fh.write(json.dumps({"type": "turn", "ts": "2026-07-07T10:00:00+0000",
                                 "user": user, "assistant": assistant}) + "\n")
    return path


def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_JOURNAL_DIRS", str(tmp_path))
    monkeypatch.setattr(ingest_hermes, "HERMES_JOURNAL_DIRS", [tmp_path])
    monkeypatch.setattr(ingest_hermes, "COLLECTION_NAME", "f2_scratch_hermes")
    # F2 deviation from brief: brief's tests inject 4-dim fake embeddings but the
    # brief's source hard-codes VECTOR_SIZE=384 (production MiniLM). ensure_collection
    # is created up-front (required for first-run + fail-closed paths) before the lazy
    # embedder's dim is knowable, so the sandbox collection must match the fakes.
    # Source stays production-correct (384); only the test sandbox is resized.
    monkeypatch.setattr(ingest_hermes, "VECTOR_SIZE", 4)


def fake_embed_factory():
    return lambda texts: [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def forbidden_embed_factory():
    raise AssertionError("embed factory must not be called when nothing is new")


class RaisingRetrieveClient:
    def __init__(self, inner):
        self.inner = inner
        self.upserts = 0

    def get_collection(self, name):
        return self.inner.get_collection(name)

    def create_collection(self, **kwargs):
        return self.inner.create_collection(**kwargs)

    def retrieve(self, *a, **k):
        raise RuntimeError("qdrant blip")

    def upsert(self, **kwargs):
        self.upserts += 1


def test_eligible_pairs_filters_short_answers(tmp_path):
    _journal(tmp_path, "20260707_100000_aa.jsonl",
             [("q1", "a" * 30), ("q2", "short")])
    pairs = list(ingest_hermes.eligible_pairs([tmp_path / "20260707_100000_aa.jsonl"]))
    assert [p["user_input"] for p in pairs] == ["q1"]


def test_first_run_ingests_everything(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    _journal(tmp_path, "20260707_100000_aa.jsonl", [("q1", "a" * 30), ("q2", "b" * 30)])
    client = QdrantClient(":memory:")
    code = ingest_hermes.process_sessions(client=client,
                                          embed_factory=fake_embed_factory)
    assert code == 0
    points, _ = client.scroll(collection_name="f2_scratch_hermes", limit=10,
                              with_payload=True)
    assert len(points) == 2
    payloads = {p.payload["user_input"]: p.payload for p in points}
    assert payloads["q1"]["harness"] == "hermes"
    assert payloads["q1"]["created_at"] == "2026-07-07T10:00:00+0000"


def test_second_run_skips_existing_and_never_embeds(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    _journal(tmp_path, "20260707_100000_aa.jsonl", [("q1", "a" * 30)])
    client = QdrantClient(":memory:")
    assert ingest_hermes.process_sessions(client=client,
                                          embed_factory=fake_embed_factory) == 0
    # decorate the existing point with derived + invalidation fields
    pid = memory_point_id(str(tmp_path / "20260707_100000_aa.jsonl"), "q1", "a" * 30)
    client.set_payload(collection_name="f2_scratch_hermes",
                       payload={"salience": 0.9, "invalid_from_ts": 1.0},
                       points=[pid])
    code = ingest_hermes.process_sessions(client=client,
                                          embed_factory=forbidden_embed_factory)
    assert code == 0
    got = client.retrieve(collection_name="f2_scratch_hermes", ids=[pid],
                          with_payload=True, with_vectors=False)[0]
    assert got.payload["salience"] == 0.9          # survived: never rewritten
    assert got.payload["invalid_from_ts"] == 1.0   # the F2 correctness stake


def test_only_new_pairs_embedded_on_incremental_run(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    journal = _journal(tmp_path, "20260707_100000_aa.jsonl", [("q1", "a" * 30)])
    client = QdrantClient(":memory:")
    ingest_hermes.process_sessions(client=client, embed_factory=fake_embed_factory)
    with open(journal, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "turn", "ts": "2026-07-07T11:00:00+0000",
                             "user": "q2", "assistant": "c" * 30}) + "\n")
    embedded = []

    def counting_factory():
        def embed(texts):
            embedded.extend(texts)
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        return embed

    assert ingest_hermes.process_sessions(client=client,
                                          embed_factory=counting_factory) == 0
    assert len(embedded) == 1 and "q2" in embedded[0]
    points, _ = client.scroll(collection_name="f2_scratch_hermes", limit=10)
    assert len(points) == 2


def test_lookup_failure_aborts_without_writes(monkeypatch, tmp_path, capsys):
    _env(monkeypatch, tmp_path)
    _journal(tmp_path, "20260707_100000_aa.jsonl", [("q1", "a" * 30)])
    inner = QdrantClient(":memory:")
    client = RaisingRetrieveClient(inner)
    code = ingest_hermes.process_sessions(client=client,
                                          embed_factory=forbidden_embed_factory)
    assert code == 1
    assert client.upserts == 0
    assert "aborting without writes" in capsys.readouterr().err


def test_report_line_is_last_stdout_line(monkeypatch, tmp_path, capsys):
    _env(monkeypatch, tmp_path)
    _journal(tmp_path, "20260707_100000_aa.jsonl", [("q1", "a" * 30)])
    client = QdrantClient(":memory:")
    ingest_hermes.process_sessions(client=client, embed_factory=fake_embed_factory)
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1] == ("🜂 hermes ingest: 1 pairs seen, 0 already present (skipped), "
                       "1 new → f2_scratch_hermes")


def test_ensure_collection_creates_missing(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = QdrantClient(":memory:")
    ingest_hermes.ensure_collection(client)
    info = client.get_collection("f2_scratch_hermes")
    assert info is not None
