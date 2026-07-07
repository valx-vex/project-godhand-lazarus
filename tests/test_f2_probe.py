# tests/test_f2_probe.py
"""Guard contract for the F2 activation probe — the reviewed Critical:
a probe must be UNABLE to touch a live brain, whatever the operator typos."""
import importlib.util
import sys
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parent.parent / "scripts" / "f2_scratch_probe.py"


def _load():
    spec = importlib.util.spec_from_file_location("f2_scratch_probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", [
    "murphy_eternal", "claude_eternal", "vault_eternal", "murphy_flash",
    "f2_scratch_", "scratch_f2", "f2_scratch_UPPER", "", "f2_scratch_ok extra",
])
def test_guard_refuses(name):
    probe = _load()
    with pytest.raises(SystemExit):
        probe.assert_scratch(name)


def test_guard_accepts_scratch_names():
    probe = _load()
    probe.assert_scratch("f2_scratch_hermes")
    probe.assert_scratch("f2_scratch_cvex_2")


def test_delete_calls_guard_first():
    probe = _load()

    class MustNotDelete:
        def delete_collection(self, name):
            raise AssertionError("guard must fire before delete")

    with pytest.raises(SystemExit):
        probe.cmd_delete(MustNotDelete(), "claude_eternal")


def test_mark_sets_derived_and_invalidation_fields():
    probe = _load()

    class Recorder:
        def __init__(self):
            self.calls = []

        def set_payload(self, collection_name, payload, points):
            self.calls.append((collection_name, payload, points))

    client = Recorder()
    probe.cmd_mark(client, "f2_scratch_x", 42)
    (coll, payload, points), = client.calls
    assert coll == "f2_scratch_x" and points == [42]
    assert payload["salience"] == 0.9
    assert payload["invalid_from_ts"] > 0
    assert payload["invalidation_reason"] == "f2 durability probe"
