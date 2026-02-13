import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog
from aether.hash_chain import verify_event_chain
from aether.policy_config import FeatureFlags, PolicyConfig
from aether.session_recovery import SessionRecovery


class TestEventLogResumeContinuity(unittest.TestCase):
    def test_resume_preserves_prev_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"

            first_log = EventLog(log_path)
            first_log.append_event(
                {"event_type": "setup", "step_id": 1, "timestamp": "t1", "cwd": "/"}
            )
            first_log.append_event(
                {"event_type": "act", "step_id": 2, "timestamp": "t2", "cwd": "/"}
            )

            recovery = SessionRecovery(PolicyConfig(feature_flags=FeatureFlags(ff_session_recovery=True)))
            resumed_log = EventLog(log_path)
            recovery.recover_and_hydrate(resumed_log)
            resumed_log.append_event(
                {"event_type": "verify", "step_id": 3, "timestamp": "t3", "cwd": "/"}
            )

            events = EventLog.load_events(log_path)
            self.assertEqual(events[2]["prev_event_hash"], events[1]["event_id"])
            self.assertTrue(verify_event_chain(events)["ok"])


if __name__ == "__main__":
    unittest.main()
