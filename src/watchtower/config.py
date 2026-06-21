from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path = Path("~/.watchtower/watchtower.db").expanduser()
    checkpoints_dir: Path = Path("~/.watchtower/checkpoints").expanduser()
    host: str = "127.0.0.1"
    port: int = 8765
    capture_commands: bool = False
    desktop_notifications: bool = True
    max_interventions_per_hour: int = 4
    max_hook_body_bytes: int = 1_048_576

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            db_path=Path(
                os.getenv("WATCHTOWER_DB_PATH", "~/.watchtower/watchtower.db")
            ).expanduser(),
            checkpoints_dir=Path(
                os.getenv("WATCHTOWER_CHECKPOINTS_DIR", "~/.watchtower/checkpoints")
            ).expanduser(),
            host=os.getenv("WATCHTOWER_HOST", "127.0.0.1"),
            port=_env_int("WATCHTOWER_PORT", 8765),
            capture_commands=_env_bool("WATCHTOWER_CAPTURE_COMMANDS", False),
            desktop_notifications=_env_bool("WATCHTOWER_DESKTOP_NOTIFICATIONS", True),
            max_interventions_per_hour=_env_int("WATCHTOWER_MAX_INTERVENTIONS_PER_HOUR", 4),
            max_hook_body_bytes=_env_int("WATCHTOWER_MAX_HOOK_BODY_BYTES", 1_048_576),
        )

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def with_overrides(self, **values: Any) -> Settings:
        clean = {key: value for key, value in values.items() if value is not None}
        return replace(self, **clean)
