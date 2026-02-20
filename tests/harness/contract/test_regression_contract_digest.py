import json
import tempfile
import unittest
from pathlib import Path

from aether.evals.frugal_evals.context_dump import dump_context_diagnostics
from aether.agent_runner import Agentrunner, TaskSpec
from aether.artifact_store import ArtifactStore
from aether.claude_adapter import MockClaudeAdapter
from aether.control_plane import ControlPlane
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway
from aether.verifier_registry import VerifierRegistry


class TestND2RegressionContractDigest(unittest.TestCase):
    def test_compiled_context_includes_completion_contract_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            workspace = run_dir / "workspace"
            workspace.mkdir()

            event_log = EventLog(run_dir / "event_log.jsonl")
            artifact_store = ArtifactStore(run_dir / "artifacts")
            policy = PolicyConfig.from_env()
            governance = GovernanceGate(
                GovernancePolicy(allowlist={"run", "verifier"}, blocklist=set(), default_decision="deny"),
                event_log,
            )
            gateway = ToolGateway(artifact_store, event_log, governance, workspace, policy)
            adapter = MockClaudeAdapter(
                responses=[
                    {
                        "content": [{"type": "text", "text": "done"}],
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

            runner.run_task(TaskSpec(prompt="nd2 contract digest regression", workspace_root=workspace, max_steps=1))

            max_step_id = max(int(event.get("step_id", 0)) for event in event_log.events)
            diagnostic_paths = dump_context_diagnostics(
                run_dir,
                max_steps=max_step_id + 1,
                out_dir=run_dir / "diag",
            )
            diagnostic = json.loads(Path(diagnostic_paths["context_diagnostic_path"]).read_text(encoding="utf-8"))
            compiled_steps = [step for step in diagnostic["steps"] if step.get("has_compiled_context")]

            self.assertGreaterEqual(len(compiled_steps), 1)
            first_compiled = next(
                step
                for step in compiled_steps
                if any(layer["name"] == "CONTRACTS" and layer["item_count"] > 0 for layer in step["layers"])
            )
            contracts_layer = next(layer for layer in first_compiled["layers"] if layer["name"] == "CONTRACTS")
            self.assertGreater(contracts_layer["item_count"], 0)
            completion_digest_items = [
                item
                for item in contracts_layer["items"]
                if isinstance(item.get("source_ref"), str)
                and "completion_contract_digest" in item["source_ref"]
            ]
            self.assertGreaterEqual(len(completion_digest_items), 1)


if __name__ == "__main__":
    unittest.main()
