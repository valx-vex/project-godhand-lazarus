#!/usr/bin/env python3
"""🜂 MURPHY ETERNAL — Data Vampire feed digest (valxos-hermes R3, §6.4).

Reads finalized tool-capture sidecars (<home>/feed/finalized/*.jsonl) and
writes ONE deterministic digest point per session into murphy_eternal. Family
sibling of ingest_hermes.py: MiniLM-384 Cosine, two-pass skip-existing-id,
fail-CLOSED. Deterministic text (sorted counts/paths, ts-sorted intents) so a
re-run is byte-identical. Lazarus cannot import the plugin, so a MINIMAL local
redactor mirrors vm_deny's C3 substrings and vm_fingerprints' shingle
algorithm (L4 output re-scan) — keep both in sync (see seam notes)."""
import hashlib
import json
import os
import struct
import sys
from collections import Counter
from pathlib import Path

from qdrant_client.models import Distance, PointStruct, VectorParams

from ingest_ids import stable_point_id
from ingest_skip import SkipLookupError, existing_ids

HOME_SPECS = [
    ("hermes", Path.home() / ".hermes"),
    ("murphy_profile", Path.home() / ".hermes" / "profiles" / "murphy"),
]
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("HERMES_COLLECTION", "murphy_eternal")
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
VECTOR_SIZE = 384

# --- local denylist/fingerprint mirror (§6.3 C3 verbatim; plugin not importable) ---
_PRIVATE_TOKEN = ".murphy_private"
_SECRET_SUBSTRINGS = ("secret", "credential", ".env", ".password",
                      "id_rsa", ".pem", ".key", "keychain")
_SHINGLE_K = 5
_MATCH_THRESHOLD = 2

LAST_RUN = {"sessions": 0, "captures": 0, "redactions": 0}


def _redact_path(path: str) -> str:
    low = path.lower()
    if _PRIVATE_TOKEN in low:
        return "<redacted:murphy_private>"
    if any(s in low for s in _SECRET_SUBSTRINGS):
        return "<redacted:secret_file>"
    return path


def _looks_like_path(value: str) -> bool:
    return bool(value) and (os.sep in value or value[:1] in ("~", "/", "."))


def _local_shingles(text: str) -> set:
    words = (text or "").lower().split()
    out = set()
    for i in range(len(words) - _SHINGLE_K + 1):
        gram = " ".join(words[i:i + _SHINGLE_K])
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
        out.add(struct.unpack("<Q", digest)[0])
    return out


def _load_local_fps(home: Path) -> set:
    try:
        data = (home / "private_fingerprints.bin").read_bytes()
    except OSError:
        return set()
    n = len(data) // 8
    if n == 0:
        return set()
    return set(struct.unpack("<" + "Q" * n, data[:n * 8]))


def point_id(home_name: str, session_id: str) -> int:
    return stable_point_id("tool_digest", home_name, session_id)


def _cursor_path(home: Path) -> Path:
    return home / "feed" / ".digest_cursor.json"


