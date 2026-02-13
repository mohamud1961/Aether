"""
Contract test: recovery_candidate field.

Proves:
- recovery_candidate is null by default
- recovery_candidate appears in all events
- Field is part of schema enforcement
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from aether.event_log import EventLog, REQUIRED_FIELDS, DEFAULT_FIELDS


class TestRecoveryCandidateEmitted(unittest.TestCase):
    """Contract tests for recovery_candidate field."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.root = Path(self.tmp_dir)
        self.log_path = self.root / "events.jsonl"
        self.event_log = EventLog(self.log_path)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_recovery_candidate_in_required_fields(self):
        """recovery_candidate must be in REQUIRED_FIELDS schema."""
        self.assertIn("recovery_candidate", REQUIRED_FIELDS)

    def test_recovery_candidate_default_is_none(self):
        """recovery_candidate defaults to None."""
        self.assertIn("recovery_candidate", DEFAULT_FIELDS)
        self.assertIsNone(DEFAULT_FIELDS["recovery_candidate"])

    def test_event_includes_recovery_candidate_null(self):
        """Normal events have recovery_candidate=null."""
        event = self.event_log.append_event({
            "event_type": "tool_call",
            "step_id": 1,
            "timestamp": "2026-01-30T09:00:00Z",
            "cwd": "/workspace",
        })

        self.assertIn("recovery_candidate", event)
        self.assertIsNone(event["recovery_candidate"])

    def test_event_can_set_recovery_candidate_true(self):
        """Events can explicitly set recovery_candidate=True."""
        event = self.event_log.append_event({
            "event_type": "recovery_checkpoint",
            "step_id": 1,
            "timestamp": "2026-01-30T09:00:00Z",
            "cwd": "/workspace",
            "recovery_candidate": True,
        })

        self.assertIn("recovery_candidate", event)
        self.assertTrue(event["recovery_candidate"])


if __name__ == "__main__":
    unittest.main()
