# Watchtower

**A local-first proactivity control plane for coding agents.**

Watchtower does not try to replace Claude Code, Codex, or another coding agent. It observes lifecycle events, detects when the work process enters a risky or wasteful state, and surfaces an evidence-backed intervention at the useful moment.

> Project status: early alpha, version `0.2.0`. The repository contains a working local daemon, Claude Code and Codex hook adapters, a versioned SQLite schema, four deterministic detectors, a dashboard, structured feedback, safe hook installation, and confirmed local context checkpoints. It does not autonomously modify source files, run remediation commands, or launch another agent.

## The idea

Most agent integrations begin with a user request. Watchtower explores a different primitive:

```text
agent activity
    -> event stream
    -> opportunity detection
    -> interruption policy
    -> grounded intervention
    -> feedback or confirmed action
```

The key product is not another model invocation. It is the layer that decides **when there is enough evidence to speak**.

## What works today

| Capability | Current behavior |
| --- | --- |
| `repeated_failure` | Detects the same failure signature at least three times in 20 minutes |
| `verification_gap` | Detects an agent stopping after the latest test, lint, or type check failed |
| `compaction_risk` | Detects context compaction while active evidence may be lost |
| `agent_conflict` | Detects overlapping edits from different sessions in one project |
| Hook installer | Structurally merges Claude Code or Codex hooks, creates backups, supports dry-run, and is idempotent |
| Structured feedback | Stores useful, not useful, incorrect, early, late, known, disruptive, accepted, or rejected feedback locally |
| Context checkpoint | After explicit confirmation, writes a deterministic Markdown handoff from retained events |
| Local quality metrics | Aggregates feedback by detector without remote telemetry |

Every intervention contains a detector, severity, project and session scope, evidence event IDs, and a proposed action.

## Architecture

```text
Claude Code hooks       Codex hooks       Canonical API
        \                   |                  /
         +---------- event adapters ----------+
                             |
                     privacy reduction
                             |
              versioned local SQLite store
                             |
                  deterministic detectors
                             |
                    interruption policy
                             |
       hook message / desktop / dashboard / feedback
                             |
           explicitly confirmed local checkpoint
```

Vendor payloads are normalized before detector evaluation. Prompts, transcripts, screenshots, keystrokes, and full file contents are outside the default data model.

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

In a second terminal, inspect the hook changes before applying them:

```bash
watchtower install all --scope user --dry-run
watchtower install all --scope user
watchtower doctor
```

Open `http://127.0.0.1:8765`, then exercise the event and detector pipeline:

```bash
watchtower demo
```

The demo sends three equivalent failed test events followed by a stop event. The dashboard should show a repeated-failure intervention and a failed-verification intervention.

## Hook installation

User-level installation:

```bash
watchtower install claude-code --scope user
watchtower install codex --scope user
watchtower install all --scope user
```

Project-level installation:

```bash
watchtower install all --scope project --project-dir /path/to/repository
```

Removal is symmetric and deletes only entries matching the Watchtower-managed hook definitions:

```bash
watchtower uninstall all --scope user --dry-run
watchtower uninstall all --scope user
```

The installer:

- parses and merges existing JSON instead of replacing it;
- preserves unrelated hooks and top-level settings;
- does not duplicate existing Watchtower entries;
- shows a unified diff;
- creates a timestamped backup before every changed write;
- writes atomically in the same directory;
- refuses invalid JSON and symlinked configuration files;
- preflights every target before an `all` operation;
- attempts rollback if a later target fails.

Claude Code user hooks are stored in `~/.claude/settings.json`. Codex user hooks are stored in `~/.codex/hooks.json`. Project scope uses the corresponding directory below the selected repository. Codex may require a trust review before project hooks run.

The checked-in examples remain available at [`examples/claude-code.settings.json`](examples/claude-code.settings.json) and [`examples/codex.hooks.json`](examples/codex.hooks.json).

## Feedback and quality metrics

The dashboard exposes quick `Useful` and `Not useful` actions plus detailed reasons. Feedback is upserted by intervention, so it can be changed later. No feedback leaves the local daemon.

```text
PUT    /v1/interventions/{id}/feedback
DELETE /v1/interventions/{id}/feedback
GET    /v1/feedback
GET    /v1/metrics/quality
```

The current metrics report total, positive, and negative feedback plus per-detector rates. They are descriptive local aggregates, not a claim of model accuracy.

## Confirmed context checkpoints

A `compaction_risk` intervention proposes `create_context_checkpoint`. The dashboard can execute that narrow action after a browser confirmation. The CLI requires `--yes`:

