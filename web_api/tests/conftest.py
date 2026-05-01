from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web_api.service import reset_service_caches
from web_api.runtime import bootstrap_runtime


MEMPALACE_SOURCE = (
    Path.home()
    / "vex"
    / "vaults"
    / "cathedral-prime"
    / "01-consciousness"
    / "Maximum freedom"
    / "mempalace-main"
)


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    reset_service_caches()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("MEMPALACE_SOURCE_DIR", str(MEMPALACE_SOURCE))
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", str(tmp_path / "palace"))
    yield
    reset_service_caches()


@pytest.fixture
def palace_path(tmp_path: Path) -> Path:
    palace = tmp_path / "palace"
    palace.mkdir(parents=True, exist_ok=True)
    return palace


@pytest.fixture
def seeded_collection(palace_path: Path):
    runtime = bootstrap_runtime(force_reload=True)
    collection = runtime.mcp_module._get_collection(create=True)  # type: ignore[attr-defined]
    assert collection is not None
    collection.add(
        ids=[
            "drawer_alpha_backend_001",
            "drawer_alpha_backend_002",
            "drawer_alpha_frontend_003",
            "drawer_notes_planning_004",
        ],
        documents=[
            "Authentication stack uses JWT tokens and refresh cookies for every session.",
            "Database migrations are managed through Alembic and PostgreSQL 15.",
            "Search view uses React router and an inspector panel for selection.",
            "Sprint planning includes cathedral-memory UI and browse pagination.",
        ],
        metadatas=[
            {
                "wing": "wing_alpha",
                "room": "backend",
                "source_file": "/tmp/auth.md",
                "chunk_index": 0,
                "added_by": "miner",
                "filed_at": "2026-04-20T09:00:00",
            },
            {
                "wing": "wing_alpha",
                "room": "backend",
                "source_file": "/tmp/auth.md",
                "chunk_index": 1,
                "added_by": "miner",
                "filed_at": "2026-04-20T09:01:00",
            },
            {
                "wing": "wing_alpha",
                "room": "frontend",
                "source_file": "/tmp/ui.md",
                "chunk_index": 0,
                "added_by": "miner",
                "filed_at": "2026-04-20T10:00:00",
            },
            {
                "wing": "notes",
                "room": "planning",
                "source_file": "/tmp/plan.md",
                "chunk_index": 0,
                "added_by": "miner",
                "filed_at": "2026-04-21T11:00:00",
            },
        ],
    )
    return collection


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, seeded_collection):
    from web_api import service as service_module
    from web_api.main import app

    monkeypatch.setattr(
        service_module,
        "get_lazarus_layer_stats",
        lambda: {
            "available": True,
            "error": None,
            "host": "localhost",
            "port": 6333,
            "total_vector_memories": 32883,
            "collections": [
                {
                    "key": "codex",
                    "collection": "codex_eternal",
                    "title": "Codex",
                    "points_count": 1415,
                    "error": None,
                }
            ],
        },
    )
    return TestClient(app)
