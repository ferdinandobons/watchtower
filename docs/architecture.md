# Architecture

Watchtower is split into six boundaries so that perception, interruption policy, and agent execution do not collapse into one opaque model call.

## 1. Event sources

The first adapters consume lifecycle events from Claude Code and Codex. Future sources may include Git, test runners, editor diagnostics, CI, and local activity tools.

Vendor payloads must not enter detector code directly.

## 2. Normalization and privacy reduction

`watchtower.adapters.hooks.normalize_hook_event` maps vendor payloads into `WatchtowerEvent`.

Before persistence, the adapter:

- keeps a bounded allowlist of scalar metadata;
- classifies common test, lint, and type-check commands;
- extracts changed file names without storing file contents;
- redacts common credential formats;
- stores full command text only when explicitly enabled;
- creates stable failure fingerprints after removing volatile values.

The transcript path supplied by agent hooks is ignored.

## 3. Local event store

SQLite is the initial event log and intervention log. It provides:

- idempotent event ingestion;
- time-window queries;
- session and project scopes;
- failure-fingerprint lookup;
- detector cooldown lookup;
- intervention status tracking.

SQLite keeps the first implementation inspectable and easy to replay. A vector database is not required for the deterministic MVP.

## 4. Detectors

A detector evaluates one newly accepted event against prior local evidence. It returns zero or more candidate interventions.

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

Future policies may include:

- focus and meeting state;
- quiet hours;
- per-project thresholds;
- learned user preferences;
- severity-sensitive channels;
- a cost model for interruption.

This layer is deliberately separate from the detectors. A condition can be true while the correct action is still to remain silent.

## 6. Presentation and future actions

An accepted intervention is stored and may be surfaced through:

- hook `systemMessage` output;
- an operating-system notification;
- the local web dashboard.

The current implementation does not start agents or change files. Future action adapters should require explicit confirmation, use narrow permissions, and append their result to the event log.

## Processing path

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
append canonical event to SQLite
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
return evidence-backed result to hook
```

## Core invariants

- Local by default.
- No transcript reading.
- No screenshot or keystroke collection.
- No command storage without opt-in.
- No autonomous remediation in the initial release.
- Every intervention names its evidence events.
- Hook forwarding fails open when the daemon is unavailable.
- Vendor integrations remain replaceable adapters.
