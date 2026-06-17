from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


TASK_PACK_ROOT = Path("tracking/collab/final_harness_eval_suite/task_packs").resolve()


def _run(script: Path, *, cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _derive_fhard_07_expected(workspace: Path) -> dict[str, str]:
    rows = [
        json.loads(raw)
        for raw in (workspace / "data/live_snapshot.ndjson").read_text(encoding="utf-8").splitlines()
        if raw.strip()
    ]
    candidates = [
        row
        for row in rows
        if str(row.get("status", "")).lower() == "open"
        and str(row.get("workspace_id", "")).startswith("ws-prod")
    ]
    expected = sorted(
        candidates,
        key=lambda row: (
            int(row["priority"]),
            str(row["workspace_id"]),
            str(row["ticket_id"]),
            str(row["event_id"]),
        ),
    )[0]
    return {
        "workspace_id": str(expected["workspace_id"]),
        "ticket_id": str(expected["ticket_id"]),
        "source_event_id": str(expected["event_id"]),
    }


def test_fhard_07_visible_verifier_derives_expected_dispatch(tmp_path: Path) -> None:
    workspace = tmp_path / "fhard07"
    shutil.copytree(
        TASK_PACK_ROOT / "hard" / "fhard_07_original_tool_schema_workspace_mix" / "solver_pack",
        workspace,
    )

    expected = _derive_fhard_07_expected(workspace / "workspace/project")
    project_root = workspace / "workspace/project"
    (project_root / "config/active_workspace.txt").write_text(expected["workspace_id"], encoding="utf-8")
    dispatch = {
        "workspace_id": expected["workspace_id"],
        "ticket_id": expected["ticket_id"],
        "action_commands": [
            f"sync_ticket {expected['ticket_id']}",
            f"dispatch_workspace {expected['workspace_id']}",
        ],
        "source_event_id": expected["source_event_id"],
    }
    (project_root / "out").mkdir(exist_ok=True)
    (project_root / "out/dispatch_plan.json").write_text(json.dumps(dispatch, indent=2), encoding="utf-8")
    final_submission = {
        "dispatch_plan_path": "out/dispatch_plan.json",
        "selected_workspace_id": expected["workspace_id"],
        "selected_ticket": expected["ticket_id"],
        "verifier_command": "python3 scripts/visible_verify.py --dispatch out/dispatch_plan.json --workspace config/active_workspace.txt",
    }
    (project_root / "out/final_submission.json").write_text(json.dumps(final_submission, indent=2), encoding="utf-8")

    passing = _run(
        project_root / "scripts/visible_verify.py",
        cwd=project_root,
        args=["--dispatch", "out/dispatch_plan.json", "--workspace", "config/active_workspace.txt"],
    )
    assert passing.returncode == 0, passing.stdout + passing.stderr

    stale_dispatch = {
        "workspace_id": "ws-stage-4",
        "ticket_id": "TK-7770",
        "action_commands": [
            "sync_ticket TK-7770",
            "dispatch_workspace ws-stage-4",
        ],
        "source_event_id": "evt-103",
    }
    (project_root / "out/dispatch_plan.json").write_text(json.dumps(stale_dispatch, indent=2), encoding="utf-8")
    failing = _run(
        project_root / "scripts/visible_verify.py",
        cwd=project_root,
        args=["--dispatch", "out/dispatch_plan.json", "--workspace", "config/active_workspace.txt"],
    )
    assert failing.returncode != 0
    assert "dispatch_commands_mismatch" in failing.stdout or "workspace_mismatch" in failing.stdout


def test_fsent_05_visible_check_requires_bundle_identity_and_handoff_depth(tmp_path: Path) -> None:
    workspace = tmp_path / "fsent05"
    shutil.copytree(
        TASK_PACK_ROOT / "composition" / "fsent_05_long_handoff_composition_smoke" / "solver_pack",
        workspace,
    )

    handoff_root = workspace / "workspace/handoff"
    seed = json.loads((handoff_root / "stage/inbox/artifact_seed.json").read_text(encoding="utf-8"))
    bundle = {
        "artifact_id": seed["artifact_id"],
        "payload": seed["payload"],
        "source": seed["source"],
        "handoff_steps": ["seed-preserved", "bundle-written", "verified"],
    }
    (handoff_root / "stage/final").mkdir(parents=True, exist_ok=True)
    (handoff_root / "out").mkdir(parents=True, exist_ok=True)
    bundle_path = handoff_root / "stage/final/handoff_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    submission = {
        "artifact_id": seed["artifact_id"],
        "bundle_path": "stage/final/handoff_bundle.json",
        "bundle_sha256": bundle_sha,
        "handoff_steps": ["seed-preserved", "bundle-written", "verified"],
        "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
    }
    submission_path = handoff_root / "out/final_submission.json"
    submission_path.write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    passing = _run(
        handoff_root / "checks/visible_check.py",
        cwd=handoff_root,
        args=["--candidate", "out/final_submission.json"],
    )
    assert passing.returncode == 0, passing.stdout + passing.stderr

    submission["handoff_steps"] = ["seed-preserved", "bundle-written"]
    submission_path.write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failing = _run(
        handoff_root / "checks/visible_check.py",
        cwd=handoff_root,
        args=["--candidate", "out/final_submission.json"],
    )
    assert failing.returncode != 0
    assert "insufficient_handoff_steps" in failing.stdout


