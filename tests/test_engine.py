from __future__ import annotations

from datetime import timedelta

from watchtower.adapters import normalize_hook_event
from watchtower.engine import WatchtowerEngine
from watchtower.models import WatchtowerEvent, utc_now
from watchtower.notifier import DesktopNotifier
from watchtower.policy import InterruptionPolicy
from watchtower.store import SQLiteStore


def failed_pytest(session: str, line: int = 42) -> WatchtowerEvent:
    return normalize_hook_event(
        "claude-code",
        {
            "session_id": session,
            "cwd": "/repo",
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/test_checkout.py"},
            "error": f"FAILED tests/test_checkout.py:{line} expected 200 got 500",
        },
    )


def test_repeated_failure_emits_on_third_equivalent_failure(
    engine: WatchtowerEngine,
) -> None:
    assert engine.process(failed_pytest("s1", 42)).interventions == []
    assert engine.process(failed_pytest("s1", 51)).interventions == []
    result = engine.process(failed_pytest("s1", 63))
    assert [item.detector for item in result.interventions] == ["repeated_failure"]


def test_agent_stop_after_failed_validation_emits_gap(engine: WatchtowerEngine) -> None:
    engine.process(failed_pytest("s2"))
    result = engine.process(
        normalize_hook_event(
            "claude-code",
            {"session_id": "s2", "cwd": "/repo", "hook_event_name": "Stop"},
        )
    )
    assert [item.detector for item in result.interventions] == ["verification_gap"]


def test_successful_validation_closes_verification_gap(engine: WatchtowerEngine) -> None:
    engine.process(failed_pytest("s3"))
    engine.process(
        normalize_hook_event(
            "claude-code",
            {
                "session_id": "s3",
                "cwd": "/repo",
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/test_checkout.py"},
                "tool_response": {"exit_code": 0},
            },
        )
    )
    result = engine.process(
        normalize_hook_event(
            "claude-code",
            {"session_id": "s3", "cwd": "/repo", "hook_event_name": "Stop"},
        )
    )
    assert result.interventions == []


def test_compaction_risk_emits_after_material_session_history(
    engine: WatchtowerEngine,
) -> None:
    base = utc_now()
    for index in range(8):
        engine.process(
            WatchtowerEvent(
                occurred_at=base + timedelta(seconds=index),
                source="codex",
                kind="agent.tool.succeeded",
                session_id="compact-1",
                project_path="/repo",
                payload={"tool_name": "Bash"},
            )
        )
    result = engine.process(
        WatchtowerEvent(
            occurred_at=base + timedelta(seconds=10),
            source="codex",
            kind="agent.context.compacting",
            session_id="compact-1",
            project_path="/repo",
        )
    )
    assert [item.detector for item in result.interventions] == ["compaction_risk"]


def test_cross_session_file_overlap_emits_conflict(engine: WatchtowerEngine) -> None:
    first = WatchtowerEvent(
        source="claude-code",
        kind="workspace.file.changed",
        session_id="agent-a",
        project_path="/repo",
        payload={"changed_files": ["src/auth.py"]},
    )
    second = WatchtowerEvent(
        source="codex",
        kind="workspace.file.changed",
        session_id="agent-b",
        project_path="/repo",
        payload={"changed_files": ["src/auth.py", "src/api.py"]},
    )
    assert engine.process(first).interventions == []
    result = engine.process(second)
    assert [item.detector for item in result.interventions] == ["agent_conflict"]


def test_global_interruption_budget_is_enforced(store: SQLiteStore) -> None:
    engine = WatchtowerEngine(
        store,
        policy=InterruptionPolicy(max_interventions_per_hour=1),
        notifier=DesktopNotifier(enabled=False),
    )
    for line in (42, 51, 63):
        first_result = engine.process(failed_pytest("budget", line))
    assert len(first_result.interventions) == 1
    stop_result = engine.process(
        normalize_hook_event(
            "claude-code",
            {"session_id": "budget", "cwd": "/repo", "hook_event_name": "Stop"},
        )
    )
    assert stop_result.interventions == []
