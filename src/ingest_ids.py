from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _normalize_part(part: Any) -> str:
    if part is None:
        return ""
    if isinstance(part, Path):
        return str(part.expanduser())
    return str(part).strip()


def stable_point_id(*parts: Any) -> int:
    """Return a deterministic Qdrant integer point id from stable source data."""
    payload = "\x1f".join(_normalize_part(part) for part in parts)
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def memory_point_id(
    source_file: str | Path | None,
    user_input: str,
    ai_response: str = "",
    conversation_id: str | None = None,
    turn_key: str | int | None = None,
) -> int:
    return stable_point_id(source_file, conversation_id, turn_key, user_input, ai_response)


def document_point_id(
    source_file: str | Path | None,
    title: str,
    body: str = "",
) -> int:
    return stable_point_id(source_file, title, body[:2048])
