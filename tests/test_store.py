from __future__ import annotations

from watchtower.models import Intervention, WatchtowerEvent
from watchtower.store import SQLiteStore


def test_duplicate_event_is_idempotent(store: SQLiteStore) -> None:
    event = WatchtowerEvent(source="test", kind="example", session_id="s1")
    assert store.append_event(event) is True
    assert store.append_event(event) is False
    assert len(store.list_events()) == 1


def test_intervention_status_round_trip(store: SQLiteStore) -> None:
    intervention = Intervention(
        detector="test",
        title="Test",
        message="Message",
        session_id="s1",
        scope_key="test:s1",
        subject_fingerprint="subject",
    )
    store.append_intervention(intervention)
    assert store.update_intervention_status(intervention.id, "acknowledged") is True
    stored = store.get_intervention(intervention.id)
    assert stored is not None
    assert stored.status == "acknowledged"
