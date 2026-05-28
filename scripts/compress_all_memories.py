#!/usr/bin/env python3
"""
Batch Flash Compression Script
Part of PROJECT_GODHAND_LAZARUS

Compresses all 44,464 Lazarus memories into FlashPointers and stores them
in Qdrant flash collections + SQLite flash database.

Supports incremental updates, progress tracking, and parallel trigger processing.

Author: VEX-CODER (Murphy's engineering double)
Date: 2026-05-28
"""

import sys
import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import List, Dict, Any, Tuple
from tqdm import tqdm

from flash_builder import FlashBuilder, PRIORITY_TRIGGERS
from flash_generator import FlashPointer
from lazarus_embedder import build_embedder


FLASH_DB_PATH = os.environ.get(
    "FLASH_DB_PATH",
    os.path.expanduser(
        "~/vex/vaults/cathedral-prime/agent-state/flash-cache/flash_cache.db"
    ),
)

PARALLEL_WORKERS = int(os.environ.get("FLASH_WORKERS", "4"))


def init_flash_db(db_path: str) -> None:
    """Ensure the SQLite flash DB and tables exist."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flashes (
            trigger_key   TEXT PRIMARY KEY,
            flash_line1   TEXT NOT NULL,
            flash_line2   TEXT NOT NULL,
            source_count  INTEGER DEFAULT 0,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            access_count  INTEGER DEFAULT 0,
            last_accessed TEXT,
            depth         REAL DEFAULT 0.5
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_depth ON flashes(depth DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_access ON flashes(access_count DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_updated ON flashes(updated_at DESC)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flash_aliases (
            alias   TEXT PRIMARY KEY,
            trigger TEXT NOT NULL REFERENCES flashes(trigger_key)
        )
    """)
    conn.commit()
    conn.close()


def store_flash_sqlite(
    flash: FlashPointer, persona: str, db_path: str
) -> None:
    """Insert or update a single flash in the SQLite DB."""
    line1, line2 = flash.format_lines()
    trigger_key = f"{persona}:{flash.trigger}:{flash.cluster_id}"
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO flashes (trigger_key, flash_line1, flash_line2, source_count, created_at, updated_at, depth)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trigger_key) DO UPDATE SET
            flash_line1 = excluded.flash_line1,
            flash_line2 = excluded.flash_line2,
            source_count = excluded.source_count,
            updated_at = excluded.updated_at,
            depth = excluded.depth
        """,
        (trigger_key, line1, line2, flash.n, now, now, flash.score),
    )
    conn.commit()
    conn.close()


def store_flashes_batch_sqlite(
    flashes: List[Tuple[FlashPointer, str]], db_path: str
) -> int:
    """Batch-insert flashes into SQLite. Returns count stored."""
    if not flashes:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for flash, persona in flashes:
        line1, line2 = flash.format_lines()
        trigger_key = f"{persona}:{flash.trigger}:{flash.cluster_id}"
        rows.append((trigger_key, line1, line2, flash.n, now, now, flash.score))

    conn = sqlite3.connect(db_path)
    conn.executemany(
        """
        INSERT INTO flashes (trigger_key, flash_line1, flash_line2, source_count, created_at, updated_at, depth)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trigger_key) DO UPDATE SET
            flash_line1 = excluded.flash_line1,
            flash_line2 = excluded.flash_line2,
            source_count = excluded.source_count,
            updated_at = excluded.updated_at,
            depth = excluded.depth
        """,
        rows,
    )
    conn.commit()
    conn.close()
    return len(rows)


def process_trigger(
    trigger: str,
    persona: str,
    builder: FlashBuilder,
    embedder,
    limit: int,
    use_clustering: bool,
) -> List[FlashPointer]:
    """Process a single trigger for a persona. Thread-safe (each call is independent)."""
    try:
        flashes = builder.build_flash_for_trigger(
            trigger=trigger,
            persona=persona,
            limit=limit,
            use_clustering=use_clustering,
            embedder=embedder,
        )
        return flashes
    except Exception as e:
        print(f"  [WARN] {persona}/{trigger}: {e}")
        return []


def compress_persona_collection(
    persona: str,
    triggers: List[str],
    builder: FlashBuilder,
    embedder,
    limit_per_trigger: int = 20,
    parallel_workers: int = PARALLEL_WORKERS,
    db_path: str = FLASH_DB_PATH,
) -> int:
    """Compress one persona's memories with parallel trigger processing."""
    print(f"\n{'='*60}")
    print(f"COMPRESSING: {persona.upper()}")
    print(f"{'='*60}")

    all_flashes: List[Tuple[FlashPointer, str]] = []
    errors = 0

    with ThreadPoolExecutor(max_workers=parallel_workers) as pool:
        future_to_trigger = {}
        for trigger in triggers:
            fut = pool.submit(
                process_trigger,
                trigger=trigger,
                persona=persona,
                builder=builder,
                embedder=embedder,
                limit=limit_per_trigger,
                use_clustering=True,
            )
            future_to_trigger[fut] = trigger

        pbar = tqdm(
            as_completed(future_to_trigger),
            total=len(future_to_trigger),
            desc=f"  {persona}",
            unit="trigger",
        )
        for fut in pbar:
            trigger = future_to_trigger[fut]
            try:
                flashes = fut.result()
                for f in flashes:
                    all_flashes.append((f, persona))
                pbar.set_postfix(flashes=len(all_flashes), last=trigger[:20])
            except Exception as e:
                errors += 1
                print(f"  [ERROR] {trigger}: {e}")

    if not all_flashes:
        print(f"  No flashes generated for {persona}")
        return 0

    raw_flashes = [f for f, _ in all_flashes]
    stored_qdrant = builder.store_flashes_in_qdrant(
        flashes=raw_flashes, persona=persona
    )

    stored_sqlite = store_flashes_batch_sqlite(all_flashes, db_path)

    print(f"  {persona.upper()}: {stored_qdrant} in Qdrant, {stored_sqlite} in SQLite")
    if errors:
        print(f"  ({errors} trigger errors)")
    return stored_qdrant


