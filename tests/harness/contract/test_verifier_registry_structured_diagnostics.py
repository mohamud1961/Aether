import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway, ToolResult
from aether.verifier_plan import VerifierDefinition
from aether.verifier_registry import VerifierRegistry


class TestVerifierRegistryStructuredDiagnostics(unittest.TestCase):
    def test_verifier_result_emits_structured_failed_test_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact_store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            gate = GovernanceGate(GovernancePolicy(allowlist={"verifier"}, blocklist=set()), event_log)
            script = (
                "import sys\n"
                "print('FAILED tests/test_outputs.py::test_recovered_data_completeness - AssertionError: bad value')\n"
                "print('FAILED tests/test_outputs.py::test_wal_was_decrypted - AssertionError: wal missing')\n"
                "print('E       assert 100 == 150')\n"
                "print('E       assert 100 == 150')\n"
                "sys.exit(1)\n"
            )
            gate.evaluate(
                "verifier",
                risk_tier="low",
                timestamp="2026-03-04T00:00:00Z",
                cwd=root.as_posix(),
                tool_args={"command": ["python3", "-c", script]},
            )
            gateway = ToolGateway(
                artifact_store,
                event_log,
                gate,
                root,
                PolicyConfig.from_env(),
            )
            registry = VerifierRegistry(
                [VerifierDefinition(name="verifier", command=["python3", "-c", script])],
                event_log,
            )

            plan = registry.select_plan(
                task_spec={"task": "demo"},
                timestamp="2026-03-04T00:00:01Z",
                cwd=root.as_posix(),
            )
            results = registry.run_plan(
                plan=plan,
                tool_gateway=gateway,
                timestamp="2026-03-04T00:00:02Z",
                cwd=root,
            )

            self.assertEqual(results[0].result, "fail")
            self.assertEqual(results[0].verifier_diagnostics.get("availability"), "available")
            self.assertEqual(results[0].verifier_diagnostics.get("failed_count"), 2)

            stage_b_events = [
                event
                for event in event_log.events
                if event.get("event_type") == "verifier_result" and event.get("verifier_stage") == "B"
            ]
            self.assertEqual(len(stage_b_events), 1)
            diagnostics = stage_b_events[0].get("verifier_diagnostics", {})
            self.assertEqual(diagnostics.get("availability"), "available")
            self.assertEqual(diagnostics.get("source"), "pytest_text")
            failed_names = [item.get("name") for item in diagnostics.get("failed_tests", [])]
            self.assertIn("tests/test_outputs.py::test_recovered_data_completeness", failed_names)
            self.assertIn("tests/test_outputs.py::test_wal_was_decrypted", failed_names)

    def test_verifier_result_fails_closed_when_artifact_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "event_log.jsonl")
            artifact_store = ArtifactStore(root / "artifacts")
            registry = VerifierRegistry(
                [VerifierDefinition(name="verifier", command=["python3", "-c", "raise SystemExit(1)"])],
                event_log,
            )
            gateway = MagicMock()
            gateway.artifact_store = artifact_store
            gateway.execute.return_value = ToolResult(
                exit_code=1,
                stdout_ref="missing_stdout",
                stderr_ref="missing_stderr",
                truncation={"stdout": {"unknown": False}, "stderr": {"unknown": False}},
                duration_ms=5,
                files_read=[],
                files_written=[],
                last_failed_command=None,
                event={"event_id": "evt_missing"},
            )

            plan = registry.select_plan(
                task_spec={"task": "demo"},
                timestamp="2026-03-04T00:10:01Z",
                cwd=root.as_posix(),
            )
            results = registry.run_plan(
                plan=plan,
                tool_gateway=gateway,
                timestamp="2026-03-04T00:10:02Z",
                cwd=root,
            )

            self.assertEqual(results[0].result, "fail")
            diagnostics = results[0].verifier_diagnostics
            self.assertEqual(diagnostics.get("availability"), "unavailable")
            self.assertEqual(diagnostics.get("reason_code"), "artifact_read_error")


if __name__ == "__main__":
    unittest.main()
