"""Native TerminalBench bridge with provenance checks and official verifier execution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from runner.benchmark_adapter_contracts import build_adapter_result_row, validate_benchmark_adapter_case
from runner.eval_substrate_contracts import validate_result_row, validate_task_pack

EXPECTED_REMOTE_FRAGMENT = "harbor-framework/terminal-bench"
ADAPTER_FAMILY = "terminalbench_native_adapter"
ADAPTER_LABEL = "TerminalBench native adapter"
AUTHORITY_LABEL = "native"
AUTHORITY_DETAIL = "terminalbench_official_task_docker_and_test_sh_runtime"
CONTAMINATION_LABELS = ["clean", "public_benchmark_row", "mirrored_resource", "official_subset"]


def native_preflight(task_root: Path) -> dict[str, Any]:
    repo_root = task_root.parent.parent
    blockers: list[str] = []
    official_yaml_layout = (task_root / "task.yaml").exists()
    if official_yaml_layout:
        required = [task_root / "task.yaml", task_root / "run-tests.sh", task_root / "solution.sh", task_root / "tests/test_outputs.py", task_root / "Dockerfile"]
    else:
        required = [task_root / "instruction.md", task_root / "task.toml", task_root / "tests/test.sh", task_root / "solution/solve.sh"]
    if any(not path.exists() for path in required):
        blockers.append("missing_terminalbench_task_assets")
    remote = _git(["git", "-C", str(repo_root), "remote", "get-url", "origin"])
    commit = _git(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
    if EXPECTED_REMOTE_FRAGMENT not in remote:
        blockers.append("terminalbench_provenance_mismatch")
    docker = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False, timeout=30)
    if docker.returncode != 0:
        blockers.append("docker_daemon_unavailable")
    return {
        "native_runtime_available": not blockers,
        "blocker_codes": blockers,
        "task_root": str(task_root),
        "repo_root": str(repo_root),
        "task_layout": "official_yaml" if official_yaml_layout else "mirrored_toml",
        "git_remote": remote,
        "git_commit": commit,
        "docker_image": _quoted_value((task_root / "task.toml").read_text(encoding="utf-8"), "docker_image") if (task_root / "task.toml").exists() else "",
        "docker_info_tail": (docker.stdout + docker.stderr)[-2000:],
    }


def run_terminalbench_native_static(task_root: Path, output_root: Path) -> dict[str, Any]:
    preflight = native_preflight(task_root)
    if not preflight["native_runtime_available"]:
        raise RuntimeError(f"terminalbench native preflight blocked: {preflight['blocker_codes']}")
    workspace = output_root / "workspace"
    logs = output_root / "logs/verifier"
    shutil.rmtree(output_root, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    official_yaml_layout = preflight["task_layout"] == "official_yaml"
    docker_image = preflight["docker_image"]
    if official_yaml_layout:
        docker_image = f"terminalbench-native-{task_root.name}:latest"
        build = subprocess.run(["docker", "build", "-t", docker_image, str(task_root)], capture_output=True, text=True, check=False, timeout=1800)
        if build.returncode != 0:
            return {"reward": "0", "verifier_stdout_tail": build.stdout[-4000:], "verifier_stderr_tail": build.stderr[-4000:], "verifier_exit_code": build.returncode, "workspace_ref": str(workspace), "ctrf_ref": "", "docker_build_failed": True}
    cp = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{workspace}:/app",
            "-v",
            f"{task_root / 'tests'}:/tests:ro",
            "-v",
            f"{task_root}:/task:ro",
            "-v",
            f"{logs}:/logs/verifier",
            "-w",
            "/app",
            docker_image,
            "bash",
            "-lc",
            "bash /task/solution.sh && TEST_DIR=/tests bash /task/run-tests.sh" if official_yaml_layout else "bash /task/solution/solve.sh && bash /tests/test.sh",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=1800,
    )
    reward = (logs / "reward.txt").read_text(encoding="utf-8").strip() if (logs / "reward.txt").exists() else ("1" if cp.returncode == 0 else "0")
    return {
        "reward": reward,
        "verifier_stdout_tail": cp.stdout[-4000:],
        "verifier_stderr_tail": cp.stderr[-4000:],
        "verifier_exit_code": cp.returncode,
        "workspace_ref": str(workspace),
        "ctrf_ref": str(logs / "ctrf.json"),
    }


def build_task_pack(task_id: str) -> dict[str, Any]:
    return validate_task_pack(
        {
            "task_id": f"terminalbench-native-{task_id}",
            "task_prompt": "Stage the official TerminalBench task under /app and execute the official verifier under /tests.",
            "fixture": {"type": "terminalbench_official_task", "workspace_ref": "/app", "request_ref": "/app"},
            "canonical_root": "/app",
            "backend_requirements": {"certified_default": "linux_container", "debug_backend": "debug_local_no_sandbox", "network": "enabled"},
            "visible_verifier": {"command": "bash /tests/test.sh", "native_verifier_execution": True},
            "hidden_verifier": {"command_shape": "official_terminalbench_verifier", "checks_ref": f"hidden://terminalbench/native/{task_id}", "leak_hidden_checks_to_prompt": False, "native_verifier_execution": True},
            "grader": {"type": "terminalbench_official_reward", "score_range": [0, 1]},
            "contamination_policy": {"status": "clean", "source": "mirrored_terminalbench_official_task", "public_benchmark_row": True},
            "artifact_capture_policy": {"capture": ["environment_manifest", "artifact_bundle", "verifier", "grader", "trace"]},
            "admission_level": "certified",
            "surface_type": "filesystem",
            "benchmark_adapter_contract": {"adapter_label": ADAPTER_LABEL, "authority_label": AUTHORITY_LABEL, "authority_detail": AUTHORITY_DETAIL, "expected_answer_format": "artifact_ref", "hidden_truth_ref": f"hidden://terminalbench/native/{task_id}", "row_provenance_ref": f"provenance://terminalbench/native/{task_id}", "source_schema_version": "terminalbench_native.v1"},
        }
    )


def build_result_row(task_id: str, *, grade: dict[str, Any], artifact_refs: list[str], trace_refs: list[str], verifier_ref: str, grader_ref: str) -> dict[str, Any]:
    row = build_adapter_result_row(
        run_id=f"terminalbench-native-{task_id}-001",
        eval_id="terminalbench-native-static",
        task_pack_id=f"terminalbench-native-{task_id}",
        backend_ref="linux_container",
        environment_ref="certified://terminalbench-native-static",
        verifier_ref=verifier_ref,
        grader_ref=grader_ref,
        benchmark_case=validate_benchmark_adapter_case(
            {
                "benchmark_family": ADAPTER_FAMILY,
                "benchmark_case_id": task_id,
                "authority_label": AUTHORITY_LABEL,
                "surface_type": "filesystem",
                "admission_level": "certified",
                "expected_answer": {"format": "artifact_ref", "value": {"hidden_truth_ref": f"hidden://terminalbench/native/{task_id}"}},
                "contamination_labels": list(CONTAMINATION_LABELS),
                "execution_unit": {"unit_id": f"terminalbench-native-{task_id}::{task_id}", "task_prompt": "Official TerminalBench verifier run", "canonical_root": "/app", "execution_contract": {"authority_detail": AUTHORITY_DETAIL}},
            }
        ),
        native_grader_output=grade,
        trace_refs=trace_refs,
        artifact_refs=artifact_refs,
        failure_class="verification_grading",
    )
    row["adapter_label"] = ADAPTER_LABEL
    row["authority_detail"] = AUTHORITY_DETAIL
    return validate_result_row(row)


def _quoted_value(text: str, key: str) -> str:
    marker = f'{key} = "'
    return text.split(marker, 1)[1].split('"', 1)[0]


def _git(argv: list[str]) -> str:
    cp = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=30)
    return (cp.stdout or cp.stderr).strip()
