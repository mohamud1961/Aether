import tempfile
import unittest
from pathlib import Path

from aether.safe_file_ops import SafeFileOps
from aether.path_sandbox import PathSandboxError


class TestSafeFileOps(unittest.TestCase):
    def test_read_before_write_for_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "existing.txt"
            target.write_text("data", encoding="utf-8")

            ops = SafeFileOps(root, enabled=True)
            result = ops.prepare_write(Path("existing.txt"))

            self.assertIn("existing.txt", result.files_read)
            self.assertIn("existing.txt", result.files_written)

    def test_blocks_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ops = SafeFileOps(root, enabled=True)

            with self.assertRaises(PathSandboxError):
                ops.prepare_write(Path("..") / "escape.txt")


if __name__ == "__main__":
    unittest.main()
