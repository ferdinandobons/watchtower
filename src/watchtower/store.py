from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from watchtower.models import Intervention, WatchtowerEvent


def _iso(value: datetime) -> str:
    return value.isoformat()


class SQLiteStore:
    """Small SQLite event store. A new connection is used for every operation."""

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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    project_path TEXT,
                    fingerprint TEXT,
                    sensitivity TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_time
                    ON events(occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_session_time
                    ON events(session_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_project_time
                    ON events(project_path, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_fingerprint_time
                    ON events(fingerprint, occurred_at DESC);

                CREATE TABLE IF NOT EXISTS interventions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    detector TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    project_path TEXT,
                    scope_key TEXT NOT NULL,
                    subject_fingerprint TEXT NOT NULL,
                    evidence_event_ids_json TEXT NOT NULL,
                    suggested_action TEXT,
                    status TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_interventions_time
                    ON interventions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_interventions_detector_scope
                    ON interventions(detector, scope_key, subject_fingerprint, created_at DESC);
                """
            )

    def append_event(self, event: WatchtowerEvent) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO events (
                    id, occurred_at, received_at, source, kind, session_id,
                    project_path, fingerprint, sensitivity, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    _iso(event.occurred_at),
                    _iso(event.received_at),
                    event.source,
                    event.kind,
                    event.session_id,
                    event.project_path,
                    event.fingerprint,
                    event.sensitivity,
                    json.dumps(event.payload, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            return cursor.rowcount == 1

    def append_intervention(self, intervention: Intervention) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO interventions (
                    id, created_at, detector, title, message, severity, session_id,
                    project_path, scope_key, subject_fingerprint,
                    evidence_event_ids_json, suggested_action, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intervention.id,
                    _iso(intervention.created_at),
                    intervention.detector,
                    intervention.title,
                    intervention.message,
                    intervention.severity,
                    intervention.session_id,
                    intervention.project_path,
                    intervention.scope_key,
                    intervention.subject_fingerprint,
                    json.dumps(intervention.evidence_event_ids, separators=(",", ":")),
                    intervention.suggested_action,
                    intervention.status,
                ),
            )

    def get_intervention(self, intervention_id: str) -> Intervention | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
        return self._intervention_from_row(row) if row else None

    def update_intervention_status(self, intervention_id: str, status: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE interventions SET status = ? WHERE id = ?",
                (status, intervention_id),
            )
            return cursor.rowcount == 1

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
        clauses: list[str] = []
        parameters: list[Any] = []
        if source is not None:
            clauses.append("source = ?")
            parameters.append(source)
        if kind is not None:
            clauses.append("kind = ?")
            parameters.append(kind)
        if kinds:
            ordered_kinds = sorted(kinds)
            clauses.append(f"kind IN ({','.join('?' for _ in ordered_kinds)})")
            parameters.extend(ordered_kinds)
        if session_id is not None:
            clauses.append("session_id = ?")
            parameters.append(session_id)
        if project_path is not None:
            clauses.append("project_path = ?")
            parameters.append(project_path)
        if fingerprint is not None:
            clauses.append("fingerprint = ?")
            parameters.append(fingerprint)
        if since is not None:
            clauses.append("occurred_at >= ?")
            parameters.append(_iso(since))
        if before is not None:
            clauses.append("occurred_at < ?")
            parameters.append(_iso(before))

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(max(1, min(limit, 1000)))
        query = f"SELECT * FROM events{where} ORDER BY occurred_at DESC LIMIT ?"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._event_from_row(row) for row in rows]

    def list_interventions(
        self,
        *,
        limit: int = 100,
        detector: str | None = None,
        scope_key: str | None = None,
        subject_fingerprint: str | None = None,
        status: str | None = None,
        statuses: set[str] | None = None,
        since: datetime | None = None,
    ) -> list[Intervention]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if detector is not None:
            clauses.append("detector = ?")
            parameters.append(detector)
        if scope_key is not None:
            clauses.append("scope_key = ?")
            parameters.append(scope_key)
        if subject_fingerprint is not None:
            clauses.append("subject_fingerprint = ?")
            parameters.append(subject_fingerprint)
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status)
        if statuses:
            ordered_statuses = sorted(statuses)
            clauses.append(f"status IN ({','.join('?' for _ in ordered_statuses)})")
            parameters.extend(ordered_statuses)
        if since is not None:
            clauses.append("created_at >= ?")
            parameters.append(_iso(since))

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(max(1, min(limit, 1000)))
        query = f"SELECT * FROM interventions{where} ORDER BY created_at DESC LIMIT ?"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._intervention_from_row(row) for row in rows]

    def count_interventions(
        self, *, since: datetime | None = None, statuses: Iterable[str] | None = None
    ) -> int:
        clauses: list[str] = []
        parameters: list[Any] = []
        if since is not None:
            clauses.append("created_at >= ?")
            parameters.append(_iso(since))
        if statuses:
            ordered_statuses = sorted(set(statuses))
            clauses.append(f"status IN ({','.join('?' for _ in ordered_statuses)})")
            parameters.extend(ordered_statuses)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connection() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM interventions{where}", parameters
            ).fetchone()
        return int(row["count"])

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> WatchtowerEvent:
        return WatchtowerEvent(
            id=row["id"],
            occurred_at=row["occurred_at"],
            received_at=row["received_at"],
            source=row["source"],
            kind=row["kind"],
            session_id=row["session_id"],
            project_path=row["project_path"],
            fingerprint=row["fingerprint"],
            sensitivity=row["sensitivity"],
            payload=json.loads(row["payload_json"]),
        )

    @staticmethod
    def _intervention_from_row(row: sqlite3.Row) -> Intervention:
        return Intervention(
            id=row["id"],
            created_at=row["created_at"],
            detector=row["detector"],
            title=row["title"],
            message=row["message"],
            severity=row["severity"],
            session_id=row["session_id"],
            project_path=row["project_path"],
            scope_key=row["scope_key"],
            subject_fingerprint=row["subject_fingerprint"],
            evidence_event_ids=json.loads(row["evidence_event_ids_json"]),
            suggested_action=row["suggested_action"],
            status=row["status"],
        )
