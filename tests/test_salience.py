# tests/test_salience.py
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import salience


def test_recency_half_life():
    # decay 0.05/day -> half-life = ln(2)/0.05 ~ 13.86 days
    now = 1_000_000.0
    half_life_s = (math.log(2) / 0.05) * 86400
    assert abs(salience.recency_score(now + half_life_s, now) - 0.5) < 1e-6
    assert salience.recency_score(now, now) == 1.0


def test_recency_none_is_zero():
    assert salience.recency_score(1000.0, None) == 0.0


def test_usage_norm_bounds():
    assert salience.usage_norm(0, 10) == 0.0
    assert salience.usage_norm(5, 0) == 0.0
    assert salience.usage_norm(10, 10) == 1.0
    assert 0.0 < salience.usage_norm(3, 10) < 1.0


def test_composite_weights_and_clamp():
    assert abs(salience.composite(1.0, 1.0, 1.0) - 1.0) < 1e-9
    assert salience.composite(0.0, 0.0, 0.0) == 0.0
    assert abs(salience.composite(1.0, 0.0, 0.0) - 0.35) < 1e-9
    assert abs(salience.composite(0.0, 0.0, 1.0) - 0.30) < 1e-9


def test_f_range():
    assert salience.f(0.0) == 0.75
    assert abs(salience.f(1.0) - 1.25) < 1e-9
    assert salience.f(-5.0) == 0.75
    assert abs(salience.f(5.0) - 1.25) < 1e-9


def test_multiplier_neutral_without_fields():
    assert salience.multiplier({}) == 1.0
    assert salience.multiplier({"user_input": "x", "harness": "hermes"}) == 1.0


def test_multiplier_pin_floor():
    m = salience.multiplier({"salience_pinned": True}, now_epoch=1000.0)
    assert m >= salience.f(salience.PIN_FLOOR) - 1e-9


def test_live_salience_prefers_last_access_over_created():
    now = salience.parse_iso("2026-07-06T00:00:00+0000")
    # created_at 100 days before now (recency exp(-5) ~ 0.0067), last_accessed_at
    # exactly at now (recency 1.0). The two branches yield DIFFERENT recencies,
    # so this actually proves last_accessed_at wins.
    created = "2026-03-28T00:00:00+0000"  # 100 days before 2026-07-06
    payload = {"created_at": created, "last_accessed_at": "2026-07-06T00:00:00+0000",
               "novelty": 0.0, "usage_norm": 0.0}
    value = salience.live_salience(payload, now_epoch=now)
    assert abs(value - 0.35) < 1e-6  # recency 1.0 from last access -> 0.35*1.0

    # Drop last_accessed_at: now the decayed created_at drives recency (~0.0067),
    # so salience collapses toward zero -> proves the fallback branch differs.
    payload.pop("last_accessed_at")
    fallback = salience.live_salience(payload, now_epoch=now)
    assert fallback < 0.01


def test_multiplier_malformed_novelty_does_not_raise():
    m = salience.multiplier({"novelty": "garbage",
                             "created_at": "2026-07-05T00:00:00+0000"})
    assert isinstance(m, float)
    assert 0.75 <= m <= 1.25


def test_created_at_from_source_hermes():
    src = "/Users/valx/.hermes/journal/finalized/20260705_155012_56d180.jsonl"
    assert salience.created_at_from_source(src) == "2026-07-05T15:50:12"


def test_created_at_from_source_non_matching():
    assert salience.created_at_from_source("/Users/valx/.claude/projects/x/file.jsonl") is None
    assert salience.created_at_from_source(None) is None


def test_parse_iso_variants():
    assert salience.parse_iso("2026-07-05T15:50:12+0000") is not None
    assert salience.parse_iso("2026-07-05T15:50:12Z") is not None
    assert salience.parse_iso("2026-07-05T15:50:12") is not None
    assert salience.parse_iso("") is None
    assert salience.parse_iso("garbage") is None
