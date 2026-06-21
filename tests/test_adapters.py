from __future__ import annotations

from watchtower.adapters import normalize_hook_event


def test_failure_fingerprint_ignores_volatile_line_numbers() -> None:
    first = normalize_hook_event(
        "claude-code",
        {
            "session_id": "s1",
            "cwd": "/repo",
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/test_auth.py"},
            "error": "FAILED tests/test_auth.py:42 expected 200 got 500",
        },
    )
    second = normalize_hook_event(
        "claude-code",
        {
            "session_id": "s1",
            "cwd": "/repo",
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/test_auth.py"},
            "error": "FAILED tests/test_auth.py:77 expected 200 got 500",
        },
    )
    assert first.kind == "verification.failed"
    assert first.fingerprint == second.fingerprint
    assert first.payload["verification_key"] == "pytest"


def test_successful_edit_becomes_workspace_change() -> None:
    event = normalize_hook_event(
        "codex",
        {
            "thread_id": "thread-1",
            "cwd": "/repo",
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"file_path": "/repo/src/main.py"},
            "tool_response": {"success": True},
        },
    )
    assert event.kind == "workspace.file.changed"
    assert event.payload["changed_files"] == ["src/main.py"]


def test_codex_post_tool_use_can_infer_failed_exit_code() -> None:
    event = normalize_hook_event(
        "codex",
        {
            "thread_id": "thread-1",
            "cwd": "/repo",
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "cargo test"},
            "tool_response": {"exit_code": 101, "stderr": "test failed"},
        },
    )
    assert event.kind == "verification.failed"
    assert event.fingerprint


def test_subagent_has_distinct_session_scope() -> None:
    event = normalize_hook_event(
        "claude-code",
        {
            "session_id": "parent",
            "agent_id": "reviewer",
            "hook_event_name": "SubagentStart",
        },
    )
    assert event.session_id == "parent:reviewer"


def test_semantically_different_status_codes_have_different_fingerprints() -> None:
    first = normalize_hook_event(
        "claude-code",
        {
            "session_id": "s1",
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Bash",
            "error": "expected status 200 but got 500",
        },
    )
    second = normalize_hook_event(
        "claude-code",
        {
            "session_id": "s1",
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Bash",
            "error": "expected status 200 but got 401",
        },
    )
    assert first.fingerprint != second.fingerprint


def test_string_tool_response_can_report_nonzero_exit() -> None:
    event = normalize_hook_event(
        "codex",
        {
            "session_id": "s1",
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest"},
            "tool_response": "Process exited with code 1",
        },
    )
    assert event.kind == "verification.failed"
