# Context checkpoints

A context checkpoint is Watchtower's first narrow, confirmed action. It converts retained lifecycle events into a local Markdown handoff before or after an agent context boundary.

It is not an autonomous repair action. It does not invoke a model, execute a project command, read a transcript, write into the source repository, or create a Git commit.

## Confirmation boundary

The HTTP API rejects checkpoint creation unless the request contains:

```json
{
  "confirmed": true
}
```

The dashboard asks for browser confirmation. The CLI requires `--yes`:

```bash
watchtower checkpoint \
  --session-id SESSION_ID \
  --intervention-id INTERVENTION_ID \
  --yes
```

## Inputs

The writer may use only data already retained in the local Watchtower database:

- canonical event kind and timestamps;
- session, source, and project metadata;
- reduced changed-file names;
- reduced verification keys and bounded error excerpts;
- intervention title, detector, message, and suggested action;
- evidence event identifiers.

## Output sections

```text
# Watchtower checkpoint
## Observed objective
## Session and agent
## Linked intervention
## Changed files
## Successful verifications
## Failed verifications
## Open errors
## Explicit decisions available
## Observed attempts
## Next step to confirm
## Evidence events
## Data not acquired
```

The objective and explicit decision sections state that the information is unavailable because prompts and transcripts are not captured.

## Storage and integrity

The default root is:

```text
~/.watchtower/checkpoints
```

Each session receives a sanitized subdirectory. The checkpoint identifier is derived from session scope, optional intervention identity, and the ordered evidence event IDs. Repeating a request for the same intervention returns the existing checkpoint.

The writer:

- creates parent directories with restrictive permissions where supported;
- writes through a temporary file in the same directory;
- flushes before atomic replacement;
- sets the checkpoint file mode to `0600` where supported;
- stores a SHA-256 digest in SQLite;
- verifies path containment and the digest when content is read through the API.

## API

```text
POST /v1/checkpoints
GET  /v1/checkpoints
GET  /v1/checkpoints/{id}/content
```

Example request:

```json
{
  "session_id": "session-123",
  "project_path": "/workspace/project",
  "intervention_id": "int_123",
  "confirmed": true
}
```

## Known limits

The current deterministic checkpoint cannot recover intent, decisions, or rejected approaches that exist only inside an agent transcript. Future integrations may accept explicitly authorized task metadata, but transcript capture is not implied by this feature.
