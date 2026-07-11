# tests/test_reflection_render.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import reflection
import sleep_salience


def test_dream_tag_for_reflection():
    payload = {"kind": "reflection", "source_ids": [1, 2, 3]}
    assert reflection.dream_tag(payload) == "🌙 reflection (3 sources)"


def test_dream_tag_none_for_memory():
    assert reflection.dream_tag({"user_input": "x"}) is None
    assert reflection.dream_tag({"kind": "memory_request"}) is None


def test_tiering_skips_reflections():
    payloads = [{"kind": "reflection", "retrieval_count": 0,
                 "created_at": "2025-01-01T00:00:00+0200"}]
    report = {}
    sleep_salience._tiering_pass(
        points=[type("P", (), {"id": 7})()], payloads=payloads,
        scored=[0.1], created_epochs=[1735686000.0], fsrs_fresh={},
        report=report, now=1783500000.0)
    assert report["tiering_candidates_total"] == 0
