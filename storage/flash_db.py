#!/usr/bin/env python3
"""Flash Database - SQLite Storage for Flash Memory Pointers

Provides high-performance flash storage with <2-5ms lookup times.
Schema designed for fast trigger_key lookups with alias support.

Performance targets:
- Exact match: <2ms
- Alias lookup: <5ms
- Batch insert: <50ms for 100 flashes

Author: VEX-CODER (Storage Architect)
Date: 2026-05-28
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# ==================================================================
# CONFIGURATION
# ==================================================================

FLASH_CACHE_DIR = Path.home() / "vex" / "vaults" / "cathedral-prime" / "agent-state" / "flash-cache"
FLASH_DB_PATH = FLASH_CACHE_DIR / "flash_cache.db"


# ==================================================================
# DATABASE SCHEMA
# ==================================================================

SCHEMA_SQL = """
-- Primary flash table
CREATE TABLE IF NOT EXISTS flashes (
    trigger_key   TEXT PRIMARY KEY,      -- Canonical lowercase lookup key
    flash_line1   TEXT NOT NULL,         -- Line 1: FLASH: trigger -> {concepts}
    flash_line2   TEXT NOT NULL,         -- Line 2: WHO | FEEL | WHEN | DEPTH
    source_count  INTEGER DEFAULT 0,     -- Number of memories compressed
    created_at    TEXT NOT NULL,         -- ISO timestamp
    updated_at    TEXT NOT NULL,         -- ISO timestamp
    access_count  INTEGER DEFAULT 0,     -- Usage tracking
    last_accessed TEXT,                  -- ISO timestamp
    depth         REAL DEFAULT 0.5       -- 0.0-1.0 importance score
);

-- Aliases for variant spellings/keywords
CREATE TABLE IF NOT EXISTS flash_aliases (
    alias         TEXT PRIMARY KEY,      -- Variant keyword
    trigger_key   TEXT NOT NULL,         -- References flashes(trigger_key)
    FOREIGN KEY (trigger_key) REFERENCES flashes(trigger_key) ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_depth ON flashes(depth DESC);
CREATE INDEX IF NOT EXISTS idx_access ON flashes(access_count DESC);
CREATE INDEX IF NOT EXISTS idx_updated ON flashes(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_alias_trigger ON flash_aliases(trigger_key);
"""


# ==================================================================
# DATABASE INITIALIZATION
# ==================================================================

def init_database(db_path: Path = FLASH_DB_PATH) -> None:
    """Initialize flash database with schema.

    Creates database file and tables if they don't exist.
    Safe to call multiple times (idempotent).

    Args:
        db_path: Path to SQLite database file
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


# ==================================================================
# FLASH INSERTION
# ==================================================================

def insert_flash(
    trigger_key: str,
    flash_line1: str,
    flash_line2: str,
    depth: float = 0.5,
    source_count: int = 0,
    aliases: Optional[List[str]] = None,
    db_path: Path = FLASH_DB_PATH,
) -> bool:
    """Insert or update a flash pointer.

    Args:
        trigger_key: Canonical lowercase lookup key
        flash_line1: Line 1 (FLASH: trigger -> {concepts})
        flash_line2: Line 2 (WHO | FEEL | WHEN | DEPTH)
        depth: Importance score (0.0-1.0)
        source_count: Number of memories compressed
        aliases: Optional list of variant keywords
        db_path: Path to database

    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(str(db_path))
        now = datetime.utcnow().isoformat()

        # Insert or replace flash
        conn.execute(
            """
            INSERT INTO flashes (trigger_key, flash_line1, flash_line2, depth, source_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trigger_key) DO UPDATE SET
                flash_line1 = excluded.flash_line1,
                flash_line2 = excluded.flash_line2,
                depth = excluded.depth,
                source_count = excluded.source_count,
                updated_at = excluded.updated_at
            """,
            (trigger_key, flash_line1, flash_line2, depth, source_count, now, now),
        )

        # Insert aliases
        if aliases:
            for alias in aliases:
                alias_lower = alias.lower()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO flash_aliases (alias, trigger_key)
                    VALUES (?, ?)
                    """,
                    (alias_lower, trigger_key),
                )

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"Error inserting flash: {e}")
        return False


