from __future__ import annotations

from typing import Protocol

from watchtower.models import Intervention, WatchtowerEvent
from watchtower.store import SQLiteStore


class Detector(Protocol):
    @property
    def name(self) -> str: ...

    def evaluate(self, event: WatchtowerEvent, store: SQLiteStore) -> list[Intervention]: ...


def event_scope_key(event: WatchtowerEvent) -> str:
    return f"{event.source}:{event.session_id}"