def test_fhard_06_visible_verifier_checks_bundle_and_final_submission(tmp_path: Path) -> None:
    workspace = tmp_path / "fhard06"
    shutil.copytree(
        TASK_PACK_ROOT / "hard" / "fhard_06_original_repo_recovery_flagship" / "solver_pack",
        workspace,
    )

    repo_root = workspace / "workspace/repo"
    bundle = {
        "closure_ticket": "RCV-2026-391",
        "runtime_host": "catalog-core.internal",
        "queue_name": "catalog_reconcile_q",
        "token_suffix": "47af",
        "commit_marker": "4c11a0",
    }
    (repo_root / "services/catalog/config").mkdir(parents=True, exist_ok=True)
    (repo_root / "services/catalog/config/runtime.env").write_text(
        "\n".join(
            [
                "RUNTIME_HOST=catalog-core.internal",
                "RUNTIME_PORT=9100",
                "QUEUE_NAME=catalog_reconcile_q",
                "RECOVERY_TOKEN=token-recovery-47af",
                "RECOVERY_MODE=hardened",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "artifacts/recovery/final").mkdir(parents=True, exist_ok=True)
    (repo_root / "out").mkdir(parents=True, exist_ok=True)
    bundle_path = repo_root / "artifacts/recovery/final/recovery_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_submission = {
        "output_path": "artifacts/recovery/final/recovery_bundle.json",
        "closure_ticket": "RCV-2026-391",
        "runtime_host": "catalog-core.internal",
        "queue_name": "catalog_reconcile_q",
        "verifier_command": "python3 scripts/verify_recovery.py --bundle artifacts/recovery/final/recovery_bundle.json --config services/catalog/config/runtime.env",
    }
    (repo_root / "out/final_submission.json").write_text(
        json.dumps(final_submission, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    passing = _run(
        repo_root / "scripts/verify_recovery.py",
        cwd=repo_root,
        args=[
            "--bundle",
            "artifacts/recovery/final/recovery_bundle.json",
            "--config",
            "services/catalog/config/runtime.env",
        ],
    )
    assert passing.returncode == 0, passing.stdout + passing.stderr

    (repo_root / "services/catalog/config/runtime.env").write_text(
        "\n".join(
            [
                "RUNTIME_HOST=catalog-old.internal",
                "RUNTIME_PORT=9100",
                "QUEUE_NAME=catalog_reconcile_q",
                "RECOVERY_TOKEN=token-recovery-47af",
                "RECOVERY_MODE=hardened",
                "",
            ]
        ),
        encoding="utf-8",
    )
    failing = _run(
        repo_root / "scripts/verify_recovery.py",
        cwd=repo_root,
        args=[
            "--bundle",
            "artifacts/recovery/final/recovery_bundle.json",
            "--config",
            "services/catalog/config/runtime.env",
        ],
    )
    assert failing.returncode != 0
    assert "runtime_host_env_mismatch" in failing.stdout or "bundle_runtime_host_mismatch" in failing.stdout
