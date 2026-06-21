from __future__ import annotations

import logging
from collections.abc import Sequence
from threading import Lock

from watchtower.detectors import (
    AgentConflictDetector,
    CompactionRiskDetector,
    RepeatedFailureDetector,
    VerificationGapDetector,
)
from watchtower.detectors.base import Detector
from watchtower.models import ProcessingResult, WatchtowerEvent
from watchtower.notifier import DesktopNotifier
from watchtower.policy import InterruptionPolicy
from watchtower.store import SQLiteStore

logger = logging.getLogger(__name__)


class WatchtowerEngine:
    def __init__(
        self,
        store: SQLiteStore,
        *,
        detectors: Sequence[Detector] | None = None,
        policy: InterruptionPolicy | None = None,
        notifier: DesktopNotifier | None = None,
    ) -> None:
        self.store = store
        self.detectors = list(
            detectors
            or [
                RepeatedFailureDetector(),
                VerificationGapDetector(),
                CompactionRiskDetector(),
                AgentConflictDetector(),
            ]
        )
        self.policy = policy or InterruptionPolicy()
        self.notifier = notifier or DesktopNotifier(enabled=False)
        self._lock = Lock()

    def process(self, event: WatchtowerEvent) -> ProcessingResult:
        with self._lock:
            accepted = self.store.append_event(event)
            if not accepted:
                return ProcessingResult(accepted=False, event=event, interventions=[])

            emitted = []
            for detector in self.detectors:
                try:
                    candidates = detector.evaluate(event, self.store)
                except Exception:
                    logger.exception("Detector %s failed", getattr(detector, "name", detector))
                    continue
                for intervention in candidates:
                    if not self.policy.allow(intervention, self.store):
                        continue
                    self.store.append_intervention(intervention)
                    self.notifier.notify(intervention)
                    emitted.append(intervention)

            return ProcessingResult(accepted=True, event=event, interventions=emitted)
