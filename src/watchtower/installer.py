from __future__ import annotations

import difflib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

InstallTarget = Literal["claude-code", "codex"]
InstallScope = Literal["user", "project"]


class HookConfigError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HookConfigResult:
    target: InstallTarget
    path: Path
    changed: bool
    dry_run: bool
    backup_path: Path | None
    diff: str


def _claude_entries(command: str) -> dict[str, list[dict]]:
    def hook(status_message: str | None = None) -> dict:
        value: dict[str, object] = {
            "type": "command",
            "command": command,
            "args": ["hook", "claude-code"],
            "timeout": 5,
        }
        if status_message:
            value["statusMessage"] = status_message
        return value

    return {
        "PostToolUse": [
            {
                "matcher": "Bash|Edit|Write",
                "hooks": [hook("Watchtower is observing the event")],
            }
        ],
        "PostToolUseFailure": [
            {
                "matcher": "Bash|Edit|Write",
                "hooks": [hook("Watchtower is checking the failure pattern")],
            }
        ],
        "Stop": [{"hooks": [hook()]}],
        "SubagentStop": [{"matcher": "*", "hooks": [hook()]}],
        "PreCompact": [{"matcher": "manual|auto", "hooks": [hook()]}],
    }


def _codex_entries(command: str) -> dict[str, list[dict]]:
    parts = [command, "hook", "codex"]
    shell_command = subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)

    def hook(status_message: str | None = None) -> dict:
        value: dict[str, object] = {
            "type": "command",
            "command": shell_command,
            "timeout": 5,
        }
        if status_message:
            value["statusMessage"] = status_message
        return value

    return {
        "PostToolUse": [
            {
                "matcher": "Bash|apply_patch",
                "hooks": [hook("Watchtower is observing the event")],
            }
        ],
        "Stop": [{"hooks": [hook()]}],
        "SubagentStop": [{"matcher": "*", "hooks": [hook()]}],
        "PreCompact": [{"matcher": "manual|auto", "hooks": [hook()]}],
    }


def managed_entries(target: InstallTarget, command: str = "watchtower") -> dict[str, list[dict]]:
    if target == "claude-code":
        return _claude_entries(command)
    if target == "codex":
        return _codex_entries(command)
    raise HookConfigError(f"Unsupported hook target: {target}")


def config_path(
    target: InstallTarget,
    scope: InstallScope,
    *,
    home: Path | None = None,
    project_dir: Path | None = None,
) -> Path:
    if scope == "user":
        base = (home or Path.home()).expanduser()
        return base / (".claude/settings.json" if target == "claude-code" else ".codex/hooks.json")
    base = (project_dir or Path.cwd()).expanduser()
    return base / (".claude/settings.json" if target == "claude-code" else ".codex/hooks.json")


def command_is_available(command: str) -> bool:
    path = Path(command).expanduser()
    if path.parent != Path(".") or os.sep in command:
        return path.is_file() and os.access(path, os.X_OK)
    return shutil.which(command) is not None


def inspect_installation(path: Path, target: InstallTarget, command: str = "watchtower") -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(document, dict):
        return False
    expected = managed_entries(target, command)
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        return False
    return all(
        all(entry in hooks.get(event_name, []) for entry in entries)
        for event_name, entries in expected.items()
    )


def install_hooks(
    path: Path,
    target: InstallTarget,
    *,
    command: str = "watchtower",
    dry_run: bool = False,
) -> HookConfigResult:
    original, document, newline, mode = _read_config(path)
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise HookConfigError(f"The `hooks` value in {path} must be a JSON object")

    for event_name, entries in managed_entries(target, command).items():
        current = hooks.setdefault(event_name, [])
        if not isinstance(current, list):
            raise HookConfigError(f"The hook list `{event_name}` in {path} must be a JSON array")
        for entry in entries:
            if entry not in current:
                current.append(entry)

    return _finish(path, target, original, document, newline, mode, dry_run=dry_run)


def uninstall_hooks(
    path: Path,
    target: InstallTarget,
    *,
    command: str = "watchtower",
    dry_run: bool = False,
) -> HookConfigResult:
    if not path.expanduser().exists():
        return HookConfigResult(
            target=target,
            path=path.expanduser(),
            changed=False,
            dry_run=dry_run,
            backup_path=None,
            diff="",
        )
    original, document, newline, mode = _read_config(path)
    hooks = document.get("hooks")
    if isinstance(hooks, dict):
        for event_name, entries in managed_entries(target, command).items():
            current = hooks.get(event_name)
            if not isinstance(current, list):
                continue
            hooks[event_name] = [entry for entry in current if entry not in entries]
            if not hooks[event_name]:
                hooks.pop(event_name, None)
        if not hooks:
            document.pop("hooks", None)
    return _finish(path, target, original, document, newline, mode, dry_run=dry_run)


def _read_config(path: Path) -> tuple[str, dict, str, int]:
    path = path.expanduser()
    if path.is_symlink():
        raise HookConfigError(f"Refusing to modify symlinked hook configuration: {path}")
    if not path.exists():
        return "", {}, "\n", 0o600
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise HookConfigError(f"Unable to read {path}: {error}") from error
    try:
        document = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError as error:
        raise HookConfigError(
            f"Invalid JSON in {path} at line {error.lineno}, column {error.colno}"
        ) from error
    if not isinstance(document, dict):
        raise HookConfigError(f"The root value in {path} must be a JSON object")
    newline = "\r\n" if "\r\n" in text else "\n"
    mode = path.stat().st_mode & 0o777
    return text, document, newline, mode


def _finish(
    path: Path,
    target: InstallTarget,
    original: str,
    document: dict,
    newline: str,
    mode: int,
    *,
    dry_run: bool,
) -> HookConfigResult:
    rendered = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if newline != "\n":
        rendered = rendered.replace("\n", newline)
    changed = rendered != original
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )
    backup: Path | None = None
    if changed and not dry_run:
        backup = _atomic_write_with_backup(path, rendered, mode)
    return HookConfigResult(
        target=target,
        path=path,
        changed=changed,
        dry_run=dry_run,
        backup_path=backup,
        diff=diff,
    )


def _atomic_write_with_backup(path: Path, content: str, mode: int) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup: Path | None = None
    if path.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        backup = path.with_name(f"{path.name}.watchtower-backup-{stamp}")
        try:
            shutil.copy2(path, backup)
        except OSError as error:
            raise HookConfigError(f"Unable to back up {path}: {error}") from error

    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except OSError as error:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        if backup and backup.exists() and not path.exists():
            shutil.copy2(backup, path)
        raise HookConfigError(f"Unable to update {path}: {error}") from error
    return backup
