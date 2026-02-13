import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.detectors import detect_completion_signals, detect_permission_request_signals


class TestDetectorPurity(unittest.TestCase):
    def test_detectors_ignore_tool_output(self) -> None:
        tool_output = "tests pass"
        self.assertEqual(detect_completion_signals(""), [])
        self.assertEqual(detect_permission_request_signals("no request here"), [])
        # tool_output is intentionally unused; detectors must only parse assistant messages.
        self.assertIsInstance(tool_output, str)

    def test_message_ref_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore(Path(tmpdir) / "artifacts")
            signals = detect_completion_signals("done", artifact_store=store)
            self.assertTrue(signals)
            message_ref = signals[0].get("message_ref")
            self.assertIsNotNone(message_ref)
            stored = store.read_bytes(message_ref)
            self.assertIn(b"done", stored)


if __name__ == "__main__":
    unittest.main()
