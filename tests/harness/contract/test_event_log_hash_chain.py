import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.hash_chain import verify_event_chain, compute_event_id
from aether.hashing import hash_canonical_json, sha256_hex


class TestEventLogHashChain(unittest.TestCase):
    def test_canonical_json_hashing(self) -> None:
        payload = {"b": 2, "a": 1}
        expected = sha256_hex(b"{\"a\":1,\"b\":2}")
        self.assertEqual(hash_canonical_json(payload), expected)

    def test_hash_chain_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            store = ArtifactStore(Path(tmpdir) / "artifacts")
            event_log = EventLog(log_path)

            event_log.append_event(
                {
                    "event_type": "unit_test",
                    "step_id": 1,
                    "timestamp": "2026-01-26T00:00:00Z",
                    "cwd": "/tmp",
                }
            )
            event_log.append_event(
                {
                    "event_type": "unit_test",
                    "step_id": 2,
                    "timestamp": "2026-01-26T00:00:01Z",
                    "cwd": "/tmp",
                }
            )

            report = verify_event_chain(event_log.events)
            self.assertTrue(report["ok"])

            tampered = list(event_log.events)
            tampered[0] = dict(tampered[0])
            tampered[0]["event_type"] = "tampered"

            tampered_report = verify_event_chain(tampered)
            self.assertFalse(tampered_report["ok"])
            self.assertEqual(tampered_report["reason_code"], "event_id_mismatch")

            result = event_log.append_hash_chain_report(
                store,
                timestamp="2026-01-26T00:00:02Z",
                cwd="/tmp",
            )
            self.assertIn(result["artifact_id"], result["event"]["artifact_refs"])

    def test_event_id_excludes_hash_fields(self) -> None:
        base_event = {
            "event_type": "unit_test",
            "step_id": 1,
            "timestamp": "2026-01-26T00:00:00Z",
            "cwd": "/tmp",
        }
        base_id = compute_event_id(base_event)

        mutated = dict(base_event)
        mutated["event_id"] = "bad"
        mutated["prev_event_hash"] = "bad"
        self.assertEqual(compute_event_id(mutated), base_id)

        reordered = {"cwd": "/tmp", "timestamp": "2026-01-26T00:00:00Z", "step_id": 1, "event_type": "unit_test"}
        self.assertEqual(compute_event_id(reordered), base_id)
