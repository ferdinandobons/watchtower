from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from watchtower.detectors.base import event_scope_key
from watchtower.models import Intervention, WatchtowerEvent, utc_now
from watchtower.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class CompactionRiskDetector:
    name: str = "compaction_risk"
    lookback: timedelta = timedelta(hours=2)
    minimum_events: int = 8
    cooldown: timedelta = timedelta(minutes=20)

    def evaluate(self, event: WatchtowerEvent, store: SQLiteStore) -> list[Intervention]:
        if event.kind != "agent.context.compacting":
            return []

        history = store.list_events(
            limit=100,
            session_id=event.session_id,
            project_path=event.project_path,
            since=event.occurred_at - self.lookback,
            before=event.occurred_at,
        )
        failures = [item for item in history if item.kind.endswith(".failed")]
        changed = [item for item in history if item.kind == "workspace.file.changed"]
        if len(history) < self.minimum_events and not failures and len(changed) < 4:
            return []

        scope_key = event_scope_key(event)
        subject = event.id
        if store.list_interventions(
            limit=1,
            detector=self.name,
            scope_key=scope_key,
            since=utc_now() - self.cooldown,
        ):
            return []

        details = []
        if failures:
            details.append(f"{len(failures)} unresolved failure event(s)")
        if changed:
            details.append(f"{len(changed)} file-change event(s)")
        details.append(f"{len(history)} recent event(s)")
        summary = ", ".join(details)

        return [
            Intervention(
                detector=self.name,
                title="Context compaction may discard active evidence",
                message=(
                    f"The session is compacting with {summary}. Create a structured "
                    "checkpoint containing decisions, failed attempts, changed files "
                    "and next steps."
                ),
                severity="info",
                session_id=event.session_id,
                project_path=event.project_path,
                scope_key=scope_key,
                subject_fingerprint=subject,
                evidence_event_ids=[item.id for item in history[:20]] + [event.id],
                suggested_action="create_context_checkpoint",
            )
        ]
