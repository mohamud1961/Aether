from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import overnight_control_plane as ocp


def test_default_checkpoint_includes_resume_and_worker_backend_fields():
    checkpoint = ocp.default_checkpoint(supervisor_id="sup-1")

    assert checkpoint["supervisor_id"] == "sup-1"
    assert checkpoint["phase"] == "fix_queue"
    assert checkpoint["resume_phase"] == "fix_queue"
    assert checkpoint["worker_backend"] == "opencode"
    assert checkpoint["worker_opencode_model"] == "azure-harnesseng/gpt-5.3-codex"
    assert checkpoint["worker_opencode_variant"] == "high"
    assert ocp.validate_checkpoint(checkpoint) == []


@pytest.mark.parametrize(
    "role,result,expected_step",
    [
        (
            "lead",
            {
                "supervisor_id": "sup-1",
                "role": "lead",
                "phase": "fix_queue",
                "current_lane": "lane",
                "current_subtask": "task",
                "next_required_action": "launch_worker",
                "current_eval_target": "target",
                "latest_artifact_paths": ["a"],
                "latest_result_root": "root",
                "worker_backend": "opencode",
                "worker_model": "gpt-5.3-codex",
                "eval_model": "gpt-5.4-mini",
                "summary": "ok",
                "updated_at_utc": "2026-06-03T20:00:00Z",
                "attempt_count": 2,
                "model": "gpt-5.4",
            },
            "lead_plan_written",
        ),
        (
            "worker",
            {
                "supervisor_id": "sup-1",
                "role": "worker",
                "phase": "iteration_loop",
                "current_lane": "lane",
                "current_subtask": "task",
                "success": True,
                "next_required_action": "launch_eval",
                "current_eval_target": "target",
                "latest_artifact_paths": ["a"],
                "latest_result_root": "root",
                "worker_backend": "opencode",
                "worker_opencode_model": "azure-harnesseng/gpt-5.3-codex",
                "worker_opencode_variant": "high",
                "failure_signature": "",
                "tests_run": ["pytest -q"],
                "patched_files": ["foo.py"],
                "summary": "ok",
                "updated_at_utc": "2026-06-03T20:00:00Z",
                "attempt_count": 3,
                "model": "gpt-5.3-codex",
            },
            "worker_result_written",
        ),
        (
            "eval",
                {
                    "supervisor_id": "sup-1",
                    "role": "eval",
                    "phase": "iteration_loop",
                "decision": "iterate",
                "reason_codes": ["dry_run"],
                "evidence_paths": ["artifact.json"],
                "latest_artifact_paths": ["artifact.json"],
                "next_required_action": "launch_lead",
                    "current_eval_target": "target",
                    "summary": "ok",
                    "updated_at_utc": "2026-06-03T20:00:00Z",
                    "attempt_count": 4,
                    "model": "gpt-5.4-mini",
                },
                "eval_result_written",
        ),
    ],
)
def test_checkpoint_patch_from_role_result_tracks_last_successful_step(role, result, expected_step):
    patch = ocp.checkpoint_patch_from_role_result(role, result)

    assert patch["last_successful_step"] == expected_step
    assert patch["attempt_count"] == result["attempt_count"]
    assert patch["worker_backend"] == "opencode"
    if role == "worker":
        assert patch["worker_worktree_root"] == ""
        assert patch["worker_opencode_model"] == "azure-harnesseng/gpt-5.3-codex"
        assert patch["worker_opencode_variant"] == "high"


def test_lead_next_action_alias_normalizes_to_launch_worker():
    result = {
        "supervisor_id": "sup-1",
        "role": "lead",
        "phase": "fix_queue",
        "current_lane": "lane",
        "current_subtask": "task",
        "next_required_action": "launch_single_fix_queue_worker",
        "current_eval_target": "target",
        "latest_artifact_paths": ["a"],
        "latest_result_root": "root",
        "worker_backend": "opencode",
        "worker_model": "gpt-5.3-codex",
        "eval_model": "gpt-5.4-mini",
        "summary": "ok",
        "updated_at_utc": "2026-06-04T00:00:00Z",
        "attempt_count": 2,
        "model": "gpt-5.4",
    }

    assert ocp.validate_role_result("lead", result) == []
    patch = ocp.checkpoint_patch_from_role_result("lead", result)
    assert patch["next_required_action"] == "launch_worker"


