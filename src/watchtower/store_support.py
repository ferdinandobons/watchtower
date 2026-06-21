from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime

ConnectionFactory = Callable[[], AbstractContextManager[sqlite3.Connection]]


def iso(value: datetime) -> str:
    return value.isoformat()
