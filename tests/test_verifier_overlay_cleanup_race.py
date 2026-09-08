from __future__ import annotations

from types import SimpleNamespace

from aether.execution import CommandResult
from aether.verifier_overlay import VerifierOverlay


def _ok(command: str = "true") -> CommandResult:
    return CommandResult(
        command=command,
        exit_code=0,
        stdout="ok\n",
        stderr="",
        stdout_bytes_total=3,
        stderr_bytes_total=0,
        timed_out=False,
        metrics={"command_execution_elapsed_s": 0.01},
        provenance=("test",),
    )


class _Child:
    def run_command(self, command: str, *, timeout_s: int = 30):
        del timeout_s
        return _ok(command)


class _Parent:
    def __init__(self) -> None:
        self.calls = 0

    def run_command(self, command: str, *, timeout_s: int = 30):
        del timeout_s
        self.calls += 1
        # ensure() copy, then command-child copy succeed. The final parent-side
        # command-child cleanup reproduces the observed Docker paused race.
        if self.calls == 3:
            raise RuntimeError("Container abc is paused, unpause the container before exec")
        return _ok(command)

    def for_workspace(self, _workspace_root: str):
        return _Child()

    def run_independent_verifier_command(self, command: str, *, workspace_root: str, timeout_s: int = 30):
        del workspace_root, timeout_s
        return {
            "result": _ok(command),
            "metadata": {
                "independent_isolation_verified": True,
                "isolation_cleanup_verified": True,
                "execution_isolation": "harbor_docker_snapshot_sibling",
                "command_execution_elapsed_s": 0.01,
            },
            "error": "",
        }


def test_parent_cleanup_pause_race_is_structured_not_raised(monkeypatch):
    # The synthetic local path does not exist; symlink scanning is orthogonal
    # to this lifecycle regression.
    monkeypatch.setattr(VerifierOverlay, "_symlink_escape_error", staticmethod(lambda _root: ""))
    overlay = VerifierOverlay(_Parent(), "/app", require_independent_isolation=True)
    result = overlay.run_command("true")
    assert result["command_child_removed"] is False
    assert result["error"].startswith("verifier command-child cleanup failed: RuntimeError:")
    assert "is paused" in result["error"]


class _SnapshotBlockerParent:
    def __init__(self) -> None:
        self.run_calls = 0
        self.isolation_calls = 0

    def run_command(self, command: str, *, timeout_s: int = 30):
        del timeout_s
        self.run_calls += 1
        return _ok(command)

    def for_workspace(self, _workspace_root: str):
        return _Child()

    def run_independent_verifier_command(self, command: str, *, workspace_root: str, timeout_s: int = 30):
        del command, workspace_root, timeout_s
        self.isolation_calls += 1
        return {
            "error": (
                "verifier_independent_isolation_docker_commit_failed:"
                "TimeoutExpired: docker commit exceeded snapshot custody"
            ),
            "metadata": {
                "independent_isolation_verified": False,
                "isolation_cleanup_verified": True,
            },
        }


def test_snapshot_commit_failure_is_not_retried_within_same_verifier_activation(monkeypatch):
    monkeypatch.setattr(VerifierOverlay, "_symlink_escape_error", staticmethod(lambda _root: ""))
    parent = _SnapshotBlockerParent()
    overlay = VerifierOverlay(parent, "/app", require_independent_isolation=True)

    first = overlay.run_command("true")
    second = overlay.run_command("true")

    assert first["error"].startswith("verifier_independent_isolation_docker_commit_failed:")
    assert second["error"] == first["error"]
    assert second["snapshot_retry_suppressed"] is True
    assert parent.isolation_calls == 1