def test_descriptive_lead_worker_action_normalizes_to_launch_worker():
    result = {
        "supervisor_id": "sup-1",
        "role": "lead",
        "phase": "fix_queue",
        "current_lane": "lane",
        "current_subtask": "task",
        "next_required_action": "launch_opencode_worker_for_custom_board_freeze_and_active_kernel_baseline",
        "current_eval_target": "target",
        "latest_artifact_paths": ["a"],
        "latest_result_root": "root",
        "worker_backend": "opencode",
        "worker_model": "gpt-5.3-codex",
        "eval_model": "gpt-5.4-mini",
        "summary": "ok",
        "updated_at_utc": "2026-06-04T00:00:00Z",
        "attempt_count": 2,
        "model": "gpt-5.4",
    }

    assert ocp.validate_role_result("lead", result) == []
    patch = ocp.checkpoint_patch_from_role_result("lead", result)
    assert patch["next_required_action"] == "launch_worker"


def test_classify_failure_detects_provider_disconnects():
    payload = ocp.classify_failure(
        "response.failed event received while stream disconnected before completion",
        exit_code=1,
        role="worker",
    )

    assert payload["signature"] == "provider_stream_disconnect"
    assert payload["category"] == "provider"
    assert payload["retryable"] is True


def test_provider_health_gate_dry_run_writes_machine_readable_status(tmp_path):
    prompt_path = tmp_path / "health_prompt.txt"
    log_path = tmp_path / "health.log"
    output_path = tmp_path / "health.json"

    payload = ocp.run_provider_health_gate(
        repo_root=Path.cwd(),
        model="gpt-5.4",
        profile="azure54",
        reasoning_effort="high",
        timeout_seconds=1,
        prompt_path=prompt_path,
        log_path=log_path,
        output_path=output_path,
        dry_run=True,
    )

    assert payload["healthy"] is True
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "healthy"
    assert "Reply with exactly OK" in prompt_path.read_text(encoding="utf-8")


def test_launch_role_dry_run_worker_emits_valid_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("brief", encoding="utf-8")
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = ocp.default_checkpoint(supervisor_id="sup-1")
    checkpoint.update(
        {
            "current_lane": "lane",
            "current_subtask": "task",
            "current_eval_target": "target",
            "worker_backend": "opencode",
            "worker_worktree_root": str(tmp_path / "worktrees"),
            "worker_opencode_model": "azure-harnesseng/gpt-5.3-codex",
            "worker_opencode_variant": "high",
        }
    )
    ocp.write_json(checkpoint_path, checkpoint)
    run_root = tmp_path / "runs"
    run_root.mkdir(parents=True)

    record = ocp.launch_role(
        role="worker",
        model="gpt-5.3-codex",
        profile="azure54",
        reasoning_effort="high",
        timeout_seconds=1,
        repo_root=repo_root,
        brief_path=brief_path,
        checkpoint_path=checkpoint_path,
        run_root=run_root,
        supervisor_id="sup-1",
        current_checkpoint=checkpoint,
        dry_run=True,
    )

    output_path = Path(record["output_path"])
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert record["success"] is True
    assert payload["role"] == "worker"
    assert payload["worker_backend"] == "opencode"
    assert payload["next_required_action"] == "launch_eval"


def test_resolve_opencode_binary_falls_back_to_default_bin_dir(tmp_path, monkeypatch):
    fake_bin = tmp_path / ".opencode" / "bin"
    fake_bin.mkdir(parents=True)
    fake_opencode = fake_bin / "opencode"
    fake_opencode.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_opencode.chmod(0o755)

    monkeypatch.setattr(ocp.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ocp, "DEFAULT_OPENCODE_BIN_DIRS", (str(fake_bin),))

    assert ocp._resolve_opencode_binary() == str(fake_opencode)


