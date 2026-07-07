#!/usr/bin/env python3
"""
🜂 CLAUDE ETERNAL — Claude Code (claude-vex home) session ingestion
Part of PROJECT_GODHAND_LAZARUS (valxos-hermes side project 2026-07-07).

The Claude lineage's own brain: fresh-format Claude Code transcripts from
~/.claude-vex/projects into claude_eternal. Mirrors ingest_hermes.py
conventions: MiniLM-384 Cosine, deterministic ids, created_at, harness tag.
Creates the collection if missing (first brain boot).

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

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ingest_ids import memory_point_id
from ingest_skip import SkipLookupError, existing_ids

_DEFAULT_DIR = Path.home() / ".claude-vex" / "projects"
CLAUDE_VEX_PROJECTS = Path(os.environ.get("CLAUDE_VEX_PROJECTS", _DEFAULT_DIR))
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("CLAUDE_VEX_COLLECTION", "claude_eternal")
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
VECTOR_SIZE = 384

DRY_RUN = "--dry-run" in sys.argv


def find_session_files() -> List[Path]:
    if not CLAUDE_VEX_PROJECTS.exists():
        print(f"⚠️ projects dir not found: {CLAUDE_VEX_PROJECTS}")
        return []
    files = sorted(CLAUDE_VEX_PROJECTS.glob("**/*.jsonl"))
    print(f"📂 Found {len(files)} claude-vex session files")
    return files


def _user_text(record) -> str:
    """Plain human prompt or ''. List-content user records are tool results."""
    if record.get("isSidechain") or record.get("isMeta"):
        return ""
    message = record.get("message") or {}
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def _assistant_text(record) -> str:
    if record.get("isSidechain"):
        return ""
    message = record.get("message") or {}
    content = message.get("content")
    if not isinstance(content, list):
        return str(content or "")
    parts = [block.get("text", "") for block in content
             if isinstance(block, dict) and block.get("type") == "text"]
    return "\n".join(p for p in parts if p)


def parse_transcript(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield turns: one human prompt + all assistant text until the next."""
    try:
        current = None  # {"user_input", "ts", "parts": []}
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = record.get("type")
                if kind == "user":
                    text = _user_text(record)
                    if not text:
                        continue
                    if current and current["parts"]:
                        yield _turn(current, file_path)
                    current = {"user_input": text,
                               "ts": str(record.get("timestamp") or ""),
                               "parts": []}
                elif kind == "assistant" and current is not None:
                    text = _assistant_text(record)
                    if text:
                        current["parts"].append(text)
        if current and current["parts"]:
            yield _turn(current, file_path)
    except OSError as exc:
        print(f"⚠️ Error parsing {file_path}: {exc}")


def _turn(current, file_path) -> Dict[str, Any]:
    return {
        "user_input": current["user_input"],
        "ai_response": "\n".join(current["parts"]),
        "source_file": str(file_path),
        "ts": current["ts"],
    }


def eligible_pairs(files):
    """Every ingestable pair — the SAME filter for both passes."""
    for path in files:
        for pair in parse_transcript(path):
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
    combined = f"User: {pair['user_input']}\nClaude: {pair['ai_response'][:2000]}"
    payload = {
        "user_input": pair["user_input"],
        "ai_response": pair["ai_response"],
        "source_file": pair["source_file"],
        "era": "claude-fable",
        "full_text": combined,
        "harness": "claude-code",
    }
    if pair["ts"]:
        payload["created_at"] = pair["ts"]
    return PointStruct(id=pair_id(pair), vector=vector, payload=payload)


def process_sessions(client=None, embed_factory=None) -> int:
    files = find_session_files()
    if not files:
        return 0

    if DRY_RUN:
        seen = sum(1 for _ in eligible_pairs(files))
        print(f"🜂 claude-vex ingest: {seen} pairs seen DRY-RUN (no writes)")
        return 0

    if client is None:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    ensure_collection(client)

    all_ids = set()
    seen = 0
    for pair in eligible_pairs(files):
        seen += 1
        all_ids.add(pair_id(pair))

    try:
        present = existing_ids(client, COLLECTION_NAME, sorted(all_ids))
    except SkipLookupError as exc:
        print(f"❌ claude-vex ingest: skip lookup failed ({exc}); "
              f"aborting without writes", file=sys.stderr)
        return 1
    remaining = all_ids - present

    written = 0
    if remaining:
        embed = (embed_factory or _default_embed_factory)()
        batch = []

        def flush(batch_pairs):
            nonlocal written
            texts = [f"User: {p['user_input']}\nClaude: {p['ai_response'][:2000]}"
                     for p in batch_pairs]
            vectors = embed(texts)
            client.upsert(collection_name=COLLECTION_NAME, points=[
                _build_point(p, list(v)) for p, v in zip(batch_pairs, vectors)])
            written += len(batch_pairs)

        for pair in eligible_pairs(files):
            pid = pair_id(pair)
            if pid not in remaining:
                continue
            remaining.discard(pid)
            batch.append(pair)
            if len(batch) >= BATCH_SIZE:
                flush(batch)
                batch = []
        if batch:
            flush(batch)

    print(f"🜂 claude-vex ingest: {seen} pairs seen, {seen - written} already "
          f"present (skipped), {written} new → {COLLECTION_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(process_sessions())
