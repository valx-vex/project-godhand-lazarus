# tests/test_f3_probe.py
"""Guard contract + dead-port failure drill for the F3 dreams probe.

Mirrors tests/test_f2_probe.py (the guard idiom is copied, not reinvented):
a probe must be UNABLE to touch — or dream over — a live brain, whatever the
operator typos. The F3 twist is a SUBSTRING denylist: a name may start with
scratch_ and still embed murphy_eternal / claude_eternal, and must be refused.
The drill proves the night survives a dead Ollama fail-open: dreams skipped
visibly, ZERO reflection rows written, exit 0. Tests never touch a real model
or a live collection."""
import importlib.util
import os
import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

PROBE = REPO / "scripts" / "f3_scratch_probe.py"


def _load():
    spec = importlib.util.spec_from_file_location("f3_scratch_probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Guard: allowlist prefix + denylist SUBSTRING, before any client ──────────
@pytest.mark.parametrize("name", [
    "murphy_eternal", "claude_eternal",            # exact live names
    "scratch_murphy_eternal_x", "scratch_claude_eternal",   # embedded (the twist)
    "murphy_eternal_scratch",                      # live substring, wrong prefix
    "", "scratch_",                                # empty / empty suffix
    "f3_scratch_probe",                            # f2-style name: wrong prefix
    "scratch_UPPER", "scratch_ok extra",           # uppercase / space
])
def test_guard_refuses(name):
    probe = _load()
    with pytest.raises(SystemExit):
        probe.assert_scratch(name)


def test_guard_accepts_scratch_names():
    probe = _load()
    probe.assert_scratch("scratch_f3_probe")
    probe.assert_scratch("scratch_f3_e2e_2")


def test_probe_run_calls_guard_before_touching_client():
    probe = _load()

    class MustNotSeed:
        def collection_exists(self, *a, **k):
            raise AssertionError("guard must fire before any client call")

    with pytest.raises(SystemExit):
        probe.probe_run(MustNotSeed(), "claude_eternal", lambda t: [[0.0]])


def test_main_calls_guard_before_constructing_client(monkeypatch):
    probe = _load()

    def boom():
        raise AssertionError("guard must fire before _client()")

    monkeypatch.setattr(probe, "_client", boom)
    with pytest.raises(SystemExit):
        probe.main(["--collection", "murphy_eternal"])


# ── Failure drill: dead Ollama port, fail-open, zero reflection rows ─────────
def _drill_env(monkeypatch, tmp_path):
    import sleep_salience
    monkeypatch.setenv("LAZARUS_RETRIEVAL_LOG", str(tmp_path / "retrieval.jsonl"))
    monkeypatch.setenv("LAZARUS_SLEEP_REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(sleep_salience, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.delenv("F3_DREAMS_DISABLE", raising=False)
    # sentinel so we can prove the drill flag rewrote it (and monkeypatch cleans up)
    monkeypatch.setenv("F3_OLLAMA_URL", "http://sentinel.invalid:1")


def test_drill_dead_port_skips_dreams_and_writes_no_reflections(monkeypatch, tmp_path):
    probe = _load()
    from f3_fakes import fake_embed
    _drill_env(monkeypatch, tmp_path)
    mem = QdrantClient(":memory:")

    report = probe.probe_run(mem, "scratch_f3_probe", fake_embed,
                             drill_dead_port=True)

    # the drill flag pointed the client at the dead port
    assert os.environ["F3_OLLAMA_URL"] == probe.DEAD_PORT_URL
    # dreams skipped visibly (fail-open)
    dreams = report["dreams"]
    assert dreams["llm_unavailable"] is True or report.get("importance_skipped", 0) > 0
    assert dreams["written"] == 0
    # the six synthetic moments were seeded, and NOTHING dreamed over them
    rows, _ = mem.scroll("scratch_f3_probe", limit=100, with_payload=True)
    assert len(rows) == 6
    assert all(r.payload.get("kind") != "reflection" for r in rows)


def test_main_drill_returns_zero_and_writes_no_reflections(monkeypatch, tmp_path, capsys):
    probe = _load()
    from f3_fakes import fake_embed
    _drill_env(monkeypatch, tmp_path)
    mem = QdrantClient(":memory:")
    monkeypatch.setattr(probe, "_client", lambda: mem)
    monkeypatch.setattr(probe, "_embed_fn", lambda: fake_embed)

    rc = probe.main(["--collection", "scratch_f3_probe", "--drill-dead-port"])

    assert rc == 0
    rows, _ = mem.scroll("scratch_f3_probe", limit=100, with_payload=True)
    assert len(rows) == 6
    assert all(r.payload.get("kind") != "reflection" for r in rows)
    # the dreams section was printed
    assert "llm_unavailable" in capsys.readouterr().out
