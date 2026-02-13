import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.proceed_gate import ProceedGate


class TestProceedGate(unittest.TestCase):
    def test_allowlist_allows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)
            policy = GovernancePolicy(allowlist=set(), blocklist=set())
            gate = GovernanceGate(policy, event_log)
            proceed_gate = ProceedGate(gate)

            decision = proceed_gate.evaluate(
                argv_prefix_signature=["python", "-m", "unittest"],
                risk_tier="low",
                timestamp="2026-01-28T00:00:00Z",
                cwd="/tmp",
            )

            self.assertTrue(decision.allow)
            self.assertEqual(decision.reason_code, "allowlist")
            self.assertIsNotNone(decision.decision_id)
            self.assertEqual(event_log.events[-1]["event_type"], "governance_decision")

    def test_blocklist_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)
            policy = GovernancePolicy(allowlist=set(), blocklist=set())
            gate = GovernanceGate(policy, event_log)
            proceed_gate = ProceedGate(gate)

            decision = proceed_gate.evaluate(
                argv_prefix_signature=["rm", "-rf", "/"],
                risk_tier="high",
                timestamp="2026-01-28T00:00:00Z",
                cwd="/tmp",
            )

            self.assertFalse(decision.allow)
            self.assertEqual(decision.reason_code, "blocklist")

    def test_signature_mismatch_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)
            policy = GovernancePolicy(allowlist=set(), blocklist=set())
            gate = GovernanceGate(policy, event_log)
            proceed_gate = ProceedGate(gate)

            decision = proceed_gate.evaluate(
                argv_prefix_signature=["python", "-c", "malicious"],
                risk_tier="high",
                timestamp="2026-01-28T00:00:00Z",
                cwd="/tmp",
            )

            self.assertFalse(decision.allow)
            self.assertEqual(decision.reason_code, "signature_mismatch")

    def test_unbound_signature_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)
            policy = GovernancePolicy(allowlist=set(), blocklist=set())
            gate = GovernanceGate(policy, event_log)
            proceed_gate = ProceedGate(gate)

            decision = proceed_gate.evaluate(
                argv_prefix_signature=["python"],
                risk_tier="high",
                timestamp="2026-01-28T00:00:00Z",
                cwd="/tmp",
            )

            self.assertFalse(decision.allow)
            self.assertEqual(decision.reason_code, "unbound_permission_request")


if __name__ == "__main__":
    unittest.main()
