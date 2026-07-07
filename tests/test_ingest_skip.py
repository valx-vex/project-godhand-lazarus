# tests/test_ingest_skip.py
"""All-or-nothing existing-id lookup (F2 D1). :memory: Qdrant + raising stubs."""
import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ingest_skip
from ingest_skip import SkipLookupError, existing_ids

COLL = "f2_test"


def make_client(ids):
    client = QdrantClient(":memory:")
    client.create_collection(collection_name=COLL,
                             vectors_config=VectorParams(size=4, distance=Distance.COSINE))
    if ids:
        client.upsert(collection_name=COLL, points=[
            PointStruct(id=i, vector=[1.0, 0.0, 0.0, 0.0], payload={"n": i})
            for i in ids])
    return client


class RaisingClient:
    """retrieve() raises from call number `fail_at` (1-based) onward."""
    def __init__(self, fail_at=1):
        self.calls = 0
        self.fail_at = fail_at

    def retrieve(self, collection_name, ids, with_payload, with_vectors):
        self.calls += 1
        if self.calls >= self.fail_at:
            raise RuntimeError("qdrant blip")
        return [type("P", (), {"id": i})() for i in ids]


def test_found_and_missing_split():
    client = make_client([1, 2, 3])
    assert existing_ids(client, COLL, [1, 3, 99]) == {1, 3}


def test_empty_ids_no_calls():
    class NeverCall:
        def retrieve(self, *a, **k):
            raise AssertionError("must not be called")
    assert existing_ids(NeverCall(), COLL, []) == set()


def test_empty_collection_is_not_an_error():
    client = make_client([])
    assert existing_ids(client, COLL, [1, 2]) == set()


def test_multiple_batches():
    client = make_client(list(range(1, 8)))
    got = existing_ids(client, COLL, list(range(1, 12)), batch=3)
    assert got == set(range(1, 8))


def test_first_batch_failure_raises():
    with pytest.raises(SkipLookupError):
        existing_ids(RaisingClient(fail_at=1), COLL, [1, 2, 3], batch=2)


def test_later_batch_failure_raises_all_or_nothing():
    """The reviewed trap: a partial answer must NEVER be returned."""
    with pytest.raises(SkipLookupError):
        existing_ids(RaisingClient(fail_at=2), COLL, [1, 2, 3, 4, 5], batch=2)


def test_batch_size_respected():
    client = RaisingClient(fail_at=99)
    existing_ids(client, COLL, list(range(10)), batch=4)
    assert client.calls == 3  # 4 + 4 + 2
