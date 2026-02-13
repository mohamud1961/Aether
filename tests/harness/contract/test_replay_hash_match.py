import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.replay import replay_recorded_output


class TestReplayHashMatch(unittest.TestCase):
    def test_replay_hash_match_and_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")

            event_log.append_event(
                {
                    "event_type": "context_compiler",
                    "step_id": 1,
                    "timestamp": "2026-01-26T00:00:00Z",
                    "cwd": root.as_posix(),
                    "context_pack_hash": "cp_hash",
                    "manifest_hash": "m_hash",
                }
            )

            stdout = store.put_bytes(b"ok", content_type="text/plain")
            stderr = store.put_bytes(b"", content_type="text/plain")
            event_log.append_event(
                {
                    "event_type": "tool_call",
                    "step_id": 2,
                    "timestamp": "2026-01-26T00:00:01Z",
                    "cwd": root.as_posix(),
                    "tool_name": "shell",
                    "tool_args": {"command": ["echo", "ok"]},
                    "exit_code": 0,
                    "stdout_ref": stdout.artifact_id,
                    "stderr_ref": stderr.artifact_id,
                    "artifact_refs": [stdout.artifact_id, stderr.artifact_id],
                }
            )

            outcome_ok = replay_recorded_output(
                events=event_log.events,
                artifact_store=store,
                event_log=event_log,
                expected_context_pack_hash="cp_hash",
                expected_manifest_hash="m_hash",
                timestamp="2026-01-26T00:00:02Z",
                cwd=root.as_posix(),
            )
            self.assertTrue(outcome_ok.ok)
            self.assertIsNone(outcome_ok.mismatch_report_ref)
            self.assertIsNone(outcome_ok.event["termination_reason"])

            outcome_bad = replay_recorded_output(
                events=event_log.events,
                artifact_store=store,
                event_log=event_log,
                expected_context_pack_hash="different",
                expected_manifest_hash="m_hash",
                timestamp="2026-01-26T00:00:03Z",
                cwd=root.as_posix(),
            )
            self.assertFalse(outcome_bad.ok)
            self.assertIsNotNone(outcome_bad.mismatch_report_ref)
            self.assertEqual(outcome_bad.event["termination_reason"], "replay_mismatch_detected")


if __name__ == "__main__":
    unittest.main()