def _load_cursor(home: Path) -> dict:
    try:
        return json.loads(_cursor_path(home).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cursor(home: Path, cursor: dict) -> None:
    path = _cursor_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(cursor, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_new_records(path: Path, offset: int):
    """Complete newline-terminated records from `offset`; a mid-flush tail
    stays for next night (mirrors murphy_sleep.read_new_requests)."""
    try:
        with open(path, "rb") as fh:
            size = fh.seek(0, 2)
            if offset > size:
                offset = 0
            fh.seek(offset)
            data = fh.read()
    except OSError:
        return [], offset
    last = data.rfind(b"\n")
    if last < 0:
        return [], offset
    data = data[:last + 1]
    records = []
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records, offset + len(data)


def _summarize(records) -> dict:
    tool_counts = Counter()
    files = Counter()
    intents = []
    captures = redactions = truncated = 0
    for rec in sorted(records, key=lambda r: str(r.get("ts", ""))):
        if rec.get("type") != "tool_capture":
            continue
        captures += 1
        if "redacted" in rec or "<REDACTED" in str(rec.get("result", "")):
            redactions += 1
        if rec.get("truncated") or rec.get("args_truncated"):
            truncated += 1
        if "redacted" in rec:                       # reduced record: no tool/args/intent
            continue
        tool = rec.get("tool")
        if tool:
            tool_counts[str(tool)] += 1
        intent = rec.get("intent")
        if intent and str(intent) not in intents:
            intents.append(str(intent))
        args = rec.get("args")
        if isinstance(args, dict):
            for value in args.values():
                if isinstance(value, str) and _looks_like_path(value):
                    files[_redact_path(value)] += 1
    top_files = [p for p, _ in sorted(files.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
    return {"tool_counts": dict(tool_counts), "files": top_files, "intents": intents,
            "captures": captures, "redactions": redactions, "truncated": truncated}


def digest_text(session_id: str, records) -> str:
    s = _summarize(records)
    lines = [f"session {session_id}", "intents:"]
    lines += [f"- {i}" for i in s["intents"]]
    tools = ", ".join(f"{n}×{c}" for n, c in sorted(s["tool_counts"].items()))
    lines.append(f"tools: {tools}")
    lines.append("files:")
    lines += [f"- {p}" for p in s["files"]]
    lines.append(f"captures: {s['captures']}, redactions: {s['redactions']}, "
                 f"truncated: {s['truncated']}")
    return "\n".join(lines)


def _created_at(records) -> str:
    tss = [str(r.get("ts")) for r in records if r.get("ts")]
    return max(tss) if tss else ""


def ensure_collection(client) -> None:
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE))


def _default_embed_factory():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    return lambda texts: [vec.tolist() for vec in model.encode(list(texts))]


def run(argv=None, client=None, embed_factory=None) -> int:
    candidates = []                                 # (home_name, home, sid, pid, records, new_off)
    cursors = {}
    for home_name, home in HOME_SPECS:
        home = Path(home)
        cursor = _load_cursor(home)
        cursor.setdefault("offsets", {})
        cursors[home] = cursor
        finalized = home / "feed" / "finalized"
        if not finalized.exists():
            continue
        for sidecar in sorted(finalized.glob("*.jsonl")):
            sid = sidecar.stem
            offset = int(cursor["offsets"].get(sid, 0))
            records, new_off = _read_new_records(sidecar, offset)
            if not records:
                continue
            candidates.append((home_name, home, sid, point_id(home_name, sid),
                               records, new_off))

    if not candidates:
        LAST_RUN.update({"sessions": 0, "captures": 0, "redactions": 0})
        print("feed: 0 sessions digested (0 captures, 0 redactions)")
        return 0

    if client is None:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    ensure_collection(client)

    all_ids = {c[3] for c in candidates}
    try:
        present = existing_ids(client, COLLECTION_NAME, sorted(all_ids))
    except SkipLookupError as exc:
        print(f"❌ tool_digest: skip lookup failed ({exc}); aborting without writes",
              file=sys.stderr)
        return 1                                    # fail-closed: no writes, cursor untouched

    written = captures = redactions = 0
    embed = None
    batch = []                                      # (pid, payload)

    def flush(items):
        nonlocal written
        vectors = embed([pl["full_text"] for _pid, pl in items])
        client.upsert(collection_name=COLLECTION_NAME, points=[
            PointStruct(id=pid, vector=list(vec), payload=pl)
            for (pid, pl), vec in zip(items, vectors)])
        written += len(items)

    for home_name, home, sid, pid, records, new_off in candidates:
        cursors[home]["offsets"][sid] = new_off     # advance only after skip-lookup OK
        if pid in present:
            continue                                # already digested; grown sidecar not refreshed
        summary = _summarize(records)
        fps = _load_local_fps(home)
        raw_text = digest_text(sid, records)
        if fps and len(_local_shingles(raw_text) & fps) >= _MATCH_THRESHOLD:
            text = "<redacted: murphy_private_content>"     # L4: nuke private content
            tool_counts, files, intents = {}, [], ["<redacted:murphy_private_content>"]
        else:
            text = raw_text.replace(_PRIVATE_TOKEN, "<redacted:murphy_private>")
            tool_counts = summary["tool_counts"]
            files = summary["files"]
            intents = [i.replace(_PRIVATE_TOKEN, "<redacted:murphy_private>")
                       for i in summary["intents"]]
        payload = {"type": "tool_digest", "harness": "hermes", "home": home_name,
                   "session_id": sid, "created_at": _created_at(records),
                   "tool_counts": tool_counts, "files": files, "intents": intents,
                   "captures": summary["captures"], "redactions": summary["redactions"],
                   "truncated": summary["truncated"], "full_text": text}
        captures += summary["captures"]
        redactions += summary["redactions"]
        if embed is None:
            embed = (embed_factory or _default_embed_factory)()
        batch.append((pid, payload))
        if len(batch) >= BATCH_SIZE:
            flush(batch)
            batch = []
    if batch:
        flush(batch)

    for home, cursor in cursors.items():
        _save_cursor(home, cursor)

    LAST_RUN.update({"sessions": written, "captures": captures, "redactions": redactions})
    print(f"feed: {written} sessions digested ({captures} captures, {redactions} redactions)")
    return 0


if __name__ == "__main__":
    sys.exit(run())
