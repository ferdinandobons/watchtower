from __future__ import annotations

import json
from pathlib import Path

import pytest

from watchtower.installer import (
    HookConfigError,
    inspect_installation,
    install_hooks,
    uninstall_hooks,
)


def test_install_is_idempotent_and_preserves_existing_hooks(tmp_path: Path) -> None:
    path = tmp_path / ".claude" / "settings.json"
    path.parent.mkdir()
    original_hook = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "existing-hook"}],
    }
    path.write_text(
        json.dumps({"theme": "dark", "hooks": {"PreToolUse": [original_hook]}}),
        encoding="utf-8",
    )

    first = install_hooks(path, "claude-code")
    assert first.changed is True
    assert first.backup_path is not None
    assert first.backup_path.is_file()
    assert inspect_installation(path, "claude-code") is True
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["theme"] == "dark"
    assert document["hooks"]["PreToolUse"] == [original_hook]

    second = install_hooks(path, "claude-code")
    assert second.changed is False
    assert second.backup_path is None


def test_install_uninstall_round_trip_leaves_unrelated_hooks(tmp_path: Path) -> None:
    path = tmp_path / ".codex" / "hooks.json"
    path.parent.mkdir()
    unrelated = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other"}]}]}}
    path.write_text(json.dumps(unrelated), encoding="utf-8")

    install_hooks(path, "codex")
    result = uninstall_hooks(path, "codex")
    assert result.changed is True
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == unrelated
    assert uninstall_hooks(path, "codex").changed is False


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    result = install_hooks(path, "claude-code", dry_run=True)
    assert result.changed is True
    assert result.diff
    assert not path.exists()


def test_uninstall_missing_file_is_a_noop(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    result = uninstall_hooks(path, "codex")
    assert result.changed is False
    assert not path.exists()


def test_invalid_json_is_never_modified(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(HookConfigError, match="Invalid JSON"):
        install_hooks(path, "claude-code")
    assert path.read_text(encoding="utf-8") == "{not-json"


def test_symlinked_config_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "settings.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlinks are unavailable on this platform")
    with pytest.raises(HookConfigError, match="symlinked"):
        install_hooks(link, "claude-code")
