from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class WatchtowerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    occurred_at: datetime = Field(default_factory=utc_now)
    received_at: datetime = Field(default_factory=utc_now)
    source: str
    kind: str
    session_id: str
    project_path: str | None = None
    fingerprint: str | None = None
    sensitivity: Literal["metadata", "content"] = "metadata"
    payload: dict[str, Any] = Field(default_factory=dict)


class Intervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"int_{uuid4().hex}")
    created_at: datetime = Field(default_factory=utc_now)
    detector: str
    title: str
    message: str
    severity: Literal["info", "warning", "critical"] = "info"
    session_id: str
    project_path: str | None = None
    scope_key: str
    subject_fingerprint: str
    evidence_event_ids: list[str] = Field(default_factory=list)
    suggested_action: str | None = None
    status: Literal["new", "acknowledged", "dismissed", "resolved"] = "new"


class ProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = True
    event: WatchtowerEvent
    interventions: list[Intervention] = Field(default_factory=list)
