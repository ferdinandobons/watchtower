from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from watchtower.models import Intervention, WatchtowerEvent, utc_now
from watchtower.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class AgentConflictDetector:
    name: str = "agent_conflict"
    window: timedelta = timedelta(minutes=10)
    cooldown: timedelta = timedelta(minutes=20)

    def evaluate(self, event: WatchtowerEvent, store: SQLiteStore) -> list[Intervention]:
        if event.kind != "workspace.file.changed" or not event.project_path:
            return []

        current_files = {str(item) for item in event.payload.get("changed_files", []) if item}
        if not current_files:
            return []

        recent_events = store.list_events(
            limit=200,
            kinds={"workspace.file.changed"},
            project_path=event.project_path,
            since=event.occurred_at - self.window,
        )
        conflicts: list[WatchtowerEvent] = []
        overlapping: set[str] = set()
        for candidate in recent_events:
            if candidate.id == event.id or candidate.session_id == event.session_id:
                continue
            candidate_files = {
                str(item) for item in candidate.payload.get("changed_files", []) if item
            }
            overlap = current_files & candidate_files
            if overlap:
                conflicts.append(candidate)
                overlapping.update(overlap)

        if not conflicts:
            return []

        session_ids = sorted({event.session_id, *(item.session_id for item in conflicts)})
        material = "|".join([event.project_path, *session_ids, *sorted(overlapping)])
        subject = f"conflict_{hashlib.sha256(material.encode()).hexdigest()[:20]}"
        scope_key = f"project:{event.project_path}"
        if store.list_interventions(
            limit=1,
            detector=self.name,
            scope_key=scope_key,
            subject_fingerprint=subject,
            since=utc_now() - self.cooldown,
        ):
            return []

        preview = ", ".join(f"`{path}`" for path in sorted(overlapping)[:5])
        return [
            Intervention(
                detector=self.name,
                title="Overlapping edits from multiple agent sessions",
                message=(
                    f"{len(session_ids)} sessions edited the same file set within "
                    f"{int(self.window.total_seconds() // 60)} minutes: {preview}. "
                    "Review the combined diff before either session continues."
                ),
                severity="critical" if len(overlapping) > 2 else "warning",
                session_id=event.session_id,
                project_path=event.project_path,
                scope_key=scope_key,
                subject_fingerprint=subject,
                evidence_event_ids=[item.id for item in conflicts[:10]] + [event.id],
                suggested_action="open_cross_agent_diff",
            )
        ]
