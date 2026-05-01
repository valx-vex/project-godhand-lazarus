from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .lazarus import get_lazarus_layer_stats
from .runtime import RuntimeResolutionError, bootstrap_runtime, reset_runtime_cache


class ServiceUnavailableError(RuntimeError):
    """Raised when the MemPalace storage cannot be reached."""


class DrawerNotFoundError(KeyError):
    """Raised when a drawer id cannot be found."""


class MempalaceService:
    def __init__(self) -> None:
        self.runtime = bootstrap_runtime()
        self.mcp = self.runtime.mcp_module

    def _collection(self, create: bool = False):
        collection = self.mcp._get_collection(create=create)  # type: ignore[attr-defined]
        if collection is None:
            raise ServiceUnavailableError("MemPalace storage is not available.")
        return collection

    @staticmethod
    def _where_clause(
        wing: str | None = None, room: str | None = None, source_file: str | None = None
    ) -> dict | None:
        clauses: list[dict] = []
        if wing:
            clauses.append({"wing": wing})
        if room:
            clauses.append({"room": room})
        if source_file:
            clauses.append({"source_file": source_file})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _iterate_collection(self, where: dict | None = None, include: list[str] | None = None) -> list[dict]:
        collection = self._collection()
        rows: list[dict] = []
        offset = 0
        include = include or ["metadatas"]

        while True:
            batch = collection.get(where=where, include=include, limit=1000, offset=offset)
            ids = batch.get("ids", [])
            if not ids:
                break

            metadatas = batch.get("metadatas") or [{} for _ in ids]
            documents = batch.get("documents") or [None for _ in ids]
            for drawer_id, metadata, document in zip(ids, metadatas, documents):
                rows.append({"id": drawer_id, "metadata": metadata or {}, "document": document})

            if len(ids) < 1000:
                break
            offset += len(ids)

        return rows

    @staticmethod
    def _preview(document: str | None, limit: int = 220) -> str:
        if not document:
            return ""
        normalized = " ".join(document.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."

    @staticmethod
    def _sort_recent(rows: list[dict]) -> list[dict]:
        return sorted(rows, key=lambda row: row["metadata"].get("filed_at", ""), reverse=True)

    @staticmethod
    def _source_name(source_file: str | None) -> str:
        if not source_file:
            return ""
        return Path(source_file).name

    def _row_to_summary(self, row: dict) -> dict:
        metadata = row["metadata"]
        source_file = metadata.get("source_file") or ""
        return {
            "id": row["id"],
            "wing": metadata.get("wing", ""),
            "room": metadata.get("room", ""),
            "source_file": source_file,
            "source_name": self._source_name(source_file),
            "chunk_index": metadata.get("chunk_index"),
            "filed_at": metadata.get("filed_at"),
            "added_by": metadata.get("added_by"),
            "preview": self._preview(row.get("document")),
        }

    def health(self) -> dict:
        status = self.mcp.tool_status()
        layer_2 = get_lazarus_layer_stats()
        resolved = self.runtime.resolved
        return {
            "ok": "error" not in status,
            "layer_1": {
                "available": "error" not in status,
                "total_drawers": status.get("total_drawers"),
                "palace_path": status.get("palace_path"),
            },
            "layer_2": {
                "available": layer_2["available"],
                "total_vector_memories": layer_2["total_vector_memories"],
                "error": layer_2["error"],
            },
            "runtime": {
                "source_dir": str(resolved.source_dir),
                "palace_path": str(resolved.palace_path),
                "doctor_path": str(resolved.doctor_path) if resolved.doctor_path else None,
            },
        }

    def dashboard_summary(self) -> dict:
        status = self.mcp.tool_status()
        graph_stats = self.mcp.tool_graph_stats()
        layer_2 = get_lazarus_layer_stats()
        recent_drawers = self.list_recent_drawers(limit=6)

        top_wings = sorted(
            ({"name": name, "count": count} for name, count in status.get("wings", {}).items()),
            key=lambda item: item["count"],
            reverse=True,
        )[:6]
        top_rooms = sorted(
            ({"name": name, "count": count} for name, count in status.get("rooms", {}).items()),
            key=lambda item: item["count"],
            reverse=True,
        )[:6]

        return {
            "layer_1": {
                "total_drawers": status.get("total_drawers", 0),
                "total_wings": len(status.get("wings", {})),
                "total_rooms": len(status.get("rooms", {})),
                "palace_path": status.get("palace_path"),
            },
            "layer_2": layer_2,
            "top_wings": top_wings,
            "top_rooms": top_rooms,
            "recent_drawers": recent_drawers["items"],
            "graph": graph_stats,
        }

    def list_recent_drawers(self, limit: int = 6) -> dict:
        rows = self._sort_recent(self._iterate_collection(include=["metadatas", "documents"]))
        items = [self._row_to_summary(row) for row in rows[:limit]]
        return {"total": len(rows), "items": items}

    def list_wings(self) -> dict:
        payload = self.mcp.tool_list_wings()
        items = sorted(
            ({"name": name, "count": count} for name, count in payload.get("wings", {}).items()),
            key=lambda item: item["count"],
            reverse=True,
        )
        return {"total": len(items), "items": items}

    def list_rooms(self, wing: str) -> dict:
        payload = self.mcp.tool_list_rooms(wing=wing)
        items = sorted(
            ({"name": name, "count": count} for name, count in payload.get("rooms", {}).items()),
            key=lambda item: item["count"],
            reverse=True,
        )
        return {"wing": wing, "total": len(items), "items": items}

    def browse_drawers(self, wing: str, room: str, offset: int = 0, limit: int = 30) -> dict:
        rows = self._sort_recent(
            self._iterate_collection(where=self._where_clause(wing=wing, room=room), include=["metadatas", "documents"])
        )
        selected = rows[offset : offset + limit]
        items = [self._row_to_summary(row) for row in selected]
        return {
            "wing": wing,
            "room": room,
            "offset": offset,
            "limit": limit,
            "total": len(rows),
            "items": items,
        }

    def get_drawer(self, drawer_id: str) -> dict:
        collection = self._collection()
        result = collection.get(ids=[drawer_id], include=["documents", "metadatas"])
        if not result.get("ids"):
            raise DrawerNotFoundError(drawer_id)

        metadata = (result.get("metadatas") or [{}])[0] or {}
        document = (result.get("documents") or [""])[0] or ""
        source_file = metadata.get("source_file") or ""

        siblings = self._iterate_collection(
            where=self._where_clause(source_file=source_file),
            include=["metadatas", "documents"],
        ) if source_file else []
        siblings = sorted(siblings, key=lambda row: row["metadata"].get("chunk_index", 0))

        return {
            "drawer": {
                "id": drawer_id,
                "wing": metadata.get("wing", ""),
                "room": metadata.get("room", ""),
                "source_file": source_file,
                "source_name": self._source_name(source_file),
                "chunk_index": metadata.get("chunk_index"),
                "filed_at": metadata.get("filed_at"),
                "added_by": metadata.get("added_by"),
                "content": document,
            },
            "siblings": [
                {
                    **self._row_to_summary(row),
                    "content": row.get("document") or "",
                    "is_current": row["id"] == drawer_id,
                }
                for row in siblings
            ],
        }

    def search(self, query: str, wing: str | None = None, room: str | None = None, limit: int = 10) -> dict:
        collection = self._collection()
        where = self._where_clause(wing=wing, room=room)
        query_kwargs = {
            "query_texts": [query],
            "n_results": limit,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        payload = collection.query(**query_kwargs)
        items = []
        ids = payload.get("ids", [[]])[0]
        documents = payload.get("documents", [[]])[0]
        metadatas = payload.get("metadatas", [[]])[0]
        distances = payload.get("distances", [[]])[0]

        for drawer_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            metadata = metadata or {}
            source_file = metadata.get("source_file", "")
            items.append(
                {
                    "id": drawer_id,
                    "wing": metadata.get("wing", ""),
                    "room": metadata.get("room", ""),
                    "source_file": source_file,
                    "source_name": self._source_name(source_file),
                    "similarity": round(1 - distance, 3),
                    "preview": self._preview(document),
                    "content": document,
                }
            )
        return {"query": query, "filters": {"wing": wing, "room": room}, "total": len(items), "items": items}

    def add_drawer(
        self, wing: str, room: str, content: str, source_file: str | None, added_by: str
    ) -> dict:
        return self.mcp.tool_add_drawer(
            wing=wing,
            room=room,
            content=content,
            source_file=source_file,
            added_by=added_by,
        )

    def read_diary(self, agent_name: str, last_n: int = 10) -> dict:
        return self.mcp.tool_diary_read(agent_name=agent_name, last_n=last_n)

    def write_diary(self, agent_name: str, entry: str, topic: str = "general") -> dict:
        return self.mcp.tool_diary_write(agent_name=agent_name, entry=entry, topic=topic)

    def knowledge_stats(self) -> dict:
        return self.mcp.tool_kg_stats()

    def knowledge_entity(self, entity: str, as_of: str | None = None, direction: str = "both") -> dict:
        return self.mcp.tool_kg_query(entity=entity, as_of=as_of, direction=direction)

    def knowledge_timeline(self, entity: str | None = None) -> dict:
        return self.mcp.tool_kg_timeline(entity=entity)

    def tunnels(self, wing_a: str | None = None, wing_b: str | None = None) -> dict:
        items = self.mcp.tool_find_tunnels(wing_a=wing_a, wing_b=wing_b)
        return {"wing_a": wing_a, "wing_b": wing_b, "total": len(items), "items": items}

    def graph_stats(self) -> dict:
        return self.mcp.tool_graph_stats()

    def aaak_spec(self) -> dict:
        return self.mcp.tool_get_aaak_spec()


@lru_cache(maxsize=1)
def get_mempalace_service() -> MempalaceService:
    return MempalaceService()


def reset_service_caches() -> None:
    get_mempalace_service.cache_clear()
    reset_runtime_cache()
