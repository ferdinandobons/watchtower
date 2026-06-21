# Contributing

Watchtower is in early alpha. Small, evidence-backed changes are preferred over broad agent abstractions.

## Set up

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Change guidelines

- Add or update tests with every behavior change.
- Keep vendor payload handling inside adapters.
- Do not store new user content by default.
- Document every new persisted field, sensitivity class, migration, and retention expectation.
- Keep detectors deterministic unless a proposal explicitly motivates a model-based detector.
- Every intervention must reference its evidence event IDs.
- Do not add autonomous write or execution actions without a confirmation design and threat model.
- Installer changes must preserve unrelated configuration and include round-trip tests.
- Database changes must use a forward-only migration and include a legacy-upgrade test.
- Action changes must test confirmation, idempotency, path boundaries, and audit behavior.
- Prefer one focused pull request.

## Detector proposals

A detector proposal should include:

1. The event pattern.
2. The minimum evidence threshold.
3. Expected false positives.
4. The cooldown key.
5. The proposed user action.
6. A replay fixture and tests.
7. A way for users to dismiss or disable it.
8. The feedback categories expected to diagnose failure modes.

## Code style

```bash
ruff check .
ruff format --check .
pytest
```

Use Python 3.11 compatible syntax. Keep public functions typed. Avoid broad exception handling outside process boundaries, detector isolation, rollback boundaries, and desktop notification fallbacks.
