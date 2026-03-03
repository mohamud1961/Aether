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
from aether.tool_schema_translator import ToolSchemaTranslator
from aether.verifier_registry import VerifierRegistry


class TestRunStartToolSurfaceProfile(unittest.TestCase):
    def test_run_start_emits_default_tool_surface_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log = EventLog(Path(tmpdir) / "event_log.jsonl")
            policy = PolicyConfig(policy_profile="eval")

            event = policy.emit_run_start_event(
                event_log,
                run_id="run-test",
                cwd="/tmp/workspace",
                enum_registry_hash="enum-hash",
            )

            self.assertIn("tool_surface_profile", event)
            self.assertEqual(
                event["tool_surface_profile"],
                {
                    "tools": ["run", "request_phase_transition"],
                    "interpreters": [],
                    "policy_profile": "eval",
                },
            )

    def test_run_start_accepts_explicit_tool_surface_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log = EventLog(Path(tmpdir) / "event_log.jsonl")
            policy = PolicyConfig(policy_profile="eval")
            explicit_profile = {
                "tools": ["run", "request_phase_transition", "fake_tool"],
                "interpreters": [],
                "policy_profile": "eval",
            }

            event = policy.emit_run_start_event(
                event_log,
                run_id="run-test",
                cwd="/tmp/workspace",
                enum_registry_hash="enum-hash",
                tool_surface_profile=explicit_profile,
            )

            self.assertEqual(event["tool_surface_profile"], explicit_profile)

    def test_run_start_tool_surface_matches_adapter_schema_without_model_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()

            event_log = EventLog(root / "events.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")
            policy = PolicyConfig.from_env()
            gateway = ToolGateway(
                artifact_store=artifact_store,
                event_log=event_log,
                governance_gate=GovernanceGate(
                    GovernancePolicy(
                        allowlist={"run", "read_file", "write_file", "search_files", "request_phase_transition"},
                        blocklist=set(),
                        default_decision="deny",
                    ),
                    event_log,
                ),
                workspace_root=workspace,
                policy_config=policy,
            )
            translator = ToolSchemaTranslator.from_gateway(gateway)
            adapter = MockClaudeAdapter(
                responses=[],
                schema_translator=translator,
            )
            runner = Agentrunner(
                adapter=adapter,
                tool_gateway=gateway,
                event_log=event_log,
                control_plane=ControlPlane(event_log, policy),
                verifier_registry=VerifierRegistry(verifiers=[], event_log=event_log),
                artifact_store=artifact_store,
                policy=policy,
            )

            result = runner.run_task(
                TaskSpec(prompt="Emit run_START only.", workspace_root=workspace, max_steps=0)
            )

            run_start_events = [event for event in event_log.events if event.get("event_type") == "run_START"]
            self.assertEqual(len(run_start_events), 1)
            expected_tools = [tool["name"] for tool in translator.get_harness_tools()]
            self.assertEqual(run_start_events[0]["tool_surface_profile"]["tools"], expected_tools)
            self.assertEqual(adapter.calls, [])
            self.assertEqual(result.reason, "step_limit")


if __name__ == "__main__":
    unittest.main()
