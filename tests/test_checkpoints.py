from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from watchtower.api import create_app
from watchtower.checkpoints import CheckpointError, ContextCheckpointWriter
from watchtower.config import Settings
from watchtower.models import Intervention, WatchtowerEvent
from watchtower.store import SQLiteStore


def _seed(store: SQLiteStore) -> Intervention:
    events = [
        WatchtowerEvent(
            source="claude-code",
            kind="workspace.file.changed",
            session_id="session-1",
            project_path="/repo",
            payload={"changed_files": ["src/auth.py"]},
        ),
        WatchtowerEvent(
            source="claude-code",
            kind="verification.failed",
            session_id="session-1",
            project_path="/repo",
            fingerprint="failure-1",
            sensitivity="content",
            payload={"verification_key": "pytest", "error": "FAILED test_auth.py:<line>"},
        ),
    ]
    for event in events:
        store.append_event(event)
    intervention = Intervention(
        detector="compaction_risk",
        title="Compaction risk",
        message="Create a checkpoint before context is compacted.",
        session_id="session-1",
        project_path="/repo",
        scope_key="claude-code:session-1",
        subject_fingerprint="compaction-1",
        evidence_event_ids=[event.id for event in events],
        suggested_action="create_context_checkpoint",
    )
    store.append_intervention(intervention)
    return intervention


def test_checkpoint_is_deterministic_local_and_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "watchtower.db")
    intervention = _seed(store)
    writer = ContextCheckpointWriter(tmp_path / "checkpoints")

    first = writer.create(
        store,
        session_id="session-1",
        project_path="/repo",
        intervention_id=intervention.id,
    )
    second = writer.create(
        store,
        session_id="session-1",
        project_path="/repo",
        intervention_id=intervention.id,
    )
    assert first.id == second.id
    assert first.path == second.path
    content = Path(first.path).read_text(encoding="utf-8")
    assert "# Watchtower checkpoint" in content
    assert "src/auth.py" in content
    assert r"FAILED test\_auth.py:&lt;line&gt;" in content
    assert "does not retain user prompts or transcripts" in content
    assert len(store.list_checkpoints()) == 1


def test_checkpoint_rejects_project_mismatch(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "watchtower.db")
    intervention = _seed(store)
    writer = ContextCheckpointWriter(tmp_path / "checkpoints")
    with pytest.raises(CheckpointError, match="project do not match"):
        writer.create(
            store,
            session_id="session-1",
            project_path="/different-repo",
            intervention_id=intervention.id,
        )


def test_checkpoint_integrity_is_verified(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "watchtower.db")
    intervention = _seed(store)
    writer = ContextCheckpointWriter(tmp_path / "checkpoints")
    checkpoint = writer.create(
        store,
        session_id="session-1",
        intervention_id=intervention.id,
    )
    Path(checkpoint.path).write_text("tampered", encoding="utf-8")
    with pytest.raises(CheckpointError, match="integrity"):
        writer.read(checkpoint)


def test_checkpoint_api_requires_explicit_confirmation(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            db_path=tmp_path / "api.db",
            checkpoints_dir=tmp_path / "checkpoints",
            desktop_notifications=False,
        )
    )
    intervention = _seed(app.state.store)
    client = TestClient(app)
    payload = {
        "session_id": "session-1",
        "project_path": "/repo",
        "intervention_id": intervention.id,
    }
    denied = client.post("/v1/checkpoints", json={**payload, "confirmed": False})
    assert denied.status_code == 400

    created = client.post("/v1/checkpoints", json={**payload, "confirmed": True})
    assert created.status_code == 200
    checkpoint_id = created.json()["id"]
    content = client.get(f"/v1/checkpoints/{checkpoint_id}/content")
    assert content.status_code == 200
    assert "# Watchtower checkpoint" in content.text
