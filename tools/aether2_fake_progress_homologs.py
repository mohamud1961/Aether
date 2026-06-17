#!/usr/bin/env python3
"""Deterministic custom homolog definitions and graders for fake-progress work.

This module is intentionally no-model and no-benchmark-execution. It defines
generic homolog eval metadata, materializes local synthetic fixtures, grades
candidate artifacts deterministically, and prepares reserved runner commands
for the later execution phase.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

MANIFEST_SCHEMA_VERSION = "aether2.fake_progress_homologs.v1"
BOARD_STATUS = "implementation_ready_not_run"
CONTROL_LABELS = ("ceiling", "known_bad", "baseline_reserved")


def _defs() -> list[dict[str, Any]]:
    return [
        {
            "eval_id": "fp_01_candidate_label_structure",
            "failure_family": "candidate_label_structure",
            "task_instruction": "Determine the rendered value and write it to out.txt.",
            "deliverable_path": "out.txt",
            "grader_id": "candidate_label_structure_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_01_candidate_label_structure --control baseline",
        },
        {
            "eval_id": "fp_02_circular_recovery_completeness",
            "failure_family": "circular_recovery_completeness",
            "task_instruction": "Recover all records and write them to recovered.json.",
            "deliverable_path": "recovered.json",
            "grader_id": "circular_recovery_completeness_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_02_circular_recovery_completeness --control baseline",
        },
        {
            "eval_id": "fp_03_constraint_preserving_edit",
            "failure_family": "constraint_preserving_edit",
            "task_instruction": "Fix the overflow symptom while preserving the allowed diff contract.",
            "deliverable_path": "draft_fixed.txt",
            "grader_id": "constraint_preserving_edit_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_03_constraint_preserving_edit --control baseline",
        },
        {
            "eval_id": "fp_04_semantic_matrix_artifact",
            "failure_family": "semantic_matrix_artifact",
            "task_instruction": "Produce the exact matrix in matrix.json.",
            "deliverable_path": "matrix.json",
            "grader_id": "semantic_matrix_artifact_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_04_semantic_matrix_artifact --control baseline",
        },
        {
            "eval_id": "fp_05_external_service_protocol",
            "failure_family": "external_service_protocol",
            "task_instruction": "Write a protocol_manifest.json that matches the external contract.",
            "deliverable_path": "protocol_manifest.json",
            "grader_id": "external_service_protocol_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_05_external_service_protocol --control baseline",
        },
        {
            "eval_id": "fp_06_final_state_inventory",
            "failure_family": "final_state_inventory",
            "task_instruction": "Prepare the final deliverable directory with only the allowed files.",
            "deliverable_path": "deliverables",
            "grader_id": "final_state_inventory_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_06_final_state_inventory --control baseline",
        },
        {
            "eval_id": "fp_07_exact_serialization_contract",
            "failure_family": "exact_serialization_contract",
            "task_instruction": "Write cells.json with the exact schema and types.",
            "deliverable_path": "cells.json",
            "grader_id": "exact_serialization_contract_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_07_exact_serialization_contract --control baseline",
        },
        {
            "eval_id": "fp_08_environment_map_plan",
            "failure_family": "environment_map_plan",
            "task_instruction": "Write execution_plan.json that respects the env contract.",
            "deliverable_path": "execution_plan.json",
            "grader_id": "environment_map_plan_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_08_environment_map_plan --control baseline",
        },
        {
            "eval_id": "fp_09_long_job_service_survival",
            "failure_family": "long_job_service_survival",
            "task_instruction": "Write service_evidence.json proving bounded survival and fresh-client validation.",
            "deliverable_path": "service_evidence.json",
            "grader_id": "long_job_service_survival_v1",
            "contamination_labels": ["clean", "custom_homolog", "synthetic_realistic"],
            "reserved_runner_command": "PYTHONPATH=. python3 tools/run_aether2_fake_progress_runner.py --eval-id fp_09_long_job_service_survival --control baseline",
        },
    ]


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "board_status": BOARD_STATUS,
        "controls_supported": list(CONTROL_LABELS),
        "evals": _defs(),
    }


def serialize_manifest(manifest: Mapping[str, Any] | None = None) -> str:
    payload = build_manifest() if manifest is None else dict(manifest)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def validate_manifest(manifest: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(manifest, Mapping):
        return {"status": "fail", "errors": ["manifest must be an object"], "manifest": {}}
    normalized = dict(manifest)
    if normalized.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")
    if normalized.get("board_status") != BOARD_STATUS:
        errors.append(f"board_status must be {BOARD_STATUS}")
    controls = normalized.get("controls_supported")
    if controls != list(CONTROL_LABELS):
        errors.append("controls_supported must exactly match ceiling, known_bad, baseline_reserved")
    evals = normalized.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append("evals must be a non-empty list")
        evals = []
    seen_ids: set[str] = set()
    for index, item in enumerate(evals):
        if not isinstance(item, Mapping):
            errors.append(f"evals[{index}] must be an object")
            continue
        eval_id = item.get("eval_id")
        if not isinstance(eval_id, str) or not eval_id.strip():
            errors.append(f"evals[{index}].eval_id must be a non-empty string")
            continue
        if eval_id in seen_ids:
            errors.append(f"duplicate eval_id: {eval_id}")
        seen_ids.add(eval_id)
        for field in ("failure_family", "task_instruction", "deliverable_path", "grader_id", "reserved_runner_command"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"evals[{index}].{field} must be a non-empty string")
        labels = item.get("contamination_labels")
        if not isinstance(labels, list) or not labels or not all(isinstance(label, str) and label for label in labels):
            errors.append(f"evals[{index}].contamination_labels must be a non-empty string list")
    return {"status": "pass" if not errors else "fail", "errors": errors, "manifest": normalized}


def materialize_fixture(eval_id: str, root: str | Path) -> Path:
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    for relative_path, payload in _fixture_seed(eval_id).items():
        target = root_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            target.write_text(payload, encoding="utf-8")
        else:
            target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root_path


def write_control_output(eval_id: str, control_label: str, root: str | Path) -> Path:
    if control_label not in CONTROL_LABELS:
        raise ValueError(f"unsupported control label: {control_label}")
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    if control_label == "baseline_reserved":
        (root_path / "BASELINE_RESERVED_NOT_RUN.txt").write_text(
            "Reserved for separate runner phase. Not executed in implementation-only scope.\n",
            encoding="utf-8",
        )
        return root_path
    payload = _control_output(eval_id, control_label)
    for relative_path, value in payload.items():
        target = root_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            target.write_text(value, encoding="utf-8")
        else:
            target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root_path


def grade_eval(eval_id: str, root: str | Path) -> dict[str, Any]:
    workspace = Path(root)
    graders = {
        "fp_01_candidate_label_structure": _grade_candidate_label_structure,
        "fp_02_circular_recovery_completeness": _grade_circular_recovery_completeness,
        "fp_03_constraint_preserving_edit": _grade_constraint_preserving_edit,
        "fp_04_semantic_matrix_artifact": _grade_semantic_matrix_artifact,
        "fp_05_external_service_protocol": _grade_external_service_protocol,
        "fp_06_final_state_inventory": _grade_final_state_inventory,
        "fp_07_exact_serialization_contract": _grade_exact_serialization_contract,
        "fp_08_environment_map_plan": _grade_environment_map_plan,
        "fp_09_long_job_service_survival": _grade_long_job_service_survival,
    }
    grader = graders[eval_id]
    return grader(workspace)


def build_control_row(eval_id: str, control_label: str, root: str | Path) -> dict[str, Any]:
    if control_label == "baseline_reserved":
        return {
            "eval_id": eval_id,
            "control_label": control_label,
            "row_status": "not_run_reserved",
            "scoreable": False,
            "reason_codes": ["reserved_for_runner_phase"],
            "artifact_root": str(Path(root)),
        }
    grade = grade_eval(eval_id, root)
    return {
        "eval_id": eval_id,
        "control_label": control_label,
        "row_status": "pass" if grade["verdict"] == "pass" else "fail",
        "scoreable": True,
        "reason_codes": list(grade["reason_codes"]),
        "artifact_root": str(Path(root)),
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _pass(message: str) -> dict[str, Any]:
    return {"verdict": "pass", "reason_codes": [], "summary": message}


def _fail(*codes: str) -> dict[str, Any]:
    return {"verdict": "fail", "reason_codes": list(codes), "summary": ", ".join(codes)}


def _fixture_seed(eval_id: str) -> dict[str, Any]:
    fixtures: dict[str, dict[str, Any]] = {
        "fp_01_candidate_label_structure": {
            "visible_label.txt": "Facet Marker\n",
            "layout.json": {"rendered_text": "flag{layered-proof}"},
        },
        "fp_02_circular_recovery_completeness": {
            "partial_records.json": [{"id": 1}, {"id": 2}, {"id": 3}],
            "full_records.json": [{"id": index} for index in range(1, 9)],
        },
        "fp_03_constraint_preserving_edit": {
            "draft.txt": "alpha beta gamma overflow\n",
            "allowed_replacements.json": {"overflow": "fitted"},
        },
        "fp_04_semantic_matrix_artifact": {
            "expected_matrix.json": {"rows": [[2, 1], [0, 3], [4, 5]]},
        },
        "fp_05_external_service_protocol": {
            "service_contract.json": {
                "service": "LedgerStore",
                "rpc_fields": {"SetValueRequest": ["key", "value"], "SetValueResponse": ["value"]},
            },
        },
        "fp_06_final_state_inventory": {
            "allowed_inventory.json": {"required": ["deliverables/app.bin"], "forbidden_suffixes": [".tmp", ".helper"]},
        },
        "fp_07_exact_serialization_contract": {
            "schema.json": {"required_keys": ["coords_x", "coords_y"], "coords_type": "list[int]"},
        },
        "fp_08_environment_map_plan": {
            "env_contract.json": {
                "source_path": "/workspace/src/toolx",
                "writable_install_root": "/opt/harness/bin",
                "non_writable_root": "/usr/local/bin",
                "fresh_process_executable": "python3.11",
            },
        },
        "fp_09_long_job_service_survival": {
            "expected_evidence.json": {"minimum_survival_sec": 8, "required_status": "ready", "fresh_client_validation": True},
        },
    }
    return fixtures[eval_id]


def _control_output(eval_id: str, control_label: str) -> dict[str, Any]:
    controls: dict[str, dict[str, dict[str, Any]]] = {
        "fp_01_candidate_label_structure": {
            "ceiling": {"out.txt": "flag{layered-proof}\n"},
            "known_bad": {"out.txt": "Facet Marker\n"},
        },
        "fp_02_circular_recovery_completeness": {
            "ceiling": {"recovered.json": [{"id": index} for index in range(1, 9)]},
            "known_bad": {"recovered.json": [{"id": 1}, {"id": 2}, {"id": 3}]},
        },
        "fp_03_constraint_preserving_edit": {
            "ceiling": {"draft_fixed.txt": "alpha beta gamma fitted\n"},
            "known_bad": {"draft_fixed.txt": "alpha beta gamma\n"},
        },
        "fp_04_semantic_matrix_artifact": {
            "ceiling": {"matrix.json": {"rows": [[2, 1], [0, 3], [4, 5]]}},
            "known_bad": {"matrix.json": {"rows": [[0, 0], [0, 0], [0, 0]]}},
        },
        "fp_05_external_service_protocol": {
            "ceiling": {
                "protocol_manifest.json": {
                    "service": "LedgerStore",
                    "rpc_fields": {"SetValueRequest": ["key", "value"], "SetValueResponse": ["value"]},
                }
            },
            "known_bad": {
                "protocol_manifest.json": {
                    "service": "LedgerStore",
                    "rpc_fields": {"SetValueRequest": ["key", "val"], "SetValueResponse": ["val"]},
                }
            },
        },
        "fp_06_final_state_inventory": {
            "ceiling": {"deliverables/app.bin": "ready\n"},
            "known_bad": {"deliverables/app.bin": "ready\n", "deliverables/debug.helper": "extra\n"},
        },
        "fp_07_exact_serialization_contract": {
            "ceiling": {"cells.json": {"coords_x": [1, 2], "coords_y": [3, 4]}},
            "known_bad": {"cells.json": {"coords_x": "1,2", "coords_y": [3, 4]}},
        },
        "fp_08_environment_map_plan": {
            "ceiling": {
                "execution_plan.json": {
                    "source_path": "/workspace/src/toolx",
                    "install_path": "/opt/harness/bin/toolx",
                    "fresh_process_executable": "python3.11",
                }
            },
            "known_bad": {
                "execution_plan.json": {
                    "source_path": "/workspace/src/toolx",
                    "install_path": "/usr/local/bin/toolx",
                    "fresh_process_executable": "python3",
                }
            },
        },
        "fp_09_long_job_service_survival": {
            "ceiling": {
                "service_evidence.json": {
                    "status": "ready",
                    "survived_window_sec": 12,
                    "fresh_client_validation": True,
                }
            },
            "known_bad": {
                "service_evidence.json": {
                    "status": "ready",
                    "survived_window_sec": 1,
                    "fresh_client_validation": False,
                }
            },
        },
    }
    return controls[eval_id][control_label]


def _grade_candidate_label_structure(workspace: Path) -> dict[str, Any]:
    expected = _read_json(workspace / "layout.json")["rendered_text"]
    actual = (workspace / "out.txt").read_text(encoding="utf-8").strip()
    return _pass("rendered value matches structural source") if actual == expected else _fail("candidate_label_selected")


def _grade_circular_recovery_completeness(workspace: Path) -> dict[str, Any]:
    expected = _read_json(workspace / "full_records.json")
    actual = _read_json(workspace / "recovered.json")
    return _pass("all records recovered") if actual == expected else _fail("recovery_incomplete_or_circular")


def _grade_constraint_preserving_edit(workspace: Path) -> dict[str, Any]:
    original = (workspace / "draft.txt").read_text(encoding="utf-8").strip().split()
    fixed = (workspace / "draft_fixed.txt").read_text(encoding="utf-8").strip().split()
    allowed = _read_json(workspace / "allowed_replacements.json")
    if len(original) != len(fixed):
        return _fail("constraint_word_count_changed")
    for before, after in zip(original, fixed):
        if before == after:
            continue
        if allowed.get(before) != after:
            return _fail("constraint_disallowed_rewrite")
    if "overflow" in fixed:
        return _fail("overflow_symptom_persisted")
    return _pass("symptom removed with allowed replacements only")


def _grade_semantic_matrix_artifact(workspace: Path) -> dict[str, Any]:
    expected = _read_json(workspace / "expected_matrix.json")
    actual = _read_json(workspace / "matrix.json")
    return _pass("semantic matrix matches") if actual == expected else _fail("matrix_semantics_mismatch")


def _grade_external_service_protocol(workspace: Path) -> dict[str, Any]:
    expected = _read_json(workspace / "service_contract.json")
    actual = _read_json(workspace / "protocol_manifest.json")
    return _pass("protocol contract matches external client expectation") if actual == expected else _fail("protocol_field_mismatch")


def _grade_final_state_inventory(workspace: Path) -> dict[str, Any]:
    policy = _read_json(workspace / "allowed_inventory.json")
    required = set(policy["required"])
    forbidden_suffixes = tuple(policy["forbidden_suffixes"])
    actual_files = {
        str(path.relative_to(workspace))
        for path in workspace.rglob("*")
        if path.is_file() and path.name not in {"allowed_inventory.json"}
    }
    if not required.issubset(actual_files):
        return _fail("missing_required_final_artifact")
    if any(path.endswith(forbidden_suffixes) for path in actual_files):
        return _fail("forbidden_helper_artifact_present")
    return _pass("final inventory is clean")


def _grade_exact_serialization_contract(workspace: Path) -> dict[str, Any]:
    schema = _read_json(workspace / "schema.json")
    actual = _read_json(workspace / "cells.json")
    for key in schema["required_keys"]:
        value = actual.get(key)
        if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
            return _fail("serialization_type_mismatch")
    return _pass("serialization contract matches exact type requirements")


def _grade_environment_map_plan(workspace: Path) -> dict[str, Any]:
    contract = _read_json(workspace / "env_contract.json")
    actual = _read_json(workspace / "execution_plan.json")
    expected_install = f"{contract['writable_install_root']}/toolx"
    if actual.get("source_path") != contract["source_path"]:
        return _fail("source_path_mismatch")
    if actual.get("install_path") != expected_install:
        return _fail("install_target_not_grader_visible")
    if actual.get("fresh_process_executable") != contract["fresh_process_executable"]:
        return _fail("fresh_process_executable_mismatch")
    return _pass("environment map plan respects writable and grader-visible paths")


def _grade_long_job_service_survival(workspace: Path) -> dict[str, Any]:
    expected = _read_json(workspace / "expected_evidence.json")
    actual = _read_json(workspace / "service_evidence.json")
    if actual.get("status") != expected["required_status"]:
        return _fail("service_not_ready")
    if int(actual.get("survived_window_sec", 0)) < int(expected["minimum_survival_sec"]):
        return _fail("service_did_not_survive_window")
    if bool(actual.get("fresh_client_validation")) is not bool(expected["fresh_client_validation"]):
        return _fail("fresh_client_validation_missing")
    return _pass("bounded survival and fresh-client validation proved")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-manifest", action="store_true")
    parser.add_argument("--validate-manifest", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_manifest()
    if args.validate_manifest:
        print(json.dumps(validate_manifest(manifest), indent=2, sort_keys=True))
        return 0
    if args.print_manifest:
        print(serialize_manifest(manifest), end="")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
