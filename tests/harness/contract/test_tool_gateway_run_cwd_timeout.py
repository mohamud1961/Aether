import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.path_sandbox import PathSandboxError
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway


class _Completed:
    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestToolGatewayRunCwdTimeout(unittest.TestCase):
    def test_run_accepts_absolute_cwd_under_workspace(self) -> None:
        """Absolute cwd under workspace root must be accepted (regression: PATH_SANDBOX_VIOLATION)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            store = ArtifactStore(workspace / "artifacts")
            event_log = EventLog(workspace / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(allowlist={"run"}, blocklist=set(), default_decision="deny"),
                event_log,
            )
            gateway = ToolGateway(store, event_log, gate, workspace, PolicyConfig.from_env())

            resolved = gateway._resolve_execution_cwd(
                tool_name="run",
                requested_cwd=workspace,
                tool_args={"cwd": str(workspace), "command": ["ls"]},
            )
            self.assertEqual(resolved, workspace.resolve())

    def test_run_accepts_absolute_cwd_subdir_under_workspace(self) -> None:
        """Absolute cwd to a subdirectory under workspace root must be accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            subdir = workspace / "src"
            subdir.mkdir(exist_ok=True)
            store = ArtifactStore(workspace / "artifacts")
            event_log = EventLog(workspace / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(allowlist={"run"}, blocklist=set(), default_decision="deny"),
                event_log,
            )
            gateway = ToolGateway(store, event_log, gate, workspace, PolicyConfig.from_env())

            resolved = gateway._resolve_execution_cwd(
                tool_name="run",
                requested_cwd=workspace,
                tool_args={"cwd": str(subdir), "command": ["ls"]},
            )
            self.assertEqual(resolved, subdir.resolve())

    def test_run_rejects_absolute_cwd_outside_workspace(self) -> None:
        """Absolute cwd outside workspace must still raise PATH_SANDBOX_VIOLATION."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            store = ArtifactStore(workspace / "artifacts")
            event_log = EventLog(workspace / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(allowlist={"run"}, blocklist=set(), default_decision="deny"),
                event_log,
            )
            gateway = ToolGateway(store, event_log, gate, workspace, PolicyConfig.from_env())

            with self.assertRaises(PathSandboxError):
                gateway._resolve_execution_cwd(
                    tool_name="run",
                    requested_cwd=workspace,
                    tool_args={"cwd": "/tmp/evil", "command": ["ls"]},
                )

    def test_run_honors_tool_cwd_under_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "subdir").mkdir()
            store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(allowlist={"run"}, blocklist=set(), default_decision="deny"),
                event_log,
            )
            runner = MagicMock(return_value=_Completed(stdout=b"ok"))
            gateway = ToolGateway(store, event_log, gate, root, PolicyConfig.from_env(), subprocess_runner=runner)

            tool_args = {"command": ["pwd"], "cwd": "subdir"}
            gate.evaluate(
                action="run",
                risk_tier="low",
                timestamp="2026-02-14T00:00:00Z",
                cwd=(root / "subdir").as_posix(),
                tool_args=tool_args,
            )

            result = gateway.execute(
                tool_name="run",
                tool_args=tool_args,
                timestamp="2026-02-14T00:00:01Z",
                cwd=Path("."),
            )

            self.assertEqual(runner.call_args.kwargs["cwd"], (root / "subdir").resolve())
            self.assertEqual(result.event.get("resolved_cwd"), (root / "subdir").resolve().as_posix())

    def test_run_rejects_cwd_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(allowlist={"run"}, blocklist=set(), default_decision="deny"),
                event_log,
            )
            gateway = ToolGateway(store, event_log, gate, root, PolicyConfig.from_env())

            with self.assertRaises(PermissionError):
                gateway.execute(
                    tool_name="run",
                    tool_args={"command": ["pwd"], "cwd": "../../escape"},
                    timestamp="2026-02-14T00:00:01Z",
                    cwd=Path("."),
                )

            blocked = event_log.events[-1]
            self.assertEqual(blocked["event_type"], "tool_call_blocked")
            self.assertEqual(blocked["deny_reason_code"], "PATH_SANDBOX_VIOLATION")

    def test_run_timeout_sets_tool_timeout_and_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(allowlist={"run"}, blocklist=set(), default_decision="deny"),
                event_log,
            )

            def _timeout_runner(*args, **kwargs):
                raise subprocess.TimeoutExpired(
                    cmd=args[0],
                    timeout=kwargs.get("timeout", 0.0),
                    output=b"partial-output",
                    stderr=b"partial-stderr",
                )

            gateway = ToolGateway(
                store,
                event_log,
                gate,
                root,
                PolicyConfig.from_env(),
                subprocess_runner=_timeout_runner,
            )
            tool_args = {"command": ["sleep", "5"], "timeout_ms": 1}
            gate.evaluate(
                action="run",
                risk_tier="low",
                timestamp="2026-02-14T00:00:00Z",
                cwd=root.as_posix(),
                tool_args=tool_args,
            )

            result = gateway.execute(
                tool_name="run",
                tool_args=tool_args,
                timestamp="2026-02-14T00:00:01Z",
                cwd=Path("."),
            )

            self.assertEqual(result.exit_code, "TIMEOUT")
            self.assertEqual(result.event.get("tool_timeout"), True)
            self.assertEqual(result.event.get("timeout_ms"), 1)
            self.assertIsInstance(result.event.get("duration_ms"), int)

            stderr_text = store.read_bytes(result.stderr_ref).decode("utf-8")
            self.assertIn("Command timed out after 1ms and was terminated.", stderr_text)


if __name__ == "__main__":
    unittest.main()
