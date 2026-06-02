from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "bootstrap_bfcl_native_runtime.sh"


def test_bootstrap_script_dry_run() -> None:
    cp = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--repo-path",
            str(REPO_ROOT),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0
    assert "dry-run complete" in cp.stdout


def test_bootstrap_script_run_attempt_skip_install(tmp_path: Path) -> None:
    output_root = tmp_path / "attempt"
    cp = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--repo-path",
            str(REPO_ROOT),
            "--venv-path",
            ".venv",
            "--skip-install",
            "--run-attempt",
            "--attempt-output-root",
            str(output_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0
    summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] in {"blocked", "ready_for_runtime_execution"}
