#!/usr/bin/env python3
"""Emit BFCL native certified-attempt preflight and result-row artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runner.azure_openai_env import detect_azure_openai_routes  # noqa: E402
from runner.benchmark_adapter_bfcl_native import (  # noqa: E402
    ADAPTER_AUTHORITY_DETAIL,
    ADAPTER_AUTHORITY_LABEL,
    ADAPTER_FAMILY,
    DEFAULT_CONTAMINATION_LABELS,
    OFFICIAL_BFCL_GRADER_SOURCE,
    native_grader_preflight,
)
from runner.eval_substrate_contracts import validate_result_row  # noqa: E402
from runner.eval_substrate_scoreboard import aggregate_result_rows  # noqa: E402
from runner.model_client import (  # noqa: E402
    AZURE_ENV_GPT53_CODEX_KEY,
    AZURE_ENV_GPT54_MINI_KEY,
)

DEFAULT_OUTPUT_ROOT = Path("tracking/collab/native_bfcl_adapter_upgrade/certified_attempt")
STANDARD_PROVIDER_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")


def run_bfcl_native_certified_attempt(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Write a preflight-only certified attempt bundle.

    This wrapper does not claim a benchmark pass. It checks whether the native
    runtime is ready and emits one invalid/open result row so dashboards can
    account for the certified-attempt state without hiding blockers.
    """

    output_root = Path(output_root).resolve()
    result_dir = output_root / "result_rows"
    artifact_dir = output_root / "artifacts"
    trace_dir = output_root / "traces"
    result_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    dependency_checks = native_grader_preflight()
    upstream_import = _upstream_import_check()
    provider_env = _provider_env_check()
    docker_check = _docker_check()

    blockers = _blockers(
        dependency_checks=dependency_checks,
        upstream_import=upstream_import,
        provider_env=provider_env,
        docker_check=docker_check,
    )
    status = "ready_for_runtime_execution" if not blockers else "blocked"
    preflight = {
        "status": status,
        "blockers": blockers,
        "dependency_checks": dependency_checks,
        "upstream_import_check": upstream_import,
        "provider_env_check": provider_env,
        "docker_check": docker_check,
        "certification_claim": "none; preflight/result-row artifact only",
        "authority_label": ADAPTER_AUTHORITY_LABEL,
        "authority_detail": ADAPTER_AUTHORITY_DETAIL,
    }
    preflight_path = _write_json(output_root / "certified_runtime_preflight.json", preflight)

    verifier_path = _write_json(
        artifact_dir / "verifier_output.json",
        {
            "status": status,
            "blockers": blockers,
            "checks_ref": "preflight://bfcl-native-certified-attempt",
        },
    )
    grader_path = _write_json(
        artifact_dir / "grader_output.json",
        {
            "verdict": "invalid",
            "reason_codes": blockers or ["not_executed_preflight_only"],
            "score": 0.0,
            "authority_label": ADAPTER_AUTHORITY_LABEL,
            "authority_detail": ADAPTER_AUTHORITY_DETAIL,
        },
    )
    trace_path = _write_json(
        trace_dir / "trace.json",
        {
            "events": [
                {"type": "native_grader_preflight", "status": dependency_checks.get("native_runtime_mode")},
                {"type": "upstream_import_check", "import_ok": upstream_import["import_ok"]},
                {"type": "provider_env_check", "available": provider_env["any_provider_env_present"]},
                {"type": "docker_check", "available": docker_check["available"]},
            ]
        },
    )
    artifact_bundle_path = _write_json(
        artifact_dir / "artifact_bundle.json",
        {
            "preflight_ref": str(preflight_path),
            "verifier_ref": str(verifier_path),
            "grader_ref": str(grader_path),
            "trace_refs": [str(trace_path)],
        },
    )

    row = validate_result_row(
        {
            "run_id": "bfcl-native-certified-attempt",
            "eval_id": "bfcl-native-certified-attempt",
            "task_pack_id": "bfcl-native-certified-attempt",
            "family": ADAPTER_FAMILY,
            "surface_type": "tool_call",
            "admission_level": "certified",
            "backend_ref": "linux_container",
            "environment_ref": str(preflight_path),
            "artifact_refs": [str(artifact_bundle_path)],
            "trace_refs": [str(trace_path)],
            "closure_status": "invalid" if blockers else "open",
            "task_truth_status": "invalid",
            "contamination_status": "contaminated",
            "failure_class": "runtime" if blockers else "unclear",
            "reason_codes": blockers or ["not_executed_preflight_only"],
            "verifier_ref": str(verifier_path),
            "grader_ref": str(grader_path),
            "score": 0.0,
            "authority_label": ADAPTER_AUTHORITY_LABEL,
            "authority_detail": ADAPTER_AUTHORITY_DETAIL,
            "contamination_labels": list(DEFAULT_CONTAMINATION_LABELS),
        }
    )
    row_path = _write_json(result_dir / "certified_attempt.json", row)
    scoreboard = aggregate_result_rows([row])
    scoreboard_path = _write_json(output_root / "scoreboard.json", scoreboard)
    summary = {
        "status": status,
        "blockers": blockers,
        "preflight_path": str(preflight_path),
        "result_row_path": str(row_path),
        "scoreboard_path": str(scoreboard_path),
        "row_count": 1,
        "certification_claim": "none; ready means preflight-ready only",
    }
    _write_json(output_root / "run_summary.json", summary)
    return summary


