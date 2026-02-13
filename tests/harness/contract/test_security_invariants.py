import unittest
from unittest import mock
from pathlib import Path
from aether.event_log import compute_event_id
from aether.artifact_store import ArtifactStore

class TestSecurityInvariants(unittest.TestCase):
    def test_event_id_hashing_precision(self) -> None:
        """
        Asserts that event_id depends on content but excludes itself.
        """
        event = {
            "event_type": "test",
            "step_id": 1,
            "timestamp": "2026-01-26T00:00:00Z",
            "cwd": "/tmp",
            "tool_name": "echo",
            "tool_args": {},
            "event_id": "WILL_BE_EXCLUDED",
            "prev_event_hash": "64_ZEROS"
        }
        
        # Hash with placeholders
        h1 = compute_event_id(event)
        
        # Change placeholders - hash should NOT change
        event["event_id"] = "CHANGED"
        event["prev_event_hash"] = "ALSO_CHANGED"
        h2 = compute_event_id(event)
        self.assertEqual(h1, h2, "event_id must exclude itself and prev_event_hash per current spec")
        
        # Change content - hash SHOULD change
        event["tool_name"] = "not_echo"
        h3 = compute_event_id(event)
        self.assertNotEqual(h1, h3, "event_id must be sensitive to content changes")

    def test_artifact_offset_safety(self) -> None:
        """
        Asserts that invalid offsets (bounds, negative) fail closed.
        """
        with unittest.mock.MagicMock() as mock_root:
            store = ArtifactStore(Path("/tmp/fake_store"))
            data = b"hello world" # 11 bytes
            
            # 1. Negative offset
            with self.assertRaisesRegex(ValueError, "non-negative"):
                store.put_bytes(data, content_type="text/plain", offsets=[{"offset": -1, "length": 5}])
            
            # 2. Length exceeds size
            with self.assertRaisesRegex(ValueError, "exceeds artifact size"):
                store.put_bytes(data, content_type="text/plain", offsets=[{"offset": 0, "length": 12}])
            
            # 3. Range exceeds size
            with self.assertRaisesRegex(ValueError, "exceeds artifact size"):
                store.put_bytes(data, content_type="text/plain", offsets=[{"offset": 6, "length": 6}])
            
            # 4. Non-integer values
            with self.assertRaisesRegex(ValueError, "integers"):
                store.put_bytes(data, content_type="text/plain", offsets=[{"offset": "0", "length": 5}]) # type: ignore
if __name__ == "__main__":
    unittest.main()
