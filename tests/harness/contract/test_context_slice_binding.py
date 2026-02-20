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


class TestContextSliceBinding(unittest.TestCase):
    def test_context_slice_emitted_for_each_model_call(self) -> None:
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

            adapter = MockClaudeAdapter(
                responses=[
                    {
                        "content": [{"type": "text", "text": "Done"}],
                        "stop_reason": "end_turn",
                        "usage": {},
                    }
                ]
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
            runner.run_task(TaskSpec(prompt="slice binding", workspace_root=workspace, max_steps=1))

            requests = [e for e in event_log.events if e.get("event_type") == "model_request"]
            slices = [e for e in event_log.events if e.get("event_type") == "context_slice_bound"]

            self.assertGreaterEqual(len(requests), 1)
            self.assertGreaterEqual(len(slices), len(requests))

            for slice_event in slices:
                for field in (
                    "context_slice_ref",
                    "context_slice_hash",
                    "context_pack_ref",
                    "context_pack_hash",
                    "manifest_ref",
                    "manifest_hash",
                    "model_request_ref",
                    "model_request_hash",
                    "workspace_fingerprint_hash",
                ):
                    self.assertTrue(slice_event.get(field), f"missing {field}")
                # Ensure bound artifact exists in CAS.
                _ = artifact_store.read_bytes(slice_event["context_slice_ref"])


if __name__ == "__main__":
    unittest.main()
