"""Prepare and execute the Packet 07 Letta golden diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.packet07_cycle1_context_targeted_autoresearch import (
    BACKBONE_INCUMBENT,
    MODEL_TIER_SELECTORS,
    _authority,
    _azure_dns_network_preflight,
    _context_specs,
    _docker_or_fallback_preflight,
    _grade_spec,
    _seed_workspace,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
    resolve_packet07_context_model_route,
)

MISSION_ID = "packet07_golden_diagnostic"
APP_EVIDENCE_VARIANT = "candidate_plus_path_normalized_app_evidence_projection_01"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_golden_diagnostic_prepare"
)
ROUTES = (BACKBONE_INCUMBENT, APP_EVIDENCE_VARIANT)
EVAL_IDS = ("letta_filesystem_001_easy", "letta_filesystem_002_medium")
ARMS = (
    {
        "arm_id": "current_conditions",
        "label": "current conditions",
        "max_steps": 4,
        "inject_orientation": False,
        "python_contract": False,
    },
    {
        "arm_id": "extended_budget_only",
        "label": "extended budget only",
        "max_steps": 12,
        "inject_orientation": False,
        "python_contract": False,
    },
    {
        "arm_id": "extended_budget_orientation",
        "label": "extended budget + orientation",
        "max_steps": 12,
        "inject_orientation": True,
        "python_contract": False,
    },
    {
        "arm_id": "extended_budget_orientation_python3",
        "label": "extended budget + orientation + python contract",
        "max_steps": 12,
        "inject_orientation": True,
        "python_contract": True,
    },
)
LOCAL_ROUTE_OVERRIDES = {
    APP_EVIDENCE_VARIANT: {
        "base_variant": BACKBONE_INCUMBENT,
        "modules": {
            "tools_getter": {
                "file_rel": "blocks/tools/app_evidence_projection_normalizer.py",
                "module_import_path": "blocks.tools.app_evidence_projection_normalizer:get_tools",
            },
            "tool_executor": {
                "file_rel": "blocks/tools/app_evidence_projection_normalizer.py",
                "module_import_path": "blocks.tools.app_evidence_projection_normalizer:execute_tool_call",
            },
        },
    }
}
ORIENTATION_OVERRIDE = {
    "file_rel": "blocks/orientation/env_snapshot.py",
    "module_import_path": "blocks.orientation.env_snapshot:orient",
}


def launch_packet07_golden_diagnostic(
    *,
    output_dir: str | Path,
    execute: bool = False,
    model_tier_selector: str = "screening_default",
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = _build_specs()
    run_spec = {
        "mission_id": MISSION_ID,
        "routes": list(ROUTES),
        "eval_ids": list(EVAL_IDS),
        "arms": list(ARMS),
        "planned_run_count": len(specs) * len(ROUTES),
        "model_tier_selector": model_tier_selector,
        "authority": _authority(),
    }
    patch_summary = {
        "mission_id": MISSION_ID,
        "runtime_changes": [
            "supports max_steps=12 on Letta diagnostic arms",
            "orientation arm injects cwd, data_root, safe_file_listing",
            "python contract arm makes python3 explicit through orientation",
            "records final_answer, exact_grade, step_count, commands, exit_codes, trace_path, model_id, variant_id, max_steps, environment_flags, root_cause_classification",
        ],
        "successor_variant_freeze": True,
    }
    preflight = _preflight(specs)
    _write_json(out / "packet07_golden_diagnostic_run_spec.json", run_spec)
    _write_json(out / "packet07_golden_diagnostic_preflight.json", preflight)
    _write_text(out / "packet07_golden_diagnostic_runtime_patch.md", _runtime_patch_md(patch_summary))
    if not execute:
        return {
            "mission_id": MISSION_ID,
            "status": "prepared",
            "output_dir": str(out),
            "run_spec_path": str(out / "packet07_golden_diagnostic_run_spec.json"),
            "preflight_path": str(out / "packet07_golden_diagnostic_preflight.json"),
            "runtime_patch_path": str(out / "packet07_golden_diagnostic_runtime_patch.md"),
        }

    records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for spec in specs:
        for variant in ROUTES:
            record, trace = _run_one(out, spec, variant, model_tier_selector=model_tier_selector)
            records.append(record)
            traces.append(trace)
    _write_jsonl(out / "packet07_golden_diagnostic_result_records.jsonl", records)
    _write_json(out / "packet07_golden_diagnostic_trace_report.json", {"mission_id": MISSION_ID, "rows": traces})
    _write_json(
        out / "packet07_golden_diagnostic_cost_report.json",
        {
            "mission_id": MISSION_ID,
            "total_tokens": sum(int(row.get("token_and_cost_summary", {}).get("total_tokens", 0) or 0) for row in records),
            "usd_estimate": sum(float(row.get("token_and_cost_summary", {}).get("usd_estimate", 0.0) or 0.0) for row in records),
        },
    )
    return {
        "mission_id": MISSION_ID,
        "status": "executed",
        "output_dir": str(out),
        "record_count": len(records),
    }


def _build_specs() -> list[dict[str, Any]]:
    library = {row["eval_id"]: row for row in _context_specs()}
    specs: list[dict[str, Any]] = []
    for eval_id in EVAL_IDS:
        base = dict(library[eval_id])
        for arm in ARMS:
            spec = dict(base)
            spec["arm"] = dict(arm)
            spec["max_steps"] = int(arm["max_steps"])
            spec["environment_flags"] = {
                "orientation_injected": bool(arm["inject_orientation"]),
                "python_contract_explicit": bool(arm["python_contract"]),
                "max_steps": int(arm["max_steps"]),
            }
            specs.append(spec)
    return specs


def _preflight(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "successor_variant_freeze": True,
        "checks": {
            "route_availability": _route_availability_check(),
            "azure_dns_network_preflight": _azure_dns_network_preflight(),
            "docker_or_fallback": _docker_or_fallback_preflight(specs),
        },
    }


def _route_availability_check() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows, blockers = [], []
    for variant in ROUTES:
        for arm in ARMS:
            try:
                manifest = _build_route_manifest(variant, arm)
                load_runtime_callables(manifest)
                validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
                rows.append({"variant_id": variant, "arm_id": arm["arm_id"], "status": "pass"})
            except Exception as exc:  # pragma: no cover - preflight surface only
                rows.append({"variant_id": variant, "arm_id": arm["arm_id"], "status": "fail", "error": str(exc)})
                blockers.append(f"route_unavailable:{variant}:{arm['arm_id']}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _build_route_manifest(variant: str, arm: dict[str, Any]) -> dict[str, Any]:
    if variant in LOCAL_ROUTE_OVERRIDES:
        override = LOCAL_ROUTE_OVERRIDES[variant]
        manifest = deepcopy(
            build_packet04_route_manifest(override["base_variant"], scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
        )
        module_overrides = dict(override["modules"])
    else:
        manifest = deepcopy(build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE))
        module_overrides = {}
    if arm.get("inject_orientation"):
        module_overrides["orientation"] = ORIENTATION_OVERRIDE
    for entry in manifest["routed_modules"]:
        entry["variant_id"] = variant
        module_override = module_overrides.get(entry["runtime_key"])
        if not module_override:
            continue
        file_rel = Path(module_override["file_rel"])
        real_path = (Path.cwd() / file_rel).resolve()
        entry["declared_card_path"] = str(file_rel)
        entry["real_file_path"] = str(real_path)
        entry["module_import_path"] = str(module_override["module_import_path"])
        entry["file_sha256"] = hashlib.sha256(real_path.read_bytes()).hexdigest()
    manifest["variant_id"] = variant
    manifest["variant_card_ref"] = None
    manifest["route_manifest_fingerprint"] = hashlib.sha256(
        json.dumps(manifest["routed_modules"], sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return manifest


def _run_one(
    out: Path,
    spec: dict[str, Any],
    variant: str,
    *,
    model_tier_selector: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{spec['arm']['arm_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    run_started = perf_counter()
    _seed_workspace(workspace, spec)
    model_route = resolve_packet07_context_model_route(model_tier_selector=model_tier_selector)
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=str(spec["task_id"]),
        task_prompt=str(spec["task_prompt"]),
        benchmark_family=str(spec["benchmark_class"]),
        model_route=model_route,
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(variant, spec["arm"]),
        enforce_packet04_route_contract=True,
        orientation_env_overrides=_orientation_env(workspace, spec["arm"]),
    )
    grade = _grade_spec(spec, result, workspace)
    commands, exit_codes = _tool_trace_fields(result.get("run_events", []))
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    model_id = str(model_route.get("request_settings", {}).get("pricing_model_id") or model_route.get("model_name") or "")
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "task_id": spec["task_id"],
        "arm_id": spec["arm"]["arm_id"],
        "variant_id": variant,
        "model_id": model_id,
        "max_steps": int(spec["max_steps"]),
        "environment_flags": dict(spec["environment_flags"]),
        "trace_path": str(run_dir / "run_events.jsonl"),
        "final_answer": final_answer,
        "exact_grade": grade,
        "step_count": int(result.get("execution", {}).get("step_count", 0) or 0),
        "tool_commands": commands,
        "exit_codes": exit_codes,
        "token_and_cost_summary": _usage(result),
        "root_cause_classification": _classify_root_cause(grade=grade, commands=commands, exit_codes=exit_codes, final_answer=final_answer, max_steps=int(spec["max_steps"]), step_count=int(result.get("execution", {}).get("step_count", 0) or 0)),
        "timing_summary": {"run_wall_sec": perf_counter() - run_started},
    }
    trace = {
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "arm_id": spec["arm"]["arm_id"],
        "variant_id": variant,
        "trace_path": record["trace_path"],
        "final_answer": final_answer,
        "step_count": record["step_count"],
        "tool_commands": commands,
        "exit_codes": exit_codes,
        "root_cause_classification": record["root_cause_classification"],
    }
    return record, trace


def _orientation_env(workspace: Path, arm: dict[str, Any]) -> dict[str, Any] | None:
    if not arm.get("inject_orientation"):
        return None
    data_root = workspace / "letta" / "filesystem"
    env = {
        "cwd": str(workspace),
        "data_root": str(data_root),
        "safe_file_listing": _safe_listing(data_root),
        "environment_flags": {
            "orientation_injected": True,
            "python_contract_explicit": bool(arm.get("python_contract")),
        },
    }
    if arm.get("python_contract"):
        env["python_binary"] = "python3"
    return env


def _safe_listing(data_root: Path) -> list[str]:
    if not data_root.exists():
        return []
    return sorted(path.name for path in data_root.iterdir() if path.is_file())


def _tool_trace_fields(events: list[dict[str, Any]]) -> tuple[list[str], list[int | None]]:
    commands: list[str] = []
    exit_codes: list[int | None] = []
    for event in events:
        if event.get("event_type") != "raw_bash_result":
            continue
        details = event.get("payload", {}).get("details", {})
        commands.append(str(details.get("command") or ""))
        code = details.get("exit_code")
        exit_codes.append(code if isinstance(code, int) else None)
    return commands, exit_codes


def _classify_root_cause(
    *,
    grade: dict[str, Any],
    commands: list[str],
    exit_codes: list[int | None],
    final_answer: str,
    max_steps: int,
    step_count: int,
) -> str:
    reasons = {str(code) for code in grade.get("reason_codes", []) if isinstance(code, str)}
    command_blob = "\n".join(commands)
    if "command not found" in command_blob or any(code not in {0, None} for code in exit_codes if code is not None and "python" in command_blob):
        return "environment/tooling"
    if "/letta/filesystem" in command_blob and "letta/filesystem" not in command_blob:
        return "environment/tooling"
    if step_count >= max_steps and not final_answer.strip():
        if any(token in command_blob for token in ("ls -1", "find .", "pwd")) and not any(
            token in command_blob for token in ("people.txt", "pets.txt", "vehicles.txt", "addresses.txt")
        ):
            return "retrieval/traversal"
        if any(token in command_blob for token in ("people.txt", "pets.txt", "vehicles.txt", "addresses.txt")):
            return "schema-discovery/parsing"
    if {"closure_required_artifact_missing", "closure_evidence_omission"} & reasons:
        return "answer dispatch"
    if final_answer.strip() and grade.get("verdict") == "fail":
        return "reduction/synthesis"
    return "grading/measurement"


def _runtime_patch_md(patch_summary: dict[str, Any]) -> str:
    lines = [
        "# Packet 07 Golden Diagnostic Runtime Patch",
        "",
        f"- mission_id: `{patch_summary['mission_id']}`",
        f"- successor_variant_freeze: `{patch_summary['successor_variant_freeze']}`",
        "- runtime_changes:",
    ]
    lines.extend(f"  - {entry}" for entry in patch_summary["runtime_changes"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--model-tier-selector", choices=MODEL_TIER_SELECTORS, default="screening_default")
    args = parser.parse_args()
    launch_packet07_golden_diagnostic(
        output_dir=args.output_dir,
        execute=bool(args.execute),
        model_tier_selector=str(args.model_tier_selector),
    )


if __name__ == "__main__":
    main()
