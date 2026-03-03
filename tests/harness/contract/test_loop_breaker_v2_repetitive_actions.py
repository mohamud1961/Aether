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


class TestLoopBreakerV2RepetitiveActions(unittest.TestCase):
    def _build_runner(self, workspace: Path, event_log: EventLog, artifact_store: ArtifactStore, responses):
        policy = PolicyConfig(loop_breaker=LoopBreakerConfig(repetitive_action_threshold=3))
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

    def test_three_identical_ls_without_fingerprint_delta_triggers_loop_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")

            responses = [
                {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {}},
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "ls_1",
                            "name": "run",
                            "input": {"command": ["ls", "-la"]},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "ls_2",
                            "name": "run",
                            "input": {"command": ["ls", "-la"]},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "ls_3",
                            "name": "run",
                            "input": {"command": ["ls", "-la"]},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
            ]
            runner = self._build_runner(workspace, event_log, artifact_store, responses)
            runner.run_task(
                TaskSpec(
                    prompt="Execute deterministic listing for loop breaker test.",
                    workspace_root=workspace,
                    max_steps=3,
                )
            )

            loop_events = [
                event
                for event in event_log.events
                if event.get("event_type") == "loop_breaker_trigger"
                and event.get("trigger_code") == "LOOP_DETECTED"
            ]
            self.assertTrue(loop_events)
            self.assertEqual(loop_events[-1].get("deny_reason_code"), "LOOP_DETECTED")

    def test_sh_c_wrapped_commands_are_fingerprinted_as_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")

            responses = [
                {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {}},
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "ls_1",
                            "name": "run",
                            "input": {"command": ["ls", "-la"]},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "ls_2",
                            "name": "run",
                            "input": {"command": ["sh", "-c", "ls -la"]},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "ls_3",
                            "name": "run",
                            "input": {"command": ["ls", "-la"]},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
            ]
            runner = self._build_runner(workspace, event_log, artifact_store, responses)
            runner.run_task(
                TaskSpec(
                    prompt="Ensure loop breaker treats sh -c wrappers as equivalent for fingerprinting.",
                    workspace_root=workspace,
                    max_steps=3,
                )
            )

            loop_events = [
                event
                for event in event_log.events
                if event.get("event_type") == "loop_breaker_trigger"
                and event.get("trigger_code") == "LOOP_DETECTED"
            ]
            self.assertTrue(loop_events)

    def test_three_identical_state_changing_actions_do_not_trigger_loop_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")

            append_command = [
                "python3",
                "-c",
                "from pathlib import Path;p=Path('loop_counter.txt');p.write_text((p.read_text() if p.exists() else '')+'x')",
            ]
            responses = [
                {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {}},
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "echo_1",
                            "name": "run",
                            "input": {"command": append_command},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "echo_2",
                            "name": "run",
                            "input": {"command": append_command},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "echo_3",
                            "name": "run",
                            "input": {"command": append_command},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {},
                },
            ]
            runner = self._build_runner(workspace, event_log, artifact_store, responses)
            runner.run_task(
                TaskSpec(
                    prompt="Execute deterministic write for loop breaker progress test.",
                    workspace_root=workspace,
                    max_steps=3,
                )
            )

            loop_events = [
                event
                for event in event_log.events
                if event.get("event_type") == "loop_breaker_trigger"
                and event.get("trigger_code") == "LOOP_DETECTED"
            ]
            self.assertFalse(loop_events)


if __name__ == "__main__":
    unittest.main()