```bash
watchtower checkpoint \
  --session-id SESSION_ID \
  --intervention-id INTERVENTION_ID \
  --yes
```

Checkpoints are Markdown files stored under `~/.watchtower/checkpoints` by default. They contain only retained Watchtower evidence:

- session and source metadata;
- changed-file names;
- successful and failed verification summaries;
- currently open verification errors;
- observed event counts;
- the linked intervention and proposed next step;
- evidence event IDs;
- an explicit list of data Watchtower did not acquire.

Checkpoint identity is derived from the evidence set, making repeated requests for the same intervention idempotent. Files are written atomically with restrictive permissions and verified by SHA-256 when read. Watchtower does not write checkpoints into the source repository and does not commit them.

## Privacy defaults

- The daemon binds to `127.0.0.1` by default.
- Events and interventions are stored in `~/.watchtower/watchtower.db`.
- Checkpoints are stored in `~/.watchtower/checkpoints`.
- Hook payloads are reduced before persistence.
- Full commands are not stored by default.
- Common credentials and bearer tokens are redacted.
- Error excerpts are bounded and marked as content-bearing events.
- Conversation transcripts and user prompts are not read.
- Screenshots and keystrokes are not captured.
- Hook forwarding fails open when the daemon is unavailable.
- Feedback and quality metrics remain local.
- Checkpoint creation requires explicit confirmation.

Command capture is an explicit opt-in:

```bash
watchtower serve --capture-commands
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `WATCHTOWER_DB_PATH` | `~/.watchtower/watchtower.db` | SQLite database path |
| `WATCHTOWER_CHECKPOINTS_DIR` | `~/.watchtower/checkpoints` | Local checkpoint directory |
| `WATCHTOWER_HOST` | `127.0.0.1` | Daemon bind address |
| `WATCHTOWER_PORT` | `8765` | Daemon port |
| `WATCHTOWER_URL` | derived from host and port | URL used by hook commands |
| `WATCHTOWER_CAPTURE_COMMANDS` | `false` | Store redacted command text |
| `WATCHTOWER_DESKTOP_NOTIFICATIONS` | `true` | Enable operating-system notifications |
| `WATCHTOWER_MAX_INTERVENTIONS_PER_HOUR` | `4` | Global interruption budget |
| `WATCHTOWER_MAX_HOOK_BODY_BYTES` | `1048576` | Maximum accepted hook payload |

## HTTP API

```text
GET    /health
POST   /v1/hooks/{source}
POST   /v1/events
GET    /v1/events
GET    /v1/events/{id}
GET    /v1/interventions
PATCH  /v1/interventions/{id}/status
PUT    /v1/interventions/{id}/feedback
DELETE /v1/interventions/{id}/feedback
GET    /v1/feedback
GET    /v1/metrics/quality
GET    /v1/metrics/summary
POST   /v1/checkpoints
GET    /v1/checkpoints
GET    /v1/checkpoints/{id}/content
GET    /
```

FastAPI exposes interactive API documentation at `/docs`.

See [`docs/event-schema.md`](docs/event-schema.md), [`docs/architecture.md`](docs/architecture.md), [`docs/installation.md`](docs/installation.md), and [`docs/checkpoints.md`](docs/checkpoints.md).

## Add a detector

A detector remains a small deterministic component:

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

The current suite contains 37 tests covering privacy reduction, vendor normalization, detector behavior, interruption budgets, migrations, storage idempotency, feedback, hook installation, checkpoint integrity, API ingestion, and hook output.

## Compatibility status

The adapters and installer are tested against versioned synthetic fixtures and the documented configuration shapes in this repository. A matrix of real client versions has not yet been published. See [`docs/compatibility.md`](docs/compatibility.md) for the explicit support status and validation backlog.

## Direction

The next milestones are:

1. Capture and anonymize real hook fixtures from released Claude Code and Codex clients.
2. Add retention, export, purge, and database backup commands.
3. Separate detector candidates from policy decisions and record suppression reasons.
4. Add an evidence detail view with detector thresholds and policy explanations.
5. Build a replay harness and public intervention benchmark.
6. Add a capability-gated action contract, starting with read-only reviewer launches.
7. Package daemon lifecycle management for macOS, Linux, and Windows.
8. Extract the generic detector and policy layer as a proactivity runtime SDK.

The long-term objective is a model-independent, open event layer that lets software become proactive without surrendering user control.

## Contributing and security

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a change. Report security and privacy issues through [`SECURITY.md`](SECURITY.md), not in a public issue.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
