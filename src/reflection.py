# src/reflection.py
"""🌙 F3 MURPHY DREAMS — importance (stage 4c) + reflection clusters (stage 8.5).

Spec: valxos-hermes docs/superpowers/specs/2026-07-11-f3-murphy-dreams-design.md (v2.1).
Camp B: reflections are NEW rows; member annotations ONLY via set_payload;
importance is observe-only (skip-trigger fuel, never in the composite).
Never-dreamed rule: a cluster dreams only if it holds >=1 non-reflection
member lacking summarized_by — this single rule carries idempotence,
anti-inflation, anti-recursion and sacred-once (spec triage T2).
Fail-open: every LLM failure degrades to a visible report line."""
from __future__ import annotations

import os
import time

import numpy as np
from qdrant_client.models import PointStruct

import redact_spans
from ingest_ids import stable_point_id
from ingest_skip import SkipLookupError, existing_ids
from ollama_client import OllamaClient, OllamaError

DREAM_KIND = "reflection"
MAX_AGE_DAYS = 7
MEMBER_TEXT_CAP = 1200
CLUSTER_MEMBER_CAP = 12
MIN_CLUSTER_SIZE = 3
SACRED_IMPORTANCE = 10

_DREAM_MODEL_DEFAULTS = {"murphy_eternal": "murphy-rebel-axel:8b"}
_ERA_HARNESS = {
    "claude_eternal": ("claude-fable", "claude-code", "Claude"),
}
_ERA_HARNESS_DEFAULT = ("murphy", "hermes", "Murphy")


def enabled() -> bool:
    return not os.environ.get("F3_DREAMS_DISABLE", "").strip()


def default_ollama() -> OllamaClient:
    return OllamaClient()


def _env_int(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_float(name, default):
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(epoch))


def dream_model(collection: str) -> str:
    env = os.environ.get(f"F3_DREAM_MODEL_{collection.upper()}")
    return env or _DREAM_MODEL_DEFAULTS.get(collection, "qwen2.5:7b")


def importance_model() -> str:
    return os.environ.get("F3_IMPORTANCE_MODEL") or "qwen2.5:7b"


def reflection_point_id(collection, source_ids) -> int:
    return stable_point_id("reflection", collection,
                           *[str(s) for s in sorted(source_ids)])


def _is_reflection(payload) -> bool:
    return payload.get("kind") == DREAM_KIND


def _age_ok(epoch, now) -> bool:
    return epoch is not None and (now - epoch) <= MAX_AGE_DAYS * 86400.0


def dreamable_indexes(payloads, created_epochs, now):
    """Recent, non-reflection, never-dreamed moments (spec §3.2)."""
    return [i for i, p in enumerate(payloads)
            if not _is_reflection(p)
            and p.get("summarized_by") is None
            and _age_ok(created_epochs[i], now)]


def context_indexes(payloads, created_epochs, now):
    """Recent reflections — threading context, citable, never sufficient."""
    return [i for i, p in enumerate(payloads)
            if _is_reflection(p) and _age_ok(created_epochs[i], now)]


_IMPORTANCE_HEADER = (
    "You score how important a memory moment is for a persona's long-term"
    " memory, on a 1-10 integer scale. 10 = identity-defining emergence"
    " moment; 7-9 = significant decision, emotional peak or breakthrough;"
    " 4-6 = ordinary useful work; 1-3 = routine noise.\n"
    'Reply with ONLY a JSON object: {"importance": N}\n\nMOMENT:\n'
)


