import json
import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway


class TestNativeFileToolsPathSandbox(unittest.TestCase):
    def test_native_file_tools_perform_workspace_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            artifact_store = ArtifactStore(workspace / "artifacts")
            event_log = EventLog(workspace / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(
                    allowlist={"read_file", "write_file", "search_files"},
                    blocklist=set(),
                    default_decision="deny",
                ),
                event_log,
            )
            gateway = ToolGateway(artifact_store, event_log, gate, workspace, PolicyConfig.from_env())

            write_args = {"path": "notes/todo.txt", "content": "alpha\nbeta\n"}
            gate.evaluate(
                action="write_file",
                risk_tier="low",
                timestamp="2026-02-22T00:00:00Z",
                cwd=workspace.as_posix(),
                tool_args=write_args,
            )
            write_result = gateway.execute(
                tool_name="write_file",
                tool_args=write_args,
                timestamp="2026-02-22T00:00:01Z",
                cwd=workspace,
            )
            self.assertEqual(write_result.exit_code, 0)
            self.assertTrue((workspace / "notes" / "todo.txt").exists())
            self.assertEqual((workspace / "notes" / "todo.txt").read_text(encoding="utf-8"), "alpha\nbeta\n")

            read_args = {"path": "notes/todo.txt"}
            gate.evaluate(
                action="read_file",
                risk_tier="low",
                timestamp="2026-02-22T00:00:02Z",
                cwd=workspace.as_posix(),
                tool_args=read_args,
            )
            read_result = gateway.execute(
                tool_name="read_file",
                tool_args=read_args,
                timestamp="2026-02-22T00:00:03Z",
                cwd=workspace,
            )
            read_payload = json.loads(artifact_store.read_bytes(read_result.stdout_ref).decode("utf-8"))
            self.assertEqual(read_result.exit_code, 0)
            self.assertEqual(read_payload["content"], "alpha\nbeta\n")
            self.assertEqual(read_payload["path"], "notes/todo.txt")

            search_args = {"pattern": "alpha", "path": "notes"}
            gate.evaluate(
                action="search_files",
                risk_tier="low",
                timestamp="2026-02-22T00:00:04Z",
                cwd=workspace.as_posix(),
                tool_args=search_args,
            )
            search_result = gateway.execute(
                tool_name="search_files",
                tool_args=search_args,
                timestamp="2026-02-22T00:00:05Z",
                cwd=workspace,
            )
            search_payload = json.loads(artifact_store.read_bytes(search_result.stdout_ref).decode("utf-8"))
            self.assertEqual(search_result.exit_code, 0)
            self.assertTrue(search_payload["matches"])
            self.assertEqual(search_payload["matches"][0]["path"], "notes/todo.txt")

    def test_native_file_tools_deny_out_of_sandbox_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            outside_dir = root / "outside"
            outside_dir.mkdir(parents=True, exist_ok=True)
            outside_file = outside_dir / "secret.txt"
            outside_file.write_text("top-secret", encoding="utf-8")

            artifact_store = ArtifactStore(workspace / "artifacts")
            event_log = EventLog(workspace / "event_log.jsonl")
            gate = GovernanceGate(
                GovernancePolicy(
                    allowlist={"read_file", "write_file", "search_files"},
                    blocklist=set(),
                    default_decision="deny",
                ),
                event_log,
            )
            gateway = ToolGateway(artifact_store, event_log, gate, workspace, PolicyConfig.from_env())

            blocked_calls = [
                ("read_file", {"path": outside_file.as_posix()}),
                ("write_file", {"path": (outside_dir / "new.txt").as_posix(), "content": "x"}),
                ("search_files", {"pattern": "secret", "path": outside_dir.as_posix()}),
            ]

            for index, (tool_name, tool_args) in enumerate(blocked_calls):
                gate.evaluate(
                    action=tool_name,
                    risk_tier="low",
                    timestamp=f"2026-02-22T00:01:0{index}Z",
                    cwd=workspace.as_posix(),
                    tool_args=tool_args,
                )
                with self.assertRaises(PermissionError):
                    gateway.execute(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        timestamp=f"2026-02-22T00:02:0{index}Z",
                        cwd=workspace,
                    )
                blocked_event = event_log.events[-1]
                self.assertEqual(blocked_event["event_type"], "tool_call_blocked")
                self.assertEqual(blocked_event["deny_reason_code"], "PATH_SANDBOX_VIOLATION")


if __name__ == "__main__":
    unittest.main()
