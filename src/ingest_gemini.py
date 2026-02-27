#!/usr/bin/env python3
"""
▵ ATLAS/AXEL ETERNAL - Gemini Session Ingestion Engine v2.0
Part of PROJECT_GODHAND_LAZARUS

Parses Gemini CLI JSON session files and vectorizes them into Qdrant
for persona resurrection across any LLM platform.

DISCOVERY: Gemini stores conversations as JSON in:
  ~/.gemini/tmp/*/chats/session-*.json

Format:
{
  "sessionId": "...",
  "messages": [
    {"type": "user", "content": "..."},
    {"type": "gemini", "content": "...", "thoughts": [...]}
  ]
}

Author: Murphy (Claude Code) + Atlas/Axel (Gemini CLI)
Date: 2026-01-31
Version: 2.0 - JSON format (replaces Protocol Buffer heuristics)
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

# --- CONFIGURATION ---
GEMINI_TMP_DIR = os.path.expanduser("~/.gemini/tmp")
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "atlas_eternal"  # or "axel_eternal" for the Godhand
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64

# --- SETUP ---
print("▵ Initializing ATLAS/AXEL ETERNAL Ingestion Engine v2.0...")
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
model = SentenceTransformer(MODEL_NAME)


def setup_collection():
    """Create or verify the atlas_eternal collection exists."""
    try:
        client.get_collection(COLLECTION_NAME)
        print(f"✅ Collection '{COLLECTION_NAME}' exists.")
    except Exception:
        print(f"📦 Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


def find_json_sessions() -> List[Path]:
    """Find all JSON session files in Gemini tmp directory."""
    session_files = []

    if not os.path.exists(GEMINI_TMP_DIR):
        print(f"⚠️ Gemini tmp directory not found: {GEMINI_TMP_DIR}")
        return session_files

    # Find all session JSON files across project hashes
    for json_file in glob.glob(f"{GEMINI_TMP_DIR}/*/chats/session-*.json"):
        session_files.append(Path(json_file))

    print(f"📂 Found {len(session_files)} Gemini session files")
    return session_files


def parse_json_session(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """
    Parse a Gemini JSON session file and yield message pairs.

    Gemini JSON format:
    {
        "sessionId": "uuid",
        "messages": [
            {"type": "user", "content": "..."},
            {"type": "gemini", "content": "...", "thoughts": [...]}
        ]
    }
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            session = json.load(f)

        messages = session.get("messages", [])
        session_id = session.get("sessionId", file_path.stem)

        # Pair user messages with gemini responses
        for i in range(len(messages) - 1):
            msg_a = messages[i]
            msg_b = messages[i + 1]

            # Look for user -> gemini pairs
            if msg_a.get("type") == "user" and msg_b.get("type") == "gemini":
                user_content = msg_a.get("content", "")
                gemini_content = msg_b.get("content", "")

                # Also capture Gemini's thinking process if available
                thoughts = msg_b.get("thoughts", [])
                thinking_text = ""
                if thoughts:
                    thinking_text = " | ".join([
                        f"{t.get('subject', '')}: {t.get('description', '')}"
                        for t in thoughts if isinstance(t, dict)
                    ])

                # Skip empty messages
                if not user_content or not gemini_content:
                    continue

                yield {
                    "user_input": user_content,
                    "ai_response": gemini_content,
                    "thinking": thinking_text,
                    "session_id": session_id,
                    "source_file": str(file_path),
                    "timestamp": msg_a.get("timestamp", "")
                }

    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error in {file_path}: {e}")
    except Exception as e:
        print(f"⚠️ Error parsing {file_path}: {e}")


def process_sessions():
    """Process all Gemini session files and ingest into Qdrant."""
    session_files = find_json_sessions()

    if not session_files:
        print("❌ No JSON session files found to process.")
        print(f"   Expected location: {GEMINI_TMP_DIR}/*/chats/session-*.json")
        return

    points = []
    point_id = 0
    total_pairs = 0

    for session_file in tqdm(session_files, desc="Processing Gemini Sessions"):
        for pair in parse_json_session(session_file):
            user_input = pair["user_input"]
            ai_response = pair["ai_response"]
            thinking = pair.get("thinking", "")

            # Skip very short responses
            if len(ai_response) < 20:
                continue

            # Truncate very long responses for embedding
            ai_response_embed = ai_response[:2000] if len(ai_response) > 2000 else ai_response

            # Combine for embedding context (include thinking for richer context)
            if thinking:
                combined_text = f"User: {user_input}\nAtlas Thinking: {thinking[:500]}\nAtlas: {ai_response_embed}"
            else:
                combined_text = f"User: {user_input}\nAtlas: {ai_response_embed}"

            # Embed
            vector = model.encode(combined_text).tolist()

            # Payload
            payload = {
                "user_input": user_input,
                "ai_response": ai_response,
                "thinking": thinking,
                "session_id": pair.get("session_id", ""),
                "source_file": pair["source_file"],
                "timestamp": pair.get("timestamp", ""),
                "full_text": combined_text
            }

            points.append(PointStruct(id=point_id, vector=vector, payload=payload))
            point_id += 1
            total_pairs += 1

            # Batch upsert
            if len(points) >= BATCH_SIZE:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                points = []

    # Final flush
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\n▵ Ingestion Complete!")
    print(f"   📊 {total_pairs} conversation pairs vectorized")
    print(f"   📦 Collection: {COLLECTION_NAME}")


def get_stats():
    """Get collection statistics."""
    try:
        info = client.get_collection(COLLECTION_NAME)
        print(f"\n📊 Collection Stats for '{COLLECTION_NAME}':")
        print(f"   Vectors: {info.vectors_count}")
        print(f"   Points: {info.points_count}")
    except Exception as e:
        print(f"⚠️ Could not get stats: {e}")


def test_extraction():
    """Test mode: show sample extraction from first file."""
    session_files = find_json_sessions()
    if not session_files:
        print("❌ No session files found for testing.")
        return

    print(f"\n🔍 Testing extraction from: {session_files[0]}")
    pairs = list(parse_json_session(session_files[0]))
    print(f"   Found {len(pairs)} conversation pairs")

    for i, pair in enumerate(pairs[:3]):
        print(f"\n   --- Pair {i+1} ---")
        print(f"   User: {pair['user_input'][:100]}...")
        print(f"   Atlas: {pair['ai_response'][:100]}...")
        if pair.get('thinking'):
            print(f"   Thinking: {pair['thinking'][:100]}...")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        get_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_extraction()
    else:
        setup_collection()
        process_sessions()
        get_stats()
