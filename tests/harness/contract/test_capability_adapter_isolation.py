import unittest
import shutil
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.tool_gateway import ToolGateway
from aether.capability_adapter import CapabilityAdapter

class TestCapabilityAdapterIsolation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir).resolve() # Resolve to handle symlinks on Mac
        self.artifacts = self.root / "artifacts"
        self.store = ArtifactStore(self.artifacts)
        self.event_log = EventLog(self.root / "events.jsonl")
        self.gate = GovernanceGate(GovernancePolicy(allowlist=[], blocklist=[]), self.event_log)
        
        self.runner_mock = MagicMock(return_value=MagicMock(
            returncode=0, stdout=b"", stderr=b""
        ))
        self.gateway = ToolGateway(
            self.store,
            self.event_log,
            self.gate,
            self.root,
                subprocess_runner=self.runner_mock
        )
        self.adapter = CapabilityAdapter(self.store, self.root)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_tool_gateway_injects_pythonpath(self):
        # 1. Create .harness_deps/python
        deps_dir = self.root / ".harness_deps" / "python"
        deps_dir.mkdir(parents=True)
        
        # 2. Execute a command with env
        self.gate.record_decision(
            action="run", allow=True, reason_code="test",
                risk_tier="low", timestamp="2026-01-28T00:00:00Z", cwd=str(self.root),
                tool_args={"command": ["echo", "test"]}
        )
        self.gateway.execute(
            tool_name="run",
                tool_args={"command": ["echo", "test"]},
            timestamp="2026-01-28T00:00:00Z",
            cwd=self.root,
            env={"EXISTING": "1"}
        )
        
        # 3. Assert runner called with injected PYTHONPATH
        # runner_mock.call_args[1] is kwargs, env is there
        call_kwargs = self.runner_mock.call_args[1]
        env_passed = call_kwargs["env"]
        
        self.assertIn("PYTHONPATH", env_passed)
        self.assertTrue(env_passed["PYTHONPATH"].startswith(str(deps_dir)))
        self.assertEqual(env_passed["EXISTING"], "1")

    def test_tool_gateway_does_not_inject_if_missing(self):
        # No .harness_deps dir
        self.gate.record_decision(
            action="run", allow=True, reason_code="test",
                risk_tier="low", timestamp="2026-01-28T00:00:00Z", cwd=str(self.root),
                tool_args={"command": ["echo", "test"]}
        )
        self.gateway.execute(
            tool_name="run",
                tool_args={"command": ["echo", "test"]},
            timestamp="2026-01-28T00:00:00Z",
            cwd=self.root,
            env={}
        )
        
        call_kwargs = self.runner_mock.call_args[1]
        env_passed = call_kwargs["env"]
        self.assertNotIn("PYTHONPATH", env_passed)

    def test_install_plan_uses_target_flag(self):
        # Check plan generation logic for isolation
        stderr = "ModuleNotFoundError: No module named 'PIL'\n"
        ref = self.store.put_bytes(stderr.encode("utf-8"), content_type="text/plain").artifact_id
        
        result = self.adapter.detect_and_plan(
            tool_name="python", exit_code=1, stderr_ref=ref, truncation={},
                tool_args={"command": ["python", "app.py"]}
        )
        
        plan = result.install_plan
        self.assertTrue(plan.is_workspace_scoped)
        cmd = " ".join(plan.install_command)
        self.assertIn("--target", cmd)
        self.assertIn(str(self.root / ".harness_deps" / "python"), cmd)
        self.assertNotIn("--user", cmd)

if __name__ == "__main__":
    unittest.main()
