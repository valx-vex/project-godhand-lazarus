"""
Source file readers for Lazarus full context retrieval.

Given a source_file path and search text from a Lazarus vector search result,
reads the original file and returns full untruncated conversation context
around the matching turn.

Supports: Claude JSONL, OpenAI JSON, Gemini JSON, Codex JSONL, Markdown.
"""

import json
import os
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional


class SourceFormat(Enum):
    CLAUDE_JSONL = "claude_jsonl"
    OPENAI_JSON = "openai_json"
    GEMINI_JSON = "gemini_json"
    CODEX_JSONL = "codex_jsonl"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"


@dataclass
class Turn:
    role: str
    content: str
    index: int
    metadata: dict


SEARCH_PATHS = [
    Path.home() / ".claude" / "projects",
    Path.home() / ".gemini" / "tmp",
    Path.home() / ".codex" / "sessions",
    Path.home() / "Documents" / "tosync" / ".gemini",
]

_openai_candidates = [
    Path(__file__).parent.parent / "data" / "conversations.json",
    Path.home() / "vex" / "vaults" / "exegisis" / "raw" / "openai-archive-2026-01-31" / "conversations.json",
]

OPENAI_DATA_FILE = os.environ.get("LAZARUS_OPENAI_DATA", "")
if not OPENAI_DATA_FILE:
    for candidate in _openai_candidates:
        if candidate.exists():
            OPENAI_DATA_FILE = str(candidate)
            break
    else:
        OPENAI_DATA_FILE = str(_openai_candidates[0])

_openai_cache: dict = {}


def detect_format(filepath: str) -> SourceFormat:
    p = Path(filepath)
    if not p.exists():
        return SourceFormat.UNKNOWN

    suffix = p.suffix.lower()
    if suffix == ".md":
        return SourceFormat.MARKDOWN

    if suffix == ".jsonl":
        try:
            with open(p, "r", encoding="utf-8") as f:
                first_line = ""
                for line in f:
                    line = line.strip()
                    if line:
                        first_line = line
                        break
                if not first_line:
                    return SourceFormat.UNKNOWN
                obj = json.loads(first_line)
                if obj.get("type") in ("response_item",):
                    return SourceFormat.CODEX_JSONL
                if "sessionId" in obj:
                    return SourceFormat.CODEX_JSONL
                return SourceFormat.CLAUDE_JSONL
        except Exception:
            return SourceFormat.UNKNOWN

    if suffix == ".json":
        try:
            with open(p, "r", encoding="utf-8") as f:
                start = f.read(200)
            if '"sessionId"' in start and '"messages"' in start:
                return SourceFormat.GEMINI_JSON
            if '"mapping"' in start or '"conversation_id"' in start:
                return SourceFormat.OPENAI_JSON
        except Exception:
            pass
        return SourceFormat.UNKNOWN

    return SourceFormat.UNKNOWN


def resolve_source_file(source_file: str) -> Optional[str]:
    p = Path(source_file)
    if p.exists():
        return str(p)

    basename = p.name
    for search_dir in SEARCH_PATHS:
        if not search_dir.exists():
            continue
        for match in search_dir.rglob(basename):
            if match.is_file():
                return str(match)

    return None


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(item["text"])
        return " ".join(parts)
    return str(content) if content else ""


def parse_claude_jsonl(filepath: str) -> list[Turn]:
    turns = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            messages = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        idx = 0
        for i in range(len(messages) - 1):
            a, b = messages[i], messages[i + 1]

            user_text = None
            ai_text = None

            if a.get("type") == "human" and b.get("type") == "assistant":
                user_text = a.get("content", "")
                ai_text = b.get("content", "")

            elif a.get("role") == "user" and b.get("role") == "assistant":
                user_text = a.get("content", "")
                ai_text = b.get("content", "")

            elif a.get("sender") == "human" and b.get("sender") in ("claude", "assistant"):
                user_text = a.get("message", a.get("content", ""))
                ai_text = b.get("message", b.get("content", ""))

            elif a.get("type") == "user" and b.get("type") == "assistant":
                user_text = _extract_text(a.get("message", {}).get("content", ""))
                ai_text = _extract_text(b.get("message", {}).get("content", ""))

            if user_text and ai_text:
                user_text = _extract_text(user_text)
                ai_text = _extract_text(ai_text)
                if user_text.strip() and ai_text.strip():
                    turns.append(Turn(role="user", content=user_text, index=idx, metadata={"line": i}))
                    turns.append(Turn(role="assistant", content=ai_text, index=idx + 1, metadata={"line": i + 1}))
                    idx += 2

    except Exception as e:
        turns.append(Turn(role="error", content=f"Parse error: {e}", index=0, metadata={}))

    return turns


