import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway
from aether.verifier_plan import VerifierDefinition
from aether.verifier_registry import VerifierRegistry
from aether.verify_and_repair import RepairPlan, verify_and_repair


class TestVerifyAndRepairBounded(unittest.TestCase):
    def test_repair_loop_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact_store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            policy = GovernancePolicy(allowlist={"verifier"}, blocklist=set())
            gate = GovernanceGate(policy, event_log)
            gate.evaluate(
                "verifier",
                risk_tier="low",
                timestamp="2026-01-27T00:00:00Z",
                cwd=root.as_posix(),
                tool_args={"command": ["python3", "-c", "import sys; sys.exit(1)"]},
            )

            gateway = ToolGateway(
                artifact_store,
                event_log,
                gate,
                root,
                PolicyConfig.from_env(),
            )
            registry = VerifierRegistry(
                [
                    VerifierDefinition(
                        name="verifier",
                command=["python3", "-c", "import sys; sys.exit(1)"],
                    )
                ],
                event_log,
            )

            def repair_strategy(_result, _fingerprint):
                return RepairPlan(description="no-op", payload=None)

            outcome = verify_and_repair(
                verifier_registry=registry,
                tool_gateway=gateway,
                event_log=event_log,
                artifact_store=artifact_store,
                workspace_root=root,
                task_spec={"task": "demo"},
                repair_strategy=repair_strategy,
                max_attempts=2,
                timestamp="2026-01-27T00:00:01Z",
                cwd=root,
            )

            self.assertEqual(outcome.termination_reason, "max_attempts")
            self.assertEqual(len(outcome.attempts), 2)
            for attempt in outcome.attempts:
                self.assertTrue(attempt.repair_artifact_ref)


if __name__ == "__main__":
    unittest.main()
