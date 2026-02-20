import tempfile
import unittest
from pathlib import Path

from aether.evals.frugal_evals.episodes import extract_episodes_from_runs
from aether.agent_runner import Agentrunner, TaskSpec
from aether.artifact_store import ArtifactStore
from aether.claude_adapter import MockClaudeAdapter
from aether.control_plane import ControlPlane
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway
from aether.verifier_registry import VerifierRegistry


def _tool_use(command: list[str], call_id: str) -> dict:
    return {
        "content": [{"type": "tool_use", "id": call_id, "name": "run", "input": {"command": command}}],
        "stop_reason": "tool_use",
        "usage": {},
    }


class TestND2RegressionShellOperatorRetry(unittest.TestCase):
    def test_shell_operator_spiral_is_collapsed_to_retry_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            run_dir = runs_root / "shell_spiral_20260214_000001"
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True)

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
                    _tool_use(["cat", ">", "a.txt"], "call_1"),
                    _tool_use(["cat", ">", "b.txt"], "call_2"),
                    _tool_use(["echo", "x", ">", "c.txt"], "call_3"),
                    _tool_use(["printf", "y", ">", "d.txt"], "call_4"),
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
            runner.run_task(
                TaskSpec(
                    prompt="trigger repeated shell-operator denials",
                    workspace_root=workspace,
                    max_steps=4,
                )
            )

            episodes = extract_episodes_from_runs(runs_root).episodes
            deny_decision_episodes = [ep for ep in episodes if ep.episode_type == "decision_tool_deny"]
            retry_denied_events = [event for event in event_log.events if event.get("event_type") == "RETRY_DENIED"]

            self.assertEqual(len(deny_decision_episodes), 1)
            self.assertGreaterEqual(len(retry_denied_events), 1)


if __name__ == "__main__":
    unittest.main()
