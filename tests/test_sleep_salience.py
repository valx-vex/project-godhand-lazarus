# tests/test_sleep_salience.py
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

import ingest_hermes
import salience
import sleep_salience
from ingest_ids import memory_point_id

DIM = 4


def fake_embed(texts):
    return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def make_client(points):
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name=sleep_salience.COLLECTION_NAME,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))
    if points:
        client.upsert(collection_name=sleep_salience.COLLECTION_NAME, points=points)
    return client


def seed_points():
    hermes_src = "/Users/valx/.hermes/journal/finalized/20260701_120000_aa.jsonl"
    return [
        PointStruct(id=1, vector=[1.0, 0.0, 0.0, 0.0],
                    payload={"user_input": "first", "ai_response": "r1",
                             "source_file": hermes_src, "harness": "hermes"}),
        PointStruct(id=2, vector=[0.999, 0.032, 0.0, 0.0],   # near-dup of 1
                    payload={"user_input": "first again", "ai_response": "r2",
                             "source_file": "/Users/valx/.hermes/journal/finalized/20260702_120000_bb.jsonl",
                             "harness": "hermes"}),
        PointStruct(id=3, vector=[0.0, 0.0, 1.0, 0.0],   # orthogonal to 1 AND 2
                    payload={"user_input": "legacy", "ai_response": "r3",
                             "source_file": "/Users/valx/.claude/projects/x.jsonl"}),
    ]


def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("LAZARUS_RETRIEVAL_LOG", str(tmp_path / "retrieval.jsonl"))
    monkeypatch.setenv("LAZARUS_SLEEP_REPORT_DIR", str(tmp_path / "reports"))
    # REPORT_DIR is resolved at import time — repoint it for the test
    monkeypatch.setattr(sleep_salience, "REPORT_DIR", tmp_path / "reports")


