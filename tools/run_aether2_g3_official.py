#!/usr/bin/env python3
"""Run Aether-2 against official Terminal-Bench task folders.

This is a G3 calibration runner:
- builds the official task Dockerfile
- seeds the container's initial /app into a host workspace
- runs Aether-2 inside the official task container with /app mounted
- only copies official tests into the container after the agent run
- executes official run-tests.sh in the same live container
- writes result_rows.jsonl and scoreboard.md

It intentionally avoids exposing solution.sh or tests to the agent.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
import types

ENV_CONTRACT_VERSION = "aether2_env_contract_v2"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _parse_toml_value(raw: str) -> object:
    value = raw.strip()
    if value.startswith(("'", '"')):
        return ast.literal_eval(value)
    if value in {"true", "false"}:
        return value == "true"
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _install_tomllib_fallback() -> None:
    try:
        import tomllib as tomllib_module  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            import tomli as tomllib_module  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            tomllib_module = types.ModuleType("tomllib")

            def loads(text: str) -> dict[str, object]:
                data: dict[str, object] = {}
                current: dict[str, object] = data
                for raw_line in text.splitlines():
                    line = raw_line.split("#", 1)[0].strip()
                    if not line:
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        path = [part.strip() for part in line[1:-1].split(".") if part.strip()]
                        current = data
                        for part in path:
                            next_value = current.get(part)
                            if not isinstance(next_value, dict):
                                next_value = {}
                                current[part] = next_value
                            current = next_value
                        continue
                    if "=" not in line:
                        continue
                    key, value = [part.strip() for part in line.split("=", 1)]
                    current[key] = _parse_toml_value(value)
                return data

            def load(fp) -> dict[str, object]:
                return loads(fp.read())

            tomllib_module.loads = loads  # type: ignore[attr-defined]
            tomllib_module.load = load  # type: ignore[attr-defined]
    sys.modules["tomllib"] = tomllib_module


_install_tomllib_fallback()

from runner.aether2.bridge_harbor import TaskSpec, _build_model_client  # noqa: E402
from runner.aether2.executor import ContainerBackend, ContainerExecutor  # noqa: E402
from runner.aether2.loop import run_aether2_loop  # noqa: E402
from tools.aether2_grader_isolation import (  # noqa: E402
    build_grader_isolation_contract,
    validate_grader_isolation_contract,
)
from tools.run_phase_journal import (  # noqa: E402
    PHASE_AGENT_RUN_COMPLETED,
    PHASE_AGENT_RUN_STARTED,
    PHASE_GRADER_RUN_COMPLETED,
    PHASE_GRADER_RUN_STARTED,
    PHASE_INITIALIZED,
    RunClassificationContext,
    RunJournal,
    build_phase_row,
    build_result_row,
    classify_run_status,
)
from tools.aether2_launch_integrity import run_launch_integrity_preflight, write_launch_integrity_report  # noqa: E402


DEFAULT_TASK_ROOT = Path("/home/azureuser/terminal-bench-official/original-tasks")
DEFAULT_OUTPUT_ROOT = Path("tracking/collab/aether2_g3_calibration/runs")

G3_COMPLETION_CONTRACT = """
OFFICIAL TASK EXECUTION CONTRACT

You are running inside an official benchmark-style task environment. Do not stop after creating a plausible file or starting a plausible process.

