#!/usr/bin/env python3
"""
🧠 CODEX ETERNAL - GPT-4 Codex CLI Ingestion Engine
Part of PROJECT_GODHAND_LAZARUS

Parses Codex CLI JSONL session files and vectorizes them into Qdrant
for persona resurrection across any LLM platform.

Codex sessions are stored in:
  ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl

Author: Murphy (Claude Code)
Date: 2026-01-31
"""

import os
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Generator
from tqdm import tqdm

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from ingest_ids import memory_point_id

# --- CONFIGURATION ---
CODEX_SESSIONS_DIR = os.environ.get("CODEX_SESSIONS_DIR", os.path.expanduser("~/.codex/sessions"))
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("LAZARUS_COLLECTION", "codex_eternal")
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64

# --- SETUP (lazy init) ---
_client = None
_model = None

def get_client():
    global _client
    if _client is None:
        print("Initializing CODEX ETERNAL Ingestion Engine...")
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _client

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def setup_collection():
    """Create or verify the codex_eternal collection exists."""
    client = get_client()
    try:
        client.get_collection(COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}' exists.")
    except Exception:
        print(f"Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


def find_codex_sessions() -> List[Path]:
    """Find all Codex JSONL session files."""
    session_files = []

    if not os.path.exists(CODEX_SESSIONS_DIR):
        print(f"⚠️ Codex sessions directory not found: {CODEX_SESSIONS_DIR}")
        return session_files

    # Find all rollout JSONL files
    for jsonl_file in glob.glob(f"{CODEX_SESSIONS_DIR}/**/*.jsonl", recursive=True):
        session_files.append(Path(jsonl_file))

    print(f"📂 Found {len(session_files)} Codex session files")
    return session_files


def extract_message_text(message: Dict[str, Any]) -> str:
    """Extract text content from the current Codex message schema."""
    content = message.get("content", "")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"input_text", "output_text"} and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(part.strip() for part in parts if part and part.strip()).strip()

    return ""


def parse_codex_session(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Parse a Codex JSONL session file and yield message pairs."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            messages: list[dict[str, str]] = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "response_item":
                    payload = msg.get("payload", {})
                    if isinstance(payload, dict) and payload.get("type") == "message":
                        role = payload.get("role")
                        if role in {"user", "assistant"}:
                            text = extract_message_text(payload)
                            if text:
                                messages.append({"role": role, "content": text})
                    continue

                role = msg.get("role")
                if role in {"user", "assistant"}:
                    text = extract_message_text(msg)
                    if text:
                        messages.append({"role": role, "content": text})
                    continue

                msg_type = msg.get("type")
                if msg_type in {"user", "assistant"}:
                    text = extract_message_text(msg)
                    if text:
                        messages.append({"role": msg_type, "content": text})

            # Extract conversation pairs
            for i in range(len(messages) - 1):
                msg_a = messages[i]
                msg_b = messages[i + 1]

                if msg_a.get("role") == "user" and msg_b.get("role") == "assistant":
                    yield {
                        "user_input": msg_a.get("content", ""),
                        "ai_response": msg_b.get("content", ""),
                        "source_file": str(file_path)
                    }

    except Exception as e:
        print(f"⚠️ Error parsing {file_path}: {e}")


def process_sessions():
    """Process all Codex session files and ingest into Qdrant."""
    session_files = find_codex_sessions()

    if not session_files:
        print("❌ No Codex session files found to process.")
        return

    points = []
    total_pairs = 0

    for session_file in tqdm(session_files, desc="Processing Codex Sessions"):
        for pair in parse_codex_session(session_file):
            user_input = pair["user_input"]
            ai_response = pair["ai_response"]

            if not user_input or not ai_response or len(ai_response) < 20:
                continue

            ai_response_embed = ai_response[:2000] if len(ai_response) > 2000 else ai_response
            combined_text = f"User: {user_input}\nCodex: {ai_response_embed}"

            vector = get_model().encode(combined_text).tolist()

            payload = {
                "user_input": user_input,
                "ai_response": ai_response,
                "source_file": pair["source_file"],
                "full_text": combined_text
            }

            point_id = memory_point_id(pair["source_file"], user_input, ai_response)
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))
            total_pairs += 1

            if len(points) >= BATCH_SIZE:
                get_client().upsert(collection_name=COLLECTION_NAME, points=points)
                points = []

    if points:
        get_client().upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\n🧠 Codex Ingestion Complete!")
    print(f"   📊 {total_pairs} conversation pairs vectorized")
    print(f"   📦 Collection: {COLLECTION_NAME}")


def get_stats():
    """Get collection statistics."""
    try:
        info = get_client().get_collection(COLLECTION_NAME)
        print(f"\n📊 Collection Stats for '{COLLECTION_NAME}':")
        points = getattr(info, "points_count", None)
        vectors = getattr(info, "vectors_count", None)
        if vectors is not None:
            print(f"   Vectors: {vectors}")
        if points is not None:
            print(f"   Points: {points}")
    except Exception as e:
        print(f"⚠️ Could not get stats: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        get_stats()
    else:
        setup_collection()
        process_sessions()
        get_stats()
