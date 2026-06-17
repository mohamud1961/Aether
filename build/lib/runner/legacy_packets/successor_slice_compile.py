"""Compile-only validator for the amended successor reference-harness slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runner.eval_runner_router import route_eval_card
from runner.packet03_eval_fixtures import get_packet03_eval_lane_policy, materialize_packet03_eval_fixture
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    SUCCESSOR_SLICE1_ALLOWED_VARIANTS,
    SUCCESSOR_SLICE1_ROUTE_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import SchemaValidationError, utc_now, validate_evaluation_lane, validate_route_manifest

DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)

REFERENCE_COMPOSITION_ID = "successor_reference_harness_seed.slice1.rhv1"
REFERENCE_VARIANT_ID = "rhv1_ref_01"
PRIMARY_COMPARATOR_VARIANT_ID = "spb_01"
COMPLETION_CONTROL_VARIANT_IDS = frozenset({"rh1_no_completion_01", "rhv1_no_completion_01"})
COMPILE_CONTRACT_VERSION = "successor_slice1_compile.v2"

SLICE_ONE_CONTROL_BOARD = (
    {
        "board_entry_id": "legacy_visibility_control",
        "variant_id": BASELINE_VARIANT_ID,
        "expected_changed_runtime_keys": [],
    },
    {
        "board_entry_id": "primary_prompt_comparator",
        "variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
        "expected_changed_runtime_keys": ["orientation"],
    },
    {
        "board_entry_id": "rhv1_reference",
        "variant_id": REFERENCE_VARIANT_ID,
        "expected_changed_runtime_keys": ["context", "execution", "orientation", "recovery", "terminal_guard", "verification"],
    },
    {
        "board_entry_id": "rhv1_ablate_env",
        "variant_id": "rhv1_ablate_env_01",
        "expected_changed_runtime_keys": ["context", "execution", "recovery", "terminal_guard", "verification"],
    },
    {
        "board_entry_id": "rhv1_ablate_state",
        "variant_id": "rhv1_ablate_state_01",
        "expected_changed_runtime_keys": ["execution", "orientation", "recovery", "terminal_guard", "verification"],
    },
    {
        "board_entry_id": "rhv1_ablate_evidence",
        "variant_id": "rhv1_ablate_evidence_01",
        "expected_changed_runtime_keys": ["context", "execution", "orientation", "recovery", "terminal_guard", "verification"],
    },
    {
        "board_entry_id": "completion_control",
        "variant_id": "rh1_no_completion_01",
        "expected_changed_runtime_keys": ["context", "execution", "orientation", "recovery", "terminal_guard"],
    },
)

SLICE_ONE_EVAL_BINDINGS = (
    {
        "eval_id": "ae_internal_discovery_evidence_efficiency_v1",
        "evaluation_lane": "promotion",
        "execution_mode": "multistep_batchable",
        "primary_comparator_variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
        "legacy_visibility_comparator_variant_id": BASELINE_VARIANT_ID,
    },
    {
        "eval_id": "ae_internal_multifile_repair_test_verify_v1",
        "evaluation_lane": "promotion",
        "execution_mode": "multistep_batchable",
        "primary_comparator_variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
        "legacy_visibility_comparator_variant_id": BASELINE_VARIANT_ID,
    },
    {
        "eval_id": "ae_sync_interrupt_cleanup_probe",
        "evaluation_lane": "bounded_diagnostic",
        "execution_mode": "sync_interactive",
        "primary_comparator_variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
        "legacy_visibility_comparator_variant_id": BASELINE_VARIANT_ID,
    },
    {
        "eval_id": "ae_completion_verifier_final_contradiction_probe",
        "evaluation_lane": "bounded_diagnostic",
        "execution_mode": "offline_judge_batchable",
        "primary_comparator_variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
        "legacy_visibility_comparator_variant_id": BASELINE_VARIANT_ID,
    },
)


def compile_successor_slice_one(
    *,
    output_dir: str | Path,
    eval_cards_path: str | Path = DEFAULT_EVAL_CARDS_PATH,
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    baseline_manifest = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
    validate_route_manifest(baseline_manifest)
    load_runtime_callables(baseline_manifest)

    control_board = _build_control_board_manifests(
        baseline_manifest=baseline_manifest,
        checks=checks,
        errors=errors,
    )
    board_variant_ids = {row["variant_id"] for row in control_board}
    _check_control_board_guards(board_variant_ids=board_variant_ids, checks=checks, errors=errors)

    reference_manifest = next((row for row in control_board if row["variant_id"] == REFERENCE_VARIANT_ID), None)
    if reference_manifest is None:
        errors.append(f"reference variant missing from compiled board: {REFERENCE_VARIANT_ID}")
        _append_check(checks, "reference_composition", False, "reference variant missing")
        reference_composition = _build_reference_composition_manifest(baseline_manifest)
    else:
        reference_composition = _build_reference_composition_manifest(reference_manifest["route_manifest"])
        _append_check(checks, "reference_composition", True, "reference composition manifest validated")

    _require_keys(
        reference_composition,
        required=("composition_id", "route_scope", "reference_variant_id", "runtime_module_import_paths"),
        label="reference_composition",
    )

    eval_cards = _load_eval_cards(Path(eval_cards_path))
    lane_bindings = _validate_lane_bindings_and_contracts(
        eval_cards=eval_cards,
        output_root=output_root,
        board_variant_ids=board_variant_ids,
        checks=checks,
        errors=errors,
    )

    _write_json(output_root / "reference_harness_composition.json", reference_composition)
    _write_json(output_root / "ablation_manifests.json", {"controls": control_board})
    _write_json(output_root / "eval_board_lane_bindings.json", {"bindings": lane_bindings["bindings"]})
    _write_json(output_root / "fixture_grader_comparator_contracts.json", lane_bindings["contracts"])

    report = {
        "compile_contract_version": COMPILE_CONTRACT_VERSION,
        "compiled_at_utc": utc_now(),
        "scope": SUCCESSOR_SLICE1_ROUTE_SCOPE,
        "reference_composition": reference_composition,
        "ablation_manifests": control_board,
        "eval_board_lane_bindings": lane_bindings["bindings"],
        "fixture_grader_comparator_contracts": lane_bindings["contracts"],
        "checks": checks,
        "errors": errors,
        "status": "pass" if not errors else "fail",
    }
    _write_json(output_root / "compile_report.json", report)
    return report


def _build_reference_composition_manifest(reference_manifest: dict[str, Any]) -> dict[str, Any]:
    runtime_map = {entry["runtime_key"]: entry["module_import_path"] for entry in reference_manifest["routed_modules"]}
    return {
        "composition_id": REFERENCE_COMPOSITION_ID,
        "route_scope": SUCCESSOR_SLICE1_ROUTE_SCOPE,
        "reference_variant_id": reference_manifest["variant_id"],
        "primary_comparator_variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
        "legacy_visibility_comparator_variant_id": BASELINE_VARIANT_ID,
        "route_manifest_version": reference_manifest["route_manifest_version"],
        "route_manifest_fingerprint": reference_manifest["route_manifest_fingerprint"],
        "runtime_module_import_paths": runtime_map,
    }


def _build_control_board_manifests(
    *,
    baseline_manifest: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    for plan in SLICE_ONE_CONTROL_BOARD:
        variant_id = plan["variant_id"]
        expected_runtime_keys = sorted(plan["expected_changed_runtime_keys"])
        check_id = f"control_board:{plan['board_entry_id']}"

        if variant_id not in SUCCESSOR_SLICE1_ALLOWED_VARIANTS:
            errors.append(f"control-board variant is out of scope: {variant_id}")
            _append_check(checks, check_id, False, "control-board variant out of scope")
            continue

        try:
            candidate_manifest = build_packet04_route_manifest(variant_id, scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
            validate_route_manifest(candidate_manifest)
            load_runtime_callables(candidate_manifest)
            if variant_id != BASELINE_VARIANT_ID:
                validate_independent_candidate_routing(
                    candidate_manifest=candidate_manifest,
                    baseline_manifest=baseline_manifest,
                )
        except Exception as err:  # pragma: no cover - defensive compile reporting
            errors.append(f"control-board manifest failed for variant_id={variant_id}: {err}")
            _append_check(checks, check_id, False, "control-board manifest failed")
            controls.append(
                {
                    "board_entry_id": plan["board_entry_id"],
                    "variant_id": variant_id,
                    "expected_changed_runtime_keys": expected_runtime_keys,
                    "observed_changed_runtime_keys": [],
                    "route_scope": SUCCESSOR_SLICE1_ROUTE_SCOPE,
                    "status": "fail",
                }
            )
            continue

        observed_runtime_keys = sorted(
            entry["runtime_key"] for entry in candidate_manifest["routed_modules"] if entry.get("claimed_changed_surface")
        )
        board_ok = observed_runtime_keys == expected_runtime_keys
        if not board_ok:
            errors.append(
                f"control-board runtime-key mismatch for {plan['board_entry_id']}: "
                f"expected={expected_runtime_keys} observed={observed_runtime_keys}"
            )
        _append_check(
            checks,
            check_id,
            board_ok,
            "control-board variant validated" if board_ok else "control-board runtime-key mismatch",
        )
        controls.append(
            {
                "board_entry_id": plan["board_entry_id"],
                "variant_id": variant_id,
                "expected_changed_runtime_keys": expected_runtime_keys,
                "observed_changed_runtime_keys": observed_runtime_keys,
                "route_scope": SUCCESSOR_SLICE1_ROUTE_SCOPE,
                "route_manifest_fingerprint": candidate_manifest["route_manifest_fingerprint"],
                "route_manifest": candidate_manifest,
                "status": "pass" if board_ok else "fail",
            }
        )

    return controls


def _check_control_board_guards(
    *,
    board_variant_ids: set[str],
    checks: list[dict[str, Any]],
    errors: list[str],
) -> None:
    has_primary_comparator = PRIMARY_COMPARATOR_VARIANT_ID in board_variant_ids
    if not has_primary_comparator:
        errors.append("compiled board missing mandatory primary comparator variant spb_01")
    _append_check(
        checks,
        "control_board_has_spb_01",
        has_primary_comparator,
        "mandatory primary comparator present" if has_primary_comparator else "missing mandatory spb_01",
    )

    has_completion_control = bool(COMPLETION_CONTROL_VARIANT_IDS.intersection(board_variant_ids))
    if not has_completion_control:
        errors.append("compiled board missing completion-related control variant")
    _append_check(
        checks,
        "control_board_has_completion_control",
        has_completion_control,
        "completion-related control present" if has_completion_control else "missing completion-related control",
    )


def _validate_lane_bindings_and_contracts(
    *,
    eval_cards: dict[str, dict[str, Any]],
    output_root: Path,
    board_variant_ids: set[str],
    checks: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    fixtures_root = output_root / "_compile_only_fixtures"
    contracts: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []

    for binding in SLICE_ONE_EVAL_BINDINGS:
        eval_id = binding["eval_id"]
        lane = validate_evaluation_lane(binding["evaluation_lane"], f"slice_one_eval_bindings.{eval_id}.evaluation_lane")
        expected_mode = binding["execution_mode"]
        primary_comparator_variant_id = binding["primary_comparator_variant_id"]
        legacy_comparator_variant_id = binding["legacy_visibility_comparator_variant_id"]

        card = eval_cards.get(eval_id)
        if card is None:
            errors.append(f"missing eval card for lane binding eval_id={eval_id}")
            _append_check(checks, f"lane_binding:{eval_id}", False, "eval card missing")
            continue

        route = route_eval_card(card, batch_lane=lane)
        fixed_invariants = card.get("fixed_invariants", {})
        if not isinstance(fixed_invariants, dict):
            fixed_invariants = {}

        mode_ok = route["execution_mode"] == expected_mode
        policy = get_packet03_eval_lane_policy(eval_id)
        policy_ok = policy["default_evaluation_lane"] == lane
        primary_is_spb = primary_comparator_variant_id == PRIMARY_COMPARATOR_VARIANT_ID
        legacy_is_scb = legacy_comparator_variant_id == BASELINE_VARIANT_ID
        comparators_distinct = primary_comparator_variant_id != legacy_comparator_variant_id
        primary_in_scope = primary_comparator_variant_id in SUCCESSOR_SLICE1_ALLOWED_VARIANTS
        legacy_in_scope = legacy_comparator_variant_id in SUCCESSOR_SLICE1_ALLOWED_VARIANTS
        primary_on_board = primary_comparator_variant_id in board_variant_ids
        legacy_on_board = legacy_comparator_variant_id in board_variant_ids
        fixed_comparator_present = isinstance(fixed_invariants.get("comparator_variant_id"), str) and bool(
            fixed_invariants.get("comparator_variant_id")
        )

        fixture_plan = materialize_packet03_eval_fixture(
            route=route,
            result_context={
                "eval_id": eval_id,
                "variant_id": REFERENCE_VARIANT_ID,
                "task_id": f"{eval_id}_compile_contract",
                "task_prompt": "compile-only contract validation",
                "rerun_index": 0,
                "claim_route_id": REFERENCE_COMPOSITION_ID,
            },
            run_dir=fixtures_root / eval_id,
        )
        fixture = fixture_plan.get("fixture") if isinstance(fixture_plan, dict) else None
        fixture_ok = isinstance(fixture, dict) and all(
            isinstance(fixture.get(field), str) and bool(fixture.get(field))
            for field in ("fixture_id", "grader_id", "eval_id")
        )
        lane_metadata = fixture_plan.get("lane_metadata") if isinstance(fixture_plan, dict) else None
        expected_promotion_authority = lane == "promotion"
        lane_metadata_ok = (
            isinstance(lane_metadata, dict)
            and lane_metadata.get("evaluation_lane") == lane
            and lane_metadata.get("promotion_authority") is expected_promotion_authority
        )
        grader_ok = bool(fixed_invariants.get("grader_version")) and fixed_invariants.get("grader_version") == fixture.get("grader_id")

        contract_ok = all(
            (
                mode_ok,
                policy_ok,
                primary_is_spb,
                legacy_is_scb,
                comparators_distinct,
                primary_in_scope,
                legacy_in_scope,
                primary_on_board,
                legacy_on_board,
                fixed_comparator_present,
                fixture_ok,
                lane_metadata_ok,
                grader_ok,
            )
        )
        if not contract_ok:
            errors.append(
                "fixture/grader/comparator contract check failed "
                f"for eval_id={eval_id} mode_ok={mode_ok} policy_ok={policy_ok} primary_is_spb={primary_is_spb} "
                f"legacy_is_scb={legacy_is_scb} comparators_distinct={comparators_distinct} primary_in_scope={primary_in_scope} "
                f"legacy_in_scope={legacy_in_scope} primary_on_board={primary_on_board} legacy_on_board={legacy_on_board} "
                f"fixed_comparator_present={fixed_comparator_present} fixture_ok={fixture_ok} "
                f"lane_metadata_ok={lane_metadata_ok} grader_ok={grader_ok}"
            )

        _append_check(
            checks,
            f"lane_binding:{eval_id}",
            contract_ok,
            "lane binding and pre-execution contracts validated" if contract_ok else "lane binding contract failed",
        )
        bindings.append(
            {
                "eval_id": eval_id,
                "evaluation_lane": lane,
                "execution_mode": route["execution_mode"],
                "primary_comparator_variant_id": primary_comparator_variant_id,
                "legacy_visibility_comparator_variant_id": legacy_comparator_variant_id,
                "route_scope": SUCCESSOR_SLICE1_ROUTE_SCOPE,
                "status": "pass" if contract_ok else "fail",
            }
        )
        contracts.append(
            {
                "eval_id": eval_id,
                "fixture_id": fixture.get("fixture_id") if isinstance(fixture, dict) else None,
                "grader_id": fixture.get("grader_id") if isinstance(fixture, dict) else None,
                "fixture_ref": fixture_plan.get("fixture_ref") if isinstance(fixture_plan, dict) else None,
                "lane_metadata": lane_metadata,
                "comparators": {
                    "primary_comparator_variant_id": primary_comparator_variant_id,
                    "legacy_visibility_comparator_variant_id": legacy_comparator_variant_id,
                    "eval_card_fixed_comparator_variant_id": fixed_invariants.get("comparator_variant_id"),
                },
                "fixed_invariants": {"grader_version": fixed_invariants.get("grader_version")},
                "checks": {
                    "execution_mode_match": mode_ok,
                    "lane_policy_match": policy_ok,
                    "primary_comparator_is_spb_01": primary_is_spb,
                    "legacy_comparator_is_sc_b_01": legacy_is_scb,
                    "comparators_distinct": comparators_distinct,
                    "primary_comparator_in_scope": primary_in_scope,
                    "legacy_comparator_in_scope": legacy_in_scope,
                    "primary_comparator_on_board": primary_on_board,
                    "legacy_comparator_on_board": legacy_on_board,
                    "eval_card_fixed_comparator_present": fixed_comparator_present,
                    "fixture_shape_valid": fixture_ok,
                    "lane_metadata_valid": lane_metadata_ok,
                    "grader_match": grader_ok,
                },
                "status": "pass" if contract_ok else "fail",
            }
        )

    lanes = {row["evaluation_lane"] for row in bindings}
    mixed_lane_ok = {"promotion", "bounded_diagnostic"}.issubset(lanes)
    if not mixed_lane_ok:
        errors.append("compiled lane bindings missing mixed promotion/bounded_diagnostic structure")
    _append_check(
        checks,
        "lane_bindings_mixed_structure",
        mixed_lane_ok,
        "mixed promotion/bounded_diagnostic structure validated" if mixed_lane_ok else "mixed-lane structure missing",
    )

    primary_presence_ok = any(row["primary_comparator_variant_id"] == PRIMARY_COMPARATOR_VARIANT_ID for row in bindings)
    if not primary_presence_ok:
        errors.append("comparator contracts linked only to sc_b_01; missing primary spb_01 bindings")
    _append_check(
        checks,
        "lane_bindings_primary_comparator_presence",
        primary_presence_ok,
        "primary comparator bindings include spb_01" if primary_presence_ok else "primary comparator spb_01 missing",
    )

    return {
        "bindings": bindings,
        "contracts": {
            "contract_version": "successor_slice1_contracts.v2",
            "contracts": contracts,
        },
    }


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            continue
        eval_id = row.get("eval_id")
        if isinstance(eval_id, str) and eval_id:
            cards[eval_id] = row
    return cards


def _append_check(checks: list[dict[str, Any]], check_id: str, ok: bool, summary: str) -> None:
    checks.append({"check_id": check_id, "status": "pass" if ok else "fail", "summary": summary})


def _require_keys(payload: dict[str, Any], *, required: tuple[str, ...], label: str) -> None:
    for key in required:
        if key not in payload:
            raise SchemaValidationError(f"{label}.{key} is required")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile-only successor slice-one validator")
    parser.add_argument("--output-dir", required=True, help="directory to write compile artifacts")
    parser.add_argument(
        "--eval-cards-path",
        default=str(DEFAULT_EVAL_CARDS_PATH),
        help="path to eval_cards.active.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = compile_successor_slice_one(
        output_dir=args.output_dir,
        eval_cards_path=args.eval_cards_path,
    )
    print(json.dumps({"status": report["status"], "report": str(Path(args.output_dir) / "compile_report.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
