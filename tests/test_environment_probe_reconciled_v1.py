from __future__ import annotations

import os
import subprocess
from pathlib import Path

from aether.environment_probe import _MAX_DISCOVERED_COMMANDS, _probe_commands
from aether.execution import CommandResult


class _PathExecutor:
    def __init__(self, *, path_value: str) -> None:
        self.path_value = path_value
        self.commands: list[str] = []

    def run_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_s: int = 30,
    ) -> CommandResult:
        self.commands.append(command)
        if command.startswith("for c in "):
            return CommandResult(command=command, exit_code=0, stdout="")
        if 'path_rest="${PATH}:"' in command:
            env = dict(os.environ)
            env["PATH"] = self.path_value
            proc = subprocess.run(
                ["/bin/sh", "-c", command],
                cwd=cwd,
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
            return CommandResult(
                command=command,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        raise AssertionError(f"unexpected command: {command}")


def _make_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def _available_discovered(commands: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        name: row
        for name, row in commands.items()
        if name != "python3" and bool(row.get("available"))
    }


def test_path_inventory_preserves_first_precedence_relative_empty_and_hidden_entries(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    relbin = tmp_path / "relbin"
    first.mkdir()
    second.mkdir()
    relbin.mkdir()

    _make_executable(first / "dupe")
    _make_executable(second / "dupe")
    _make_executable(second / "later")
    _make_executable(relbin / "relcmd")
    _make_executable(tmp_path / "cwdcmd")
    _make_executable(tmp_path / ".hiddenexec")

    # Relative first entry, consecutive/empty cwd entry, relative entry,
    # another relative entry, then trailing empty cwd entry.
    executor = _PathExecutor(path_value="first::relbin:second:")
    commands = _probe_commands(
        executor,
        workspace_root=str(tmp_path),
        command_probe_names=("python3",),
    )

    assert commands["dupe"] == {"available": True, "path": str((first / "dupe").resolve())}
    assert commands["later"] == {"available": True, "path": str((second / "later").resolve())}
    assert commands["relcmd"] == {"available": True, "path": str((relbin / "relcmd").resolve())}
    assert commands["cwdcmd"] == {"available": True, "path": str((tmp_path / "cwdcmd").resolve())}
    assert commands[".hiddenexec"] == {
        "available": True,
        "path": str((tmp_path / ".hiddenexec").resolve()),
    }
    assert all(str(row["path"]).startswith("/") for row in _available_discovered(commands).values())


def test_path_inventory_caps_after_deduplication_not_before(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    for index in range(200):
        name = f"a{index:03d}"
        _make_executable(first / name)
        _make_executable(second / name)
    for index in range(100):
        _make_executable(second / f"b{index:03d}")

    executor = _PathExecutor(path_value=f"{first}:{second}")
    commands = _probe_commands(
        executor,
        workspace_root=str(tmp_path),
        command_probe_names=("python3",),
    )
    discovered = _available_discovered(commands)

    assert len(discovered) == _MAX_DISCOVERED_COMMANDS
    assert "a000" in discovered and "a199" in discovered
    assert "b055" in discovered
    assert "b056" not in discovered
    assert discovered["a000"]["path"] == str((first / "a000").resolve())


def test_path_inventory_uses_no_external_discovery_utilities() -> None:
    class _CaptureExecutor:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> CommandResult:
            del cwd, timeout_s
            self.commands.append(command)
            if command.startswith("for c in "):
                return CommandResult(command=command, exit_code=0, stdout="")
            return CommandResult(command=command, exit_code=0, stdout="")

    executor = _CaptureExecutor()
    _probe_commands(executor, workspace_root="/app", command_probe_names=("python3",))
    discovery = next(command for command in executor.commands if 'path_rest="${PATH}:"' in command)
    for forbidden in ("compgen", " sort ", "awk ", "head ", "find ", "command -v --"):
        assert forbidden not in discovery
    assert f'-ge {_MAX_DISCOVERED_COMMANDS}' in discovery
    assert "break 2" in discovery
