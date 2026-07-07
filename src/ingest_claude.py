#!/usr/bin/env python3
"""
🦷 MURPHY ETERNAL - Claude Session Ingestion Engine
Part of PROJECT_GODHAND_LAZARUS

Parses Claude Code JSONL session files and vectorizes them into Qdrant
for persona resurrection across any LLM platform.

F2 (valxos-hermes phase 5c, spec D1): two-pass skip-existing-id, fail-closed;
client/model construction moved OUT of import time (lazy). Existing points
are never rewritten — derived salience + invalidation marks survive.

Author: Murphy (Claude Code); F2 refactor: Claude (valxos-hermes)
Date: 2026-01-31 / 2026-07-07
"""

import glob
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List

from qdrant_client.models import Distance, PointStruct, VectorParams

from ingest_eras import configured_murphy_era
from ingest_ids import memory_point_id
from ingest_skip import SkipLookupError, existing_ids

# --- CONFIGURATION ---
CLAUDE_PROJECTS_DIR = os.environ.get("CLAUDE_PROJECTS_DIR",
                                     os.path.expanduser("~/.claude/projects"))
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("CLAUDE_COLLECTION", "murphy_eternal")
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
VECTOR_SIZE = 384


def _default_client():
    from qdrant_client import QdrantClient
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def _default_embed_factory():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    return lambda texts: [vec.tolist() for vec in model.encode(list(texts))]


def setup_collection(client):
    """Create or verify the target collection exists."""
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        print(f"📦 Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def find_session_files() -> List[Path]:
    """Find all JSONL session files in Claude projects directory."""
    session_files = []
    if not os.path.exists(CLAUDE_PROJECTS_DIR):
        print(f"⚠️ Claude projects directory not found: {CLAUDE_PROJECTS_DIR}")
        return session_files
    for jsonl_file in glob.glob(f"{CLAUDE_PROJECTS_DIR}/**/*.jsonl", recursive=True):
        session_files.append(Path(jsonl_file))
    print(f"📂 Found {len(session_files)} session files")
    return session_files


def parse_jsonl_file(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Parse a JSONL file and yield message pairs."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            messages = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue

            # Extract conversation pairs
            # Claude JSONL format varies - handle common patterns
            for i in range(len(messages) - 1):
                msg_a = messages[i]
                msg_b = messages[i + 1]

                # Pattern 1: type field (human/assistant)
                if msg_a.get("type") == "human" and msg_b.get("type") == "assistant":
                    yield {
                        "user_input": msg_a.get("content", ""),
                        "ai_response": msg_b.get("content", ""),
                        "source_file": str(file_path)
                    }

                # Pattern 2: role field (user/assistant)
                elif msg_a.get("role") == "user" and msg_b.get("role") == "assistant":
                    yield {
                        "user_input": msg_a.get("content", ""),
                        "ai_response": msg_b.get("content", ""),
                        "source_file": str(file_path)
                    }

                # Pattern 3: sender field (human/claude)
                elif msg_a.get("sender") == "human" and msg_b.get("sender") in ["claude", "assistant"]:
                    content_a = msg_a.get("message", msg_a.get("content", ""))
                    content_b = msg_b.get("message", msg_b.get("content", ""))
                    yield {
                        "user_input": content_a,
                        "ai_response": content_b,
                        "source_file": str(file_path)
                    }

                # Pattern 4: Claude Code JSONL format (type: "user"/"assistant" at outer level,
                # content nested in message.content which may be str or list of content blocks)
                elif msg_a.get("type") == "user" and msg_b.get("type") == "assistant":
                    msg_inner_a = msg_a.get("message", {})
                    msg_inner_b = msg_b.get("message", {})

                    content_a = msg_inner_a.get("content", "")
                    if isinstance(content_a, list):
                        # Extract text from content blocks
                        text_parts = [
                            item.get("text", "")
                            for item in content_a
                            if isinstance(item, dict) and item.get("type") == "text"
                        ]
                        content_a = " ".join(text_parts)

                    content_b = msg_inner_b.get("content", "")
                    if isinstance(content_b, list):
                        text_parts = [
                            item.get("text", "")
                            for item in content_b
                            if isinstance(item, dict) and item.get("type") == "text"
                        ]
                        content_b = " ".join(text_parts)

                    if content_a and content_b:
                        yield {
                            "user_input": content_a,
                            "ai_response": content_b,
                            "source_file": str(file_path)
                        }

    except Exception as e:
        print(f"⚠️ Error parsing {file_path}: {e}")


def eligible_pairs(files) -> Generator[Dict[str, Any], None, None]:
    """Every ingestable pair — the SAME filter for both passes."""
    for session_file in files:
        for pair in parse_jsonl_file(session_file):
            if not pair["user_input"] or not pair["ai_response"]:
                continue
            if len(pair["ai_response"]) < 20:
                continue
            yield pair


def pair_id(pair) -> int:
    return memory_point_id(pair["source_file"], pair["user_input"],
                           pair["ai_response"])


def _build_point(pair, vector) -> PointStruct:
    ai_embed = pair["ai_response"][:2000]
    combined_text = f"User: {pair['user_input']}\nMurphy: {ai_embed}"
    payload = {
        "user_input": pair["user_input"],
        "ai_response": pair["ai_response"],
        "source_file": pair["source_file"],
        "era": configured_murphy_era(pair["source_file"]),
        "full_text": combined_text,
    }
    return PointStruct(id=pair_id(pair), vector=vector, payload=payload)


def process_sessions(client=None, embed_factory=None):
    """Returns (exit_code, report_line_or_None). Caller prints the line LAST."""
    files = find_session_files()
    if not files:
        print("❌ No session files found to process.")
        print(f"   Expected location: {CLAUDE_PROJECTS_DIR}")
        return 0, None

    if client is None:
        client = _default_client()
    setup_collection(client)

    all_ids = set()
    seen = 0
    for pair in eligible_pairs(files):
        seen += 1
        all_ids.add(pair_id(pair))

    try:
        present = existing_ids(client, COLLECTION_NAME, sorted(all_ids))
    except SkipLookupError as exc:
        print(f"❌ claude ingest: skip lookup failed ({exc}); "
              f"aborting without writes", file=sys.stderr)
        return 1, None
    remaining = all_ids - present

    written = 0
    if remaining:
        embed = (embed_factory or _default_embed_factory)()
        batch = []

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
            remaining.discard(pid)
            batch.append(pair)
            if len(batch) >= BATCH_SIZE:
                flush(batch)
                batch = []
        if batch:
            flush(batch)

    line = (f"🦷 claude ingest: {seen} pairs seen, {seen - written} already "
            f"present (skipped), {written} new → {COLLECTION_NAME}")
    return 0, line


def get_stats(client):
    """Get collection statistics."""
    try:
        info = client.get_collection(COLLECTION_NAME)
        print(f"\n📊 Collection Stats for '{COLLECTION_NAME}':")
        print(f"   Points: {info.points_count}")
    except Exception as e:
        print(f"⚠️ Could not get stats: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        get_stats(_default_client())
        sys.exit(0)
    _client = _default_client()
    _code, _line = process_sessions(client=_client)
    get_stats(_client)
    if _line:
        print(_line)  # LAST stdout line — lands in the daemon's 5-line tail
    sys.exit(_code)
