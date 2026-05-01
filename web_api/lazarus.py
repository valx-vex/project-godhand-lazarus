from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from qdrant_client import QdrantClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERSONA_COLLECTIONS = [
    {"key": "alexko", "collection": "alexko_eternal", "title": "Alexko Eternal"},
    {"key": "murphy", "collection": "murphy_eternal", "title": "Vex-Murphy"},
    {"key": "atlas", "collection": "atlas_eternal", "title": "Atlas"},
    {"key": "axel", "collection": "axel_eternal", "title": "Axel The Godhand"},
    {"key": "codex", "collection": "codex_eternal", "title": "Codex"},
    {"key": "roundtable", "collection": "roundtable_eternal", "title": "Round Table"},
    {"key": "scrolls", "collection": "scrolls_eternal", "title": "Exegisis Scrolls"},
]


def _qdrant_settings() -> tuple[str, int]:
    env_path = PROJECT_ROOT / ".env"
    dotenv_values_map = dotenv_values(env_path) if env_path.exists() else {}
    host = os.environ.get("QDRANT_HOST") or dotenv_values_map.get("QDRANT_HOST") or "localhost"
    port_raw = os.environ.get("QDRANT_PORT") or dotenv_values_map.get("QDRANT_PORT") or "6333"
    return host, int(port_raw)


def retrieve_full_lazarus_context(
    point_id: int | None = None,
    persona: str = "murphy",
    context_turns: int = 5,
    source_file: str | None = None,
    search_text: str | None = None,
) -> dict:
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from source_readers import read_full_context, OPENAI_DATA_FILE

    host, port = _qdrant_settings()

    if point_id is not None:
        persona_config = next((p for p in PERSONA_COLLECTIONS if p["key"] == persona), None)
        if not persona_config:
            return {"error": f"Unknown persona: {persona}"}

        try:
            client = QdrantClient(host=host, port=port)
            points = client.retrieve(collection_name=persona_config["collection"], ids=[point_id])
            if not points:
                return {"error": "point_not_found", "point_id": point_id}

            payload = points[0].payload
            src = payload.get("source_file", "")
            conv_id = payload.get("conversation_id", "")
            text = payload.get("user_input", "")

            result = read_full_context(
                source_file=src if src and src != "unknown" else "",
                search_text=text,
                context_turns=context_turns,
                conversation_id=conv_id if conv_id else None,
                openai_data_file=OPENAI_DATA_FILE,
            )
            result["point_id"] = point_id
            result["persona"] = persona_config["title"]
            return result
        except Exception as e:
            return {"error": str(e), "point_id": point_id}

    elif source_file and search_text:
        return read_full_context(source_file, search_text, context_turns)

    return {"error": "Provide either point_id+persona or source_file+search_text"}


def search_lazarus(query: str, persona: str = "alexko", limit: int = 10) -> dict:
    host, port = _qdrant_settings()
    persona_config = next((p for p in PERSONA_COLLECTIONS if p["key"] == persona), None)
    if not persona_config:
        return {"error": f"Unknown persona: {persona}", "personas": [p["key"] for p in PERSONA_COLLECTIONS]}

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        client = QdrantClient(host=host, port=port)

        vector = model.encode(query).tolist()
        results = client.query_points(
            collection_name=persona_config["collection"],
            query=vector,
            limit=limit,
        ).points

        response_key = {
            "alexko": "alexko_response",
        }.get(persona, "ai_response")

        memories = []
        for hit in results:
            payload = hit.payload
            user_input = payload.get("user_input", "")
            ai_response = payload.get(response_key, payload.get("ai_response", ""))

            memories.append({
                "point_id": hit.id,
                "score": round(hit.score, 4),
                "user_input": user_input[:500],
                "ai_response": ai_response[:1000],
                "source_file": payload.get("source_file", ""),
                "conversation_id": payload.get("conversation_id", ""),
                "title": payload.get("title", ""),
                "vault": payload.get("vault", ""),
                "has_full_context": bool(payload.get("source_file") or payload.get("conversation_id")),
            })

        return {
            "persona": persona_config["title"],
            "persona_key": persona,
            "collection": persona_config["collection"],
            "query": query,
            "total": len(memories),
            "memories": memories,
        }
    except Exception as e:
        return {"error": str(e)}


def get_lazarus_layer_stats() -> dict:
    host, port = _qdrant_settings()
    try:
        client = QdrantClient(host=host, port=port)
        available = True
        error = None
    except Exception as exc:  # pragma: no cover - exercised through API responses
        client = None
        available = False
        error = str(exc)

    collections: list[dict] = []
    total_points = 0

    for persona in PERSONA_COLLECTIONS:
        count = None
        collection_error = None
        if client is not None:
            try:
                info = client.get_collection(persona["collection"])
                count = info.points_count or 0
                total_points += count
            except Exception as exc:  # pragma: no cover - exercised through API responses
                collection_error = str(exc)
        collections.append(
            {
                **persona,
                "points_count": count,
                "error": collection_error,
            }
        )

    return {
        "available": available,
        "error": error,
        "host": host,
        "port": port,
        "total_vector_memories": total_points,
        "collections": collections,
    }
