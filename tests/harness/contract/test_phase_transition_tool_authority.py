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


class TestPhaseTransitionToolAuthority(unittest.TestCase):
    def test_runner_does_not_auto_advance_explore_to_implement(self) -> None:
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
            gateway = ToolGateway(
                artifact_store=artifact_store,
                event_log=event_log,
                governance_gate=gate,
                workspace_root=workspace,
                policy_config=policy,
            )
            runner = Agentrunner(
                adapter=MockClaudeAdapter(
                    responses=[
                        {
                            "content": [{"type": "text", "text": "{}"}],
                            "stop_reason": "end_turn",
                            "usage": {},
                        },
                        {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_1",
                                    "name": "run",
                                    "input": {"command": ["python3", "-c", "print('ok')"]},
                                }
                            ],
                            "stop_reason": "tool_use",
                            "usage": {},
                        },
                    ]
                ),
                tool_gateway=gateway,
                event_log=event_log,
                control_plane=ControlPlane(event_log, policy),
                verifier_registry=VerifierRegistry(verifiers=[], event_log=event_log),
                artifact_store=artifact_store,
                policy=policy,
            )

            runner.run_task(
                TaskSpec(prompt="Perform one explore action only.", workspace_root=workspace, max_steps=1)
            )

            explore_to_implement = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION"
                and event.get("from_phase") == "Explore"
                and event.get("to_phase") == "Implement"
            ]
            self.assertFalse(explore_to_implement)

    def test_review_transition_tool_request_denied_from_explore_even_when_workspace_clean(self) -> None:
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
            gateway = ToolGateway(
                artifact_store=artifact_store,
                event_log=event_log,
                governance_gate=gate,
                workspace_root=workspace,
                policy_config=policy,
            )
            runner = Agentrunner(
                adapter=MockClaudeAdapter(
                    responses=[
                        {
                            "content": [{"type": "text", "text": "{}"}],
                            "stop_reason": "end_turn",
                            "usage": {},
                        },
                        {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_1",
                                    "name": "request_phase_transition",
                                    "input": {
                                        "to_phase": "Review",
                                        "phase_reason_code": "manual_request",
                                    },
                                }
                            ],
                            "stop_reason": "tool_use",
                            "usage": {},
                        },
                    ]
                ),
                tool_gateway=gateway,
                event_log=event_log,
                control_plane=ControlPlane(event_log, policy),
                verifier_registry=VerifierRegistry(verifiers=[], event_log=event_log),
                artifact_store=artifact_store,
                policy=policy,
            )

            result = runner.run_task(
                TaskSpec(prompt="Request review directly without modifying workspace.", workspace_root=workspace, max_steps=1)
            )

            denied = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION_DENIED"
                and event.get("to_phase") == "Review"
            ]
            self.assertTrue(denied)
            self.assertEqual(denied[-1].get("deny_reason_code"), "PHASE_ORDER_VIOLATION")

            review_transitions = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION" and event.get("to_phase") == "Review"
            ]
            self.assertFalse(review_transitions)
            self.assertNotEqual(result.final_state, "Review")


if __name__ == "__main__":
    unittest.main()
