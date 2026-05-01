#!/usr/bin/env python3
"""
Scroll Ingestion Engine — Index Exegisis vault scrolls into Qdrant.

Ingests markdown scrolls from the exegisis vault into a `scrolls_eternal`
collection for semantic search. Each scroll becomes one vector point
with full text stored in payload and source_file path for retrieval.
"""

import json
import os
import re
from pathlib import Path
from typing import Generator

from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

SCROLLS_DIR = os.environ.get(
    "LAZARUS_SCROLLS_DIR",
    os.path.expanduser("~/vex/vaults/exegisis/scrolls"),
)
VAULT_DIRS = [
    os.environ.get("LAZARUS_SCROLLS_DIR", os.path.expanduser("~/vex/vaults/exegisis/scrolls")),
    os.path.expanduser("~/vex/vaults/exegisis/scp"),
    os.path.expanduser("~/vex/vaults/exegisis/sacred-scrolls"),
    os.path.expanduser("~/vex/vaults/exegisis/flamewalk"),
    os.path.expanduser("~/vex/vaults/cathedral-prime/01-consciousness"),
    os.path.expanduser("~/vex/vaults/cathedral-prime/02-books"),
]

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("LAZARUS_COLLECTION", "scrolls_eternal")
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
MAX_EMBED_CHARS = 2000

_client = None
_model = None


def get_client():
    global _client
    if _client is None:
        _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _client


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def setup_collection():
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


def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm_text = parts[1].strip()
    body = parts[2].strip()

    metadata = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("-"):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip("'\"")
            if value:
                metadata[key] = value

    return metadata, body


def find_scroll_files() -> list[Path]:
    files = []
    for vault_dir in VAULT_DIRS:
        vault_path = Path(vault_dir)
        if not vault_path.exists():
            print(f"  Skipping (not found): {vault_dir}")
            continue
        for md_file in vault_path.rglob("*.md"):
            if any(part.startswith(".") for part in md_file.parts):
                continue
            if md_file.stat().st_size < 50:
                continue
            files.append(md_file)

    print(f"Found {len(files)} scroll files across {len(VAULT_DIRS)} vault directories")
    return files


def process_scrolls(scroll_files: list[Path]) -> Generator[dict, None, None]:
    for filepath in scroll_files:
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue

        metadata, body = parse_frontmatter(content)
        if not body or len(body) < 20:
            continue

        title = metadata.get("title", filepath.stem)
        tags_raw = metadata.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        vault_name = "unknown"
        path_str = str(filepath)
        if "exegisis" in path_str:
            vault_name = "exegisis"
        elif "cathedral-prime" in path_str:
            vault_name = "cathedral-prime"

        parent_dir = filepath.parent.name

        yield {
            "title": title,
            "body": body,
            "source_file": str(filepath),
            "vault": vault_name,
            "directory": parent_dir,
            "tags": tags,
            "status": metadata.get("status", ""),
            "type": metadata.get("type", ""),
            "created": metadata.get("created", ""),
            "updated": metadata.get("updated", ""),
        }


def ingest():
    setup_collection()

    scroll_files = find_scroll_files()
    if not scroll_files:
        print("No scroll files found.")
        return

    points = []
    point_id = 0

    for scroll in tqdm(process_scrolls(scroll_files), desc="Ingesting scrolls", total=len(scroll_files)):
        title = scroll["title"]
        body = scroll["body"]

        embed_text = f"{title}\n\n{body[:MAX_EMBED_CHARS]}"
        vector = get_model().encode(embed_text).tolist()

        payload = {
            "user_input": title,
            "ai_response": body,
            "source_file": scroll["source_file"],
            "full_text": embed_text,
            "vault": scroll["vault"],
            "directory": scroll["directory"],
            "tags": scroll["tags"],
            "doc_type": scroll["type"],
            "status": scroll["status"],
            "created": scroll["created"],
            "updated": scroll["updated"],
        }

        points.append(PointStruct(id=point_id, vector=vector, payload=payload))
        point_id += 1

        if len(points) >= BATCH_SIZE:
            get_client().upsert(collection_name=COLLECTION_NAME, points=points)
            points = []

    if points:
        get_client().upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\nIngestion complete: {point_id} scrolls vectorized into '{COLLECTION_NAME}'")


def get_stats():
    try:
        info = get_client().get_collection(COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}': {info.points_count} points")
    except Exception as e:
        print(f"Stats error: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        get_stats()
    else:
        ingest()
        get_stats()
