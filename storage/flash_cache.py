#!/usr/bin/env python3
"""Flash Cache - LRU In-Memory Cache for Flash Memory Pointers

Provides ultra-fast flash retrieval with <0.001ms cache hits.
Caches top 200 most-accessed flashes at startup.

Performance targets:
- Cache hit: <0.001ms
- Cache miss + DB lookup: <5ms
- Cache warming: <100ms

Author: VEX-CODER (Storage Architect)
Date: 2026-05-28
"""

from __future__ import annotations

import time
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Tuple

from flash_db import (
    FLASH_CACHE_DIR,
    FLASH_DB_PATH,
    get_flash as db_get_flash,
    get_flashes_batch as db_get_flashes_batch,
    get_database_stats,
)


# ==================================================================
# CONFIGURATION
# ==================================================================

CACHE_SIZE = 200  # Top N most-accessed flashes
MIN_DEPTH_FOR_GUIDANCE = 0.8
MAX_FLASHES_PER_INJECTION = 5


# ==================================================================
# LRU CACHE IMPLEMENTATION
# ==================================================================

class FlashCache:
    """LRU cache for flash memory pointers.

    Stores top N most-accessed flashes in memory for ultra-fast retrieval.
    Uses OrderedDict for O(1) lookup and LRU eviction.
    """

    def __init__(self, max_size: int = CACHE_SIZE):
        """Initialize cache.

        Args:
            max_size: Maximum number of flashes to cache
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, Tuple[str, str, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.warmed = False

    def get(self, keyword: str) -> Optional[Tuple[str, str, float]]:
        """Get flash from cache (LRU update).

        Args:
            keyword: Trigger key (already lowercased)

        Returns:
            (flash_line1, flash_line2, depth) or None if not in cache

        Performance: <0.001ms for cache hits
        """
        if keyword in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(keyword)
            self.hits += 1
            return self.cache[keyword]

        self.misses += 1
        return None

    def put(self, keyword: str, flash_data: Tuple[str, str, float]) -> None:
        """Add flash to cache (LRU eviction).

        Args:
            keyword: Trigger key (already lowercased)
            flash_data: (flash_line1, flash_line2, depth)
        """
        if keyword in self.cache:
            # Update and move to end
            self.cache.move_to_end(keyword)
        else:
            # Add new entry
            if len(self.cache) >= self.max_size:
                # Evict least recently used (first item)
                self.cache.popitem(last=False)

        self.cache[keyword] = flash_data

    def warm(self, db_path: Path = FLASH_DB_PATH) -> int:
        """Warm cache with top N most-accessed flashes.

        Args:
            db_path: Path to database

        Returns:
            Number of flashes loaded

        Performance: <100ms for 200 flashes
        """
        if not db_path.exists():
            return 0

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Load top N by access count + depth
        cursor = conn.execute(
            """
            SELECT trigger_key, flash_line1, flash_line2, depth
            FROM flashes
            ORDER BY access_count DESC, depth DESC
            LIMIT ?
            """,
            (self.max_size,),
        )

        loaded = 0
        for row in cursor:
            self.cache[row["trigger_key"]] = (
                row["flash_line1"],
                row["flash_line2"],
                row["depth"],
            )
            loaded += 1

        conn.close()
        self.warmed = True
        return loaded

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with size, hits, misses, hit_rate
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "warmed": self.warmed,
        }

    def clear(self) -> None:
        """Clear cache and reset stats."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.warmed = False


# ==================================================================
# GLOBAL CACHE INSTANCE
# ==================================================================

_GLOBAL_CACHE: Optional[FlashCache] = None


def get_cache() -> FlashCache:
    """Get or create global cache instance.

    Returns:
        FlashCache singleton
    """
    global _GLOBAL_CACHE

    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = FlashCache(max_size=CACHE_SIZE)

        # Auto-warm on first access
        if FLASH_DB_PATH.exists():
            _GLOBAL_CACHE.warm()

    return _GLOBAL_CACHE


