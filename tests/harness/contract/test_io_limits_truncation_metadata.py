import unittest
import tempfile
import shutil
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.policy_config import PolicyConfig, FeatureFlags
from aether.io_limits_adapter import IOLimitsAdapter

class TestIOLimitsTruncationMetadata(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.root = Path(self.tmp_dir)
        self.artifact_store = ArtifactStore(self.root)
        
        # Enable IO Limits
        self.flags = FeatureFlags(ff_io_limits_adapter=True)
        self.policy = PolicyConfig(feature_flags=self.flags)
        
        # Small chunk size to force chunking easily
        self.adapter = IOLimitsAdapter(
            self.artifact_store, 
            self.policy,
                chunk_size_bytes=10, 
            preview_bytes=5
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_truncation_metadata_preserved_in_artifact_response(self):
        data = b"Some data"
        truncation = {"truncated": True, "original_size": 100}
        
        result = self.adapter.process_file_read("test.txt", data, truncation)
        
        # Should be an artifact dict, NOT a string, because even small files 
        # might be upgraded to artifacts if truncation logic requires it?
        # Wait, my implementation returns string for small text files unless I change logic.
        # Let's check implementation behavior:
        # "If truncation metadata is present, we SHOULD treat it as an artifact... if truncation_metadata... pass (go to artifact path)"
        # So yes, it should return a dict.
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "artifact_ref")
        self.assertEqual(result["truncation"], truncation)

    def test_truncation_metadata_ignored_if_ff_disabled(self):
        disabled_policy = PolicyConfig(feature_flags=FeatureFlags(ff_io_limits_adapter=False))
        adapter = IOLimitsAdapter(self.artifact_store, disabled_policy)
        
        data = b"Some data"
        truncation = {"truncated": True}
        
        # Should return string
        result = adapter.process_file_read("test.txt", data, truncation)
        self.assertIsInstance(result, str)
        self.assertEqual(result, "Some data")

    def test_large_file_produces_offsets(self):
        # 10 bytes chunk size, 25 bytes data -> 3 chunks (10, 10, 5)
        data = b"A" * 25
        result = self.adapter.process_file_read("large.txt", data)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "artifact_ref")
        offsets = result["offsets"]
        self.assertEqual(len(offsets), 3)
        self.assertEqual(offsets[0], {"offset": 0, "length": 10})
        self.assertEqual(offsets[1], {"offset": 10, "length": 10})
        self.assertEqual(offsets[2], {"offset": 20, "length": 5})

    def test_binary_file_always_artifact(self):
        # Small binary data, should still be artifact
        data = b"\x00\x01\x02"
        result = self.adapter.process_file_read("binary.bin", data)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "artifact_ref")
        self.assertEqual(result["content_type"], "application/octet-stream")

if __name__ == "__main__":
    unittest.main()