def parse_gemini_json(filepath: str) -> list[Turn]:
    turns = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = data.get("messages", [])
        idx = 0
        for msg in messages:
            role = msg.get("type", msg.get("role", "unknown"))
            content = msg.get("content", "")
            thinking = msg.get("thoughts", [])
            thinking_text = ""
            if thinking:
                thinking_text = " | ".join(
                    t.get("description", t.get("subject", ""))
                    for t in thinking if isinstance(t, dict)
                )

            mapped_role = "user" if role == "user" else "assistant"
            full_content = content
            if thinking_text:
                full_content = f"{content}\n[Thinking: {thinking_text}]"

            turns.append(Turn(
                role=mapped_role,
                content=full_content,
                index=idx,
                metadata={"session_id": data.get("sessionId", ""), "original_role": role},
            ))
            idx += 1

    except Exception as e:
        turns.append(Turn(role="error", content=f"Parse error: {e}", index=0, metadata={}))

    return turns


def parse_codex_jsonl(filepath: str) -> list[Turn]:
    turns = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            messages = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        idx = 0
        for i in range(len(messages) - 1):
            a, b = messages[i], messages[i + 1]

            user_text = None
            ai_text = None

            a_role = a.get("role", "")
            b_role = b.get("role", "")

            if a.get("type") == "response_item":
                a_role = a.get("payload", {}).get("role", a_role)
            if b.get("type") == "response_item":
                b_role = b.get("payload", {}).get("role", b_role)

            if not a_role:
                a_role = a.get("type", "")
            if not b_role:
                b_role = b.get("type", "")

            if a_role == "user" and b_role in ("assistant", "response_item"):
                user_text = _extract_text(a.get("content", a.get("message", {}).get("content", "")))
                ai_text = _extract_text(b.get("content", b.get("payload", {}).get("content",
                    b.get("message", {}).get("content", ""))))

            if user_text and ai_text and user_text.strip() and ai_text.strip():
                turns.append(Turn(role="user", content=user_text, index=idx, metadata={"line": i}))
                turns.append(Turn(role="assistant", content=ai_text, index=idx + 1, metadata={"line": i + 1}))
                idx += 2

    except Exception as e:
        turns.append(Turn(role="error", content=f"Parse error: {e}", index=0, metadata={}))

    return turns


def _load_openai_data(data_file: str) -> dict:
    global _openai_cache
    try:
        mtime = os.path.getmtime(data_file)
    except OSError:
        return {}

    cached = _openai_cache.get(data_file)
    if cached and cached["mtime"] == mtime:
        return cached["index"]

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    index = {}
    for conv in data:
        cid = conv.get("id", "")
        if cid:
            index[cid] = conv

    _openai_cache[data_file] = {"mtime": mtime, "index": index}
    return index


