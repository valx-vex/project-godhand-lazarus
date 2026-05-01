from __future__ import annotations

from pathlib import Path

import pytest

from web_api.runtime import RuntimeResolutionError, resolve_runtime, reset_runtime_cache


def test_resolve_runtime_prefers_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    reset_runtime_cache()
    source_dir = tmp_path / "mempalace-source"
    package_dir = source_dir / "mempalace"
    package_dir.mkdir(parents=True)
    (package_dir / "mcp_server.py").write_text("# stub\n", encoding="utf-8")
    palace_path = tmp_path / "palace"
    palace_path.mkdir()

    monkeypatch.setenv("MEMPALACE_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", str(palace_path))
    monkeypatch.setenv("MEMPALACE_PYTHON_BIN", "/usr/bin/python3")

    resolved = resolve_runtime()

    assert resolved.source_dir == source_dir.resolve()
    assert resolved.palace_path == palace_path
    assert str(resolved.python_bin) == "/usr/bin/python3"


def test_resolve_runtime_raises_for_missing_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    reset_runtime_cache()
    monkeypatch.setenv("MEMPALACE_SOURCE_DIR", str(tmp_path / "missing"))

    with pytest.raises(RuntimeResolutionError):
        resolve_runtime()
