from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from watchtower.detectors.base import event_scope_key
from watchtower.models import Intervention, WatchtowerEvent, utc_now
from watchtower.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class RepeatedFailureDetector:
    name: str = "repeated_failure"
    threshold: int = 3
    window: timedelta = timedelta(minutes=20)
    cooldown: timedelta = timedelta(minutes=45)

    def evaluate(self, event: WatchtowerEvent, store: SQLiteStore) -> list[Intervention]:
        if event.kind not in {"agent.tool.failed", "verification.failed"}:
            return []
        if not event.fingerprint:
            return []

        failures = store.list_events(
            limit=50,
            kinds={"agent.tool.failed", "verification.failed"},
            session_id=event.session_id,
            project_path=event.project_path,
            fingerprint=event.fingerprint,
            since=event.occurred_at - self.window,
        )
        if len(failures) < self.threshold:
            return []

        scope_key = event_scope_key(event)
        if store.list_interventions(
            limit=1,
            detector=self.name,
            scope_key=scope_key,
            subject_fingerprint=event.fingerprint,
            since=utc_now() - self.cooldown,
        ):
            return []

        verification = event.payload.get("verification_key")
        subject = f"the `{verification}` verification" if verification else "the same operation"
        return [
            Intervention(
                detector=self.name,
                title="Repeated failure loop detected",
                message=(
                    f"{subject.capitalize()} failed {len(failures)} times within "
                    f"{int(self.window.total_seconds() // 60)} minutes. "
                    "Pause the current strategy and review the shared failure signature."
                ),
                severity="warning",
                session_id=event.session_id,
                project_path=event.project_path,
                scope_key=scope_key,
                subject_fingerprint=event.fingerprint,
                evidence_event_ids=[item.id for item in failures[:10]],
                suggested_action="launch_read_only_reviewer",
            )
        ]
