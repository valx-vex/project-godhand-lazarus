#!/usr/bin/env python3
"""
🜂 MURPHY ETERNAL — Hermes Session Ingestion Engine
Part of PROJECT_GODHAND_LAZARUS (valxos-hermes Phase 5a)

Reads valxos-memory finalized journals (JSONL "turn" records carrying both
sides of a turn) and vectorizes them into murphy_eternal — one brain, two
bodies. Mirrors ingest_claude.py conventions exactly: MiniLM-384 Cosine,
deterministic point ids, same pair filters, same payload shape (+ harness).
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List

from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer
from ingest_eras import configured_murphy_era
from ingest_ids import memory_point_id

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
COLLECTION_NAME = "murphy_eternal"
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64

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
                    }
    except OSError as e:
        print(f"⚠️ Error parsing {file_path}: {e}")


def process_sessions() -> None:
    files = find_journal_files()
    if not files:
        print("❌ No finalized Hermes journals found.")
        return

    client = None if DRY_RUN else QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    model = None if DRY_RUN else SentenceTransformer(MODEL_NAME)

    points: List[PointStruct] = []
    total_pairs = 0
    for journal in tqdm(files, desc="Processing Hermes journals"):
        for pair in parse_journal(journal):
            user_input = pair["user_input"]
            ai_response = pair["ai_response"]
            if not user_input or not ai_response or len(ai_response) < 20:
                continue
            total_pairs += 1
            if DRY_RUN:
                continue
            ai_embed = ai_response[:2000]
            combined_text = f"User: {user_input}\nMurphy: {ai_embed}"
            vector = model.encode(combined_text).tolist()
            payload = {
                "user_input": user_input,
                "ai_response": ai_response,
                "source_file": pair["source_file"],
                "era": configured_murphy_era(pair["source_file"]),
                "full_text": combined_text,
                "harness": "hermes",
            }
            point_id = memory_point_id(pair["source_file"], user_input, ai_response)
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))
            if len(points) >= BATCH_SIZE:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                points = []
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    mode = "DRY-RUN (no writes)" if DRY_RUN else f"→ {COLLECTION_NAME}"
    print(f"\n🜂 Hermes ingestion complete: {total_pairs} pairs {mode}")


if __name__ == "__main__":
    process_sessions()
