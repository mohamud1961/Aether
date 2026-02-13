import tempfile
import unittest
from pathlib import Path

from aether.workspace_fingerprint import compute_workspace_fingerprint, has_fingerprint_delta


class TestWorkspaceFingerprint(unittest.TestCase):
    def test_deterministic_ordering_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "b.txt").write_text("b", encoding="utf-8")
            (root / "a.txt").write_text("a", encoding="utf-8")

            first = compute_workspace_fingerprint(root)
            second = compute_workspace_fingerprint(root)

            self.assertEqual(first.fingerprint_hash, second.fingerprint_hash)
            ordered_paths = [entry.path for entry in first.file_hashes]
            self.assertEqual(ordered_paths, ["a.txt", "b.txt"])

    def test_unchanged_workspace_same_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("stable", encoding="utf-8")

            first = compute_workspace_fingerprint(root)
            second = compute_workspace_fingerprint(root)

            self.assertEqual(first.fingerprint_hash, second.fingerprint_hash)

    def test_fingerprint_delta_tracks_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("stable", encoding="utf-8")

            first = compute_workspace_fingerprint(root)
            second = compute_workspace_fingerprint(root, previous_fingerprint=first)
            self.assertEqual(second.diff_summary["fingerprint_delta"], 0)
            self.assertTrue(second.diff_summary["no_file_diffs"])
            self.assertFalse(has_fingerprint_delta(second.diff_summary))

            (root / "file.txt").write_text("changed", encoding="utf-8")
            third = compute_workspace_fingerprint(root, previous_fingerprint=second)
            self.assertGreater(third.diff_summary["fingerprint_delta"], 0)
            self.assertFalse(third.diff_summary["no_file_diffs"])
            self.assertTrue(has_fingerprint_delta(third.diff_summary))
