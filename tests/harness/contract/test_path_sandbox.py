import tempfile
import unittest
from pathlib import Path

from aether.path_sandbox import PathSandboxError, resolve_sandboxed_path


class TestPathSandbox(unittest.TestCase):
    def test_allows_paths_within_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            allowed = resolve_sandboxed_path(root, Path("nested/file.txt"))
            allowed.relative_to(root.resolve())

            allowed_abs = resolve_sandboxed_path(root, root / "abs.txt")
            self.assertEqual(allowed_abs, (root / "abs.txt").resolve())

    def test_blocks_escape_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            outside_abs = root.parent / "outside.txt"

            with self.assertRaises(PathSandboxError) as absolute_ctx:
                resolve_sandboxed_path(root, outside_abs)
            self.assertEqual(absolute_ctx.exception.reason_code, "absolute_outside_root")

            with self.assertRaises(PathSandboxError) as relative_ctx:
                resolve_sandboxed_path(root, Path(".."))
            self.assertEqual(relative_ctx.exception.reason_code, "relative_escape")


if __name__ == "__main__":
    unittest.main()
