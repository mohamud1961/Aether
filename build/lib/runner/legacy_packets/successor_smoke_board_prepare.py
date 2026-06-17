"""Compile-only preparation for the bounded successor smoke board."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from runner.eval_runner_router import route_eval_card
from runner.packet03_eval_fixtures import materialize_packet03_eval_fixture
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    SUCCESSOR_SLICE1_ROUTE_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import (
    SUCCESSOR_PRIMARY_COMPARATOR_VARIANT_ID,
    SUCCESSOR_RHV1_OBSERVED_MARKER_IDS,
    SUCCESSOR_RHV1_REFERENCE_VARIANT_ID,
    utc_now,
    validate_evaluation_lane,
    validate_route_manifest,
)

DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)

SMOKE_PREP_CONTRACT_VERSION = "successor_smoke_board_prepare.v1"
PRIMARY_COMPARATOR_VARIANT_ID = "spb_01"
REFERENCE_VARIANT_ID = "rhv1_ref_01"
OPTIONAL_ATTRIBUTION_VARIANT_ID = "rhv1_ablate_env_01"

SMOKE_ROUTE_SET = (
    {
        "route_entry_id": "primary_prompt_comparator",
        "variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
        "required": True,
        "enabled_for_initial_smoke": True,
        "reason": "mandatory primary comparator",
    },
    {
        "route_entry_id": "rhv1_reference",
        "variant_id": REFERENCE_VARIANT_ID,
        "required": True,
        "enabled_for_initial_smoke": True,
        "reason": "reference successor harness route",
    },
    {
        "route_entry_id": "optional_env_attribution",
        "variant_id": OPTIONAL_ATTRIBUTION_VARIANT_ID,
        "required": False,
        "enabled_for_initial_smoke": False,
        "reason": "single optional ablation for immediate attribution only",
    },
)

SMOKE_EVAL_BOARD = (
    {
        "home_id": "smoke_discovery_evidence_efficiency",
        "eval_id": "ae_internal_discovery_evidence_efficiency_v1",
        "evaluation_lane": "promotion",
        "required": True,
        "focus": "discovery_evidence_efficiency",
    },
    {
        "home_id": "smoke_environment_toolchain_adaptation",
        "eval_id": "ae_internal_multifile_repair_test_verify_v1",
        "evaluation_lane": "promotion",
        "required": True,
        "focus": "environment_toolchain_adaptation_proxy",
        "focus_note": (
            "proxy-collapsed home: this eval remains the nearest active in-scope environment/toolchain proxy "
            "and is also the admissible completion-trap check for this first smoke slice; no contradiction-family home"
        ),
    },
    {
        "home_id": "smoke_context_state_continuity_optional",
        "eval_id": "ae_workspace_target_decoy_generalization_multistep_v1",
        "evaluation_lane": "guardrail_debug",
        "required": False,
        "focus": "context_state_continuity",
    },
)

GLOBAL_TRACE_MARKERS = (
    "run_header.json_present",
    "run_events.jsonl_append_only",
    "score_envelope.json_present",
    "trace_summary_present",
    "claim_route_id_present",
    "route_manifest_fingerprint_present",
    "primary_comparator_variant_id_present",
    "legacy_visibility_comparator_variant_id_present",
    "verification_reason_codes_present",
    "verification_substitution_violations_present",
    "lifecycle_sequence_fingerprint_present",
    "terminal_write_count_present",
    "cleanup_completion_reason_codes_present",
)


def prepare_successor_smoke_board(
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

    route_rows = _compile_route_set(baseline_manifest=baseline_manifest, checks=checks, errors=errors)
    _check_route_set_bounds(route_rows=route_rows, checks=checks, errors=errors)

    eval_cards = _load_eval_cards(Path(eval_cards_path))
    eval_board = _compile_eval_board(
        eval_cards=eval_cards,
        output_root=output_root,
        checks=checks,
        errors=errors,
    )
    _check_eval_home_bounds(eval_board=eval_board, checks=checks, errors=errors)

    trace_markers = _build_trace_markers(eval_board=eval_board)
    readiness = _build_readiness_checks(eval_board=eval_board, route_rows=route_rows)
    _append_check(
        checks,
        "readiness_all_required_checks_pass",
        readiness["all_required_checks_pass"],
        "required grader/comparator checks pass" if readiness["all_required_checks_pass"] else "readiness checks failed",
    )
    if not readiness["all_required_checks_pass"]:
        errors.append("smoke-board readiness checks failed; not ready for first bounded live gate")

    artifact_boundary = _build_artifact_boundary(
        route_rows=route_rows,
        eval_board=eval_board,
        trace_markers=trace_markers,
    )

    _write_json(output_root / "smoke_route_set.json", {"route_scope": SUCCESSOR_SLICE1_ROUTE_SCOPE, "routes": route_rows})
    _write_json(output_root / "smoke_eval_board.json", {"homes": eval_board})
    _write_json(output_root / "smoke_trace_markers.json", trace_markers)
    _write_json(output_root / "smoke_grader_comparator_readiness.json", readiness)
    _write_json(output_root / "smoke_live_gate_artifact_boundary.json", artifact_boundary)

    report = {
        "smoke_prepare_contract_version": SMOKE_PREP_CONTRACT_VERSION,
        "prepared_at_utc": utc_now(),
        "route_scope": SUCCESSOR_SLICE1_ROUTE_SCOPE,
        "routes": route_rows,
        "eval_board": eval_board,
        "trace_marker_contract": trace_markers,
        "grader_comparator_readiness": readiness,
        "first_live_gate_artifact_boundary": artifact_boundary,
        "checks": checks,
        "errors": errors,
        "status": "pass" if not errors else "fail",
    }
    _write_json(output_root / "smoke_prepare_report.json", report)
    return report


def _compile_route_set(
    *,
    baseline_manifest: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for plan in SMOKE_ROUTE_SET:
        variant_id = plan["variant_id"]
        check_id = f"route_set:{plan['route_entry_id']}"
        try:
            manifest = build_packet04_route_manifest(variant_id, scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
            validate_route_manifest(manifest)
            load_runtime_callables(manifest)
            if variant_id != BASELINE_VARIANT_ID:
                validate_independent_candidate_routing(
                    candidate_manifest=manifest,
                    baseline_manifest=baseline_manifest,
                )
            status = "pass"
            _append_check(checks, check_id, True, "route manifest compiled")
        except Exception as err:  # pragma: no cover - defensive compile reporting
            manifest = None
            status = "fail"
            if plan["required"]:
                errors.append(f"required smoke route failed: variant_id={variant_id} err={err}")
            _append_check(checks, check_id, False, "route manifest compile failure")
        rows.append(
            {
                "route_entry_id": plan["route_entry_id"],
                "variant_id": variant_id,
                "required": bool(plan["required"]),
                "enabled_for_initial_smoke": bool(plan["enabled_for_initial_smoke"]),
                "reason": plan["reason"],
                "route_manifest_fingerprint": manifest["route_manifest_fingerprint"] if isinstance(manifest, dict) else None,
                "status": status,
            }
        )
    return rows


def _compile_eval_board(
    *,
    eval_cards: dict[str, dict[str, Any]],
    output_root: Path,
    checks: list[dict[str, Any]],
    errors: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fixtures_root = output_root / "_compile_only_fixtures"
    for home in SMOKE_EVAL_BOARD:
        eval_id = home["eval_id"]
        lane = validate_evaluation_lane(home["evaluation_lane"], f"smoke_eval_board.{eval_id}.evaluation_lane")
        check_id = f"eval_home:{home['home_id']}"
        card = eval_cards.get(eval_id)
        if card is None:
            if home["required"]:
                errors.append(f"required smoke eval home missing active eval card: eval_id={eval_id}")
            _append_check(checks, check_id, False, "eval card missing")
            rows.append(
                {
                    "home_id": home["home_id"],
                    "eval_id": eval_id,
                    "evaluation_lane": lane,
                    "focus": home["focus"],
                    "required": bool(home["required"]),
                    "status": "fail",
                }
            )
            continue

        route = route_eval_card(card, batch_lane=lane)
        fixture_plan = materialize_packet03_eval_fixture(
            route=route,
            result_context={
                "eval_id": eval_id,
                "variant_id": REFERENCE_VARIANT_ID,
                "task_id": f"{eval_id}_smoke_prepare_contract",
                "task_prompt": "smoke-board preparation contract validation",
                "rerun_index": 0,
                "claim_route_id": f"successor_smoke_board.{home['home_id']}",
            },
            run_dir=fixtures_root / home["home_id"],
        )
        fixture = fixture_plan.get("fixture") if isinstance(fixture_plan, dict) else {}
        fixed = card.get("fixed_invariants", {})
        score_layers = card.get("score_layer_expectations", {})
        checks_ok = all(
            (
                isinstance(fixed.get("grader_version"), str) and bool(fixed["grader_version"]),
                isinstance(fixed.get("fixture_version"), str) and bool(fixed["fixture_version"]),
                isinstance(fixture.get("fixture_id"), str) and bool(fixture["fixture_id"]),
                isinstance(fixture.get("grader_id"), str) and bool(fixture["grader_id"]),
                score_layers.get("non_substitution_rule") == "required",
                isinstance(card.get("trace_requirements"), list) and bool(card.get("trace_requirements")),
            )
        )
        if not checks_ok and home["required"]:
            errors.append(f"required smoke eval home contract failed: eval_id={eval_id}")
        _append_check(
            checks,
            check_id,
            checks_ok,
            "smoke eval home contract prepared" if checks_ok else "smoke eval home contract failed",
        )
        rows.append(
            {
                "home_id": home["home_id"],
                "eval_id": eval_id,
                "evaluation_lane": lane,
                "execution_mode": route["execution_mode"],
                "focus": home["focus"],
                "focus_note": home.get("focus_note"),
                "required": bool(home["required"]),
                "primary_comparator_variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
                "legacy_visibility_comparator_variant_id": BASELINE_VARIANT_ID,
                "grader_id": fixture.get("grader_id"),
                "fixture_id": fixture.get("fixture_id"),
                "trace_requirements": list(card.get("trace_requirements", [])),
                "non_substitution_rule": score_layers.get("non_substitution_rule"),
                "status": "pass" if checks_ok else "fail",
            }
        )
    return rows


def _build_trace_markers(*, eval_board: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trace_marker_contract_version": "successor_smoke_trace_markers.v1",
        "global_required_markers": list(GLOBAL_TRACE_MARKERS),
        "declared_vs_observed_mechanism_contract": {
            "declared_field": "trace_summary.declared_mechanisms",
            "observed_field": "trace_summary.observed_mechanisms",
            "rhv1_reference_variant_id": SUCCESSOR_RHV1_REFERENCE_VARIANT_ID,
            "primary_comparator_variant_id": SUCCESSOR_PRIMARY_COMPARATOR_VARIANT_ID,
            "required_rhv1_observed_marker_ids": list(SUCCESSOR_RHV1_OBSERVED_MARKER_IDS),
            "forbid_rhv1_marker_family_on_primary_comparator": True,
        },
        "home_trace_requirements": [
            {"home_id": row["home_id"], "eval_id": row["eval_id"], "trace_requirements": row.get("trace_requirements", [])}
            for row in eval_board
        ],
    }


def _build_readiness_checks(*, eval_board: list[dict[str, Any]], route_rows: list[dict[str, Any]]) -> dict[str, Any]:
    active_routes = {row["variant_id"] for row in route_rows if row["enabled_for_initial_smoke"] and row["status"] == "pass"}
    required_eval_rows = [row for row in eval_board if row["required"]]
    rows: list[dict[str, Any]] = []
    for row in required_eval_rows:
        comparator_ok = (
            row["primary_comparator_variant_id"] == PRIMARY_COMPARATOR_VARIANT_ID
            and row["legacy_visibility_comparator_variant_id"] == BASELINE_VARIANT_ID
            and row["primary_comparator_variant_id"] != row["legacy_visibility_comparator_variant_id"]
            and row["primary_comparator_variant_id"] in active_routes
        )
        grader_ok = isinstance(row.get("grader_id"), str) and bool(row.get("grader_id"))
        fixture_ok = isinstance(row.get("fixture_id"), str) and bool(row.get("fixture_id"))
        non_sub_ok = row.get("non_substitution_rule") == "required"
        row_ok = all((comparator_ok, grader_ok, fixture_ok, non_sub_ok, row["status"] == "pass"))
        rows.append(
            {
                "home_id": row["home_id"],
                "eval_id": row["eval_id"],
                "checks": {
                    "comparator_contract_ok": comparator_ok,
                    "grader_id_present": grader_ok,
                    "fixture_id_present": fixture_ok,
                    "non_substitution_rule_required": non_sub_ok,
                    "home_contract_status_pass": row["status"] == "pass",
                },
                "status": "pass" if row_ok else "fail",
            }
        )
    return {
        "readiness_contract_version": "successor_smoke_grader_comparator_readiness.v1",
        "required_home_checks": rows,
        "all_required_checks_pass": all(row["status"] == "pass" for row in rows),
    }


def _build_artifact_boundary(
    *,
    route_rows: list[dict[str, Any]],
    eval_board: list[dict[str, Any]],
    trace_markers: dict[str, Any],
) -> dict[str, Any]:
    return {
        "boundary_contract_version": "successor_smoke_live_gate_boundary.v1",
        "preparation_only": True,
        "forbidden_during_preparation": [
            "packet_opening",
            "live_batch_execution",
            "packet06_reopen",
            "contender_readiness_claims",
            "transfer_or_benchmark_scope_widening",
        ],
        "allowed_artifacts_only": [
            "smoke_route_set.json",
            "smoke_eval_board.json",
            "smoke_trace_markers.json",
            "smoke_grader_comparator_readiness.json",
            "smoke_live_gate_artifact_boundary.json",
            "smoke_prepare_report.json",
        ],
        "first_bounded_live_gate_inputs": {
            "route_set_hash": _hash_payload(route_rows),
            "eval_board_hash": _hash_payload(eval_board),
            "trace_marker_hash": _hash_payload(trace_markers),
            "primary_comparator_variant_id": PRIMARY_COMPARATOR_VARIANT_ID,
            "legacy_visibility_comparator_variant_id": BASELINE_VARIANT_ID,
        },
    }


def _check_route_set_bounds(*, route_rows: list[dict[str, Any]], checks: list[dict[str, Any]], errors: list[str]) -> None:
    required_ids = {PRIMARY_COMPARATOR_VARIANT_ID, REFERENCE_VARIANT_ID}
    compiled_required = {row["variant_id"] for row in route_rows if row["required"] and row["status"] == "pass"}
    has_required = required_ids.issubset(compiled_required)
    if not has_required:
        errors.append("smoke route set is missing one or more required compiled routes")
    _append_check(
        checks,
        "smoke_routes_required_presence",
        has_required,
        "required routes compiled" if has_required else "missing required compiled routes",
    )


def _check_eval_home_bounds(*, eval_board: list[dict[str, Any]], checks: list[dict[str, Any]], errors: list[str]) -> None:
    count = len(eval_board)
    in_bounds = 2 <= count <= 4
    if not in_bounds:
        errors.append(f"smoke eval board must contain 2-4 homes, found {count}")
    _append_check(
        checks,
        "smoke_eval_home_count_bounds",
        in_bounds,
        "eval-home count in 2-4 bound" if in_bounds else "eval-home count out of bounds",
    )


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


def _hash_payload(payload: Any) -> str:
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _append_check(checks: list[dict[str, Any]], check_id: str, ok: bool, summary: str) -> None:
    checks.append({"check_id": check_id, "status": "pass" if ok else "fail", "summary": summary})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile-only successor smoke-board preparation")
    parser.add_argument("--output-dir", required=True, help="directory to write smoke-board preparation artifacts")
    parser.add_argument(
        "--eval-cards-path",
        default=str(DEFAULT_EVAL_CARDS_PATH),
        help="path to eval_cards.active.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = prepare_successor_smoke_board(output_dir=args.output_dir, eval_cards_path=args.eval_cards_path)
    print(json.dumps({"status": report["status"], "report": str(Path(args.output_dir) / "smoke_prepare_report.json")}))


if __name__ == "__main__":
    main()