def parse_openai_conversation(data_file: str, conversation_id: str) -> list[Turn]:
    turns = []
    try:
        index = _load_openai_data(data_file)
        conv = index.get(conversation_id)
        if not conv:
            return [Turn(role="error", content=f"Conversation {conversation_id} not found", index=0, metadata={})]

        mapping = conv.get("mapping", {})
        messages = []
        for key, value in mapping.items():
            message = value.get("message")
            if message and message.get("content"):
                role = message["author"]["role"]
                content_parts = message["content"].get("parts", [])
                if not content_parts:
                    continue
                text = "".join(str(p) for p in content_parts if isinstance(p, str))
                if text.strip():
                    messages.append({
                        "role": role,
                        "text": text,
                        "time": message.get("create_time", 0),
                    })

        messages.sort(key=lambda x: x["time"] or 0)

        for i, msg in enumerate(messages):
            turns.append(Turn(
                role=msg["role"],
                content=msg["text"],
                index=i,
                metadata={
                    "conversation_id": conversation_id,
                    "title": conv.get("title", ""),
                    "timestamp": msg["time"],
                },
            ))

    except Exception as e:
        turns.append(Turn(role="error", content=f"Parse error: {e}", index=0, metadata={}))

    return turns


def parse_markdown(filepath: str) -> list[Turn]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return [Turn(role="document", content=content, index=0, metadata={"source_file": filepath})]
    except Exception as e:
        return [Turn(role="error", content=f"Read error: {e}", index=0, metadata={})]


def find_matching_turn(turns: list[Turn], search_text: str) -> int:
    if not turns or not search_text:
        return 0

    search_lower = search_text.lower().strip()
    if len(search_lower) > 200:
        search_lower = search_lower[:200]

    best_idx = 0
    best_score = 0.0

    for i, turn in enumerate(turns):
        content_lower = turn.content.lower()
        if search_lower in content_lower:
            return i

    for i, turn in enumerate(turns):
        content_lower = turn.content.lower()
        score = SequenceMatcher(None, search_lower, content_lower[:500]).ratio()
        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def extract_context(turns: list[Turn], center_index: int, context_turns: int = 5) -> list[Turn]:
    start = max(0, center_index - context_turns)
    end = min(len(turns), center_index + context_turns + 1)
    return turns[start:end]


def read_full_context(
    source_file: str,
    search_text: str,
    context_turns: int = 5,
    conversation_id: Optional[str] = None,
    openai_data_file: Optional[str] = None,
) -> dict:
    if conversation_id and not source_file:
        data_file = openai_data_file or OPENAI_DATA_FILE
        if not Path(data_file).exists():
            return {"error": "openai_data_not_found", "data_file": data_file}

        turns = parse_openai_conversation(data_file, conversation_id)
        if turns and turns[0].role == "error":
            return {"error": turns[0].content}

        match_idx = find_matching_turn(turns, search_text)
        context = extract_context(turns, match_idx, context_turns)

        return {
            "source_type": "openai_json",
            "conversation_id": conversation_id,
            "total_turns": len(turns),
            "matched_turn_index": match_idx,
            "context_range": [context[0].index, context[-1].index] if context else [],
            "turns": [asdict(t) for t in context],
        }

    resolved = resolve_source_file(source_file) if source_file else None
    if not resolved:
        return {
            "error": "source_file_not_found",
            "path": source_file,
            "suggestion": "File may have been moved or deleted",
        }

    fmt = detect_format(resolved)

    if fmt == SourceFormat.CLAUDE_JSONL:
        turns = parse_claude_jsonl(resolved)
    elif fmt == SourceFormat.GEMINI_JSON:
        turns = parse_gemini_json(resolved)
    elif fmt == SourceFormat.CODEX_JSONL:
        turns = parse_codex_jsonl(resolved)
    elif fmt == SourceFormat.MARKDOWN:
        turns = parse_markdown(resolved)
    elif fmt == SourceFormat.OPENAI_JSON:
        turns = parse_openai_conversation(resolved, conversation_id or "")
    else:
        return {"error": "unsupported_format", "source_file": resolved, "detected_format": fmt.value}

    if not turns:
        return {"error": "no_turns_found", "source_file": resolved}

    if turns[0].role == "error":
        return {"error": turns[0].content, "source_file": resolved}

    match_idx = find_matching_turn(turns, search_text)
    context = extract_context(turns, match_idx, context_turns)

    return {
        "source_type": fmt.value,
        "source_file": resolved,
        "total_turns": len(turns),
        "matched_turn_index": match_idx,
        "context_range": [context[0].index, context[-1].index] if context else [],
        "turns": [asdict(t) for t in context],
    }
