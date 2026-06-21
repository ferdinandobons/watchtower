from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)(\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
]


def redact_text(value: str, *, limit: int = 2000) -> str:
    text = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 1:
            text = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
        elif pattern.groups == 2:
            text = pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated {len(text) - limit} chars]"


def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.strip().split()


def classify_verification_command(command: str | None) -> str | None:
    """Classify common test, lint and type-check commands without storing arguments."""
    if not command:
        return None
    tokens = [token.lower() for token in _command_tokens(command)]
    if not tokens:
        return None

    joined = " ".join(tokens)
    patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("pytest", ("pytest", "python -m pytest", "python3 -m pytest")),
        ("tox", ("tox",)),
        ("nox", ("nox",)),
        ("npm-test", ("npm test", "npm run test")),
        ("pnpm-test", ("pnpm test", "pnpm run test")),
        ("yarn-test", ("yarn test", "yarn run test")),
        ("bun-test", ("bun test",)),
        ("cargo-test", ("cargo test",)),
        ("go-test", ("go test",)),
        ("dotnet-test", ("dotnet test",)),
        ("maven-test", ("mvn test", "mvnw test", "./mvnw test")),
        ("gradle-test", ("gradle test", "gradlew test", "./gradlew test")),
        ("make-test", ("make test",)),
        ("ruff", ("ruff check",)),
        ("mypy", ("mypy", "python -m mypy", "python3 -m mypy")),
        ("eslint", ("eslint", "npx eslint", "pnpm eslint", "yarn eslint")),
        ("typescript", ("tsc", "npx tsc", "pnpm tsc", "yarn tsc")),
    )
    for key, prefixes in patterns:
        if any(joined == prefix or joined.startswith(f"{prefix} ") for prefix in prefixes):
            return key
    return None


def _response_failure(response: Any) -> bool | None:
    if isinstance(response, dict):
        for key in ("success", "ok"):
            value = response.get(key)
            if isinstance(value, bool):
                return not value
        for key in ("exit_code", "exitCode", "returncode", "return_code"):
            value = response.get(key)
            if isinstance(value, int):
                return value != 0
        status = response.get("status")
        if isinstance(status, str):
            lowered = status.lower()
            if lowered in {"failed", "failure", "error", "declined", "cancelled", "canceled"}:
                return True
            if lowered in {"completed", "success", "succeeded", "ok"}:
                return False
        for key in ("error", "errors"):
            if response.get(key):
                return True
        for value in response.values():
            nested = _response_failure(value)
            if nested is not None:
                return nested
    if isinstance(response, list):
        for value in response:
            nested = _response_failure(value)
            if nested is not None:
                return nested
    if isinstance(response, str):
        match = re.search(
            r"(?i)\b(?:exit(?:ed)?|return(?:ed)?)\s+(?:with\s+)?"
            r"(?:code|status)\s*[:=]?\s*(-?\d+)\b",
            response,
        )
        if match:
            return int(match.group(1)) != 0
    return None


def infer_tool_failure(raw: dict[str, Any]) -> bool:
    event_name = str(raw.get("hook_event_name", ""))
    if event_name in {"PostToolUseFailure", "StopFailure", "PermissionDenied"}:
        return True
    if raw.get("error"):
        return True
    inferred = _response_failure(raw.get("tool_response"))
    return bool(inferred)


def extract_error(raw: dict[str, Any]) -> str:
    error = raw.get("error")
    if error:
        return redact_text(str(error))

    response = raw.get("tool_response")
    if isinstance(response, dict):
        for key in ("error", "stderr", "aggregatedOutput", "output", "message"):
            if response.get(key):
                return redact_text(str(response[key]))
    if response:
        return redact_text(str(response))
    return "Tool execution failed"


def _normalize_file_path(value: str, cwd: str | None) -> str | None:
    value = value.strip()
    if not value or value in {"/dev/null", "a/dev/null", "b/dev/null"}:
        return None
    value = value.removeprefix("a/").removeprefix("b/")
    path = Path(value)
    if path.is_absolute() and cwd:
        try:
            path = path.relative_to(Path(cwd))
        except ValueError:
            return path.name
    return path.as_posix()


def extract_changed_files(raw: dict[str, Any]) -> list[str]:
    """Extract file names without persisting full commands or file contents."""
    values: list[str] = []
    cwd_value = raw.get("cwd")
    cwd = str(cwd_value) if cwd_value else None

    for key in ("file_path", "path", "file"):
        value = raw.get(key)
        if isinstance(value, str):
            values.append(value)

    tool_input = raw.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "file"):
            value = tool_input.get(key)
            if isinstance(value, str):
                values.append(value)
        command = tool_input.get("command")
        if isinstance(command, str):
            for line in command.splitlines():
                stripped = line.strip()
                if stripped.startswith(("+++ ", "--- ")):
                    values.append(stripped[4:].split("\t", 1)[0])
                elif stripped.startswith("*** Update File: "):
                    values.append(stripped.removeprefix("*** Update File: "))
                elif stripped.startswith("*** Add File: "):
                    values.append(stripped.removeprefix("*** Add File: "))
                elif stripped.startswith("*** Delete File: "):
                    values.append(stripped.removeprefix("*** Delete File: "))

    response = raw.get("tool_response")
    if isinstance(response, dict):
        for key in ("filePath", "file_path", "path"):
            value = response.get(key)
            if isinstance(value, str):
                values.append(value)

    normalized: list[str] = []
    for value in values:
        candidate = _normalize_file_path(value, cwd)
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized[:100]


def sanitized_hook_payload(
    raw: dict[str, Any], *, capture_commands: bool = False
) -> dict[str, Any]:
    """Reduce hook payloads to bounded metadata and redact likely secrets."""
    allowed_scalar_fields = (
        "hook_event_name",
        "tool_name",
        "tool_use_id",
        "turn_id",
        "model",
        "permission_mode",
        "source",
        "trigger",
        "agent_id",
        "agent_type",
        "is_interrupt",
        "duration_ms",
        "notification_type",
        "stop_hook_active",
        "change_type",
    )
    payload: dict[str, Any] = {
        key: raw[key]
        for key in allowed_scalar_fields
        if key in raw and isinstance(raw[key], (str, int, float, bool, type(None)))
    }

    tool_input = raw.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    verification_key = classify_verification_command(str(command) if command is not None else None)
    if verification_key:
        payload["verification_key"] = verification_key
    if capture_commands and command is not None:
        payload["command"] = redact_text(str(command), limit=4000)

    changed_files = extract_changed_files(raw)
    if changed_files:
        payload["changed_files"] = changed_files

    if raw.get("error"):
        payload["error"] = redact_text(str(raw["error"]))
    return payload