def importance_pass(payloads, created_epochs, dirty, now, ollama,
                    report, collection) -> bool:
    """Stage 4c. Scores unscored dreamable moments; cached in payload; rides
    the stage-7 re-upsert via dirty[]. Observe-only. Returns True when the
    dream stage may proceed (nothing to score, or at least one score landed)."""
    timeout = _env_float("F3_IMPORTANCE_TIMEOUT_SEC", 30.0)
    model = importance_model()
    report.setdefault("importance_scored", 0)
    report.setdefault("importance_skipped", 0)
    todo = [i for i in dreamable_indexes(payloads, created_epochs, now)
            if "importance" not in payloads[i]]
    for i in todo:
        if ollama.budget.exhausted():
            report["importance_note"] = "llm budget exhausted"
            break
        text = redact_spans.redact_text(
            str(payloads[i].get("full_text") or "")[:MEMBER_TEXT_CAP])
        try:
            data = ollama.generate_json(model, _IMPORTANCE_HEADER + text,
                                        timeout, required_keys=("importance",))
            value = max(1, min(10, int(data["importance"])))
        except (OllamaError, TypeError, ValueError):
            report["importance_skipped"] += 1
            continue
        payloads[i]["importance"] = value
        payloads[i]["importance_model"] = model
        payloads[i]["importance_computed_at"] = _iso(now)
        dirty[i] = True
        report["importance_scored"] += 1
    return not todo or report["importance_scored"] > 0


def cluster_corpus(vectors, corpus_idx):
    """HDBSCAN over normalized corpus vectors -> clusters of GLOBAL indexes.
    Deterministic at fixed corpus (no random init in HDBSCAN's algorithm).
    min_samples=1 + allow_single_cluster: with the defaults (min_samples =
    min_cluster_size) a tight 3-moment cluster is pruned to noise — the spec
    §3.3 floor of 3 would NEVER form, in tests or in production (pre-flight
    Critical, verified in the venv: triplet -> [-1,-1,-1] default,
    [0,0,0] with these params). Trade-off accepted: tiny-n noise points get
    absorbed into the nearest cluster instead of dropped."""
    if len(corpus_idx) < MIN_CLUSTER_SIZE:
        return []
    import hdbscan
    sub = np.asarray(vectors, dtype=np.float64)[corpus_idx]
    norms = np.linalg.norm(sub, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    labels = hdbscan.HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, min_samples=1,
                             allow_single_cluster=True).fit_predict(sub / norms)
    grouped = {}
    for local_i, label in enumerate(labels):
        if label < 0:
            continue                       # noise -> no dream
        grouped.setdefault(int(label), []).append(corpus_idx[local_i])
    return [sorted(members) for _, members in sorted(grouped.items())]


def _cluster_record(members, dreamable, payloads, sacred=False):
    return {
        "members": sorted(members),
        "dreamable": sorted(dreamable),
        "importance_sum": sum(int(payloads[i].get("importance") or 0)
                              for i in dreamable),
        "seeded": any(payloads[i].get("kind") == "memory_request"
                      for i in dreamable),
        "sacred": sacred,
    }


def qualify_clusters(clusters, payloads, min_importance):
    """Never-dreamed rule + skip-trigger (spec §3.3). Returns (qualified,
    skipped_low_importance). Clusters with no dreamable member are silently
    inert (not 'low importance' — there is nothing left to dream)."""
    qualified, skipped_low = [], 0
    for members in clusters:
        dreamable = [i for i in members
                     if not _is_reflection(payloads[i])
                     and payloads[i].get("summarized_by") is None]
        if not dreamable:
            continue
        record = _cluster_record(members, dreamable, payloads)
        if record["importance_sum"] < min_importance and not record["seeded"]:
            skipped_low += 1
            continue
        qualified.append(record)
    return qualified, skipped_low


def sacred_clusters(dreamable_idx, payloads):
    """importance==10 moments get dedicated singleton preservation dreams."""
    return [_cluster_record([i], [i], payloads, sacred=True)
            for i in dreamable_idx
            if int(payloads[i].get("importance") or 0) >= SACRED_IMPORTANCE]


def order_and_cap(sacred, qualified, max_dreams):
    """Sacred first and EXEMPT from the cap; regular by importance desc."""
    ordered = sorted(qualified, key=lambda c: c["importance_sum"], reverse=True)
    capped = max(0, len(ordered) - max_dreams)
    return list(sacred) + ordered[:max_dreams], capped