Completion standard:
- Only call task_done after you have verified the actual externally observable condition the task asks for.
- Your final checks must be strong enough that an independent verifier could pass without relying on your claims.
- If the task asks for a server/service/VM, prove the service is still alive and usable from a fresh client after your setup.
- If the task asks for an artifact file, inspect the file content and compare it against the required format/content, not just existence.
- If the task asks for speed/performance, run a representative benchmark and prove the required speedup or explicitly continue improving.
- If the task asks for QEMU/telnet/VNC/desktop readiness, prove semantic readiness, not just that a port is open.
- For QEMU/telnet, verify an actual login/session command succeeds, not merely socket connect.
- For VNC/desktop tasks, verify screenshots are non-blank and that keyboard/monitor commands change visible state.
- For media/transcription tasks, actually download/extract/process the source and inspect the produced answer. Do not write placeholder guesses.
- For long-running jobs, use start_job when persistence matters and check job_status/readiness before task_done.
- If a check fails, do not call task_done. Repair or clearly continue.
- Include the exact commands you used as checks in task_done.
"""

def augment_instruction_for_official_calibration(instruction: str, task_id: str) -> str:
    return (
        instruction.rstrip()
        + "\n\n"
        + G3_COMPLETION_CONTRACT.strip()
        + f"\n\nTask id: {task_id}\n"
    )


def _contract_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_environment_contract(
    *,
    task_id: str,
    task_dir: Path,
    workspace: Path,
    artifacts: Path,
    container_name: str,
    grader_isolation_contract: dict[str, Any],
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "contract_type": "aether2_environment_contract",
        "contract_version": ENV_CONTRACT_VERSION,
        "task_id": task_id,
        "host_workspace_root": str(task_dir),
        "host_task_root": str(task_dir.parent),
        "host_artifact_root": str(artifacts),
        "container_workspace_root": "/app",
        "official_test_path": "/tests",
        "runner_test_path": "/app/tests",
        "path_mapping": {
            "host_workspace_root": str(workspace),
            "container_workspace_root": "/app",
            "host_artifact_root": str(artifacts),
            "container_artifact_root": "/logs",
        },
        "shell": "bash",
        "python": {
            "host": sys.executable,
            "container": "python3",
        },
        "package_managers": {
            "host": "python3 -m pip",
            "container": "system package manager only",
        },
        "user": {
            "host_user": getpass.getuser(),
            "host_uid": os.getuid() if hasattr(os, "getuid") else None,
            "host_gid": os.getgid() if hasattr(os, "getgid") else None,
        },
        "permissions": {
            "writable_roots": [str(workspace), str(artifacts)],
            "read_only_roots": [str(task_dir)],
        },
        "network": {
            "enabled": True,
            "mode": "docker-default",
        },
        "model_start_contract": {
            "canonical_cwd": "/app",
            "workspace_root": "/app",
            "visible_tests": [],
            "hidden_tests_available_to_model": False,
            "completion_requires_independent_evidence": True,
        },
        "artifact_expectations": {
            "workspace_must_sync_back": True,
            "artifact_capture_roots": ["/app", "/logs"],
            "empty_artifact_is_not_success": True,
        },
        "service_expectations": {
            "process_survival_required_when_task_requests_service": True,
            "fresh_client_probe_required_when_task_requests_service": True,
            "open_port_only_is_weak_evidence": True,
        },
        "finalization_expectations": {
            "task_done_requires_successful_replayed_check": True,
            "self_authored_readback_is_weak_evidence": True,
            "official_grader_is_final_authority": True,
        },
        "process_model": {
            "container_name": container_name,
            "launch_command": ["docker", "run", "-d", "--name", container_name, "..."],
        },
        "service_binds": [],
        "runtime_identity": {
            "task_id": task_id,
            "run_dir": str(workspace.parent),
        },
        "lifecycle": {
            "agent_phase": "containerized",
            "verifier_phase": "post-agent-live-container",
        },
        "grader_isolation": {
            "contract_type": grader_isolation_contract.get("contract_type"),
            "contract_version": grader_isolation_contract.get("contract_version"),
            "contract_digest": grader_isolation_contract.get("contract_digest"),
            "contract_ref": "grader_isolation_contract.json",
        },
        "unknowns": {
            "service_ports": [],
            "grader_toolchain": grader_isolation_contract.get("grader_environment_manifest", {}).get(
                "primary_tool_path"
            )
            if isinstance(grader_isolation_contract.get("grader_environment_manifest"), dict)
            else None,
        },
    }
    contract["contract_digest"] = _contract_digest(contract)
    contract["environment_contract_digest"] = contract["contract_digest"]
    contract["environment_contract_version"] = contract["contract_version"]
    contract["environment_contract_ref"] = "environment_contract.json"
    contract["contract_ref"] = contract["environment_contract_ref"]
    return contract


def _collect_service_evidence(
    *,
    container_id: str,
    loop_result: Any | None,
    verification_exit_code: int | None,
    verification_stdout: str,
    verification_stderr: str,
    observation_window_started_at: float,
) -> dict[str, Any]:
    def _run_docker(args: list[str], *, timeout: int = 30) -> dict[str, Any]:
        return run(args, timeout=timeout, cwd=Path.cwd())

    port_listing = _run_docker(["docker", "port", container_id], timeout=20)
    inspect_raw = _run_docker(["docker", "inspect", container_id], timeout=20)
    process_snapshot = _run_docker(["docker", "exec", container_id, "bash", "-lc", "ps -ef"], timeout=20)
    listener_snapshot = _run_docker(
        [
            "docker",
            "exec",
            container_id,
            "bash",
            "-lc",
            "(ss -ltnp || netstat -tulpn || true)",
        ],
        timeout=20,
    )

    inspect_payload: dict[str, Any] = {}
    if inspect_raw.get("returncode") == 0:
        try:
            parsed = json.loads(inspect_raw.get("stdout") or "[]")
            if isinstance(parsed, list) and parsed:
                first = parsed[0]
                if isinstance(first, dict):
                    inspect_payload = {
                        "state": first.get("State"),
                        "network_settings": first.get("NetworkSettings"),
                        "config": {
                            "image": first.get("Config", {}).get("Image") if isinstance(first.get("Config"), dict) else None,
                            "env": first.get("Config", {}).get("Env") if isinstance(first.get("Config"), dict) else None,
                        },
                    }
        except json.JSONDecodeError:
            inspect_payload = {"raw_stdout": inspect_raw.get("stdout")}

    evidence = {
        "observation_window_sec": round(time.time() - observation_window_started_at, 2),
        "job_survival": getattr(loop_result, "job_survival", None) if loop_result is not None else None,
        "session_survival": getattr(loop_result, "session_survival", None) if loop_result is not None else None,
        "verification_exit_code": verification_exit_code,
        "verification_stdout_tail": verification_stdout[-2000:],
        "verification_stderr_tail": verification_stderr[-2000:],
        "port_binding_report": port_listing,
        "container_inspect": inspect_payload,
        "process_snapshot": process_snapshot,
        "listener_snapshot": listener_snapshot,
        "cleanup_plan": {
            "container_id": container_id,
            "remove_after_row_write": True,
        },
    }
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--task-root", default=str(DEFAULT_TASK_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--agent-timeout-sec", type=int, default=None)
    parser.add_argument("--test-timeout-sec", type=int, default=None)
    parser.add_argument("--keep-container-on-fail", action="store_true")
    args = parser.parse_args()

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output_root = Path(args.output_root) / timestamp
    output_root.mkdir(parents=True, exist_ok=True)

    launch_report = run_launch_integrity_preflight(repo_root=REPO_ROOT)
    launch_report_path = write_launch_integrity_report(output_root / "launch_integrity.json", launch_report)
    if not launch_report.ok:
        rows = [
            build_result_row(
                row_status="invalid_launch",
                classification_stage="launch",
                details={
                    "task_id": task_id,
                    "reason": "launch_integrity_preflight_failed",
                    "launch_integrity_ref": str(launch_report_path),
                    "launch_integrity": launch_report.as_dict(),
                    "wall_time_sec": 0.0,
                },
            )
            for task_id in args.task_id
        ]
        write_outputs(output_root, rows)
        print("launch_integrity_preflight_failed: " + ",".join(launch_report.reason_codes))
        print(f"Wrote {output_root / 'result_rows.jsonl'}")
        print(f"Wrote {output_root / 'scoreboard.md'}")
        return 1

    rows: list[dict[str, Any]] = []
    for task_id in args.task_id:
        row = run_one_task(
            task_id=task_id,
            task_root=Path(args.task_root),
            output_root=output_root,
            agent_timeout_override=args.agent_timeout_sec,
            test_timeout_override=args.test_timeout_sec,
            keep_container_on_fail=args.keep_container_on_fail,
        )
        rows.append(row)
        write_outputs(output_root, rows)

    print(f"Wrote {output_root / 'result_rows.jsonl'}")
    print(f"Wrote {output_root / 'scoreboard.md'}")
    return 0 if all(row["row_status"] == "pass" for row in rows) else 1


def run_one_task(
    *,
    task_id: str,
    task_root: Path,
    output_root: Path,
    agent_timeout_override: int | None,
    test_timeout_override: int | None,
    keep_container_on_fail: bool,
) -> dict[str, Any]:
    task_dir = task_root / task_id
    run_dir = output_root / task_id
    workspace = run_dir / "workspace"
    artifacts = run_dir / "artifacts"
    logs = run_dir / "logs"
    build_log = logs / "docker_build.log"
    verifier_log = logs / "official_verifier.json"
    environment_contract_path = artifacts / "environment_contract.json"
    grader_isolation_contract_path = artifacts / "grader_isolation_contract.json"
    service_evidence_path = artifacts / "service_evidence.json"

    shutil.rmtree(run_dir, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    task_yaml = task_dir / "task.yaml"
    dockerfile = task_dir / "Dockerfile"
    run_tests = task_dir / "run-tests.sh"
    tests_dir = task_dir / "tests"

    missing = [p for p in (task_yaml, dockerfile, run_tests, tests_dir) if not p.exists()]
    if missing:
        return {
            "task_id": task_id,
            "row_status": "invalid_environment",
            "reason": "missing official task assets",
            "missing": [str(p) for p in missing],
        }

    meta = parse_task_yaml(task_yaml)
    instruction = build_agent_instruction(task_id, meta["instruction"])

    agent_timeout = agent_timeout_override or int(float(meta.get("max_agent_timeout_sec") or 900))
    test_timeout = test_timeout_override or int(float(meta.get("max_test_timeout_sec") or 180)) + 180

    image = f"aether2-g3-{safe_name(task_id)}:{uuid.uuid4().hex[:10]}"
    container_name = f"aether2-g3-{safe_name(task_id)}-{uuid.uuid4().hex[:10]}"

    started_at = time.time()
    container_id = ""
    grader_isolation_contract: dict[str, Any] | None = None
    environment_contract: dict[str, Any] | None = None
    try:
        build = run(
            ["docker", "build", "-t", image, str(task_dir)],
            timeout=3600,
            cwd=Path.cwd(),
        )
        build_log.write_text(json.dumps(build, indent=2) + "\n", encoding="utf-8")
        if build["returncode"] != 0:
            return row_from_failure(
                task_id=task_id,
                run_dir=run_dir,
                reason="docker_build_failed",
                started_at=started_at,
                details=build,
            )

        seed = seed_workspace_from_image(image=image, workspace=workspace, logs=logs)
        if seed["returncode"] != 0:
            return row_from_failure(
                task_id=task_id,
                run_dir=run_dir,
                reason="seed_workspace_failed",
                started_at=started_at,
                details=seed,
            )

        docker_run = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-w",
            "/app",
            "-v",
            f"{workspace.resolve()}:/app",
            "-v",
            f"{(logs / 'container').resolve()}:/logs",
            "-e",
            "TEST_DIR=/tmp/aether2-tests",
            image,
            "sleep",
            "infinity",
        ]
        (logs / "container").mkdir(parents=True, exist_ok=True)
        launched = run(docker_run, timeout=120, cwd=Path.cwd())
        if launched["returncode"] != 0:
            return row_from_failure(
                task_id=task_id,
                run_dir=run_dir,
                reason="container_start_failed",
                started_at=started_at,
                details=launched,
            )
        container_id = launched["stdout"].strip()

        grader_isolation_contract = build_grader_isolation_contract(
            official_tests_source_ref=str(tests_dir),
            agent_env=os.environ,
            official_path="/tests",
            runner_path="/app/tests",
        )
        validate_grader_isolation_contract(grader_isolation_contract)
        write_json(grader_isolation_contract_path, grader_isolation_contract)

        environment_contract = _build_environment_contract(
            task_id=task_id,
            task_dir=task_dir,
            workspace=workspace,
            artifacts=artifacts,
            container_name=container_name,
            grader_isolation_contract=grader_isolation_contract,
        )
        write_json(environment_contract_path, environment_contract)

        task = TaskSpec(
            task_id=task_id,
            instruction=augment_instruction_for_official_calibration(instruction, task_id),
            task_dir=task_dir,
            workspace_root=workspace,
            artifacts_dir=artifacts,
        )
        executor = ContainerExecutor(
            workspace_root=workspace,
            backend=ContainerBackend(
                kind="docker",
                container_id=container_id,
                container_workspace_root="/app",
                exec_shell="bash",
                base_env={"TEST_DIR": "/tmp/aether2-tests"},
            ),
        )

        model_client = _build_model_client()
        loop_result = run_aether2_loop(
            task,
            model_client,
            executor,
            deadline_ts=time.time() + agent_timeout,
        )
        write_json(artifacts / "aether2_result.json", json_safe(loop_result))

        copy_tests = copy_official_tests_into_container(
            container_id=container_id,
            task_dir=task_dir,
            logs=logs,
        )
        if copy_tests["returncode"] != 0:
            return row_from_failure(
                task_id=task_id,
                run_dir=run_dir,
                reason="copy_tests_failed",
                started_at=started_at,
                details=copy_tests,
                loop_result=loop_result,
                container_id=container_id,
                environment_contract=environment_contract,
                grader_isolation_contract=grader_isolation_contract,
            )

        verifier = run(
            [
                "docker",
                "exec",
                "-w",
                "/app",
                "-e",
                "TEST_DIR=/tmp/aether2-tests",
                container_id,
                "bash",
                "-lc",
                "bash /tmp/aether2-run-tests.sh",
            ],
            timeout=test_timeout,
            cwd=Path.cwd(),
        )
        write_json(verifier_log, verifier)

        sync = run(
            ["docker", "cp", f"{container_id}:/app/.", str(artifacts / "app")],
            timeout=180,
            cwd=Path.cwd(),
        )
        write_json(logs / "artifact_sync.json", sync)

        service_evidence = _collect_service_evidence(
            container_id=container_id,
            loop_result=loop_result,
            verification_exit_code=verifier["returncode"],
            verification_stdout=verifier["stdout"],
            verification_stderr=verifier["stderr"],
            observation_window_started_at=started_at,
        )
        write_json(service_evidence_path, service_evidence)

        if verifier["returncode"] == 0:
            row_status = "pass"
        else:
            row_status = classify_run_status(
                RunClassificationContext(
                    stage="grader",
                    exit_code=verifier["returncode"],
                    timed_out=bool(verifier["timed_out"]),
                    stderr=f"{verifier['stdout']}\n{verifier['stderr']}",
                )
            )
        row = build_result_row(
            row_status=row_status,
            classification_stage="grader",
        details={
            "task_id": task_id,
            "verifier_exit_code": verifier["returncode"],
            "timed_out": verifier["timed_out"],
            "wall_time_sec": round(time.time() - started_at, 2),
                "run_dir": str(run_dir),
                "workspace": str(workspace),
                "artifacts": str(artifacts),
                "image": image,
                "container_id": container_id,
                "difficulty": meta.get("difficulty"),
                "category": meta.get("category"),
                "environment_contract_version": environment_contract["environment_contract_version"],
                "environment_contract_digest": environment_contract["environment_contract_digest"],
                "environment_contract_ref": str(environment_contract_path),
                "grader_isolation_contract_version": grader_isolation_contract["contract_version"],
                "grader_isolation_contract_digest": grader_isolation_contract["contract_digest"],
                "grader_isolation_contract_ref": str(grader_isolation_contract_path),
            "service_evidence_ref": str(service_evidence_path),
            "service_evidence": service_evidence,
            "reasoning_trace_ref": getattr(loop_result, "reasoning_trace_ref", None),
            "loop_result": json_safe(loop_result),
            "verifier_stdout_tail": verifier["stdout"][-4000:],
            "verifier_stderr_tail": verifier["stderr"][-4000:],
        },
    )
        row["environment_contract"] = environment_contract
        row["grader_isolation_contract"] = grader_isolation_contract
        write_json(run_dir / "row.json", row)
        return row

    except Exception as exc:
        return row_from_failure(
            task_id=task_id,
            run_dir=run_dir,
            reason="runner_exception",
            started_at=started_at,
            details={"error": repr(exc)},
            container_id=container_id,
            environment_contract=environment_contract,
            grader_isolation_contract=grader_isolation_contract,
        )
    finally:
        if container_id:
            # Preserve the task artifacts, but do not leave service containers around.
            # If debugging a failing run, pass --keep-container-on-fail in a later run.
            status_path = run_dir / "row.json"
            failed = True
            if status_path.exists():
                try:
                    failed = json.loads(status_path.read_text()).get("row_status") != "pass"
                except Exception:
                    failed = True
            if not (failed and keep_container_on_fail):
                run(["docker", "rm", "-f", container_id], timeout=120, cwd=Path.cwd())


def seed_workspace_from_image(*, image: str, workspace: Path, logs: Path) -> dict[str, Any]:
    create = run(["docker", "create", image], timeout=120, cwd=Path.cwd())
    write_json(logs / "seed_create.json", create)
    if create["returncode"] != 0:
        return create

    cid = create["stdout"].strip()
    try:
        # docker create containers are stopped, so do not use docker exec here.
        # Try copying /app directly. If /app does not exist in the image, use an
        # empty workspace. If /app exists, this preserves official task assets
        # such as alpine.iso or isos/win311.img.
        cp = run(["docker", "cp", f"{cid}:/app/.", str(workspace)], timeout=900, cwd=Path.cwd())
        write_json(logs / "seed_copy.json", cp)

        if cp["returncode"] == 0:
            cp["seeded"] = True
            write_json(logs / "seed_copy.json", cp)
            return cp

        combined = (cp.get("stdout", "") + "\n" + cp.get("stderr", "")).lower()
        missing_app = (
            "could not find the file /app" in combined
            or "no such file or directory" in combined
            or "not found" in combined
        )
        if missing_app:
            workspace.mkdir(parents=True, exist_ok=True)
            skipped = {
                "cmd": ["docker", "cp", f"{cid}:/app/.", str(workspace)],
                "returncode": 0,
                "stdout": "seed skipped: image has no /app directory; using empty host workspace mounted as /app at runtime",
                "stderr": cp.get("stderr", ""),
                "timed_out": False,
                "duration_sec": cp.get("duration_sec", 0.0),
                "seeded": False,
            }
            write_json(logs / "seed_copy.json", skipped)
            return skipped

        return cp
    finally:
        run(["docker", "rm", "-f", cid], timeout=120, cwd=Path.cwd())


def copy_official_tests_into_container(*, container_id: str, task_dir: Path, logs: Path) -> dict[str, Any]:
    copied_compat = run(["docker", "cp", str(task_dir / "tests"), f"{container_id}:/tmp/aether2-tests"], timeout=180, cwd=Path.cwd())
    write_json(logs / "copy_compat_tests.json", copied_compat)
    if copied_compat["returncode"] != 0:
        return copied_compat
    copied_official = run(["docker", "cp", str(task_dir / "tests"), f"{container_id}:/tests"], timeout=180, cwd=Path.cwd())
    write_json(logs / "copy_official_tests.json", copied_official)
    if copied_official["returncode"] != 0:
        return copied_official
    copied_runner = run(["docker", "cp", str(task_dir / "tests"), f"{container_id}:/app/tests"], timeout=180, cwd=Path.cwd())
    write_json(logs / "copy_runner_tests.json", copied_runner)
    if copied_runner["returncode"] != 0:
        return copied_runner
    copied_runner = run(["docker", "cp", str(task_dir / "run-tests.sh"), f"{container_id}:/tmp/aether2-run-tests.sh"], timeout=180, cwd=Path.cwd())
    write_json(logs / "copy_run_tests.json", copied_runner)
    return copied_runner


def parse_task_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return {
        "instruction": yaml_block(text, "instruction"),
        "difficulty": yaml_scalar(text, "difficulty"),
        "category": yaml_scalar(text, "category"),
        "max_agent_timeout_sec": yaml_scalar(text, "max_agent_timeout_sec"),
        "max_test_timeout_sec": yaml_scalar(text, "max_test_timeout_sec"),
    }


def yaml_scalar(text: str, key: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.*?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip().strip("'\"") if match else ""


def yaml_block(text: str, key: str) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:\s*[|>]-?\s*$", line):
            start = i + 1
            break
        if re.match(rf"^{re.escape(key)}:\s*.+$", line):
            return line.split(":", 1)[1].strip().strip("'\"")
    if start is None:
        return ""
    block: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith((" ", "\t")) and re.match(r"^[A-Za-z0-9_-]+:", line):
            break
        block.append(line)
    nonblank = [len(x) - len(x.lstrip(" ")) for x in block if x.strip()]
    indent = min(nonblank) if nonblank else 0
    return "\n".join(x[indent:] if len(x) >= indent else x for x in block).strip()


def build_agent_instruction(task_id: str, official_instruction: str) -> str:
    return f"""You are running the official public Terminal-Bench task `{task_id}` inside its task Docker image.

