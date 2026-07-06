# tests/test_retrieval_log.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import retrieval_log


def _use_tmp_log(monkeypatch, tmp_path):
    target = tmp_path / "logs" / "retrieval.jsonl"
    monkeypatch.setenv("LAZARUS_RETRIEVAL_LOG", str(target))
    return target


def test_log_and_aggregate_counts(monkeypatch, tmp_path):
    target = _use_tmp_log(monkeypatch, tmp_path)
    assert retrieval_log.log_retrieval(
        "lazarus_summon", "murphy_eternal", "sacred flame",
        [{"id": 11, "cosine": 0.9, "adjusted": 0.95},
         {"id": 22, "cosine": 0.8, "adjusted": 0.79}],
        persona="murphy", limit=5)
    assert retrieval_log.log_retrieval(
        "lazarus_remember", "murphy_eternal", "bridge day",
        [{"id": 11, "cosine": 0.7, "adjusted": 0.7}])
    lines = target.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["tool"] == "lazarus_summon" and first["persona"] == "murphy"
    usage = retrieval_log.aggregate_usage()
    assert usage[11]["count"] == 2
    assert usage[22]["count"] == 1


def test_last_ts_tracks_latest(monkeypatch, tmp_path):
    target = _use_tmp_log(monkeypatch, tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {"ts": "2026-07-01T10:00:00+0000", "results": [{"id": 5}]},
        {"ts": "2026-07-03T10:00:00+0000", "results": [{"id": 5}]},
        {"ts": "2026-07-02T10:00:00+0000", "results": [{"id": 5}]},
    ]
    target.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    usage = retrieval_log.aggregate_usage()
    assert usage[5]["count"] == 3
    assert usage[5]["last_ts"] == "2026-07-03T10:00:00+0000"


def test_malformed_lines_skipped(monkeypatch, tmp_path):
    target = _use_tmp_log(monkeypatch, tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('not json\n{"ts": "2026-07-01T00:00:00+0000", "results": [{"id": 1}]}\n')
    usage = retrieval_log.aggregate_usage()
    assert usage[1]["count"] == 1 and len(usage) == 1


def test_missing_file_empty(monkeypatch, tmp_path):
    _use_tmp_log(monkeypatch, tmp_path)
    assert retrieval_log.aggregate_usage() == {}


def test_log_never_raises(monkeypatch):
    monkeypatch.setenv("LAZARUS_RETRIEVAL_LOG", "/dev/null/impossible/x.jsonl")
    assert retrieval_log.log_retrieval("t", "c", "q", [{"id": 1}]) is False


def test_wrong_shape_json_lines_skipped(monkeypatch, tmp_path):
    target = _use_tmp_log(monkeypatch, tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '[1,2,3]\n'
        '{"results": "abc"}\n'
        '{"results": [1, 2, 3]}\n'
        '{"results": [{"id": [1, 2]}]}\n'
        '{"ts": "2026-07-01T00:00:00+0000", "results": [{"id": 9}]}\n')
    usage = retrieval_log.aggregate_usage()
    assert usage == {9: {"count": 1, "last_ts": "2026-07-01T00:00:00+0000",
                         "last_epoch": retrieval_log.salience.parse_iso("2026-07-01T00:00:00+0000")}}
