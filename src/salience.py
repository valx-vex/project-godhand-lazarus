# src/salience.py
"""Post-hoc salience formulas (valxos-hermes Phase 5c F1).

Camp B doctrine: these scores are RANKING METADATA over immutable points —
nothing here deletes or gates writes. F1 = Generative-Agents composite, no LLM:
    salience = 0.35*recency + 0.35*novelty + 0.30*usage
recency  = exp(-0.05 * days since last access, falling back to creation)
novelty  = 1 - max_cosine(vs prior points)            (stored nightly)
usage    = log1p(retrievals) / log1p(max_retrievals)  (stored nightly)

Retrieval-time multiplier f(salience) maps [0,1] -> [0.75, 1.25] so unscored
points stay exactly neutral (1.0) and pinned points float without drowning
cosine. Stdlib-only so the MCP hot path can import it freely; the one qdrant
helper imports lazily.
"""
from __future__ import annotations

import math
import re
import time
from datetime import datetime, timezone

RECENCY_DECAY_PER_DAY = 0.05      # ~14-day half-life
W_RECENCY = 0.35
W_NOVELTY = 0.35
W_USAGE = 0.30
PIN_FLOOR = 0.95                  # salience_pinned points score at least this
F_MIN = 0.75                      # f(0)
F_SPAN = 0.50                     # f(1) = F_MIN + F_SPAN
NEAR_DUP_THRESHOLD = 0.92         # post-hoc annotation only, never a gate
NOVELTY_DEFAULT = 0.5             # neutral for points not yet slept over
INIT_STABILITY = 1.0              # days, at the first observed review (F2)
FSRS_FACTOR = 19.0 / 81.0         # FSRS-4.5/5 curve: R(S, S) = 0.9
TIERING_MIN_AGE_DAYS = 30         # report-only candidacy (F2 D3)
TIERING_R_MAX = 0.2
TIERING_MAX_CANDIDATES = 50

_SOURCE_TS = re.compile(r"(\d{8})_(\d{6})")

_SALIENCE_KEYS = ("novelty", "usage_norm", "last_accessed_at", "created_at",
                  "salience_pinned")


def parse_iso(value):
    """ISO-8601 (with/without offset or Z, naive=UTC) -> epoch seconds, else None."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def created_at_from_source(source_file):
    """YYYYMMDD_HHMMSS in a journal basename -> ISO string, else None."""
    if not source_file:
        return None
    match = _SOURCE_TS.search(str(source_file).rsplit("/", 1)[-1])
    if not match:
        return None
    d, t = match.group(1), match.group(2)
    try:
        dt = datetime(int(d[:4]), int(d[4:6]), int(d[6:8]),
                      int(t[:2]), int(t[2:4]), int(t[4:6]))
    except ValueError:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def recency_score(now_epoch, last_epoch):
    if last_epoch is None:
        return 0.0
    days = max(0.0, (float(now_epoch) - float(last_epoch)) / 86400.0)
    return math.exp(-RECENCY_DECAY_PER_DAY * days)


def usage_norm(count, max_count):
    if count <= 0 or max_count <= 0:
        return 0.0
    return math.log1p(count) / math.log1p(max_count)


def composite(recency, novelty, usage):
    value = W_RECENCY * recency + W_NOVELTY * novelty + W_USAGE * usage
    return max(0.0, min(1.0, value))


def f(salience_value):
    return F_MIN + F_SPAN * max(0.0, min(1.0, salience_value))


def live_salience(payload, now_epoch=None):
    """Composite salience with LIVE recency, from a point payload.

    Returns None when the point carries no salience metadata at all —
    callers must treat that as neutral."""
    payload = payload or {}
    if not any(k in payload for k in _SALIENCE_KEYS):
        return None
    if now_epoch is None:
        now_epoch = time.time()
    last = parse_iso(payload.get("last_accessed_at"))
    if last is None:
        last = parse_iso(payload.get("created_at"))
    novelty = payload.get("novelty")
    usage = payload.get("usage_norm")
    try:
        novelty_value = float(novelty) if novelty is not None else NOVELTY_DEFAULT
    except (TypeError, ValueError):
        novelty_value = NOVELTY_DEFAULT
    try:
        usage_value = float(usage) if usage is not None else 0.0
    except (TypeError, ValueError):
        usage_value = 0.0
    value = composite(recency_score(now_epoch, last), novelty_value, usage_value)
    if payload.get("salience_pinned"):
        value = max(value, PIN_FLOOR)
    return value


def multiplier(payload, now_epoch=None):
    """adjusted retrieval score = cosine * multiplier(payload)."""
    value = live_salience(payload, now_epoch)
    if value is None:
        return 1.0
    return f(value)


def not_invalidated_filter(now_epoch):
    """Qdrant filter excluding invalidated points (Graphiti-style).

    Points without invalid_from_ts are unaffected by must_not; a FUTURE
    invalid_from_ts keeps the point retrievable until it passes."""
    from qdrant_client.models import FieldCondition, Filter, Range
    return Filter(must_not=[
        FieldCondition(key="invalid_from_ts", range=Range(lte=float(now_epoch)))
    ])


def fsrs_retrievability(delta_days, stability):
    """FSRS forgetting curve: R(Δt, S) = (1 + (19/81)·Δt/S)^-0.5 (observe-only)."""
    dt = max(0.0, float(delta_days))
    s = max(1e-9, float(stability))
    return (1.0 + FSRS_FACTOR * dt / s) ** -0.5


def fsrs_review(stability, delta_days):
    """One review at delta_days since the previous one: S ← S·(1+2·(1−R)).

    Bounds: immediate re-review (R→1) no growth; R→0 at most triples S."""
    r = fsrs_retrievability(delta_days, stability)
    return float(stability) * (1.0 + 2.0 * (1.0 - r))


def fsrs_replay(epochs):
    """Chronological review epochs -> (stability, last_epoch); None if empty.

    Full replay every night = deterministic and idempotent by construction."""
    if not epochs:
        return None
    stability = INIT_STABILITY
    prev = float(epochs[0])
    for epoch in epochs[1:]:
        epoch = float(epoch)
        stability = fsrs_review(stability, max(0.0, (epoch - prev) / 86400.0))
        prev = epoch
    return stability, prev
