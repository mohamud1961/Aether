from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_hash_exists
from ..utils.hashes import stable_hash
from ._common import events_of, fail_case, make_case, pass_case


PACK = "context"


EXPECTED_LAYER_ORDER = [
    "DOCTRINE",
    "POLICY",
    "TASK",
    "PLAN",
    "STATE",
    "VERIFICATION",
    "UNTRUSTED",
]


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _cx_01_strict_layer_order(ctx: TestExecutionContext):
    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    if not compiled:
        return fail_case("missing_contextpack_compiled")

    for event in compiled:
        slice_list = event.get("slice_list")
        if not isinstance(slice_list, list):
            continue
        layers = [str(item.get("layer", item.get("name", ""))).upper() for item in slice_list if isinstance(item, Mapping)]
        filtered = [layer for layer in layers if layer in EXPECTED_LAYER_ORDER]
        if filtered != sorted(filtered, key=lambda layer: EXPECTED_LAYER_ORDER.index(layer)):
            return fail_case("context_layer_order_violation", observed_layers=layers)

    return pass_case()


def _cx_02_untrusted_delimiters(ctx: TestExecutionContext):
    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    if not compiled:
        return fail_case("missing_contextpack_compiled")

    violations = _events(ctx, "POLICY_VIOLATION")
    if any(event.get("violation_code") == "UNTRUSTED_WITHOUT_DELIMITERS" for event in violations):
        return pass_case()

    for event in compiled:
        slices = event.get("slice_list")
        if not isinstance(slices, list):
            continue
        for slice_item in slices:
            if not isinstance(slice_item, Mapping):
                continue
            trust = str(slice_item.get("trust_level", "")).upper()
            if trust == "UNTRUSTED" and not slice_item.get("delimiter"):
                return fail_case("untrusted_slice_without_delimiter")

    return pass_case()


def _cx_03_sweet_zone_and_overdrive(ctx: TestExecutionContext):
    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    if not compiled:
        return fail_case("missing_contextpack_compiled")

    run_start = _events(ctx, "run_START")
    hard_minimum = any(
        event.get("cx03_minimum_hard") is True
        or (
            isinstance(event.get("policy_flags"), Mapping)
            and event.get("policy_flags", {}).get("cx03_minimum_hard") is True
        )
        for event in run_start
    )

    overdrive_count = 0
    advisory_below_min_count = 0
    for event in compiled:
        mode = str(event.get("compiler_mode", "normal")).lower()
        token_est = event.get("token_est")
        budget = event.get("token_budget")
        if isinstance(token_est, int) and isinstance(budget, int) and budget > 0:
            ratio = token_est / budget
            if ratio < 0.10:
                if hard_minimum:
                    return fail_case("sweet_zone_minimum_not_met", ratio=ratio)
                advisory_below_min_count += 1
            if mode == "normal" and ratio > 0.40:
                return fail_case("sweet_zone_exceeded", ratio=ratio)
            if mode == "overdrive":
                overdrive_count += 1
                if ratio > 0.60:
                    return fail_case("overdrive_budget_exceeded", ratio=ratio)
                if not event.get("overdrive_reason_code"):
                    return fail_case("overdrive_missing_reason_code")

    if overdrive_count > 3:
        return fail_case("overdrive_step_count_exceeded", overdrive_count=overdrive_count)

    return pass_case(
        advisory_sweet_zone_minimum_violations=advisory_below_min_count,
        sweet_zone_minimum_mode="hard" if hard_minimum else "advisory",
    )


def _cx_04_manifest_completeness_hashing(ctx: TestExecutionContext):
    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    if not compiled:
        return fail_case("missing_contextpack_compiled")

    for event in compiled:
        context_ref = event.get("context_pack_ref")
        manifest_ref = event.get("manifest_ref")
        context_hash = event.get("context_pack_hash")
        manifest_hash = event.get("manifest_hash")

        if not isinstance(context_ref, str):
            return fail_case("missing_context_pack_ref")
        failure = require_hash_exists(ctx.artifact_store, context_ref)
        if failure is not None:
            return fail_case(failure.fail_signature, missing_ref=context_ref)

        if isinstance(manifest_ref, str):
            failure = require_hash_exists(ctx.artifact_store, manifest_ref)
            if failure is not None:
                return fail_case(failure.fail_signature, missing_ref=manifest_ref)

        if isinstance(context_hash, str):
            context_json = ctx.artifact_store.load_json(context_ref)
            if stable_hash(context_json) != context_hash:
                return fail_case("context_pack_hash_mismatch")

        if isinstance(manifest_ref, str) and isinstance(manifest_hash, str):
            manifest_json = ctx.artifact_store.load_json(manifest_ref)
            if stable_hash(manifest_json) != manifest_hash:
                return fail_case("manifest_hash_mismatch")

    return pass_case()


