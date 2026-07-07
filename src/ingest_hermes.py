#!/usr/bin/env python3
"""
🜂 MURPHY ETERNAL — Hermes Session Ingestion Engine
Part of PROJECT_GODHAND_LAZARUS (valxos-hermes Phase 5a; F2 skip-existing 5c)

Reads valxos-memory finalized journals (JSONL "turn" records carrying both
sides of a turn) and vectorizes them into murphy_eternal — one brain, two
bodies. Mirrors ingest_claude.py conventions exactly: MiniLM-384 Cosine,
deterministic point ids, same pair filters, same payload shape (+ harness).

F2 (spec D1): two-pass skip-existing-id. Pass 1 streams ids only; existing
points are NEVER rewritten (derived salience + invalidation marks survive by
construction). Fail-CLOSED: if the existing-id lookup fails, exit non-zero
without writing — the sync daemon retries on its next tick.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List

from qdrant_client.models import Distance, PointStruct, VectorParams

from ingest_eras import configured_murphy_era
from ingest_ids import memory_point_id
from ingest_skip import SkipLookupError, existing_ids
from salience import created_at_from_source

# --- CONFIGURATION ---
_DEFAULT_DIRS = [
    Path.home() / ".hermes" / "journal" / "finalized",
    Path.home() / ".hermes" / "profiles" / "murphy" / "journal" / "finalized",
]
HERMES_JOURNAL_DIRS = [
    Path(p) for p in os.environ.get("HERMES_JOURNAL_DIRS", "").split(":") if p
] or _DEFAULT_DIRS
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("HERMES_COLLECTION", "murphy_eternal")
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
VECTOR_SIZE = 384

DRY_RUN = "--dry-run" in sys.argv


def find_journal_files() -> List[Path]:
    files: List[Path] = []
    for directory in HERMES_JOURNAL_DIRS:
        if directory.exists():
            files.extend(sorted(directory.glob("*.jsonl")))
    print(f"📂 Found {len(files)} finalized Hermes journals")
    return files


def parse_journal(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield (user, assistant) pairs from valxos-memory journal turn records."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "turn":
                    continue  # meta / user_pending / finalized
                user = str(rec.get("user", ""))
                assistant = str(rec.get("assistant", ""))
                if user and assistant:
                    yield {
                        "user_input": user,
                        "ai_response": assistant,
                        "source_file": str(file_path),
                        "ts": str(rec.get("ts") or ""),
                    }
    except OSError as e:
        print(f"⚠️ Error parsing {file_path}: {e}")


def eligible_pairs(files) -> Generator[Dict[str, Any], None, None]:
    """Every ingestable pair — the SAME filter for both passes."""
    for journal in files:
        for pair in parse_journal(journal):
            if len(pair["ai_response"]) < 20:
                continue
            yield pair


def pair_id(pair) -> int:
    return memory_point_id(pair["source_file"], pair["user_input"],
                           pair["ai_response"])


def ensure_collection(client) -> None:
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE))
        print(f"🜂 Created collection {COLLECTION_NAME} ({VECTOR_SIZE}d Cosine)")


def _default_embed_factory():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    return lambda texts: [vec.tolist() for vec in model.encode(list(texts))]


def _build_point(pair, vector) -> PointStruct:
    payload = {
        "user_input": pair["user_input"],
        "ai_response": pair["ai_response"],
        "source_file": pair["source_file"],
        "era": configured_murphy_era(pair["source_file"]),
        "full_text": f"User: {pair['user_input']}\nMurphy: {pair['ai_response'][:2000]}",
        "harness": "hermes",
    }
    created = pair.get("ts") or created_at_from_source(pair["source_file"])
    if created:
        payload["created_at"] = created
    return PointStruct(id=pair_id(pair), vector=vector, payload=payload)


def process_sessions(client=None, embed_factory=None) -> int:
    files = find_journal_files()
    if not files:
        print("❌ No finalized Hermes journals found.")
        return 0

    if DRY_RUN:
        seen = sum(1 for _ in eligible_pairs(files))
        print(f"🜂 hermes ingest: {seen} pairs seen DRY-RUN (no writes)")
        return 0

    if client is None:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    ensure_collection(client)

    # Pass 1: ids only — no text retained, no model loaded.
    all_ids = set()
    seen = 0
    for pair in eligible_pairs(files):
        seen += 1
        all_ids.add(pair_id(pair))

    try:
        present = existing_ids(client, COLLECTION_NAME, sorted(all_ids))
    except SkipLookupError as exc:
        print(f"❌ hermes ingest: skip lookup failed ({exc}); "
              f"aborting without writes", file=sys.stderr)
        return 1
    remaining = all_ids - present

    # Pass 2: embed + upsert ONLY new ids (model loads lazily).
    written = 0
    if remaining:
        embed = (embed_factory or _default_embed_factory)()
        batch: List[Dict[str, Any]] = []

        def flush(batch_pairs):
            nonlocal written
            texts = [f"User: {p['user_input']}\nMurphy: {p['ai_response'][:2000]}"
                     for p in batch_pairs]
            vectors = embed(texts)
            client.upsert(collection_name=COLLECTION_NAME, points=[
                _build_point(p, list(v)) for p, v in zip(batch_pairs, vectors)])
            written += len(batch_pairs)

        for pair in eligible_pairs(files):
            pid = pair_id(pair)
            if pid not in remaining:
                continue
            remaining.discard(pid)  # duplicate content in corpus: embed once
            batch.append(pair)
            if len(batch) >= BATCH_SIZE:
                flush(batch)
                batch = []
        if batch:
            flush(batch)

    print(f"🜂 hermes ingest: {seen} pairs seen, {seen - written} already present "
          f"(skipped), {written} new → {COLLECTION_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(process_sessions())
