from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


FeedbackRating = Literal[
    "useful",
    "not_useful",
    "incorrect",
    "too_early",
    "too_late",
    "already_known",
    "too_disruptive",
    "action_accepted",
    "action_rejected",
]


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


class InterventionFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"fb_{uuid4().hex}")
    intervention_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)
    channel: str = Field(default="dashboard", min_length=1, max_length=64)
    detector: str
    detector_version: str = "1"


class ContextCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    created_at: datetime = Field(default_factory=utc_now)
    session_id: str
    project_path: str | None = None
    intervention_id: str | None = None
    path: str
    sha256: str
    evidence_event_ids: list[str] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = True
    event: WatchtowerEvent
    interventions: list[Intervention] = Field(default_factory=list)
