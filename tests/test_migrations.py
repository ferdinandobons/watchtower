from __future__ import annotations

import sqlite3
from pathlib import Path

from watchtower.store import SQLiteStore


def test_existing_v1_database_is_migrated_without_data_loss(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE events (
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
        CREATE TABLE interventions (
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
        INSERT INTO events VALUES (
            'evt-old', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00',
            'test', 'agent.tool.succeeded', 'session-old', NULL, NULL, 'metadata', '{}'
        );
        """
    )
    connection.commit()
    connection.close()

    store = SQLiteStore(path)
    assert store.schema_version() == store.latest_schema_version == 3
    assert store.get_event("evt-old") is not None
    assert store.list_feedback() == []
    assert store.list_checkpoints() == []
