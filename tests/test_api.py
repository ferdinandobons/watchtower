from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from watchtower.api import create_app
from watchtower.config import Settings


def test_health_and_hook_pipeline(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            db_path=tmp_path / "api.db",
            desktop_notifications=False,
            max_interventions_per_hour=20,
        )
    )
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"

    for line in (42, 51, 63):
        response = client.post(
            "/v1/hooks/claude-code",
            json={
                "session_id": "api-session",
                "cwd": "/repo",
                "hook_event_name": "PostToolUseFailure",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/test_api.py"},
                "error": f"FAILED tests/test_api.py:{line} expected true got false",
            },
        )
        assert response.status_code == 200

    body = response.json()
    assert body["interventions"][0]["detector"] == "repeated_failure"
    interventions = client.get("/v1/interventions").json()
    intervention_id = interventions[0]["id"]
    updated = client.patch(
        f"/v1/interventions/{intervention_id}/status",
        json={"status": "acknowledged"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "acknowledged"


def test_hook_body_limit(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            db_path=tmp_path / "small.db",
            desktop_notifications=False,
            max_hook_body_bytes=20,
        )
    )
    client = TestClient(app)
    response = client.post(
        "/v1/hooks/codex",
        content=b'{"session_id":"this-is-too-large"}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
