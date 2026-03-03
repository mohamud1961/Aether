import tempfile
import unittest
from pathlib import Path

from aether.agent_runner import Agentrunner, TaskSpec
from aether.artifact_store import ArtifactStore
from aether.claude_adapter import MockClaudeAdapter
from aether.control_plane import ControlPlane
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.policy_config import LoopBreakerConfig, PolicyConfig
from aether.tool_gateway import ToolGateway
from aether.verifier_registry import VerifierRegistry


class TestTransitionLoopBreaker(unittest.TestCase):
    def test_transition_only_loop_triggers_and_requires_concrete_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()

            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")
            policy = PolicyConfig(loop_breaker=LoopBreakerConfig(transition_only_window_size=2))
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
                                    "input": {"to_phase": "Explore", "phase_reason_code": "manual_request"},
                                }
                            ],
                            "stop_reason": "tool_use",
                            "usage": {},
                        },
                        {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_2",
                                    "name": "request_phase_transition",
                                    "input": {"to_phase": "Explore", "phase_reason_code": "manual_request"},
                                }
                            ],
                            "stop_reason": "tool_use",
                            "usage": {},
                        },
                        {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_3",
                                    "name": "request_phase_transition",
                                    "input": {"to_phase": "Plan", "phase_reason_code": "manual_request"},
                                }
                            ],
                            "stop_reason": "tool_use",
                            "usage": {},
                        },
                        {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_4",
                                    "name": "run",
                                    "input": {"command": ["python3", "-c", "print('evidence')"]},
                                }
                            ],
                            "stop_reason": "tool_use",
                            "usage": {},
                        },
                        {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_5",
                                    "name": "request_phase_transition",
                                    "input": {"to_phase": "Plan", "phase_reason_code": "manual_request"},
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
                TaskSpec(
                    prompt="Break transition-only loops before budget exhaustion.",
                    workspace_root=workspace,
                    max_steps=5,
                )
            )

            loop_events = [
                event for event in event_log.events if event.get("event_type") == "loop_breaker_trigger"
            ]
            self.assertTrue(loop_events)
            self.assertEqual(loop_events[-1].get("trigger_code"), "TRANSITION_ONLY_LOOP")
            self.assertEqual(loop_events[-1].get("deny_reason_code"), "TRANSITION_LOOP_ACTIVE")

            loop_denials = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION_DENIED"
                and event.get("deny_reason_code") == "TRANSITION_LOOP_ACTIVE"
            ]
            self.assertTrue(loop_denials)

            run_events = [
                event
                for event in event_log.events
                if str(event.get("event_type", "")).upper() == "TOOL_CALL"
                and event.get("tool_name") == "run"
            ]
            self.assertTrue(run_events)
            run_step = run_events[-1].get("step_id")
            post_run_loop_denials = [
                event for event in loop_denials if isinstance(event.get("step_id"), int) and event["step_id"] > run_step
            ]
            self.assertFalse(post_run_loop_denials)

            transitions_to_plan = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION"
                and event.get("to_phase") == "Plan"
            ]
            self.assertTrue(transitions_to_plan)


if __name__ == "__main__":
    unittest.main()