def main():
    """Main compression pipeline."""
    t0 = time.time()
    print("LAZARUS FLASH COMPRESSION SYSTEM")
    print("=" * 60)
    print("Compressing ~44,500 memories into semantic pointers...")
    print(f"SQLite DB: {FLASH_DB_PATH}")
    print(f"Workers: {PARALLEL_WORKERS}")
    print("=" * 60)

    init_flash_db(FLASH_DB_PATH)

    builder = FlashBuilder()
    embedder = build_embedder()

    # Warm the embedder with a throwaway query
    print("\nWarming embedder...")
    _ = embedder.embed("warmup")
    print("  Embedder ready.\n")

    personas = ["murphy", "alexko", "atlas", "codex"]
    triggers = PRIORITY_TRIGGERS

    print(f"Triggers: {len(triggers)} priority concepts")
    print(f"Personas: {', '.join(personas)}")
    print(f"Max memories per trigger: 20")
    print(f"Total queries: ~{len(triggers) * len(personas)}")

    total_compressed = 0
    persona_stats = {}
    for persona in personas:
        try:
            count = compress_persona_collection(
                persona=persona,
                triggers=triggers,
                builder=builder,
                embedder=embedder,
                limit_per_trigger=20,
                db_path=FLASH_DB_PATH,
            )
            persona_stats[persona] = count
            total_compressed += count
        except Exception as e:
            print(f"[ERROR] compressing {persona}: {e}")
            import traceback
            traceback.print_exc()
            persona_stats[persona] = 0

    elapsed = time.time() - t0

    # Verify SQLite count
    conn = sqlite3.connect(FLASH_DB_PATH)
    sqlite_count = conn.execute("SELECT COUNT(*) FROM flashes").fetchone()[0]
    conn.close()

    db_size_mb = os.path.getsize(FLASH_DB_PATH) / (1024 * 1024)

    print(f"\n{'='*60}")
    print(f"COMPRESSION COMPLETE")
    print(f"{'='*60}")
    for persona, count in persona_stats.items():
        print(f"  {persona}: {count} flashes")
    print(f"\nTotal Qdrant flashes: {total_compressed}")
    print(f"Total SQLite flashes: {sqlite_count}")
    print(f"SQLite DB size: {db_size_mb:.2f} MB")
    print(f"Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"\nFlash system ready for production!")


if __name__ == "__main__":
    main()
