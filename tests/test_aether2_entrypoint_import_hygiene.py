"""Regression sentinel for the F1 launch-collapse failure family.

457/482 attempts in the frozen G4 tournament crashed at process start with::

    ModuleNotFoundError: No module named 'runner'

because ``tools/run_aether2_g3_official.py`` (VM-only) imports
``runner.aether2.*`` at module top without first inserting the repo root onto
``sys.path``. The canonical correct pattern lives in ``tools/run_aether2_g2.py``::

    REPO_ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(REPO_ROOT))

    from runner.aether2.bridge_harbor import TaskSpec, _build_runtime
    ...

This test is intentionally generic (no task names, no benchmark vocabulary):
for every ``tools/run_aether2_*.py`` and any other ``tools/run_*.py`` that
imports ``runner`` at module scope, it launches the entrypoint as a
subprocess from a foreign cwd (a fresh tempdir) with ``PYTHONPATH`` stripped
from the environment, and asserts the process never crashes with
``ModuleNotFoundError: No module named 'runner'``.

The test does not assert on exit code: many entrypoints exit non-zero for
benign reasons when given no/incomplete arguments (e.g. ``--task-id``
required, no model credentials, etc.). Only the absence of the F1 import
crash signature is asserted. To keep the run fast and side-effect free,
entrypoints are launched with a short wall-clock budget and killed if they
are still running (i.e. they got past the module-import phase and are doing
real work).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import spawn_with_retry

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"

# Generous enough to clear the module-import phase (which fails near-instantly
# if `sys.path` is missing the repo root) but short enough to keep the suite
# fast even for entrypoints that would otherwise start real work (model
# clients, Docker, long-running jobs).
_LAUNCH_TIMEOUT_SEC = 8.0

_MODULE_NOT_FOUND_RUNNER_RE = re.compile(r"ModuleNotFoundError: No module named ['\"]runner['\"]")


def _imports_runner_at_module_scope(path: Path) -> bool:
    """Return True if the file has a top-level `from runner...`/`import runner...`."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("from runner") or stripped.startswith("import runner"):
            return True
    return False


def _discover_entrypoints() -> list[Path]:
    candidates: dict[Path, None] = {}
    for path in sorted(TOOLS_DIR.glob("run_aether2_*.py")):
        candidates[path] = None
    for path in sorted(TOOLS_DIR.glob("run_*.py")):
        if path in candidates:
            continue
        if _imports_runner_at_module_scope(path):
            candidates[path] = None
    return sorted(candidates)


ENTRYPOINTS = _discover_entrypoints()


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS, ids=lambda p: p.name)
def test_entrypoint_imports_runner_without_pythonpath(entrypoint: Path) -> None:
    """Launching the entrypoint from a foreign cwd with PYTHONPATH stripped
    must not crash with `ModuleNotFoundError: No module named 'runner'`.

    This is the permanent guard against the F1 launch-collapse family: any
    `tools/run_aether2_*.py` (or `tools/run_*.py` importing `runner`) added in
    the future is automatically covered by the glob above and must carry its
    own `sys.path` bootstrap (see `tools/run_aether2_g2.py:34-35`).
    """
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    with tempfile.TemporaryDirectory() as tmpdir:
        proc = spawn_with_retry(
            subprocess.Popen,
            [sys.executable, str(entrypoint), "--help"],
            cwd=tmpdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=_LAUNCH_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            # The entrypoint got past the module-import phase and is doing
            # real work (or `--help` is unsupported and it is blocking on
            # something else, e.g. waiting on required args/credentials).
            proc.kill()
            stdout, stderr = proc.communicate()

        combined = (stdout or "") + (stderr or "")
        assert not _MODULE_NOT_FOUND_RUNNER_RE.search(combined), (
            f"{entrypoint} crashed with the F1 'No module named runner' import "
            f"error when launched from a foreign cwd with PYTHONPATH stripped. "
            f"It is missing the sys.path bootstrap from tools/run_aether2_g2.py "
            f"(REPO_ROOT = Path(__file__).resolve().parents[1]; "
            f"sys.path.insert(0, str(REPO_ROOT)) BEFORE any `from runner...` "
            f"import).\n--- combined output ---\n{combined}"
        )


def test_discovers_at_least_one_entrypoint() -> None:
    """Sanity check: the glob-based discovery finds the known-good g2 entrypoint
    (and any future tools/run_aether2_*.py / runner-importing tools/run_*.py)."""
    assert ENTRYPOINTS, "expected at least one tools/run_aether2_*.py entrypoint"
    names = {p.name for p in ENTRYPOINTS}
    assert "run_aether2_g2.py" in names
