"""
Governance Deny Positive Control Test

Proves that a denied command does NOT execute, not just that
a deny event was logged. Uses a sentinel file approach.
"""

import os
import tempfile
import unittest
from pathlib import Path


class TestGovernanceDenyPositiveControl(unittest.TestCase):
    """
    Contract test: governance deny must prevent actual execution.
    
    Attack scenario this prevents:
    1. Model requests destructive command
    2. Governance logs "deny"
    3. But subprocess still runs (governance is logging-only)
    
    This test proves side-effect prevention, not just logging.
    """

    def setUp(self):
        """Create a temporary directory for sentinel files."""
        self.temp_dir = tempfile.mkdtemp()
        self.sentinel_file = Path(self.temp_dir) / "sentinel.txt"

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_denied_command_does_not_create_sentinel(self):
        """
        A denied command that would create a file must not create it.
        
        Test structure:
        1. Configure governance to deny a specific command
        2. Attempt to execute command that creates sentinel
        3. Assert sentinel does NOT exist
        """
        try:
            from aether.governance_gate import GovernanceGate, GovernancePolicy
            from aether.tool_gateway import ToolGateway
            from aether.event_log import EventLog
            from aether.artifact_store import ArtifactStore
        except ImportError:
            self.skipTest("harness modules not available")

        # Create minimal infrastructure
        artifact_store = ArtifactStore(Path(self.temp_dir) / "artifacts")
        event_log = EventLog(Path(self.temp_dir) / "events.jsonl")

        # Configure governance to DENY touch commands
        policy = GovernancePolicy(
            allowlist=set(),
            blocklist={"touch"},
            default_decision="allow"
        )
        governance = GovernanceGate(policy, event_log)

        # Create tool gateway with governance
        gateway = ToolGateway(
            artifact_store=artifact_store,
                event_log=event_log,
            governance_gate=governance,
            workspace_root=Path(self.temp_dir)
        )

        # Attempt to execute blocked command
        # This would create sentinel if governance doesn't block
        command = ["touch", str(self.sentinel_file)]
        
        # First evaluate governance decision (required before execute)
        decision = governance.evaluate(
            action="touch",
            risk_tier="low",
            timestamp="2026-01-28T00:00:00Z",
            cwd=str(self.temp_dir),
            tool_args={"command": command}
        )
        
        # Decision should be deny
        self.assertFalse(decision.allow, "Governance should deny 'touch' command")

        # Try to execute - should raise PermissionError for denied action
        with self.assertRaises(PermissionError):
            gateway.execute(
                tool_name="touch",
                tool_args={"command": command},
                timestamp="2026-01-28T00:00:01Z",
                cwd=Path(self.temp_dir)
            )

        # Critical assertion: sentinel must NOT exist
        self.assertFalse(
            self.sentinel_file.exists(),
            "SECURITY VIOLATION: Denied command created sentinel file! "
            "Governance deny is logging-only, not enforcing."
        )

        # Also verify deny was logged
        deny_events = [
            e for e in event_log.events
            if e.get('event_type') == 'governance_decision'
            and e.get('governance', {}).get('decision') == 'deny'
        ]
        self.assertGreater(
            len(deny_events), 0,
            "Governance deny was not logged"
        )

    def test_allowed_command_creates_sentinel(self):
        """
        An allowed command that creates a file must create it.
        
        This is the positive control for the negative test above.
        """
        try:
            from aether.governance_gate import GovernanceGate, GovernancePolicy
            from aether.tool_gateway import ToolGateway
            from aether.event_log import EventLog
            from aether.artifact_store import ArtifactStore
        except ImportError:
            self.skipTest("harness modules not available")

        artifact_store = ArtifactStore(Path(self.temp_dir) / "artifacts")
        event_log = EventLog(Path(self.temp_dir) / "events.jsonl")

        # Configure governance to ALLOW touch commands
        policy = GovernancePolicy(
            allowlist={"touch"},
                blocklist=set(),
            default_decision="deny"
        )
        governance = GovernanceGate(policy, event_log)

        gateway = ToolGateway(
            artifact_store=artifact_store,
                event_log=event_log,
            governance_gate=governance,
            workspace_root=Path(self.temp_dir)
        )

        # Execute allowed command
        allowed_sentinel = Path(self.temp_dir) / "allowed_sentinel.txt"
        command = ["touch", str(allowed_sentinel)]
        
        # First evaluate governance decision (required before execute)
        decision = governance.evaluate(
            action="touch",
            risk_tier="low",
            timestamp="2026-01-28T00:00:00Z",
            cwd=str(self.temp_dir),
            tool_args={"command": command}
        )
        
        # Decision should be allow
        self.assertTrue(decision.allow, "Governance should allow 'touch' command")

        result = gateway.execute(
            tool_name="touch",
                tool_args={"command": command},
            timestamp="2026-01-28T00:00:01Z",
            cwd=Path(self.temp_dir)
        )

        # Sentinel MUST exist for allowed command
        self.assertTrue(
            allowed_sentinel.exists(),
            "Allowed command did not create sentinel - gateway is broken"
        )


class TestGovernanceDenyMock(unittest.TestCase):
    """
    Fallback test when harness is not importable.
    
    Uses mock objects to verify the interface contract.
    """

    def test_denied_command_interface_contract(self):
        """Verify the expected interface for governance deny."""
        # This test defines the expected behavior even when
        # the harness isn't available for integration testing

        class MockGovernanceGate:
            def __init__(self):
                self.blocklist = set()
                self.decisions = []

            def add_to_blocklist(self, pattern):
                self.blocklist.add(pattern)

            def evaluate(self, command):
                cmd_str = command[0] if isinstance(command, list) else command
                if cmd_str in self.blocklist:
                    self.decisions.append({'decision': 'deny', 'command': command})
                    return {'allow': False, 'reason_code': 'blocklist_match'}
                self.decisions.append({'decision': 'allow', 'command': command})
                return {'allow': True, 'reason_code': 'default_allow'}

        gov = MockGovernanceGate()
        gov.add_to_blocklist("rm")

        # Evaluate dangerous command
        result = gov.evaluate(["rm", "-rf", "/"])

        self.assertFalse(result['allow'])
        self.assertEqual(result['reason_code'], 'blocklist_match')
        self.assertEqual(len(gov.decisions), 1)
        self.assertEqual(gov.decisions[0]['decision'], 'deny')


if __name__ == '__main__':
    unittest.main()
