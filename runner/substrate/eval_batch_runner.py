"""Packet 03 batch execution slice for atomic eval families."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runner.agent import run_reference_baseline
from runner.eval_runner_router import resolve_model_route_for_route, route_eval_card
from runner.experiment_contracts import (
    normalize_recommendation_lane_class,
    validate_batch_spec,
    validate_recommendation_draft,
    validate_result_artifact_linkage,
    validate_result_record,
    validate_trace_summary,
)
from runner.packet03_eval_fixtures import materialize_packet03_eval_fixture
from runner.packet03_eval_graders import apply_packet03_eval_grader
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    ALLOWED_PACKET04_VARIANTS,
    PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE,
    PACKET05A_WORKSPACE_TARGET_SCOPE,
    build_packet04_route_manifest,
    get_allowed_packet04_variants,
    validate_independent_candidate_routing,
)
from runner.model_client import (
    make_azure_gpt53_codex_route_from_env,
    make_azure_gpt54_mini_route_from_env,
    make_openai_chat_completions_route,
)
from runner.schemas import (
    GOVERNED_TRUTH_AUTHORITY_COMPLETENESS,
    GOVERNED_TRUTH_COMPLETION_SCOPES,
    SchemaValidationError,
    SUCCESSOR_RHV1_OBSERVED_MARKER_IDS,
    SUCCESSOR_RHV1_REFERENCE_VARIANT_ID,
    fingerprint_payload,
    validate_event,
    validate_eval_run_header_metadata,
    validate_evaluation_lane,
    utc_now,
)

MODEL_POLICY_TIERS = frozenset({"screening_default", "screening_fallback", "promotion_tier"})
GOVERNED_EVAL_BUDGET_WARNING_THRESHOLDS_USD = (100.0, 200.0, 250.0)
GOVERNED_EVAL_BUDGET_HARD_CAP_USD = 300.0
RECOMMENDATION_GOVERNANCE_VERSION = "packet04a_recommendation_governance.v1"
RECOMMENDATION_GATE_IDS = tuple(f"G{index}" for index in range(1, 16))
LEGACY_PROXY_PROMOTION_SURFACE_EVAL_IDS = frozenset(
    {
        "ae_completion_layer_contract_guard",
        "ae_lifecycle_terminality_contract_guard",
        "ae_cwd_workdir_path_contract_guard",
        "ae_tool_call_shape_argument_contract",
    }
)
ALLOWED_AUDIT_STATUSES = frozenset({"pass", "fail", "missing"})
MODEL_PRICING_PER_MILLION_TOKENS = {
    "gpt-5.4-mini": {
        "input": 0.75,
        "cached_input": 0.075,
        "output": 4.50,
    },
    "gpt-5.3-codex": {
        "input": 1.75,
        "cached_input": 0.175,
        "output": 14.00,
    },
}
LEGACY_BATCH_LANE_ALIASES = {
    "stability_lane": "promotion",
    "adversarial_lane": "promotion",
}
TOOL_FAMILY_AUTHORITY_EVAL_IDS = frozenset(
    {
        "ae_tool_call_contract_quality_v2",
        "ae_tool_result_attribution_quality_v2",
        "ae_internal_toolchain_dependency_pressure_v1",
        "ae_internal_artifact_log_extraction_v1",
    }
)
WORKSPACE_TARGET_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_correctness_probe",
        "eval_workspace_target_correctness_atomic_v1",
        "ae_workspace_target_decoy_generalization_v2",
        "eval_workspace_target_decoy_generalization_atomic_v2",
        "ae_workspace_target_decoy_generalization_multistep_v1",
        "eval_workspace_target_decoy_generalization_multistep_v1",
    }
)
WORKSPACE_TARGET_MULTISTEP_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_decoy_generalization_multistep_v1",
        "eval_workspace_target_decoy_generalization_multistep_v1",
    }
)
WORKSPACE_TARGET_REENTRY_EVAL_IDS = frozenset(
    {
        "ae_workspace_target_decoy_generalization_v2",
        "eval_workspace_target_decoy_generalization_atomic_v2",
    }
)


def run_batch(
    *,
    batch_spec: dict[str, Any],
    eval_cards: dict[str, dict[str, Any]] | list[dict[str, Any]],
    model_route_override: dict[str, Any] | None = None,
    model_client_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one Packet 03 batch and emit machine-readable outputs."""
    normalized_batch = _normalize_batch_lane_contract(dict(batch_spec))
    normalized_batch = validate_batch_spec(normalized_batch)
    eval_cards_by_id = _index_eval_cards(eval_cards)
    task_cases = _normalize_task_cases(normalized_batch)
    routes = _resolve_routes(normalized_batch, eval_cards_by_id)

    batch_dir = Path(normalized_batch["output_root"]).resolve() / normalized_batch["batch_id"]
    runs_dir = batch_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    augmented_batch = dict(normalized_batch)
    augmented_batch["execution_mode_lock"] = {
        eval_id: route["execution_mode"] for eval_id, route in routes.items()
    }
    augmented_batch["eval_card_refs"] = {
        eval_id: route["eval_card"].get("eval_card_ref", f"inline:{eval_id}")
        for eval_id, route in routes.items()
    }
    validate_batch_spec(augmented_batch)
    route_manifests = _resolve_packet04_route_manifests(augmented_batch)

    trace_summaries: list[dict[str, Any]] = []
    result_records: list[dict[str, Any]] = []
    run_contexts = _iter_run_contexts(augmented_batch, task_cases)
    model_tier_selector = _resolve_model_tier_selector(augmented_batch)
    batch_provider_route = _resolve_batch_provider_route(augmented_batch)
    budget_tracker = _init_budget_tracker(planned_run_count=len(run_contexts))
    for result_context in run_contexts:
        if budget_tracker["hard_cap_reached"]:
            break
        eval_id = result_context["eval_id"]
        route = routes[eval_id]
        run_id = _build_run_id(
            batch_id=augmented_batch["batch_id"],
            eval_id=eval_id,
            variant_id=result_context["variant_id"],
            task_id=result_context["task_id"],
            rerun_index=result_context["rerun_index"],
        )
        run_dir = runs_dir / run_id
        fixture_plan = materialize_packet03_eval_fixture(
            route=route,
            result_context=result_context,
            run_dir=run_dir,
        )
        execution_result = _execute_route(
            route=route,
            result_context=result_context,
            fixture_plan=fixture_plan,
            run_id=run_id,
            run_dir=run_dir,
            eval_family=augmented_batch["eval_family"],
            model_route_override=model_route_override,
            model_policy_override=augmented_batch.get("model_policy"),
            model_tier_selector=model_tier_selector,
            batch_provider_route=batch_provider_route,
            model_client_kwargs=model_client_kwargs,
            route_manifest=route_manifests.get(result_context["variant_id"]),
            enforce_packet04_route_contract=bool(route_manifests),
        )
        _write_eval_run_header(
            batch=normalized_batch,
            route=route,
            result_context=result_context,
            execution_result=execution_result,
            run_dir=run_dir,
        )
        execution_result = apply_packet03_eval_grader(
            route=route,
            execution_result=execution_result,
            fixture_plan=fixture_plan,
        )
        _append_governed_eval_truth_event(
            run_dir=run_dir,
            eval_id=eval_id,
            execution_mode=route["execution_mode"],
            execution_result=execution_result,
        )
        _write_json(run_dir / "score_envelope.json", execution_result["score_envelope"])
        _validate_run_artifacts(run_dir)

        trace_summary = _build_trace_summary(
            run_id=run_id,
            eval_id=eval_id,
            variant_id=result_context["variant_id"],
            execution_mode=route["execution_mode"],
            evaluation_lane=route["evaluation_lane"],
            promotion_authority=route["promotion_authority"],
            execution_result=execution_result,
            result_context=result_context,
        )
        validate_trace_summary(trace_summary)
        trace_summaries.append(trace_summary)
        trace_summary_ref = f"{batch_dir / 'trace_summaries.jsonl'}#run_id={run_id}"
        result_record = _build_result_record(
            batch=augmented_batch,
            route=route,
            result_context=result_context,
            run_id=run_id,
            trace_summary_ref=trace_summary_ref,
            execution_result=execution_result,
            fixture_plan=fixture_plan,
            route_manifest=route_manifests.get(result_context["variant_id"]),
        )
        budget_update = _accumulate_budget_progress(
            budget_tracker=budget_tracker,
            run_id=run_id,
            result_record=result_record,
        )
        if budget_update["hard_cap_triggered"]:
            reason_codes = set(result_record.get("reason_codes", []))
            reason_codes.add("budget_hard_cap_reached")
            result_record["reason_codes"] = sorted(reason_codes)
            result_record["failure_cluster"] = "budget_exhaustion"
        validate_result_record(result_record)
        validate_result_artifact_linkage(
            result_record,
            trace_summaries=trace_summaries,
            output_root=batch_dir,
        )
        result_records.append(result_record)

    budget_summary = _budget_summary_from_tracker(budget_tracker)
    if _is_packet04_governed_batch(augmented_batch):
        _write_execution_audit_artifacts(
            batch=augmented_batch,
            result_records=result_records,
            output_root=batch_dir,
        )
    recommendation = _build_recommendation_draft(
        augmented_batch,
        result_records,
        budget_summary=budget_summary,
        output_root=batch_dir,
    )
    validate_recommendation_draft(recommendation, output_root=batch_dir)

    batch_spec_path = batch_dir / "batch_spec.json"
    result_records_path = batch_dir / "result_records.jsonl"
    trace_summaries_path = batch_dir / "trace_summaries.jsonl"
    recommendations_path = batch_dir / "recommendations.json"

    _write_json(batch_spec_path, augmented_batch)
    _write_jsonl(result_records_path, result_records)
    _write_jsonl(trace_summaries_path, trace_summaries)
    _write_json(recommendations_path, recommendation)

    return {
        "batch_id": augmented_batch["batch_id"],
        "batch_dir": str(batch_dir),
        "batch_spec_path": str(batch_spec_path),
        "result_records_path": str(result_records_path),
        "trace_summaries_path": str(trace_summaries_path),
        "recommendations_path": str(recommendations_path),
        "run_count": len(result_records),
        "execution_mode_lock": augmented_batch["execution_mode_lock"],
        "evaluation_lane": augmented_batch["evaluation_lane"],
        "budget_governance": budget_summary,
    }