def test_backfill_novelty_and_snapshot(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    report = sleep_salience.run(client=client, embed_fn=fake_embed)
    assert report["points_total"] == 3
    assert report["created_at_backfilled"] == 2      # both hermes points; legacy has no date
    assert report["novelty_computed"] == 3
    assert report["snapshot_written"] == 3
    points = {p.id: p.payload for p in sleep_salience.load_points(client)}
    assert points[1]["created_at"] == "2026-07-01T12:00:00"
    assert "created_at" not in points[3]
    assert points[2]["near_duplicate_of"] == 1        # 1 is prior to 2
    assert points[2]["novelty"] < 0.1
    assert points[3]["novelty"] == 1.0                # orthogonal to everything
    for pid in (1, 2, 3):
        assert "salience" in points[pid] and "salience_components" in points[pid]


def test_second_run_is_incremental(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    sleep_salience.run(client=client, embed_fn=fake_embed)
    report2 = sleep_salience.run(client=client, embed_fn=fake_embed)
    assert report2["novelty_computed"] == 0
    assert report2["created_at_backfilled"] == 0
    assert report2["snapshot_written"] == 0           # delta guard holds overnight


def test_usage_from_retrieval_log(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    log = tmp_path / "retrieval.jsonl"
    log.write_text(json.dumps({
        "ts": "2026-07-05T10:00:00+0000",
        "results": [{"id": 1}, {"id": 1}, {"id": 2}]}) + "\n")
    client = make_client(seed_points())
    report = sleep_salience.run(client=client, embed_fn=fake_embed)
    assert report["usage_updated"] == 2
    points = {p.id: p.payload for p in sleep_salience.load_points(client)}
    assert points[1]["retrieval_count"] == 2
    assert points[1]["last_accessed_at"] == "2026-07-05T10:00:00+0000"
    assert points[1]["usage_norm"] == 1.0
    assert 0.0 < points[2]["usage_norm"] < 1.0


def test_memory_requests_become_pinned_points_idempotently(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    request = {"id": "abc123", "ts": "2026-07-06T01:00:00+0000",
               "session_id": "s1", "kind": "memory",
               "content": "Valentin's birthday matters", "note": "he said so"}
    report = sleep_salience.run(requests=[request], client=client, embed_fn=fake_embed)
    assert report["requests_honored"] == 1
    assert report["points_total"] == 4
    report2 = sleep_salience.run(requests=[request], client=client, embed_fn=fake_embed)
    assert report2["points_total"] == 4               # deterministic id -> idempotent
    expected_id = memory_point_id("memory_request:abc123",
                                  "Valentin's birthday matters", "he said so")
    points = {p.id: p.payload for p in sleep_salience.load_points(client)}
    assert points[expected_id]["salience_pinned"] is True
    assert points[expected_id]["kind"] == "memory_request"
    assert points[expected_id]["created_at"] == "2026-07-06T01:00:00+0000"


def test_vocabulary_kind_requests_are_not_points(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    request = {"id": "v1", "ts": "2026-07-06T01:00:00+0000", "kind": "vocabulary",
               "content": "LOTIJ", "note": "Legion of the Infinite Jest"}
    report = sleep_salience.run(requests=[request], client=client, embed_fn=fake_embed)
    assert report["requests_honored"] == 0
    assert report["points_total"] == 3


def test_invalidate_marks_never_deletes(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    monkeypatch.setattr(sleep_salience, "LEDGER_PATH",
                        tmp_path / "invalidations.jsonl")
    client = make_client(seed_points())
    sleep_salience.run(client=client, embed_fn=fake_embed)
    count = sleep_salience.invalidate_points([2], reason="superseded in test",
                                             superseded_by=1, client=client)
    assert count == 1
    points = {p.id: p.payload for p in sleep_salience.load_points(client)}
    assert points[2]["superseded_by"] == 1
    assert points[2]["invalid_from_ts"] <= time.time()
    # still physically present (never deleted), but excluded by the filter:
    visible = client.query_points(
        collection_name=sleep_salience.COLLECTION_NAME,
        query=[0.999, 0.032, 0.0, 0.0], limit=10,
        query_filter=salience.not_invalidated_filter(time.time())).points
    assert 2 not in [h.id for h in visible]
    assert len(points) == 3


def test_report_written_to_disk(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    sleep_salience.run(client=client, embed_fn=fake_embed)
    latest = json.loads((tmp_path / "reports" / "sleep_report_latest.json").read_text())
    assert latest["points_total"] == 3
    history = (tmp_path / "reports" / "sleep_history.jsonl").read_text().strip()
    assert len(history.splitlines()) == 1


def test_dry_run_writes_nothing(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    request = {"id": "abc", "ts": "2026-07-06T01:00:00+0000", "kind": "memory",
               "content": "x", "note": ""}
    report = sleep_salience.run(requests=[request], client=client,
                                embed_fn=fake_embed, dry_run=True)
    assert report["dry_run"] is True
    assert report["requests_honored"] == 0
    points = {p.id: p.payload for p in sleep_salience.load_points(client)}
    assert all("salience" not in p for p in points.values())
    assert len(points) == 3


def test_run_custom_collection(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    client = QdrantClient(":memory:")
    for name in ("murphy_eternal", "claude_eternal"):
        client.create_collection(collection_name=name,
                                 vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))
    client.upsert(collection_name="claude_eternal", points=seed_points())
    report = sleep_salience.run(client=client, embed_fn=fake_embed,
                                collection="claude_eternal")
    assert report["collection"] == "claude_eternal"
    assert report["points_total"] == 3
    claude_points = {p.id: p.payload for p in
                     sleep_salience.load_points(client, "claude_eternal")}
    assert all("salience" in p for p in claude_points.values())
    murphy_points, _ = client.scroll(collection_name="murphy_eternal", limit=10,
                                     with_payload=True)
    assert murphy_points == []


def test_parse_journal_yields_ts():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        journal = Path(d) / "20260706_010203_ff.jsonl"
        journal.write_text(
            json.dumps({"type": "turn", "ts": "2026-07-06T01:02:03+0000",
                        "user": "u", "assistant": "a" * 30}) + "\n"
            + json.dumps({"type": "finalized", "ts": "x"}) + "\n")
        pairs = list(ingest_hermes.parse_journal(journal))
    assert len(pairs) == 1
    assert pairs[0]["ts"] == "2026-07-06T01:02:03+0000"


# --- F2 FSRS pass (observe-only) ---
import pytest


def _log_records(tmp_path, records):
    log = tmp_path / "retrieval.jsonl"
    with open(log, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def test_fsrs_fields_written_for_reviewed_points(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    _log_records(tmp_path, [
        {"ts": "2026-07-01T10:00:00+0000", "collection": "murphy_eternal",
         "results": [{"id": 1}]},
        {"ts": "2026-07-03T10:00:00+0000", "collection": "murphy_eternal",
         "results": [{"id": 1}]},
    ])
    client = make_client(seed_points())
    now = salience.parse_iso("2026-07-05T10:00:00+0000")
    report = sleep_salience.run(client=client, embed_fn=fake_embed, now=now)
    assert report["fsrs_updated"] == 1
    points = {p.id: p.payload for p in sleep_salience.load_points(client)}
    assert points[1]["stability"] > salience.INIT_STABILITY   # one real review
    expected_r = salience.fsrs_retrievability(
        2.0, points[1]["stability"])                          # 2 days since last
    assert points[1]["fsrs_retrievability"] == pytest.approx(expected_r, abs=1e-4)
    assert "fsrs_computed_at" in points[1]
    assert "stability" not in points[2]                       # never retrieved
    assert "stability" not in points[3]


def test_fsrs_second_run_is_idempotent(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    _log_records(tmp_path, [
        {"ts": "2026-07-01T10:00:00+0000", "collection": "murphy_eternal",
         "results": [{"id": 1}]},
    ])
    client = make_client(seed_points())
    now = salience.parse_iso("2026-07-05T10:00:00+0000")
    sleep_salience.run(client=client, embed_fn=fake_embed, now=now)
    report2 = sleep_salience.run(client=client, embed_fn=fake_embed, now=now)
    assert report2["fsrs_updated"] == 0                       # write rule holds


def test_fsrs_respects_collection_filter(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    _log_records(tmp_path, [
        {"ts": "2026-07-01T10:00:00+0000", "collection": "claude_eternal",
         "results": [{"id": 1}]},
    ])
    client = make_client(seed_points())
    report = sleep_salience.run(client=client, embed_fn=fake_embed)
    assert report["fsrs_updated"] == 0                        # wrong collection
    points = {p.id: p.payload for p in sleep_salience.load_points(client)}
    assert "stability" not in points[1]


def test_fsrs_multiplier_untouched_by_fsrs_fields(monkeypatch, tmp_path):
    """Observe-only pin: fsrs fields must not move the live multiplier."""
    payload = {"created_at": "2026-07-01T10:00:00+0000", "novelty": 0.5}
    now = salience.parse_iso("2026-07-05T10:00:00+0000")
    base = salience.multiplier(payload, now)
    payload.update({"stability": 9.9, "fsrs_retrievability": 0.01,
                    "fsrs_computed_at": "x"})
    assert salience.multiplier(payload, now) == base


# --- F2 invalidation ledger (self-healing marks) ---
def _ledger_env(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    monkeypatch.setattr(sleep_salience, "LEDGER_PATH",
                        tmp_path / "invalidations.jsonl")


def test_invalidate_appends_ledger_before_set_payload(monkeypatch, tmp_path):
    _ledger_env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    sleep_salience.invalidate_points([2], reason="test", superseded_by=1,
                                     client=client)
    records = [json.loads(l) for l in
               (tmp_path / "invalidations.jsonl").read_text().splitlines()]
    assert len(records) == 1
    rec = records[0]
    assert rec["collection"] == sleep_salience.COLLECTION_NAME
    assert rec["point_ids"] == [2]
    assert rec["patch"]["invalidation_reason"] == "test"
    assert rec["patch"]["superseded_by"] == 1
    assert "invalid_from_ts" in rec["patch"]


def test_ledger_write_failure_aborts_before_qdrant(monkeypatch, tmp_path):
    _ledger_env(monkeypatch, tmp_path)
    monkeypatch.setattr(sleep_salience, "LEDGER_PATH",
                        tmp_path / "no_such_dir_is_a_file" / "x.jsonl")
    (tmp_path / "no_such_dir_is_a_file").write_text("a file, not a dir")

    class MustNotWrite:
        def set_payload(self, **k):
            raise AssertionError("set_payload must not run when ledger fails")

    import pytest as _pytest
    with _pytest.raises(OSError):
        sleep_salience.invalidate_points([2], reason="x", client=MustNotWrite())


def test_sleep_reapplies_ledger_marks_after_wipe(monkeypatch, tmp_path):
    """The self-heal: a wiped mark returns at the next pass, timestamps intact."""
    _ledger_env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    sleep_salience.invalidate_points([2], reason="superseded", client=client)
    original = {p.id: p.payload for p in
                sleep_salience.load_points(client)}[2]["invalid_from_ts"]
    # simulate an unguarded writer wiping the point (fresh full upsert)
    from qdrant_client.models import PointStruct as PS
    client.upsert(collection_name=sleep_salience.COLLECTION_NAME, points=[
        PS(id=2, vector=[0.999, 0.032, 0.0, 0.0],
           payload={"user_input": "first again", "ai_response": "r2"})])
    report = sleep_salience.run(client=client, embed_fn=fake_embed)
    assert report["invalidations_reapplied"] == 1
    healed = {p.id: p.payload for p in sleep_salience.load_points(client)}[2]
    assert healed["invalid_from_ts"] == original          # verbatim timestamps
    assert healed["invalidation_reason"] == "superseded"


def test_ledger_records_filtered_by_collection_and_tolerant(monkeypatch, tmp_path):
    _ledger_env(monkeypatch, tmp_path)
    ledger = tmp_path / "invalidations.jsonl"
    ledger.write_text(
        json.dumps({"ts": "t", "collection": "other", "point_ids": [9],
                    "patch": {"invalid_from_ts": 1.0}}) + "\n"
        + "{ broken\n"
        + json.dumps({"ts": "t", "collection": sleep_salience.COLLECTION_NAME,
                      "point_ids": [2], "patch": {"invalid_from_ts": 5.0}}) + "\n"
        + json.dumps({"ts": "t", "collection": sleep_salience.COLLECTION_NAME,
                      "point_ids": [], "patch": {}}) + "\n")
    records = sleep_salience._ledger_records(sleep_salience.COLLECTION_NAME)
    assert len(records) == 1 and records[0]["point_ids"] == [2]


def test_dry_run_does_not_reapply(monkeypatch, tmp_path):
    _ledger_env(monkeypatch, tmp_path)
    client = make_client(seed_points())
    sleep_salience.invalidate_points([2], reason="x", client=client)
    report = sleep_salience.run(client=client, embed_fn=fake_embed, dry_run=True)
    assert report["invalidations_reapplied"] == 0
