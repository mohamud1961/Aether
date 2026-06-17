"""BFCL native adapter using official v3 state-diff grading semantics."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

from runner.benchmark_adapter_contracts import (
    build_adapter_result_row,
    validate_benchmark_adapter_case,
)
from runner import bfcl_assets
from runner.eval_substrate_contracts import validate_result_row, validate_task_pack

REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BFCL_SAMPLES_PATH = REPO_ROOT / "research/sources/codebases/deepagents/libs/evals/tests/evals/data/benchmark_samples/bfcl_v3_final.json"
_DEFAULT_BFCL_APIS_DIR = REPO_ROOT / "research/sources/codebases/deepagents/libs/evals/tests/evals/data/bfcl_apis"
_FALLBACK_BFCL_SAMPLES_PATH = REPO_ROOT / "tracking/collab/final_harness_eval_suite/adapter_fixtures/bfcl/benchmark_samples/bfcl_v3_final.json"
_FALLBACK_BFCL_APIS_DIR = REPO_ROOT / "tracking/collab/final_harness_eval_suite/adapter_fixtures/bfcl/bfcl_apis"

MIRRORED_BFCL_SAMPLES_PATH = _DEFAULT_BFCL_SAMPLES_PATH if _DEFAULT_BFCL_SAMPLES_PATH.exists() else _FALLBACK_BFCL_SAMPLES_PATH
MIRRORED_BFCL_APIS_DIR = _DEFAULT_BFCL_APIS_DIR if _DEFAULT_BFCL_APIS_DIR.exists() else _FALLBACK_BFCL_APIS_DIR
OFFICIAL_BFCL_GRADER_SOURCE = REPO_ROOT / "research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py"

ADAPTER_FAMILY = "bfcl_native_adapter"
ADAPTER_LABEL = "BFCL native adapter"
ADAPTER_AUTHORITY_LABEL = "native"
ADAPTER_AUTHORITY_DETAIL = "bfcl_native_official_v3_state_replay_grader_using_official_cases_and_api_assets"
DEFAULT_HIDDEN_CHECKS_REF = "hidden://bfcl-native/official-v3-curated"
DEFAULT_CONTAMINATION_LABELS = ["clean", "public_benchmark_row", "mirrored_resource", "official_subset"]
OFFICIAL_CURATED_CASE_IDS = (
    "multi_turn_composite_97",
    "multi_turn_composite_116",
    "multi_turn_composite_199",
    "multi_turn_miss_func_55",
    "multi_turn_miss_param_55",
)

_CLASS_IMPORTS = {
    "MessageAPI": ("bfcl_apis.message_api", "MessageAPI"),
    "TicketAPI": ("bfcl_apis.ticket_api", "TicketAPI"),
    "TradingBot": ("bfcl_apis.trading_bot", "TradingBot"),
    "TravelAPI": ("bfcl_apis.travel_booking", "TravelAPI"),
    "VehicleControlAPI": ("bfcl_apis.vehicle_control", "VehicleControlAPI"),
}

_SENDER_ID_SUFFIX = re.compile(r",\s*sender_id=['\"][^'\"]*['\"](?=\s*\))")
_SENDER_ID_PREFIX = re.compile(r"sender_id=['\"][^'\"]*['\"],\s*")


def load_mirrored_cases(path: Path | None = None) -> dict[str, dict[str, Any]]:
    if path is None:
        path = bfcl_assets.resolve_bfcl_samples_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("tasks") if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError("mirrored BFCL sample payload must be a list or dict with tasks")
    return {str(case["id"]): case for case in cases if isinstance(case, dict) and "id" in case}


def load_official_curated_cases() -> dict[str, dict[str, Any]]:
    cases = load_mirrored_cases()
    selected = {case_id: cases.get(case_id) for case_id in OFFICIAL_CURATED_CASE_IDS}
    missing = sorted(case_id for case_id, case in selected.items() if case is None)
    if missing:
        raise ValueError(f"missing_official_bfcl_cases: {', '.join(missing)}")
    return {case_id: selected[case_id] for case_id in OFFICIAL_CURATED_CASE_IDS if selected[case_id] is not None}


def flatten_ground_truth_calls(case: dict[str, Any]) -> list[str]:
    turns = case.get("ground_truth", [])
    calls: list[str] = []
    if not isinstance(turns, list):
        return calls
    for turn in turns:
        if not isinstance(turn, list):
            continue
        for call in turn:
            if isinstance(call, str) and call.strip():
                calls.append(call.strip())
    return calls


def supported_case(case: dict[str, Any]) -> bool:
    classes = case.get("involved_classes", [])
    if not isinstance(classes, list):
        return False
    return all(isinstance(name, str) and name in _CLASS_IMPORTS for name in classes)


def native_grader_preflight() -> dict[str, Any]:
    asset_preflight = bfcl_assets.bfcl_asset_preflight()
    official_grader_source_present = OFFICIAL_BFCL_GRADER_SOURCE.exists()
    deps = ("deepagents", "langchain_core", "langgraph", "langsmith")
    dep_availability = {name: importlib.util.find_spec(name) is not None for name in deps}
    blocker_codes = list(asset_preflight["blocker_codes"])
    if not all(dep_availability.values()):
        blocker_codes.append("missing_bfcl_native_runtime_dependencies")
    return {
        "native_runtime_available": not blocker_codes,
        "native_runtime_mode": "official_native_runtime" if not blocker_codes else "official_grader_only_no_model_runtime",
        "blocker_codes": blocker_codes,
        "missing_paths": list(asset_preflight["missing_paths"]),
        "selected_samples_path": asset_preflight["selected_sample_path"],
        "selected_apis_dir": asset_preflight["selected_apis_dir"],
        "sample_path_candidates": list(asset_preflight["sample_path_candidates"]),
        "api_dir_candidates": list(asset_preflight["api_dir_candidates"]),
        "official_grader_source_present": official_grader_source_present,
        "official_grader_source_ref": str(OFFICIAL_BFCL_GRADER_SOURCE),
        "official_model_runtime_dependencies": dep_availability,
    }


def build_task_pack(*, task_pack_id: str, case_id: str) -> dict[str, Any]:
    task_pack = {
        "task_id": task_pack_id,
        "task_prompt": f"Execute official BFCL v3 tool-call sequence for case {case_id}.",
        "fixture": {"type": "official_bfcl_case", "workspace_ref": f"bfcl/{case_id}"},
        "canonical_root": "/app",
        "backend_requirements": {
            "certified_default": "linux_container",
            "debug_backend": "debug_local_no_sandbox",
            "network": "disabled",
        },
        "visible_verifier": {"command": "python3 run_adapter.py --case-id <case_id>"},
        "hidden_verifier": {
            "command_shape": "python3 hidden_grader.py --case-id <case_id> --tool-call-log <artifact_ref>",
            "checks_ref": DEFAULT_HIDDEN_CHECKS_REF,
            "leak_hidden_checks_to_prompt": False,
        },
        "grader": {"type": "bfcl_native_official_state_replay", "score_range": [0, 1]},
        "contamination_policy": {
            "status": "clean",
            "source": "mirrored_official_bfcl_resource",
            "public_benchmark_row": True,
        },
        "artifact_capture_policy": {
            "capture": ["environment_manifest", "artifact_bundle", "verifier", "grader", "trace"]
        },
        "admission_level": "diagnostic",
        "surface_type": "tool_call",
        "benchmark_adapter_contract": {
            "adapter_label": ADAPTER_LABEL,
            "authority_label": ADAPTER_AUTHORITY_LABEL,
            "authority_detail": ADAPTER_AUTHORITY_DETAIL,
            "expected_answer_format": "tool_call_sequence",
            "hidden_truth_ref": DEFAULT_HIDDEN_CHECKS_REF,
            "official_grader_source_ref": str(OFFICIAL_BFCL_GRADER_SOURCE),
        },
    }
    return validate_task_pack(task_pack)


def build_benchmark_case(*, case_id: str, task_pack_id: str) -> dict[str, Any]:
    benchmark_case = {
        "benchmark_family": ADAPTER_FAMILY,
        "benchmark_case_id": case_id,
        "authority_label": ADAPTER_AUTHORITY_LABEL,
        "surface_type": "tool_call",
        "admission_level": "diagnostic",
        "expected_answer": {
            "format": "tool_call_sequence",
            "value": {"hidden_truth_ref": DEFAULT_HIDDEN_CHECKS_REF},
        },
        "contamination_labels": list(DEFAULT_CONTAMINATION_LABELS),
        "execution_unit": {
            "unit_id": f"{task_pack_id}::{case_id}",
            "task_prompt": f"Execute official BFCL v3 tool-call sequence for case {case_id}.",
            "canonical_root": "/app",
            "execution_contract": {
                "authority_detail": ADAPTER_AUTHORITY_DETAIL,
                "hidden_truth_ref": DEFAULT_HIDDEN_CHECKS_REF,
                "official_grader_source_ref": str(OFFICIAL_BFCL_GRADER_SOURCE),
            },
        },
    }
    return validate_benchmark_adapter_case(benchmark_case)


def grade_bfcl_case_native(case: dict[str, Any], observed_calls: list[str]) -> dict[str, Any]:
    expected_calls = flatten_ground_truth_calls(case)
    unsupported = sorted(
        class_name for class_name in case.get("involved_classes", []) if class_name not in _CLASS_IMPORTS
    )
    if unsupported:
        return {
            "verdict": "invalid",
            "reason_codes": ["bfcl_native_unsupported_classes"],
            "unsupported_classes": unsupported,
            "authority_label": ADAPTER_AUTHORITY_LABEL,
            "authority_detail": ADAPTER_AUTHORITY_DETAIL,
            "hidden_truth_ref": DEFAULT_HIDDEN_CHECKS_REF,
        }

    gt_instances = _instantiate_case_apis(case)
    observed_instances = _instantiate_case_apis(case)
    expected_errors = _replay_calls(gt_instances, expected_calls, suppress=True)
    observed_errors = _replay_calls(observed_instances, observed_calls, suppress=True)
    mismatch_fields = _state_mismatch_fields(observed_instances, gt_instances, case)

    reason_codes: list[str] = []
    if not observed_calls:
        reason_codes.append("bfcl_no_calls_emitted")
    if mismatch_fields:
        reason_codes.append("bfcl_state_mismatch")

    verdict = "pass" if not reason_codes else "fail"
    return {
        "verdict": verdict,
        "reason_codes": sorted(set(reason_codes)),
        "score": 1.0 if verdict == "pass" else 0.0,
        "expected_call_count": len(expected_calls),
        "observed_call_count": len(observed_calls),
        "expected_calls_hash": _hash_list([_normalize_call(call) for call in expected_calls]),
        "observed_calls_hash": _hash_list([_normalize_call(call) for call in observed_calls]),
        "expected_replay_error_hash": _hash_list(expected_errors),
        "observed_replay_error_hash": _hash_list(observed_errors),
        "expected_replay_error_count": len(expected_errors),
        "observed_replay_error_count": len(observed_errors),
        "state_mismatch_field_count": len(mismatch_fields),
        "state_mismatch_fields": mismatch_fields[:50],
        "state_mismatch_hash": _hash_list(mismatch_fields),
        "authority_label": ADAPTER_AUTHORITY_LABEL,
        "authority_detail": ADAPTER_AUTHORITY_DETAIL,
        "hidden_truth_ref": DEFAULT_HIDDEN_CHECKS_REF,
        "official_grader_source_ref": str(OFFICIAL_BFCL_GRADER_SOURCE),
    }


def build_result_row_for_grade(
    *,
    run_id: str,
    eval_id: str,
    task_pack_id: str,
    case_id: str,
    control_label: str,
    environment_ref: str,
    artifact_refs: list[str],
    trace_refs: list[str],
    verifier_ref: str,
    grader_ref: str,
    grade: dict[str, Any],
    backend_ref: str = "debug_local_no_sandbox",
) -> dict[str, Any]:
    verdict = str(grade["verdict"])
    row = build_adapter_result_row(
        run_id=run_id,
        eval_id=eval_id,
        task_pack_id=task_pack_id,
        backend_ref=backend_ref,
        environment_ref=environment_ref,
        verifier_ref=verifier_ref,
        grader_ref=grader_ref,
        benchmark_case=build_benchmark_case(case_id=case_id, task_pack_id=task_pack_id),
        native_grader_output=grade,
        trace_refs=trace_refs,
        artifact_refs=artifact_refs,
        failure_class="none" if verdict == "pass" else "tool_contract",
    )
    row["control_label"] = control_label
    row["adapter_label"] = ADAPTER_LABEL
    row["authority_detail"] = ADAPTER_AUTHORITY_DETAIL
    row["hidden_truth_ref"] = DEFAULT_HIDDEN_CHECKS_REF
    return validate_result_row(row)


def _instantiate_case_apis(case: dict[str, Any]) -> dict[str, Any]:
    _ensure_mirrored_api_import_path()
    instances: dict[str, Any] = {}
    for class_name in case.get("involved_classes", []):
        module_name, symbol = _CLASS_IMPORTS[class_name]
        module = importlib.import_module(module_name)
        cls = getattr(module, symbol)
        instance = cls()
        instance._load_scenario(copy.deepcopy(case.get("initial_config", {}).get(class_name, {})), long_context=False)
        instances[class_name] = instance
    return instances


def _replay_calls(instances: dict[str, Any], calls: list[str], *, suppress: bool) -> list[str]:
    methods: dict[str, Any] = {}
    for instance in instances.values():
        for method_name in instance.__class__.__dict__:
            if method_name.startswith("_"):
                continue
            method = getattr(instance, method_name, None)
            if callable(method):
                methods[method_name] = method
    errors: list[str] = []
    for index, raw_call in enumerate(calls):
        try:
            func, args, kwargs = _parse_safe_call_expression(_fix_bfcl_gt_call(raw_call))
            method = methods.get(func)
            if method is None:
                raise ValueError(f"unknown_method:{func}")
            method(*args, **kwargs)
        except Exception as exc:
            errors.append(f"{index}:{type(exc).__name__}")
            if not suppress:
                continue
    return errors


def _state_mismatch_fields(observed_instances: dict[str, Any], expected_instances: dict[str, Any], case: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for class_name in case.get("involved_classes", []):
        observed_inst = observed_instances[class_name]
        expected_inst = expected_instances[class_name]
        for attr_name in vars(expected_inst):
            if attr_name.startswith("_"):
                continue
            if _to_jsonable(getattr(observed_inst, attr_name)) != _to_jsonable(getattr(expected_inst, attr_name)):
                mismatches.append(f"{class_name}.{attr_name}")
    return mismatches


def _normalize_call(raw_call: str) -> str:
    stripped = _fix_bfcl_gt_call(raw_call.strip())
    try:
        parsed = ast.parse(stripped, mode="eval")
    except SyntaxError:
        return re.sub(r"\s+", " ", stripped)
    return ast.dump(parsed.body, annotate_fields=True, include_attributes=False)


def _hash_list(items: list[str]) -> str:
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def _fix_bfcl_gt_call(call_str: str) -> str:
    call_str = _SENDER_ID_SUFFIX.sub("", call_str)
    return _SENDER_ID_PREFIX.sub("", call_str)


def _ensure_mirrored_api_import_path() -> None:
    parent = str(bfcl_assets.resolve_bfcl_apis_dir().parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)


def _parse_safe_call_expression(raw_call: str) -> tuple[str, list[Any], dict[str, Any]]:
    parsed = ast.parse(raw_call.strip(), mode="eval")
    if not isinstance(parsed.body, ast.Call):
        raise ValueError("unsupported_expression")
    call = parsed.body
    if not isinstance(call.func, ast.Name):
        raise ValueError("unsupported_function_reference")
    args = [ast.literal_eval(node) for node in call.args]
    kwargs: dict[str, Any] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise ValueError("star_kwargs_not_supported")
        kwargs[str(keyword.arg)] = ast.literal_eval(keyword.value)
    return call.func.id, args, kwargs


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_to_jsonable(item) for item in value)
    return value
