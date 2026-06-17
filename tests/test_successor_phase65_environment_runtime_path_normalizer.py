from __future__ import annotations

import json
from pathlib import Path

from blocks.tools.app_path_normalizer import execute_tool_call


class _Sandbox:
    sandbox_type = "none"

    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.last_command = ""
        self.seen_script_text = ""

    def exec(self, command):  # type: ignore[no-untyped-def]
        self.last_command = command
        if command.startswith("bash ") and ".phase65_" in command:
            script_path_text = command.split(" ", 1)[1].strip()
            if (
                len(script_path_text) >= 2
                and script_path_text[0] == script_path_text[-1]
                and script_path_text[0] in {"'", '"'}
            ):
                script_path_text = script_path_text[1:-1]
            script_path = Path(script_path_text)
            self.seen_script_text = script_path.read_text(encoding="utf-8")
        return {"exit_code": 0, "stdout": command, "stderr": "", "timed_out": False}


def test_path_normalizer_rewrites_exact_app_alias_without_touching_non_aliases(tmp_path):
    sandbox = _Sandbox(tmp_path)
    result = execute_tool_call(
        {
            "name": "raw_bash",
            "arguments": json.dumps(
                {
                    "command": "cd /app && ls /app && cat /app/output.txt && echo /application && echo http://app"
                }
            ),
        },
        sandbox,
    )

    assert result["result_class"] == "success"
    assert f"cd {tmp_path}" in result["command"]
    assert f"ls {tmp_path}" in result["command"]
    assert f"cat {tmp_path}/output.txt" in result["command"]
    assert "/application" in result["command"]
    assert "http://app" in result["command"]


def test_path_normalizer_rewrites_local_script_body_and_cleans_temp_file(tmp_path):
    script = tmp_path / "verify.sh"
    script.write_text("#!/usr/bin/env bash\ncat /app/output.txt\n", encoding="utf-8")
    sandbox = _Sandbox(tmp_path)

    result = execute_tool_call(
        {"name": "raw_bash", "arguments": json.dumps({"command": "bash ./verify.sh"})},
        sandbox,
    )

    assert result["result_class"] == "success"
    assert "/app/output.txt" not in sandbox.seen_script_text
    assert f"{tmp_path}/output.txt" in sandbox.seen_script_text
    assert not list(tmp_path.glob(".phase65_*"))


def test_path_normalizer_rewrites_quoted_local_script_body_and_cleans_temp_file(tmp_path):
    script = tmp_path / "verify.sh"
    script.write_text("#!/usr/bin/env bash\ncat /app/output.txt\n", encoding="utf-8")
    sandbox = _Sandbox(tmp_path)

    result = execute_tool_call(
        {"name": "raw_bash", "arguments": json.dumps({"command": 'bash "./verify.sh"'})},
        sandbox,
    )

    assert result["result_class"] == "success"
    assert '.phase65_' in result["command"]
    assert "/app/output.txt" not in sandbox.seen_script_text
    assert f"{tmp_path}/output.txt" in sandbox.seen_script_text
    assert not list(tmp_path.glob(".phase65_*"))


def test_path_normalizer_does_not_rewrite_nonlocal_absolute_scripts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    external = tmp_path / "external.sh"
    external.write_text("#!/usr/bin/env bash\necho /app/output.txt\n", encoding="utf-8")
    sandbox = _Sandbox(workspace)

    result = execute_tool_call(
        {"name": "raw_bash", "arguments": json.dumps({"command": f"bash {external}"})},
        sandbox,
    )

    assert result["result_class"] == "success"
    assert result["command"] == f"bash {external}"
    assert not list(workspace.glob(".phase65_*"))
