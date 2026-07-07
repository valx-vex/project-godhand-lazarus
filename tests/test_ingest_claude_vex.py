# tests/test_ingest_claude_vex.py
"""Parser contract tests for src/ingest_claude_vex.py (Claude's own brain).

Synthetic fresh-format Claude Code JSONL only — tmp files, no Qdrant, no model.
process_sessions() is NOT exercised here (that would touch live Qdrant); only
the pure parser + helpers are.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ingest_claude_vex as icv
from ingest_ids import memory_point_id


def _write(tmp_path, records):
    path = tmp_path / "session.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return path


def _user(text, **extra):
    rec = {
        "type": "user",
        "message": {"content": text},
        "timestamp": "2026-07-07T01:00:00.000Z",
        "isSidechain": False,
    }
    rec.update(extra)
    return rec


def _assistant(texts, tool_use=False, **extra):
    content = [{"type": "text", "text": t} for t in texts]
    if tool_use:
        content.append({"type": "tool_use", "id": "x", "name": "Bash", "input": {}})
    rec = {"type": "assistant", "message": {"content": content}, "isSidechain": False}
    rec.update(extra)
    return rec


def test_plain_turn_merges_assistant_text(tmp_path):
    """One human prompt + 2 assistant records -> one merged turn; tool_use ignored; ts kept."""
    path = _write(tmp_path, [
        _user("Explain the plan"),
        _assistant(["First part."], tool_use=True),
        _assistant(["Second part with more text here."]),
    ])
    turns = list(icv.parse_transcript(path))
    assert len(turns) == 1
    turn = turns[0]
    assert turn["user_input"] == "Explain the plan"
    assert turn["ai_response"] == "First part.\nSecond part with more text here."
    assert turn["ts"] == "2026-07-07T01:00:00.000Z"
    assert turn["source_file"] == str(path)


def test_sidechain_records_skipped(tmp_path):
    """Sidechain user AND sidechain assistant contribute nothing to the turn."""
    path = _write(tmp_path, [
        _user("Real prompt to Claude here"),
        _assistant(["Real reply that is definitely long enough."]),
        _user("sidechain prompt", isSidechain=True),
        _assistant(["sidechain reply text"], isSidechain=True),
    ])
    turns = list(icv.parse_transcript(path))
    assert len(turns) == 1
    assert turns[0]["ai_response"] == "Real reply that is definitely long enough."


def test_ismeta_user_skipped(tmp_path):
    """isMeta user records are noise -> no turn opens, assistant text is dropped."""
    path = _write(tmp_path, [
        _user("meta noise", isMeta=True),
        _assistant(["some assistant text that is long enough"]),
    ])
    assert list(icv.parse_transcript(path)) == []


def test_list_content_user_is_tool_result_and_skipped(tmp_path):
    """A list-content user record is a tool result: skipped, and the turn keeps flowing."""
    path = _write(tmp_path, [
        _user("Start a turn please"),
        _assistant(["Reply one is here."]),
        {
            "type": "user",
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "x", "content": "cmd output"}
            ]},
            "timestamp": "2026-07-07T01:00:01.000Z",
            "isSidechain": False,
        },
        _assistant(["Reply two after the tool result."]),
    ])
    turns = list(icv.parse_transcript(path))
    assert len(turns) == 1
    assert turns[0]["ai_response"] == "Reply one is here.\nReply two after the tool result."


def test_second_user_starts_new_turn(tmp_path):
    """A second qualifying user record closes the prior turn and opens a new one."""
    path = _write(tmp_path, [
        _user("First question here"),
        _assistant(["First answer that is long enough."]),
        _user("Second question here"),
        _assistant(["Second answer that is long enough."]),
    ])
    turns = list(icv.parse_transcript(path))
    assert len(turns) == 2
    assert turns[0]["user_input"] == "First question here"
    assert turns[0]["ai_response"] == "First answer that is long enough."
    assert turns[1]["user_input"] == "Second question here"
    assert turns[1]["ai_response"] == "Second answer that is long enough."


def test_short_ai_response_still_parsed(tmp_path):
    """The len<20 filter lives in process_sessions, NOT the parser: parse still yields it."""
    path = _write(tmp_path, [
        _user("Short?"),
        _assistant(["ok"]),
    ])
    turns = list(icv.parse_transcript(path))
    assert len(turns) == 1
    assert turns[0]["ai_response"] == "ok"
    assert len(turns[0]["ai_response"]) < 20


def test_point_id_is_deterministic_from_parsed_pair(tmp_path):
    """id is derived deterministically from (source_file, user_input, ai_response)."""
    path = _write(tmp_path, [
        _user("Prompt for id test"),
        _assistant(["An answer long enough for ids."]),
    ])
    turn = list(icv.parse_transcript(path))[0]
    got = memory_point_id(turn["source_file"], turn["user_input"], turn["ai_response"])
    again = memory_point_id(str(path), "Prompt for id test", "An answer long enough for ids.")
    assert got == again
    assert isinstance(got, int)


# --- F2 two-pass skip-existing (spec D1) ---
from qdrant_client import QdrantClient


def _env_f2(monkeypatch, tmp_path):
    monkeypatch.setattr(icv, "CLAUDE_VEX_PROJECTS", tmp_path)
    monkeypatch.setattr(icv, "COLLECTION_NAME", "f2_scratch_cvex")
    # F2 (Task 3 adjudication): brief injects 4-dim fake embeddings but source
    # hard-codes VECTOR_SIZE=384 (prod MiniLM); resize only the test sandbox.
    monkeypatch.setattr(icv, "VECTOR_SIZE", 4)


def _fake_embed_factory():
    return lambda texts: [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _forbidden_embed_factory():
    raise AssertionError("embed factory must not be called when nothing is new")


def test_f2_first_run_then_skip_preserves_marks(monkeypatch, tmp_path):
    _env_f2(monkeypatch, tmp_path)
    path = _write(tmp_path, [
        _user("Remember the bridge"),
        _assistant(["An answer long enough to ingest, yes."]),
    ])
    client = QdrantClient(":memory:")
    assert icv.process_sessions(client=client,
                                embed_factory=_fake_embed_factory) == 0
    pid = memory_point_id(str(path), "Remember the bridge",
                          "An answer long enough to ingest, yes.")
    client.set_payload(collection_name="f2_scratch_cvex",
                       payload={"novelty": 0.7, "invalid_from_ts": 2.0},
                       points=[pid])
    assert icv.process_sessions(client=client,
                                embed_factory=_forbidden_embed_factory) == 0
    got = client.retrieve(collection_name="f2_scratch_cvex", ids=[pid],
                          with_payload=True, with_vectors=False)[0]
    assert got.payload["novelty"] == 0.7
    assert got.payload["invalid_from_ts"] == 2.0


def test_f2_lookup_failure_aborts(monkeypatch, tmp_path, capsys):
    _env_f2(monkeypatch, tmp_path)
    _write(tmp_path, [
        _user("Another prompt"),
        _assistant(["Another answer long enough to ingest."]),
    ])

    class Raising:
        def __init__(self):
            self.upserts = 0

        def get_collection(self, name):
            return object()

        def retrieve(self, *a, **k):
            raise RuntimeError("blip")

        def upsert(self, **k):
            self.upserts += 1

    client = Raising()
    assert icv.process_sessions(client=client,
                                embed_factory=_forbidden_embed_factory) == 1
    assert client.upserts == 0
    assert "aborting without writes" in capsys.readouterr().err


def test_f2_report_line_last(monkeypatch, tmp_path, capsys):
    _env_f2(monkeypatch, tmp_path)
    _write(tmp_path, [
        _user("Prompt for the report line"),
        _assistant(["Reply long enough for the report test."]),
    ])
    client = QdrantClient(":memory:")
    icv.process_sessions(client=client, embed_factory=_fake_embed_factory)
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1] == ("🜂 claude-vex ingest: 1 pairs seen, 0 already present "
                       "(skipped), 1 new → f2_scratch_cvex")


def test_f2_eligible_pairs_filters_short(monkeypatch, tmp_path):
    _env_f2(monkeypatch, tmp_path)
    path = _write(tmp_path, [_user("Short?"), _assistant(["ok"])])
    assert list(icv.eligible_pairs([path])) == []
