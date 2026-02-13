import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog, REQUIRED_FIELDS, NULL_EVENT_HASH


class TestEventLogBaselineFields(unittest.TestCase):
    def test_required_fields_and_monotonic_step_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "event_log.jsonl"
            event_log = EventLog(log_path)

            event = event_log.append_event(
                {
                    "event_type": "unit_test",
                    "step_id": 1,
                    "timestamp": "2026-01-26T00:00:00Z",
                    "cwd": "/tmp",
                }
            )

            for field in REQUIRED_FIELDS:
                self.assertIn(field, event)
            self.assertEqual(event["prev_event_hash"], NULL_EVENT_HASH)

            with self.assertRaises(ValueError):
                event_log.append_event(
                    {
                        "event_type": "unit_test",
                        "step_id": 1,
                        "timestamp": "2026-01-26T00:00:01Z",
                        "cwd": "/tmp",
                    }
                )
