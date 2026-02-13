import tempfile
import unittest
from pathlib import Path

from aether.canonical_workdir import CanonicalWorkdirError, canonicalize_cwd


class TestCanonicalWorkdir(unittest.TestCase):
    def test_canonicalizes_within_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "subdir").mkdir()

            resolved = canonicalize_cwd(root, Path("subdir"))
            self.assertEqual(resolved, (root / "subdir").resolve())

            resolved_root = canonicalize_cwd(root, root)
            self.assertEqual(resolved_root, root.resolve())

    def test_blocks_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            outside = root.parent

            with self.assertRaises(CanonicalWorkdirError):
                canonicalize_cwd(root, outside)

            with self.assertRaises(CanonicalWorkdirError):
                canonicalize_cwd(root, Path(".."))


if __name__ == "__main__":
    unittest.main()
