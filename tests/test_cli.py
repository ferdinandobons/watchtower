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
