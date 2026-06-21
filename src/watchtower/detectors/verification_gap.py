from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from watchtower.detectors.base import event_scope_key
from watchtower.models import Intervention, WatchtowerEvent, utc_now
from watchtower.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class VerificationGapDetector:
    name: str = "verification_gap"
    lookback: timedelta = timedelta(hours=3)
    cooldown: timedelta = timedelta(minutes=30)

    def evaluate(self, event: WatchtowerEvent, store: SQLiteStore) -> list[Intervention]:
        if event.kind not in {"agent.turn.stopped", "agent.subagent.stopped"}:
            return []

        latest = store.list_events(
            limit=1,
            kinds={"verification.failed", "verification.succeeded"},
            session_id=event.session_id,
            project_path=event.project_path,
            since=event.occurred_at - self.lookback,
            before=event.occurred_at,
        )
        if not latest or latest[0].kind != "verification.failed":
            return []

        failed = latest[0]
        scope_key = event_scope_key(event)
        subject = failed.id
        if store.list_interventions(
            limit=1,
            detector=self.name,
            scope_key=scope_key,
            subject_fingerprint=subject,
            since=utc_now() - self.cooldown,
        ):
            return []

        verification = str(failed.payload.get("verification_key") or "validation")
        return [
            Intervention(
                detector=self.name,
                title="Agent stopped after a failed verification",
                message=(
                    f"The latest `{verification}` check failed and no later successful "
                    "verification was observed before the agent stopped."
                ),
                severity="warning",
                session_id=event.session_id,
                project_path=event.project_path,
                scope_key=scope_key,
                subject_fingerprint=subject,
                evidence_event_ids=[failed.id, event.id],
                suggested_action="reopen_with_failure_context",
            )
        ]
