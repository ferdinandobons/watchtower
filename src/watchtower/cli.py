from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from watchtower.config import Settings


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


def _command_doctor(args: argparse.Namespace) -> int:
    try:
        result = _request_json("GET", f"{args.url.rstrip('/')}/health", timeout=args.timeout)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Watchtower daemon is unavailable: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


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

    doctor = subparsers.add_parser("doctor", help="Check the local daemon")
    doctor.add_argument("--url", default=os.getenv("WATCHTOWER_URL", defaults.base_url))
    doctor.add_argument("--timeout", type=float, default=3)
    doctor.set_defaults(handler=_command_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
