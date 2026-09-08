#!/usr/bin/env python3
"""Verify the public release from tracked files only, without untracked workspace state."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], cwd: Path) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    files = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    with tempfile.TemporaryDirectory(prefix="aether-public-cold-") as td:
        cold = Path(td)
        for rel in files:
            src = ROOT / rel
            dst = cold / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        # Recreate only the publication index; no original .git directory or untracked files are copied.
        run(["git", "init", "-q"], cold)
        run(["git", "add", "."], cold)
        run([sys.executable, "tools/check_public_release.py"], cold)
        run([sys.executable, "tools/check_production_surface.py"], cold)
        run([sys.executable, "-m", "pytest", "-q", "tests"], cold)
        run([sys.executable, "-c", "import aether; print('AETHER_IMPORT_OK', aether.__file__)"], cold)
        print(f"COLD_PUBLIC_RELEASE_VALID files={len(files)}")


if __name__ == "__main__":
    main()
