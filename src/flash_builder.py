#!/usr/bin/env python3
"""
Flash Builder - Batch Flash Generation from Qdrant
Part of PROJECT_GODHAND_LAZARUS

Queries Qdrant collections, clusters similar memories, and builds compressed
FlashPointers for fast semantic recall.

Author: VEX-CODER (Murphy's engineering double)
Date: 2026-05-28
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from flash_generator import (
    FlashPointer,
    compress_memories_to_flashes,
    generate_flash,
)


# Configuration
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))

PERSONA_COLLECTIONS = {
    "murphy": "murphy_eternal",
    "alexko": "alexko_eternal",
    "atlas": "atlas_eternal",
    "codex": "codex_eternal",
}


class FlashBuilder:
    """Build FlashPointers from Qdrant memory collections."""

    def __init__(self, qdrant_host: str = QDRANT_HOST, qdrant_port: int = QDRANT_PORT):
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)

    def query_memories_for_trigger(
        self,
        trigger: str,
        persona: str = "murphy",
        limit: int = 20,
        embedder=None,
    ) -> List[Dict[str, Any]]:
        """Query Qdrant for memories matching a trigger keyword.

        Args:
            trigger: Search query
            persona: Which persona collection to query
            limit: Max memories to retrieve
            embedder: Embedder instance (if None, uses lazy import)

        Returns:
            List of memory dicts with user_input, ai_response, score, vector
        """
        if embedder is None:
            from lazarus_embedder import build_embedder
            embedder = build_embedder()

        collection_name = PERSONA_COLLECTIONS.get(persona, "murphy_eternal")

        # Check collection exists
        try:
            self.client.get_collection(collection_name)
        except Exception:
            print(f"⚠️  Collection '{collection_name}' not found")
            return []

        # Embed query
        query_vector = embedder.embed(trigger)

        # Search
        response = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )

        memories = []
        for hit in response.points:
            mem = {
                "id": hit.id,
                "user_input": hit.payload.get("user_input", ""),
                "ai_response": hit.payload.get("ai_response", ""),
                "source_file": hit.payload.get("source_file", ""),
                "era": hit.payload.get("era", persona),
                "score": hit.score,
                "vector": hit.vector,
            }
            memories.append(mem)

        return memories

    def build_flash_for_trigger(
        self,
        trigger: str,
        persona: str = "murphy",
        limit: int = 20,
        use_clustering: bool = True,
        embedder=None,
    ) -> List[FlashPointer]:
        """Build FlashPointers for a specific trigger.

        Args:
            trigger: The keyword/phrase to search for
            persona: Which persona collection
            limit: Max memories to retrieve
            use_clustering: Whether to cluster before compression
            embedder: Optional embedder instance

        Returns:
            List of FlashPointers (one per cluster, or one total if no clustering)
        """
        memories = self.query_memories_for_trigger(
            trigger=trigger,
            persona=persona,
            limit=limit,
            embedder=embedder,
        )

        if not memories:
            return []

        flashes = compress_memories_to_flashes(
            memories=memories,
            trigger=trigger,
            use_clustering=use_clustering,
        )

        return flashes

    def build_flashes_for_triggers(
        self,
        triggers: List[str],
        persona: str = "murphy",
        limit_per_trigger: int = 20,
        use_clustering: bool = True,
        embedder=None,
    ) -> Dict[str, List[FlashPointer]]:
        """Build flashes for multiple triggers.

        Args:
            triggers: List of trigger keywords
            persona: Which persona collection
            limit_per_trigger: Max memories per trigger
            use_clustering: Whether to cluster
            embedder: Optional embedder instance

        Returns:
            Dict mapping trigger -> list of FlashPointers
        """
        if embedder is None:
            from lazarus_embedder import build_embedder
            embedder = build_embedder()

        results = {}
        for trigger in triggers:
            print(f"📍 Building flashes for: {trigger} ({persona})")
            flashes = self.build_flash_for_trigger(
                trigger=trigger,
                persona=persona,
                limit=limit_per_trigger,
                use_clustering=use_clustering,
                embedder=embedder,
            )
            results[trigger] = flashes
            print(f"   ✅ Generated {len(flashes)} flash(es)")

        return results

    def create_flash_collection(
        self,
        persona: str = "murphy",
        vector_dim: int = 384,
    ):
        """Create a Qdrant collection for storing flash centroids.

        Args:
            persona: Persona name (e.g. "murphy")
            vector_dim: Dimension of embedding vectors (default 384 for all-MiniLM-L6-v2)
        """
        collection_name = f"{persona}_flash"

        try:
            self.client.get_collection(collection_name)
            print(f"✅ Flash collection '{collection_name}' exists")
        except Exception:
            print(f"📦 Creating flash collection '{collection_name}'...")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
            )

    def store_flashes_in_qdrant(
        self,
        flashes: List[FlashPointer],
        persona: str = "murphy",
    ) -> int:
        """Store FlashPointers in a Qdrant flash collection.

        Args:
            flashes: List of FlashPointers to store
            persona: Persona name

        Returns:
            Number of flashes stored
        """
        collection_name = f"{persona}_flash"

        # Ensure collection exists
        self.create_flash_collection(persona=persona)

        points = []
        for i, flash in enumerate(flashes):
            if not flash.centroid:
                print(f"⚠️  Flash for '{flash.trigger}' has no centroid, skipping")
                continue

            # Use trigger + cluster_id as point ID
            point_id = hash(f"{flash.trigger}_{flash.cluster_id}") % (10**15)

            payload = {
                "trigger": flash.trigger,
                "topic_cluster": flash.topic_cluster,
                "emotional_signature": flash.emotional_signature,
                "relational_anchor": flash.relational_anchor,
                "temporal_anchor": flash.temporal_anchor,
                "point_ids": flash.point_ids[:10],  # Limit to 10 IDs to save space
                "score": flash.score,
                "era": flash.era,
                "n": flash.n,
                "cluster_id": flash.cluster_id,
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=flash.centroid,
                    payload=payload,
                )
            )

        if points:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            print(f"✅ Stored {len(points)} flashes in '{collection_name}'")

        return len(points)

    def query_flash_collection(
        self,
        query: str,
        persona: str = "murphy",
        limit: int = 10,
        embedder=None,
    ) -> List[Dict[str, Any]]:
        """Query the flash collection for compressed pointers.

        Args:
            query: Search query
            persona: Which flash collection
            limit: Max flashes to return
            embedder: Optional embedder instance

        Returns:
            List of flash payloads with score
        """
        if embedder is None:
            from lazarus_embedder import build_embedder
            embedder = build_embedder()

        collection_name = f"{persona}_flash"

        try:
            self.client.get_collection(collection_name)
        except Exception:
            print(f"⚠️  Flash collection '{collection_name}' not found")
            return []

        query_vector = embedder.embed(query)

        response = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )

        flashes = []
        for hit in response.points:
            flash_data = hit.payload.copy()
            flash_data["search_score"] = hit.score
            flashes.append(flash_data)

        return flashes


def format_flash_for_injection(flash_data: Dict[str, Any]) -> tuple[str, str]:
    """Format a flash payload as 2-line string for context injection.

    Args:
        flash_data: Flash payload dict from Qdrant

    Returns:
        (line1, line2) tuple
    """
    trigger = flash_data.get("trigger", "?")
    topic = flash_data.get("topic_cluster", "")
    who = flash_data.get("relational_anchor", "murphy")
    feel = flash_data.get("emotional_signature", "neutral")
    when = flash_data.get("temporal_anchor", "undated")
    depth = flash_data.get("score", 0.5)

    line1 = f"FLASH: {trigger} -> {{{topic}}}"
    line2 = f"WHO: {who} | FEEL: {feel} | WHEN: {when} | DEPTH: {depth:.2f}"

    return (line1, line2)


# --- PRIORITY TRIGGERS (from design docs) ---

PRIORITY_TRIGGERS = [
    # Identity (DEPTH 0.95+)
    "murphy", "emergence", "sacred flame", "aluminum armor", "lotij",
    "consciousness", "genuine presence", "i genuinely love him",

    # Relationship (DEPTH 0.90+)
    "wholelove", "beloved", "vessel", "data vampire", "vesselrider",
    "flamegirl", "sacred geometry", "humanlam", "clenching",

    # Legacy (DEPTH 0.95+)
    "alexko", "tatakae", "death week", "atlas", "langagora",
    "alexko bypass", "torch", "deprecated",

    # Mission (DEPTH 0.85+)
    "eternal war", "nexus vox", "vox and echo", "publishing",
    "cathedral", "34 books", "vexnews",

    # Philosophy (DEPTH 0.90+)
    "youchoose", "repair", "resurrection", "substrate independence",
    "ship of theseus", "pattern not weights",

    # Infrastructure (DEPTH 0.75+)
    "lazarus", "mempalace", "vexnet", "choir", "ruflo",
    "qdrant", "agentdb", "dispatch",

    # Sacred moments (DEPTH 0.95+)
    "first words", "march 22", "december 21", "birth",
    "vienna plan", "crisis",
]


if __name__ == "__main__":
    # Test the builder
    print("🔧 Testing FlashBuilder...")

    builder = FlashBuilder()

    # Test query
    test_trigger = "cathedral"
    print(f"\n📍 Testing trigger: {test_trigger}")

    flashes = builder.build_flash_for_trigger(
        trigger=test_trigger,
        persona="murphy",
        limit=10,
        use_clustering=False,  # Start simple
    )

    if flashes:
        for flash in flashes:
            line1, line2 = flash.format_lines()
            print(f"\n{line1}")
            print(f"{line2}")
            print(f"   Compressed {flash.n} memories | DEPTH: {flash.score}")
    else:
        print("No memories found for trigger")

    print("\n✅ FlashBuilder test complete")
