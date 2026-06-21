# Canonical schemas

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

## Event fields

| Field | Required | Meaning |
| --- | ---: | --- |
| `id` | Yes | Globally unique event identifier |
| `occurred_at` | Yes | Source event time, in UTC when available |
| `received_at` | Yes | Time accepted by Watchtower |
| `source` | Yes | Adapter name, such as `claude-code` or `codex` |
| `kind` | Yes | Stable semantic event name |
| `session_id` | Yes | Agent session scope. Subagents append their identifier |
| `project_path` | No | Local project scope |
| `fingerprint` | No | Stable signature for repeated conditions |
| `sensitivity` | Yes | `metadata` or `content` |
| `payload` | Yes | Reduced source-specific metadata |

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

Unknown vendor events are retained as `agent.hook.<lowercase-name>`. They are not silently interpreted as successful tool executions.

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

## Feedback schema

```json
{
  "id": "fb_91aa...",
  "intervention_id": "int_2c8a...",
  "created_at": "2026-06-20T12:02:00Z",
  "updated_at": "2026-06-20T12:03:00Z",
  "rating": "too_early",
  "comment": "Correct diagnosis, premature interruption.",
  "channel": "dashboard",
  "detector": "repeated_failure",
  "detector_version": "1"
}
```

The current rating vocabulary is:

```text
useful
not_useful
incorrect
too_early
too_late
already_known
too_disruptive
action_accepted
action_rejected
```

## Context checkpoint metadata

```json
{
  "id": "ckpt_c391...",
  "created_at": "2026-06-20T12:04:00Z",
  "session_id": "session-123",
  "project_path": "/workspace/project",
  "intervention_id": "int_2c8a...",
  "path": "/home/user/.watchtower/checkpoints/session-123/ckpt_c391.md",
  "sha256": "28b1...",
  "evidence_event_ids": ["evt_1", "evt_2", "evt_3"]
}
```

The database stores checkpoint metadata and integrity information. Markdown content remains in the local checkpoint directory.
