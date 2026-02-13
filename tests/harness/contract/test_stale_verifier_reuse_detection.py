import tempfile
import unittest
from pathlib import Path

from aether.control_plane import ControlPlane, last_verified_fingerprint_hash
from aether.event_log import EventLog


class TestStaleVerifierReuseDetection(unittest.TestCase):
    def test_stale_verifier_reuse_triggers_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "event_log.jsonl")
            event_log.append_event(
                {
                    "event_type": "verifier_result",
                    "step_id": 1,
                    "timestamp": "2026-01-26T00:00:00Z",
                    "cwd": root.as_posix(),
                    "verifier_run": True,
                    "verifier_result": "pass",
                    "workspace_fingerprint_hash": "fp1",
                }
            )

            last_verified = last_verified_fingerprint_hash(event_log.events)
            control_plane = ControlPlane(event_log)
            outcome = control_plane.transition(
                current_state="CHECK_TRIGGER",
                requested_state="COMMIT",
                dirty_since_last_verify=False,
                verifier_result="pass",
                workspace_fingerprint_hash="fp2",
                last_verified_fingerprint_hash=last_verified,
                timestamp="2026-01-26T00:00:01Z",
                cwd=root.as_posix(),
            )
            self.assertEqual(outcome.next_state, "VERIFY")
            self.assertIn("fingerprint_mismatch", outcome.triggers_fired)


if __name__ == "__main__":
    unittest.main()
