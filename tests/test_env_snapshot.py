from __future__ import annotations

from blocks.orientation.env_snapshot import orient


def test_env_snapshot_includes_optional_fields_when_provided():
    context = orient(
        "inspect workspace",
        env_info={
            "cwd": "/tmp/workspace",
            "data_root": "letta/filesystem",
            "safe_file_listing": ["people.txt", "pets.txt"],
            "python_binary": "python3",
            "environment_flags": {
                "orientation_injected": True,
                "python_contract_explicit": True,
                "max_steps": 12,
            },
        },
    )

    system_message = context["messages"][0]["content"]
    assert "Workspace cwd: /tmp/workspace" in system_message
    assert "Data root: letta/filesystem" in system_message
    assert "Safe file listing:" in system_message
    assert "- people.txt" in system_message
    assert "- pets.txt" in system_message
    assert "Use `python3` for Python commands in this environment." in system_message
    assert "Environment flags:" in system_message
    assert "- max_steps: 12" in system_message
    assert "- orientation_injected: true" in system_message
    assert "- python_contract_explicit: true" in system_message