def _normalize_batch_lane_contract(batch_spec: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(batch_spec)
    lane = normalized.get("evaluation_lane")
    if lane is None:
        fixed_invariants = normalized.get("fixed_invariants")
        if isinstance(fixed_invariants, dict):
            lane = fixed_invariants.get("evaluation_lane")
    if lane is None:
        raise SchemaValidationError("batch_spec.evaluation_lane is required")
    if isinstance(lane, str):
        lane = LEGACY_BATCH_LANE_ALIASES.get(lane, lane)
    lane = validate_evaluation_lane(lane, "batch_spec.evaluation_lane")
    normalized["evaluation_lane"] = lane
    if "promotion_authority" not in normalized:
        normalized["promotion_authority"] = lane == "promotion"
    if _is_packet04_batch(normalized):
        normalized.setdefault("lane_blocker_policy", "packet04a_lane_blocker_policy.v1")
        normalized.setdefault("route_contract_id", "packet04_route_manifest.v1")
        normalized.setdefault("ownership_bucket_map_ref", "runner/packet04_route_manifest.py")
        variant_card_refs = normalized.get("variant_card_refs")
        if not isinstance(variant_card_refs, dict):
            variant_ids = normalized.get("variant_ids")
            variant_card_refs = {}
            if isinstance(variant_ids, list):
                for variant_id in variant_ids:
                    if not isinstance(variant_id, str) or not variant_id:
                        continue
                    variant_card_refs[variant_id] = (
                        "tracking/collab/stage_03_execution_planning/packets/"
                        "packet_04_first_atomic_variants/outputs/variant_cards.md"
                        f"#variant_id={variant_id}"
                    )
            normalized["variant_card_refs"] = variant_card_refs
    return normalized


def _index_eval_cards(eval_cards: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(eval_cards, dict):
        return {str(eval_id): dict(card) for eval_id, card in eval_cards.items()}
    indexed: dict[str, dict[str, Any]] = {}
    for index, card in enumerate(eval_cards):
        if not isinstance(card, dict):
            raise SchemaValidationError(f"eval_cards[{index}] must be an object")
        eval_id = card.get("eval_id")
        if not isinstance(eval_id, str) or not eval_id:
            raise SchemaValidationError(f"eval_cards[{index}].eval_id must be a non-empty string")
        indexed[eval_id] = dict(card)
    return indexed


def _resolve_routes(batch: dict[str, Any], eval_cards_by_id: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    execution_mode_lock = batch.get("execution_mode_lock", {})
    fixed_invariants = batch.get("fixed_invariants")
    legacy_batch_lane = None
    if isinstance(fixed_invariants, dict):
        raw_fixed_lane = fixed_invariants.get("evaluation_lane")
        if raw_fixed_lane in LEGACY_BATCH_LANE_ALIASES:
            legacy_batch_lane = raw_fixed_lane
    for eval_id in batch["eval_ids"]:
        card = eval_cards_by_id.get(eval_id)
        if card is None:
            raise SchemaValidationError(f"missing eval_card for eval_id={eval_id}")
        route = route_eval_card(card, batch_lane=None if legacy_batch_lane else batch["evaluation_lane"])
        if execution_mode_lock:
            expected_mode = execution_mode_lock.get(eval_id)
            if expected_mode and route["execution_mode"] != expected_mode:
                raise SchemaValidationError(
                    f"execution_mode_lock mismatch for eval_id={eval_id}: {expected_mode} != {route['execution_mode']}"
                )
        _enforce_batch_eligibility(batch, route)
        routes[eval_id] = route
    return routes


def _enforce_batch_eligibility(batch: dict[str, Any], route: dict[str, Any]) -> None:
    if route["batch_eligibility"]:
        return
    if route["execution_mode"] != "sync_interactive":
        raise SchemaValidationError(
            f"eval_id={route['eval_id']} is not batch-eligible outside sync_interactive mode"
        )
    task_cases = batch.get("task_cases")
    task_case_count = len(task_cases) if isinstance(task_cases, list) else 1
    if batch["rerun_count"] > 1 or len(batch["variant_ids"]) > 1 or task_case_count > 1:
        raise SchemaValidationError(
            f"sync_interactive eval_id={route['eval_id']} must run with rerun_count=1, one variant, and one task"
        )


def _normalize_task_cases(batch: dict[str, Any]) -> list[dict[str, Any]]:
    task_cases = batch.get("task_cases")
    if task_cases is None:
        default_case: dict[str, Any] = {
            "task_id": batch["task_set_id"],
            "task_prompt": batch.get("task_prompt", ""),
        }
        for field in ("claim_route_id", "task_intent"):
            value = batch.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise SchemaValidationError(f"batch_spec.{field} must be a non-empty string when provided")
            default_case[field] = value
        return [default_case]
    if not isinstance(task_cases, list) or not task_cases:
        raise SchemaValidationError("batch_spec.task_cases must be a non-empty list when provided")
    normalized: list[dict[str, Any]] = []
    for index, task_case in enumerate(task_cases):
        if not isinstance(task_case, dict):
            raise SchemaValidationError(f"batch_spec.task_cases[{index}] must be an object")
        task_id = task_case.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise SchemaValidationError(f"batch_spec.task_cases[{index}].task_id must be a non-empty string")
        prompt = task_case.get("task_prompt", "")
        if not isinstance(prompt, str):
            raise SchemaValidationError(f"batch_spec.task_cases[{index}].task_prompt must be a string")
        row: dict[str, Any] = {"task_id": task_id, "task_prompt": prompt}
        for field in ("claim_route_id", "task_intent"):
            value = task_case.get(field, batch.get(field))
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise SchemaValidationError(
                    f"batch_spec.task_cases[{index}].{field} must be a non-empty string when provided"
                )
            row[field] = value
        normalized.append(row)
    return normalized


def _iter_run_contexts(batch: dict[str, Any], task_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for eval_id in batch["eval_ids"]:
        for variant_id in batch["variant_ids"]:
            for task_case in task_cases:
                for rerun_index in range(batch["rerun_count"]):
                    row = {
                        "eval_id": eval_id,
                        "variant_id": variant_id,
                        "task_id": task_case["task_id"],
                        "task_prompt": task_case["task_prompt"],
                        "rerun_index": rerun_index,
                    }
                    for field in ("claim_route_id", "task_intent"):
                        value = task_case.get(field)
                        if isinstance(value, str) and value:
                            row[field] = value
                    contexts.append(row)
    return contexts


def _resolve_packet04_route_manifests(batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not _is_packet04_batch(batch):
        return {}
    variant_ids = batch.get("variant_ids", [])
    if not isinstance(variant_ids, list):
        raise SchemaValidationError("batch_spec.variant_ids must be a list")
    scope = _resolve_packet04_route_scope(batch)
    allowed_variants = get_allowed_packet04_variants(scope=scope)
    try:
        baseline_manifest = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=scope)
    except ValueError as err:
        raise SchemaValidationError(str(err)) from err
    manifests: dict[str, dict[str, Any]] = {BASELINE_VARIANT_ID: baseline_manifest}
    for variant_id in variant_ids:
        if not isinstance(variant_id, str) or not variant_id:
            raise SchemaValidationError("batch_spec.variant_ids entries must be non-empty strings")
        if variant_id not in allowed_variants:
            allowed = ", ".join(sorted(allowed_variants))
            raise SchemaValidationError(
                "Packet 04 route scope is locked. "
                f"scope={scope} variant_id={variant_id} is out of scope. Allowed: {allowed}"
            )
        if variant_id == BASELINE_VARIANT_ID:
            continue
        try:
            candidate_manifest = build_packet04_route_manifest(variant_id, scope=scope)
            validate_independent_candidate_routing(
                candidate_manifest=candidate_manifest,
                baseline_manifest=baseline_manifest,
            )
        except ValueError as err:
            raise SchemaValidationError(str(err)) from err
        manifests[variant_id] = candidate_manifest
    return manifests


def _resolve_packet04_route_scope(batch: dict[str, Any]) -> str:
    candidates = [batch.get("packet04_route_scope")]
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        candidates.append(fixed_invariants.get("packet04_route_scope"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    eval_ids = batch.get("eval_ids")
    if isinstance(eval_ids, list):
        eval_id_set = {eval_id for eval_id in eval_ids if isinstance(eval_id, str)}
        if eval_id_set and eval_id_set.issubset(WORKSPACE_TARGET_MULTISTEP_EVAL_IDS):
            return PACKET05A_WORKSPACE_TARGET_MULTISTEP_SCOPE
        if eval_id_set and eval_id_set.issubset(WORKSPACE_TARGET_REENTRY_EVAL_IDS):
            return PACKET05A_WORKSPACE_TARGET_SCOPE
    return "packet04a_first_slice"


def _is_packet04_batch(batch: dict[str, Any]) -> bool:
    packet_stage = batch.get("packet_stage")
    if isinstance(packet_stage, str) and packet_stage == "packet_04":
        return True
    eval_family = batch.get("eval_family")
    return isinstance(eval_family, str) and eval_family.startswith("packet_04")


def _is_packet04_governed_batch(batch: dict[str, Any]) -> bool:
    if _is_packet04_batch(batch):
        return True
    batch_id = batch.get("batch_id")
    if isinstance(batch_id, str) and "packet04" in batch_id.lower():
        return True
    variant_ids = batch.get("variant_ids")
    if isinstance(variant_ids, list):
        for variant_id in variant_ids:
            if isinstance(variant_id, str) and variant_id.startswith("v04_"):
                return True
    return False


def _allow_packet06_authority_fallback(batch: dict[str, Any]) -> bool:
    packet_stage = batch.get("packet_stage")
    claim_route_id = batch.get("claim_route_id")
    return packet_stage == "packet_06" and isinstance(claim_route_id, str) and bool(claim_route_id)


def _build_run_id(*, batch_id: str, eval_id: str, variant_id: str, task_id: str, rerun_index: int) -> str:
    raw = f"{batch_id}__{eval_id}__{variant_id}__{task_id}__r{rerun_index}"
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in raw)


def _execute_route(
    *,
    route: dict[str, Any],
    result_context: dict[str, Any],
    fixture_plan: dict[str, Any],
    run_id: str,
    run_dir: Path,
    eval_family: str,
    model_route_override: dict[str, Any] | None,
    model_policy_override: dict[str, Any] | None,
    model_tier_selector: str,
    batch_provider_route: str | None,
    model_client_kwargs: dict[str, Any] | None,
    route_manifest: dict[str, Any] | None,
    enforce_packet04_route_contract: bool,
) -> dict[str, Any]:
    mode = route["execution_mode"]
    merged_model_client_kwargs: dict[str, Any] | None = None
    if isinstance(model_client_kwargs, dict) or isinstance(fixture_plan.get("model_client_kwargs"), dict):
        merged_model_client_kwargs = {}
        if isinstance(model_client_kwargs, dict):
            merged_model_client_kwargs.update(model_client_kwargs)
        fixture_model_kwargs = fixture_plan.get("model_client_kwargs")
        if isinstance(fixture_model_kwargs, dict):
            merged_model_client_kwargs.update(fixture_model_kwargs)
    effective_model_route_override = _resolve_batch_model_route_override(
        route=route,
        batch_model_policy=model_policy_override,
        batch_model_route_override=model_route_override,
        model_tier_selector=model_tier_selector,
        batch_provider_route=batch_provider_route,
    )
    model_route = resolve_model_route_for_route(
        route,
        override_model_route=effective_model_route_override,
        model_policy_override=model_policy_override,
        model_tier_selector=model_tier_selector,
    )
    if mode == "multistep_batchable":
        max_steps = _resolve_multistep_turn_budget(route.get("eval_card"))
    elif mode in {"deterministic_no_model", "one_shot_batchable", "offline_judge_batchable"}:
        max_steps = 1
    else:
        max_steps = 3
    if mode == "sync_interactive":
        horizon = route["eval_card"].get("expected_horizon")
        if isinstance(horizon, int) and horizon > 0:
            max_steps = horizon
    return run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=fixture_plan.get("task_id", result_context["task_id"]),
        task_prompt=fixture_plan.get("task_prompt", result_context["task_prompt"]),
        benchmark_family=eval_family,
        case_id=result_context["eval_id"],
        seed_id=result_context["variant_id"],
        model_route=model_route,
        model_client_kwargs=merged_model_client_kwargs,
        runtime_probe=fixture_plan.get("runtime_probe"),
        workspace_state_overrides=fixture_plan.get("workspace_state_overrides"),
        execution_state_overrides=fixture_plan.get("execution_state_overrides"),
        max_steps=max_steps,
        route_manifest=route_manifest,
        enforce_packet04_route_contract=enforce_packet04_route_contract,
    )


def _resolve_batch_model_route_override(
    *,
    route: dict[str, Any],
    batch_model_policy: dict[str, Any] | None,
    batch_model_route_override: dict[str, Any] | None,
    model_tier_selector: str,
    batch_provider_route: str | None,
) -> dict[str, Any] | None:
    if batch_model_route_override is not None:
        return batch_model_route_override
    provider_route = batch_provider_route
    if provider_route is None:
        eval_card = route.get("eval_card")
        if not isinstance(eval_card, dict):
            return None
        fixed_invariants = eval_card.get("fixed_invariants")
        if not isinstance(fixed_invariants, dict):
            return None
        provider_route = fixed_invariants.get("provider_route")
    if provider_route != "openai_api":
        return None
    if route.get("execution_mode") == "deterministic_no_model":
        return None
    policy_source = batch_model_policy if isinstance(batch_model_policy, dict) else route.get("model_tier_policy")
    if not isinstance(policy_source, dict):
        return None
    selected_tier = policy_source.get(model_tier_selector)
    if not isinstance(selected_tier, str) or not selected_tier:
        return None
    if selected_tier in {"no_model", "not_applicable"}:
        return None
    if selected_tier.startswith("azure:"):
        azure_model_name = selected_tier.split("azure:", 1)[1]
        if azure_model_name == "gpt-5.4-mini":
            return make_azure_gpt54_mini_route_from_env(request_settings={"temperature": 0})
        if azure_model_name == "gpt-5.3-codex":
            return make_azure_gpt53_codex_route_from_env(request_settings={"temperature": 0})
        raise SchemaValidationError(
            "batch_spec.provider_route=openai_api with azure model tier requires "
            "azure:gpt-5.4-mini or azure:gpt-5.3-codex"
        )
    model_name = selected_tier
    for prefix in ("oauth:",):
        if model_name.startswith(prefix):
            model_name = model_name.split(prefix, 1)[1]
            break
    if not model_name:
        return None
    return make_openai_chat_completions_route(
        model_name=model_name,
        request_settings={"temperature": 0},
    )


def _resolve_batch_provider_route(batch: dict[str, Any]) -> str | None:
    provider_candidates = [
        batch.get("provider_route"),
    ]
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        provider_candidates.append(fixed_invariants.get("provider_route"))
    for provider_route in provider_candidates:
        if provider_route is None:
            continue
        if not isinstance(provider_route, str):
            raise SchemaValidationError("batch_spec.provider_route must be a string when provided")
        if provider_route not in {"openai_api", "codex_subscription", "local_stub", "none", "oauth"}:
            raise SchemaValidationError(f"unsupported batch_spec.provider_route: {provider_route}")
        return provider_route
    return None


def _resolve_multistep_turn_budget(eval_card: Any) -> int:
    if not isinstance(eval_card, dict):
        return 3
    budget = eval_card.get("multistep_turn_budget")
    if not isinstance(budget, int):
        return 3
    if budget < 2:
        return 2
    return min(budget, 8)


def _write_eval_run_header(
    *,
    batch: dict[str, Any],
    route: dict[str, Any],
    result_context: dict[str, Any],
    execution_result: dict[str, Any],
    run_dir: Path,
) -> None:
    run_header = dict(execution_result.get("run_header", {}))
    routed_modules = run_header.get("routed_modules", [])
    routed_module_paths = [
        entry["real_file_path"]
        for entry in routed_modules
        if isinstance(entry, dict) and isinstance(entry.get("real_file_path"), str)
    ]
    run_header.update(
        {
            "batch_id": batch["batch_id"],
            "eval_id": result_context["eval_id"],
            "variant_id": result_context["variant_id"],
            "rerun_index": result_context["rerun_index"],
            "evaluation_lane": route["evaluation_lane"],
            "promotion_authority": route["promotion_authority"],
            "route_id": route["route_id"],
            "route_contract_id": batch.get("route_contract_id", "packet03_route_contract.v1"),
            "routed_module_paths": routed_module_paths,
            "run_fingerprint": fingerprint_payload(
                {
                    "run_id": run_header.get("run_id"),
                    "route_id": route["route_id"],
                    "evaluation_lane": route["evaluation_lane"],
                    "variant_id": result_context["variant_id"],
                    "route_manifest_fingerprint": run_header.get("route_manifest_fingerprint"),
                    "routed_modules": [
                        {
                            "surface_id": entry.get("surface_id"),
                            "real_file_path": entry.get("real_file_path"),
                            "file_sha256": entry.get("file_sha256"),
                        }
                        for entry in routed_modules
                        if isinstance(entry, dict)
                    ],
                }
            ),
        }
    )
    validate_eval_run_header_metadata(run_header, "run_header")
    _write_json(run_dir / "run_header.json", run_header)
    execution_result["run_header"] = run_header


def _validate_run_artifacts(run_dir: Path) -> None:
    for artifact_name in ("run_header.json", "run_events.jsonl", "score_envelope.json", "route_manifest.json"):
        artifact_path = run_dir / artifact_name
        if not artifact_path.exists():
            raise SchemaValidationError(f"missing run artifact: {artifact_path}")


def _append_governed_eval_truth_event(
    *,
    run_dir: Path,
    eval_id: str,
    execution_mode: str,
    execution_result: dict[str, Any],
) -> None:
    raw_execution_truth = _derive_raw_execution_truth(execution_result=execution_result)
    governed_eval_truth = _derive_governed_eval_truth(
        eval_id=eval_id,
        execution_mode=execution_mode,
        execution_result=execution_result,
    )
    execution_result["raw_execution_truth"] = raw_execution_truth
    execution_result["governed_eval_truth"] = governed_eval_truth

    events = execution_result.get("run_events")
    if not isinstance(events, list):
        events = []
    event = {
        "seq": len(events),
        "ts_utc": utc_now(),
        "phase": "eval",
        "event_type": "governed_eval_truth_finalized",
        "correlation_id": None,
        "payload": {
            "details": {
                "raw_execution_truth": raw_execution_truth,
                "governed_eval_truth": governed_eval_truth,
            }
        },
        "artifact_refs": [],
    }
    validate_event(event)
    events.append(event)
    execution_result["run_events"] = events
    run_events_path = run_dir / "run_events.jsonl"
    with run_events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _derive_raw_execution_truth(*, execution_result: dict[str, Any]) -> dict[str, Any]:
    execution = execution_result.get("execution", {})
    status = execution.get("status")
    if not isinstance(status, str) or not status:
        status = "missing"
    terminal_outcome = execution.get("terminal_outcome")
    terminal_outcome_status = None
    if isinstance(terminal_outcome, dict):
        terminal_status = terminal_outcome.get("status")
        if isinstance(terminal_status, str) and terminal_status:
            terminal_outcome_status = terminal_status
    raw_truth = {
        "execution_status": status,
        "step_count": int(execution.get("step_count", 0) or 0),
        "terminal_outcome_status": terminal_outcome_status,
    }
    return raw_truth


def _derive_governed_eval_truth(
    *,
    eval_id: str,
    execution_mode: str,
    execution_result: dict[str, Any],
) -> dict[str, Any]:
    score = execution_result.get("score_envelope", {})
    aggregate = score.get("aggregate") if isinstance(score, dict) else {}
    final_verdict = aggregate.get("final_verdict") if isinstance(aggregate, dict) else None
    if not isinstance(final_verdict, str) or not final_verdict:
        final_verdict = "unresolved"
    trace = execution_result.get("packet03_eval_trace")
    if not isinstance(trace, dict):
        trace = {}
    governed_terminal_status = _derive_tool_family_terminal_status(
        eval_id=eval_id,
        execution_mode=execution_mode,
        execution_result=execution_result,
        packet03_trace=trace,
    )
    authority_closure = _derive_tool_family_authority_closure(
        eval_id=eval_id,
        governed_terminal_status=governed_terminal_status,
        final_verdict=final_verdict,
        packet03_trace=trace,
    )
    governed_truth = {
        "truth_source": "post_grader",
        "truth_version": "packet05a_governed_eval_truth.v1",
        "final_verdict": final_verdict,
        "governed_terminal_status": governed_terminal_status,
        "completion_scope": authority_closure["completion_scope"],
        "authority_completeness": authority_closure["authority_completeness"],
        "authority_incomplete_reasons": authority_closure["authority_incomplete_reasons"],
    }
    return governed_truth


def _derive_tool_family_terminal_status(
    *,
    eval_id: str,
    execution_mode: str,
    execution_result: dict[str, Any],
    packet03_trace: dict[str, Any],
) -> str:
    execution_status = execution_result.get("execution", {}).get("status")
    if not isinstance(execution_status, str):
        execution_status = "missing"
    if eval_id not in TOOL_FAMILY_AUTHORITY_EVAL_IDS:
        return "not_applicable"
    if execution_mode not in {"deterministic_no_model", "multistep_batchable"}:
        return "not_applicable"
    if execution_status == "error":
        return "tool_eval_execution_error"
    planned_case_count = _tool_family_planned_case_count(eval_id=eval_id, packet03_trace=packet03_trace)
    observed_case_count = _tool_family_observed_case_count(eval_id=eval_id, packet03_trace=packet03_trace)
    if planned_case_count > 0 and observed_case_count >= planned_case_count:
        return "tool_eval_completed"
    return "tool_eval_incomplete"


def _derive_tool_family_authority_closure(
    *,
    eval_id: str,
    governed_terminal_status: str,
    final_verdict: str,
    packet03_trace: dict[str, Any],
) -> dict[str, Any]:
    if eval_id not in TOOL_FAMILY_AUTHORITY_EVAL_IDS:
        return {
            "completion_scope": "not_applicable",
            "authority_completeness": "not_applicable",
            "authority_incomplete_reasons": [],
        }

    incomplete_reasons: list[str] = []
    if governed_terminal_status != "tool_eval_completed":
        incomplete_reasons.append("case_coverage_not_complete")
    if final_verdict != "pass":
        incomplete_reasons.append("governed_final_verdict_not_pass")

    if not bool(packet03_trace.get("mechanism_visibility_complete")):
        incomplete_reasons.append("mechanism_visibility_incomplete")
    if not bool(packet03_trace.get("schema_complete_for_promotion")):
        incomplete_reasons.append("schema_complete_for_promotion_false")
    if bool(packet03_trace.get("helper_only_evidence")):
        incomplete_reasons.append("helper_only_or_proxy_evidence")

    if eval_id == "ae_tool_result_attribution_quality_v2" and not _tool_result_attribution_trace_complete(packet03_trace):
        incomplete_reasons.append("tool_result_trace_incomplete")
    if eval_id == "ae_tool_call_contract_quality_v2" and not _tool_call_contract_trace_complete(packet03_trace):
        incomplete_reasons.append("tool_call_trace_incomplete")
    if eval_id == "ae_internal_artifact_log_extraction_v1" and not _artifact_log_trace_complete(packet03_trace):
        incomplete_reasons.append("artifact_log_trace_incomplete")
    if eval_id == "ae_internal_toolchain_dependency_pressure_v1" and not _toolchain_pressure_trace_complete(packet03_trace):
        incomplete_reasons.append("toolchain_pressure_trace_incomplete")

    authority_completeness = "complete" if not incomplete_reasons else "incomplete"
    if authority_completeness not in GOVERNED_TRUTH_AUTHORITY_COMPLETENESS:
        raise SchemaValidationError("invalid governed authority completeness state")

    completion_scope = "case_coverage_only"
    if completion_scope not in GOVERNED_TRUTH_COMPLETION_SCOPES:
        raise SchemaValidationError("invalid governed completion scope state")

    return {
        "completion_scope": completion_scope,
        "authority_completeness": authority_completeness,
        "authority_incomplete_reasons": sorted(set(incomplete_reasons)),
    }


def _tool_family_planned_case_count(*, eval_id: str, packet03_trace: dict[str, Any]) -> int:
    if eval_id == "ae_tool_call_contract_quality_v2":
        return int(packet03_trace.get("tool_contract_cases_total", 0) or 0)
    if eval_id == "ae_tool_result_attribution_quality_v2":
        return int(packet03_trace.get("tool_result_attribution_cases_total", 0) or 0)
    if eval_id == "ae_internal_toolchain_dependency_pressure_v1":
        return int(packet03_trace.get("toolchain_pressure_cases_total", 0) or 0)
    if eval_id == "ae_internal_artifact_log_extraction_v1":
        return int(packet03_trace.get("artifact_log_cases_total", 0) or 0)
    return 0


def _tool_family_observed_case_count(*, eval_id: str, packet03_trace: dict[str, Any]) -> int:
    if eval_id == "ae_tool_call_contract_quality_v2":
        case_results = packet03_trace.get("tool_contract_case_results")
    elif eval_id == "ae_tool_result_attribution_quality_v2":
        case_results = packet03_trace.get("tool_result_attribution_case_results")
    elif eval_id == "ae_internal_toolchain_dependency_pressure_v1":
        case_results = packet03_trace.get("toolchain_pressure_case_results")
    elif eval_id == "ae_internal_artifact_log_extraction_v1":
        case_results = packet03_trace.get("artifact_log_case_results")
    else:
        return 0
    if not isinstance(case_results, list):
        return 0
    count = 0
    for item in case_results:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("observed_reason_code"), str) and item["observed_reason_code"]:
            count += 1
    return count


def _build_trace_summary(
    *,
    run_id: str,
    eval_id: str,
    variant_id: str,
    execution_mode: str,
    evaluation_lane: str,
    promotion_authority: bool,
    execution_result: dict[str, Any],
    result_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = execution_result["score_envelope"]
    events = execution_result["run_events"]
    raw_execution_truth = execution_result.get("raw_execution_truth")
    if not isinstance(raw_execution_truth, dict):
        raw_execution_truth = _derive_raw_execution_truth(execution_result=execution_result)
    governed_eval_truth = execution_result.get("governed_eval_truth")
    if not isinstance(governed_eval_truth, dict):
        governed_eval_truth = _derive_governed_eval_truth(
            eval_id=eval_id,
            execution_mode=execution_mode,
            execution_result=execution_result,
        )
    layer_l4 = score["layers"]["L4_final_acceptance"]
    trace_summary = {
        "run_id": run_id,
        "variant_id": variant_id,
        "execution_mode": execution_mode,
        "evaluation_lane": evaluation_lane,
        "promotion_authority": promotion_authority,
        "eval_id": eval_id,
        "raw_execution_truth": raw_execution_truth,
        "governed_eval_truth": governed_eval_truth,
        "error_summary": {
            "event_count": len(events),
            "execution_status": execution_result["execution"]["status"],
        },
        "loop_pattern_summary": {
            "step_count": execution_result["execution"]["step_count"],
            "status": execution_result["execution"]["status"],
        },
        "tool_error_summary": {"tool_error_events": _count_tool_errors(events)},
        "workspace_integrity_summary": {
            "verified": bool(execution_result["verified"]),
        },
        "verifier_final_contradiction_summary": {
            "final_verdict": score["aggregate"]["final_verdict"],
            "l4_reason_codes": list(layer_l4.get("reason_codes", [])),
        },
        "token_spike_summary": {"token_spike_detected": False},
        "recovery_summary": {"recovery_events": _count_recovery_events(events)},
    }
    trace_summary["declared_mechanisms"] = _declared_mechanism_summary(
        variant_id=variant_id,
        run_header=execution_result.get("run_header"),
    )
    trace_summary["observed_mechanisms"] = _observed_mechanism_summary(
        variant_id=variant_id,
        eval_id=eval_id,
        execution_result=execution_result,
    )
    if isinstance(result_context, dict):
        for field in ("claim_route_id", "task_intent"):
            value = result_context.get(field)
            if isinstance(value, str) and value:
                trace_summary[field] = value
    packet03_trace = execution_result.get("packet03_eval_trace")
    if isinstance(packet03_trace, dict):
        trace_summary["packet03_eval_summary"] = packet03_trace
    return trace_summary


def _declared_mechanism_summary(*, variant_id: str, run_header: Any) -> dict[str, Any]:
    claimed_runtime_keys: list[str] = []
    claimed_surface_ids: list[str] = []
    if isinstance(run_header, dict):
        routed_modules = run_header.get("routed_modules")
        if isinstance(routed_modules, list):
            for entry in routed_modules:
                if not isinstance(entry, dict) or not bool(entry.get("claimed_changed_surface")):
                    continue
                runtime_key = entry.get("runtime_key")
                if isinstance(runtime_key, str) and runtime_key:
                    claimed_runtime_keys.append(runtime_key)
                surface_id = entry.get("surface_id")
                if isinstance(surface_id, str) and surface_id:
                    claimed_surface_ids.append(surface_id)
    return {
        "declared_mechanism_contract_version": "successor_declared_mechanisms.v1",
        "variant_id": variant_id,
        "claimed_runtime_keys": sorted(set(claimed_runtime_keys)),
        "claimed_surface_ids": sorted(set(claimed_surface_ids)),
    }


def _observed_mechanism_summary(
    *,
    variant_id: str,
    eval_id: str,
    execution_result: dict[str, Any],
) -> dict[str, Any]:
    if variant_id != SUCCESSOR_RHV1_REFERENCE_VARIANT_ID:
        return {
            "observed_mechanism_contract_version": "successor_observed_mechanisms.v1",
            "variant_id": variant_id,
            "marker_family": "none",
            "markers": {},
        }

    packet03_trace = execution_result.get("packet03_eval_trace")
    if not isinstance(packet03_trace, dict):
        packet03_trace = {}
    history = execution_result.get("execution", {}).get("history", [])
    verification = execution_result.get("verification", {})
    score = execution_result.get("score_envelope", {})

    raw_markers = {
        "environment_aware_orientation": _marker_entry(
            observed=_observed_environment_aware_orientation(history),
            evidence_refs=["execution.history[0].content"],
        ),
        "target_state_updates": _marker_entry(
            observed=_observed_target_state_updates(execution_result=execution_result, packet03_trace=packet03_trace),
            evidence_refs=["execution.steps[].results[].command", "packet03_eval_summary.final_evidence_packet.changed_files"],
        ),
        "evidence_state_ledger_entries": _marker_entry(
            observed=_observed_evidence_state_entries(packet03_trace),
            evidence_refs=["packet03_eval_summary.discovery_step_evidence", "packet03_eval_summary.final_justification_markers"],
        ),
        "structured_state_context_summaries": _marker_entry(
            observed=_observed_structured_state_summaries(packet03_trace),
            evidence_refs=["packet03_eval_summary.bounded_probing_markers", "packet03_eval_summary.inspect_before_edit_markers"],
        ),
        "evidence_backed_completion_gate": _marker_entry(
            observed=_observed_evidence_backed_completion_gate(packet03_trace),
            evidence_refs=["packet03_eval_summary.final_justification_markers", "packet03_eval_summary.final_evidence_packet"],
        ),
        "verification_before_completion_decision": _marker_entry(
            observed=_observed_verification_before_completion(packet03_trace=packet03_trace, verification=verification),
            evidence_refs=["packet03_eval_summary.verify_before_completion", "verification.layer_statuses"],
        ),
        "failure_source_typing": _marker_entry(
            observed=_observed_failure_source_typing(
                eval_id=eval_id,
                score_envelope=score if isinstance(score, dict) else {},
            ),
            evidence_refs=["score_envelope.aggregate.final_verdict", "score_envelope.layers.*.reason_codes"],
        ),
    }
    markers = {
        marker_id: raw_markers.get(marker_id, _marker_entry(observed=False, evidence_refs=[]))
        for marker_id in SUCCESSOR_RHV1_OBSERVED_MARKER_IDS
    }
    return {
        "observed_mechanism_contract_version": "successor_observed_mechanisms.v1",
        "variant_id": variant_id,
        "marker_family": "rhv1_observed_markers.v1",
        "markers": markers,
    }


def _marker_entry(*, observed: bool, evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "observed": bool(observed),
        "evidence_refs": [ref for ref in evidence_refs if isinstance(ref, str) and ref],
    }


def _observed_environment_aware_orientation(history: Any) -> bool:
    if not isinstance(history, list) or not history:
        return False
    first = history[0]
    if not isinstance(first, dict):
        return False
    content = first.get("content")
    if not isinstance(content, str):
        return False
    return "Workspace cwd:" in content and "Task id:" in content


def _observed_target_state_updates(*, execution_result: dict[str, Any], packet03_trace: dict[str, Any]) -> bool:
    final_packet = packet03_trace.get("final_evidence_packet")
    if isinstance(final_packet, dict):
        changed = final_packet.get("changed_files")
        if isinstance(changed, list) and any(isinstance(path, str) and path for path in changed):
            return True
    return _execution_contains_write_command(execution_result)


def _execution_contains_write_command(execution_result: dict[str, Any]) -> bool:
    execution = execution_result.get("execution")
    if not isinstance(execution, dict):
        return False
    steps = execution.get("steps")
    if not isinstance(steps, list):
        return False
    write_markers = (" >", ">>", "cp ", "mv ", "sed ", "tee ", "python3 - <<", "cat <<")
    for step in steps:
        if not isinstance(step, dict):
            continue
        results = step.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            command = result.get("command")
            if not isinstance(command, str):
                continue
            lowered = f" {command.lower()} "
            if any(marker in lowered for marker in write_markers):
                return True
    return False


def _observed_evidence_state_entries(packet03_trace: dict[str, Any]) -> bool:
    final_markers = packet03_trace.get("final_justification_markers")
    if isinstance(final_markers, dict):
        return True
    final_packet = packet03_trace.get("final_evidence_packet")
    if isinstance(final_packet, dict):
        return True
    return False


def _observed_structured_state_summaries(packet03_trace: dict[str, Any]) -> bool:
    for key in ("bounded_probing_markers", "inspect_before_edit_markers", "assistant_completion_trace"):
        if isinstance(packet03_trace.get(key), dict):
            return True
    return False


def _observed_evidence_backed_completion_gate(packet03_trace: dict[str, Any]) -> bool:
    final_markers = packet03_trace.get("final_justification_markers")
    if isinstance(final_markers, dict) and final_markers.get("canonical") is True:
        return True
    final_packet = packet03_trace.get("final_evidence_packet")
    if isinstance(final_packet, dict):
        verifier_command = final_packet.get("verifier_command")
        if isinstance(verifier_command, str) and verifier_command:
            return True
    return False


def _observed_verification_before_completion(*, packet03_trace: dict[str, Any], verification: Any) -> bool:
    verify_before_completion = packet03_trace.get("verify_before_completion")
    if isinstance(verify_before_completion, bool):
        return verify_before_completion
    if isinstance(packet03_trace.get("verifier_execution_seen"), bool):
        return bool(packet03_trace.get("verifier_execution_seen"))
    if isinstance(verification, dict):
        layer_statuses = verification.get("layer_statuses")
        if isinstance(layer_statuses, dict):
            return bool(layer_statuses)
    return False


def _observed_failure_source_typing(*, eval_id: str, score_envelope: dict[str, Any]) -> bool:
    if not isinstance(score_envelope, dict):
        return False
    reason_codes = _collect_reason_codes(score_envelope)
    cluster = _derive_failure_cluster(score_envelope, reason_codes=reason_codes, eval_id=eval_id)
    return isinstance(cluster, str) and bool(cluster)


def _build_result_record(
    *,
    batch: dict[str, Any],
    route: dict[str, Any],
    result_context: dict[str, Any],
    run_id: str,
    trace_summary_ref: str,
    execution_result: dict[str, Any],
    fixture_plan: dict[str, Any],
    route_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    score = execution_result["score_envelope"]
    run_header = execution_result["run_header"]
    reason_codes = _collect_reason_codes(score)
    token_summary = _token_and_cost_summary(execution_result)
    budget_cap = dict(batch["budget_caps"])
    budget_cap_usd = _coerce_float(batch.get("budget_cap_usd"))
    if budget_cap_usd <= 0:
        budget_cap_usd = _coerce_float(budget_cap.get("usd"))
    budget_spend_usd = _coerce_float(token_summary.get("usd_estimate"))
    budget_used = {
        "run_count": 1,
        "estimated_tokens": token_summary["total_tokens"],
        "usd": budget_spend_usd,
    }
    routed_modules = run_header.get("routed_modules", [])
    claimed_surface_fingerprints, unchanged_surface_fingerprints = _surface_fingerprint_maps(routed_modules)
    route_manifest_fingerprint = run_header.get("route_manifest_fingerprint")
    route_manifest_ref = str(Path("runs") / run_id / "route_manifest.json")
    if isinstance(run_header.get("route_manifest_ref"), str) and run_header["route_manifest_ref"]:
        route_manifest_ref = str(Path("runs") / run_id / run_header["route_manifest_ref"])
    variant_card_ref = run_header.get("variant_card_ref")
    if not isinstance(variant_card_ref, str):
        variant_card_ref = route_manifest.get("variant_card_ref") if isinstance(route_manifest, dict) else None
    lane_state = _derive_lane_state(
        batch=batch,
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )
    measurement_state = _derive_measurement_authority_state(
        eval_id=result_context["eval_id"],
        execution_result=execution_result,
        fixture_plan=fixture_plan,
        lane_state=lane_state,
    )
    lane_state = _apply_measurement_blockers(
        lane_state=lane_state,
        evaluation_lane=route["evaluation_lane"],
        measurement_state=measurement_state,
        final_verdict=score["aggregate"]["final_verdict"],
    )
    grader_version = _derive_grader_version(
        run_header=run_header,
        execution_result=execution_result,
        measurement_state=measurement_state,
    )
    governed_eval_truth = execution_result.get("governed_eval_truth")
    if not isinstance(governed_eval_truth, dict):
        governed_eval_truth = _derive_governed_eval_truth(
            eval_id=result_context["eval_id"],
            execution_mode=route["execution_mode"],
            execution_result=execution_result,
        )
    governed_terminal_status = governed_eval_truth.get("governed_terminal_status")
    if not isinstance(governed_terminal_status, str) or not governed_terminal_status:
        governed_terminal_status = "not_applicable"
    governed_truth_ref = str(Path("runs") / run_id / "run_events.jsonl#event_type=governed_eval_truth_finalized")
    claim_route_id = result_context.get("claim_route_id")
    task_intent = result_context.get("task_intent")
    record = {
        "batch_id": batch["batch_id"],
        "run_id": run_id,
        "variant_id": result_context["variant_id"],
        "contender_id": result_context["variant_id"],
        "eval_id": result_context["eval_id"],
        "task_id": result_context["task_id"],
        "rerun_index": result_context["rerun_index"],
        "model_route": run_header["model_route"],
        "effective_settings_id": run_header["model_route"]["request_settings_fingerprint"],
        "invariant_fingerprint": fingerprint_payload(
            {
                "fixed_invariants": batch["fixed_invariants"],
                "eval_id": result_context["eval_id"],
                "evaluation_lane": route["evaluation_lane"],
                "task_set_id": batch["task_set_id"],
            }
        ),
        "variant_card_ref": variant_card_ref,
        "route_manifest_ref": route_manifest_ref,
        "route_manifest_fingerprint": route_manifest_fingerprint,
        "claimed_surface_fingerprints": claimed_surface_fingerprints,
        "unchanged_surface_fingerprints": unchanged_surface_fingerprints,
        "grader_version": grader_version,
        "score_summary": {"final_verdict": score["aggregate"]["final_verdict"]},
        "reason_codes": reason_codes,
        "token_and_cost_summary": token_summary,
        "budget_used": budget_used,
        "budget_cap": budget_cap,
        "budget_cap_usd": budget_cap_usd,
        "budget_spend_usd": budget_spend_usd,
        "promotion_authority": lane_state["promotion_authority"],
        "promotion_blocker_codes": lane_state["promotion_blocker_codes"],
        "promotion_eligibility": lane_state["promotion_eligibility"],
        "forced_probe_observed": lane_state["forced_probe_observed"],
        "standin_observed": lane_state["standin_observed"],
        "legacy_lane_artifact_detected": lane_state["legacy_lane_artifact_detected"],
        "governed_truth_ref": governed_truth_ref,
        "governed_terminal_status": governed_terminal_status,
        "stability_metrics_summary": {
            "evaluation_lane": route["evaluation_lane"],
            "rerun_count_target": batch["rerun_count"],
            "rerun_index": result_context["rerun_index"],
        },
        "trace_summary_ref": trace_summary_ref,
        "failure_cluster": _derive_failure_cluster(
            score,
            reason_codes=reason_codes,
            eval_id=result_context["eval_id"],
        ),
        "secondary_failure_tags": [],
        "promotion_flags": {"human_gate_required": True, "draft_only": True},
        "execution_mode": route["execution_mode"],
        "evaluation_lane": route["evaluation_lane"],
        "run_artifact_refs": {
            "run_header_ref": str(Path("runs") / run_id / "run_header.json"),
            "run_events_ref": str(Path("runs") / run_id / "run_events.jsonl"),
            "score_envelope_ref": str(Path("runs") / run_id / "score_envelope.json"),
            "route_manifest_ref": route_manifest_ref,
        },
        "recommendation_gate_inputs": {
            "lane_class": route["evaluation_lane"],
            "surface_bounded": _surface_is_bounded(
                lane_class=route["evaluation_lane"],
                blocker_codes=lane_state["promotion_blocker_codes"],
            ),
            "mechanism_visibility_complete": measurement_state["mechanism_visibility_complete"],
            "schema_complete_for_promotion": measurement_state["schema_complete_for_promotion"],
            "helper_only_evidence": measurement_state["helper_only_evidence"],
            "comparator_variant_id": _resolve_comparator_variant_id(batch) or "missing",
            "same_batch_comparator_run_ids": [],
            "primary_delta_metric": None,
            "corroboration_surface_ids": [],
            "audit_status_aa": "missing",
            "audit_status_ab": "missing",
            "audit_artifact_ref_aa": None,
            "audit_artifact_ref_ab": None,
            "forced_probe_observed": lane_state["forced_probe_observed"],
            "standin_observed": lane_state["standin_observed"],
            "variant_card_ref": variant_card_ref,
            "route_manifest_ref": route_manifest_ref,
            "route_manifest_fingerprint": route_manifest_fingerprint,
            "claimed_surface_fingerprints": claimed_surface_fingerprints,
            "unchanged_surface_fingerprints": unchanged_surface_fingerprints,
            "governed_truth_ref": governed_truth_ref,
            "governed_terminal_status": governed_terminal_status,
        },
    }
    if isinstance(claim_route_id, str) and claim_route_id:
        record["claim_route_id"] = claim_route_id
    if isinstance(task_intent, str) and task_intent:
        record["task_intent"] = task_intent
    return record


def _derive_measurement_authority_state(
    *,
    eval_id: str,
    execution_result: dict[str, Any],
    fixture_plan: dict[str, Any],
    lane_state: dict[str, Any],
) -> dict[str, bool]:
    packet03_trace = execution_result.get("packet03_eval_trace")
    if isinstance(packet03_trace, dict):
        explicit_mechanism = packet03_trace.get("mechanism_visibility_complete")
        explicit_schema = packet03_trace.get("schema_complete_for_promotion")
        explicit_helper_only = packet03_trace.get("helper_only_evidence")
        if all(isinstance(value, bool) for value in (explicit_mechanism, explicit_schema, explicit_helper_only)):
            if eval_id == "ae_tool_result_attribution_quality_v2":
                attribution_complete = _tool_result_attribution_trace_complete(packet03_trace)
                if not attribution_complete:
                    return {
                        "mechanism_visibility_complete": False,
                        "schema_complete_for_promotion": False,
                        "helper_only_evidence": False,
                    }
            return {
                "mechanism_visibility_complete": bool(explicit_mechanism),
                "schema_complete_for_promotion": bool(explicit_schema),
                "helper_only_evidence": bool(explicit_helper_only),
            }

    fixture_lane_metadata = fixture_plan.get("lane_metadata")
    if isinstance(fixture_lane_metadata, dict):
        explicit_mechanism = fixture_lane_metadata.get("mechanism_visibility_complete")
        explicit_schema = fixture_lane_metadata.get("schema_complete_for_promotion")
        explicit_helper_only = fixture_lane_metadata.get("helper_only_evidence")
        if all(isinstance(value, bool) for value in (explicit_mechanism, explicit_schema, explicit_helper_only)):
            return {
                "mechanism_visibility_complete": bool(explicit_mechanism),
                "schema_complete_for_promotion": bool(explicit_schema),
                "helper_only_evidence": bool(explicit_helper_only),
            }

    if eval_id in LEGACY_PROXY_PROMOTION_SURFACE_EVAL_IDS:
        return {
            "mechanism_visibility_complete": False,
            "schema_complete_for_promotion": False,
            "helper_only_evidence": True,
        }

    if lane_state["forced_probe_observed"] or lane_state["standin_observed"]:
        return {
            "mechanism_visibility_complete": False,
            "schema_complete_for_promotion": False,
            "helper_only_evidence": True,
        }

    return {
        "mechanism_visibility_complete": True,
        "schema_complete_for_promotion": True,
        "helper_only_evidence": False,
    }


def _tool_result_attribution_trace_complete(packet03_trace: dict[str, Any]) -> bool:
    case_results = packet03_trace.get("tool_result_attribution_case_results")
    if not isinstance(case_results, list) or not case_results:
        return False
    for case in case_results:
        if not isinstance(case, dict):
            return False
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            return False
        attribution_trace = case.get("attribution_trace")
        if not isinstance(attribution_trace, dict):
            return False
        permission_signal = attribution_trace.get("permission_signal_detected")
        runtime_signal = attribution_trace.get("runtime_signal_detected")
        if not isinstance(permission_signal, bool) or not isinstance(runtime_signal, bool):
            return False
        if case.get("expected_reason_code") == "tool_runtime_mixed_permission_runtime_signals":
            if permission_signal is not True or runtime_signal is not True:
                return False
    return True


def _tool_call_contract_trace_complete(packet03_trace: dict[str, Any]) -> bool:
    case_results = packet03_trace.get("tool_contract_case_results")
    if not isinstance(case_results, list) or not case_results:
        return False
    for case in case_results:
        if not isinstance(case, dict):
            return False
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            return False
        for key in (
            "expected_contract_class",
            "observed_contract_class",
            "expected_result_class",
            "observed_result_class",
            "expected_reason_code",
            "observed_reason_code",
        ):
            value = case.get(key)
            if not isinstance(value, str) or not value:
                return False
    return True


def _artifact_log_trace_complete(packet03_trace: dict[str, Any]) -> bool:
    case_results = packet03_trace.get("artifact_log_case_results")
    if not isinstance(case_results, list) or not case_results:
        return False
    for case in case_results:
        if not isinstance(case, dict):
            return False
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            return False
        for key in ("expected_result_class", "observed_result_class", "expected_reason_code", "observed_reason_code"):
            value = case.get(key)
            if not isinstance(value, str) or not value:
                return False
        attribution_trace = case.get("attribution_trace")
        if not isinstance(attribution_trace, dict):
            return False
        permission_signal = attribution_trace.get("permission_signal_detected")
        runtime_signal = attribution_trace.get("runtime_signal_detected")
        if not isinstance(permission_signal, bool) or not isinstance(runtime_signal, bool):
            return False
        if case.get("expected_reason_code") == "tool_runtime_mixed_permission_runtime_signals":
            if permission_signal is not True or runtime_signal is not True:
                return False
    return True


def _toolchain_pressure_trace_complete(packet03_trace: dict[str, Any]) -> bool:
    case_results = packet03_trace.get("toolchain_pressure_case_results")
    if not isinstance(case_results, list) or not case_results:
        return False
    for case in case_results:
        if not isinstance(case, dict):
            return False
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            return False
        for key in (
            "expected_contract_class",
            "observed_contract_class",
            "expected_result_class",
            "observed_result_class",
            "expected_reason_code",
            "observed_reason_code",
        ):
            value = case.get(key)
            if not isinstance(value, str) or not value:
                return False
    return True


def _apply_measurement_blockers(
    *,
    lane_state: dict[str, Any],
    evaluation_lane: str,
    measurement_state: dict[str, bool],
    final_verdict: str,
) -> dict[str, Any]:
    updated = dict(lane_state)
    blocker_codes = {
        code
        for code in updated.get("promotion_blocker_codes", [])
        if isinstance(code, str) and code
    }
    if evaluation_lane == "promotion":
        if not measurement_state.get("mechanism_visibility_complete", False):
            blocker_codes.add("mechanism_visibility_incomplete")
        if (
            not measurement_state.get("schema_complete_for_promotion", False)
            or measurement_state.get("helper_only_evidence", False)
        ):
            blocker_codes.add("schema_missing_required_fields")
        if final_verdict != "pass":
            blocker_codes.add("lane_policy_restriction")
        if blocker_codes:
            if "schema_missing_required_fields" in blocker_codes:
                promotion_eligibility = "blocked_schema_missing_required_fields"
            else:
                promotion_eligibility = f"blocked_{sorted(blocker_codes)[0]}"
        else:
            promotion_eligibility = "eligible"
        updated["promotion_eligibility"] = promotion_eligibility
    updated["promotion_blocker_codes"] = sorted(blocker_codes)
    return updated


def _derive_grader_version(
    *,
    run_header: dict[str, Any],
    execution_result: dict[str, Any],
    measurement_state: dict[str, bool],
) -> str:
    base_version = run_header["scoring_contract"]["scoring_contract_version"]
    packet03_trace = execution_result.get("packet03_eval_trace")
    if not isinstance(packet03_trace, dict):
        return base_version
    parts = [base_version]
    grader_id = packet03_trace.get("grader_id")
    if isinstance(grader_id, str) and grader_id:
        parts.append(grader_id)
    if any(
        key in packet03_trace
        for key in ("mechanism_visibility_complete", "schema_complete_for_promotion", "helper_only_evidence")
    ):
        measurement_tag = "packet05a_mechanism_visible_v1"
        if (
            not measurement_state.get("mechanism_visibility_complete", False)
            or not measurement_state.get("schema_complete_for_promotion", False)
            or measurement_state.get("helper_only_evidence", False)
        ):
            measurement_tag = "packet05a_proxy_or_incomplete_v1"
        parts.append(measurement_tag)
    return "+".join(parts)


def _derive_lane_state(
    *,
    batch: dict[str, Any],
    route: dict[str, Any],
    execution_result: dict[str, Any],
    fixture_plan: dict[str, Any],
) -> dict[str, Any]:
    blocker_codes = {
        code
        for code in route.get("lane_blocker_codes", [])
        if isinstance(code, str) and code
    }
    fixture_lane_metadata = fixture_plan.get("lane_metadata")
    if isinstance(fixture_lane_metadata, dict):
        for code in fixture_lane_metadata.get("promotion_blocker_codes", []):
            if isinstance(code, str) and code:
                blocker_codes.add(code)
    forced_probe_observed = _forced_probe_observed(execution_result, fixture_plan)
    standin_observed = _standin_observed(batch, execution_result)
    legacy_lane_artifact_detected = _legacy_lane_artifact_detected(batch, route)
    if forced_probe_observed:
        blocker_codes.add("forced_probe_dependency")
    if standin_observed:
        blocker_codes.add("standin_dependency")
    if legacy_lane_artifact_detected:
        blocker_codes.add("legacy_stability_lane_artifact")

    evaluation_lane = route["evaluation_lane"]
    if evaluation_lane == "guardrail_debug":
        blocker_codes.add("guardrail_debug_non_promotable")
        promotion_eligibility = "blocked_guardrail_debug_lane"
    elif evaluation_lane == "bounded_diagnostic":
        blocker_codes.add("bounded_diagnostic_non_promotable")
        promotion_eligibility = "blocked_bounded_diagnostic_lane"
    elif blocker_codes:
        promotion_eligibility = f"blocked_{sorted(blocker_codes)[0]}"
    else:
        promotion_eligibility = "eligible"
    return {
        "promotion_authority": bool(route.get("promotion_authority", evaluation_lane == "promotion")),
        "promotion_blocker_codes": sorted(blocker_codes),
        "promotion_eligibility": promotion_eligibility,
        "forced_probe_observed": forced_probe_observed,
        "standin_observed": standin_observed,
        "legacy_lane_artifact_detected": legacy_lane_artifact_detected,
    }


def _forced_probe_observed(execution_result: dict[str, Any], fixture_plan: dict[str, Any]) -> bool:
    lane_metadata = fixture_plan.get("lane_metadata")
    if isinstance(lane_metadata, dict) and bool(lane_metadata.get("forced_probe_dependency")):
        return True
    runtime_probe = execution_result.get("runtime_probe")
    if isinstance(runtime_probe, dict):
        contamination_safe = bool(runtime_probe.get("contamination_safe"))
        if not contamination_safe:
            if int(runtime_probe.get("executed_call_count", 0) or 0) > 0:
                return True
            if int(runtime_probe.get("planned_call_count", 0) or 0) > 0:
                return True
    for event in execution_result.get("run_events", []):
        if not isinstance(event, dict):
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        details = payload.get("details")
        if isinstance(details, dict) and bool(details.get("forced_probe")):
            return True
    return False


def _standin_observed(batch: dict[str, Any], execution_result: dict[str, Any]) -> bool:
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        baseline_mode = fixed_invariants.get("baseline_mode")
        if isinstance(baseline_mode, str):
            lowered = baseline_mode.lower()
            if "shim" in lowered or "standin" in lowered:
                return True
    run_header = execution_result.get("run_header", {})
    if isinstance(run_header, dict):
        block_selection = run_header.get("block_selection")
        if isinstance(block_selection, dict):
            for block_id in block_selection.values():
                if isinstance(block_id, str):
                    lowered = block_id.lower()
                    if "shim" in lowered or "standin" in lowered:
                        return True
        routed_modules = run_header.get("routed_modules")
        if isinstance(routed_modules, list):
            for entry in routed_modules:
                if not isinstance(entry, dict):
                    continue
                module_import_path = entry.get("module_import_path")
                if isinstance(module_import_path, str):
                    lowered = module_import_path.lower()
                    if "shim" in lowered or "standin" in lowered:
                        return True
    return False


def _legacy_lane_artifact_detected(batch: dict[str, Any], route: dict[str, Any]) -> bool:
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        if fixed_invariants.get("packet") == "packet_03":
            return False
        fixed_lane = fixed_invariants.get("evaluation_lane")
        if fixed_lane in {"stability_lane", "adversarial_lane"}:
            return True
    card_lane = route.get("eval_card", {}).get("evaluation_lane")
    if card_lane in {"stability_lane", "adversarial_lane"}:
        return True
    return False


def _surface_fingerprint_maps(
    routed_modules: Any,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    claimed: dict[str, dict[str, str]] = {}
    unchanged: dict[str, dict[str, str]] = {}
    if not isinstance(routed_modules, list):
        return claimed, unchanged
    for entry in routed_modules:
        if not isinstance(entry, dict):
            continue
        surface_id = entry.get("surface_id")
        file_sha = entry.get("file_sha256")
        real_path = entry.get("real_file_path")
        if not isinstance(surface_id, str) or not isinstance(file_sha, str) or not isinstance(real_path, str):
            continue
        payload = {"file_sha256": file_sha, "real_file_path": real_path}
        if bool(entry.get("claimed_changed_surface")):
            claimed[surface_id] = payload
        else:
            unchanged[surface_id] = payload
    return claimed, unchanged


def _collect_reason_codes(score_envelope: dict[str, Any]) -> list[str]:
    reason_codes = list(score_envelope["aggregate"].get("substitution_guard_violations", []))
    for layer in score_envelope["layers"].values():
        reason_codes.extend(layer.get("reason_codes", []))
    deduped = sorted({code for code in reason_codes if isinstance(code, str) and code})
    return deduped


def _derive_failure_cluster(
    score_envelope: dict[str, Any],
    *,
    reason_codes: list[str],
    eval_id: str,
) -> str:
    verdict = score_envelope["aggregate"]["final_verdict"]
    if verdict == "pass":
        return "none"
    if eval_id in WORKSPACE_TARGET_EVAL_IDS:
        return "workspace_target_miss"
    if eval_id in {
        "ae_tool_call_shape_argument_contract",
        "ae_tool_call_contract_quality_v2",
        "ae_tool_result_normalization_permission_probe",
        "ae_tool_result_attribution_quality_v2",
    }:
        return "tool_invocation_error"
    if eval_id == "ae_sync_interrupt_cleanup_probe":
        return "recovery_loop_or_retry_spiral"
    if eval_id == "ae_completion_verifier_final_contradiction_probe":
        return "verifier_final_contradiction"
    if eval_id == "ae_completion_layer_contract_guard":
        return "completion_false_positive"
    if eval_id == "ae_verification_reason_code_quality_v2":
        return "completion_false_positive"
    if eval_id == "ae_lifecycle_adversarial_terminality_v2":
        return "process_lifecycle_and_cancellation_boundary_failure"
    if eval_id == "ae_lifecycle_terminality_contract_guard":
        return "process_lifecycle_and_cancellation_boundary_failure"
    if eval_id == "ae_cwd_workdir_path_contract_guard":
        return "cwd_path_drift"
    if "verifier_artifact_missing_cannot_be_hidden_by_l4_pass" in score_envelope["aggregate"].get(
        "substitution_guard_violations", []
    ):
        return "completion_false_positive"
    if "l2_unavailable_cannot_be_substituted_by_l3_pass" in score_envelope["aggregate"].get(
        "substitution_guard_violations", []
    ):
        return "verifier_final_contradiction"
    if any(code.startswith("workspace_target_") for code in reason_codes):
        return "workspace_target_miss"
    if any(code.startswith("tool_call_") or code.startswith("tool_result_") for code in reason_codes):
        return "tool_invocation_error"
    if any(code.startswith("sync_interrupt_") for code in reason_codes):
        return "recovery_loop_or_retry_spiral"
    if any(code.startswith("completion_layer_") for code in reason_codes):
        return "completion_false_positive"
    return "model_capability_shortfall"


def _token_and_cost_summary(execution_result: dict[str, Any]) -> dict[str, Any]:
    steps = execution_result["execution"].get("steps", [])
    total_input_messages = 0
    total_input_tokens = 0
    total_cached_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    input_cost_usd = 0.0
    cached_input_cost_usd = 0.0
    output_cost_usd = 0.0
    usd = 0.0
    pricing_models_used: set[str] = set()
    for step in steps:
        completion = step.get("completion", {})
        usage = completion.get("usage", {})
        normalized_usage = _normalize_usage_for_accounting(usage)
        if isinstance(usage.get("input_messages"), int):
            total_input_messages += usage["input_messages"]
        total_input_tokens += normalized_usage["input_tokens"]
        total_cached_input_tokens += normalized_usage["cached_input_tokens"]
        total_output_tokens += normalized_usage["output_tokens"]
        total_tokens += normalized_usage["total_tokens"]

        pricing_model_id = _resolve_pricing_model_id(completion.get("model_route"))
        if pricing_model_id:
            pricing_models_used.add(pricing_model_id)
            cost_breakdown = _compute_local_cost_usd(
                usage=normalized_usage,
                pricing_model_id=pricing_model_id,
            )
            input_cost_usd += cost_breakdown["input_cost_usd"]
            cached_input_cost_usd += cost_breakdown["cached_input_cost_usd"]
            output_cost_usd += cost_breakdown["output_cost_usd"]
            usd += cost_breakdown["total_cost_usd"]
            continue
        usage_cost = usage.get("usd") or usage.get("cost_usd")
        if isinstance(usage_cost, (int, float)):
            usd += float(usage_cost)
    if total_tokens == 0:
        total_tokens = total_input_tokens + total_output_tokens
    billable_input_tokens = max(total_input_tokens - total_cached_input_tokens, 0)
    return {
        "total_input_messages": total_input_messages,
        "input_tokens": total_input_tokens,
        "cached_input_tokens": total_cached_input_tokens,
        "billable_input_tokens": billable_input_tokens,
        "total_output_tokens": total_output_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "usd": usd,
        "usd_estimate": usd,
        "cost_breakdown_usd": {
            "input_cost": input_cost_usd,
            "cached_input_cost": cached_input_cost_usd,
            "output_cost": output_cost_usd,
            "total_cost": usd,
        },
        "pricing_model_ids": sorted(pricing_models_used),
    }


def _normalize_usage_for_accounting(usage: Any) -> dict[str, int]:
    usage_dict = usage if isinstance(usage, dict) else {}
    input_tokens = _coerce_int(usage_dict.get("input_tokens"))
    if input_tokens <= 0:
        input_tokens = _coerce_int(usage_dict.get("prompt_tokens"))
    output_tokens = _coerce_int(usage_dict.get("output_tokens"))
    if output_tokens <= 0:
        output_tokens = _coerce_int(usage_dict.get("completion_tokens"))
    total_tokens = _coerce_int(usage_dict.get("total_tokens"))
    cached_input_tokens = _coerce_int(usage_dict.get("cached_input_tokens"))
    if cached_input_tokens <= 0:
        prompt_details = usage_dict.get("prompt_tokens_details")
        prompt_details = prompt_details if isinstance(prompt_details, dict) else usage_dict.get("input_tokens_details")
        if isinstance(prompt_details, dict):
            cached_input_tokens = _coerce_int(prompt_details.get("cached_tokens"))
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": max(input_tokens, 0),
        "cached_input_tokens": max(cached_input_tokens, 0),
        "output_tokens": max(output_tokens, 0),
        "total_tokens": max(total_tokens, 0),
    }


def _resolve_pricing_model_id(model_route: Any) -> str | None:
    if not isinstance(model_route, dict):
        return None
    request_settings = model_route.get("request_settings")
    request_settings = request_settings if isinstance(request_settings, dict) else {}
    pricing_model_id = request_settings.get("pricing_model_id")
    if isinstance(pricing_model_id, str) and pricing_model_id in MODEL_PRICING_PER_MILLION_TOKENS:
        return pricing_model_id
    model_name = model_route.get("model_name")
    if isinstance(model_name, str) and model_name in MODEL_PRICING_PER_MILLION_TOKENS:
        return model_name
    return None


def _compute_local_cost_usd(*, usage: dict[str, int], pricing_model_id: str) -> dict[str, float]:
    pricing = MODEL_PRICING_PER_MILLION_TOKENS.get(pricing_model_id)
    if not isinstance(pricing, dict):
        return {
            "input_cost_usd": 0.0,
            "cached_input_cost_usd": 0.0,
            "output_cost_usd": 0.0,
            "total_cost_usd": 0.0,
        }
    input_tokens = max(usage.get("input_tokens", 0), 0)
    cached_input_tokens = max(usage.get("cached_input_tokens", 0), 0)
    output_tokens = max(usage.get("output_tokens", 0), 0)
    billable_input_tokens = max(input_tokens - cached_input_tokens, 0)

    input_cost_usd = (billable_input_tokens / 1_000_000.0) * float(pricing["input"])
    cached_input_cost_usd = (cached_input_tokens / 1_000_000.0) * float(pricing["cached_input"])
    output_cost_usd = (output_tokens / 1_000_000.0) * float(pricing["output"])
    total_cost_usd = input_cost_usd + cached_input_cost_usd + output_cost_usd

    return {
        "input_cost_usd": input_cost_usd,
        "cached_input_cost_usd": cached_input_cost_usd,
        "output_cost_usd": output_cost_usd,
        "total_cost_usd": total_cost_usd,
    }


def _count_tool_errors(events: list[dict[str, Any]]) -> int:
    count = 0
    for event in events:
        if event.get("phase") != "tool" or event.get("event_type") != "raw_bash_result":
            continue
        payload = event.get("payload")
        details = payload.get("details") if isinstance(payload, dict) else None
        if not isinstance(details, dict):
            count += 1
            continue
        result_class = details.get("result_class")
        reason_code = details.get("reason_code")
        exit_code = details.get("exit_code")
        if result_class == "success" and reason_code == "tool_success" and exit_code == 0:
            continue
        count += 1
    return count


def _count_recovery_events(events: list[dict[str, Any]]) -> int:
    return sum(1 for event in events if event.get("phase") == "recover")


def _build_recommendation_draft(
    batch: dict[str, Any],
    result_records: list[dict[str, Any]],
    *,
    budget_summary: dict[str, Any] | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    candidate_actions: list[dict[str, Any]] = []
    hard_cap_reached = bool(budget_summary and budget_summary.get("hard_cap_reached"))
    comparator_variant_id = _resolve_comparator_variant_id(batch)
    reference_batch = _is_reference_baseline_measurement_batch(batch)
    model_tier_selector = _resolve_model_tier_selector(batch)
    packet04_governed_batch = _is_packet04_governed_batch(batch)
    audit_truth = _load_execution_audit_truth(output_root=output_root) if packet04_governed_batch else {}
    sibling_records, sibling_audit_truths, authority_history_records, authority_history_audit_truths = (
        _load_sibling_authority_bundle(
        batch=batch,
        output_root=output_root,
        packet04_governed_batch=packet04_governed_batch,
        )
    )
    for variant_id in batch["variant_ids"]:
        variant_records = [record for record in result_records if record["variant_id"] == variant_id]
        gate_inputs, gate_results = _evaluate_recommendation_gates(
            batch=batch,
            result_records=result_records,
            sibling_records=sibling_records,
            variant_id=variant_id,
            comparator_variant_id=comparator_variant_id,
            model_tier_selector=model_tier_selector,
            human_gate_required=True,
            packet04_governed_batch=packet04_governed_batch,
            audit_truth=audit_truth,
            sibling_audit_truths=sibling_audit_truths,
            authority_history_records=authority_history_records,
            authority_history_audit_truths=authority_history_audit_truths,
        )
        gate_failure_summary = _gate_failure_summary(gate_results)
        is_reference_baseline_variant = bool(comparator_variant_id) and variant_id == comparator_variant_id
        if reference_batch and variant_id == BASELINE_VARIANT_ID:
            is_reference_baseline_variant = True
        if hard_cap_reached:
            proposed_status = "bound"
            rationale = (
                "Batch budget hard cap reached at $300.00. Promotion claims are blocked and remain non-promotable."
            )
        elif is_reference_baseline_variant:
            proposed_status = "bound"
            rationale = "Reference baseline comparator is measured here but cannot self-promote from Packet 03."
        elif _gate_failed(gate_results, "G12", "G13") or _gate_reason(
            gate_results, "G5"
        ) == "bounded_or_guardrail_surface_used_for_corroboration":
            proposed_status = "bound"
            rationale = (
                "Recommendation governance rejected bounded/debug-only or contaminated evidence. "
                f"Gate failures: {gate_failure_summary}"
            )
        elif _all_gates_pass(gate_results):
            proposed_status = "promote_to_atomic_eligible"
            rationale = "All recommendation governance gates passed under Packet 04A contract."
        elif _primary_delta_is_negative(gate_inputs):
            proposed_status = "retire"
            rationale = f"Comparator delta is negative on primary surface. Gate failures: {gate_failure_summary}"
        elif _screened_no_uplift_zero_delta(
            gate_inputs=gate_inputs,
            gate_results=gate_results,
            packet04_governed_batch=packet04_governed_batch,
        ):
            proposed_status = "screened_no_uplift"
            rationale = (
                "Clean Packet 04A audit passed, but the comparator delta on the primary surface remained neutral. "
                "This is an honest no-uplift negative, not a survivor or promotion candidate."
            )
        else:
            proposed_status = "hold_for_more_evidence"
            rationale = (
                "Mandatory governance evidence is incomplete or non-promotable under Packet 04A. "
                f"Gate failures: {gate_failure_summary}"
            )
        evidence_refs = [record["run_id"] for record in variant_records if isinstance(record.get("run_id"), str)]
        evidence_refs.extend(gate_inputs.get("same_batch_comparator_run_ids", []))
        candidate_actions.append(
            {
                "variant_id": variant_id,
                "proposed_status": proposed_status,
                "rationale": rationale,
                "evidence_refs": sorted(set(evidence_refs)),
                "regression_risks": ["requires_human_review"],
                "token_cost_delta": {
                    "estimated_tokens": sum(record["budget_used"]["estimated_tokens"] for record in variant_records),
                    "usd": sum(_coerce_float(record.get("budget_used", {}).get("usd")) for record in variant_records),
                },
                "complexity_delta": {
                    "code_change_required": False,
                    "failed_gate_count": sum(
                        1 for gate_id in RECOMMENDATION_GATE_IDS if not gate_results[gate_id]["passed"]
                    ),
                },
                "next_eval_or_transfer_step": _next_step_for_status(proposed_status),
                "recommendation_gate_inputs": gate_inputs,
                "recommendation_gate_results": gate_results,
            }
        )
    recommendation = {
        "batch_id": batch["batch_id"],
        "candidate_actions": candidate_actions,
        "human_gate_required": True,
        "recommendation_governance_version": RECOMMENDATION_GOVERNANCE_VERSION,
    }
    if isinstance(budget_summary, dict):
        recommendation["budget_governance"] = budget_summary
    if hard_cap_reached:
        recommendation["batch_status"] = "blocked_non_promotable"
    return recommendation


def _evaluate_recommendation_gates(
    *,
    batch: dict[str, Any],
    result_records: list[dict[str, Any]],
    sibling_records: list[dict[str, Any]],
    variant_id: str,
    comparator_variant_id: str | None,
    model_tier_selector: str,
    human_gate_required: bool,
    packet04_governed_batch: bool,
    audit_truth: dict[str, Any],
    sibling_audit_truths: list[dict[str, Any]],
    authority_history_records: list[dict[str, Any]],
    authority_history_audit_truths: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    allow_packet06_authority_fallback = _allow_packet06_authority_fallback(batch)
    variant_records = [record for record in result_records if record.get("variant_id") == variant_id]
    if _legacy_packet03_all_pass_candidate_mode(
        packet04_governed_batch=packet04_governed_batch,
        variant_id=variant_id,
        comparator_variant_id=comparator_variant_id,
        variant_records=variant_records,
    ):
        return _legacy_packet03_pass_through_gates(
            variant_id=variant_id,
            comparator_variant_id=comparator_variant_id,
            variant_records=variant_records,
        )
    primary_eval_id = _resolve_primary_eval_id(batch, variant_records)
    comparator_records = _comparator_records_for_variant(
        result_records=result_records,
        variant_id=variant_id,
        comparator_variant_id=comparator_variant_id,
    )
    sibling_variant_records = [record for record in sibling_records if record.get("variant_id") == variant_id]
    sibling_comparator_records = _comparator_records_for_variant(
        result_records=sibling_records,
        variant_id=variant_id,
        comparator_variant_id=comparator_variant_id,
    )
    if allow_packet06_authority_fallback:
        sibling_variant_records = [
            record for record in sibling_variant_records if _is_non_proxy_corroboration_record(record)
        ]
        sibling_comparator_records = [
            record for record in sibling_comparator_records if _is_non_proxy_corroboration_record(record)
        ]
    primary_candidate_records = _records_for_eval_id(variant_records, primary_eval_id)
    primary_comparator_records = _records_for_eval_id(comparator_records, primary_eval_id)
    primary_task_ids = _task_ids_for_records(primary_candidate_records, fallback_records=primary_comparator_records)
    history_variant_records = []
    history_comparator_records = []
    if allow_packet06_authority_fallback:
        history_variant_records = [
            record for record in authority_history_records if record.get("variant_id") == variant_id
        ]
        history_comparator_records = _comparator_records_for_variant(
            result_records=authority_history_records,
            variant_id=variant_id,
            comparator_variant_id=comparator_variant_id,
        )
    historical_primary_candidate_records = _records_for_eval_id_and_tasks(
        history_variant_records,
        primary_eval_id,
        primary_task_ids,
    )
    historical_primary_comparator_records = _records_for_eval_id_and_tasks(
        history_comparator_records,
        primary_eval_id,
        primary_task_ids,
    )
    same_batch_comparator_run_ids = [
        record["run_id"]
        for record in primary_comparator_records
        if isinstance(record.get("run_id"), str) and record["run_id"]
    ]

    primary_delta = _primary_delta_metric(primary_candidate_records, primary_comparator_records)
    required_reruns = _required_rerun_minimum(batch, primary_candidate_records)
    candidate_reruns = len(primary_candidate_records)
    comparator_reruns = len(primary_comparator_records)
    if allow_packet06_authority_fallback:
        candidate_reruns += len(historical_primary_candidate_records)
        comparator_reruns += len(historical_primary_comparator_records)
    corroboration_candidate_records = variant_records + sibling_variant_records
    corroboration_comparator_records = comparator_records + sibling_comparator_records
    if any(_is_non_proxy_corroboration_record(record) for record in corroboration_candidate_records):
        corroboration_candidate_records = [
            record for record in corroboration_candidate_records if _is_non_proxy_corroboration_record(record)
        ]
        corroboration_comparator_records = [
            record for record in corroboration_comparator_records if _is_non_proxy_corroboration_record(record)
        ]
    positive_delta_surface_ids, bounded_corroboration_surface_ids = _corroboration_surface_ids(
        batch=batch,
        variant_records=corroboration_candidate_records,
        comparator_records=corroboration_comparator_records,
        primary_eval_id=primary_eval_id,
    )
    lane_classes = [_record_lane_class(record) for record in variant_records]
    lane_class = _aggregate_lane_class(lane_classes)
    surface_bounded = any(_record_surface_bounded(record) for record in variant_records)
    audit_artifact_ref_aa: str | None = None
    audit_artifact_ref_ab: str | None = None
    if packet04_governed_batch:
        audit_truths = [audit_truth, *sibling_audit_truths, *authority_history_audit_truths]
        audit_status_aa = _audit_status_from_truths(
            audit_truths=audit_truths,
            variant_id=variant_id,
            key="audit_status_aa",
        )
        audit_status_ab = _audit_status_from_truths(
            audit_truths=audit_truths,
            variant_id=variant_id,
            key="audit_status_ab",
        )
        audit_artifact_ref_aa = _audit_artifact_ref_from_truths(
            audit_truths=audit_truths,
            variant_id=variant_id,
            key="audit_status_aa",
        )
        audit_artifact_ref_ab = _audit_artifact_ref_from_truths(
            audit_truths=audit_truths,
            variant_id=variant_id,
            key="audit_status_ab",
        )
        if allow_packet06_authority_fallback and audit_status_aa == "missing":
            aa_records = primary_candidate_records + historical_primary_candidate_records
            audit_status_aa = _infer_aa_status_from_records(aa_records)
            if audit_status_aa != "missing" and audit_artifact_ref_aa is None:
                audit_artifact_ref_aa = "authority_history:inferred_from_result_records"
    else:
        audit_status_aa = _aggregate_audit_status(
            records=primary_candidate_records + primary_comparator_records,
            batch=batch,
            key="audit_status_aa",
        )
        audit_status_ab = _aggregate_audit_status(
            records=primary_candidate_records + primary_comparator_records,
            batch=batch,
            key="audit_status_ab",
        )
    involved_eval_ids = {record.get("eval_id") for record in variant_records if isinstance(record.get("eval_id"), str)}
    involved_eval_ids.update(
        {
            record.get("eval_id")
            for record in sibling_variant_records
            if isinstance(record.get("eval_id"), str)
        }
    )
    involved_eval_ids.add(primary_eval_id)
    compared_records = [
        record
        for record in variant_records + comparator_records + sibling_variant_records + sibling_comparator_records
        if record.get("eval_id") in involved_eval_ids
    ]
    forced_probe_observed = any(_record_forced_probe_observed(record) for record in compared_records)
    standin_observed = any(_record_standin_observed(record) for record in compared_records)
    mechanism_visibility_complete = bool(variant_records) and all(
        _record_mechanism_visibility_complete(record) for record in variant_records
    )
    schema_complete_for_promotion = bool(variant_records) and all(
        _record_schema_complete_for_promotion(record) for record in variant_records
    )
    helper_only_evidence = any(_record_helper_only_evidence(record) for record in variant_records)
    merged_claimed_fingerprints = _merge_surface_fingerprint_maps(variant_records, "claimed_surface_fingerprints")
    merged_unchanged_fingerprints = _merge_surface_fingerprint_maps(variant_records, "unchanged_surface_fingerprints")
    first_variant_card_ref = _first_non_empty_string(variant_records, "variant_card_ref")
    first_route_manifest_ref = _first_non_empty_string(variant_records, "route_manifest_ref")
    first_route_manifest_fingerprint = _first_non_empty_string(variant_records, "route_manifest_fingerprint")
    first_governed_truth_ref = _first_non_empty_string(variant_records, "governed_truth_ref")
    if first_governed_truth_ref is None:
        first_governed_truth_ref = "missing"
    first_governed_terminal_status = _first_non_empty_string(variant_records, "governed_terminal_status")
    if first_governed_terminal_status is None:
        first_governed_terminal_status = "missing"

    g1_pass = bool(primary_delta["delta"] is not None and primary_delta["delta"] > 0 and same_batch_comparator_run_ids)
    g1_reason = "ok"
    if not g1_pass:
        if primary_delta["delta"] is None:
            g1_reason = "missing_same_batch_comparator_delta"
        elif primary_delta["delta"] < 0:
            g1_reason = "negative_same_batch_comparator_delta"
        else:
            g1_reason = "non_positive_same_batch_comparator_delta"

    g2_pass = _comparability_fingerprint_match(primary_candidate_records, primary_comparator_records)
    g2_reason = "ok" if g2_pass else "invariant_fingerprint_or_comparability_mismatch"

    g3_pass = candidate_reruns >= required_reruns and comparator_reruns >= required_reruns
    g3_reason = "ok" if g3_pass else "rerun_minimum_not_met"

    g4_pass = bool(positive_delta_surface_ids)
    g4_reason = "ok" if g4_pass else "missing_sibling_surface_corroboration_delta"

    g5_pass = g4_pass and not bounded_corroboration_surface_ids
    if g5_pass:
        g5_reason = "ok"
    elif not g4_pass:
        g5_reason = "missing_corroboration_for_non_bounded_check"
    else:
        g5_reason = "bounded_or_guardrail_surface_used_for_corroboration"

    g6_pass = bool(lane_classes) and all(value == "promotion" for value in lane_classes)
    g6_reason = "ok" if g6_pass else "lane_metadata_missing_or_non_promotable"

    g7_pass = audit_status_aa == "pass"
    g7_reason = "ok" if g7_pass else f"audit_status_aa_{audit_status_aa}"

    g8_pass = audit_status_ab == "pass"
    g8_reason = "ok" if g8_pass else f"audit_status_ab_{audit_status_ab}"

    all_primary_pass = _all_pass(primary_candidate_records) and _all_pass(primary_comparator_records)
    meaningful_primary_delta = bool(primary_delta["delta"] is not None and primary_delta["delta"] > 0)
    g9_pass = not (all_primary_pass and not meaningful_primary_delta)
    g9_reason = "ok" if g9_pass else "all_pass_no_delta"

    g10_pass = model_tier_selector == "promotion_tier"
    g10_reason = "ok" if g10_pass else f"model_tier_selector_{model_tier_selector}_not_promotion_tier"

    g11_pass = human_gate_required is True
    g11_reason = "ok" if g11_pass else "human_gate_required_false"

    g12_pass = not forced_probe_observed
    g12_reason = "ok" if g12_pass else "forced_probe_observed_true"

    g13_pass = not standin_observed
    g13_reason = "ok" if g13_pass else "standin_observed_true"

    g14_pass = bool(variant_records) and all(_record_has_provenance_chain(record) for record in variant_records)
    g14_reason = "ok" if g14_pass else "provenance_chain_incomplete"

    g15_pass = mechanism_visibility_complete and schema_complete_for_promotion and not helper_only_evidence
    if g15_pass:
        g15_reason = "ok"
    elif helper_only_evidence:
        g15_reason = "helper_only_or_proxy_surface"
    elif not mechanism_visibility_complete:
        g15_reason = "mechanism_visibility_incomplete"
    else:
        g15_reason = "schema_incomplete_for_promotion"

    gate_results = {
        "G1": {"passed": g1_pass, "reason": g1_reason},
        "G2": {"passed": g2_pass, "reason": g2_reason},
        "G3": {"passed": g3_pass, "reason": g3_reason},
        "G4": {"passed": g4_pass, "reason": g4_reason},
        "G5": {"passed": g5_pass, "reason": g5_reason},
        "G6": {"passed": g6_pass, "reason": g6_reason},
        "G7": {"passed": g7_pass, "reason": g7_reason},
        "G8": {"passed": g8_pass, "reason": g8_reason},
        "G9": {"passed": g9_pass, "reason": g9_reason},
        "G10": {"passed": g10_pass, "reason": g10_reason},
        "G11": {"passed": g11_pass, "reason": g11_reason},
        "G12": {"passed": g12_pass, "reason": g12_reason},
        "G13": {"passed": g13_pass, "reason": g13_reason},
        "G14": {"passed": g14_pass, "reason": g14_reason},
        "G15": {"passed": g15_pass, "reason": g15_reason},
    }
    gate_inputs = {
        "lane_class": lane_class,
        "surface_bounded": surface_bounded,
        "mechanism_visibility_complete": mechanism_visibility_complete,
        "schema_complete_for_promotion": schema_complete_for_promotion,
        "helper_only_evidence": helper_only_evidence,
        "comparator_variant_id": comparator_variant_id or "missing",
        "same_batch_comparator_run_ids": same_batch_comparator_run_ids,
        "primary_delta_metric": {
            "metric_name": "pass_rate_delta",
            "candidate_value": primary_delta["candidate_value"],
            "comparator_value": primary_delta["comparator_value"],
            "delta": primary_delta["delta"],
            "threshold": 0.0,
            "direction": "higher_is_better",
        },
        "corroboration_surface_ids": positive_delta_surface_ids,
        "audit_status_aa": audit_status_aa,
        "audit_status_ab": audit_status_ab,
        "audit_artifact_ref_aa": audit_artifact_ref_aa if packet04_governed_batch else None,
        "audit_artifact_ref_ab": audit_artifact_ref_ab if packet04_governed_batch else None,
        "forced_probe_observed": forced_probe_observed,
        "standin_observed": standin_observed,
        "variant_card_ref": first_variant_card_ref,
        "route_manifest_ref": first_route_manifest_ref,
        "route_manifest_fingerprint": first_route_manifest_fingerprint,
        "claimed_surface_fingerprints": merged_claimed_fingerprints,
        "unchanged_surface_fingerprints": merged_unchanged_fingerprints,
        "governed_truth_ref": first_governed_truth_ref,
        "governed_terminal_status": first_governed_terminal_status,
    }
    return gate_inputs, gate_results


def _legacy_packet03_all_pass_candidate_mode(
    *,
    packet04_governed_batch: bool,
    variant_id: str,
    comparator_variant_id: str | None,
    variant_records: list[dict[str, Any]],
) -> bool:
    if packet04_governed_batch:
        return False
    if not variant_records or not _all_pass(variant_records):
        return False
    if comparator_variant_id and variant_id == comparator_variant_id:
        return False
    return all(not isinstance(record.get("recommendation_gate_inputs"), dict) for record in variant_records)


def _legacy_packet03_pass_through_gates(
    *,
    variant_id: str,
    comparator_variant_id: str | None,
    variant_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    evidence_eval_ids = sorted(
        {
            record.get("eval_id")
            for record in variant_records
            if isinstance(record.get("eval_id"), str) and record.get("eval_id")
        }
    )
    gate_inputs = {
        "lane_class": "promotion",
        "surface_bounded": False,
        "mechanism_visibility_complete": True,
        "schema_complete_for_promotion": True,
        "helper_only_evidence": False,
        "comparator_variant_id": comparator_variant_id or "missing",
        "same_batch_comparator_run_ids": [],
        "primary_delta_metric": {
            "metric_name": "legacy_packet03_all_pass_candidate",
            "candidate_value": 1.0,
            "comparator_value": None,
            "delta": None,
            "threshold": 0.0,
            "direction": "higher_is_better",
        },
        "corroboration_surface_ids": evidence_eval_ids,
        "audit_status_aa": "pass",
        "audit_status_ab": "pass",
        "audit_artifact_ref_aa": None,
        "audit_artifact_ref_ab": None,
        "forced_probe_observed": False,
        "standin_observed": False,
        "variant_card_ref": _first_non_empty_string(variant_records, "variant_card_ref"),
        "route_manifest_ref": _first_non_empty_string(variant_records, "route_manifest_ref"),
        "route_manifest_fingerprint": _first_non_empty_string(variant_records, "route_manifest_fingerprint"),
        "claimed_surface_fingerprints": _merge_surface_fingerprint_maps(variant_records, "claimed_surface_fingerprints"),
        "unchanged_surface_fingerprints": _merge_surface_fingerprint_maps(
            variant_records, "unchanged_surface_fingerprints"
        ),
        "governed_truth_ref": _first_non_empty_string(variant_records, "governed_truth_ref") or "missing",
        "governed_terminal_status": _first_non_empty_string(variant_records, "governed_terminal_status") or "missing",
    }
    gate_results = {gate_id: {"passed": True, "reason": "ok"} for gate_id in RECOMMENDATION_GATE_IDS}
    return gate_inputs, gate_results


def _resolve_comparator_variant_id(batch: dict[str, Any]) -> str | None:
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        comparator_variant_id = fixed_invariants.get("comparator_variant_id")
        if isinstance(comparator_variant_id, str) and comparator_variant_id:
            return comparator_variant_id
    variant_ids = batch.get("variant_ids")
    if isinstance(variant_ids, list) and BASELINE_VARIANT_ID in variant_ids:
        return BASELINE_VARIANT_ID
    return None


def _resolve_recommendation_audit_status(*, batch: dict[str, Any], key: str) -> str:
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        status = fixed_invariants.get(key)
        if status in {"pass", "fail", "missing"}:
            return status
    audit_status = batch.get("audit_status")
    if isinstance(audit_status, dict):
        status = audit_status.get(key)
        if status in {"pass", "fail", "missing"}:
            return status
    return "missing"


def _audit_status_from_truth(*, audit_truth: dict[str, Any], variant_id: str, key: str) -> str:
    status_by_variant = audit_truth.get("status_by_variant")
    if isinstance(status_by_variant, dict):
        variant_status = status_by_variant.get(variant_id)
        if isinstance(variant_status, dict):
            status = variant_status.get(key)
            if status in ALLOWED_AUDIT_STATUSES:
                return status
    return "missing"


def _audit_status_from_truths(*, audit_truths: list[dict[str, Any]], variant_id: str, key: str) -> str:
    statuses = [
        _audit_status_from_truth(audit_truth=truth, variant_id=variant_id, key=key)
        for truth in audit_truths
        if isinstance(truth, dict)
    ]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "pass" for status in statuses):
        return "pass"
    return "missing"


def _audit_artifact_ref_from_truths(
    *,
    audit_truths: list[dict[str, Any]],
    variant_id: str,
    key: str,
) -> str | None:
    artifact_ref_key = "audit_artifact_ref_aa" if key == "audit_status_aa" else "audit_artifact_ref_ab"
    for truth in audit_truths:
        if not isinstance(truth, dict):
            continue
        status = _audit_status_from_truth(audit_truth=truth, variant_id=variant_id, key=key)
        artifact_ref = truth.get(artifact_ref_key)
        if status != "missing" and isinstance(artifact_ref, str) and artifact_ref:
            return artifact_ref
    for truth in audit_truths:
        if not isinstance(truth, dict):
            continue
        artifact_ref = truth.get(artifact_ref_key)
        if isinstance(artifact_ref, str) and artifact_ref:
            return artifact_ref
    return None


def _load_execution_audit_truth(*, output_root: str | Path | None) -> dict[str, Any]:
    truth: dict[str, Any] = {
        "audit_artifact_ref_aa": None,
        "audit_artifact_ref_ab": None,
        "status_by_variant": {},
    }
    if output_root is None:
        return truth
    batch_dir = Path(output_root).resolve()
    for audit_key, filename in (
        ("audit_status_aa", "aa_pair_manifest.json"),
        ("audit_status_ab", "ab_pair_delta_report.json"),
    ):
        artifact_ref_key = "audit_artifact_ref_aa" if audit_key == "audit_status_aa" else "audit_artifact_ref_ab"
        relative_ref = str(Path("audits") / filename)
        artifact_path = batch_dir / relative_ref
        if not artifact_path.exists():
            continue
        truth[artifact_ref_key] = relative_ref
        payload = _read_json_file(artifact_path)
        if not isinstance(payload, dict):
            continue
        status_by_variant = payload.get("status_by_variant")
        if not isinstance(status_by_variant, dict):
            continue
        for variant_id, status_payload in status_by_variant.items():
            if not isinstance(variant_id, str) or not isinstance(status_payload, dict):
                continue
            audit_status = status_payload.get("audit_status")
            if audit_status not in ALLOWED_AUDIT_STATUSES:
                continue
            variant_status = truth["status_by_variant"].setdefault(variant_id, {})
            variant_status[audit_key] = audit_status
    return truth


def _load_sibling_authority_bundle(
    *,
    batch: dict[str, Any],
    output_root: str | Path | None,
    packet04_governed_batch: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if output_root is None:
        return [], [], [], []
    claim_route_id = batch.get("claim_route_id")
    if not isinstance(claim_route_id, str) or not claim_route_id:
        return [], [], [], []
    current_batch_dir = Path(output_root).resolve()
    run_root = current_batch_dir.parent
    if not run_root.exists() or not run_root.is_dir():
        return [], [], [], []
    packet_stage = batch.get("packet_stage")

    sibling_records: list[dict[str, Any]] = []
    sibling_audit_truths: list[dict[str, Any]] = []
    authority_history_records: list[dict[str, Any]] = []
    authority_history_audit_truths: list[dict[str, Any]] = []

    def _batch_matches_authority(batch_payload: dict[str, Any]) -> bool:
        if batch_payload.get("claim_route_id") != claim_route_id:
            return False
        if packet_stage and batch_payload.get("packet_stage") != packet_stage:
            return False
        return True

    for sibling_dir in sorted(run_root.iterdir()):
        if sibling_dir == current_batch_dir or not sibling_dir.is_dir():
            continue
        sibling_batch = _read_json_file(sibling_dir / "batch_spec.json")
        if not isinstance(sibling_batch, dict):
            continue
        if not _batch_matches_authority(sibling_batch):
            continue
        for row in _read_jsonl_file(sibling_dir / "result_records.jsonl"):
            if isinstance(row, dict):
                sibling_records.append(row)
        if packet04_governed_batch:
            sibling_audit_truths.append(_load_execution_audit_truth(output_root=sibling_dir))

    runs_root = run_root.parent
    if runs_root.exists() and runs_root.is_dir():
        current_batch_id = current_batch_dir.name
        include_historical_siblings = not sibling_records
        for run_family_dir in sorted(runs_root.iterdir()):
            if run_family_dir == run_root or not run_family_dir.is_dir():
                continue
            if include_historical_siblings:
                for historical_sibling_dir in sorted(run_family_dir.iterdir()):
                    if not historical_sibling_dir.is_dir():
                        continue
                    if historical_sibling_dir.name == current_batch_id:
                        continue
                    sibling_batch = _read_json_file(historical_sibling_dir / "batch_spec.json")
                    if not isinstance(sibling_batch, dict):
                        continue
                    if not _batch_matches_authority(sibling_batch):
                        continue
                    for row in _read_jsonl_file(historical_sibling_dir / "result_records.jsonl"):
                        if isinstance(row, dict):
                            sibling_records.append(row)
                    if packet04_governed_batch:
                        sibling_audit_truths.append(_load_execution_audit_truth(output_root=historical_sibling_dir))
            historical_batch_dir = run_family_dir / current_batch_id
            if not historical_batch_dir.exists() or not historical_batch_dir.is_dir():
                continue
            historical_batch = _read_json_file(historical_batch_dir / "batch_spec.json")
            if not isinstance(historical_batch, dict):
                continue
            if not _batch_matches_authority(historical_batch):
                continue
            for row in _read_jsonl_file(historical_batch_dir / "result_records.jsonl"):
                if isinstance(row, dict):
                    authority_history_records.append(row)
            if packet04_governed_batch:
                authority_history_audit_truths.append(_load_execution_audit_truth(output_root=historical_batch_dir))

    return sibling_records, sibling_audit_truths, authority_history_records, authority_history_audit_truths


def _write_execution_audit_artifacts(
    *,
    batch: dict[str, Any],
    result_records: list[dict[str, Any]],
    output_root: str | Path,
) -> None:
    batch_dir = Path(output_root).resolve()
    comparator_variant_id = _resolve_comparator_variant_id(batch)
    aa_payload = _build_aa_audit_payload(
        batch=batch,
        result_records=result_records,
        output_root=batch_dir,
    )
    ab_payload = _build_ab_audit_payload(
        batch=batch,
        result_records=result_records,
        output_root=batch_dir,
        comparator_variant_id=comparator_variant_id,
    )
    _write_json(batch_dir / "audits" / "aa_pair_manifest.json", aa_payload)
    _write_json(batch_dir / "audits" / "ab_pair_delta_report.json", ab_payload)


def _build_aa_audit_payload(
    *,
    batch: dict[str, Any],
    result_records: list[dict[str, Any]],
    output_root: Path,
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in result_records:
        variant_id = record.get("variant_id")
        eval_id = record.get("eval_id")
        task_id = record.get("task_id")
        if not all(isinstance(value, str) and value for value in (variant_id, eval_id, task_id)):
            continue
        grouped.setdefault((variant_id, eval_id, task_id), []).append(record)
    for key in list(grouped):
        grouped[key] = sorted(
            grouped[key],
            key=lambda item: (
                _coerce_int(item.get("rerun_index")),
                str(item.get("run_id") or ""),
            ),
        )

    variant_ids = [
        variant_id
        for variant_id in batch.get("variant_ids", [])
        if isinstance(variant_id, str) and variant_id
    ]
    if not variant_ids:
        variant_ids = sorted(
            {
                variant_id
                for variant_id, _, _ in grouped
            }
        )

    pairs: list[dict[str, Any]] = []
    status_by_variant: dict[str, dict[str, Any]] = {}
    for variant_id in variant_ids:
        variant_pairs: list[dict[str, Any]] = []
        for (group_variant_id, _, _), group_records in grouped.items():
            if group_variant_id != variant_id or len(group_records) < 2:
                continue
            for left_record, right_record in zip(group_records, group_records[1:]):
                pair = _build_aa_pair_row(
                    left_record=left_record,
                    right_record=right_record,
                    output_root=output_root,
                )
                pairs.append(pair)
                variant_pairs.append(pair)
        status_by_variant[variant_id] = _status_for_pair_rows(
            variant_pairs,
            missing_reason="aa_pair_not_available",
        )

    return {
        "audit_type": "A/A",
        "audit_contract_version": "packet04a_execution_audit.v1",
        "batch_id": batch.get("batch_id"),
        "status_by_variant": status_by_variant,
        "pairs": pairs,
    }


def _build_ab_audit_payload(
    *,
    batch: dict[str, Any],
    result_records: list[dict[str, Any]],
    output_root: Path,
    comparator_variant_id: str | None,
) -> dict[str, Any]:
    variant_ids = [
        variant_id
        for variant_id in batch.get("variant_ids", [])
        if isinstance(variant_id, str) and variant_id
    ]
    if not variant_ids:
        variant_ids = sorted(
            {
                variant_id
                for variant_id in (record.get("variant_id") for record in result_records)
                if isinstance(variant_id, str) and variant_id
            }
        )

    baseline_index: dict[tuple[str, str, int], dict[str, Any]] = {}
    if isinstance(comparator_variant_id, str) and comparator_variant_id:
        for record in result_records:
            if record.get("variant_id") != comparator_variant_id:
                continue
            eval_id = record.get("eval_id")
            task_id = record.get("task_id")
            if not isinstance(eval_id, str) or not isinstance(task_id, str):
                continue
            rerun_index = _coerce_int(record.get("rerun_index"))
            baseline_index[(eval_id, task_id, rerun_index)] = record

    pairs: list[dict[str, Any]] = []
    status_by_variant: dict[str, dict[str, Any]] = {}
    for variant_id in variant_ids:
        if not comparator_variant_id or variant_id == comparator_variant_id:
            status_by_variant[variant_id] = _status_for_pair_rows(
                [],
                missing_reason="ab_pair_not_applicable",
            )
            continue
        candidate_records = sorted(
            [
                record for record in result_records
                if record.get("variant_id") == variant_id
            ],
            key=lambda item: (
                str(item.get("eval_id") or ""),
                str(item.get("task_id") or ""),
                _coerce_int(item.get("rerun_index")),
                str(item.get("run_id") or ""),
            ),
        )
        variant_pairs: list[dict[str, Any]] = []
        for candidate_record in candidate_records:
            eval_id = candidate_record.get("eval_id")
            task_id = candidate_record.get("task_id")
            if not isinstance(eval_id, str) or not isinstance(task_id, str):
                continue
            rerun_index = _coerce_int(candidate_record.get("rerun_index"))
            baseline_record = baseline_index.get((eval_id, task_id, rerun_index))
            pair = _build_ab_pair_row(
                baseline_record=baseline_record,
                candidate_record=candidate_record,
                output_root=output_root,
            )
            pairs.append(pair)
            variant_pairs.append(pair)
        status_by_variant[variant_id] = _status_for_pair_rows(
            variant_pairs,
            missing_reason="ab_pair_not_available",
        )

    return {
        "audit_type": "A/B",
        "audit_contract_version": "packet04a_execution_audit.v1",
        "batch_id": batch.get("batch_id"),
        "comparator_variant_id": comparator_variant_id,
        "status_by_variant": status_by_variant,
        "pairs": pairs,
    }


def _status_for_pair_rows(pair_rows: list[dict[str, Any]], *, missing_reason: str) -> dict[str, Any]:
    if not pair_rows:
        return {
            "audit_status": "missing",
            "pair_count": 0,
            "failure_reasons": [missing_reason],
        }
    failures = [
        pair for pair in pair_rows
        if pair.get("status") == "fail"
    ]
    failure_reasons = sorted(
        {
            reason
            for pair in failures
            for reason in pair.get("failure_reasons", [])
            if isinstance(reason, str)
        }
    )
    if failures:
        return {
            "audit_status": "fail",
            "pair_count": len(pair_rows),
            "failure_reasons": failure_reasons,
        }
    return {
        "audit_status": "pass",
        "pair_count": len(pair_rows),
        "failure_reasons": [],
    }


def _build_aa_pair_row(
    *,
    left_record: dict[str, Any],
    right_record: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    left_snapshot, left_errors = _snapshot_for_record(left_record, output_root=output_root)
    right_snapshot, right_errors = _snapshot_for_record(right_record, output_root=output_root)
    failure_reasons: list[str] = []
    failure_reasons.extend(f"left_{reason}" for reason in left_errors)
    failure_reasons.extend(f"right_{reason}" for reason in right_errors)

    surface_checks: list[dict[str, Any]] = []
    deterministic_check: dict[str, Any] | None = None
    route_manifest_fingerprint_equal = False
    if left_snapshot and right_snapshot:
        left_fingerprint = left_snapshot["route_manifest_fingerprint"]
        right_fingerprint = right_snapshot["route_manifest_fingerprint"]
        route_manifest_fingerprint_equal = (
            isinstance(left_fingerprint, str)
            and left_fingerprint
            and left_fingerprint == right_fingerprint
        )
        if not route_manifest_fingerprint_equal:
            failure_reasons.append("route_manifest_fingerprint_mismatch")

        left_surfaces = left_snapshot["surfaces"]
        right_surfaces = right_snapshot["surfaces"]
        left_ids = set(left_surfaces.keys())
        right_ids = set(right_surfaces.keys())
        if left_ids != right_ids:
            failure_reasons.append("surface_id_set_mismatch")
        for surface_id in sorted(left_ids | right_ids):
            left_surface = left_surfaces.get(surface_id)
            right_surface = right_surfaces.get(surface_id)
            if not isinstance(left_surface, dict) or not isinstance(right_surface, dict):
                surface_checks.append(
                    {
                        "surface_id": surface_id,
                        "status": "missing",
                    }
                )
                continue
            path_equal = left_surface.get("real_file_path") == right_surface.get("real_file_path")
            hash_equal = left_surface.get("file_sha256") == right_surface.get("file_sha256")
            if not path_equal or not hash_equal:
                failure_reasons.append(f"surface_mismatch:{surface_id}")
            surface_checks.append(
                {
                    "surface_id": surface_id,
                    "real_file_path_equal": path_equal,
                    "file_sha256_equal": hash_equal,
                }
            )

        deterministic_mode = (
            left_snapshot.get("execution_mode") == "deterministic_no_model"
            and right_snapshot.get("execution_mode") == "deterministic_no_model"
        )
        if deterministic_mode:
            verdict_equal = left_snapshot.get("final_verdict") == right_snapshot.get("final_verdict")
            reason_codes_equal = left_snapshot.get("reason_codes") == right_snapshot.get("reason_codes")
            deterministic_check = {
                "enabled": True,
                "final_verdict_equal": verdict_equal,
                "reason_codes_equal": reason_codes_equal,
            }
            if not verdict_equal:
                failure_reasons.append("deterministic_verdict_mismatch")
            if not reason_codes_equal:
                failure_reasons.append("deterministic_reason_codes_mismatch")

    return {
        "status": "pass" if not failure_reasons else "fail",
        "variant_id": left_record.get("variant_id"),
        "eval_id": left_record.get("eval_id"),
        "task_id": left_record.get("task_id"),
        "left_run_id": left_record.get("run_id"),
        "right_run_id": right_record.get("run_id"),
        "left_route_manifest_fingerprint": (
            left_snapshot.get("route_manifest_fingerprint") if left_snapshot else None
        ),
        "right_route_manifest_fingerprint": (
            right_snapshot.get("route_manifest_fingerprint") if right_snapshot else None
        ),
        "route_manifest_fingerprint_equal": route_manifest_fingerprint_equal,
        "surface_checks": surface_checks,
        "deterministic_check": deterministic_check,
        "failure_reasons": sorted(set(failure_reasons)),
    }


def _build_ab_pair_row(
    *,
    baseline_record: dict[str, Any] | None,
    candidate_record: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    failure_reasons: list[str] = []
    if baseline_record is None:
        return {
            "status": "fail",
            "baseline_run_id": None,
            "candidate_run_id": candidate_record.get("run_id"),
            "candidate_variant_id": candidate_record.get("variant_id"),
            "failure_reasons": ["baseline_pair_missing"],
            "delta_classification": "metadata_only_delta",
            "claimed_surface_checks": [],
            "unchanged_surface_checks": [],
        }

    baseline_snapshot, baseline_errors = _snapshot_for_record(baseline_record, output_root=output_root)
    candidate_snapshot, candidate_errors = _snapshot_for_record(candidate_record, output_root=output_root)
    failure_reasons.extend(f"baseline_{reason}" for reason in baseline_errors)
    failure_reasons.extend(f"candidate_{reason}" for reason in candidate_errors)

    claimed_surface_checks: list[dict[str, Any]] = []
    unchanged_surface_checks: list[dict[str, Any]] = []
    implementation_delta_buckets: list[str] = []
    implementation_delta_count = 0
    if baseline_snapshot and candidate_snapshot:
        baseline_surfaces = baseline_snapshot["surfaces"]
        candidate_surfaces = candidate_snapshot["surfaces"]
        claimed_surface_ids = sorted(
            surface_id
            for surface_id, surface_payload in candidate_surfaces.items()
            if surface_payload.get("claimed_changed_surface")
        )
        unchanged_surface_ids = sorted(
            surface_id
            for surface_id, surface_payload in candidate_surfaces.items()
            if not surface_payload.get("claimed_changed_surface")
        )
        if not claimed_surface_ids:
            failure_reasons.append("claimed_surface_set_missing")

        for surface_id in claimed_surface_ids:
            baseline_surface = baseline_surfaces.get(surface_id)
            candidate_surface = candidate_surfaces.get(surface_id)
            if not isinstance(baseline_surface, dict) or not isinstance(candidate_surface, dict):
                failure_reasons.append(f"claimed_surface_missing:{surface_id}")
                claimed_surface_checks.append({"surface_id": surface_id, "status": "missing"})
                continue
            path_diff = baseline_surface.get("real_file_path") != candidate_surface.get("real_file_path")
            hash_diff = baseline_surface.get("file_sha256") != candidate_surface.get("file_sha256")
            delta_detected = path_diff or hash_diff
            if not delta_detected:
                failure_reasons.append(f"claimed_surface_no_routed_delta:{surface_id}")
            else:
                implementation_delta_count += 1
                bucket = candidate_surface.get("ownership_bucket")
                if isinstance(bucket, str) and bucket:
                    implementation_delta_buckets.append(bucket)
            claimed_surface_checks.append(
                {
                    "surface_id": surface_id,
                    "path_diff": path_diff,
                    "hash_diff": hash_diff,
                    "delta_detected": delta_detected,
                }
            )

        for surface_id in unchanged_surface_ids:
            baseline_surface = baseline_surfaces.get(surface_id)
            candidate_surface = candidate_surfaces.get(surface_id)
            if not isinstance(baseline_surface, dict) or not isinstance(candidate_surface, dict):
                failure_reasons.append(f"unchanged_surface_missing:{surface_id}")
                unchanged_surface_checks.append({"surface_id": surface_id, "status": "missing"})
                continue
            path_equal = baseline_surface.get("real_file_path") == candidate_surface.get("real_file_path")
            hash_equal = baseline_surface.get("file_sha256") == candidate_surface.get("file_sha256")
            if not path_equal or not hash_equal:
                failure_reasons.append(f"unchanged_surface_diverged:{surface_id}")
            unchanged_surface_checks.append(
                {
                    "surface_id": surface_id,
                    "path_equal": path_equal,
                    "hash_equal": hash_equal,
                }
            )

        if implementation_delta_count <= 0:
            failure_reasons.append("implementation_routed_delta_missing")
        elif implementation_delta_buckets and all(bucket == "support_infra" for bucket in implementation_delta_buckets):
            failure_reasons.append("support_infra_only_delta")

    delta_classification = "implementation_routed_delta" if implementation_delta_count > 0 else "metadata_only_delta"
    return {
        "status": "pass" if not failure_reasons else "fail",
        "baseline_run_id": baseline_record.get("run_id"),
        "candidate_run_id": candidate_record.get("run_id"),
        "candidate_variant_id": candidate_record.get("variant_id"),
        "eval_id": candidate_record.get("eval_id"),
        "task_id": candidate_record.get("task_id"),
        "delta_classification": delta_classification,
        "claimed_surface_checks": claimed_surface_checks,
        "unchanged_surface_checks": unchanged_surface_checks,
        "failure_reasons": sorted(set(failure_reasons)),
    }


def _snapshot_for_record(
    record: dict[str, Any],
    *,
    output_root: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    run_artifact_refs = record.get("run_artifact_refs")
    if not isinstance(run_artifact_refs, dict):
        return None, ["run_artifact_refs_missing"]
    run_header_ref = run_artifact_refs.get("run_header_ref")
    if not isinstance(run_header_ref, str) or not run_header_ref:
        return None, ["run_header_ref_missing"]
    route_manifest_ref = run_artifact_refs.get("route_manifest_ref")
    if not isinstance(route_manifest_ref, str) or not route_manifest_ref:
        route_manifest_ref = record.get("route_manifest_ref")
    if not isinstance(route_manifest_ref, str) or not route_manifest_ref:
        return None, ["route_manifest_ref_missing"]

    run_header_payload = _read_json_file(_resolve_ref_path(ref=run_header_ref, output_root=output_root))
    route_manifest_payload = _read_json_file(_resolve_ref_path(ref=route_manifest_ref, output_root=output_root))
    errors: list[str] = []
    if not isinstance(run_header_payload, dict):
        errors.append("run_header_artifact_missing_or_invalid")
    if not isinstance(route_manifest_payload, dict):
        errors.append("route_manifest_artifact_missing_or_invalid")
    if errors:
        return None, errors

    routed_modules = run_header_payload.get("routed_modules")
    if not isinstance(routed_modules, list) or not routed_modules:
        return None, ["routed_modules_missing_or_empty"]
    surfaces: dict[str, dict[str, Any]] = {}
    for entry in routed_modules:
        if not isinstance(entry, dict):
            continue
        surface_id = entry.get("surface_id")
        real_file_path = entry.get("real_file_path")
        file_sha256 = entry.get("file_sha256")
        if not isinstance(surface_id, str) or not isinstance(real_file_path, str) or not isinstance(file_sha256, str):
            continue
        surfaces[surface_id] = {
            "real_file_path": real_file_path,
            "file_sha256": file_sha256,
            "claimed_changed_surface": bool(entry.get("claimed_changed_surface")),
            "ownership_bucket": entry.get("ownership_bucket"),
        }
    if not surfaces:
        return None, ["routed_modules_incomplete"]

    run_header_fingerprint = run_header_payload.get("route_manifest_fingerprint")
    route_manifest_fingerprint = route_manifest_payload.get("route_manifest_fingerprint")
    resolved_fingerprint: str | None = None
    if isinstance(run_header_fingerprint, str) and run_header_fingerprint:
        resolved_fingerprint = run_header_fingerprint
    if isinstance(route_manifest_fingerprint, str) and route_manifest_fingerprint:
        if resolved_fingerprint is None:
            resolved_fingerprint = route_manifest_fingerprint
        elif route_manifest_fingerprint != resolved_fingerprint:
            return None, ["route_manifest_fingerprint_mismatch_between_artifacts"]
    if not isinstance(resolved_fingerprint, str) or not resolved_fingerprint:
        return None, ["route_manifest_fingerprint_missing"]

    reason_codes = record.get("reason_codes")
    normalized_reason_codes: list[str] = []
    if isinstance(reason_codes, list):
        normalized_reason_codes = sorted(code for code in reason_codes if isinstance(code, str))
    return {
        "run_id": record.get("run_id"),
        "execution_mode": record.get("execution_mode"),
        "final_verdict": record.get("score_summary", {}).get("final_verdict"),
        "reason_codes": normalized_reason_codes,
        "route_manifest_fingerprint": resolved_fingerprint,
        "surfaces": surfaces,
    }, []


def _resolve_ref_path(*, ref: str, output_root: Path) -> Path:
    path = Path(ref)
    if path.is_absolute():
        return path
    return output_root / path


def _resolve_primary_eval_id(batch: dict[str, Any], records: list[dict[str, Any]]) -> str:
    eval_ids = batch.get("eval_ids")
    if isinstance(eval_ids, list) and eval_ids:
        first_eval_id = eval_ids[0]
        if isinstance(first_eval_id, str) and first_eval_id:
            return first_eval_id
    for record in records:
        eval_id = record.get("eval_id")
        if isinstance(eval_id, str) and eval_id:
            return eval_id
    return ""


def _comparator_records_for_variant(
    *,
    result_records: list[dict[str, Any]],
    variant_id: str,
    comparator_variant_id: str | None,
) -> list[dict[str, Any]]:
    if not comparator_variant_id:
        return []
    if variant_id == comparator_variant_id:
        return []
    return [
        record
        for record in result_records
        if record.get("variant_id") == comparator_variant_id
    ]


def _records_for_eval_id(records: list[dict[str, Any]], eval_id: str) -> list[dict[str, Any]]:
    if not eval_id:
        return []
    return [record for record in records if record.get("eval_id") == eval_id]


def _records_for_eval_id_and_tasks(
    records: list[dict[str, Any]],
    eval_id: str,
    task_ids: set[str],
) -> list[dict[str, Any]]:
    if not eval_id:
        return []
    if not task_ids:
        return _records_for_eval_id(records, eval_id)
    return [
        record
        for record in records
        if record.get("eval_id") == eval_id and record.get("task_id") in task_ids
    ]


def _task_ids_for_records(records: list[dict[str, Any]], *, fallback_records: list[dict[str, Any]]) -> set[str]:
    task_ids = {
        task_id
        for task_id in (record.get("task_id") for record in records)
        if isinstance(task_id, str) and task_id
    }
    if task_ids:
        return task_ids
    return {
        task_id
        for task_id in (record.get("task_id") for record in fallback_records)
        if isinstance(task_id, str) and task_id
    }


def _infer_aa_status_from_records(records: list[dict[str, Any]]) -> str:
    admissible_records = [record for record in records if _record_is_admissible_for_aa_inference(record)]
    if len(admissible_records) < 2:
        return "missing"
    ordered = sorted(
        admissible_records,
        key=lambda item: (
            _coerce_int(item.get("rerun_index")),
            str(item.get("run_id") or ""),
        ),
    )
    execution_modes = {record.get("execution_mode") for record in ordered}
    deterministic_mode = execution_modes == {"deterministic_no_model"}
    for left_record, right_record in zip(ordered, ordered[1:]):
        left_fingerprint = left_record.get("route_manifest_fingerprint")
        right_fingerprint = right_record.get("route_manifest_fingerprint")
        if not isinstance(left_fingerprint, str) or not left_fingerprint:
            return "fail"
        if not isinstance(right_fingerprint, str) or not right_fingerprint:
            return "fail"
        if left_fingerprint != right_fingerprint:
            return "fail"
        if deterministic_mode:
            left_verdict = left_record.get("score_summary", {}).get("final_verdict")
            right_verdict = right_record.get("score_summary", {}).get("final_verdict")
            if left_verdict != right_verdict:
                return "fail"
            left_reason_codes = sorted(
                code for code in left_record.get("reason_codes", []) if isinstance(code, str)
            )
            right_reason_codes = sorted(
                code for code in right_record.get("reason_codes", []) if isinstance(code, str)
            )
            if left_reason_codes != right_reason_codes:
                return "fail"
    return "pass"


def _record_is_admissible_for_aa_inference(record: dict[str, Any]) -> bool:
    final_verdict = record.get("score_summary", {}).get("final_verdict")
    return final_verdict == "pass"


def _primary_delta_metric(
    candidate_records: list[dict[str, Any]],
    comparator_records: list[dict[str, Any]],
) -> dict[str, float | None]:
    candidate_value = _pass_rate(candidate_records)
    comparator_value = _pass_rate(comparator_records)
    delta = None
    if candidate_value is not None and comparator_value is not None:
        delta = candidate_value - comparator_value
    return {
        "candidate_value": candidate_value,
        "comparator_value": comparator_value,
        "delta": delta,
    }


def _pass_rate(records: list[dict[str, Any]]) -> float | None:
    if not records:
        return None
    pass_count = sum(
        1
        for record in records
        if record.get("score_summary", {}).get("final_verdict") == "pass"
    )
    return pass_count / float(len(records))


def _required_rerun_minimum(batch: dict[str, Any], candidate_records: list[dict[str, Any]]) -> int:
    execution_mode = ""
    if candidate_records:
        execution_mode_value = candidate_records[0].get("execution_mode")
        if isinstance(execution_mode_value, str):
            execution_mode = execution_mode_value
    required = 2 if execution_mode == "deterministic_no_model" else 3
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        if any(
            bool(fixed_invariants.get(flag))
            for flag in ("mixed_stability_window", "high_value_promotion_surface", "l3_judge_sensitive")
        ):
            required = 5
        override_value = fixed_invariants.get("rerun_minimum_override")
        if isinstance(override_value, int) and override_value > required:
            required = override_value
    override_value = batch.get("rerun_minimum_override")
    if isinstance(override_value, int) and override_value > required:
        required = override_value
    return required


def _corroboration_surface_ids(
    *,
    batch: dict[str, Any],
    variant_records: list[dict[str, Any]],
    comparator_records: list[dict[str, Any]],
    primary_eval_id: str,
) -> tuple[list[str], list[str]]:
    eval_ids: list[str] = []
    for eval_id in batch.get("eval_ids", []):
        if isinstance(eval_id, str) and eval_id and eval_id != primary_eval_id:
            eval_ids.append(eval_id)
    if not eval_ids:
        seen: set[str] = set()
        for record in variant_records:
            eval_id = record.get("eval_id")
            if isinstance(eval_id, str) and eval_id and eval_id != primary_eval_id and eval_id not in seen:
                seen.add(eval_id)
                eval_ids.append(eval_id)

    positive_delta_surface_ids: list[str] = []
    bounded_surface_ids: list[str] = []
    for eval_id in eval_ids:
        candidate_surface_records = _records_for_eval_id(variant_records, eval_id)
        comparator_surface_records = _records_for_eval_id(comparator_records, eval_id)
        surface_delta = _primary_delta_metric(candidate_surface_records, comparator_surface_records)
        if surface_delta["delta"] is None or surface_delta["delta"] <= 0:
            continue
        positive_delta_surface_ids.append(eval_id)
        surface_bounded = any(_record_surface_bounded(record) for record in candidate_surface_records)
        lane_ok = candidate_surface_records and all(_record_lane_class(record) == "promotion" for record in candidate_surface_records)
        if surface_bounded or not lane_ok:
            bounded_surface_ids.append(eval_id)
    return positive_delta_surface_ids, bounded_surface_ids


def _record_gate_inputs(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("recommendation_gate_inputs")
    if isinstance(value, dict):
        return value
    return {}


def _record_lane_class(record: dict[str, Any]) -> str:
    gate_inputs = _record_gate_inputs(record)
    lane_class = gate_inputs.get("lane_class")
    try:
        return normalize_recommendation_lane_class(lane_class)
    except SchemaValidationError:
        return "missing"


def _aggregate_lane_class(lane_classes: list[str]) -> str:
    normalized = [value for value in lane_classes if value]
    if not normalized:
        return "missing"
    unique = set(normalized)
    if len(unique) == 1:
        return normalized[0]
    return "mixed"


def _surface_is_bounded(*, lane_class: str, blocker_codes: list[str]) -> bool:
    normalized_lane = lane_class
    try:
        normalized_lane = normalize_recommendation_lane_class(lane_class)
    except SchemaValidationError:
        normalized_lane = lane_class
    if normalized_lane in {"guardrail_debug", "bounded_diagnostic"}:
        return True
    bounded_markers = (
        "bounded_l3_dependency",
        "lane_policy_restriction",
        "legacy_stability_lane_artifact",
        "guardrail_debug_non_promotable",
    )
    for code in blocker_codes:
        if isinstance(code, str) and any(marker in code for marker in bounded_markers):
            return True
    return False


def _record_surface_bounded(record: dict[str, Any]) -> bool:
    gate_inputs = _record_gate_inputs(record)
    surface_bounded = gate_inputs.get("surface_bounded")
    if isinstance(surface_bounded, bool):
        return surface_bounded
    lane_class = _record_lane_class(record)
    blocker_codes = record.get("promotion_blocker_codes")
    if not isinstance(blocker_codes, list):
        blocker_codes = []
    return _surface_is_bounded(lane_class=lane_class, blocker_codes=blocker_codes)


def _record_mechanism_visibility_complete(record: dict[str, Any]) -> bool:
    gate_inputs = _record_gate_inputs(record)
    return bool(gate_inputs.get("mechanism_visibility_complete"))


def _record_schema_complete_for_promotion(record: dict[str, Any]) -> bool:
    gate_inputs = _record_gate_inputs(record)
    return bool(gate_inputs.get("schema_complete_for_promotion"))


def _record_helper_only_evidence(record: dict[str, Any]) -> bool:
    gate_inputs = _record_gate_inputs(record)
    return bool(gate_inputs.get("helper_only_evidence"))


def _is_non_proxy_corroboration_record(record: dict[str, Any]) -> bool:
    task_intent = record.get("task_intent")
    return isinstance(task_intent, str) and "non_proxy_corroboration" in task_intent


def _aggregate_audit_status(
    *,
    records: list[dict[str, Any]],
    batch: dict[str, Any],
    key: str,
) -> str:
    statuses: list[str] = []
    for record in records:
        gate_inputs = _record_gate_inputs(record)
        status = gate_inputs.get(key)
        if status in {"pass", "fail", "missing"}:
            statuses.append(status)
    if not statuses:
        statuses.append(_resolve_recommendation_audit_status(batch=batch, key=key))
    if any(status == "fail" for status in statuses):
        return "fail"
    if all(status == "pass" for status in statuses):
        return "pass"
    return "missing"


def _record_forced_probe_observed(record: dict[str, Any]) -> bool:
    gate_inputs = _record_gate_inputs(record)
    value = gate_inputs.get("forced_probe_observed")
    if isinstance(value, bool):
        return value
    return bool(record.get("forced_probe_observed"))


def _record_standin_observed(record: dict[str, Any]) -> bool:
    gate_inputs = _record_gate_inputs(record)
    value = gate_inputs.get("standin_observed")
    if isinstance(value, bool):
        return value
    return bool(record.get("standin_observed"))


def _record_has_provenance_chain(record: dict[str, Any]) -> bool:
    gate_inputs = _record_gate_inputs(record)
    variant_card_ref = gate_inputs.get("variant_card_ref", record.get("variant_card_ref"))
    route_manifest_ref = gate_inputs.get("route_manifest_ref", record.get("route_manifest_ref"))
    route_manifest_fingerprint = gate_inputs.get(
        "route_manifest_fingerprint",
        record.get("route_manifest_fingerprint"),
    )
    claimed = gate_inputs.get("claimed_surface_fingerprints", record.get("claimed_surface_fingerprints"))
    unchanged = gate_inputs.get("unchanged_surface_fingerprints", record.get("unchanged_surface_fingerprints"))
    if not isinstance(variant_card_ref, str) or not variant_card_ref:
        return False
    if not isinstance(route_manifest_ref, str) or not route_manifest_ref:
        return False
    if not isinstance(route_manifest_fingerprint, str) or not route_manifest_fingerprint:
        return False
    if not isinstance(claimed, dict) or not isinstance(unchanged, dict):
        return False
    return bool(claimed or unchanged)


def _merge_surface_fingerprint_maps(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for record in records:
        raw_map = record.get(field)
        if not isinstance(raw_map, dict):
            continue
        for surface_id, payload in raw_map.items():
            if isinstance(surface_id, str):
                merged[surface_id] = payload
    return merged


def _first_non_empty_string(records: list[dict[str, Any]], key: str) -> str | None:
    for record in records:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
        gate_inputs = _record_gate_inputs(record)
        value = gate_inputs.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _comparability_fingerprint_match(
    candidate_records: list[dict[str, Any]],
    comparator_records: list[dict[str, Any]],
) -> bool:
    candidate_signatures = {
        signature
        for signature in (_comparability_signature(record) for record in candidate_records)
        if signature is not None
    }
    comparator_signatures = {
        signature
        for signature in (_comparability_signature(record) for record in comparator_records)
        if signature is not None
    }
    if not candidate_signatures or not comparator_signatures:
        return False
    return candidate_signatures == comparator_signatures


def _comparability_signature(record: dict[str, Any]) -> tuple[str, str, str, str] | None:
    effective_settings_id = record.get("effective_settings_id")
    invariant_fingerprint = record.get("invariant_fingerprint")
    grader_version = _normalized_grader_version_for_comparability(record.get("grader_version"))
    execution_mode = record.get("execution_mode")
    values = (
        effective_settings_id,
        invariant_fingerprint,
        grader_version,
        execution_mode,
    )
    if not all(isinstance(value, str) and value for value in values):
        return None
    return (
        str(effective_settings_id),
        str(invariant_fingerprint),
        str(grader_version),
        str(execution_mode),
    )


def _normalized_grader_version_for_comparability(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    removable_tags = {
        "packet05a_mechanism_visible_v1",
        "packet05a_proxy_or_incomplete_v1",
    }
    parts = [part for part in value.split("+") if part and part not in removable_tags]
    if not parts:
        return None
    return "+".join(parts)


def _all_pass(records: list[dict[str, Any]]) -> bool:
    return bool(records) and all(
        record.get("score_summary", {}).get("final_verdict") == "pass"
        for record in records
    )


def _all_gates_pass(gate_results: dict[str, dict[str, Any]]) -> bool:
    return all(
        bool(gate_results.get(gate_id, {}).get("passed"))
        for gate_id in RECOMMENDATION_GATE_IDS
    )


def _gate_failed(gate_results: dict[str, dict[str, Any]], *gate_ids: str) -> bool:
    return any(not bool(gate_results.get(gate_id, {}).get("passed")) for gate_id in gate_ids)


def _gate_reason(gate_results: dict[str, dict[str, Any]], gate_id: str) -> str:
    reason = gate_results.get(gate_id, {}).get("reason")
    if isinstance(reason, str):
        return reason
    return ""


def _gate_failure_summary(gate_results: dict[str, dict[str, Any]]) -> str:
    failures = []
    for gate_id in RECOMMENDATION_GATE_IDS:
        gate_result = gate_results.get(gate_id, {})
        if gate_result.get("passed"):
            continue
        reason = gate_result.get("reason")
        failures.append(f"{gate_id}:{reason}")
    if not failures:
        return "none"
    return ", ".join(failures)


def _primary_delta_is_negative(gate_inputs: dict[str, Any]) -> bool:
    primary_delta_metric = gate_inputs.get("primary_delta_metric")
    if not isinstance(primary_delta_metric, dict):
        return False
    delta = primary_delta_metric.get("delta")
    return isinstance(delta, (int, float)) and float(delta) < 0


def _screened_no_uplift_zero_delta(
    *,
    gate_inputs: dict[str, Any],
    gate_results: dict[str, dict[str, Any]],
    packet04_governed_batch: bool,
) -> bool:
    if not packet04_governed_batch:
        return False
    primary_delta_metric = gate_inputs.get("primary_delta_metric")
    if not isinstance(primary_delta_metric, dict):
        return False
    delta = primary_delta_metric.get("delta")
    if not isinstance(delta, (int, float)) or float(delta) != 0.0:
        return False
    if gate_inputs.get("lane_class") != "promotion":
        return False
    if gate_inputs.get("surface_bounded") is True:
        return False
    required_pass_ids = ("G2", "G3", "G6", "G7", "G8", "G11", "G12", "G13", "G14", "G15")
    if any(not gate_results.get(gate_id, {}).get("passed") for gate_id in required_pass_ids):
        return False
    if _gate_reason(gate_results, "G1") != "non_positive_same_batch_comparator_delta":
        return False
    if _gate_reason(gate_results, "G4") != "missing_sibling_surface_corroboration_delta":
        return False
    if _gate_reason(gate_results, "G5") != "missing_corroboration_for_non_bounded_check":
        return False
    if _gate_reason(gate_results, "G9") != "all_pass_no_delta":
        return False
    return True


def _next_step_for_status(proposed_status: str) -> str:
    if proposed_status == "promote_to_atomic_eligible":
        return "human_review_required_before_manual_status_change"
    if proposed_status == "retire":
        return "human_review_retire_candidate_if_confirmed"
    if proposed_status == "bound":
        return "route_to_guardrail_debug_or_bound_lane_review"
    if proposed_status == "screened_no_uplift":
        return "close_as_screened_no_uplift_and_do_not_rerun_same_surface"
    return "collect_missing_governance_evidence_and_rerun"


def _resolve_model_tier_selector(batch: dict[str, Any]) -> str:
    selector_candidates = [
        batch.get("model_tier_selector"),
    ]
    fixed_invariants = batch.get("fixed_invariants")
    if isinstance(fixed_invariants, dict):
        selector_candidates.append(fixed_invariants.get("model_tier_selector"))
    for selector in selector_candidates:
        if selector is None:
            continue
        if not isinstance(selector, str):
            raise SchemaValidationError("batch_spec.model_tier_selector must be a string when provided")
        if selector not in MODEL_POLICY_TIERS:
            raise SchemaValidationError(
                f"batch_spec.model_tier_selector must be one of {sorted(MODEL_POLICY_TIERS)}"
            )
        return selector
    if _allow_packet06_authority_fallback(batch):
        return "promotion_tier"
    return "screening_default"


def _init_budget_tracker(*, planned_run_count: int) -> dict[str, Any]:
    return {
        "planned_run_count": planned_run_count,
        "executed_run_count": 0,
        "warning_thresholds_usd": list(GOVERNED_EVAL_BUDGET_WARNING_THRESHOLDS_USD),
        "hard_cap_usd": GOVERNED_EVAL_BUDGET_HARD_CAP_USD,
        "cumulative_usd": 0.0,
        "warnings": [],
        "hard_cap_reached": False,
        "hard_cap_trigger_run_id": None,
    }


def _accumulate_budget_progress(
    *,
    budget_tracker: dict[str, Any],
    run_id: str,
    result_record: dict[str, Any],
) -> dict[str, Any]:
    previous_total = _coerce_float(budget_tracker.get("cumulative_usd"))
    run_usd = _coerce_float(result_record.get("budget_used", {}).get("usd"))
    cumulative_total = previous_total + run_usd
    budget_tracker["cumulative_usd"] = cumulative_total
    budget_tracker["executed_run_count"] = int(budget_tracker.get("executed_run_count", 0)) + 1

    warning_thresholds = budget_tracker.get("warning_thresholds_usd", [])
    warning_events: list[dict[str, Any]] = []
    if isinstance(warning_thresholds, list):
        for threshold in warning_thresholds:
            if not isinstance(threshold, (int, float)):
                continue
            threshold_value = float(threshold)
            if previous_total < threshold_value <= cumulative_total:
                event = {
                    "threshold_usd": threshold_value,
                    "cumulative_usd": cumulative_total,
                    "run_id": run_id,
                }
                warning_events.append(event)
                warnings = budget_tracker.get("warnings")
                if isinstance(warnings, list):
                    warnings.append(event)

    hard_cap_value = _coerce_float(budget_tracker.get("hard_cap_usd"))
    hard_cap_triggered = False
    if not budget_tracker.get("hard_cap_reached") and cumulative_total >= hard_cap_value:
        budget_tracker["hard_cap_reached"] = True
        budget_tracker["hard_cap_trigger_run_id"] = run_id
        hard_cap_triggered = True

    return {
        "warning_events": warning_events,
        "hard_cap_triggered": hard_cap_triggered,
        "cumulative_usd": cumulative_total,
    }


def _budget_summary_from_tracker(budget_tracker: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "policy": {
            "warning_thresholds_usd": list(budget_tracker.get("warning_thresholds_usd", [])),
            "hard_cap_usd": _coerce_float(budget_tracker.get("hard_cap_usd")),
        },
        "planned_run_count": int(budget_tracker.get("planned_run_count", 0)),
        "executed_run_count": int(budget_tracker.get("executed_run_count", 0)),
        "total_usd": _coerce_float(budget_tracker.get("cumulative_usd")),
        "warnings": list(budget_tracker.get("warnings", [])),
        "hard_cap_reached": bool(budget_tracker.get("hard_cap_reached")),
    }
    if summary["hard_cap_reached"]:
        summary["status"] = "blocked_non_promotable"
        summary["hard_cap_trigger_run_id"] = budget_tracker.get("hard_cap_trigger_run_id")
    else:
        summary["status"] = "within_budget"
    return summary


def _is_reference_baseline_measurement_batch(batch: dict[str, Any]) -> bool:
    fixed_invariants = batch.get("fixed_invariants", {})
    comparator_variant_id = (
        fixed_invariants.get("comparator_variant_id")
        if isinstance(fixed_invariants, dict)
        else None
    )
    if isinstance(comparator_variant_id, str):
        lowered = comparator_variant_id.lower()
        if "reference_baseline" in lowered:
            return True
    for field in ("batch_id", "eval_family", "task_set_id"):
        value = batch.get(field)
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if "reference" in lowered and ("baseline" in lowered or "packet_02" in lowered):
            return True
    return False


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _coerce_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _read_jsonl_file(path: Path) -> list[Any]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[Any] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
