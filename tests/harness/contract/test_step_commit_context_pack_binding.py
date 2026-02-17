import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog


class TestStepCommitContextPackBinding(unittest.TestCase):
    def test_step_commit_valid_with_context_pack_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "events.jsonl")

            event = event_log.append_event(
                {
                    "event_type": "STEP_COMMIT",
                    "timestamp": "2026-02-14T00:00:00Z",
                    "cwd": root.as_posix(),
                    "workspace_hash": "workspace-hash",
                    "context_pack_ref": "cp-ref",
                }
            )

            self.assertTrue(event.get("valid"))
            self.assertEqual(event.get("commit_status"), "valid")
            self.assertEqual(event.get("missing_components"), [])


if __name__ == "__main__":
    unittest.main()