def test_opencode_launch_env_prefixes_default_bin_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(ocp, "DEFAULT_OPENCODE_BIN_DIRS", ("/alpha/bin", "/beta/bin"))
    monkeypatch.setenv("PATH", "/usr/bin:/beta/bin")
    worktree_root = tmp_path / "worker"
    (worktree_root / ".venv" / "bin").mkdir(parents=True)

    env = ocp._opencode_launch_env(worktree_root)

    assert env["PATH"] == f"{worktree_root / '.venv' / 'bin'}:/alpha/bin:/beta/bin:/usr/bin"
    assert env["VIRTUAL_ENV"] == str(worktree_root / ".venv")


def test_adopt_mirrored_role_output_if_present_copies_into_canonical_tree(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    worktree_root = tmp_path / "worktree"
    canonical_output = repo_root / "tracking/collab/vm_supervisor_runs/sup/attempts/worker_0001/worker_result.json"
    mirrored_output = worktree_root / canonical_output.relative_to(repo_root)
    mirrored_output.parent.mkdir(parents=True, exist_ok=True)
    mirrored_output.write_text('{"role":"worker","success":true}\n', encoding="utf-8")

    adopted = ocp._adopt_mirrored_role_output_if_present(
        repo_root=repo_root,
        worktree_root=worktree_root,
        canonical_output_path=canonical_output,
    )

    assert adopted == str(mirrored_output)
    assert canonical_output.read_text(encoding="utf-8") == '{"role":"worker","success":true}\n'


def test_launch_role_worker_adopts_mirrored_opencode_result(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("brief", encoding="utf-8")
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = ocp.default_checkpoint(supervisor_id="sup-1")
    checkpoint.update(
        {
            "current_lane": "lane",
            "current_subtask": "task",
            "current_eval_target": "target",
            "worker_backend": "opencode",
            "worker_worktree_root": str(tmp_path / "worktrees"),
            "worker_opencode_model": "azure-harnesseng/gpt-5.3-codex",
            "worker_opencode_variant": "high",
        }
    )
    ocp.write_json(checkpoint_path, checkpoint)
    run_root = repo_root / "tracking/collab/vm_supervisor_runs/sup-1/attempts"
    run_root.mkdir(parents=True)
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()
    expected_output = run_root / "worker_0001" / "worker_result.json"

    def fake_prepare_worker_worktree(**_kwargs):
        worktree_root = Path(_kwargs["worktree_root"])
        worktree_root.mkdir(parents=True, exist_ok=True)
        return worktree_root

    def fake_run_opencode_role(**kwargs):
        worktree_root = Path(kwargs["worktree_root"])
        mirrored_output = worktree_root / expected_output.relative_to(repo_root)
        mirrored_output.parent.mkdir(parents=True, exist_ok=True)
        mirrored_output.write_text(
            json.dumps(
                {
                    "supervisor_id": "sup-1",
                    "role": "worker",
                    "phase": "fix_queue",
                    "current_lane": "lane",
                    "current_subtask": "task",
                    "success": True,
                    "next_required_action": "launch_eval",
                    "current_eval_target": "target",
                    "latest_artifact_paths": [
                        str(repo_root / "tracking/collab/local_iteration_loop_2026-06-04/vm_pulls/self_cert_false_negative_slice_fixcheck6/20260604T175139Z/scoreboard.json")
                    ],
                    "latest_result_root": str(
                        repo_root / "tracking/collab/local_iteration_loop_2026-06-04/vm_pulls/self_cert_false_negative_slice_fixcheck6/20260604T175139Z"
                    ),
                    "worker_backend": "opencode",
                    "failure_signature": "",
                    "tests_run": ["pytest -q"],
                    "patched_files": ["runner/file.py"],
                    "summary": "ok",
                    "updated_at_utc": "2026-06-04T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "exit_code": 0,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "failure": {"signature": "", "category": "", "retryable": False},
            "worktree_root": str(worktree_root),
            "opencode_config": str(worktree_root / "opencode.json"),
            "variant": "high",
        }

    monkeypatch.setattr(ocp, "_prepare_worker_worktree", fake_prepare_worker_worktree)
    monkeypatch.setattr(ocp, "_run_opencode_role", fake_run_opencode_role)

    record = ocp.launch_role(
        role="worker",
        model="gpt-5.3-codex",
        profile="azure54",
        reasoning_effort="high",
        timeout_seconds=1,
        repo_root=repo_root,
        brief_path=brief_path,
        checkpoint_path=checkpoint_path,
        run_root=run_root,
        supervisor_id="sup-1",
        current_checkpoint=checkpoint,
        worker_backend="opencode",
        worker_worktree_root_base=tmp_path / "worktrees",
        worker_opencode_model="azure-harnesseng/gpt-5.3-codex",
        worker_opencode_variant="high",
        snapshot_root=snapshot_root,
        overlay_rel_paths=[],
    )

    assert record["success"] is True
    assert record["mirrored_output_path"].endswith("/worker_result.json")
    assert expected_output.exists()
    role_result = json.loads((Path(record["role_run_root"]) / "role_result.json").read_text(encoding="utf-8"))
    assert role_result["latest_result_root"].endswith("/20260604T175139Z")
    assert role_result["reported_latest_result_root"].endswith("/20260604T175139Z")
    assert any(path.endswith("/scoreboard.json") for path in role_result["latest_artifact_paths"])
    assert any(path.endswith("/worker_checkout_truth.json") for path in role_result["latest_artifact_paths"])
    assert any(path.endswith("/worker_runtime_contract.json") for path in role_result["latest_artifact_paths"])


def test_launch_role_worker_prepare_failure_returns_explicit_failure(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("brief", encoding="utf-8")
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = ocp.default_checkpoint(supervisor_id="sup-1")
    checkpoint.update(
        {
            "current_lane": "lane",
            "current_subtask": "task",
            "current_eval_target": "target",
            "worker_backend": "opencode",
            "worker_worktree_root": str(tmp_path / "worktrees"),
            "worker_opencode_model": "azure-harnesseng/gpt-5.3-codex",
            "worker_opencode_variant": "high",
        }
    )
    ocp.write_json(checkpoint_path, checkpoint)
    run_root = repo_root / "tracking/collab/vm_supervisor_runs/sup-1/attempts"
    run_root.mkdir(parents=True)
    snapshot_root = tmp_path / "snapshots"
    snapshot_root.mkdir()

    def fake_prepare_worker_worktree(**_kwargs):
        raise RuntimeError("git worktree add failed: HEAD missing")

    monkeypatch.setattr(ocp, "_prepare_worker_worktree", fake_prepare_worker_worktree)

    record = ocp.launch_role(
        role="worker",
        model="gpt-5.3-codex",
        profile="azure54",
        reasoning_effort="high",
        timeout_seconds=1,
        repo_root=repo_root,
        brief_path=brief_path,
        checkpoint_path=checkpoint_path,
        run_root=run_root,
        supervisor_id="sup-1",
        current_checkpoint=checkpoint,
        worker_backend="opencode",
        worker_worktree_root_base=tmp_path / "worktrees",
        worker_opencode_model="azure-harnesseng/gpt-5.3-codex",
        worker_opencode_variant="high",
        snapshot_root=snapshot_root,
        overlay_rel_paths=[],
    )

    assert record["success"] is False
    assert record["failure_signature"] == "worker_worktree_prepare_failed"
    failure_payload = json.loads((Path(record["role_run_root"]) / "failure_classification.json").read_text(encoding="utf-8"))
    assert failure_payload["category"] == "environment"


def test_launch_role_preserves_role_reported_lane_and_subtask(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    brief_path = tmp_path / "brief.md"
    brief_path.write_text("brief", encoding="utf-8")
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = ocp.default_checkpoint(supervisor_id="sup-1")
    checkpoint.update(
        {
            "current_lane": "overnight_readiness",
            "current_subtask": "freeze_custom_board_and_run_active_kernel_baseline",
            "current_eval_target": "custom_board_kernel_iteration",
        }
    )
    ocp.write_json(checkpoint_path, checkpoint)
    run_root = tmp_path / "runs"
    run_root.mkdir(parents=True)

    def fake_run_codex_role(**_kwargs):
        output_path = run_root / "lead_0001" / "lead_plan.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "supervisor_id": "sup-1",
                    "role": "lead",
                    "phase": "fix_queue",
                    "current_lane": "overnight_relaunch_preflight",
                    "current_subtask": "verify_worker_handoff_against_existing_scored_slice",
                    "next_required_action": "launch_worker",
                    "current_eval_target": "existing_scored_slice_preflight",
                    "latest_artifact_paths": ["artifact"],
                    "latest_result_root": "result-root",
                    "worker_backend": "opencode",
                    "worker_model": "azure-harnesseng/gpt-5.3-codex",
                    "eval_model": "gpt-5.4-mini",
                    "summary": "ok",
                    "updated_at_utc": "2026-06-05T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "exit_code": 0,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "failure": {"signature": "", "category": "", "retryable": False},
            "codex_home": str(tmp_path / "codex-home"),
            "command": [],
        }

    monkeypatch.setattr(ocp, "_run_codex_role", fake_run_codex_role)

    record = ocp.launch_role(
        role="lead",
        model="gpt-5.4",
        profile="azure54",
        reasoning_effort="high",
        timeout_seconds=1,
        repo_root=repo_root,
        brief_path=brief_path,
        checkpoint_path=checkpoint_path,
        run_root=run_root,
        supervisor_id="sup-1",
        current_checkpoint=checkpoint,
    )

    assert record["success"] is True
    role_result = json.loads((Path(record["role_run_root"]) / "role_result.json").read_text(encoding="utf-8"))
    assert role_result["current_lane"] == "overnight_relaunch_preflight"
    assert role_result["current_subtask"] == "verify_worker_handoff_against_existing_scored_slice"
    assert role_result["current_eval_target"] == "existing_scored_slice_preflight"


def test_initial_checkpoint_defaults_to_custom_board_kernel_iteration():
    checkpoint = ocp.default_checkpoint(
        supervisor_id="sup-init",
        phase="fix_queue",
        current_lane="overnight_readiness",
        current_subtask=ocp.INITIAL_OVERNIGHT_SUBTASK,
        current_eval_target=ocp.INITIAL_OVERNIGHT_TARGET,
        latest_result_root="",
        worker_backend="opencode",
        worker_worktree_root="/tmp/worktrees",
        worker_opencode_model="azure-harnesseng/gpt-5.3-codex",
        worker_opencode_variant="high",
        restart_count=0,
        attempt_count=0,
        last_failure_signature="",
        resume_phase="fix_queue",
    )

    assert checkpoint["current_subtask"] == "freeze_custom_board_and_run_active_kernel_baseline"
    assert checkpoint["current_eval_target"] == "custom_board_kernel_iteration"


@pytest.mark.parametrize(
    "last_successful_step,expected_phase",
    [
        ("worker_result_written", "iteration_loop"),
        ("eval_result_written", "iteration_loop"),
        ("lead_plan_written", None),
    ],
)
def test_bootstrap_iteration_loop_phase_patch_only_promotes_after_real_work(last_successful_step, expected_phase):
    checkpoint = ocp.default_checkpoint(
        supervisor_id="sup-init",
        phase="fix_queue",
        current_lane="overnight_readiness",
        current_subtask=ocp.INITIAL_OVERNIGHT_SUBTASK,
        current_eval_target=ocp.INITIAL_OVERNIGHT_TARGET,
        latest_result_root="",
        worker_backend="opencode",
        worker_worktree_root="/tmp/worktrees",
        worker_opencode_model="azure-harnesseng/gpt-5.3-codex",
        worker_opencode_variant="high",
        restart_count=0,
        attempt_count=0,
        last_failure_signature="",
        resume_phase="fix_queue",
    )
    checkpoint.update(
        {
            "next_required_action": "launch_lead",
            "last_successful_step": last_successful_step,
        }
    )

    patch = ocp._bootstrap_iteration_loop_phase_patch(checkpoint)

    if expected_phase is None:
        assert patch == {}
    else:
        assert patch["phase"] == expected_phase
        assert patch["updated_at_utc"]
