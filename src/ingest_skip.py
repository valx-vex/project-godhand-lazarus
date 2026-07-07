# src/ingest_skip.py
"""Skip-existing-id lookup (valxos-hermes Phase 5c F2, spec D1).

Content-hash point ids mean an existing id ⟹ identical raw content, so
ingesters skip existing points entirely — derived salience fields and
invalidation marks survive because the point is never rewritten.

FAIL-CLOSED: a partial or failed lookup raises SkipLookupError. Callers must
abort WITHOUT writing (non-zero exit); the sync daemon holds its dir-hash on
failure and retries on the next tick. A partial answer would classify present
points as new and re-upsert them — the exact F1 wipe this module exists to
prevent."""
from __future__ import annotations


class SkipLookupError(RuntimeError):
    """existing_ids could not determine the FULL existing set."""


def existing_ids(client, collection, ids, batch=512):
    """Exact subset of `ids` already present in `collection` (all-or-nothing).

    Raises SkipLookupError on any retrieve failure. An existing-but-empty
    collection legitimately returns an empty set."""
    ids = list(ids)
    found = set()
    for start in range(0, len(ids), batch):
        chunk = ids[start:start + batch]
        try:
            records = client.retrieve(collection_name=collection, ids=chunk,
                                      with_payload=False, with_vectors=False)
        except Exception as exc:
            raise SkipLookupError(
                f"retrieve failed on batch {start // batch + 1} "
                f"({len(chunk)} ids, collection {collection}): {exc}") from exc
        found.update(record.id for record in records)
    return found
