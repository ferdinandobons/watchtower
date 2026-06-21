# Compatibility status

This file separates implemented parsing support from support verified against released clients.

## Current status

| Integration | Configuration shape implemented | Synthetic fixture tests | Real client version range published |
| --- | ---: | ---: | ---: |
| Claude Code command hooks | Yes | Yes | No |
| Codex command hooks | Yes | Yes | No |
| Claude Code installer | Yes | Yes | No |
| Codex installer | Yes | Yes | No |

The absence of a published client range means the repository must not describe a particular released client version as verified.

## Event shapes currently normalized

Claude Code and Codex adapters recognize the following event names when present:

```text
SessionStart
SessionEnd
UserPromptSubmit
PreToolUse
PostToolUse
PostToolUseFailure
PermissionRequest
PermissionDenied
PreCompact
PostCompact
Stop
StopFailure
Notification
SubagentStart
SubagentStop
TaskCreated
TaskCompleted
FileChanged
```

Unknown event names are retained as reduced `agent.hook.<name>` events. An unknown event is not interpreted as a successful tool execution.

## Validation backlog

Before declaring a client version supported:

1. Capture payloads from a controlled session.
2. Remove prompts, personal paths, repository content, and secrets.
3. Add the payload as a versioned fixture.
4. Add a golden normalization test.
5. Verify install, trust review, event delivery, fail-open behavior, and removal.
6. Record operating system, client version, date, and known limitations in this table.

## Environments exercised by CI

The repository CI matrix targets Python 3.11, 3.12, and 3.13 on Ubuntu. Native notification and configuration-path behavior on macOS and Windows still requires dedicated CI jobs.
