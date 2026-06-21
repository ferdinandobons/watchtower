from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from watchtower.models import ContextCheckpoint, Intervention, WatchtowerEvent
from watchtower.store import SQLiteStore

_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


class CheckpointError(RuntimeError):
    pass


class CheckpointNotFound(CheckpointError):
    pass


def _safe_component(value: str) -> str:
    cleaned = _SAFE_COMPONENT.sub("-", value).strip("-.")
    return cleaned[:80] or "unknown-session"


def _inline(value: object) -> str:
    text = str(value).replace("`", "'").replace("\n", " ").strip()
    return text[:1000]


def _markdown_text(value: object) -> str:
    text = html.escape(_inline(value), quote=False)
    for character in ("\\", "*", "_", "[", "]", "(", ")", "#", "!", "|"):
        text = text.replace(character, f"\\{character}")
    return text


def _bullets(values: list[str], empty: str) -> list[str]:
    return [f"- {value}" for value in values] if values else [f"- {empty}"]


class ContextCheckpointWriter:
    """Create deterministic, local-only context checkpoints from retained events."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser()

    def create(
        self,
        store: SQLiteStore,
        *,
        session_id: str,
        project_path: str | None = None,
        intervention_id: str | None = None,
        event_limit: int = 300,
    ) -> ContextCheckpoint:
        intervention: Intervention | None = None
        if intervention_id:
            intervention = store.get_intervention(intervention_id)
            if intervention is None:
                raise CheckpointNotFound(f"Intervention {intervention_id} was not found")
            if intervention.session_id != session_id:
                raise CheckpointError("Intervention and checkpoint session do not match")
            if (
                project_path is not None
                and intervention.project_path is not None
                and project_path != intervention.project_path
            ):
                raise CheckpointError("Intervention and checkpoint project do not match")
            if project_path is None:
                project_path = intervention.project_path
            existing = store.get_checkpoint_for_intervention(intervention_id)
            if existing and Path(existing.path).is_file():
                self.read(existing)
                return existing

        events = store.list_events(
            limit=max(1, min(event_limit, 1000)),
            session_id=session_id,
            project_path=project_path,
        )
        if not events:
            raise CheckpointNotFound("No retained events were found for this session")
        events = sorted(events, key=lambda item: (item.occurred_at, item.id))
        evidence_event_ids = [event.id for event in events]
        identity = json.dumps(
            {
                "session_id": session_id,
                "project_path": project_path,
                "intervention_id": intervention_id,
                "evidence_event_ids": evidence_event_ids,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        checkpoint_id = f"ckpt_{hashlib.sha256(identity.encode()).hexdigest()[:24]}"
        existing = store.get_checkpoint(checkpoint_id)
        created_at = existing.created_at if existing else datetime.now(UTC)
        content = self._render(
            checkpoint_id=checkpoint_id,
            created_at=created_at,
            session_id=session_id,
            project_path=project_path,
            events=events,
            intervention=intervention,
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        session_dir = self.root / _safe_component(session_id)
        path = session_dir / f"{checkpoint_id}.md"
        self._atomic_write(path, content)
        checkpoint = ContextCheckpoint(
            id=checkpoint_id,
            created_at=created_at,
            session_id=session_id,
            project_path=project_path,
            intervention_id=intervention_id,
            path=str(path),
            sha256=digest,
            evidence_event_ids=evidence_event_ids,
        )
        store.append_checkpoint(checkpoint)
        return store.get_checkpoint(checkpoint.id) or checkpoint

    def read(self, checkpoint: ContextCheckpoint) -> str:
        path = Path(checkpoint.path)
        try:
            resolved = path.resolve(strict=True)
            root = self.root.resolve(strict=False)
            resolved.relative_to(root)
        except (FileNotFoundError, ValueError) as error:
            raise CheckpointNotFound(
                "Checkpoint file is missing or outside the data directory"
            ) from error
        content = resolved.read_text(encoding="utf-8")
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != checkpoint.sha256:
            raise CheckpointError("Checkpoint integrity verification failed")
        return content

    @staticmethod
    def _render(
        *,
        checkpoint_id: str,
        created_at: datetime,
        session_id: str,
        project_path: str | None,
        events: list[WatchtowerEvent],
        intervention: Intervention | None,
    ) -> str:
        sources = sorted({event.source for event in events})
        changed_files: list[str] = []
        for event in events:
            for value in event.payload.get("changed_files", []):
                item = _inline(value)
                if item and item not in changed_files:
                    changed_files.append(item)

        successful: list[str] = []
        failed: list[str] = []
        latest_verification: dict[str, WatchtowerEvent] = {}
        for event in events:
            if event.kind not in {"verification.succeeded", "verification.failed"}:
                continue
            key = _inline(event.payload.get("verification_key") or "validation")
            latest_verification[key] = event
            stamp = event.occurred_at.isoformat()
            if event.kind == "verification.succeeded":
                successful.append(f"`{key}` at {stamp}")
            else:
                error = _markdown_text(event.payload.get("error") or "failure details unavailable")
                failed.append(f"`{key}` at {stamp}: {error}")

        open_errors: list[str] = []
        for key, event in sorted(latest_verification.items()):
            if event.kind == "verification.failed":
                error = _markdown_text(event.payload.get("error") or "failure details unavailable")
                open_errors.append(f"`{key}`: {error}")

        kind_counts = Counter(event.kind for event in events)
        attempts = [f"`{kind}`: {count}" for kind, count in sorted(kind_counts.items())]
        evidence = [
            f"`{event.id}` · `{event.kind}` · {event.occurred_at.isoformat()}" for event in events
        ]

        if intervention:
            next_step = (
                f"Review the Watchtower intervention `{intervention.detector}` and confirm "
                f"whether to proceed with `{intervention.suggested_action or 'manual_review'}`."
            )
            intervention_lines = [
                f"- Detector: `{_inline(intervention.detector)}`",
                f"- Message: {_markdown_text(intervention.message)}",
                f"- Suggested action: `{_inline(intervention.suggested_action or 'none')}`",
            ]
        else:
            next_step = "Confirm the next action in the coding agent after reviewing open failures."
            intervention_lines = ["- No intervention was explicitly linked to this checkpoint."]

        lines = [
            "# Watchtower checkpoint",
            "",
            f"- Checkpoint: `{checkpoint_id}`",
            f"- Generated: {created_at.isoformat()}",
            "- Source: local Watchtower event store",
            "",
            "## Observed objective",
            "",
            (
                "The objective is unavailable because Watchtower does not retain "
                "user prompts or transcripts."
            ),
            "",
            "## Session and agent",
            "",
            f"- Session: `{_inline(session_id)}`",
            f"- Sources: {', '.join(f'`{_inline(source)}`' for source in sources)}",
            f"- Project: `{_inline(project_path or 'not available')}`",
            "",
            "## Linked intervention",
            "",
            *intervention_lines,
            "",
            "## Changed files",
            "",
            *_bullets(
                [f"`{value}`" for value in changed_files],
                "No changed-file metadata retained.",
            ),
            "",
            "## Successful verifications",
            "",
            *_bullets(successful, "No successful verification retained."),
            "",
            "## Failed verifications",
            "",
            *_bullets(failed, "No failed verification retained."),
            "",
            "## Open errors",
            "",
            *_bullets(open_errors, "No verification is currently known to be failing."),
            "",
            "## Explicit decisions available",
            "",
            "- None. Conversation transcripts and prompts are intentionally not captured.",
            "",
            "## Observed attempts",
            "",
            *_bullets(attempts, "No attempts retained."),
            "",
            "## Next step to confirm",
            "",
            f"- {next_step}",
            "",
            "## Evidence events",
            "",
            *_bullets(evidence, "No evidence events available."),
            "",
            "## Data not acquired",
            "",
            "- User prompts and conversation transcripts",
            "- Screenshots and keystrokes",
            "- Full file contents",
            "- Full shell commands unless command capture was explicitly enabled",
            "",
        ]
        return "\n".join(lines)

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with suppress(OSError):
            path.parent.chmod(0o700)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as handle:
                temporary = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        except OSError as error:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
            raise CheckpointError(f"Unable to write checkpoint: {error}") from error