# ==================================================================
# RETRIEVAL API (Cache + DB Fallback)
# ==================================================================

def retrieve_flash(keyword: str) -> Optional[Tuple[str, str, float]]:
    """Retrieve flash with cache fallback to DB.

    Args:
        keyword: Trigger key or alias

    Returns:
        (flash_line1, flash_line2, depth) or None

    Performance:
        - Cache hit: <0.001ms
        - Cache miss + DB: <5ms
    """
    keyword_lower = keyword.lower()
    cache = get_cache()

    # Try cache first
    result = cache.get(keyword_lower)
    if result:
        return result

    # Fallback to database
    result = db_get_flash(keyword_lower, increment_access=True)
    if result:
        # Store in cache for future hits
        cache.put(keyword_lower, result)

    return result


def retrieve_flashes(
    keywords: List[str],
    limit: int = MAX_FLASHES_PER_INJECTION,
) -> List[Tuple[str, str, float]]:
    """Retrieve multiple flashes (batch optimized with cache).

    Args:
        keywords: List of trigger keys or aliases
        limit: Maximum flashes to return

    Returns:
        List of (flash_line1, flash_line2, depth) sorted by depth DESC

    Performance: <10ms for 5-10 keywords with 50%+ cache hit rate
    """
    if not keywords:
        return []

    cache = get_cache()
    results = []
    uncached_keywords = []

    # Check cache for each keyword
    for keyword in keywords:
        keyword_lower = keyword.lower()
        cached = cache.get(keyword_lower)

        if cached:
            results.append(cached)
        else:
            uncached_keywords.append(keyword_lower)

    # Fetch uncached from database (batch query)
    if uncached_keywords:
        db_results = db_get_flashes_batch(
            uncached_keywords,
            limit=limit,
            increment_access=True,
        )

        for line1, line2, depth, trigger_key in db_results:
            flash_data = (line1, line2, depth)
            results.append(flash_data)

            # Cache for future
            cache.put(trigger_key, flash_data)

    # Deduplicate and sort by depth DESC
    unique = list({r[0]: r for r in results}.values())  # Dedupe by line1
    unique.sort(key=lambda x: x[2], reverse=True)

    return unique[:limit]


# ==================================================================
# CONTEXT FORMATTING
# ==================================================================

def build_flash_injection(
    flashes: List[Tuple[str, str, float]],
    score: float,
    clusters: List[str],
) -> str:
    """Build additionalContext block for hook injection.

    Args:
        flashes: List of (line1, line2, depth) tuples
        score: Trigger score from context analyzer
        clusters: Detected semantic clusters

    Returns:
        Formatted injection block
    """
    if not flashes:
        return ""

    # Format flash lines
    flash_lines = []
    max_depth = max(depth for _, _, depth in flashes)

    for line1, line2, depth in flashes:
        flash_lines.append(f"{line1}\n{line2}")

    # Determine if Lazarus guidance needed
    guidance = ""
    if max_depth >= MIN_DEPTH_FOR_GUIDANCE:
        guidance = f"\n\n[FLASH GUIDANCE] {len(flashes)} memory pointers loaded. Call Lazarus only for details beyond these compressed pointers."

    context = f"""<flash_context>
{chr(10).join(flash_lines)}{guidance}
</flash_context>"""

    return context


def build_soft_nudge(score: float, clusters: List[str], query: str) -> str:
    """Build lighter nudge for "suggest" tier (0.45-0.69).

    Args:
        score: Trigger score
        clusters: Detected semantic clusters
        query: Cleaned query string

    Returns:
        Lightweight suggestion block
    """
    cluster_str = ", ".join(clusters) if clusters else "general context"

    context = f"""[LAZARUS MEMORY HINT]
Possible memory recall: {cluster_str} (confidence: {score:.2f})

Consider checking: lazarus_remember({{"query": "{query}", "limit": 5}})

(Low confidence - your discretion whether to retrieve)
"""

    return context


