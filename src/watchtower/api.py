from __future__ import annotations

import json
import re
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from watchtower import __version__
from watchtower.adapters import normalize_hook_event
from watchtower.config import Settings
from watchtower.dashboard import dashboard_html
from watchtower.engine import WatchtowerEngine
from watchtower.models import Intervention, ProcessingResult, WatchtowerEvent
from watchtower.notifier import DesktopNotifier
from watchtower.policy import InterruptionPolicy
from watchtower.store import SQLiteStore

_SOURCE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["new", "acknowledged", "dismissed", "resolved"]


async def _read_json(request: Request, max_bytes: int) -> dict:
    total = 0
    chunks: list[bytes] = []
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Hook payload is too large")
        chunks.append(chunk)
    try:
        value = json.loads(b"".join(chunks) or b"{}")
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON") from error
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    return value


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = SQLiteStore(settings.db_path)
    engine = WatchtowerEngine(
        store,
        policy=InterruptionPolicy(settings.max_interventions_per_hour),
        notifier=DesktopNotifier(settings.desktop_notifications),
    )

    app = FastAPI(
        title="Watchtower",
        version=__version__,
        description="Local event intake and proactive intervention API for coding agents.",
    )
    app.state.settings = settings
    app.state.store = store
    app.state.engine = engine

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        return dashboard_html()

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "version": __version__,
            "local_only": settings.host in {"127.0.0.1", "localhost", "::1"},
            "database": str(settings.db_path),
        }

    @app.post("/v1/hooks/{source}", response_model=ProcessingResult)
    async def ingest_hook(source: str, request: Request) -> ProcessingResult:
        if not _SOURCE_PATTERN.fullmatch(source):
            raise HTTPException(status_code=400, detail="Invalid source name")
        raw = await _read_json(request, settings.max_hook_body_bytes)
        event = normalize_hook_event(source, raw, capture_commands=settings.capture_commands)
        return engine.process(event)

    @app.post("/v1/events", response_model=ProcessingResult)
    def ingest_event(event: WatchtowerEvent) -> ProcessingResult:
        return engine.process(event)

    @app.get("/v1/events", response_model=list[WatchtowerEvent])
    def list_events(
        limit: int = Query(default=100, ge=1, le=1000),
        source: str | None = None,
        kind: str | None = None,
        session_id: str | None = None,
        project_path: str | None = None,
    ) -> list[WatchtowerEvent]:
        return store.list_events(
            limit=limit,
            source=source,
            kind=kind,
            session_id=session_id,
            project_path=project_path,
        )

    @app.get("/v1/interventions", response_model=list[Intervention])
    def list_interventions(
        limit: int = Query(default=100, ge=1, le=1000),
        detector: str | None = None,
        status: str | None = None,
    ) -> list[Intervention]:
        return store.list_interventions(limit=limit, detector=detector, status=status)

    @app.patch("/v1/interventions/{intervention_id}/status", response_model=Intervention)
    def update_status(intervention_id: str, update: StatusUpdate) -> Intervention:
        if not store.update_intervention_status(intervention_id, update.status):
            raise HTTPException(status_code=404, detail="Intervention not found")
        intervention = store.get_intervention(intervention_id)
        if intervention is None:
            raise HTTPException(status_code=404, detail="Intervention not found")
        return intervention

    return app
