# Watchtower

**A local-first proactivity control plane for coding agents.**

Watchtower does not try to replace Claude Code, Codex, or another coding agent. It observes their lifecycle events, detects when the work process has entered a risky or wasteful state, and surfaces an evidence-backed intervention at the useful moment.

> Project status: early alpha. The current release is a working vertical slice with a local daemon, hook adapters, SQLite event storage, four deterministic detectors, an interruption policy, a dashboard, and tests. It does not execute remediation actions autonomously.

## The idea

Most agent integrations answer a request. Watchtower explores a different primitive:

```text
agent activity
    -> event stream
    -> opportunity detection
    -> interruption policy
    -> grounded intervention
    -> human decision
```

The key product is not another model invocation. It is the layer that decides **when there is enough evidence to speak**.

## Working MVP

Watchtower currently detects:

| Detector | Trigger | Suggested response |
| --- | --- | --- |
| `repeated_failure` | The same failure signature appears at least three times in 20 minutes | Pause the strategy and launch an independent read-only review |
| `verification_gap` | An agent stops after the latest test, lint, or type check failed | Reopen with the failed verification attached |
| `compaction_risk` | Context compaction begins while active evidence may be lost | Create a structured checkpoint |
| `agent_conflict` | Different sessions edit overlapping files in the same project | Review a cross-agent diff before continuing |

Every intervention contains the detector, severity, project and session scope, evidence event IDs, and a proposed action. The first version only advises. It does not modify files, run commands, or start another agent without a future explicit approval flow.

## Architecture

```text
Claude Code hooks       Codex hooks       Canonical API
        \                   |                  /
         +---------- event adapters ----------+
                             |
                     privacy reduction
                             |
                     local SQLite store
                             |
                  deterministic detectors
                             |
                    interruption policy
                             |
             hook message / desktop / dashboard
```

The adapters are intentionally thin. The detector engine depends on a canonical event schema rather than vendor-specific payloads.

## Quick start

Requirements: Python 3.11 or newer.

```bash
git clone https://github.com/ferdinandobons/watchtower.git
cd watchtower
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

watchtower serve --no-notifications
```

Open `http://127.0.0.1:8765`, then exercise the complete pipeline in another terminal:

```bash
watchtower demo
```

The demo sends three equivalent failed test events followed by a stop event. The dashboard should show a repeated-failure intervention and a failed-verification intervention.

Useful commands:

```bash
watchtower doctor
watchtower hook claude-code < hook-payload.json
watchtower hook codex < hook-payload.json
python -m watchtower serve
```

## Connect Claude Code

Claude Code command hooks receive lifecycle JSON on standard input. Merge [`examples/claude-code.settings.json`](examples/claude-code.settings.json) into either:

- `~/.claude/settings.json` for all projects
- `.claude/settings.json` for one repository

The example forwards successful and failed tool calls, stop events, subagent completion, and pre-compaction events to the local daemon.

Official reference: https://code.claude.com/docs/en/hooks

## Connect Codex

Copy or merge [`examples/codex.hooks.json`](examples/codex.hooks.json) into either:

- `~/.codex/hooks.json`
- `.codex/hooks.json` inside a trusted repository

Codex emits `PostToolUse` for supported Bash executions even when the command exits with a non-zero status, so Watchtower infers success or failure from the tool response. Codex asks the user to review and trust non-managed hook definitions before running them.

Official reference: https://developers.openai.com/codex/hooks

## Privacy defaults

Watchtower is designed to start with the smallest useful event surface:

- The daemon binds to `127.0.0.1` by default.
- Data is written to `~/.watchtower/watchtower.db`.
- Hook payloads are reduced before storage.
- Full commands are not stored by default.
- Common credentials and bearer tokens are redacted.
- Error excerpts are bounded and marked as content-bearing events.
- Conversation transcripts are not read.
- Screenshots and keystrokes are not captured.
- Hook forwarding fails open when the daemon is unavailable, so an outage does not stop the coding agent.

Command capture is an explicit opt-in:

```bash
watchtower serve --capture-commands
```

Review the privacy model before using that option in a sensitive repository.

## Configuration

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WATCHTOWER_DB_PATH` | `~/.watchtower/watchtower.db` | SQLite database path |
| `WATCHTOWER_HOST` | `127.0.0.1` | Daemon bind address |
| `WATCHTOWER_PORT` | `8765` | Daemon port |
| `WATCHTOWER_URL` | derived from host and port | URL used by hook commands |
| `WATCHTOWER_CAPTURE_COMMANDS` | `false` | Store redacted command text |
| `WATCHTOWER_DESKTOP_NOTIFICATIONS` | `true` | Enable operating-system notifications |
| `WATCHTOWER_MAX_INTERVENTIONS_PER_HOUR` | `4` | Global interruption budget |
| `WATCHTOWER_MAX_HOOK_BODY_BYTES` | `1048576` | Maximum accepted hook payload |

## HTTP API

The daemon exposes:

```text
GET    /health
POST   /v1/hooks/{source}
POST   /v1/events
GET    /v1/events
GET    /v1/interventions
PATCH  /v1/interventions/{id}/status
GET    /
```

FastAPI also exposes interactive API documentation at `/docs`.

A canonical event looks like:

```json
{
  "source": "codex",
  "kind": "verification.failed",
  "session_id": "session-123",
  "project_path": "/workspace/project",
  "fingerprint": "failure_4be8bde7c8b8a78c21df41d0",
  "sensitivity": "content",
  "payload": {
    "tool_name": "Bash",
    "verification_key": "pytest",
    "error": "FAILED tests/test_auth.py:<line>"
  }
}
```

See [`docs/event-schema.md`](docs/event-schema.md) for the contract.

## Add a detector

A detector is a small deterministic component:

```python
from watchtower.models import Intervention, WatchtowerEvent
from watchtower.store import SQLiteStore


class MyDetector:
    name = "my_detector"

    def evaluate(
        self, event: WatchtowerEvent, store: SQLiteStore
    ) -> list[Intervention]:
        if event.kind != "my.trigger":
            return []
        return [
            Intervention(
                detector=self.name,
                title="Something worth reviewing",
                message="The evidence-backed explanation.",
                session_id=event.session_id,
                project_path=event.project_path,
                scope_key=f"{event.source}:{event.session_id}",
                subject_fingerprint=event.id,
                evidence_event_ids=[event.id],
            )
        ]
```

Register it in `WatchtowerEngine`, then add detector-level and end-to-end tests. A detector should remain silent unless its evidence threshold is met.

## Development

```bash
make install
make test
make lint
make run
```

The test suite covers privacy reduction, vendor payload normalization, detector behavior, interruption budgets, storage idempotency, API ingestion, and hook output.

## Direction

The next milestones are:

1. Produce structured context checkpoints before compaction.
2. Create cross-agent handoffs that can be reviewed before injection.
3. Package native Claude Code and Codex installation flows.
4. Record explicit user feedback on every intervention.
5. Add replayable event fixtures and a benchmark for intervention precision.
6. Introduce confirmed action adapters, starting with read-only reviewer launches.
7. Extract the generic detector and policy layer as a proactivity runtime SDK.

The long-term objective is a model-independent, open event layer that lets software become proactive without surrendering user control.

## Contributing and security

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a change. Report security and privacy issues through the process in [`SECURITY.md`](SECURITY.md), not in a public issue.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
