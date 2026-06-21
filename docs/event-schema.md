# Canonical event schema

A canonical event is the boundary between source-specific integrations and the proactivity engine.

```json
{
  "id": "evt_5e12...",
  "occurred_at": "2026-06-20T12:00:00Z",
  "received_at": "2026-06-20T12:00:00Z",
  "source": "claude-code",
  "kind": "verification.failed",
  "session_id": "session-123",
  "project_path": "/workspace/project",
  "fingerprint": "failure_4be8...",
  "sensitivity": "content",
  "payload": {
    "hook_event_name": "PostToolUseFailure",
    "tool_name": "Bash",
    "verification_key": "pytest",
    "error": "FAILED tests/test_auth.py:<line>"
  }
}
```

## Required fields

| Field | Meaning |
| --- | --- |
| `id` | Globally unique event identifier |
| `occurred_at` | Source event time, in UTC when available |
| `received_at` | Time accepted by Watchtower |
| `source` | Adapter name, such as `claude-code` or `codex` |
| `kind` | Stable semantic event name |
| `session_id` | Agent session scope. Subagents append their identifier |
| `sensitivity` | `metadata` or `content` |
| `payload` | Reduced source-specific metadata |

## Optional fields

| Field | Meaning |
| --- | --- |
| `project_path` | Local project scope |
| `fingerprint` | Stable signature for repeated conditions |

## Initial event kinds

```text
agent.session.started
agent.session.ended
agent.prompt.submitted
agent.tool.started
agent.tool.succeeded
agent.tool.failed
agent.permission.requested
agent.permission.denied
agent.context.compacting
agent.context.compacted
agent.turn.stopped
agent.turn.failed
agent.subagent.started
agent.subagent.stopped
agent.task.created
agent.task.completed
agent.notification
verification.succeeded
verification.failed
workspace.file.changed
```

Unknown vendor events are retained as `agent.hook.<lowercase-name>` so the intake remains forward compatible while detector behavior stays explicit.

## Intervention schema

```json
{
  "id": "int_2c8a...",
  "created_at": "2026-06-20T12:01:00Z",
  "detector": "repeated_failure",
  "title": "Repeated failure loop detected",
  "message": "The pytest verification failed three times within 20 minutes.",
  "severity": "warning",
  "session_id": "session-123",
  "project_path": "/workspace/project",
  "scope_key": "claude-code:session-123",
  "subject_fingerprint": "failure_4be8...",
  "evidence_event_ids": ["evt_1", "evt_2", "evt_3"],
  "suggested_action": "launch_read_only_reviewer",
  "status": "new"
}
```

Intervention status is one of `new`, `acknowledged`, `dismissed`, or `resolved`.
