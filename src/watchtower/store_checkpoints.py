from __future__ import annotations

import json
import sqlite3
from typing import Any

from watchtower.models import ContextCheckpoint
from watchtower.store_support import ConnectionFactory, iso


def append_checkpoint(connection_factory: ConnectionFactory, checkpoint: ContextCheckpoint) -> None:
    with connection_factory() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO checkpoints (
                id, created_at, session_id, project_path, intervention_id,
                path, sha256, evidence_event_ids_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint.id,
                iso(checkpoint.created_at),
                checkpoint.session_id,
                checkpoint.project_path,
                checkpoint.intervention_id,
                checkpoint.path,
                checkpoint.sha256,
                json.dumps(checkpoint.evidence_event_ids, separators=(",", ":")),
            ),
        )


def get_checkpoint(
    connection_factory: ConnectionFactory, checkpoint_id: str
) -> ContextCheckpoint | None:
    with connection_factory() as connection:
        row = connection.execute(
            "SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,)
        ).fetchone()
    return _checkpoint_from_row(row) if row else None


def get_checkpoint_for_intervention(
    connection_factory: ConnectionFactory, intervention_id: str
) -> ContextCheckpoint | None:
    with connection_factory() as connection:
        row = connection.execute(
            "SELECT * FROM checkpoints WHERE intervention_id = ? ORDER BY created_at DESC LIMIT 1",
            (intervention_id,),
        ).fetchone()
    return _checkpoint_from_row(row) if row else None


def list_checkpoints(
    connection_factory: ConnectionFactory,
    *,
    limit: int = 100,
    session_id: str | None = None,
    project_path: str | None = None,
) -> list[ContextCheckpoint]:
    clauses: list[str] = []
    parameters: list[Any] = []
    if session_id is not None:
        clauses.append("session_id = ?")
        parameters.append(session_id)
    if project_path is not None:
        clauses.append("project_path = ?")
        parameters.append(project_path)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(max(1, min(limit, 1000)))
    with connection_factory() as connection:
        rows = connection.execute(
            f"SELECT * FROM checkpoints{where} ORDER BY created_at DESC LIMIT ?", parameters
        ).fetchall()
    return [_checkpoint_from_row(row) for row in rows]


def count_checkpoints(connection_factory: ConnectionFactory) -> int:
    with connection_factory() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM checkpoints").fetchone()
    return int(row["count"])


def _checkpoint_from_row(row: sqlite3.Row) -> ContextCheckpoint:
    return ContextCheckpoint(
        id=row["id"],
        created_at=row["created_at"],
        session_id=row["session_id"],
        project_path=row["project_path"],
        intervention_id=row["intervention_id"],
        path=row["path"],
        sha256=row["sha256"],
        evidence_event_ids=json.loads(row["evidence_event_ids_json"]),
    )
