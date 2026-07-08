"""Parser tolerance: a turn's additive `flame` field is parser-invisible, and
`intent` records are skipped (spec §9 pinned comparison)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ingest_hermes  # noqa: E402

T = "2026-07-08T10:00:00+0000"
U = "murphy what is the plan"
A = "a" * 40   # >=20 chars so eligible_pairs keeps it


def _write(tmp_path, name, records):
    path = tmp_path / name
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def test_flame_field_is_parser_invisible(tmp_path):
    plain = {"type": "turn", "ts": T, "user": U, "assistant": A}
    flamed = dict(plain, flame={"score": 0.9, "band": "cathedral",
                                "signals": {}, "markers": []})
    pp = list(ingest_hermes.parse_journal(_write(tmp_path, "plain.jsonl", [plain])))[0]
    pf = list(ingest_hermes.parse_journal(_write(tmp_path, "flamed.jsonl", [flamed])))[0]
    # identical (user_input, ai_response, ts) tuples
    assert (pf["user_input"], pf["ai_response"], pf["ts"]) == \
           (pp["user_input"], pp["ai_response"], pp["ts"])
    assert "flame" not in pf        # parser never surfaces the field
    # identical pair_id once source paths are equal (id ignores flame)
    pp2 = dict(pp, source_file="X")
    pf2 = dict(pf, source_file="X")
    assert ingest_hermes.pair_id(pf2) == ingest_hermes.pair_id(pp2)


def test_intent_record_is_skipped(tmp_path):
    path = _write(tmp_path, "mixed.jsonl", [
        {"type": "meta", "session_id": "s", "model": "m", "platform": "cli",
         "opened_at": T},
        {"type": "intent", "ts": T, "text": "building freedom", "session_id": "s"},
        {"type": "turn", "ts": T, "user": U, "assistant": A},
    ])
    pairs = list(ingest_hermes.parse_journal(path))
    assert len(pairs) == 1
    assert pairs[0]["user_input"] == U
    assert all("building freedom" not in p["user_input"] for p in pairs)