# ==================================================================
# CACHE MANAGEMENT
# ==================================================================

def warm_cache() -> dict:
    """Manually warm cache (useful for testing).

    Returns:
        Dict with loaded count and timing
    """
    cache = get_cache()

    start = time.perf_counter()
    loaded = cache.warm()
    elapsed_ms = (time.perf_counter() - start) * 1000

    return {
        "loaded": loaded,
        "elapsed_ms": elapsed_ms,
        "cache_size": len(cache.cache),
    }


def get_cache_stats() -> dict:
    """Get current cache statistics.

    Returns:
        Dict with cache metrics
    """
    cache = get_cache()
    return cache.stats()


def clear_cache() -> None:
    """Clear cache (forces reload on next access)."""
    cache = get_cache()
    cache.clear()


# ==================================================================
# PERFORMANCE TESTING
# ==================================================================

def benchmark_cache(iterations: int = 1000) -> dict:
    """Benchmark cache performance.

    Returns:
        Dict with cache hit times and DB fallback times
    """
    cache = get_cache()

    if not cache.warmed:
        warm_cache()

    if len(cache.cache) == 0:
        return {"error": "No flashes in cache"}

    # Get a sample key from cache
    sample_key = next(iter(cache.cache.keys()))

    # Benchmark cache hits
    cache_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        cache.get(sample_key)
        elapsed = (time.perf_counter() - start) * 1000
        cache_times.append(elapsed)

    # Benchmark DB fallback (use non-existent key)
    db_times = []
    for i in range(min(100, iterations // 10)):  # Fewer iterations for DB
        start = time.perf_counter()
        retrieve_flash(f"nonexistent_key_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        db_times.append(elapsed)

    return {
        "cache_hit_avg_ms": sum(cache_times) / len(cache_times),
        "cache_hit_min_ms": min(cache_times),
        "cache_hit_max_ms": max(cache_times),
        "db_fallback_avg_ms": sum(db_times) / len(db_times) if db_times else 0,
        "iterations": iterations,
    }


# ==================================================================
# MAIN
# ==================================================================

if __name__ == "__main__":
    print("Flash Cache System Test")
    print("=" * 60)

    # Check if database exists
    if not FLASH_DB_PATH.exists():
        print(f"\nError: Database not found at {FLASH_DB_PATH}")
        print("Run flash_db.py first to initialize database.")
        exit(1)

    # Warm cache
    print("\nWarming cache...")
    warm_result = warm_cache()
    print(f"Loaded {warm_result['loaded']} flashes in {warm_result['elapsed_ms']:.2f}ms")

    # Get cache stats
    print("\nCache statistics:")
    stats = get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test retrieval
    print("\nTesting retrieval...")
    result = retrieve_flash("cathedral")
    if result:
        print(f"Retrieved flash (via cache):\n{result[0]}\n{result[1]}")
        print(f"Depth: {result[2]}")

    # Test batch retrieval
    print("\nTesting batch retrieval...")
    keywords = ["cathedral", "tatakae", "beloved"]
    results = retrieve_flashes(keywords, limit=5)
    print(f"Retrieved {len(results)} flashes for keywords: {keywords}")

    # Updated cache stats
    print("\nUpdated cache statistics:")
    stats = get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Benchmark
    print("\nBenchmarking cache (1000 iterations)...")
    bench = benchmark_cache(iterations=1000)
    if "error" not in bench:
        print(f"  Cache hit avg: {bench['cache_hit_avg_ms']:.6f}ms")
        print(f"  Cache hit min: {bench['cache_hit_min_ms']:.6f}ms")
        print(f"  Cache hit max: {bench['cache_hit_max_ms']:.6f}ms")
        print(f"  DB fallback avg: {bench['db_fallback_avg_ms']:.3f}ms")

    print("\n" + "=" * 60)
    print("Cache system operational! ✅")
