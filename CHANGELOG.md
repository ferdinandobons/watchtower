# Changelog

## 0.2.0

Reliable local integration and first confirmed action:

- structured, idempotent Claude Code and Codex hook installer;
- symmetric uninstaller that preserves unrelated hooks;
- dry-run diffs, timestamped backups, atomic writes, symlink refusal, and multi-target rollback;
- expanded `watchtower doctor` installation and schema diagnostics;
- forward-only SQLite migrations with explicit schema versioning;
- persistence internals split into focused event, intervention, feedback, and checkpoint modules;
- local, modifiable feedback linked to interventions;
- per-detector and aggregate quality metrics;
- deterministic context checkpoints created only after explicit confirmation;
- local checkpoint integrity verification and path-containment checks;
- dashboard feedback controls, checkpoint action, evidence IDs, and quality metrics;
- checkpoint CLI and API endpoints;
- compatibility, installation, feedback, and checkpoint documentation;
- expanded suite from 23 to 37 tests.

## 0.1.0

Initial working vertical slice:

- local FastAPI daemon and dashboard;
- canonical event and intervention models;
- Claude Code and Codex hook adapters;
- privacy reduction and secret redaction;
- SQLite event store;
- repeated failure, verification gap, compaction risk, and agent conflict detectors;
- detector cooldowns and global interruption budget;
- fail-open hook command;
- demo and doctor commands;
- test suite and CI configuration.
