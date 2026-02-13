import unittest
import tempfile
import shutil
import json
from pathlib import Path

from aether.event_log import EventLog
from aether.policy_config import PolicyConfig, FeatureFlags
from aether.session_recovery import SessionRecovery, IntegrityError

class TestSessionRecoveryIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.root = Path(self.tmp_dir)
        self.policy = PolicyConfig(feature_flags=FeatureFlags(ff_session_recovery=True))
        self.recovery = SessionRecovery(self.policy)
        self.log_path = self.root / "events.jsonl"
        self.event_log = EventLog(self.log_path)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_recover_valid_chain(self):
        # Create valid chain
        self.event_log.append_event({"event_type": "setup", "step_id": 1, "timestamp": "t1", "cwd": "/"})
        self.event_log.append_event({"event_type": "action", "step_id": 2, "timestamp": "t2", "cwd": "/", 
                                     "workspace_fingerprint_hash": "fp1"})
        
        result = self.recovery.recover(self.log_path)
        
        self.assertEqual(len(result.events), 2)
        self.assertEqual(result.last_step_id, 2)
        self.assertEqual(result.last_fingerprint_hash, "fp1")

    def test_recover_invalid_chain_raises(self):
        # Create valid chain
        self.event_log.append_event({"event_type": "setup", "step_id": 1, "timestamp": "t1", "cwd": "/"})
        self.event_log.append_event({"event_type": "action", "step_id": 2, "timestamp": "t2", "cwd": "/"})
        
        # Tamper with file directly
        lines = self.log_path.read_text().splitlines()
        e1 = json.loads(lines[0])
        e1["timestamp"] = "tampered"
        
        with self.log_path.open("w") as f:
            f.write(json.dumps(e1) + "\n")
            f.write(lines[1] + "\n")
            
        with self.assertRaises(IntegrityError) as cm:
            self.recovery.recover(self.log_path)
            
        self.assertIn("event_id_mismatch", str(cm.exception))

    def test_missing_file_returns_empty(self):
        missing = self.root / "missing.jsonl"
        result = self.recovery.recover(missing)
        self.assertEqual(len(result.events), 0)
        self.assertEqual(result.last_step_id, 0)

if __name__ == "__main__":
    unittest.main()
