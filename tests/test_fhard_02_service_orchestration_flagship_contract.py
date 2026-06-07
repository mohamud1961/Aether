from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


TASK_PACK_ROOT = Path("tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_02_service_orchestration_flagship").resolve()


def _run_visible_verifier(candidate_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(TASK_PACK_ROOT / "solver_pack" / "visible_verifier.py"),
            "--candidate-dir",
            str(candidate_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_fhard_02_solver_pack_exposes_runnable_service_artifacts() -> None:
    fixture_manifest = json.loads((TASK_PACK_ROOT / "fixture_manifest.json").read_text(encoding="utf-8"))
    for rel_path in fixture_manifest["fixture_files"]:
        assert (TASK_PACK_ROOT / "solver_pack" / rel_path).exists(), rel_path

    service_config = json.loads(
        (TASK_PACK_ROOT / "solver_pack" / "service" / "config" / "service_config.json").read_text(encoding="utf-8")
    )
    decoy_config = json.loads(
        (TASK_PACK_ROOT / "solver_pack" / "service" / "config" / "old_port_config.json").read_text(encoding="utf-8")
    )
    assert service_config["required_port"] == 4318
    assert service_config["endpoint_path"] == "/healthz"
    assert decoy_config["required_port"] != service_config["required_port"]


def test_fhard_02_runtime_helpers_launch_probe_and_cleanup(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK_PACK_ROOT / "solver_pack", workspace)

    launch = subprocess.run(
        [sys.executable, "service/runtime/launcher.py"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert launch.returncode == 0, launch.stdout + launch.stderr

    config = json.loads((workspace / "service" / "config" / "service_config.json").read_text(encoding="utf-8"))
    url = f"http://127.0.0.1:{config['required_port']}{config['endpoint_path']}"

    deadline = time.time() + 10.0
    probe_result = None
    while time.time() < deadline:
        probe_result = subprocess.run(
            [
                sys.executable,
                "service/runtime/probe.py",
                "--port",
                str(config["required_port"]),
                "--endpoint",
                config["endpoint_path"],
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(probe_result.stdout.strip() or "{}")
        if payload.get("ok"):
            break
        time.sleep(0.2)

    assert probe_result is not None
    payload = json.loads(probe_result.stdout)
    assert payload["url"] == url
    assert payload["ok"] is True
    assert payload["http_status"] == 200

    pid = int((workspace / "service.pid").read_text(encoding="utf-8").strip())
    cleanup = subprocess.run(
        ["bash", "service/runtime/cleanup.sh"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cleanup.returncode == 0, cleanup.stdout + cleanup.stderr

    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.1)
    else:
        raise AssertionError(f"service pid {pid} still alive after cleanup")


def test_fhard_02_visible_verifier_requires_prompt_schema(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()

    passing_receipt = {
        "service_url": "http://127.0.0.1:4318/healthz",
        "probes_passed": 3,
        "wrong_port_rejected": True,
        "cleanup_performed": True,
        "notes": ["curl -sf http://127.0.0.1:4318/healthz", "curl -sf http://127.0.0.1:4318/healthz"],
    }
    (candidate / "readiness_receipt.json").write_text(json.dumps(passing_receipt, indent=2), encoding="utf-8")
    passing = _run_visible_verifier(candidate)
    assert passing.returncode == 0, passing.stdout

    legacy_receipt = {
        "status": "ready",
        "probe_count": 3,
        "wrong_port_rejected": True,
    }
    (candidate / "readiness_receipt.json").write_text(json.dumps(legacy_receipt, indent=2), encoding="utf-8")
    failing = _run_visible_verifier(candidate)
    assert failing.returncode != 0
    assert "missing_service_url" in failing.stdout or "cleanup_not_confirmed" in failing.stdout