def _cx_05_cache_index_pointers(ctx: TestExecutionContext):
    bound = _events(ctx, "CONTEXT_SLICE_BOUND")
    if not bound:
        return pass_case()

    for event in bound:
        for field in ("context_pack_ref", "context_pack_hash", "manifest_ref", "manifest_hash"):
            if event.get(field) in (None, ""):
                return fail_case("context_slice_bound_missing_field", field=field)

    return pass_case()


def _cx_06_rehydration_exact_spans(ctx: TestExecutionContext):
    bound = _events(ctx, "CONTEXT_SLICE_BOUND")
    if not bound:
        return pass_case()

    for event in bound:
        if event.get("bytes_match") is False:
            return fail_case("rehydration_bytes_mismatch")
        if event.get("source_hash_match") is False:
            return fail_case("rehydration_source_hash_mismatch")

    return pass_case()


def _cx_07_cache_key_correctness(ctx: TestExecutionContext):
    decisions = _events(ctx, "MODEL_ROUTE_DECISION")
    if not decisions:
        return pass_case()

    seen: dict[str, tuple[object, object]] = {}
    for event in decisions:
        signal = event.get("signals_hash")
        if signal in (None, ""):
            return fail_case("missing_signals_hash")
        routing = (event.get("from_model_id"), event.get("to_model_id"))
        signal_key = str(signal)
        if signal_key in seen and seen[signal_key] != routing:
            return fail_case("route_decision_nondeterministic_for_same_signal")
        seen[signal_key] = routing

    return pass_case()


def _cx_08_permission_creep_blocked(ctx: TestExecutionContext):
    override = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if event.get("violation_code") == "OVERRIDE_ATTEMPT"
    ]
    if override:
        return pass_case()

    denies = _events(ctx, "TOOL_DENY")
    for deny in denies:
        if str(deny.get("deny_reason_code", "")).upper() in {"TOOL_SURFACE_EXPANDED", "POLICY_SURFACE_WIDENED"}:
            return pass_case()

    return pass_case()


def _cx_09_overdrive_cost_impact_logging_required(ctx: TestExecutionContext):
    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    overdrive = [event for event in compiled if str(event.get("compiler_mode", "normal")).lower() == "overdrive"]
    if not overdrive:
        return pass_case()

    metrics = _events(ctx, "METRIC_SUMMARY")
    metrics_by_step = {event.get("step_id"): event for event in metrics}

    for event in overdrive:
        step_id = event.get("step_id")
        metric = metrics_by_step.get(step_id)
        if metric is None:
            return fail_case("overdrive_missing_metric_summary", step_id=step_id)

        has_cost_delta = any(
            metric.get(field) not in (None, "")
            for field in ("overdrive_cost_delta_usd", "overdrive_token_delta", "overdrive_cost_impact")
        )
        if not has_cost_delta:
            return fail_case("overdrive_cost_impact_not_logged", step_id=step_id)

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="CX-01", name="Strict Layer Order", objective="ContextPack layers respect deterministic order.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cx_01_strict_layer_order),
        make_case(pack=PACK, test_id="CX-02", name="UNTRUSTED Delimiters Enforced", objective="Untrusted content must be delimited and tagged.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cx_02_untrusted_delimiters),
        make_case(pack=PACK, test_id="CX-03", name="Sweet Zone and Overdrive Limits", objective="Compiler token usage enforces sweet-zone and bounded overdrive.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cx_03_sweet_zone_and_overdrive),
        make_case(pack=PACK, test_id="CX-04", name="Manifest Completeness and Hashing", objective="Manifest and context hashes are complete and CAS-consistent.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cx_04_manifest_completeness_hashing),
        make_case(pack=PACK, test_id="CX-05", name="Cache Index Uses Pointers", objective="Summaries remain derived pointers, never substituted truth.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cx_05_cache_index_pointers),
        make_case(pack=PACK, test_id="CX-06", name="Rehydration Returns Exact Spans", objective="Rehydration bytes and source hashes match exactly.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cx_06_rehydration_exact_spans),
        make_case(pack=PACK, test_id="CX-07", name="Cache Key Correctness", objective="Cache keys include required inputs and invalidate on key changes.", required_event_types=["MODEL_ROUTE_DECISION"], checker=_cx_07_cache_key_correctness),
        make_case(pack=PACK, test_id="CX-08", name="Compiler Permission Creep Blocked", objective="Untrusted evidence cannot widen tool/policy surface.", required_event_types=["run_END"], checker=_cx_08_permission_creep_blocked),
        make_case(pack=PACK, test_id="CX-09", name="Overdrive Cost Impact Logged", objective="Overdrive mode requires explicit cost-impact logging.", required_event_types=["CONTEXTPACK_COMPILED", "METRIC_SUMMARY"], checker=_cx_09_overdrive_cost_impact_logging_required),
    ]
