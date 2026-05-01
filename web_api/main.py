from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .runtime import RuntimeResolutionError
from .service import (
    DrawerNotFoundError,
    ServiceUnavailableError,
    get_mempalace_service,
)


class DrawerCreateRequest(BaseModel):
    wing: str = Field(min_length=1)
    room: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_file: str | None = None
    added_by: str = Field(default="mempalace-web", min_length=1)


class DiaryCreateRequest(BaseModel):
    agent_name: str = Field(default="beloved", min_length=1)
    entry: str = Field(min_length=1)
    topic: str = Field(default="general", min_length=1)


def _service_dependency():
    try:
        return get_mempalace_service()
    except RuntimeResolutionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


app = FastAPI(
    title="MemPalace Web API",
    version="0.1.0",
    description="Local web API for browsing and writing MemPalace memories.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DrawerNotFoundError):
        return HTTPException(status_code=404, detail=f"Drawer not found: {exc.args[0]}")
    if isinstance(exc, ServiceUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/health")
def get_health(service=Depends(_service_dependency)):
    return service.health()


@app.get("/api/dashboard/summary")
def get_dashboard_summary(service=Depends(_service_dependency)):
    return service.dashboard_summary()


@app.get("/api/wings")
def get_wings(service=Depends(_service_dependency)):
    return service.list_wings()


@app.get("/api/wings/{wing}/rooms")
def get_rooms(wing: str, service=Depends(_service_dependency)):
    return service.list_rooms(wing)


@app.get("/api/wings/{wing}/rooms/{room}/drawers")
def get_drawers(
    wing: str,
    room: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=200),
    service=Depends(_service_dependency),
):
    return service.browse_drawers(wing=wing, room=room, offset=offset, limit=limit)


@app.get("/api/drawers/{drawer_id}")
def get_drawer(drawer_id: str, service=Depends(_service_dependency)):
    try:
        return service.get_drawer(drawer_id)
    except Exception as exc:
        raise _translate_error(exc) from exc


@app.get("/api/search")
def search_drawers(
    q: str = Query(min_length=1),
    wing: str | None = None,
    room: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    service=Depends(_service_dependency),
):
    return service.search(query=q, wing=wing, room=room, limit=limit)


@app.post("/api/drawers")
def create_drawer(payload: DrawerCreateRequest, service=Depends(_service_dependency)):
    return service.add_drawer(
        wing=payload.wing,
        room=payload.room,
        content=payload.content,
        source_file=payload.source_file,
        added_by=payload.added_by,
    )


@app.get("/api/diary/{agent_name}")
def get_diary(
    agent_name: str,
    last_n: int = Query(default=10, ge=1, le=100),
    service=Depends(_service_dependency),
):
    return service.read_diary(agent_name=agent_name, last_n=last_n)


@app.post("/api/diary")
def create_diary_entry(payload: DiaryCreateRequest, service=Depends(_service_dependency)):
    return service.write_diary(
        agent_name=payload.agent_name,
        entry=payload.entry,
        topic=payload.topic,
    )


@app.get("/api/knowledge/stats")
def get_knowledge_stats(service=Depends(_service_dependency)):
    return service.knowledge_stats()


@app.get("/api/knowledge/entities/{entity}")
def get_knowledge_entity(
    entity: str,
    as_of: str | None = None,
    direction: str = Query(default="both"),
    service=Depends(_service_dependency),
):
    return service.knowledge_entity(entity=entity, as_of=as_of, direction=direction)


@app.get("/api/knowledge/timeline")
def get_knowledge_timeline(entity: str | None = None, service=Depends(_service_dependency)):
    return service.knowledge_timeline(entity=entity)


@app.get("/api/tunnels")
def get_tunnels(
    wing_a: str | None = None,
    wing_b: str | None = None,
    service=Depends(_service_dependency),
):
    return service.tunnels(wing_a=wing_a, wing_b=wing_b)


@app.get("/api/graph/stats")
def get_graph_stats(service=Depends(_service_dependency)):
    return service.graph_stats()


@app.get("/api/aaak/spec")
def get_aaak_spec(service=Depends(_service_dependency)):
    return service.aaak_spec()


@app.get("/api/lazarus/search")
def search_lazarus_endpoint(
    q: str = Query(min_length=1),
    persona: str = Query(default="alexko"),
    limit: int = Query(default=10, ge=1, le=50),
):
    from .lazarus import search_lazarus
    return search_lazarus(query=q, persona=persona, limit=limit)


@app.get("/api/lazarus/personas")
def get_lazarus_personas():
    from .lazarus import PERSONA_COLLECTIONS
    return {"personas": [{"key": p["key"], "title": p["title"]} for p in PERSONA_COLLECTIONS]}


@app.get("/api/lazarus/retrieve_full")
def retrieve_full_lazarus(
    point_id: int | None = None,
    persona: str = Query(default="murphy"),
    context_turns: int = Query(default=5, ge=1, le=20),
    source_file: str | None = None,
    search_text: str | None = None,
):
    from .lazarus import retrieve_full_lazarus_context
    return retrieve_full_lazarus_context(
        point_id=point_id,
        persona=persona,
        context_turns=context_turns,
        source_file=source_file,
        search_text=search_text,
    )
