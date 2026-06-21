# Architecture

Watchtower separates perception, opportunity detection, interruption policy, presentation, feedback, and confirmed action execution. The separation prevents the system from collapsing into one opaque model call.

## 1. Event sources

The first adapters consume lifecycle events from Claude Code and Codex. Future sources may include Git, test runners, editor diagnostics, CI, and explicitly authorized local activity tools.

Vendor payloads must not enter detector code directly.

## 2. Normalization and privacy reduction

`watchtower.adapters.hooks.normalize_hook_event` maps vendor payloads into `WatchtowerEvent`.

Before persistence, the adapter:

- keeps a bounded allowlist of scalar metadata;
- classifies common test, lint, and type-check commands;
- extracts changed-file names without storing file contents;
- redacts common credential formats;
- stores full command text only when explicitly enabled;
- creates stable failure fingerprints after removing volatile values.

Transcript paths supplied by agent hooks are ignored.

## 3. Versioned local store

SQLite stores events, accepted interventions, structured feedback, and context-checkpoint metadata. Forward-only migrations are recorded in `schema_migrations`.

The store provides:

- idempotent event ingestion;
- time-window queries;
- session and project scopes;
- failure-fingerprint lookup;
- detector cooldown lookup;
- intervention status tracking;
- one modifiable feedback record per intervention;
- local quality aggregation;
- checkpoint identity and integrity metadata.

A vector database is not required for the deterministic alpha.

## 4. Detectors

A detector evaluates one newly accepted event against prior local evidence and returns zero or more candidate interventions.

Detectors should:

1. Have a narrow trigger.
2. Use explicit evidence thresholds.
3. Produce stable subject fingerprints for cooldowns.
4. Reference the event IDs that support the claim.
5. Suggest an action without executing it.
6. Remain independently testable.

The engine catches detector exceptions so one experimental detector does not stop event ingestion.

## 5. Interruption policy

The policy decides whether a valid candidate is allowed to reach the user. The current policy enforces a global hourly budget. Detector-specific cooldowns prevent repeated alerts for the same subject.

Candidate and policy-decision persistence are not yet separate. This remains a prerequisite for precise suppression metrics.

## 6. Presentation and feedback

An accepted intervention may be surfaced through:

- hook `systemMessage` output;
- an operating-system notification;
- the local web dashboard.

The dashboard records local structured feedback. Feedback is not transmitted remotely.

## 7. Confirmed context checkpoint

`create_context_checkpoint` is the first narrow action. It is intentionally not a generic process-execution framework.

The action:

- requires explicit API, dashboard, or CLI confirmation;
- reads only retained Watchtower records;
- writes only below the configured Watchtower checkpoint directory;
- creates deterministic Markdown;
- records evidence IDs and a SHA-256 digest;
- verifies path containment and integrity when read;
- never edits source files or creates Git commits.

Future actions require a capability model, preview, approval, timeout, and audit contract before entering the core.

## 8. Hook installation boundary

The installer operates outside the daemon. It performs a structured JSON merge, preserves unrelated configuration, produces a diff, creates a backup, and atomically replaces the destination.

Configuration files that are malformed or symlinked are rejected. Multi-target operations are preflighted before the first write.

## Event processing path

```text
POST /v1/hooks/{source}
        |
        v
bounded JSON reader
        |
        v
source adapter and privacy reduction
        |
        v
append canonical event to versioned SQLite
        |
        v
run deterministic detectors
        |
        v
apply detector cooldown and interruption budget
        |
        v
persist intervention and notify
        |
        v
record optional local feedback
        |
        v
execute only an explicitly confirmed narrow action
```

## Core invariants

- Local by default.
- No transcript or prompt reading.
- No screenshot or keystroke collection.
- No command storage without opt-in.
- Every intervention names its evidence events.
- Hook forwarding fails open when the daemon is unavailable.
- Vendor integrations remain replaceable adapters.
- Feedback remains local.
- Checkpoint writing requires explicit confirmation.
- No generic project command execution in the alpha.
