from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from watchtower.models import WatchtowerEvent
from watchtower.store_support import ConnectionFactory, iso


def append_event(connection_factory: ConnectionFactory, event: WatchtowerEvent) -> bool:
    with connection_factory() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO events (
                id, occurred_at, received_at, source, kind, session_id,
                project_path, fingerprint, sensitivity, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                iso(event.occurred_at),
                iso(event.received_at),
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


def get_event(connection_factory: ConnectionFactory, event_id: str) -> WatchtowerEvent | None:
    with connection_factory() as connection:
        row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _event_from_row(row) if row else None


def get_events(
    connection_factory: ConnectionFactory, event_ids: Iterable[str]
) -> list[WatchtowerEvent]:
    ordered_ids = list(dict.fromkeys(event_ids))
    if not ordered_ids:
        return []
    placeholders = ",".join("?" for _ in ordered_ids)
    with connection_factory() as connection:
        rows = connection.execute(
            f"SELECT * FROM events WHERE id IN ({placeholders})", ordered_ids
        ).fetchall()
    by_id = {row["id"]: _event_from_row(row) for row in rows}
    return [by_id[event_id] for event_id in ordered_ids if event_id in by_id]


def list_events(
    connection_factory: ConnectionFactory,
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
        parameters.append(iso(since))
    if before is not None:
        clauses.append("occurred_at < ?")
        parameters.append(iso(before))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(max(1, min(limit, 1000)))
    query = f"SELECT * FROM events{where} ORDER BY occurred_at DESC LIMIT ?"
    with connection_factory() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_event_from_row(row) for row in rows]


def count_events(connection_factory: ConnectionFactory) -> int:
    with connection_factory() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM events").fetchone()
    return int(row["count"])


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
