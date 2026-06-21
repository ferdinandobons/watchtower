from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="initial_event_store",
        sql="""
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
        """,
    ),
    Migration(
        version=2,
        name="structured_feedback",
        sql="""
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            intervention_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            rating TEXT NOT NULL,
            comment TEXT,
            channel TEXT NOT NULL,
            detector TEXT NOT NULL,
            detector_version TEXT NOT NULL,
            FOREIGN KEY(intervention_id) REFERENCES interventions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_updated
            ON feedback(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_feedback_detector_rating
            ON feedback(detector, rating, updated_at DESC);
        """,
    ),
    Migration(
        version=3,
        name="context_checkpoints",
        sql="""
        CREATE TABLE IF NOT EXISTS checkpoints (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            session_id TEXT NOT NULL,
            project_path TEXT,
            intervention_id TEXT,
            path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            evidence_event_ids_json TEXT NOT NULL,
            FOREIGN KEY(intervention_id) REFERENCES interventions(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_checkpoints_session_time
            ON checkpoints(session_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_intervention
            ON checkpoints(intervention_id);
        """,
    ),
)


def apply_migrations(connection: sqlite3.Connection) -> list[Migration]:
    """Apply all pending schema migrations inside the caller's transaction."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")}
    completed: list[Migration] = []
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        connection.executescript(migration.sql)
        connection.execute(
            "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, datetime.now(UTC).isoformat()),
        )
        completed.append(migration)
    return completed
