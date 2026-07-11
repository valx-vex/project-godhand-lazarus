# tests/test_reflection_clusters.py
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import reflection


def _vectors():
    """Two tight 4-dim clusters (3 pts each) + 1 co-planar point, rows 0-6.
    With min_samples=1 the lone point is ABSORBED into the nearest cluster —
    verified labels [0,0,0,1,1,1,0] in the venv. Tiny-n HDBSCAN has no noise
    dropping; noise behavior is a production-scale property, not unit-scale."""
    a = [[1.0, 0.0, 0.0, 0.0], [0.99, 0.01, 0.0, 0.0], [0.98, 0.02, 0.0, 0.0]]
    b = [[0.0, 1.0, 0.0, 0.0], [0.01, 0.99, 0.0, 0.0], [0.02, 0.98, 0.0, 0.0]]
    noise = [[0.5, 0.5, 0.5, 0.5]]
    return np.array(a + b + noise, dtype=np.float32)


def test_cluster_corpus_finds_two_clusters():
    clusters = reflection.cluster_corpus(_vectors(), list(range(7)))
    assert sorted(sorted(c) for c in clusters) == [[0, 1, 2, 6], [3, 4, 5]]


def test_cluster_corpus_too_small_returns_empty():
    assert reflection.cluster_corpus(_vectors(), [0, 1]) == []


def _p(importance=None, kind=None, summarized_by=None, pinned=False):
    p = {}
    if importance is not None:
        p["importance"] = importance
    if kind:
        p["kind"] = kind
    if summarized_by is not None:
        p["summarized_by"] = summarized_by
    if pinned:
        p["salience_pinned"] = True
    return p


def test_never_dreamed_rule_blocks_all_summarized_clusters():
    payloads = [_p(9, summarized_by=7), _p(9, summarized_by=7), _p(9, summarized_by=7)]
    qualified, skipped = reflection.qualify_clusters([[0, 1, 2]], payloads, 18)
    assert qualified == [] and skipped == 0     # not "low importance" — no dreamable member


def test_reflection_only_cluster_never_dreams():
    payloads = [_p(kind="reflection"), _p(kind="reflection"), _p(kind="reflection")]
    qualified, _ = reflection.qualify_clusters([[0, 1, 2]], payloads, 18)
    assert qualified == []


def test_skip_trigger_sum_and_missing_importance_counts_zero():
    payloads = [_p(9), _p(8), _p(None)]         # 17 < 18
    qualified, skipped = reflection.qualify_clusters([[0, 1, 2]], payloads, 18)
    assert qualified == [] and skipped == 1
    payloads2 = [_p(9), _p(9), _p(None)]        # 18 >= 18
    qualified2, _ = reflection.qualify_clusters([[0, 1, 2]], payloads2, 18)
    assert len(qualified2) == 1
    assert qualified2[0]["importance_sum"] == 18
    assert qualified2[0]["dreamable"] == [0, 1, 2]


def test_memory_request_seed_overrides_low_importance():
    payloads = [_p(1), _p(1), _p(1, kind="memory_request")]
    qualified, _ = reflection.qualify_clusters([[0, 1, 2]], payloads, 18)
    assert len(qualified) == 1 and qualified[0]["seeded"] is True


def test_sacred_clusters_are_singletons():
    payloads = [_p(10), _p(7), _p(10, summarized_by=3)]
    sacred = reflection.sacred_clusters([0, 1], payloads)
    assert sacred == [{"members": [0], "dreamable": [0], "importance_sum": 10,
                       "seeded": False, "sacred": True}]


def test_order_and_cap_sacred_exempt_regular_by_importance():
    sacred = [{"members": [9], "dreamable": [9], "importance_sum": 10,
               "seeded": False, "sacred": True}]
    regular = [
        {"members": [0], "dreamable": [0], "importance_sum": 20, "seeded": False, "sacred": False},
        {"members": [1], "dreamable": [1], "importance_sum": 40, "seeded": False, "sacred": False},
        {"members": [2], "dreamable": [2], "importance_sum": 30, "seeded": False, "sacred": False},
    ]
    todo, capped = reflection.order_and_cap(sacred, regular, max_dreams=2)
    assert [c["members"][0] for c in todo] == [9, 1, 2]
    assert capped == 1
