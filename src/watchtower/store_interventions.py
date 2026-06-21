from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from watchtower.models import Intervention
from watchtower.store_support import ConnectionFactory, iso


def append_intervention(connection_factory: ConnectionFactory, intervention: Intervention) -> None:
    with connection_factory() as connection:
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
                iso(intervention.created_at),
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


def get_intervention(
    connection_factory: ConnectionFactory, intervention_id: str
) -> Intervention | None:
    with connection_factory() as connection:
        row = connection.execute(
            "SELECT * FROM interventions WHERE id = ?", (intervention_id,)
        ).fetchone()
    return _intervention_from_row(row) if row else None


def update_intervention_status(
    connection_factory: ConnectionFactory, intervention_id: str, status: str
) -> bool:
    with connection_factory() as connection:
        cursor = connection.execute(
            "UPDATE interventions SET status = ? WHERE id = ?", (status, intervention_id)
        )
        return cursor.rowcount == 1


def list_interventions(
    connection_factory: ConnectionFactory,
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
    if session_id is not None:
        clauses.append("session_id = ?")
        parameters.append(session_id)
    if project_path is not None:
        clauses.append("project_path = ?")
        parameters.append(project_path)
    if status is not None:
        clauses.append("status = ?")
        parameters.append(status)
    if statuses:
        ordered_statuses = sorted(statuses)
        clauses.append(f"status IN ({','.join('?' for _ in ordered_statuses)})")
        parameters.extend(ordered_statuses)
    if since is not None:
        clauses.append("created_at >= ?")
        parameters.append(iso(since))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(max(1, min(limit, 1000)))
    query = f"SELECT * FROM interventions{where} ORDER BY created_at DESC LIMIT ?"
    with connection_factory() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_intervention_from_row(row) for row in rows]


def count_interventions(
    connection_factory: ConnectionFactory,
    *,
    since: datetime | None = None,
    statuses: Iterable[str] | None = None,
) -> int:
    clauses: list[str] = []
    parameters: list[Any] = []
    if since is not None:
        clauses.append("created_at >= ?")
        parameters.append(iso(since))
    if statuses:
        ordered_statuses = sorted(set(statuses))
        clauses.append(f"status IN ({','.join('?' for _ in ordered_statuses)})")
        parameters.extend(ordered_statuses)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connection_factory() as connection:
        row = connection.execute(
            f"SELECT COUNT(*) AS count FROM interventions{where}", parameters
        ).fetchone()
    return int(row["count"])


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
