from __future__ import annotations

from watchtower.cli import _hook_message


def test_hook_message_is_empty_without_interventions() -> None:
    assert _hook_message({"interventions": []}) == {}


def test_hook_message_contains_grounded_intervention() -> None:
    output = _hook_message(
        {
            "interventions": [
                {
                    "severity": "warning",
                    "title": "Repeated failure loop detected",
                    "message": "The same verification failed three times.",
                    "suggested_action": "launch_read_only_reviewer",
                }
            ]
        }
    )
    assert "systemMessage" in output
    assert "Repeated failure loop detected" in output["systemMessage"]
    assert "launch_read_only_reviewer" in output["systemMessage"]


def test_install_and_uninstall_cli_round_trip(tmp_path, capsys) -> None:
    import sys

    from watchtower.cli import main
    from watchtower.installer import inspect_installation

    install_args = [
        "install",
        "claude-code",
        "--scope",
        "user",
        "--home",
        str(tmp_path),
        "--command",
        sys.executable,
    ]
    assert main(install_args) == 0
    path = tmp_path / ".claude" / "settings.json"
    assert inspect_installation(path, "claude-code", sys.executable)

    uninstall_args = [
        "uninstall",
        "claude-code",
        "--scope",
        "user",
        "--home",
        str(tmp_path),
        "--command",
        sys.executable,
    ]
    assert main(uninstall_args) == 0
    assert not inspect_installation(path, "claude-code", sys.executable)
    assert "claude-code" in capsys.readouterr().out


def test_checkpoint_cli_requires_confirmation(capsys) -> None:
    from watchtower.cli import main

    assert main(["checkpoint", "--session-id", "s1"]) == 2
    assert "Re-run with --yes" in capsys.readouterr().err
