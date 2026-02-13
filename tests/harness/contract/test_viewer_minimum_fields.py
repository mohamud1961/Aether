import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog
from aether.viewer import build_view


class TestViewerMinimumFields(unittest.TestCase):
    def test_viewer_includes_core_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log = EventLog(Path(tmpdir) / "event_log.jsonl")
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
                    "event_type": "tool_call",
                    "step_id": 2,
                    "timestamp": "2026-01-26T00:00:01Z",
                    "cwd": "/tmp",
                    "tool_name": "shell",
                    "tool_args": {"command": ["echo", "ok"]},
                    "exit_code": 0,
                    "stdout_ref": "out",
                    "stderr_ref": "err",
                    "artifact_refs": ["out", "err"],
                }
            )

            view = build_view(event_log.events)
            channel_a = view["channel_a"]
            self.assertEqual(len(channel_a), 2)
            for entry in channel_a:
                self.assertIsNotNone(entry["step_id"])
                self.assertIsNotNone(entry["event_id"])
                self.assertIsNotNone(entry["prev_event_hash"])

            unit_entry = channel_a[0]
            self.assertIsNone(unit_entry["tool_name"])
            self.assertIsNone(unit_entry["tool_args"])
            self.assertIsNone(unit_entry["exit_code"])
            self.assertIsNone(unit_entry["completion_signals"])

            tool_entry = channel_a[1]
            self.assertEqual(tool_entry["tool_name"], "shell")
            self.assertEqual(tool_entry["stdout_ref"], "out")
            self.assertEqual(tool_entry["stderr_ref"], "err")

            self.assertTrue(view["hash_chain_report"]["ok"])


if __name__ == "__main__":
    unittest.main()
