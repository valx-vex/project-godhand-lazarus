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


# --- F2 review_events + aggregate_usage behavior pin ---
def _write_log(tmp_path, records):
    path = tmp_path / "log.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write((rec if isinstance(rec, str) else json.dumps(rec)) + "\n")
    return path


def test_review_events_orders_and_filters_collection(tmp_path):
    path = _write_log(tmp_path, [
        {"ts": "2026-07-07T12:00:00+0000", "collection": "murphy_eternal",
         "results": [{"id": 1}]},
        {"ts": "2026-07-07T10:00:00+0000", "collection": "murphy_eternal",
         "results": [{"id": 1}, {"id": 2}]},
        {"ts": "2026-07-07T11:00:00+0000", "collection": "claude_eternal",
         "results": [{"id": 1}]},
    ])
    events = retrieval_log.review_events(path=path, collection="murphy_eternal")
    assert set(events) == {1, 2}
    assert events[1] == sorted(events[1]) and len(events[1]) == 2
    all_events = retrieval_log.review_events(path=path)
    assert len(all_events[1]) == 3                     # no filter -> all records


def test_review_events_dedups_within_record_and_skips_junk(tmp_path):
    path = _write_log(tmp_path, [
        {"ts": "2026-07-07T10:00:00+0000", "collection": "c",
         "results": [{"id": 5}, {"id": 5}, {"nope": 1}, "junk"]},
        {"ts": "not-a-date", "collection": "c", "results": [{"id": 5}]},
        "{ broken json",
        {"ts": "2026-07-07T11:00:00+0000", "collection": "c", "results": "nope"},
    ])
    events = retrieval_log.review_events(path=path, collection="c")
    assert len(events[5]) == 1                          # dup collapsed; junk skipped


def test_review_events_missing_file(tmp_path):
    assert retrieval_log.review_events(path=tmp_path / "absent.jsonl") == {}


def test_aggregate_usage_signature_unchanged():
    """Behavior pin (spec D2a): aggregate_usage must NOT gain a collection filter."""
    import inspect
    params = list(inspect.signature(retrieval_log.aggregate_usage).parameters)
    assert params == ["path"]
