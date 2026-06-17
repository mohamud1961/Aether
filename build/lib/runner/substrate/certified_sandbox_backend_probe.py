"""Small Docker backend probe for eval-first sandbox contract work.

This probe is diagnostic only and does not certify the backend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROBE_ID = "certified_sandbox_backend_probe_v0"
CANONICAL_WORKSPACE = "/workspace/task"
DEFAULT_IMAGE = "python:3.11-slim"
RESULT_ROW_NAME = "certified_sandbox_backend_probe_result_row.json"
CONTAINER_SNIPPET = (
    "import json,os,pathlib,platform,shutil,subprocess,sys; "
    "p=pathlib.Path.cwd(); "
    "token=os.environ.get('PROBE_RUN_TOKEN',''); "
    "bare_python=shutil.which('python') or ''; "
    "bare_version=''; "
    "cp=subprocess.run([bare_python,'--version'],capture_output=True,text=True) if bare_python else None; "
    "bare_version=((cp.stdout or cp.stderr).strip() if cp else ''); "
    "report={'cwd':os.getcwd(),'python3_available':True,"
    "'python3_path':sys.executable,"
    "'python_version':sys.version.split()[0],'platform':platform.platform(),"
    "'bare_python_path':bare_python,'bare_python_version':bare_version,"
    "'run_token':token,'input_exists':(p/'probe_input.txt').exists()}; "
    "(p/'probe_container_report.json').write_text(json.dumps(report,sort_keys=True),encoding='utf-8'); "
    "(p/'artifact_sync_check.txt').write_text(token+'\\n',encoding='utf-8'); "
    "print(json.dumps(report,sort_keys=True))"
)
VERIFIER_CMD = (
    "set -eu; "
    "echo verifier_probe_start; "
    "test -f probe_container_report.json; "
    "grep -qx \"$PROBE_RUN_TOKEN\" artifact_sync_check.txt; "
    "printf 'verifier_probe_ok %s\\n' \"$PROBE_RUN_TOKEN\" > verifier_visible.log; "
    "cat verifier_visible.log"
)


def _docker_base_cmd(docker_context: str | None) -> list[str]:
    cmd = ["docker"]
    if docker_context:
        cmd.extend(["--context", docker_context])
    return cmd


def _run(cmd: list[str], *, timeout_sec: int = 60, cwd: Path | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
        return {"cmd": cmd, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"cmd": cmd, "returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "", "timed_out": True}


def _json_field(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_json(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _reason_codes(checks: dict[str, bool]) -> list[str]:
    return [f"{name}_failed" for name, passed in checks.items() if not passed]


def _context_name(stdout: str, fallback: str) -> str:
    text = stdout.strip()
    return text or fallback


def _backend_type(context_metadata: dict[str, Any]) -> str:
    endpoints = _nested_dict(context_metadata.get("Endpoints"))
    docker = _nested_dict(endpoints.get("docker"))
    host = str(docker.get("Host", ""))
    if host.startswith("unix://") or host.startswith("npipe://"):
        return "local_docker"
    if host:
        return "remote_docker"
    return "unknown_docker"


def _docker_endpoint(context_metadata: dict[str, Any]) -> str:
    endpoints = _nested_dict(context_metadata.get("Endpoints"))
    docker = _nested_dict(endpoints.get("docker"))
    return str(docker.get("Host", ""))


def _required_gate_checks(
    *,
    backend_type: str,
    context_name: str,
    docker_endpoint: str,
    require_backend: str | None,
    require_context: str | None,
    require_endpoint_regex: str | None,
) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    if require_backend:
        checks["required_backend"] = backend_type == require_backend
    if require_context:
        checks["required_context"] = context_name == require_context
    if require_endpoint_regex:
        checks["required_endpoint"] = re.search(require_endpoint_regex, docker_endpoint) is not None
    return checks


def _evaluate_checks(
    steps: dict[str, dict[str, Any]],
    workspace: Path,
    *,
    run_token: str,
    backend_type: str,
    docker_info: dict[str, Any],
    image_metadata: dict[str, Any],
    required_checks: dict[str, bool] | None = None,
) -> dict[str, bool]:
    container_report = _json_field(steps["container_probe"]["stdout"])
    if not isinstance(container_report, dict):
        container_report = {}
    artifact_path = workspace / "artifact_sync_check.txt"
    verifier_log = workspace / "verifier_visible.log"
    artifact_text = artifact_path.read_text(encoding="utf-8").strip() if artifact_path.exists() else ""
    verifier_text = verifier_log.read_text(encoding="utf-8") if verifier_log.exists() else ""
    checks = {
        "docker_context": steps["docker_context_show"]["returncode"] == 0 and steps["docker_context"]["returncode"] == 0,
        "backend_identified": backend_type in {"local_docker", "remote_docker"},
        "image_pull": steps["image_pull"]["returncode"] == 0,
        "docker_version": steps["docker_version"]["returncode"] == 0,
        "docker_info": steps["docker_info"]["returncode"] == 0,
        "image_metadata": steps["image_metadata"]["returncode"] == 0,
        "linux_docker_server": str(docker_info.get("OSType", "")).lower() == "linux",
        "linux_container_image": str(image_metadata.get("Os", "")).lower() == "linux",
        "container_started": steps["container_start"]["returncode"] == 0,
        "workspace_created": steps["workspace_create"]["returncode"] == 0,
        "input_sync_in": steps["input_sync_in"]["returncode"] == 0,
        "container_probe": steps["container_probe"]["returncode"] == 0,
        "cwd_mapping": container_report.get("cwd") == CANONICAL_WORKSPACE,
        "python3_available": bool(container_report.get("python3_available")),
        "run_token_fresh": container_report.get("run_token") == run_token and artifact_text == run_token and run_token in verifier_text,
        "verifier_visible": steps["verifier_probe"]["returncode"] == 0 and "verifier_probe_ok" in steps["verifier_probe"]["stdout"],
        "artifact_sync_back": steps["artifact_sync_back"]["returncode"] == 0 and artifact_path.exists() and verifier_log.exists(),
    }
    checks.update(required_checks or {})
    return checks


def _metadata(stdout: str) -> dict[str, Any]:
    value = _json_field(stdout)
    return value if isinstance(value, dict) else {}


def _nested_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def run_probe(
    *,
    output_dir: str | Path,
    docker_context: str | None = None,
    image: str = DEFAULT_IMAGE,
    timeout_sec: int = 90,
    require_backend: str | None = None,
    require_context: str | None = None,
    require_endpoint_regex: str | None = None,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    workspace = out / "host_workspace"
    if workspace.exists():
        for path in sorted(workspace.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "probe_input.txt").write_text("probe\n", encoding="utf-8")

    base = _docker_base_cmd(docker_context)
    run_token = uuid.uuid4().hex
    context_show = _run(base + ["context", "show"], timeout_sec=timeout_sec)
    context_name = docker_context or _context_name(context_show["stdout"], "current")
    context_inspect_cmd = base + ["context", "inspect", "--format", "{{json .}}"]
    if docker_context:
        context_inspect_cmd.insert(-2, docker_context)
    steps: dict[str, dict[str, Any]] = {
        "docker_context_show": context_show,
        "docker_context": _run(context_inspect_cmd, timeout_sec=timeout_sec),
        "docker_version": _run(base + ["version", "--format", "{{json .}}"], timeout_sec=timeout_sec),
        "docker_info": _run(base + ["info", "--format", "{{json .}}"], timeout_sec=timeout_sec),
        "image_pull": _run(base + ["pull", image], timeout_sec=timeout_sec),
        "image_metadata": _run(base + ["image", "inspect", image, "--format", "{{json .}}"], timeout_sec=timeout_sec),
    }
    container_id = ""
    try:
        steps["container_create"] = _run(base + ["create", image, "sleep", "infinity"], timeout_sec=timeout_sec)
        container_id = steps["container_create"]["stdout"].strip()
        if container_id:
            steps["container_start"] = _run(base + ["start", container_id], timeout_sec=timeout_sec)
            steps["workspace_create"] = _run(base + ["exec", container_id, "mkdir", "-p", CANONICAL_WORKSPACE], timeout_sec=timeout_sec)
            steps["input_sync_in"] = _run(base + ["cp", str(workspace / "probe_input.txt"), f"{container_id}:{CANONICAL_WORKSPACE}/probe_input.txt"], timeout_sec=timeout_sec)
            steps["container_probe"] = _run(
                base + ["exec", "-w", CANONICAL_WORKSPACE, "-e", f"PROBE_RUN_TOKEN={run_token}", container_id, "python3", "-c", CONTAINER_SNIPPET],
                timeout_sec=timeout_sec,
            )
            steps["verifier_probe"] = _run(
                base + ["exec", "-w", CANONICAL_WORKSPACE, "-e", f"PROBE_RUN_TOKEN={run_token}", container_id, "sh", "-lc", VERIFIER_CMD],
                timeout_sec=timeout_sec,
            )
            steps["artifact_sync_back"] = _run(base + ["cp", f"{container_id}:{CANONICAL_WORKSPACE}/.", str(workspace)], timeout_sec=timeout_sec)
        else:
            missing = {"cmd": [], "returncode": 1, "stdout": "", "stderr": "container id unavailable"}
            for name in ("container_start", "workspace_create", "input_sync_in", "container_probe", "verifier_probe", "artifact_sync_back"):
                steps[name] = missing
    finally:
        if container_id:
            steps["container_cleanup"] = _run(base + ["rm", "-f", container_id], timeout_sec=timeout_sec)
        else:
            steps["container_cleanup"] = {"cmd": [], "returncode": 0, "stdout": "", "stderr": ""}

    docker_version = _metadata(steps["docker_version"]["stdout"])
    docker_info = _metadata(steps["docker_info"]["stdout"])
    image_metadata = _metadata(steps["image_metadata"]["stdout"])
    context_metadata = _metadata(steps["docker_context"]["stdout"])
    backend_type = _backend_type(context_metadata)
    docker_endpoint = _docker_endpoint(context_metadata)
    required_checks = _required_gate_checks(
        backend_type=backend_type,
        context_name=context_name,
        docker_endpoint=docker_endpoint,
        require_backend=require_backend,
        require_context=require_context,
        require_endpoint_regex=require_endpoint_regex,
    )
    checks = _evaluate_checks(
        steps,
        workspace,
        run_token=run_token,
        backend_type=backend_type,
        docker_info=docker_info,
        image_metadata=image_metadata,
        required_checks=required_checks,
    )
    invalid_reason_codes = _reason_codes(checks)
    artifact_path = workspace / "artifact_sync_check.txt"
    status = "pass" if all(checks.values()) else "fail"
    docker_client = _nested_dict(docker_version.get("Client"))
    docker_server = _nested_dict(docker_version.get("Server"))
    environment_manifest = {
        "backend_type": backend_type,
        "docker_context": context_name,
        "docker_endpoint": docker_endpoint,
        "docker": {
            "client_version": str(docker_client.get("Version", "")),
            "server_version": str(docker_server.get("Version", docker_info.get("ServerVersion", ""))),
            "server_os": str(docker_info.get("OSType", "")),
            "server_arch": str(docker_info.get("Architecture", "")),
        },
        "host": {"os": platform.system(), "architecture": platform.machine()},
        "image": {
            "reference": image,
            "id": str(image_metadata.get("Id", "")),
            "os": str(image_metadata.get("Os", "")),
            "architecture": str(image_metadata.get("Architecture", "")),
        },
        "workspace": {
            "canonical_path": CANONICAL_WORKSPACE,
            "transfer_mode": "docker_cp",
        },
        "network_policy": "docker_default_no_extra_network_flags",
        "required_gates": {
            "require_backend": require_backend,
            "require_context": require_context,
            "require_endpoint_regex": require_endpoint_regex,
        },
    }
    result_row = {
        "probe_id": PROBE_ID,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "certification_claimed": False,
        "certified_eligible": status == "pass",
        "invalid_reason_codes": invalid_reason_codes,
        "backend_type": backend_type,
        "docker_context": context_name,
        "docker_endpoint": docker_endpoint,
        "docker": {
            "client_version": str(docker_client.get("Version", "")),
            "server_version": str(docker_server.get("Version", docker_info.get("ServerVersion", ""))),
            "server_os": str(docker_info.get("OSType", "")),
            "server_arch": str(docker_info.get("Architecture", "")),
        },
        "host": {
            "os": platform.system(),
            "architecture": platform.machine(),
        },
        "image": {
            "reference": image,
            "id": str(image_metadata.get("Id", "")),
            "os": str(image_metadata.get("Os", "")),
            "architecture": str(image_metadata.get("Architecture", "")),
        },
        "workspace": {
            "canonical_path": CANONICAL_WORKSPACE,
            "cwd_observed": str(_metadata(steps["container_probe"]["stdout"]).get("cwd", "")),
            "cwd_matches": checks["cwd_mapping"],
        },
        "python": {
            "python3_available": checks["python3_available"],
            "python3_path": str(_metadata(steps["container_probe"]["stdout"]).get("python3_path", "")),
            "python3_version": str(_metadata(steps["container_probe"]["stdout"]).get("python_version", "")),
            "bare_python_path": str(_metadata(steps["container_probe"]["stdout"]).get("bare_python_path", "")),
            "bare_python_version": str(_metadata(steps["container_probe"]["stdout"]).get("bare_python_version", "")),
        },
        "network_policy": "docker_default_no_extra_network_flags",
        "environment_manifest": environment_manifest,
        "environment_manifest_hash": _hash_json(environment_manifest),
        "verifier": {
            "exit_code": steps["verifier_probe"].get("returncode"),
            "stdout": steps["verifier_probe"].get("stdout", ""),
            "stderr": steps["verifier_probe"].get("stderr", ""),
        },
        "artifact": {
            "host_path": str(artifact_path),
            "sha256": _sha256(artifact_path) if artifact_path.exists() else "",
        },
        "status": status,
        "checks": checks,
        "step_summaries": {
            name: {
                "returncode": payload.get("returncode"),
                "stdout": payload.get("stdout", "")[-1000:],
                "stderr": payload.get("stderr", "")[-1000:],
            }
            for name, payload in steps.items()
        },
        "artifacts": {
            "output_dir": str(out),
            "workspace": str(workspace),
            "result_row_path": str(out / RESULT_ROW_NAME),
            "container_report": str(workspace / "probe_container_report.json"),
            "verifier_log": str(workspace / "verifier_visible.log"),
        },
    }
    (out / RESULT_ROW_NAME).write_text(json.dumps(result_row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result_row


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a non-certifying Docker sandbox backend probe.")
    parser.add_argument("--output-dir", required=True, help="Directory where result row JSON and artifacts are written.")
    parser.add_argument("--docker-context", default=None, help="Optional docker context name to use.")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help=f"Docker image to probe (default: {DEFAULT_IMAGE}).")
    parser.add_argument("--timeout-sec", type=int, default=90, help="Timeout per docker command.")
    parser.add_argument("--require-backend", choices=["local_docker", "remote_docker"], default=None, help="Require a specific inferred backend type for certified eligibility.")
    parser.add_argument("--require-context", default=None, help="Require the resolved Docker context name to match this value.")
    parser.add_argument("--require-endpoint-regex", default=None, help="Require the Docker endpoint URI to match this regular expression.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_probe(
        output_dir=args.output_dir,
        docker_context=args.docker_context,
        image=args.image,
        timeout_sec=args.timeout_sec,
        require_backend=args.require_backend,
        require_context=args.require_context,
        require_endpoint_regex=args.require_endpoint_regex,
    )
    print(json.dumps({"status": result["status"], "result_row_path": result["artifacts"]["result_row_path"]}, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