def _upstream_import_check() -> dict[str, Any]:
    module_name = "deepagents_external_benchmarks_probe"
    source = OFFICIAL_BFCL_GRADER_SOURCE
    try:
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            raise ImportError(f"could not create import spec for {source}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module.__name__] = module
        spec.loader.exec_module(module)
        case_count = len(getattr(module, "BFCL_V3_CASES", []))
        return {
            "import_ok": True,
            "stdout": f"OK {case_count}",
            "stderr": "",
            "source": str(source),
        }
    except Exception as exc:  # pragma: no cover - exercised via failure envs.
        return {
            "import_ok": False,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "source": str(source),
        }


def _provider_env_check() -> dict[str, Any]:
    standard_present = [name for name in STANDARD_PROVIDER_ENVS if os.environ.get(name)]
    azure_routes = detect_azure_openai_routes()
    present_provider_envs = list(standard_present)
    for env_name in azure_routes["present_envs"]:
        if env_name not in present_provider_envs:
            present_provider_envs.append(env_name)
    available_provider_routes = list(azure_routes["available_route_ids"])
    if os.environ.get(AZURE_ENV_GPT54_MINI_KEY) and "azure_openai_gpt54_mini" not in available_provider_routes:
        available_provider_routes.append("azure_openai_gpt54_mini_partial")
    if os.environ.get(AZURE_ENV_GPT53_CODEX_KEY) and "azure_openai_gpt53_codex" not in available_provider_routes:
        available_provider_routes.append("azure_openai_gpt53_codex_partial")
    return {
        "present_standard_provider_envs": standard_present,
        "present_provider_envs": present_provider_envs,
        "available_provider_routes": available_provider_routes,
        "azure_openai_routes": azure_routes,
        "any_provider_env_present": bool(standard_present or azure_routes["any_route_available"]),
    }


def _docker_check() -> dict[str, Any]:
    docker_path = shutil.which("docker")
    if not docker_path:
        return {"available": False, "docker_path": "", "stdout": "", "stderr": "docker_not_found"}
    try:
        completed = subprocess.run(
            [docker_path, "info"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except Exception as exc:  # pragma: no cover - environment dependent.
        return {
            "available": False,
            "docker_path": docker_path,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }
    return {
        "available": completed.returncode == 0,
        "docker_path": docker_path,
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
        "exit_code": completed.returncode,
    }


def _blockers(
    *,
    dependency_checks: dict[str, Any],
    upstream_import: dict[str, Any],
    provider_env: dict[str, Any],
    docker_check: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    blockers.extend(str(code) for code in dependency_checks.get("blocker_codes", []))
    if not upstream_import.get("import_ok"):
        blockers.append("upstream_bfcl_grader_import_failed")
    if not provider_env.get("any_provider_env_present"):
        blockers.append("missing_model_provider_env")
    if not docker_check.get("available"):
        blockers.append("docker_unavailable")
    return sorted(set(blockers))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    print(json.dumps(run_bfcl_native_certified_attempt(Path(args.output_root)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
