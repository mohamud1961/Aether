import tempfile
import unittest
from pathlib import Path

from aether.control_plane import ControlPlane
from aether.event_log import EventLog


class TestControlPlaneStateOrdering(unittest.TestCase):
    def test_state_transitions_logged_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "event_log.jsonl")
            control_plane = ControlPlane(event_log)

            control_plane.transition(
                current_state="SETUP",
                requested_state="WORK",
                dirty_since_last_verify=False,
                verifier_result=None,
                workspace_fingerprint_hash="fp1",
                last_verified_fingerprint_hash="fp1",
                timestamp="2026-01-26T00:00:00Z",
                cwd=root.as_posix(),
            )
            control_plane.transition(
                current_state="WORK",
                requested_state="CHECK_TRIGGER",
                dirty_since_last_verify=False,
                verifier_result=None,
                workspace_fingerprint_hash="fp1",
                last_verified_fingerprint_hash="fp1",
                timestamp="2026-01-26T00:00:01Z",
                cwd=root.as_posix(),
            )

            self.assertEqual(len(event_log.events), 2)
            self.assertLess(event_log.events[0]["step_id"], event_log.events[1]["step_id"])
            self.assertEqual(event_log.events[0]["event_type"], "state_transition")


if __name__ == "__main__":
    unittest.main()
