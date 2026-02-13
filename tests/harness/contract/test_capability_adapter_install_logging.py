import unittest
import shutil
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.tool_gateway import ToolGateway
from aether.capability_adapter import CapabilityAdapter

class TestCapabilityAdapterInstallLogging(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir)
        self.artifacts = self.root / "artifacts"
        self.event_log_path = self.root / "events.jsonl"
        self.store = ArtifactStore(self.artifacts)
        self.event_log = EventLog(self.event_log_path)
        
        # Policy allows pip install prefixes
        self.policy = GovernancePolicy(
            allowlist=[
                ("python3", "-m", "pip", "install", "--target"),
            ],
            blocklist=[]
        )
        self.gate = GovernanceGate(self.policy, self.event_log)
        
        self.gateway = ToolGateway(
            self.store,
            self.event_log,
            self.gate,
            self.root,
            # Mock runner to simulate success
            subprocess_runner=MagicMock(return_value=MagicMock(
                returncode=0, stdout=b"OK", stderr=b""
            ))
        )
        self.adapter = CapabilityAdapter(self.store, self.root)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_install_plan_execution_logging(self):
        # 1. Generate a plan directly
        stderr = "ModuleNotFoundError: No module named 'PIL'\n"
        sys_stderr_ref = self.store.put_bytes(stderr.encode("utf-8"), content_type="text/plain").artifact_id
        
        detection = self.adapter.detect_and_plan(
            tool_name="python", exit_code=1, stderr_ref=sys_stderr_ref, truncation={},
                tool_args={"command": ["python", "script.py"]}
        )
        self.assertTrue(detection.missing_dependency)
        plan = detection.install_plan
        
        # 2. Execute plan via ToolGateway
        self.gate.record_decision(
            action="run", allow=True, reason_code="test",
                risk_tier="low", timestamp="2026-01-28T00:00:00Z", cwd=str(self.root),
                tool_args={"command": plan.install_command}
        )
        result = self.gateway.execute(
            tool_name="run",
                tool_args={"command": plan.install_command},
            timestamp="2026-01-28T00:00:00Z",
            cwd=self.root
        )
        
        # 3. Verify execution success
        self.assertEqual(result.exit_code, 0)
        
        # 4. Verify log event
        events = self.event_log.events
        # We expect a tool_call event for the install
        # event[0] might be governance decision? No, GovernanceGate writes to same event log?
        # Yes, GovernanceGate writes permission_request/decision.
        # Let's find the tool_call
        tool_cal_events = [e for e in events if e["event_type"] == "tool_call"]
        self.assertEqual(len(tool_cal_events), 1)
        install_event = tool_cal_events[0]
        
        # Check command
        cmd = install_event["tool_args"]["command"]
        self.assertEqual(cmd, plan.install_command)
        
        # Check artifacts present
        self.assertTrue(len(install_event["artifact_refs"]) >= 2) # stdout, stderr
        self.assertIsNotNone(install_event["stdout_ref"])
        self.assertIsNotNone(install_event["stderr_ref"])

if __name__ == "__main__":
    unittest.main()
