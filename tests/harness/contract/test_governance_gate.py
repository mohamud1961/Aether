import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy


class TestGovernanceGate(unittest.TestCase):
    def test_blocklist_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)
            policy = GovernancePolicy(
                allowlist=set(),
                blocklist={"rm"},
                default_decision="allow",
            )
            gate = GovernanceGate(policy, event_log)
            decision = gate.evaluate(
                action="rm",
                risk_tier="high",
                timestamp="2026-01-26T00:00:00Z",
                cwd="/tmp",
                tool_args={"command": ["rm", "-rf", "tmp"]},
            )
            self.assertFalse(decision.allow)
            self.assertEqual(decision.reason_code, "blocklist")

    def test_allowlist_allows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)
            policy = GovernancePolicy(
                allowlist={"ls"},
                blocklist=set(),
                default_decision="deny",
            )
            gate = GovernanceGate(policy, event_log)
            decision = gate.evaluate(
                action="ls",
                risk_tier="low",
                timestamp="2026-01-26T00:00:00Z",
                cwd="/tmp",
                tool_args={"command": ["ls"]},
            )
            self.assertTrue(decision.allow)
            self.assertEqual(decision.reason_code, "allowlist")

    def test_governance_decision_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)
            policy = GovernancePolicy(allowlist=set(), blocklist=set(), default_decision="allow")
            gate = GovernanceGate(policy, event_log)
            
            gate.evaluate(
                action="echo",
                risk_tier="low",
                timestamp="2026-01-26T00:00:00Z",
                cwd="/tmp",
                tool_args={"command": ["echo", "ok"]},
            )
            
            events = event_log.load_events(log_path)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "governance_decision")
            self.assertEqual(events[0]["governance"]["decision"], "allow")
            self.assertEqual(events[0]["governance"]["reason_code"], "default_allow")
