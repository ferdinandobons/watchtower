from __future__ import annotations

import json
import re
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from watchtower import __version__
from watchtower.adapters import normalize_hook_event
from watchtower.checkpoints import CheckpointError, CheckpointNotFound, ContextCheckpointWriter
from watchtower.config import Settings
from watchtower.dashboard import dashboard_html
from watchtower.engine import WatchtowerEngine
from watchtower.models import (
    ContextCheckpoint,
    FeedbackRating,
    Intervention,
    InterventionFeedback,
    ProcessingResult,
    WatchtowerEvent,
    utc_now,
)
from watchtower.notifier import DesktopNotifier
from watchtower.policy import InterruptionPolicy
from watchtower.store import SQLiteStore

_SOURCE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["new", "acknowledged", "dismissed", "resolved"]


class FeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)
    channel: str = Field(default="dashboard", min_length=1, max_length=64)


class CheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=512)
    project_path: str | None = Field(default=None, max_length=4096)
    intervention_id: str | None = Field(default=None, max_length=128)
    confirmed: bool = False


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
    checkpoint_writer = ContextCheckpointWriter(settings.checkpoints_dir)
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
    app.state.checkpoint_writer = checkpoint_writer

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        return dashboard_html()

    @app.get("/health")
    def health() -> dict[str, str | bool | int]:
        return {
            "status": "ok",
            "version": __version__,
            "local_only": settings.host in {"127.0.0.1", "localhost", "::1"},
            "database": str(settings.db_path),
            "schema_version": store.schema_version(),
            "latest_schema_version": store.latest_schema_version,
            "checkpoints_dir": str(settings.checkpoints_dir),
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

    @app.get("/v1/events/{event_id}", response_model=WatchtowerEvent)
    def get_event(event_id: str) -> WatchtowerEvent:
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event

    @app.get("/v1/interventions", response_model=list[Intervention])
    def list_interventions(
        limit: int = Query(default=100, ge=1, le=1000),
        detector: str | None = None,
        status: str | None = None,
        session_id: str | None = None,
        project_path: str | None = None,
    ) -> list[Intervention]:
        return store.list_interventions(
            limit=limit,
            detector=detector,
            status=status,
            session_id=session_id,
            project_path=project_path,
        )

    @app.patch("/v1/interventions/{intervention_id}/status", response_model=Intervention)
    def update_status(intervention_id: str, update: StatusUpdate) -> Intervention:
        if not store.update_intervention_status(intervention_id, update.status):
            raise HTTPException(status_code=404, detail="Intervention not found")
        intervention = store.get_intervention(intervention_id)
        if intervention is None:
            raise HTTPException(status_code=404, detail="Intervention not found")
        return intervention

    @app.put(
        "/v1/interventions/{intervention_id}/feedback",
        response_model=InterventionFeedback,
    )
    def set_feedback(intervention_id: str, update: FeedbackUpdate) -> InterventionFeedback:
        intervention = store.get_intervention(intervention_id)
        if intervention is None:
            raise HTTPException(status_code=404, detail="Intervention not found")
        existing = store.get_feedback(intervention_id)
        now = utc_now()
        feedback = InterventionFeedback(
            id=existing.id if existing else f"fb_{uuid4().hex}",
            intervention_id=intervention_id,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            rating=update.rating,
            comment=update.comment,
            channel=update.channel,
            detector=intervention.detector,
            detector_version="1",
        )
        return store.upsert_feedback(feedback)

    @app.delete("/v1/interventions/{intervention_id}/feedback", status_code=204)
    def delete_feedback(intervention_id: str) -> None:
        if not store.delete_feedback(intervention_id):
            raise HTTPException(status_code=404, detail="Feedback not found")

    @app.get("/v1/feedback", response_model=list[InterventionFeedback])
    def list_feedback(
        limit: int = Query(default=100, ge=1, le=1000),
        detector: str | None = None,
        rating: str | None = None,
    ) -> list[InterventionFeedback]:
        return store.list_feedback(limit=limit, detector=detector, rating=rating)

    @app.get("/v1/metrics/quality")
    def quality_metrics() -> dict:
        return store.quality_metrics()

    @app.get("/v1/metrics/summary")
    def summary_metrics() -> dict[str, int]:
        return {
            "events": store.count_events(),
            "interventions": store.count_interventions(),
            "open_interventions": store.count_interventions(statuses={"new"}),
            "checkpoints": store.count_checkpoints(),
        }

    @app.post("/v1/checkpoints", response_model=ContextCheckpoint)
    def create_checkpoint(request: CheckpointRequest) -> ContextCheckpoint:
        if not request.confirmed:
            raise HTTPException(
                status_code=400,
                detail="Explicit confirmation is required before writing a checkpoint",
            )
        try:
            return checkpoint_writer.create(
                store,
                session_id=request.session_id,
                project_path=request.project_path,
                intervention_id=request.intervention_id,
            )
        except CheckpointNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CheckpointError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/v1/checkpoints", response_model=list[ContextCheckpoint])
    def list_checkpoints(
        limit: int = Query(default=100, ge=1, le=1000),
        session_id: str | None = None,
        project_path: str | None = None,
    ) -> list[ContextCheckpoint]:
        return store.list_checkpoints(
            limit=limit,
            session_id=session_id,
            project_path=project_path,
        )

    @app.get("/v1/checkpoints/{checkpoint_id}/content", response_class=PlainTextResponse)
    def checkpoint_content(checkpoint_id: str) -> str:
        checkpoint = store.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        try:
            return checkpoint_writer.read(checkpoint)
        except CheckpointNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CheckpointError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app
