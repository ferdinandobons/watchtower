from __future__ import annotations

from pathlib import Path

import pytest

from watchtower.engine import WatchtowerEngine
from watchtower.notifier import DesktopNotifier
from watchtower.policy import InterruptionPolicy
from watchtower.store import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "watchtower.db")


@pytest.fixture
def engine(store: SQLiteStore) -> WatchtowerEngine:
    return WatchtowerEngine(
        store,
        policy=InterruptionPolicy(max_interventions_per_hour=100),
        notifier=DesktopNotifier(enabled=False),
    )
