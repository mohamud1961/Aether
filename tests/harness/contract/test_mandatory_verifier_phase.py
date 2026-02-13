import subprocess
import tempfile
import unittest
from pathlib import Path

from aether.control_plane import ControlPlane
from aether.event_log import EventLog
from aether.workspace_fingerprint import compute_workspace_fingerprint, has_fingerprint_delta


class TestMandatoryVerifierPhase(unittest.TestCase):
    def test_ls_does_not_set_dirty_and_allows_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "baseline.txt").write_text("stable", encoding="utf-8")

            first = compute_workspace_fingerprint(root)
            subprocess.run(["ls"], cwd=root, check=True)
            second = compute_workspace_fingerprint(
                root,
                previous_fingerprint=first,
                last_verified_hash=first.fingerprint_hash,
            )

            dirty = has_fingerprint_delta(second.diff_summary)
            self.assertFalse(dirty)

            event_log = EventLog(root / "event_log.jsonl")
            control_plane = ControlPlane(event_log)
            outcome = control_plane.transition(
                current_state="Implement",
                requested_state="Review",
                dirty_since_last_verify=dirty,
                verifier_result=None,
                workspace_fingerprint_hash=second.fingerprint_hash,
                last_verified_fingerprint_hash=first.fingerprint_hash,
                verifier_run=False,
                completion_signals=[{"type": "completion"}],
                files_written_count=0,
                verification_hint_detected=False,
                timestamp="2026-02-22T00:00:00Z",
                cwd=root.as_posix(),
            )

            self.assertEqual(outcome.next_state, "Review")
            self.assertEqual(outcome.triggers_fired, [])

    def test_touch_sets_dirty_and_requires_verify_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            first = compute_workspace_fingerprint(root)
            subprocess.run(["touch", "file.txt"], cwd=root, check=True)
            second = compute_workspace_fingerprint(
                root,
                previous_fingerprint=first,
                last_verified_hash=first.fingerprint_hash,
            )

            dirty = has_fingerprint_delta(second.diff_summary)
            self.assertTrue(dirty)

            event_log = EventLog(root / "event_log.jsonl")
            control_plane = ControlPlane(event_log)

            to_verify = control_plane.transition(
                current_state="Implement",
                requested_state="Review",
                dirty_since_last_verify=dirty,
                verifier_result=None,
                workspace_fingerprint_hash=second.fingerprint_hash,
                last_verified_fingerprint_hash=first.fingerprint_hash,
                verifier_run=False,
                completion_signals=[{"type": "completion"}],
                files_written_count=1,
                verification_hint_detected=False,
                timestamp="2026-02-22T00:00:00Z",
                cwd=root.as_posix(),
            )
            self.assertEqual(to_verify.next_state, "Verify")
            self.assertIn("dirty_since_last_verify", to_verify.triggers_fired)

            to_review = control_plane.transition(
                current_state="Verify",
                requested_state="Review",
                dirty_since_last_verify=False,
                verifier_result="pass",
                workspace_fingerprint_hash=second.fingerprint_hash,
                last_verified_fingerprint_hash=second.fingerprint_hash,
                verifier_run=True,
                completion_signals=[{"type": "completion"}],
                files_written_count=1,
                verification_hint_detected=False,
                timestamp="2026-02-22T00:00:01Z",
                cwd=root.as_posix(),
            )
            self.assertEqual(to_review.next_state, "Review")


if __name__ == "__main__":
    unittest.main()
