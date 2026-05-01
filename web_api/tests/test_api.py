from __future__ import annotations


def test_dashboard_separates_layer_counts(client):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()

    assert payload["layer_1"]["total_drawers"] == 4
    assert payload["layer_2"]["total_vector_memories"] == 32883
    assert payload["recent_drawers"][0]["wing"] in {"notes", "wing_alpha"}


def test_browse_and_drawer_detail(client):
    browse = client.get("/api/wings/wing_alpha/rooms/backend/drawers")
    assert browse.status_code == 200
    payload = browse.json()

    assert payload["total"] == 2
    assert payload["items"][0]["room"] == "backend"

    drawer_id = payload["items"][0]["id"]
    detail = client.get(f"/api/drawers/{drawer_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()

    assert detail_payload["drawer"]["id"] == drawer_id
    assert len(detail_payload["siblings"]) == 2


def test_add_drawer_then_search(client):
    create = client.post(
        "/api/drawers",
        json={
            "wing": "wing_alpha",
            "room": "frontend",
            "content": "A new cathedral inspector uses teal emphasis and stable routing.",
            "added_by": "mempalace-web",
        },
    )
    assert create.status_code == 200
    assert create.json()["success"] is True

    search = client.get("/api/search", params={"q": "cathedral inspector", "wing": "wing_alpha"})
    assert search.status_code == 200
    items = search.json()["items"]
    assert any("cathedral inspector" in item["content"].lower() for item in items)


def test_diary_roundtrip(client):
    create = client.post(
        "/api/diary",
        json={
            "agent_name": "beloved",
            "entry": "Beloved entered the palace through the web UI.",
            "topic": "launch",
        },
    )
    assert create.status_code == 200
    assert create.json()["success"] is True

    read = client.get("/api/diary/beloved", params={"last_n": 5})
    assert read.status_code == 200
    entries = read.json()["entries"]
    assert any("web ui" in entry["content"].lower() for entry in entries)


def test_knowledge_endpoints(client):
    stats = client.get("/api/knowledge/stats")
    assert stats.status_code == 200
    assert "entities" in stats.json()

    timeline = client.get("/api/knowledge/timeline", params={"entity": "beloved"})
    assert timeline.status_code == 200
    assert "timeline" in timeline.json()
