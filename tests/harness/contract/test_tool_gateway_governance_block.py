import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.tool_gateway import ToolGateway


class TestToolGatewayGovernanceBlock(unittest.TestCase):
    def test_governance_denies_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact_store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            policy = GovernancePolicy(allowlist=set(), blocklist={"blocked"})
            gate = GovernanceGate(policy, event_log)

            gate.evaluate(
                "blocked",
                risk_tier="high",
                timestamp="2026-01-26T00:00:00Z",
                cwd=root.as_posix(),
                tool_args={"command": ["python3", "-c", "open('blocked.txt','w').write('x')"]},
            )

            gateway = ToolGateway(
                artifact_store,
                event_log,
                gate,
                root,
            )

            with self.assertRaises(PermissionError):
                gateway.execute(
                    tool_name="blocked",
                tool_args={"command": ["python3", "-c", "open('blocked.txt','w').write('x')"]},
                    timestamp="2026-01-26T00:00:01Z",
                    cwd=Path("."),
                    write_paths=[Path("blocked.txt")],
                )

            self.assertFalse((root / "blocked.txt").exists())
            event = event_log.events[-1]
            self.assertEqual(event["event_type"], "tool_call_blocked")
            self.assertIsNone(event["exit_code"])


if __name__ == "__main__":
    unittest.main()
