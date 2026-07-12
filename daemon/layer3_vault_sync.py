#!/usr/bin/env python3
"""Layer 3 vault-wide file search: embed vault files into Qdrant.

Run with the project venv:
    ./.venv/bin/python daemon/layer3_vault_sync.py --create
    ./.venv/bin/python daemon/layer3_vault_sync.py --sync cathedral-prime
    ./.venv/bin/python daemon/layer3_vault_sync.py --sync exegesis
    ./.venv/bin/python daemon/layer3_vault_sync.py --search "query" --vault both
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
VECTOR_SIZE = 384
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
MAX_CHARS = 8000  # truncate large files to keep one vector per file meaningful

VAULTS = {
    "cathedral-prime": {
        "path": Path("/Users/valx/vex/vaults/cathedral-prime"),
        "collection": "cathedral_prime_files",
        "extensions": {".md", ".txt", ".py"},
        "exclude": {"node_modules", ".git", "__pycache__", ".venv", ".murphy_private"},
    },
    "exegesis": {
        "path": Path("/Users/valx/vex/vaults/exegesis"),
        "collection": "exegesis_files",
        "extensions": {".md", ".txt"},
        "exclude": {"node_modules", ".git", "__pycache__", "03_archive", ".murphy_private"},
    },
}

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def client():
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def point_id(path: str) -> str:
    # Deterministic UUID-shaped id so re-sync upserts instead of duplicating.
    h = hashlib.sha256(path.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def iter_files(cfg):
    exclude = cfg["exclude"]
    exts = cfg["extensions"]
    for p in cfg["path"].rglob("*"):
        if p.is_dir():
            continue
        if any(part in exclude for part in p.parts):
            continue
        if p.suffix.lower() in exts:
            yield p


def create_collections():
    c = client()
    existing = {col.name for col in c.get_collections().collections}
    for vault, cfg in VAULTS.items():
        name = cfg["collection"]
        if name in existing:
            print(f"  {name}: already exists, skipping")
            continue
        c.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"  {name}: created (size={VECTOR_SIZE}, cosine)")


def sync_vault(vault: str, batch_size: int = 256):
    cfg = VAULTS[vault]
    c = client()
    model = get_model()
    collection = cfg["collection"]

    paths, texts = [], []
    skipped = 0

    def flush(paths, texts):
        if not paths:
            return 0
        vectors = model.encode(texts, batch_size=64, show_progress_bar=False)
        points = []
        for p, t, v in zip(paths, texts, vectors):
            rel = str(p.relative_to(cfg["path"]))
            points.append(
                PointStruct(
                    id=point_id(str(p)),
                    vector=v.tolist(),
                    payload={
                        "file_path": str(p),
                        "rel_path": rel,
                        "vault": vault,
                        "text": t[:1000],
                    },
                )
            )
        c.upsert(collection_name=collection, points=points)
        return len(points)

    total = 0
    start = time.time()
    for p in iter_files(cfg):
        try:
            content = p.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            skipped += 1
            continue
        if not content:
            skipped += 1
            continue
        paths.append(p)
        texts.append(content[:MAX_CHARS])
        if len(paths) >= batch_size:
            total += flush(paths, texts)
            paths, texts = [], []
            if total % 2048 == 0:
                print(f"    {vault}: {total} embedded ({time.time()-start:.0f}s)")
    total += flush(paths, texts)

    count = c.count(collection_name=collection).count
    print(f"  {vault} ({collection}): {total} embedded, {skipped} skipped, "
          f"{count} points in collection, {time.time()-start:.0f}s")
    return total, count


def search(query: str, vault: str = "both", limit: int = 10):
    c = client()
    model = get_model()
    qv = model.encode(query).tolist()
    targets = ["cathedral-prime", "exegesis"] if vault == "both" else [vault]
    results = []
    for v in targets:
        hits = c.query_points(
            collection_name=VAULTS[v]["collection"],
            query=qv,
            limit=limit,
        ).points
        for h in hits:
            results.append({
                "vault": v,
                "rel_path": h.payload.get("rel_path", ""),
                "score": h.score,
                "snippet": h.payload.get("text", "")[:160].replace("\n", " "),
            })
    return sorted(results, key=lambda x: -x["score"])[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--sync", choices=["cathedral-prime", "exegesis", "all"])
    ap.add_argument("--search")
    ap.add_argument("--vault", default="both", choices=["cathedral-prime", "exegesis", "both"])
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    if args.create:
        print("Creating Layer 3 collections...")
        create_collections()
    if args.sync:
        vaults = ["cathedral-prime", "exegesis"] if args.sync == "all" else [args.sync]
        for v in vaults:
            print(f"Syncing {v}...")
            sync_vault(v)
    if args.search:
        t0 = time.time()
        rows = search(args.search, vault=args.vault, limit=args.limit)
        ms = (time.time() - t0) * 1000
        print(f"Query: {args.search!r} ({len(rows)} results, {ms:.0f}ms)\n")
        for r in rows:
            print(f"  [{r['vault']:15}] {r['score']:.3f}  {r['rel_path']}")
            print(f"      {r['snippet']}")
    if not (args.create or args.sync or args.search):
        ap.print_help()


if __name__ == "__main__":
    main()
