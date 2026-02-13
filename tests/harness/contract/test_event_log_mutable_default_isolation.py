import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog


class TestEventLogMutableDefaultIsolation(unittest.TestCase):
    def test_truncation_defaults_are_not_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log = EventLog(Path(tmpdir) / "events.jsonl")
            first = event_log.append_event(
                {
                    "event_type": "a",
                    "timestamp": "2026-02-06T00:00:00Z",
                    "cwd": "/tmp",
                }
            )
            second = event_log.append_event(
                {
                    "event_type": "b",
                    "timestamp": "2026-02-06T00:00:01Z",
                    "cwd": "/tmp",
                }
            )

            self.assertIsNot(first["truncation"], second["truncation"])


if __name__ == "__main__":
    unittest.main()
