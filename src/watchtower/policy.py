from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from watchtower.models import Intervention, utc_now
from watchtower.store import SQLiteStore


@dataclass(frozen=True, slots=True)
class InterruptionPolicy:
    max_interventions_per_hour: int = 4

    def allow(self, intervention: Intervention, store: SQLiteStore) -> bool:
        if self.max_interventions_per_hour <= 0:
            return False
        recent_count = store.count_interventions(since=utc_now() - timedelta(hours=1))
        return recent_count < self.max_interventions_per_hour
