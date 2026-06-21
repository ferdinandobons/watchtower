from __future__ import annotations

from watchtower.privacy import (
    classify_verification_command,
    extract_changed_files,
    redact_text,
    sanitized_hook_payload,
)


def test_redacts_common_secrets() -> None:
    value = "api_key=supersecret token: abc123 sk-abcdefghijklmnopqrst"
    redacted = redact_text(value)
    assert "supersecret" not in redacted
    assert "abc123" not in redacted
    assert "sk-abcdefghijklmnopqrst" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_commands_are_not_captured_by_default() -> None:
    raw = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/test_auth.py --token secret"},
    }
    payload = sanitized_hook_payload(raw)
    assert payload["verification_key"] == "pytest"
    assert "command" not in payload


def test_command_capture_is_explicit_and_redacted() -> None:
    raw = {"tool_input": {"command": "curl -H 'Authorization: Bearer abcdef' localhost"}}
    payload = sanitized_hook_payload(raw, capture_commands=True)
    assert "abcdef" not in payload["command"]
    assert "[REDACTED]" in payload["command"]


def test_extracts_changed_files_from_patch_without_content() -> None:
    raw = {
        "cwd": "/repo",
        "tool_input": {"command": "*** Begin Patch\n*** Update File: src/auth.py\n*** End Patch"},
    }
    assert extract_changed_files(raw) == ["src/auth.py"]


def test_classifies_common_verification_commands() -> None:
    assert classify_verification_command("python -m pytest -q") == "pytest"
    assert classify_verification_command("npm run test -- --watch=false") == "npm-test"
    assert classify_verification_command("cargo test --workspace") == "cargo-test"
    assert classify_verification_command("echo hello") is None
