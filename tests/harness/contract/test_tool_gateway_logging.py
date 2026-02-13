import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.tool_gateway import ToolGateway


class TestToolGatewayLogging(unittest.TestCase):
    def test_logging_and_truncation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact_store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            policy = GovernancePolicy(allowlist={"run"}, blocklist=set())
            gate = GovernanceGate(policy, event_log)

            gate.evaluate(
                "run",
                risk_tier="low",
                timestamp="2026-01-26T00:00:00Z",
                cwd=root.as_posix(),
                tool_args={"command": ["python3", "-c", "print('hello')"]},
            )

            gateway = ToolGateway(
                artifact_store,
                event_log,
                gate,
                root,
            )

            result = gateway.execute(
                tool_name="run",
                tool_args={"command": ["python3", "-c", "print('hello')"]},
                timestamp="2026-01-26T00:00:01Z",
                cwd=Path("."),
            )

            event = event_log.events[-1]
            self.assertEqual(event["tool_name"], "run")
            self.assertEqual(event["exit_code"], 0)
            self.assertIsNotNone(event.get("stdout_ref"))
            self.assertIsNotNone(event.get("stderr_ref"))
            self.assertIn("stdout", event["truncation"])
            self.assertIn("stderr", event["truncation"])
            self.assertFalse(event["truncation"]["stdout"]["unknown"])
            self.assertFalse(event["truncation"]["stderr"]["unknown"])

            stdout_bytes = artifact_store.read_bytes(result.stdout_ref)
            self.assertIn(b"hello", stdout_bytes)


if __name__ == "__main__":
    unittest.main()
