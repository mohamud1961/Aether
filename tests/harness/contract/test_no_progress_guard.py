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


class TestNoProgressGuard(unittest.TestCase):
    def _build_runner(self, workspace: Path, event_log: EventLog, artifact_store: ArtifactStore, policy: PolicyConfig, responses):
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
        return Agentrunner(
            adapter=MockClaudeAdapter(responses=responses),
            tool_gateway=gateway,
            event_log=event_log,
            control_plane=ControlPlane(event_log, policy),
            verifier_registry=VerifierRegistry(verifiers=[], event_log=event_log),
            artifact_store=artifact_store,
            policy=policy,
        )

    def test_no_progress_guard_forces_plan_in_explore(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")
            policy = PolicyConfig(
                loop_breaker=LoopBreakerConfig(
                    no_progress_turn_threshold=2,
                    no_progress_max_force_plan=1,
                )
            )

            blocked_tool = {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "bad_cwd",
                        "name": "run",
                        "input": {"command": ["cat", "foo.txt"], "cwd": "workspace"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {},
            }
            responses = [
                {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {}},
                blocked_tool,
                blocked_tool,
            ]
            runner = self._build_runner(workspace, event_log, artifact_store, policy, responses)
            runner.run_task(
                TaskSpec(
                    prompt="Trigger no-progress guard and force Plan.",
                    workspace_root=workspace,
                    max_steps=2,
                )
            )

            guard_events = [
                event
                for event in event_log.events
                if event.get("event_type") == "loop_breaker_trigger"
                and event.get("trigger_code") == "NO_PROGRESS_GUARD"
                and event.get("action_taken") == "FORCE_PLAN"
            ]
            self.assertTrue(guard_events)

            plan_transitions = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION"
                and event.get("from_phase") == "Explore"
                and event.get("to_phase") == "Plan"
            ]
            self.assertTrue(plan_transitions)

    def test_no_progress_guard_fails_stuck_in_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")
            policy = PolicyConfig(
                loop_breaker=LoopBreakerConfig(
                    no_progress_turn_threshold=1,
                    no_progress_max_force_plan=1,
                )
            )

            blocked_tool = {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "bad_cwd",
                        "name": "run",
                        "input": {"command": ["cat", "foo.txt"], "cwd": "workspace"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {},
            }
            responses = [
                {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {}},
                blocked_tool,
                blocked_tool,
            ]
            runner = self._build_runner(workspace, event_log, artifact_store, policy, responses)
            result = runner.run_task(
                TaskSpec(
                    prompt="Trigger no-progress guard failure path.",
                    workspace_root=workspace,
                    max_steps=2,
                )
            )

            self.assertFalse(result.success)
            self.assertEqual(result.reason, "no_progress")
            self.assertEqual(result.final_state, "FAIL")


if __name__ == "__main__":
    unittest.main()
