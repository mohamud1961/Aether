from __future__ import annotations

import subprocess
from pathlib import Path

from aether.execution import CommandResult
from aether.harbor_executor import HarborEnvironmentExecutor
from aether.verifier_overlay import VerifierOverlay


class _OverlayExecutor:
    supports_activation_scoped_verifier_snapshot = True

    def __init__(self, root: Path) -> None:
        self.root = root
        self.commands: list[str] = []
        self.isolated_roots: list[str] = []
        self.fixtures: list[dict[str, str]] = []
        self.released: list[str] = []

    def run_command(self, command: str, timeout_s: int = 30):
        del timeout_s
        self.commands.append(command)
        if command.startswith("rm -rf ") and " && cp -a " in command:
            # Simulate the pristine activation copy only.
            class R:
                success = True; exit_code = 0; stdout = ""; stderr = ""
            return R()
        if command.startswith("rm -rf "):
            class R:
                success = True; exit_code = 0; stdout = ""; stderr = ""
            return R()
        class R:
            success = True; exit_code = 0; stdout = ""; stderr = ""
        return R()

    def for_workspace(self, workspace_root: str):
        return self

    def run_independent_verifier_command(self, command: str, *, workspace_root: str, timeout_s: int, fixture_contents=None):
        del timeout_s
        self.isolated_roots.append(workspace_root)
        self.fixtures.append(dict(fixture_contents or {}))
        return {
            "result": CommandResult(command=command, exit_code=0, stdout="ok\n", stderr=""),
            "metadata": {
                "execution_isolation": "harbor_docker_snapshot_sibling",
                "independent_isolation_verified": True,
                "isolation_cleanup_verified": True,
                "snapshot_reused": len(self.isolated_roots) > 1,
            },
        }

    def release_independent_verifier_snapshot(self, workspace_root: str):
        self.released.append(workspace_root)
        return {"released": True, "snapshot_image_removed": True}


def test_verifier_overlay_reuses_pristine_root_without_parent_command_child_copies(tmp_path: Path) -> None:
    root = tmp_path / "app"
    root.mkdir()
    (root / "state.txt").write_text("stable\n")
    executor = _OverlayExecutor(root)
    overlay = VerifierOverlay(executor, str(root), require_independent_isolation=True)

    first = overlay.run_command("cat /app/state.txt")
    second = overlay.run_command("cat /app/state.txt")
    assert first["success"] is True and second["success"] is True
    assert len(executor.isolated_roots) == 2
    assert executor.isolated_roots[0] == executor.isolated_roots[1] == overlay.overlay_root
    cp_commands = [c for c in executor.commands if " && cp -a " in c]
    assert len(cp_commands) == 1, "only the pristine activation overlay may be copied in the parent"
    assert not any(".command_" in c for c in cp_commands)
    torn = overlay.teardown()
    assert torn["removed"] is True
    assert executor.released == [executor.isolated_roots[0]]


class _CommandChildOverlayExecutor(_OverlayExecutor):
    supports_activation_scoped_verifier_snapshot = False


def test_verifier_overlay_binds_non_harbor_isolation_to_command_child(tmp_path: Path) -> None:
    """Generic isolated runners receive the child required by their path contract."""
    root = tmp_path / "app"
    root.mkdir()
    (root / "state.txt").write_text("stable\n")
    executor = _CommandChildOverlayExecutor(root)
    overlay = VerifierOverlay(executor, str(root), require_independent_isolation=True)

    result = overlay.run_command("cat /app/state.txt")

    assert result["success"] is True
    assert len(executor.isolated_roots) == 1
    isolated_root = executor.isolated_roots[0]
    assert ".verifier_overlay_" in isolated_root
    assert ".command_" in isolated_root
    assert isolated_root != overlay.overlay_root
    cp_commands = [c for c in executor.commands if " && cp -a " in c]
    assert len(cp_commands) == 2, "activation and command-child copies are both required"
    assert any(".command_" in c for c in cp_commands[1:])
    assert result["command_child_removed"] is True


def test_harbor_activation_snapshot_commits_once_reuses_twice_and_releases(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    paused = False

    class Env:
        def type(self): return "docker"
    import asyncio
    loop = asyncio.new_event_loop()
    executor = HarborEnvironmentExecutor(Env(), event_loop=loop, workspace_root="/app", local_state_dir=tmp_path)
    monkeypatch.setattr(executor, "_harbor_docker_main_container_id", lambda: ("a" * 64, ""))
    monkeypatch.setattr(executor, "_wait_for_docker_container_runnable", lambda *a, **k: (True, "", 1))

    def fake_host_call(args: list[str], *, timeout_s: int):
        nonlocal paused
        del timeout_s
        calls.append(list(args))
        if args[:3] == ["docker", "inspect", "--format"]:
            return subprocess.CompletedProcess(args, 0, stdout=f"true {'true' if paused else 'false'}\n", stderr=""), ""
        if args[:2] == ["docker", "pause"]:
            paused = True; return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:2] == ["docker", "unpause"]:
            paused = False; return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:3] == ["docker", "commit", "--pause=false"]:
            return subprocess.CompletedProcess(args, 0, stdout="sha256:snapshot\n", stderr=""), ""
        if args[:2] == ["docker", "run"]:
            joined = " ".join(args)
            assert 'mv "$src" /app' in joined
            assert 'cp -a "$src"/. /app/' not in joined
            return subprocess.CompletedProcess(args, 0, stdout="sibling\n", stderr=""), ""
        if args[:2] == ["docker", "exec"]:
            if "test" in args and "-f" in args:
                return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
            return subprocess.CompletedProcess(args, 0, stdout="verified\n", stderr=""), ""
        if args[:3] == ["docker", "rm", "-f"] or args[:3] == ["docker", "image", "rm"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=""), ""
        if args[:2] == ["docker", "inspect"] or args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="not found"), ""
        raise AssertionError(args)

    monkeypatch.setattr(executor, "_docker_host_call", fake_host_call)
    root = "/app.verifier_overlay_deadbeef"
    one = executor.run_independent_verifier_command("printf one", workspace_root=root)
    two = executor.run_independent_verifier_command("printf two", workspace_root=root)
    assert not one.get("error") and not two.get("error")
    assert one["metadata"]["snapshot_reused"] is False
    assert two["metadata"]["snapshot_reused"] is True
    assert sum(1 for c in calls if c[:3] == ["docker", "commit", "--pause=false"]) == 1
    assert sum(1 for c in calls if c[:2] == ["docker", "run"]) == 2
    release = executor.release_independent_verifier_snapshot(root)
    assert release["released"] is True
    assert sum(1 for c in calls if c[:3] == ["docker", "image", "rm"]) == 1
    loop.close()