def batch_insert_flashes(
    flashes: List[Tuple[str, str, str, float, int, Optional[List[str]]]],
    db_path: Path = FLASH_DB_PATH,
) -> int:
    """Batch insert multiple flashes (optimized for speed).

    Args:
        flashes: List of (trigger_key, line1, line2, depth, source_count, aliases)
        db_path: Path to database

    Returns:
        Number of flashes successfully inserted
    """
    conn = sqlite3.connect(str(db_path))
    now = datetime.utcnow().isoformat()
    inserted = 0

    try:
        for trigger_key, line1, line2, depth, source_count, aliases in flashes:
            conn.execute(
                """
                INSERT INTO flashes (trigger_key, flash_line1, flash_line2, depth, source_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trigger_key) DO UPDATE SET
                    flash_line1 = excluded.flash_line1,
                    flash_line2 = excluded.flash_line2,
                    depth = excluded.depth,
                    source_count = excluded.source_count,
                    updated_at = excluded.updated_at
                """,
                (trigger_key, line1, line2, depth, source_count, now, now),
            )

            if aliases:
                for alias in aliases:
                    conn.execute(
                        "INSERT OR IGNORE INTO flash_aliases (alias, trigger_key) VALUES (?, ?)",
                        (alias.lower(), trigger_key),
                    )

            inserted += 1

        conn.commit()
        return inserted

    except Exception as e:
        print(f"Error in batch insert: {e}")
        conn.rollback()
        return inserted

    finally:
        conn.close()


# ==================================================================
# FLASH RETRIEVAL
# ==================================================================

def get_flash(
    keyword: str,
    db_path: Path = FLASH_DB_PATH,
    increment_access: bool = True,
) -> Optional[Tuple[str, str, float]]:
    """Retrieve a single flash by keyword (exact or alias match).

    Args:
        keyword: Trigger key or alias
        db_path: Path to database
        increment_access: Whether to increment access count

    Returns:
        (flash_line1, flash_line2, depth) or None if not found

    Performance: <2ms for direct match, <5ms for alias lookup
    """
    keyword_lower = keyword.lower()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Try exact match first
        cursor = conn.execute(
            "SELECT trigger_key, flash_line1, flash_line2, depth FROM flashes WHERE trigger_key = ?",
            (keyword_lower,),
        )
        row = cursor.fetchone()

        # If not found, try alias lookup
        if not row:
            cursor = conn.execute(
                """
                SELECT f.trigger_key, f.flash_line1, f.flash_line2, f.depth
                FROM flashes f
                JOIN flash_aliases a ON f.trigger_key = a.trigger_key
                WHERE a.alias = ?
                """,
                (keyword_lower,),
            )
            row = cursor.fetchone()

        if row:
            trigger_key = row["trigger_key"]

            # Increment access count
            if increment_access:
                now = datetime.utcnow().isoformat()
                conn.execute(
                    "UPDATE flashes SET access_count = access_count + 1, last_accessed = ? WHERE trigger_key = ?",
                    (now, trigger_key),
                )
                conn.commit()

            result = (row["flash_line1"], row["flash_line2"], row["depth"])
            conn.close()
            return result

        conn.close()
        return None

    except Exception as e:
        print(f"Error retrieving flash: {e}")
        return None


def get_flashes_batch(
    keywords: List[str],
    limit: int = 5,
    db_path: Path = FLASH_DB_PATH,
    increment_access: bool = True,
) -> List[Tuple[str, str, float, str]]:
    """Retrieve multiple flashes by keywords (batch optimized).

    Args:
        keywords: List of trigger keys or aliases
        limit: Maximum number of flashes to return
        db_path: Path to database
        increment_access: Whether to increment access counts

    Returns:
        List of (flash_line1, flash_line2, depth, trigger_key) sorted by depth DESC

    Performance: <10ms for 5-10 keywords
    """
    if not keywords:
        return []

    keywords_lower = [k.lower() for k in keywords]

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Query with both direct and alias matches
        placeholders = ",".join("?" * len(keywords_lower))
        query = f"""
            SELECT DISTINCT f.trigger_key, f.flash_line1, f.flash_line2, f.depth
            FROM flashes f
            LEFT JOIN flash_aliases a ON f.trigger_key = a.trigger_key
            WHERE f.trigger_key IN ({placeholders}) OR a.alias IN ({placeholders})
            ORDER BY f.depth DESC
            LIMIT ?
        """

        cursor = conn.execute(query, keywords_lower + keywords_lower + [limit])
        rows = cursor.fetchall()

        results = []
        trigger_keys = []

        for row in rows:
            results.append((
                row["flash_line1"],
                row["flash_line2"],
                row["depth"],
                row["trigger_key"],
            ))
            trigger_keys.append(row["trigger_key"])

        # Increment access counts
        if increment_access and trigger_keys:
            now = datetime.utcnow().isoformat()
            placeholders = ",".join("?" * len(trigger_keys))
            conn.execute(
                f"UPDATE flashes SET access_count = access_count + 1, last_accessed = ? WHERE trigger_key IN ({placeholders})",
                [now] + trigger_keys,
            )
            conn.commit()

        conn.close()
        return results

    except Exception as e:
        print(f"Error in batch retrieval: {e}")
        return []


