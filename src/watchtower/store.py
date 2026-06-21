from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from watchtower import store_checkpoints, store_events, store_feedback, store_interventions
from watchtower.migrations import MIGRATIONS, apply_migrations
from watchtower.models import ContextCheckpoint, Intervention, InterventionFeedback, WatchtowerEvent


class SQLiteStore:
    """Small SQLite event store with explicit, forward-only migrations."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connection() as connection:
            apply_migrations(connection)

    def schema_version(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
        return int(row["version"])

    @property
    def latest_schema_version(self) -> int:
        return MIGRATIONS[-1].version

    def append_event(self, event: WatchtowerEvent) -> bool:
        return store_events.append_event(self._connection, event)

    def get_event(self, event_id: str) -> WatchtowerEvent | None:
        return store_events.get_event(self._connection, event_id)

    def get_events(self, event_ids: Iterable[str]) -> list[WatchtowerEvent]:
        return store_events.get_events(self._connection, event_ids)

    def list_events(
        self,
        *,
        limit: int = 100,
        source: str | None = None,
        kind: str | None = None,
        kinds: set[str] | None = None,
        session_id: str | None = None,
        project_path: str | None = None,
        fingerprint: str | None = None,
        since: datetime | None = None,
        before: datetime | None = None,
    ) -> list[WatchtowerEvent]:
        return store_events.list_events(
            self._connection,
            limit=limit,
            source=source,
            kind=kind,
            kinds=kinds,
            session_id=session_id,
            project_path=project_path,
            fingerprint=fingerprint,
            since=since,
            before=before,
        )

    def count_events(self) -> int:
        return store_events.count_events(self._connection)

    def append_intervention(self, intervention: Intervention) -> None:
        store_interventions.append_intervention(self._connection, intervention)

    def get_intervention(self, intervention_id: str) -> Intervention | None:
        return store_interventions.get_intervention(self._connection, intervention_id)

    def update_intervention_status(self, intervention_id: str, status: str) -> bool:
        return store_interventions.update_intervention_status(
            self._connection, intervention_id, status
        )

    def list_interventions(
        self,
        *,
        limit: int = 100,
        detector: str | None = None,
        scope_key: str | None = None,
        subject_fingerprint: str | None = None,
        session_id: str | None = None,
        project_path: str | None = None,
        status: str | None = None,
        statuses: set[str] | None = None,
        since: datetime | None = None,
    ) -> list[Intervention]:
        return store_interventions.list_interventions(
            self._connection,
            limit=limit,
            detector=detector,
            scope_key=scope_key,
            subject_fingerprint=subject_fingerprint,
            session_id=session_id,
            project_path=project_path,
            status=status,
            statuses=statuses,
            since=since,
        )

    def count_interventions(
        self, *, since: datetime | None = None, statuses: Iterable[str] | None = None
    ) -> int:
        return store_interventions.count_interventions(
            self._connection, since=since, statuses=statuses
        )

    def upsert_feedback(self, feedback: InterventionFeedback) -> InterventionFeedback:
        return store_feedback.upsert_feedback(self._connection, feedback)

    def get_feedback(self, intervention_id: str) -> InterventionFeedback | None:
        return store_feedback.get_feedback(self._connection, intervention_id)

    def delete_feedback(self, intervention_id: str) -> bool:
        return store_feedback.delete_feedback(self._connection, intervention_id)

    def list_feedback(
        self,
        *,
        limit: int = 100,
        detector: str | None = None,
        rating: str | None = None,
    ) -> list[InterventionFeedback]:
        return store_feedback.list_feedback(
            self._connection, limit=limit, detector=detector, rating=rating
        )

    def quality_metrics(self) -> dict[str, Any]:
        return store_feedback.quality_metrics(self._connection)

    def append_checkpoint(self, checkpoint: ContextCheckpoint) -> None:
        store_checkpoints.append_checkpoint(self._connection, checkpoint)

    def get_checkpoint(self, checkpoint_id: str) -> ContextCheckpoint | None:
        return store_checkpoints.get_checkpoint(self._connection, checkpoint_id)

    def get_checkpoint_for_intervention(self, intervention_id: str) -> ContextCheckpoint | None:
        return store_checkpoints.get_checkpoint_for_intervention(self._connection, intervention_id)

    def list_checkpoints(
        self,
        *,
        limit: int = 100,
        session_id: str | None = None,
        project_path: str | None = None,
    ) -> list[ContextCheckpoint]:
        return store_checkpoints.list_checkpoints(
            self._connection,
            limit=limit,
            session_id=session_id,
            project_path=project_path,
        )

    def count_checkpoints(self) -> int:
        return store_checkpoints.count_checkpoints(self._connection)
