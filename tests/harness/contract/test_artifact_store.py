import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.hashing import sha256_hex


class TestArtifactStore(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ArtifactStore(Path(self.temp_dir.name))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_content_addressed_and_preview(self) -> None:
        data = b"hello world"
        artifact = self.store.put_bytes(data, content_type="text/plain")

        self.assertEqual(artifact.artifact_id, sha256_hex(data))
        self.assertEqual(artifact.size_bytes, len(data))
        self.assertIsNotNone(artifact.preview_ref)

        metadata = self.store.get_metadata(artifact.artifact_id)
        self.assertEqual(metadata["artifact_id"], artifact.artifact_id)
        self.assertEqual(metadata["preview_ref"], artifact.preview_ref)

        artifact_repeat = self.store.put_bytes(data, content_type="text/plain")
        self.assertEqual(artifact_repeat.artifact_id, artifact.artifact_id)
        self.assertEqual(self.store.read_bytes(artifact.artifact_id), data)

    def test_offsets_persist_in_metadata(self) -> None:
        data = b"abcdef"
        offsets = [{"offset": 0, "length": 3}, {"offset": 3, "length": 3}]

        artifact = self.store.put_bytes(
            data,
                content_type="text/plain",
            offsets=offsets,
        )

        metadata = self.store.get_metadata(artifact.artifact_id)
        self.assertEqual(metadata["offsets"], offsets)

    def test_invalid_offsets_fail_closed(self) -> None:
        data = b"abcdef"
        invalid_offsets = [{"offset": 4, "length": 4}]
        with self.assertRaises(ValueError):
            self.store.put_bytes(
                data,
                content_type="text/plain",
                offsets=invalid_offsets,
            )

        negative_offsets = [{"offset": -1, "length": 1}]
        with self.assertRaises(ValueError):
            self.store.put_bytes(
                data,
                content_type="text/plain",
                offsets=negative_offsets,
            )
