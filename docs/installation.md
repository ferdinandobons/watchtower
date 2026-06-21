# Hook installation

Watchtower installs command hooks by parsing and structurally merging the existing JSON configuration. It does not replace the complete file.

## Paths

| Target | User scope | Project scope |
| --- | --- | --- |
| Claude Code | `~/.claude/settings.json` | `<project>/.claude/settings.json` |
| Codex | `~/.codex/hooks.json` | `<project>/.codex/hooks.json` |

## Preview and install

```bash
watchtower install all --scope user --dry-run
watchtower install all --scope user
```

For a project other than the current working directory:

```bash
watchtower install all \
  --scope project \
  --project-dir /path/to/repository \
  --dry-run
```

A successful changed write produces a timestamped sibling backup:

```text
settings.json.watchtower-backup-20260621T120000.123456Z
```

## Idempotency

An installation entry is considered present only when its structured hook object is equal to the object managed by the running Watchtower version. Running the same install command twice does not append duplicates.

Watchtower installs separate entries instead of editing an unrelated hook entry. Existing event lists, matchers, commands, and top-level keys remain in place.

## Uninstall

```bash
watchtower uninstall all --scope user --dry-run
watchtower uninstall all --scope user
```

Uninstall removes only entries equal to Watchtower-managed definitions for the selected target and command. Other entries under the same event remain unchanged. Empty event lists and an empty top-level `hooks` object are removed.

## Safety behavior

The installer:

1. Reads the entire target as UTF-8 JSON.
2. Rejects a non-object root.
3. Rejects malformed hook containers.
4. Refuses to follow a symlinked configuration file.
5. Preflights all requested targets before writing.
6. Creates a backup when a file already exists.
7. Writes a temporary file in the same directory.
8. Flushes it to disk and atomically replaces the destination.
9. Preserves the existing file mode and newline convention when available.
10. Attempts to restore earlier targets if a later target in an `all` operation fails.

Invalid JSON is never rewritten automatically.

## Custom executable path

The default managed command is `watchtower`. An explicit executable can be used:

```bash
watchtower install claude-code --command /opt/watchtower/bin/watchtower
```

Use the same `--command` value during uninstall because it is part of the managed hook identity.

## Codex trust review

A Codex client may require explicit review of project-level command hooks before executing them. Installation writes the configuration but does not bypass the client's trust or approval controls.

## Inspection

```bash
watchtower doctor
```

The doctor output reports whether the `watchtower` command is resolvable, whether each user and project hook set is installed, daemon health, database schema version, and checkpoint directory.