Current working directory is `/app`. This is the writable task workspace. The official verifier will run after you finish, in the same live container, against the files and services you leave in `/app`.

Rules:
- Solve the task, not a plan-only diagnostic.
- Use the available tools to inspect, create files, run commands, start services, and verify your own work.
- Do not read or modify hidden verifier tests.
- Do not read `solution.sh`.
- Before calling task_done, run concrete checks that support your completion claim.
- If the task requires a server, VM, or background process, leave it running for the official verifier.

Official task instruction:

{official_instruction}
"""


def _failure_stage(reason: str, *, loop_result: Any | None, container_id: str) -> str:
    if reason in {"docker_build_failed", "seed_workspace_failed", "container_start_failed", "missing official task assets"}:
        return "launch"
    if reason == "copy_tests_failed":
        return "grader"
    if loop_result is not None or container_id:
        return "agent"
    return "launch"


def _classify_failure_row_status(
    *,
    reason: str,
    details: dict[str, Any],
    loop_result: Any | None,
    container_id: str,
) -> str:
    if reason == "missing official task assets":
        return "invalid_launch"
    stage = _failure_stage(reason, loop_result=loop_result, container_id=container_id)
    context = RunClassificationContext(
        stage=stage,
        error_message=reason,
        stderr=json.dumps(json_safe(details), sort_keys=True),
    )
    return classify_run_status(context)


def row_from_failure(
    *,
    task_id: str,
    run_dir: Path,
    reason: str,
    started_at: float,
    details: dict[str, Any],
    loop_result: Any | None = None,
    container_id: str = "",
    environment_contract: dict[str, Any] | None = None,
    grader_isolation_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_status = _classify_failure_row_status(
        reason=reason,
        details=details,
        loop_result=loop_result,
        container_id=container_id,
    )
    row = build_result_row(
        row_status=row_status,
        classification_stage=_failure_stage(reason, loop_result=loop_result, container_id=container_id),
        details={
            "reason": reason,
            "reasoning_trace_ref": getattr(loop_result, "reasoning_trace_ref", None) if loop_result is not None else None,
            "wall_time_sec": round(time.time() - started_at, 2),
            "run_dir": str(run_dir),
            "container_id": container_id,
            "details": json_safe(details),
            "loop_result": json_safe(loop_result),
        },
    )
    row.update({
        "task_id": task_id,
        "environment_contract": environment_contract,
        "grader_isolation_contract": grader_isolation_contract,
    })
    if isinstance(environment_contract, dict):
        row["environment_contract_version"] = environment_contract.get("environment_contract_version")
        row["environment_contract_digest"] = environment_contract.get("environment_contract_digest")
        row["environment_contract_ref"] = environment_contract.get("environment_contract_ref")
    if isinstance(grader_isolation_contract, dict):
        row["grader_isolation_contract_version"] = grader_isolation_contract.get("contract_version")
        row["grader_isolation_contract_digest"] = grader_isolation_contract.get("contract_digest")
        row["grader_isolation_contract_ref"] = grader_isolation_contract.get("contract_ref")
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "row.json", row)
    return row


def write_outputs(output_root: Path, rows: list[dict[str, Any]]) -> None:
    result_rows = output_root / "result_rows.jsonl"
    result_rows.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    lines = [
        "# Aether-2 G3 official calibration scoreboard",
        "",
        f"Run directory: {output_root}",
        "",
        "| task_id | row_status | verifier_exit | wall_time_sec | reason |",
        "|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('task_id')} | {row.get('row_status')} | "
            f"{row.get('verifier_exit_code', '')} | {row.get('wall_time_sec', '')} | "
            f"{row.get('reason', '')} |"
        )
    (output_root / "scoreboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(argv: list[str], *, timeout: int, cwd: Path) -> dict[str, Any]:
    started = time.time()
    try:
        cp = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": argv,
            "returncode": cp.returncode,
            "stdout": cp.stdout or "",
            "stderr": cp.stderr or "",
            "timed_out": False,
            "duration_sec": round(time.time() - started, 2),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": argv,
            "returncode": 124,
            "stdout": decode_stream(exc.stdout),
            "stderr": decode_stream(exc.stderr),
            "timed_out": True,
            "duration_sec": round(time.time() - started, 2),
        }


def decode_stream(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value):
        return json_safe(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if hasattr(value, "__dict__"):
        return json_safe(vars(value))
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-") or "task"


if __name__ == "__main__":
    raise SystemExit(main())
