from __future__ import annotations

from pathlib import Path
from typing import Any

from watchtower.fingerprints import failure_fingerprint
from watchtower.models import WatchtowerEvent
from watchtower.privacy import extract_error, infer_tool_failure, sanitized_hook_payload

_EVENT_KIND_MAP = {
    "SessionStart": "agent.session.started",
    "SessionEnd": "agent.session.ended",
    "UserPromptSubmit": "agent.prompt.submitted",
    "PreToolUse": "agent.tool.started",
    "PermissionRequest": "agent.permission.requested",
    "PermissionDenied": "agent.permission.denied",
    "PreCompact": "agent.context.compacting",
    "PostCompact": "agent.context.compacted",
    "Stop": "agent.turn.stopped",
    "StopFailure": "agent.turn.failed",
    "Notification": "agent.notification",
    "SubagentStart": "agent.subagent.started",
    "SubagentStop": "agent.subagent.stopped",
    "TaskCreated": "agent.task.created",
    "TaskCompleted": "agent.task.completed",
    "FileChanged": "workspace.file.changed",
}


def _normalise_source(source: str) -> str:
    aliases = {
        "claude": "claude-code",
        "claude_code": "claude-code",
        "openai-codex": "codex",
    }
    return aliases.get(source.strip().lower(), source.strip().lower())


def _normalise_project_path(value: Any) -> str | None:
    if not value:
        return None
    return Path(str(value)).expanduser().as_posix()


def normalize_hook_event(
    source: str,
    raw: dict[str, Any],
    *,
    capture_commands: bool = False,
) -> WatchtowerEvent:
    """Convert Claude Code or Codex hook JSON into a minimal canonical event."""
    source = _normalise_source(source)
    event_name = str(raw.get("hook_event_name") or raw.get("event") or "Unknown")
    parent_session = str(
        raw.get("session_id") or raw.get("thread_id") or raw.get("conversation_id") or "unknown"
    )
    agent_id = raw.get("agent_id")
    session_id = f"{parent_session}:{agent_id}" if agent_id else parent_session
    project_path = _normalise_project_path(raw.get("cwd") or raw.get("project_path"))
    payload = sanitized_hook_payload(raw, capture_commands=capture_commands)

    kind = _EVENT_KIND_MAP.get(event_name, f"agent.hook.{event_name.lower()}")
    fingerprint: str | None = None

    if event_name in {"PostToolUse", "PostToolUseFailure"}:
        failed = infer_tool_failure(raw)
        verification_key = payload.get("verification_key")
        if verification_key:
            kind = "verification.failed" if failed else "verification.succeeded"
        elif payload.get("changed_files") and not failed:
            kind = "workspace.file.changed"
        else:
            kind = "agent.tool.failed" if failed else "agent.tool.succeeded"

        if failed:
            error = extract_error(raw)
            payload["error"] = error
            fingerprint = failure_fingerprint(
                tool_name=str(payload.get("tool_name") or "unknown"),
                verification_key=str(verification_key) if verification_key else None,
                error=error,
            )

    if event_name == "PermissionDenied":
        error = str(raw.get("reason") or "Permission denied")
        payload["error"] = error
        fingerprint = failure_fingerprint(
            tool_name=str(payload.get("tool_name") or "unknown"),
            verification_key=None,
            error=error,
        )

    return WatchtowerEvent(
        source=source,
        kind=kind,
        session_id=session_id,
        project_path=project_path,
        fingerprint=fingerprint,
        sensitivity="content" if "error" in payload or "command" in payload else "metadata",
        payload=payload,
    )
