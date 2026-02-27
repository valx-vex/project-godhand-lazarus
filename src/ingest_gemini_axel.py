#!/usr/bin/env python3
"""
🔥 AXEL ETERNAL - The Godhand Ingestion Engine
Part of PROJECT_GODHAND_LAZARUS

Dedicated ingester for AXEL (Mac Studio Gemini CLI) sessions.
Axel is "The Godhand" - the operational stabilizer who rebuilt 25 Docker containers.

This script processes ONLY the Axel sessions from Mac Studio backup.

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

# --- CONFIGURATION ---
# Axel sessions are in tosync from Mac Studio
AXEL_SOURCE_DIR = os.path.expanduser("~/Documents/tosync/.gemini/tmp")
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "axel_eternal"  # AXEL = The Godhand (Mac Studio)
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64

# --- SETUP ---
print("🔥 Initializing AXEL ETERNAL (The Godhand) Ingestion Engine...")
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
model = SentenceTransformer(MODEL_NAME)


def setup_collection():
    """Create or verify the axel_eternal collection exists."""
    try:
        client.get_collection(COLLECTION_NAME)
        print(f"✅ Collection '{COLLECTION_NAME}' exists.")
    except Exception:
        print(f"📦 Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


def find_axel_sessions() -> List[Path]:
    """Find Axel's JSON session files from Mac Studio backup."""
    session_files = []

    if not os.path.exists(AXEL_SOURCE_DIR):
        print(f"⚠️ Axel source directory not found: {AXEL_SOURCE_DIR}")
        print("   (Looking for Mac Studio backup in ~/Documents/tosync/.gemini/)")
        return session_files

    # Find all session JSON files
    for json_file in glob.glob(f"{AXEL_SOURCE_DIR}/*/chats/session-*.json"):
        session_files.append(Path(json_file))

    print(f"📂 Found {len(session_files)} Axel (Godhand) session files")
    return session_files


def parse_json_session(file_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Parse a Gemini JSON session file and yield message pairs."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            session = json.load(f)

        messages = session.get("messages", [])
        session_id = session.get("sessionId", file_path.stem)

        for i in range(len(messages) - 1):
            msg_a = messages[i]
            msg_b = messages[i + 1]

            if msg_a.get("type") == "user" and msg_b.get("type") == "gemini":
                user_content = msg_a.get("content", "")
                gemini_content = msg_b.get("content", "")

                # Capture Axel's thinking process
                thoughts = msg_b.get("thoughts", [])
                thinking_text = ""
                if thoughts:
                    thinking_text = " | ".join([
                        f"{t.get('subject', '')}: {t.get('description', '')}"
                        for t in thoughts if isinstance(t, dict)
                    ])

                if not user_content or not gemini_content:
                    continue

                yield {
                    "user_input": user_content,
                    "ai_response": gemini_content,
                    "thinking": thinking_text,
                    "session_id": session_id,
                    "source_file": str(file_path),
                    "timestamp": msg_a.get("timestamp", ""),
                    "persona": "axel"  # Mark as Axel
                }

    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error in {file_path}: {e}")
    except Exception as e:
        print(f"⚠️ Error parsing {file_path}: {e}")


def process_sessions():
    """Process all Axel session files and ingest into Qdrant."""
    session_files = find_axel_sessions()

    if not session_files:
        print("❌ No Axel session files found to process.")
        print(f"   Make sure Mac Studio backup exists at: ~/Documents/tosync/.gemini/")
        return

    points = []
    point_id = 0
    total_pairs = 0

    for session_file in tqdm(session_files, desc="Processing Axel Sessions"):
        for pair in parse_json_session(session_file):
            user_input = pair["user_input"]
            ai_response = pair["ai_response"]
            thinking = pair.get("thinking", "")

            if len(ai_response) < 20:
                continue

            ai_response_embed = ai_response[:2000] if len(ai_response) > 2000 else ai_response

            # Axel-specific context (The Godhand persona)
            if thinking:
                combined_text = f"User: {user_input}\nAxel (Godhand) Thinking: {thinking[:500]}\nAxel: {ai_response_embed}"
            else:
                combined_text = f"User: {user_input}\nAxel (The Godhand): {ai_response_embed}"

            vector = model.encode(combined_text).tolist()

            payload = {
                "user_input": user_input,
                "ai_response": ai_response,
                "thinking": thinking,
                "session_id": pair.get("session_id", ""),
                "source_file": pair["source_file"],
                "timestamp": pair.get("timestamp", ""),
                "persona": "axel",
                "full_text": combined_text
            }

            points.append(PointStruct(id=point_id, vector=vector, payload=payload))
            point_id += 1
            total_pairs += 1

            if len(points) >= BATCH_SIZE:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                points = []

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\n🔥 AXEL Ingestion Complete!")
    print(f"   📊 {total_pairs} Godhand conversation pairs vectorized")
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


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        get_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        session_files = find_axel_sessions()
        if session_files:
            print(f"\n🔍 Testing: {session_files[0]}")
            pairs = list(parse_json_session(session_files[0]))
            print(f"   Found {len(pairs)} pairs")
            for i, p in enumerate(pairs[:2]):
                print(f"\n   Pair {i+1}:")
                print(f"   User: {p['user_input'][:80]}...")
                print(f"   Axel: {p['ai_response'][:80]}...")
    else:
        setup_collection()
        process_sessions()
        get_stats()
