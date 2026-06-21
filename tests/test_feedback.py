from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from watchtower.api import create_app
from watchtower.config import Settings
from watchtower.models import Intervention


def test_feedback_is_local_modifiable_and_aggregated(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            db_path=tmp_path / "feedback.db",
            checkpoints_dir=tmp_path / "checkpoints",
            desktop_notifications=False,
        )
    )
    intervention = Intervention(
        detector="repeated_failure",
        title="Repeated failure",
        message="Three matching failures",
        session_id="s1",
        scope_key="test:s1",
        subject_fingerprint="failure-1",
    )
    app.state.store.append_intervention(intervention)
    client = TestClient(app)

    created = client.put(
        f"/v1/interventions/{intervention.id}/feedback",
        json={"rating": "useful", "channel": "dashboard"},
    )
    assert created.status_code == 200
    feedback_id = created.json()["id"]

    updated = client.put(
        f"/v1/interventions/{intervention.id}/feedback",
        json={"rating": "too_early", "comment": "Correct, but premature"},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == feedback_id
    assert updated.json()["rating"] == "too_early"

    metrics = client.get("/v1/metrics/quality").json()
    assert metrics["overall"]["total"] == 1
    assert metrics["overall"]["negative"] == 1
    assert metrics["by_detector"][0]["detector"] == "repeated_failure"

    summary = client.get("/v1/metrics/summary").json()
    assert summary == {
        "events": 0,
        "interventions": 1,
        "open_interventions": 1,
        "checkpoints": 0,
    }

    deleted = client.delete(f"/v1/interventions/{intervention.id}/feedback")
    assert deleted.status_code == 204
    assert client.get("/v1/feedback").json() == []