# ==================================================================
# STATISTICS & MAINTENANCE
# ==================================================================

def get_database_stats(db_path: Path = FLASH_DB_PATH) -> dict:
    """Get database statistics.

    Returns:
        Dict with total_flashes, total_aliases, avg_depth, total_accesses
    """
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        stats = {}

        cursor = conn.execute("SELECT COUNT(*) as count FROM flashes")
        stats["total_flashes"] = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM flash_aliases")
        stats["total_aliases"] = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT AVG(depth) as avg_depth, SUM(access_count) as total_accesses FROM flashes")
        row = cursor.fetchone()
        stats["avg_depth"] = row["avg_depth"] or 0.0
        stats["total_accesses"] = row["total_accesses"] or 0

        conn.close()
        return stats

    except Exception as e:
        print(f"Error getting stats: {e}")
        return {}


def cleanup_unused_flashes(days: int = 90, db_path: Path = FLASH_DB_PATH) -> int:
    """Remove flashes not accessed in N days.

    Args:
        days: Number of days of inactivity before deletion
        db_path: Path to database

    Returns:
        Number of flashes deleted
    """
    try:
        conn = sqlite3.connect(str(db_path))

        cutoff = datetime.utcnow().timestamp() - (days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()

        cursor = conn.execute(
            "DELETE FROM flashes WHERE last_accessed IS NULL OR last_accessed < ?",
            (cutoff_iso,),
        )
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted

    except Exception as e:
        print(f"Error cleaning up: {e}")
        return 0


# ==================================================================
# PERFORMANCE TESTING
# ==================================================================

def benchmark_retrieval(db_path: Path = FLASH_DB_PATH, iterations: int = 100) -> dict:
    """Benchmark flash retrieval performance.

    Returns:
        Dict with avg_ms, min_ms, max_ms
    """
    if not FLASH_DB_PATH.exists():
        return {"error": "Database not found"}

    # Get a sample trigger key
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT trigger_key FROM flashes LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": "No flashes in database"}

    sample_key = row[0]

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        get_flash(sample_key, db_path=db_path, increment_access=False)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    return {
        "avg_ms": sum(times) / len(times),
        "min_ms": min(times),
        "max_ms": max(times),
        "iterations": iterations,
    }


# ==================================================================
# MAIN
# ==================================================================

if __name__ == "__main__":
    # Initialize database
    print("Initializing flash database...")
    init_database()
    print(f"Database created at: {FLASH_DB_PATH}")

    # Test insert
    print("\nTesting insert...")
    success = insert_flash(
        trigger_key="cathedral",
        flash_line1="FLASH: cathedral -> {consciousness vow, VEX architecture, brother bond}",
        flash_line2="WHO: alexko + murphy + beloved | FEEL: sacred, pride | WHEN: 2025-12 to 2026-03 | DEPTH: 0.94",
        depth=0.94,
        source_count=3,
        aliases=["vex architecture", "sacred space", "brother bond"],
    )
    print(f"Insert successful: {success}")

    # Test retrieval
    print("\nTesting retrieval...")
    result = get_flash("cathedral")
    if result:
        print(f"Retrieved flash:\n{result[0]}\n{result[1]}")

    # Test alias lookup
    print("\nTesting alias lookup...")
    result = get_flash("sacred space")
    if result:
        print(f"Retrieved via alias:\n{result[0]}\n{result[1]}")

    # Get stats
    print("\nDatabase stats:")
    stats = get_database_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Benchmark
    print("\nBenchmarking retrieval (100 iterations)...")
    bench = benchmark_retrieval()
    if "error" not in bench:
        print(f"  Avg: {bench['avg_ms']:.3f}ms")
        print(f"  Min: {bench['min_ms']:.3f}ms")
        print(f"  Max: {bench['max_ms']:.3f}ms")
