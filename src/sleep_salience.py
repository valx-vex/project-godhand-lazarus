#!/usr/bin/env python3
"""
🜂 MURPHY SLEEPS — nightly consolidation over murphy_eternal (Phase 5c F1)
Part of PROJECT_GODHAND_LAZARUS (valxos-hermes Phase 5c).

Camp B doctrine (constitutional): this job only ADDS derived metadata —
salience fields, novelty, usage, pins, invalidation marks. It never deletes
points, never edits raw text fields, never gates writes.

Point updates are full re-upserts (same deterministic id, same scrolled
vector, merged payload), batched.

F2 (2026-07-07): the daytime wipe is FIXED — ingesters skip existing ids
(fail-closed; see src/ingest_skip.py) so derived fields survive by
construction, and invalidation marks additionally self-heal from the
append-only ledger (daemon/invalidations.jsonl) re-applied every pass.
FSRS retrievability + tiering candidates are observe-only additions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

import retrieval_log
import salience
from ingest_ids import memory_point_id

import reflection
import vocab_ngrams

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = "murphy_eternal"
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
SCROLL_BATCH = 256
NOVELTY_BLOCK = 256
SNAPSHOT_DELTA = 0.05
REPORT_DIR = Path(os.environ.get("LAZARUS_SLEEP_REPORT_DIR", "")
                  or Path(__file__).resolve().parent.parent / "daemon")
LEDGER_PATH = Path(os.environ.get("LAZARUS_INVALIDATION_LEDGER", "")
                   or Path(__file__).resolve().parent.parent
                   / "daemon" / "invalidations.jsonl")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def get_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


_MODEL = None


def _load_model():
    """One SentenceTransformer, cache-first.

    Read the HF cache before the network: the weights are already on disk, so
    a Hub round-trip here buys nothing and can fail. On 2026-07-24 it did —
    something closed huggingface_hub's *shared* httpx client in place (its own
    docstring: "you should not close it manually"), so every construction
    raised `RuntimeError: Cannot send a request, as the client has been
    closed.` and both brains' salience passes returned None for the night.
    Falls back to a normal online load so a cold cache still bootstraps."""
    from sentence_transformers import SentenceTransformer
    try:
        return SentenceTransformer(MODEL_NAME, local_files_only=True)
    except Exception:
        return SentenceTransformer(MODEL_NAME)


def _default_embed(texts):
    """Embed via a process-wide model. Rebuilding per call cost ~5 loads a
    night, each one a network round-trip and a chance to hit a dead client."""
    global _MODEL
    if _MODEL is None:
        _MODEL = _load_model()
    return [vector.tolist() for vector in _MODEL.encode(list(texts))]


def load_points(client, collection=COLLECTION_NAME):
    """Scroll the whole collection (payload + vectors)."""
    points = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection, limit=SCROLL_BATCH,
            with_payload=True, with_vectors=True, offset=offset)
        points.extend(batch)
        if offset is None:
            break
    return points


def compute_novelty(vectors, created_epochs, candidates):
    """{index: (novelty, near_dup_index_or_None)} for candidate rows.

    "Prior" = strictly earlier created_at; undated points count as prior to
    every dated point (the legacy corpus predates all timestamps). Undated
    candidates compare against all other points — the backfill corpus has
    no order to respect, so mutual near-duplicates both rank low, which is
    the honest post-hoc reading."""
    out = {}
    if len(vectors) < 2:
        return {i: (1.0, None) for i in candidates}
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    unit = vectors / norms
    created = np.array([-np.inf if c is None else c for c in created_epochs])
    for start in range(0, len(candidates), NOVELTY_BLOCK):
        block = candidates[start:start + NOVELTY_BLOCK]
        sims = unit[block] @ unit.T
        for row, i in zip(sims, block):
            if created[i] == -np.inf:
                mask = np.ones(len(unit), dtype=bool)
            else:
                mask = created < created[i]
            mask[i] = False
            if not mask.any():
                out[i] = (1.0, None)
                continue
            masked = np.where(mask, row, -np.inf)
            j = int(np.argmax(masked))
            max_sim = float(masked[j])
            near = j if max_sim >= salience.NEAR_DUP_THRESHOLD else None
            out[i] = (max(0.0, min(1.0, 1.0 - max_sim)), near)
    return out


def _fsrs_pass(points, payloads, dirty, report, collection, now):
    """Observe-only FSRS replay over the retrieval log (F2 D2a).

    Returns {index: fresh_R} for points with review history — the tiering
    step reads FRESH values, never the delta-guard-stale payload copies."""
    events = retrieval_log.review_events(collection=collection)
    fresh = {}
    for i, point in enumerate(points):
        epochs = events.get(point.id)
        if not epochs:
            continue
        stability, last_epoch = salience.fsrs_replay(epochs)
        r_now = salience.fsrs_retrievability((now - last_epoch) / 86400.0,
                                             stability)
        fresh[i] = r_now
        payload = payloads[i]
        new_s = round(stability, 4)
        new_r = round(r_now, 4)
        try:
            prev_r = float(payload["fsrs_retrievability"])
        except (KeyError, TypeError, ValueError):
            prev_r = None
        if (payload.get("stability") != new_s or prev_r is None
                or abs(new_r - prev_r) > SNAPSHOT_DELTA):
            payload["stability"] = new_s
            payload["fsrs_retrievability"] = new_r
            payload["fsrs_computed_at"] = _now_iso()
            dirty[i] = True
            report["fsrs_updated"] += 1
    return fresh


def _tiering_pass(points, payloads, scored, created_epochs, fsrs_fresh,
                  report, now):
    """Report-only cold-storage candidates (F2 D3). Writes NOTHING to points.

    Uses FRESH in-pass values (scored, fsrs_fresh) — not the delta-guard-stale
    payload copies. Undated points are counted, never listed: age unknown ≠
    old, and the undated set is the founding legacy corpus."""
    rows = []
    undated = 0
    for i, payload in enumerate(payloads):
        if (payload.get("salience_pinned") or payload.get("kind") == "memory_request"
                or payload.get("kind") == reflection.DREAM_KIND):
            continue
        inv = payload.get("invalid_from_ts")
        try:
            if inv is not None and float(inv) <= now:
                continue
        except (TypeError, ValueError):
            pass
        try:
            retrievals = int(payload.get("retrieval_count") or 0)
        except (TypeError, ValueError):
            retrievals = 0
        reason = None
        if i in fsrs_fresh and fsrs_fresh[i] < salience.TIERING_R_MAX:
            reason = "forgotten"
        elif retrievals <= 0:
            if created_epochs[i] is None:
                undated += 1
                continue
            if (now - created_epochs[i]) / 86400.0 > salience.TIERING_MIN_AGE_DAYS:
                reason = "never_used"
        if reason is None:
            continue
        rows.append((scored[i], created_epochs[i] or 0.0, i, reason, retrievals))
    rows.sort(key=lambda row: (row[0], row[1]))
    report["tiering_candidates_total"] = len(rows)
    report["tiering_undated_excluded"] = undated
    report["tiering_candidates"] = [
        {"id": points[i].id, "reason": reason,
         "preview": str(payloads[i].get("user_input", ""))[:80],
         "created_at": payloads[i].get("created_at"),
         "retrieval_count": retrievals,
         "stability": payloads[i].get("stability"),
         "fsrs_retrievability": (round(fsrs_fresh[i], 4)
                                 if i in fsrs_fresh else None),
         "salience": round(value, 4),
         "near_dup": "near_duplicate_of" in payloads[i]}
        for value, _, i, reason, retrievals
        in rows[:salience.TIERING_MAX_CANDIDATES]]


def build_request_points(requests, embed_fn):
    """memory-kind request records -> pinned first-class points."""
    entries = []
    for req in requests or []:
        content = str(req.get("content") or "").strip()
        rid = str(req.get("id") or "").strip()
        if not content or not rid:
            continue
        if str(req.get("kind") or "memory") != "memory":
            continue
        note = (str(req.get("note") or "").strip()
                or "Murphy asked the house to remember this.")
        source = f"memory_request:{rid}"
        combined = f"User: {content}\nMurphy: {note}"
        entries.append((req, rid, content, note, source, combined))
    if not entries:
        return []
    vectors = embed_fn([entry[5] for entry in entries])
    points = []
    for (req, rid, content, note, source, combined), vector in zip(entries, vectors):
        payload = {
            "user_input": content,
            "ai_response": note,
            "source_file": source,
            "era": "murphy",
            "full_text": combined,
            "harness": "hermes",
            "kind": "memory_request",
            "salience_pinned": True,
            "created_at": req.get("ts") or _now_iso(),
            "session_id": req.get("session_id") or "",
        }
        points.append(PointStruct(id=memory_point_id(source, content, note),
                                  vector=list(vector), payload=payload))
    return points


def invalidate_points(point_ids, reason="", superseded_by=None, client=None,
                      collection=COLLECTION_NAME):
    """Graphiti-style invalidation: mark, never delete."""
    if not point_ids:
        return 0
    client = client or get_client()
    patch = {
        "invalid_from": _now_iso(),
        "invalid_from_ts": time.time(),
        "invalidation_reason": str(reason or ""),
    }
    if superseded_by is not None:
        patch["superseded_by"] = superseded_by
    _append_ledger(collection, point_ids, patch)   # ledger FIRST (F2 D2b)
    client.set_payload(collection_name=collection, payload=patch,
                       points=list(point_ids))
    return len(point_ids)


def _append_ledger(collection, point_ids, patch):
    """Append-only invalidation ledger (F2 D2b). Raises on failure —
    a mark that exists only on a payload is the fragile state F2 removes."""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _now_iso(), "collection": collection,
                             "point_ids": list(point_ids), "patch": patch},
                            default=str) + "\n")


def _ledger_records(collection):
    """Ledger records for one collection; malformed/foreign lines skipped."""
    records = []
    try:
        with open(LEDGER_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict) or rec.get("collection") != collection:
                    continue
                if not isinstance(rec.get("point_ids"), list) or not rec["point_ids"]:
                    continue
                if not isinstance(rec.get("patch"), dict) or not rec["patch"]:
                    continue
                records.append(rec)
    except OSError:
        return records
    return records


def run(requests=None, dry_run=False, client=None, embed_fn=None, now=None,
        collection=COLLECTION_NAME, ollama_client=None):
    started = time.time()
    now = now if now is not None else started
    client = client or get_client()
    embed_fn = embed_fn or _default_embed

    report = {
        "ts": _now_iso(), "collection": collection, "dry_run": bool(dry_run),
        "points_total": 0, "created_at_backfilled": 0, "novelty_computed": 0,
        "near_duplicates_flagged": 0, "usage_updated": 0, "fsrs_updated": 0,
        "requests_honored": 0, "snapshot_written": 0, "top_salience": [],
        "invalidations_reapplied": 0,
        "tiering_candidates": [], "tiering_candidates_total": 0,
        "tiering_undated_excluded": 0,
    }

    # 1. Honor memory requests first — they join tonight's pass as points.
    request_points = [] if dry_run else build_request_points(requests, embed_fn)
    for start in range(0, len(request_points), BATCH_SIZE):
        client.upsert(collection_name=collection,
                      points=request_points[start:start + BATCH_SIZE])
    report["requests_honored"] = len(request_points)

    # 2. Load everything (including points just written).
    points = load_points(client, collection)
    report["points_total"] = len(points)
    if not points:
        if collection == "claude_eternal":
            report["vocab_terms"] = {}
        _write_report(report, started)
        return report

    payloads = [dict(p.payload or {}) for p in points]
    vectors = np.array([p.vector for p in points], dtype=np.float32)
    dirty = [False] * len(points)

    # 3. created_at backfill (hermes journal basenames carry timestamps).
    for i, payload in enumerate(payloads):
        if payload.get("created_at"):
            continue
        derived = salience.created_at_from_source(payload.get("source_file"))
        if derived:
            payload["created_at"] = derived
            dirty[i] = True
            report["created_at_backfilled"] += 1

    created_epochs = [salience.parse_iso(p.get("created_at")) for p in payloads]

    # 4.0 G5 Claude vocab n-grams (claude_eternal ONLY; pure, observe-only, runs
    # in every mode incl. dry_run — no writes, no LLM). Additive report key;
    # try/except into report, never re-raise (established observe-only idiom).
    if collection == "claude_eternal":
        try:
            report["vocab_terms"] = vocab_ngrams.day_terms(
                payloads, created_epochs, now)
        except Exception as exc:                      # never break the pass
            report["vocab_terms"] = {}
            report["vocab_error"] = f"{type(exc).__name__}: {exc}"

    # 4. Usage from the retrieval log.
    usage = retrieval_log.aggregate_usage()
    max_count = max((u["count"] for u in usage.values()), default=0)
    for i, (point, payload) in enumerate(zip(points, payloads)):
        entry = usage.get(point.id)
        if not entry:
            continue
        norm = round(salience.usage_norm(entry["count"], max_count), 4)
        if (payload.get("retrieval_count") != entry["count"]
                or payload.get("last_accessed_at") != entry["last_ts"]
                or payload.get("usage_norm") != norm):
            payload["retrieval_count"] = entry["count"]
            payload["last_accessed_at"] = entry["last_ts"]
            payload["usage_norm"] = norm
            dirty[i] = True
            report["usage_updated"] += 1

    # 4b. FSRS retrievability (observe-only; F2). Fresh values feed tiering.
    fsrs_fresh = _fsrs_pass(points, payloads, dirty, report, collection, now)

    # 4c. F3 importance (observe-only — skip-trigger fuel, NEVER composite).
    ollama = None
    f3_importance_ok = False
    if not dry_run and reflection.enabled():
        try:
            ollama = ollama_client or reflection.default_ollama()
            f3_importance_ok = reflection.importance_pass(
                payloads, created_epochs, dirty, now, ollama, report, collection)
        except Exception as exc:                      # never break the pass
            report["importance_error"] = f"{type(exc).__name__}: {exc}"

    # 5. Novelty, once per point.
    candidates = [i for i, p in enumerate(payloads) if "novelty" not in p]
    novelties = compute_novelty(vectors, created_epochs, candidates)
    for i, (novelty, near_idx) in novelties.items():
        payloads[i]["novelty"] = round(novelty, 4)
        if near_idx is not None:
            payloads[i]["near_duplicate_of"] = points[near_idx].id
            report["near_duplicates_flagged"] += 1
        dirty[i] = True
    report["novelty_computed"] = len(novelties)

    # 6. Salience snapshot (retrieval recomputes live; this is observability).
    scored = []
    for i, payload in enumerate(payloads):
        last = (salience.parse_iso(payload.get("last_accessed_at"))
                or created_epochs[i])
        recency = salience.recency_score(now, last)
        novelty = float(payload.get("novelty", salience.NOVELTY_DEFAULT))
        usage_component = float(payload.get("usage_norm", 0.0))
        value = salience.composite(recency, novelty, usage_component)
        if payload.get("salience_pinned"):
            value = max(value, salience.PIN_FLOOR)
        scored.append(value)
        previous = payload.get("salience")
        if previous is None or abs(value - float(previous)) > SNAPSHOT_DELTA:
            payload["salience"] = round(value, 4)
            payload["salience_components"] = {
                "recency": round(recency, 4), "novelty": round(novelty, 4),
                "usage": round(usage_component, 4)}
            payload["salience_computed_at"] = _now_iso()
            dirty[i] = True
            report["snapshot_written"] += 1

    # 6b. Tiering candidates (report-only; F2 D3).
    _tiering_pass(points, payloads, scored, created_epochs, fsrs_fresh,
                  report, now)

    # 7. Write merged points back (full re-upsert, same id + vector).
    if not dry_run:
        updates = [
            PointStruct(id=points[i].id,
                        vector=[float(x) for x in vectors[i]],
                        payload=payloads[i])
            for i, is_dirty in enumerate(dirty) if is_dirty
        ]
        for start in range(0, len(updates), BATCH_SIZE):
            client.upsert(collection_name=collection,
                          points=updates[start:start + BATCH_SIZE])

    # 8. Re-apply the invalidation ledger (self-healing marks; F2 D2b).
    if not dry_run:
        for rec in _ledger_records(collection):
            try:
                client.set_payload(collection_name=collection,
                                   payload=rec["patch"],
                                   points=list(rec["point_ids"]))
                report["invalidations_reapplied"] += len(rec["point_ids"])
            except Exception:
                continue  # e.g. a scratch collection's stale record

    # 8.5. F3 dreams (additive rows; NEVER allowed to break the pass — T5).
    if not dry_run and reflection.enabled():
        try:
            reflection.dream_pass(client, collection, points, payloads,
                                  vectors, created_epochs, now,
                                  ollama or reflection.default_ollama(),
                                  embed_fn, report,
                                  importance_ok=f3_importance_ok)
        except Exception as exc:
            report.setdefault("dreams", {})
            report["dreams"].update({"error": f"{type(exc).__name__}: {exc}",
                                     "written": report["dreams"].get("written", 0)})

    ranked = sorted(range(len(points)), key=lambda i: scored[i], reverse=True)[:10]
    report["top_salience"] = [
        {"id": points[i].id, "salience": round(scored[i], 4),
         "preview": str(payloads[i].get("user_input", ""))[:80]}
        for i in ranked
    ]
    _write_report(report, started)
    return report


def _write_report(report, started):
    report["duration_s"] = round(time.time() - started, 2)
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        latest = f"sleep_report_latest_{report.get('collection', 'unknown')}.json"
        for name in ("sleep_report_latest.json", latest):
            (REPORT_DIR / name).write_text(
                json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        with open(REPORT_DIR / "sleep_history.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, default=str) + "\n")
    except OSError:
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Murphy sleeps — nightly consolidation")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--requests-file", help="JSONL of memory_request records")
    parser.add_argument("--invalidate", type=int, action="append", default=[],
                        help="point id to invalidate (repeatable; marks, never deletes)")
    parser.add_argument("--reason", default="")
    parser.add_argument("--superseded-by", type=int, default=None)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    args = parser.parse_args(argv)

    if args.invalidate:
        count = invalidate_points(args.invalidate, reason=args.reason,
                                  superseded_by=args.superseded_by,
                                  collection=args.collection)
        print(f"🜄 invalidated {count} point(s) — marked, never deleted")
        return 0

    requests = []
    if args.requests_file:
        with open(args.requests_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    requests.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    report = run(requests=requests, dry_run=args.dry_run,
                 collection=args.collection)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
