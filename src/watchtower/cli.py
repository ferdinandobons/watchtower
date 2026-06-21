from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from watchtower.config import Settings
from watchtower.installer import (
    HookConfigError,
    HookConfigResult,
    InstallTarget,
    command_is_available,
    config_path,
    inspect_installation,
    install_hooks,
    uninstall_hooks,
)


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 5,
) -> Any:
    data = None
    headers = {"accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"null")


def _hook_message(result: dict[str, Any]) -> dict[str, str]:
    interventions = result.get("interventions")
    if not isinstance(interventions, list) or not interventions:
        return {}
    lines = ["Watchtower detected a high-signal condition:"]
    for item in interventions[:2]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "info")).upper()
        title = str(item.get("title", "Intervention"))
        message = str(item.get("message", ""))
        action = item.get("suggested_action")
        line = f"[{severity}] {title}. {message}"
        if action:
            line += f" Suggested action: {action}."
        lines.append(line)
    return {"systemMessage": "\n".join(lines)}


def _command_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from watchtower.api import create_app

    settings = Settings.from_env().with_overrides(
        host=args.host,
        port=args.port,
        db_path=args.db,
        checkpoints_dir=args.checkpoints_dir,
        capture_commands=args.capture_commands if args.capture_commands else None,
        desktop_notifications=False if args.no_notifications else None,
    )
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=args.log_level,
    )
    return 0


