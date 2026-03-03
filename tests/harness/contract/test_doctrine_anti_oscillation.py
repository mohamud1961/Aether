import tempfile
import unittest
from pathlib import Path

from aether.agent_runner import Agentrunner, TaskSpec
from aether.artifact_store import ArtifactStore
from aether.claude_adapter import MockClaudeAdapter
from aether.control_plane import ControlPlane
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway
from aether.verifier_registry import VerifierRegistry


class TestDoctrineAntiOscillation(unittest.TestCase):
    def test_doctrine_includes_explicit_transition_anti_oscillation_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()

            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")
            policy = PolicyConfig.from_env()
            gate = GovernanceGate(
                GovernancePolicy(allowlist={"run", "verifier"}, blocklist=set(), default_decision="deny"),
                event_log,
            )
            gateway = ToolGateway(artifact_store, event_log, gate, workspace, policy)
            runner = Agentrunner(
                adapter=MockClaudeAdapter(responses=[]),
                tool_gateway=gateway,
                event_log=event_log,
                control_plane=ControlPlane(event_log, policy),
                verifier_registry=VerifierRegistry(verifiers=[], event_log=event_log),
                artifact_store=artifact_store,
                policy=policy,
            )

            task = TaskSpec(prompt="Apply doctrine update", workspace_root=workspace, max_steps=1)
            runner._initialize_execution_mode(task)
            runner._initialize_context(task)
            doctrine = runner.context_pack.get_tier_items("DOCTRINE")[-1]["content"]

            self.assertIn(
                "Do not request a phase transition unless a specific phase precondition is unmet.",
                doctrine,
            )
            self.assertIn("Prompt Legend:", doctrine)
            self.assertIn("[TASK]", doctrine)
            self.assertIn("[CONTRACTS]", doctrine)
            self.assertIn("[STATE]", doctrine)
            self.assertIn("[EVIDENCE]", doctrine)
            self.assertIn("[SCRATCH]", doctrine)
            self.assertIn("command_synopsis", doctrine)
            self.assertIn(
                "Do not repeat the same phase transition rationale if it was just denied or if no new evidence was gathered.",
                doctrine,
            )
            self.assertIn("request_phase_transition API usage:", doctrine)
            self.assertIn("missing_conditions", doctrine)
            self.assertIn("resolution_hint", doctrine)
            self.assertIn(
                "Continuity: the current ContextPack already includes relevant prior-step artifacts and denial outcomes.",
                doctrine,
            )
            self.assertNotIn(
                "Apply minimal correct code changes aligned with task and plan constraints.",
                runner._phase_goal("Implement"),
            )
            self.assertEqual(
                "Apply minimal correct changes aligned with task and plan constraints.",
                runner._phase_goal("Implement"),
            )
            self.assertNotIn("you have no memory of previous turns", doctrine)


if __name__ == "__main__":
    unittest.main()
