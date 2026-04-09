#!/usr/bin/env python3
"""
Export a Qdrant collection into JSONL suitable for LoRA / SFT.

Default output format:
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}], "meta": {...}}
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from qdrant_client import QdrantClient


_REDACTIONS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-REDACTED"),
    (re.compile(r"(?i)anthropic[_-]?api[_-]?key\\s*[:=]\\s*['\\\"]?[A-Za-z0-9_-]{10,}"), "ANTHROPIC_API_KEY=REDACTED"),
    (re.compile(r"(?i)openai[_-]?api[_-]?key\\s*[:=]\\s*['\\\"]?[A-Za-z0-9_-]{10,}"), "OPENAI_API_KEY=REDACTED"),
    (re.compile(r"AIzaSy[A-Za-z0-9_-]{20,}"), "AIzaSyREDACTED"),
)


def _redact(text: str) -> str:
    out = text
    for pat, repl in _REDACTIONS:
        out = pat.sub(repl, out)
    return out


def _extract_pair(payload: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    user = (payload.get("user_input") or payload.get("user") or "").strip()
    assistant = (
        payload.get("valther")
        or payload.get("assistant")
        or payload.get("alexko_response")
        or payload.get("ai_response")
        or payload.get("ai")
        or ""
    ).strip()
    if not user or not assistant:
        return None
    return user, assistant


def _iter_points(client: QdrantClient, collection: str, batch: int) -> Iterable[Dict[str, Any]]:
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            limit=batch,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )
        for p in points:
            yield {"id": getattr(p, "id", None), "payload": p.payload or {}}
        if next_offset is None:
            break


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--qdrant-host", default="localhost")
    ap.add_argument("--qdrant-port", type=int, default=6333)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--max", type=int, default=0, help="Max records (0 = all)")
    ap.add_argument("--no-redact", action="store_true")
    args = ap.parse_args()

    client = QdrantClient(host=args.qdrant_host, port=args.qdrant_port)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for item in _iter_points(client, args.collection, args.batch):
            payload = item["payload"]
            pair = _extract_pair(payload)
            if not pair:
                continue
            user, assistant = pair

            if not args.no_redact:
                user = _redact(user)
                assistant = _redact(assistant)

            row = {
                "messages": [
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant},
                ],
                "meta": {
                    "collection": args.collection,
                    "source_file": payload.get("source_file"),
                    "conversation_id": payload.get("conversation_id"),
                    "title": payload.get("title"),
                    "timestamp": payload.get("timestamp"),
                    "id": item.get("id"),
                },
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
            if args.max and n >= args.max:
                break

    print(f"wrote {n} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

