import unittest
import shutil
import tempfile
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.capability_adapter import CapabilityAdapter

class TestNpmIgnoreScripts(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir)
        self.artifacts = self.root / "artifacts"
        self.store = ArtifactStore(self.artifacts)
        self.adapter = CapabilityAdapter(self.store, self.root)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_npm_plan_has_ignore_scripts(self):
        stderr = "Error: Cannot find module 'left-pad'\n"
        ref = self.store.put_bytes(stderr.encode("utf-8"), content_type="text/plain").artifact_id
        
        result = self.adapter.detect_and_plan(
            tool_name="node", exit_code=1, stderr_ref=ref, truncation={},
                tool_args={"command": ["node", "index.js"]}
        )
        
        plan = result.install_plan
        self.assertEqual(plan.manager, "npm")
        self.assertIn("--ignore-scripts", plan.install_command)
        self.assertIn("--no-save", plan.install_command)
        self.assertIn("--no-audit", plan.install_command)
        self.assertIn("--no-fund", plan.install_command)

if __name__ == "__main__":
    unittest.main()
