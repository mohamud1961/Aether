"""Validate preregistered targeted-board manifests and scheduler policy."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

BOARD_SCHEMA_VERSION = "aether2.targeted_board.v1"
BOARD_REGISTRATION_STATUS = "preregistered_only"
BOARD_EXECUTION_STATE = "not_executed"

MAX_TASKS = 10
MAX_LIGHT_CONTAINERS = 3
MAX_HEAVY_BUILDS = 1
MAX_QEMU_SERVICE_TASKS = 1

REQUIRED_TASK_FIELDS = (
    "task_id",
    "failure_family",
    "reason_selected",
    "expected_capability_pressure",
    "baseline_evidence",
    "predicted_change",
    "named_sentinels",
    "resource_class",
    "timeout_seconds",
    "contamination_controls",
)

RESOURCE_CLASSES = (
    "light_container",
    "heavy_build",
    "qemu_service_sensitive",
)

REQUIRED_PREFLIGHTS = ("disk_pressure", "process_pressure")
REQUIRED_OUTPUT_DIR_TEMPLATE_FIELDS = ("{board_id}", "{task_id}")


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, field_path: str, errors: list[str]) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(f"{field_path} must be a list of non-empty strings")
        return []

    items: list[str] = []
    for index, item in enumerate(value):
        if not _is_nonempty_string(item):
            errors.append(f"{field_path}[{index}] must be a non-empty string")
            continue
        items.append(item.strip())
    if not items:
        errors.append(f"{field_path} must not be empty")
    return items


def _evidence_list(value: Any, *, field_path: str, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(f"{field_path} must be a list of evidence objects")
        return []

    evidence_items: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            errors.append(f"{field_path}[{index}] must be an object")
            continue
        kind = item.get("kind")
        ref = item.get("ref")
        if not _is_nonempty_string(kind):
            errors.append(f"{field_path}[{index}].kind must be a non-empty string")
        if not _is_nonempty_string(ref):
            errors.append(f"{field_path}[{index}].ref must be a non-empty string")
        evidence_items.append({**item, "kind": str(kind).strip(), "ref": str(ref).strip()})
    if not evidence_items:
        errors.append(f"{field_path} must not be empty")
    return evidence_items


def _require_nonnegative_int(value: Any, *, field_path: str, max_value: int, errors: list[str]) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{field_path} must be an integer")
        return None
    if value < 0:
        errors.append(f"{field_path} must be non-negative")
    elif value > max_value:
        errors.append(f"{field_path} must be <= {max_value}")
    return value


def _validate_task(task: Any, index: int) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(task, Mapping):
        return {}, [f"tasks[{index}] must be an object"]

    normalized = dict(task)
    task_id = normalized.get("task_id")
    if not _is_nonempty_string(task_id):
        errors.append(f"tasks[{index}].task_id must be a non-empty string")
    else:
        normalized["task_id"] = task_id.strip()

    for field in REQUIRED_TASK_FIELDS[1:]:
        if field not in normalized:
            errors.append(f"tasks[{index}].{field} is required")

    for field in ("failure_family", "reason_selected", "expected_capability_pressure", "predicted_change"):
        value = normalized.get(field)
        if not _is_nonempty_string(value):
            errors.append(f"tasks[{index}].{field} must be a non-empty string")
        else:
            normalized[field] = value.strip()

    normalized["baseline_evidence"] = _evidence_list(
        normalized.get("baseline_evidence"),
        field_path=f"tasks[{index}].baseline_evidence",
        errors=errors,
    )
    normalized["named_sentinels"] = _string_list(
        normalized.get("named_sentinels"),
        field_path=f"tasks[{index}].named_sentinels",
        errors=errors,
    )
    normalized["contamination_controls"] = _string_list(
        normalized.get("contamination_controls"),
        field_path=f"tasks[{index}].contamination_controls",
        errors=errors,
    )

    resource_class = normalized.get("resource_class")
    if not _is_nonempty_string(resource_class):
        errors.append(f"tasks[{index}].resource_class must be a non-empty string")
    else:
        resource_class = resource_class.strip()
        if resource_class not in RESOURCE_CLASSES:
            errors.append(
                f"tasks[{index}].resource_class must be one of {RESOURCE_CLASSES}"
            )
        normalized["resource_class"] = resource_class

    timeout_seconds = normalized.get("timeout_seconds")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
        errors.append(f"tasks[{index}].timeout_seconds must be a positive integer")

    return normalized, errors


def validate_targeted_board_scheduler(scheduler: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(scheduler, Mapping):
        return {"status": "fail", "errors": ["scheduler must be an object"], "scheduler": {}}

    normalized = dict(scheduler)

    concurrency_limits = normalized.get("concurrency_limits")
    if not isinstance(concurrency_limits, Mapping):
        errors.append("scheduler.concurrency_limits must be an object")
        normalized_limits: dict[str, Any] = {}
    else:
        normalized_limits = dict(concurrency_limits)
        _require_nonnegative_int(
            normalized_limits.get("light_containers"),
            field_path="scheduler.concurrency_limits.light_containers",
            max_value=MAX_LIGHT_CONTAINERS,
            errors=errors,
        )
        _require_nonnegative_int(
            normalized_limits.get("heavy_builds"),
            field_path="scheduler.concurrency_limits.heavy_builds",
            max_value=MAX_HEAVY_BUILDS,
            errors=errors,
        )
        _require_nonnegative_int(
            normalized_limits.get("qemu_service_sensitive"),
            field_path="scheduler.concurrency_limits.qemu_service_sensitive",
            max_value=MAX_QEMU_SERVICE_TASKS,
            errors=errors,
        )
    normalized["concurrency_limits"] = normalized_limits

    preflight_checks = _string_list(
        normalized.get("preflight_checks"),
        field_path="scheduler.preflight_checks",
        errors=errors,
    )
    if not set(REQUIRED_PREFLIGHTS).issubset(set(preflight_checks)):
        errors.append("scheduler.preflight_checks must include disk_pressure and process_pressure")
    normalized["preflight_checks"] = preflight_checks

    cleanup_scope = normalized.get("cleanup_scope")
    if cleanup_scope != "attributable_resources_only":
        errors.append("scheduler.cleanup_scope must be attributable_resources_only")

    output_dir_policy = normalized.get("output_dir_policy")
    if not isinstance(output_dir_policy, Mapping):
        errors.append("scheduler.output_dir_policy must be an object")
        normalized_output_policy: dict[str, Any] = {}
    else:
        normalized_output_policy = dict(output_dir_policy)
        if normalized_output_policy.get("mode") != "immutable_per_task_attempt":
            errors.append("scheduler.output_dir_policy.mode must be immutable_per_task_attempt")

        task_template = normalized_output_policy.get("task_root_template")
        if not _is_nonempty_string(task_template):
            errors.append("scheduler.output_dir_policy.task_root_template must be a non-empty string")
        else:
            task_template = task_template.strip()
            missing = [token for token in REQUIRED_OUTPUT_DIR_TEMPLATE_FIELDS if token not in task_template]
            if missing:
                errors.append(
                    "scheduler.output_dir_policy.task_root_template must contain {board_id} and {task_id}"
                )
            if "{attempt_id}" in task_template:
                errors.append(
                    "scheduler.output_dir_policy.task_root_template must not contain {attempt_id}"
                )
            normalized_output_policy["task_root_template"] = task_template

        attempt_template = normalized_output_policy.get("attempt_root_template")
        if not _is_nonempty_string(attempt_template):
            errors.append("scheduler.output_dir_policy.attempt_root_template must be a non-empty string")
        else:
            attempt_template = attempt_template.strip()
            required_tokens = ("{board_id}", "{task_id}", "{attempt_id}")
            if not all(token in attempt_template for token in required_tokens):
                errors.append(
                    "scheduler.output_dir_policy.attempt_root_template must contain {board_id}, {task_id}, and {attempt_id}"
                )
            normalized_output_policy["attempt_root_template"] = attempt_template
    normalized["output_dir_policy"] = normalized_output_policy

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "scheduler": normalized,
    }


def validate_targeted_board_manifest(manifest: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(manifest, Mapping):
        return {"status": "fail", "errors": ["manifest must be an object"], "manifest": {}}

    normalized = dict(manifest)

    schema_version = normalized.get("schema_version")
    if schema_version != BOARD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {BOARD_SCHEMA_VERSION}")

    board_id = normalized.get("board_id")
    if not _is_nonempty_string(board_id):
        errors.append("board_id must be a non-empty string")
    else:
        normalized["board_id"] = board_id.strip()

    registration_status = normalized.get("registration_status")
    if registration_status != BOARD_REGISTRATION_STATUS:
        errors.append(f"registration_status must be {BOARD_REGISTRATION_STATUS}")

    execution_state = normalized.get("execution_state")
    if execution_state != BOARD_EXECUTION_STATE:
        errors.append(f"execution_state must be {BOARD_EXECUTION_STATE}")

    tasks = normalized.get("tasks")
    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)):
        errors.append("tasks must be a list")
        normalized_tasks: list[dict[str, Any]] = []
    else:
        normalized_tasks = []
        if len(tasks) > MAX_TASKS:
            errors.append(f"tasks must contain at most {MAX_TASKS} tasks")
        seen_task_ids: set[str] = set()
        for index, task in enumerate(tasks):
            normalized_task, task_errors = _validate_task(task, index)
            errors.extend(task_errors)
            task_id = normalized_task.get("task_id")
            if _is_nonempty_string(task_id):
                task_id = task_id.strip()
                if task_id in seen_task_ids:
                    errors.append(f"tasks[{index}].task_id duplicates {task_id!r}")
                else:
                    seen_task_ids.add(task_id)
                normalized_task["task_id"] = task_id
            normalized_tasks.append(normalized_task)
    normalized["tasks"] = normalized_tasks

    scheduler_report = validate_targeted_board_scheduler(normalized.get("scheduler"))
    errors.extend(scheduler_report["errors"])
    normalized["scheduler"] = scheduler_report["scheduler"]

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "manifest": normalized,
    }


def serialize_targeted_board_scheduler(scheduler: Any) -> str:
    report = validate_targeted_board_scheduler(scheduler)
    if report["status"] != "pass":
        raise ValueError("; ".join(report["errors"]))
    return json.dumps(report["scheduler"], indent=2, sort_keys=True)


def serialize_targeted_board_manifest(manifest: Any) -> str:
    report = validate_targeted_board_manifest(manifest)
    if report["status"] != "pass":
        raise ValueError("; ".join(report["errors"]))
    return json.dumps(report["manifest"], indent=2, sort_keys=True)


def build_targeted_board_run_manifest(
    manifest: Any,
    *,
    output_root: str | Path | None = None,
    execution_state: str = "prepared",
) -> dict[str, Any]:
    report = validate_targeted_board_manifest(manifest)
    if report["status"] != "pass":
        raise ValueError("; ".join(report["errors"]))

    normalized = report["manifest"]
    scheduler = normalized["scheduler"]
    tasks: list[dict[str, Any]] = []
    for task in normalized["tasks"]:
        baseline_refs = []
        for evidence in task.get("baseline_evidence", ()) or ():
            if isinstance(evidence, Mapping):
                ref = evidence.get("ref")
                if isinstance(ref, str) and ref.strip():
                    baseline_refs.append(ref.strip())
        tasks.append(
            {
                "task_id": task["task_id"],
                "failure_family": task["failure_family"],
                "resource_class": task["resource_class"],
                "timeout_seconds": task["timeout_seconds"],
                "named_sentinels": list(task["named_sentinels"]),
                "contamination_controls": list(task["contamination_controls"]),
                "baseline_evidence_refs": baseline_refs,
            }
        )

    run_manifest = {
        "manifest_type": "aether2_targeted_board_run_manifest",
        "manifest_version": 1,
        "schema_version": BOARD_SCHEMA_VERSION,
        "board_id": normalized["board_id"],
        "registration_status": normalized["registration_status"],
        "execution_state": execution_state,
        "output_root": str(output_root) if output_root is not None else None,
        "task_count": len(tasks),
        "cleanup_scope": scheduler["cleanup_scope"],
        "scheduler": scheduler,
        "tasks": tasks,
    }
    return run_manifest


def build_example_targeted_board_manifest() -> dict[str, Any]:
    return {
        "schema_version": BOARD_SCHEMA_VERSION,
        "board_id": "aether2_g5_targeted_board_preregistration",
        "registration_status": BOARD_REGISTRATION_STATUS,
        "execution_state": BOARD_EXECUTION_STATE,
        "scheduler": {
            "concurrency_limits": {
                "light_containers": MAX_LIGHT_CONTAINERS,
                "heavy_builds": MAX_HEAVY_BUILDS,
                "qemu_service_sensitive": MAX_QEMU_SERVICE_TASKS,
            },
            "preflight_checks": list(REQUIRED_PREFLIGHTS),
            "cleanup_scope": "attributable_resources_only",
            "output_dir_policy": {
                "mode": "immutable_per_task_attempt",
                "task_root_template": "runs/{board_id}/{task_id}",
                "attempt_root_template": "runs/{board_id}/{task_id}/attempt-{attempt_id}",
            },
        },
        "tasks": [
            {
                "task_id": "task_workspace_rooting",
                "failure_family": "workspace_root_contract",
                "reason_selected": "baseline evidence shows the task depends on stable workspace rooting",
                "expected_capability_pressure": "workspace normalization and artifact isolation",
                "baseline_evidence": [
                    {
                        "kind": "trace",
                        "ref": "tracking/collab/aether2_g5_implementation_orchestration_20260613/evidence/task_workspace_rooting/baseline_trace.jsonl",
                    },
                    {
                        "kind": "row",
                        "ref": "tracking/collab/aether2_g5_implementation_orchestration_20260613/evidence/task_workspace_rooting/baseline_row.json",
                    },
                ],
                "predicted_change": "normalize workspace resolution and preserve per-attempt output separation",
                "named_sentinels": [
                    "workspace-root-resolution",
                    "attempt-output-isolation",
                    "cleanup-attribution",
                ],
                "resource_class": "light_container",
                "timeout_seconds": 900,
                "contamination_controls": [
                    "fresh workspace per attempt",
                    "no shared temporary tree",
                ],
            },
            {
                "task_id": "task_build_pressure",
                "failure_family": "build_dependency_pressure",
                "reason_selected": "baseline evidence points to slow or fragile build orchestration",
                "expected_capability_pressure": "build coordination and artifact determinism",
                "baseline_evidence": [
                    {
                        "kind": "trace",
                        "ref": "tracking/collab/aether2_g5_implementation_orchestration_20260613/evidence/task_build_pressure/baseline_trace.jsonl",
                    },
                    {
                        "kind": "row",
                        "ref": "tracking/collab/aether2_g5_implementation_orchestration_20260613/evidence/task_build_pressure/baseline_row.json",
                    },
                ],
                "predicted_change": "reduce build churn and stabilize generated artifacts",
                "named_sentinels": [
                    "build-pressure-guard",
                    "artifact-determinism",
                ],
                "resource_class": "heavy_build",
                "timeout_seconds": 3600,
                "contamination_controls": [
                    "clean build tree",
                    "discard reused object files",
                ],
            },
            {
                "task_id": "task_service_serialization",
                "failure_family": "service_boot_serialization",
                "reason_selected": "baseline evidence suggests service startup is race-sensitive",
                "expected_capability_pressure": "service sequencing and teardown hygiene",
                "baseline_evidence": [
                    {
                        "kind": "trace",
                        "ref": "tracking/collab/aether2_g5_implementation_orchestration_20260613/evidence/task_service_serialization/baseline_trace.jsonl",
                    },
                    {
                        "kind": "row",
                        "ref": "tracking/collab/aether2_g5_implementation_orchestration_20260613/evidence/task_service_serialization/baseline_row.json",
                    },
                ],
                "predicted_change": "serialize service-sensitive setup and cleanly release shared state",
                "named_sentinels": [
                    "service-start-order",
                    "qemu-slot-serialization",
                    "state-teardown-attribution",
                ],
                "resource_class": "qemu_service_sensitive",
                "timeout_seconds": 2400,
                "contamination_controls": [
                    "exclusive service slot",
                    "per-attempt state directory",
                ],
            },
        ],
    }
