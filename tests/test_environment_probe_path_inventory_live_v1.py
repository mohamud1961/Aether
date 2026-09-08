from __future__ import annotations

import subprocess

from aether.environment_probe import _probe_commands
from aether.execution import CommandResult, MemoryExecutor


class _LivePathInventoryExecutor(MemoryExecutor):
    def __init__(self) -> None:
        super().__init__(workspace_root=".")
        self.discovery_exit_code: int | None = None
        self.discovery_stderr = ""

    def run_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_s: int = 30,
    ) -> CommandResult:
        self.command_history.append(command)
        if "path_rest=\"${PATH}:\"" not in command:
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="python3\t/usr/bin/python3\n",
            )
        completed = subprocess.run(
            ["/bin/sh", "-c", command],
            cwd=cwd or None,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        self.discovery_exit_code = completed.returncode
        self.discovery_stderr = completed.stderr
        return CommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def test_path_inventory_pipeline_executes_live_without_sort_separator_error() -> None:
    executor = _LivePathInventoryExecutor()
    commands = _probe_commands(
        executor,
        workspace_root=".",
        command_probe_names=("python3",),
    )
    assert executor.discovery_exit_code == 0, executor.discovery_stderr
    discovered = {
        name: row
        for name, row in commands.items()
        if name != "python3" and row.get("available")
    }
    assert discovered
    assert all(str(row.get("path") or "").startswith("/") for row in discovered.values())
