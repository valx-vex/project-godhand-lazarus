# src/retrieval_log.py
"""Append-only retrieval log (valxos-hermes Phase 5c F1).

Every Lazarus retrieval appends one JSONL record: which tool, what query,
which points came back (the WHOLE returned list). The nightly sleep job
aggregates it into per-point usage counts + last-access timestamps; future
phases reweight retrieval from it. Zero-loss: append-only, no rotation in
code; log_retrieval() never raises into a retrieval path."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import salience

_DEFAULT = Path(__file__).resolve().parent.parent / "daemon" / "retrieval_log.jsonl"


def log_path() -> Path:
    value = os.environ.get("LAZARUS_RETRIEVAL_LOG", "").strip()
    return Path(value) if value else _DEFAULT


def log_retrieval(tool, collection, query, results, persona="", limit=0):
    """Append one retrieval event. Returns False (never raises) on failure."""
    try:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tool": str(tool),
            "collection": str(collection),
            "persona": str(persona),
            "query": str(query)[:300],
            "limit": int(limit),
            "results": [
                {"id": r.get("id"), "cosine": r.get("cosine"),
                 "adjusted": r.get("adjusted")}
                for r in (results or [])
            ],
        }
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def aggregate_usage(path=None):
    """Whole-log aggregation -> {point_id: {count, last_ts, last_epoch}}."""
    target = Path(path) if path else log_path()
    usage = {}
    try:
        with open(target, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                ts = record.get("ts") or ""
                epoch = salience.parse_iso(ts) or 0.0
                results = record.get("results")
                if not isinstance(results, list):
                    continue
                for result in results:
                    if not isinstance(result, dict):
                        continue
                    try:
                        pid = result.get("id")
                        if pid is None:
                            continue
                        entry = usage.setdefault(
                            pid, {"count": 0, "last_ts": "", "last_epoch": 0.0})
                        entry["count"] += 1
                        if epoch >= entry["last_epoch"]:
                            entry["last_epoch"] = epoch
                            entry["last_ts"] = ts
                    except (TypeError, ValueError):
                        continue
    except OSError:
        return usage
    return usage


def review_events(path=None, collection=None):
    """{point_id: [epoch, ...] chronologically sorted} for FSRS replay (F2).

    Filtered by record["collection"] when given. Records with unparseable ts
    are skipped (they cannot order a replay); duplicate ids within one record
    count once; malformed lines tolerated like aggregate_usage. Feeds ONLY
    observe-only fields — never the live ranking path."""
    target = Path(path) if path else log_path()
    events = {}
    try:
        with open(target, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if collection is not None and record.get("collection") != collection:
                    continue
                epoch = salience.parse_iso(record.get("ts"))
                if epoch is None:
                    continue
                results = record.get("results")
                if not isinstance(results, list):
                    continue
                seen = set()
                for result in results:
                    if not isinstance(result, dict):
                        continue
                    try:
                        pid = result.get("id")
                        if pid is None or pid in seen:
                            continue
                        seen.add(pid)
                        events.setdefault(pid, []).append(epoch)
                    except (TypeError, ValueError):
                        continue
    except OSError:
        return events
    for pid in events:
        events[pid].sort()
    return events