def _command_hook(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    raw_bytes = sys.stdin.buffer.read(settings.max_hook_body_bytes + 1)
    if len(raw_bytes) > settings.max_hook_body_bytes:
        print("{}")
        print("Watchtower ignored an oversized hook payload", file=sys.stderr)
        return 0
    try:
        payload = json.loads(raw_bytes or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("expected object")
    except (json.JSONDecodeError, ValueError) as error:
        print("{}")
        print(f"Watchtower ignored invalid hook JSON: {error}", file=sys.stderr)
        return 0

    try:
        result = _request_json(
            "POST",
            f"{args.url.rstrip('/')}/v1/hooks/{args.source}",
            payload,
            timeout=args.timeout,
        )
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print("{}")
        print(f"Watchtower daemon unavailable: {error}", file=sys.stderr)
        return 0

    output = _hook_message(result if isinstance(result, dict) else {})
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


def _installation_state(args: argparse.Namespace) -> dict[str, Any]:
    targets: tuple[InstallTarget, ...] = ("claude-code", "codex")
    result: dict[str, Any] = {"command_available": command_is_available(args.command)}
    for scope in ("user", "project"):
        for target in targets:
            path = config_path(
                target,
                scope,
                home=args.home,
                project_dir=args.project_dir,
            )
            result[f"{target}:{scope}"] = {
                "path": str(path),
                "installed": inspect_installation(path, target, args.command),
            }
    return result


def _command_doctor(args: argparse.Namespace) -> int:
    output: dict[str, Any] = {"installations": _installation_state(args)}
    exit_code = 0
    try:
        output["daemon"] = _request_json(
            "GET", f"{args.url.rstrip('/')}/health", timeout=args.timeout
        )
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        output["daemon"] = {"status": "unavailable", "error": str(error)}
        exit_code = 1
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return exit_code


def _command_demo(args: argparse.Namespace) -> int:
    session_id = f"watchtower-demo-{uuid4().hex[:8]}"
    cwd = Path.cwd().as_posix()
    errors = [
        "FAILED tests/test_checkout.py:42 expected status 200 but got 500",
        "FAILED tests/test_checkout.py:51 expected status 200 but got 500",
        "FAILED tests/test_checkout.py:63 expected status 200 but got 500",
    ]
    generated: list[dict[str, Any]] = []
    for error in errors:
        payload = {
            "session_id": session_id,
            "cwd": cwd,
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/test_checkout.py"},
            "error": error,
        }
        try:
            result = _request_json(
                "POST",
                f"{args.url.rstrip('/')}/v1/hooks/claude-code",
                payload,
                timeout=args.timeout,
            )
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error_obj:
            print(f"Watchtower demo failed: {error_obj}", file=sys.stderr)
            return 1
        if isinstance(result, dict):
            generated.extend(result.get("interventions", []))

    stop_payload = {
        "session_id": session_id,
        "cwd": cwd,
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    }
    result = _request_json(
        "POST",
        f"{args.url.rstrip('/')}/v1/hooks/claude-code",
        stop_payload,
        timeout=args.timeout,
    )
    if isinstance(result, dict):
        generated.extend(result.get("interventions", []))

    print(f"Demo session: {session_id}")
    print(f"Interventions generated: {len(generated)}")
    for intervention in generated:
        print(f"- {intervention.get('title')}: {intervention.get('message')}")
    print(f"Dashboard: {args.url.rstrip('/')}/")
    return 0


def _targets(value: str) -> tuple[InstallTarget, ...]:
    if value == "all":
        return ("claude-code", "codex")
    if value == "claude-code":
        return ("claude-code",)
    if value == "codex":
        return ("codex",)
    raise ValueError(f"Unsupported installation target: {value}")


def _print_config_result(result: HookConfigResult, action: str) -> None:
    state = "would change" if result.dry_run and result.changed else "changed"
    if not result.changed:
        state = "already configured" if action == "install" else "already absent"
    print(f"{result.target}: {state} {result.path}")
    if result.diff:
        print(result.diff, end="" if result.diff.endswith("\n") else "\n")
    if result.backup_path:
        print(f"Backup: {result.backup_path}")


def _command_configure(args: argparse.Namespace, *, uninstall: bool) -> int:
    if not uninstall and not command_is_available(args.command):
        print(
            f"The hook command `{args.command}` is not executable or is not available in PATH.",
            file=sys.stderr,
        )
        return 2

    operation = uninstall_hooks if uninstall else install_hooks
    target_names = _targets(args.target)
    paths = [
        (
            target,
            config_path(
                target,
                args.scope,
                home=args.home,
                project_dir=args.project_dir,
            ),
        )
        for target in target_names
    ]
    try:
        previews = [
            operation(path, target, command=args.command, dry_run=True) for target, path in paths
        ]
        if args.dry_run:
            for result in previews:
                _print_config_result(result, "uninstall" if uninstall else "install")
            return 0
        results: list[HookConfigResult] = []
        try:
            for target, path in paths:
                results.append(operation(path, target, command=args.command, dry_run=False))
        except HookConfigError:
            for completed in reversed(results):
                if not completed.changed:
                    continue
                try:
                    if completed.backup_path and completed.backup_path.exists():
                        shutil.copy2(completed.backup_path, completed.path)
                    else:
                        completed.path.unlink(missing_ok=True)
                except OSError as rollback_error:
                    print(
                        f"Rollback failed for {completed.path}: {rollback_error}",
                        file=sys.stderr,
                    )
            raise
    except HookConfigError as error:
        print(f"Watchtower hook configuration failed: {error}", file=sys.stderr)
        return 2

    for result in results:
        _print_config_result(result, "uninstall" if uninstall else "install")
    if not uninstall and "codex" in target_names:
        print("Codex may require a trust review before project hooks are executed.")
    return 0


def _command_install(args: argparse.Namespace) -> int:
    return _command_configure(args, uninstall=False)


def _command_uninstall(args: argparse.Namespace) -> int:
    return _command_configure(args, uninstall=True)


def _command_checkpoint(args: argparse.Namespace) -> int:
    if not args.yes:
        print(
            "Checkpoint creation writes a Markdown file in the Watchtower data directory. "
            "Re-run with --yes to confirm.",
            file=sys.stderr,
        )
        return 2
    payload = {
        "session_id": args.session_id,
        "project_path": args.project_path,
        "intervention_id": args.intervention_id,
        "confirmed": True,
    }
    try:
        result = _request_json(
            "POST",
            f"{args.url.rstrip('/')}/v1/checkpoints",
            payload,
            timeout=args.timeout,
        )
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Checkpoint creation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _add_installation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", choices=["claude-code", "codex", "all"])
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--command", default="watchtower")


def build_parser() -> argparse.ArgumentParser:
    defaults = Settings.from_env()
    parser = argparse.ArgumentParser(
        prog="watchtower",
        description="Local proactivity control plane for coding agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Start the local daemon and dashboard")
    serve.add_argument("--host", default=defaults.host)
    serve.add_argument("--port", type=int, default=defaults.port)
    serve.add_argument("--db", type=Path, default=defaults.db_path)
    serve.add_argument("--checkpoints-dir", type=Path, default=defaults.checkpoints_dir)
    serve.add_argument("--capture-commands", action="store_true")
    serve.add_argument("--no-notifications", action="store_true")
    serve.add_argument(
        "--log-level",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        default="info",
    )
    serve.set_defaults(handler=_command_serve)

    hook = subparsers.add_parser("hook", help="Forward one hook payload from stdin")
    hook.add_argument("source", choices=["claude-code", "codex"])
    hook.add_argument("--url", default=os.getenv("WATCHTOWER_URL", defaults.base_url))
    hook.add_argument("--timeout", type=float, default=4)
    hook.set_defaults(handler=_command_hook)

    demo = subparsers.add_parser("demo", help="Generate a repeated failure scenario")
    demo.add_argument("--url", default=os.getenv("WATCHTOWER_URL", defaults.base_url))
    demo.add_argument("--timeout", type=float, default=5)
    demo.set_defaults(handler=_command_demo)

    doctor = subparsers.add_parser("doctor", help="Check daemon and hook installations")
    doctor.add_argument("--url", default=os.getenv("WATCHTOWER_URL", defaults.base_url))
    doctor.add_argument("--timeout", type=float, default=3)
    doctor.add_argument("--project-dir", type=Path, default=Path.cwd())
    doctor.add_argument("--home", type=Path, default=Path.home())
    doctor.add_argument("--command", default="watchtower")
    doctor.set_defaults(handler=_command_doctor)

    install = subparsers.add_parser("install", help="Install Claude Code or Codex hooks")
    _add_installation_arguments(install)
    install.set_defaults(handler=_command_install)

    uninstall = subparsers.add_parser("uninstall", help="Remove only hooks managed by Watchtower")
    _add_installation_arguments(uninstall)
    uninstall.set_defaults(handler=_command_uninstall)

    checkpoint = subparsers.add_parser(
        "checkpoint", help="Create a confirmed local context checkpoint"
    )
    checkpoint.add_argument("--session-id", required=True)
    checkpoint.add_argument("--project-path")
    checkpoint.add_argument("--intervention-id")
    checkpoint.add_argument("--yes", action="store_true")
    checkpoint.add_argument("--url", default=os.getenv("WATCHTOWER_URL", defaults.base_url))
    checkpoint.add_argument("--timeout", type=float, default=5)
    checkpoint.set_defaults(handler=_command_checkpoint)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
