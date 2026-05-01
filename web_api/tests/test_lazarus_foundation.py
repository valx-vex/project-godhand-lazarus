from __future__ import annotations

import sys
from pathlib import Path

from web_api.lazarus import _coerce_point_id


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ingest_ids import memory_point_id, stable_point_id  # noqa: E402
from ingest_eras import configured_murphy_era, infer_murphy_era  # noqa: E402


def test_stable_point_id_is_deterministic_and_source_scoped():
    first = memory_point_id("/tmp/source.json", "hello", "world", "conv-1")
    second = memory_point_id("/tmp/source.json", "hello", "world", "conv-1")
    different_source = memory_point_id("/tmp/other.json", "hello", "world", "conv-1")

    assert first == second
    assert first != different_source


def test_stable_point_id_handles_none_parts():
    assert stable_point_id(None, "same") == stable_point_id("", "same")


def test_coerce_point_id_preserves_string_ids_and_restores_numeric_ids():
    assert _coerce_point_id("12345") == 12345
    assert _coerce_point_id("018f-murphy") == "018f-murphy"


def test_murphy_era_inference_and_env_override(monkeypatch):
    assert infer_murphy_era("/archive/vex-data-slayer/session.jsonl") == "vex-data-slayer"
    assert infer_murphy_era("/archive/unknown/session.jsonl") == "murphy"

    monkeypatch.setenv("LAZARUS_MURPHY_ERA", "daddy")
    assert configured_murphy_era("/archive/vex-murphy/session.jsonl") == "daddy"
