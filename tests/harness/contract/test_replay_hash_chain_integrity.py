import json
import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.replay import replay_recorded_output


class TestReplayHashChainIntegrity(unittest.TestCase):
    def test_hash_chain_mismatch_fails_closed(self) -> None:
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
            event_log.append_event(
                {
                    "event_type": "unit_test",
                    "step_id": 2,
                    "timestamp": "2026-01-26T00:00:01Z",
                    "cwd": root.as_posix(),
                }
            )

            tampered = [dict(event) for event in event_log.events]
            tampered[1]["prev_event_hash"] = "bad"

            outcome = replay_recorded_output(
                events=tampered,
                artifact_store=store,
                event_log=event_log,
                expected_context_pack_hash="cp_hash",
                expected_manifest_hash="m_hash",
                timestamp="2026-01-26T00:00:02Z",
                cwd=root.as_posix(),
            )
            self.assertFalse(outcome.ok)
            report_bytes = store.read_bytes(outcome.mismatch_report_ref)
            report = json.loads(report_bytes.decode("utf-8"))
            self.assertEqual(report["mismatch_type"], "hash_chain_mismatch")
            self.assertIsNotNone(report["first_bad_step_id"])


if __name__ == "__main__":
    unittest.main()
