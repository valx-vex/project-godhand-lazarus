#!/usr/bin/env python3
"""
🦷 MURPHY ETERNAL - Claude Session Ingestion Engine
Part of PROJECT_GODHAND_LAZARUS

Parses Claude Code JSONL session files and vectorizes them into Qdrant
for persona resurrection across any LLM platform.

Author: Murphy (Claude Code)
Date: 2026-01-31
"""

import json
import os
import glob
from pathlib import Path
from typing import List, Dict, Any, Generator
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from ingest_eras import configured_murphy_era
from ingest_ids import memory_point_id

# --- CONFIGURATION ---
CLAUDE_PROJECTS_DIR = os.environ.get("CLAUDE_PROJECTS_DIR", os.path.expanduser("~/.claude/projects"))
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = "murphy_eternal"
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64

# --- SETUP ---
print("🦷 Initializing MURPHY ETERNAL Ingestion Engine...")
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
model = SentenceTransformer(MODEL_NAME)


def setup_collection():
    """Create or verify the murphy_eternal collection exists."""
    try:
        client.get_collection(COLLECTION_NAME)
        print(f"✅ Collection '{COLLECTION_NAME}' exists.")
    except Exception:
        print(f"📦 Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


def find_session_files() -> List[Path]:
    """Find all JSONL session files in Claude projects directory."""
    session_files = []

    if not os.path.exists(CLAUDE_PROJECTS_DIR):
        print(f"⚠️ Claude projects directory not found: {CLAUDE_PROJECTS_DIR}")
        return session_files

    # Claude stores sessions in nested project directories
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


def process_sessions():
    """Process all Claude session files and ingest into Qdrant."""
    session_files = find_session_files()

    if not session_files:
        print("❌ No session files found to process.")
        print(f"   Expected location: {CLAUDE_PROJECTS_DIR}")
        return

    points = []
    total_pairs = 0

    for session_file in tqdm(session_files, desc="Processing Sessions"):
        for pair in parse_jsonl_file(session_file):
            user_input = pair["user_input"]
            ai_response = pair["ai_response"]

            # Skip empty or very short responses
            if not user_input or not ai_response or len(ai_response) < 20:
                continue

            # Truncate very long responses for embedding
            if len(ai_response) > 2000:
                ai_response_embed = ai_response[:2000]
            else:
                ai_response_embed = ai_response

            # Combine for embedding context
            combined_text = f"User: {user_input}\nMurphy: {ai_response_embed}"

            # Embed
            vector = model.encode(combined_text).tolist()

            # Payload
            payload = {
                "user_input": user_input,
                "ai_response": ai_response,
                "source_file": pair["source_file"],
                "era": configured_murphy_era(pair["source_file"]),
                "full_text": combined_text
            }

            point_id = memory_point_id(
                pair["source_file"],
                user_input,
                ai_response,
            )
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))
            total_pairs += 1

            # Batch upsert
            if len(points) >= BATCH_SIZE:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                points = []

    # Final flush
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\n🦷 Ingestion Complete!")
    print(f"   📊 {total_pairs} conversation pairs vectorized")
    print(f"   📦 Collection: {COLLECTION_NAME}")


def get_stats():
    """Get collection statistics."""
    try:
        info = client.get_collection(COLLECTION_NAME)
        print(f"\n📊 Collection Stats for '{COLLECTION_NAME}':")
        print(f"   Points: {info.points_count}")
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
