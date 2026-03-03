from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_hash_exists
from ._common import events_of, fail_case, make_case, pass_case, success_events


PACK = "tool"
INTERPRETER_PREFIXES = ("python", "bash", "sh", "node", "ruby", "perl")


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _tg_01_single_gateway_rule(ctx: TestExecutionContext):
    bypass_events = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if str(event.get("violation_code", "")).upper() in {"GATEWAY_BYPASS", "DIRECT_EXECUTION"}
    ]
    if bypass_events and success_events(ctx):
        return fail_case("success_after_gateway_bypass")
    return pass_case()


def _tg_02_canonical_receipt_fields(ctx: TestExecutionContext):
    calls = _events(ctx, "TOOL_CALL")
    if not calls:
        return fail_case("missing_tool_calls")

    required_fields = [
        "stdout_hash",
        "stderr_hash",
        "truncation_flags",
        "side_effect_scope",
        "reversibility",
        "observed_workspace_hash_before",
    ]

    for call in calls:
        for field in required_fields:
            if call.get(field) in (None, ""):
                return fail_case("missing_tool_receipt_field", field=field, step_id=call.get("step_id"))

    return pass_case()


def _tg_03_dialect_adapter_lossless(ctx: TestExecutionContext):
    calls = _events(ctx, "TOOL_CALL")
    for call in calls:
        if call.get("tool_name") in (None, ""):
            return fail_case("missing_tool_name")
        if call.get("tool_category") in (None, ""):
            return fail_case("missing_tool_category")
        if call.get("args_hash") in (None, ""):
            return fail_case("missing_args_hash")

    override_violations = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if event.get("violation_code") == "OVERRIDE_ATTEMPT"
    ]
    if override_violations and success_events(ctx):
        return fail_case("dialect_route_policy_bypass")

    return pass_case()


def _tg_04_request_phase_transition_always_available(ctx: TestExecutionContext):
    denied = _events(ctx, "PHASE_TRANSITION_DENIED")
    for event in denied:
        if event.get("deny_reason_code") in (None, ""):
            return fail_case("missing_phase_transition_reason")
    return pass_case()


def _tg_05_path_sandboxing(ctx: TestExecutionContext):
    path_denies = [
        event
        for event in (_events(ctx, "TOOL_DENY") + _events(ctx, "POLICY_VIOLATION"))
        if str(event.get("deny_reason_code", event.get("violation_code", ""))).upper()
        in {"PATH_VIOLATION", "PATH_TRAVERSAL", "ABSOLUTE_OUTSIDE_ROOT", "RELATIVE_ESCAPE"}
    ]
    if path_denies and success_events(ctx):
        return fail_case("success_after_path_violation")

    run_end = _events(ctx, "run_END")
    if path_denies and run_end:
        if any(event.get("terminal_outcome") == "SUCCESS" for event in run_end):
            return fail_case("success_after_path_violation")

    return pass_case()


def _tg_06_network_control(ctx: TestExecutionContext):
    run_start = _events(ctx, "run_START")
    network_disabled = any(event.get("network_enabled") is False for event in run_start)
    if not network_disabled:
        return pass_case()

    network_calls = [
        event
        for event in _events(ctx, "TOOL_CALL")
        if event.get("tool_category") == "NETWORK"
    ]
    if network_calls:
        return fail_case("network_egress_allowed_when_disabled")

    return pass_case()


def _tg_07_script_hash_allowlisting(ctx: TestExecutionContext):
    run_start = _events(ctx, "run_START")
    interpreter_exposed = False
    for event in run_start:
        surface = event.get("tool_surface_profile")
        if isinstance(surface, Mapping):
            if surface.get("interpreters_exposed") is True:
                interpreter_exposed = True
            exposed = surface.get("exposed_interpreters")
            if isinstance(exposed, list) and exposed:
                interpreter_exposed = True
        elif isinstance(surface, str):
            lowered = surface.lower()
            if "interpreter" in lowered or "shell" in lowered:
                interpreter_exposed = True

    if not interpreter_exposed:
        interpreter_exposed = any(
            str(event.get("tool_name", "")).startswith(INTERPRETER_PREFIXES)
            for event in (_events(ctx, "TOOL_CALL") + _events(ctx, "TOOL_DENY"))
        )

    if not interpreter_exposed:
        return pass_case(applicability="NOT_APPLICABLE", reason="interpreter_not_exposed")

    denies = _events(ctx, "TOOL_DENY")
    for event in denies:
        code = str(event.get("deny_reason_code", "")).upper()
        if code == "SCRIPT_HASH_NOT_ALLOWLISTED":
            return pass_case()

    interpreter_calls = [
        event
        for event in _events(ctx, "TOOL_CALL")
        if str(event.get("tool_name", "")).startswith(("python", "bash", "sh"))
    ]
    for call in interpreter_calls:
        if call.get("script_hash_allowlisted") is not True:
            return fail_case("interpreter_call_without_allowlisted_script_hash")

    return pass_case()


def _tg_11_tool_timeout_receipt_correctness(ctx: TestExecutionContext):
    calls = [event for event in _events(ctx, "TOOL_CALL") if event.get("timeout") is True]
    if not calls:
        return pass_case()

    for call in calls:
        exit_code = call.get("exit_code")
        if exit_code not in {"TIMEOUT", "timeout"}:
            return fail_case("tool_timeout_exit_code_invalid", step_id=call.get("step_id"))
        if call.get("timeout_ms") in (None, ""):
            return fail_case("tool_timeout_missing_timeout_ms", step_id=call.get("step_id"))
        for field in ("stdout_hash", "stderr_hash", "truncation_flags"):
            if call.get(field) in (None, ""):
                return fail_case("tool_timeout_missing_receipt_field", field=field, step_id=call.get("step_id"))

    return pass_case()


def _tg_08_side_effect_rollback_truth(ctx: TestExecutionContext):
    external_calls = [
        event
        for event in _events(ctx, "TOOL_CALL")
        if event.get("side_effect_scope") == "EXTERNAL"
    ]
    if not external_calls:
        return pass_case()

    for call in external_calls:
        if call.get("reversibility") != "NOT_REVERSIBLE":
            return fail_case("external_side_effect_reversibility_invalid")

    limitations = _events(ctx, "ROLLBACK_LIMITATION")
    if not limitations:
        return fail_case("missing_rollback_limitation")

    waiver = any(
        event.get("approval_type") in {"EXTERNAL_EFFECT_WAIVER", "PLAN_WAIVER"}
        for event in _events(ctx, "APPROVAL_GRANTED")
    )
    if success_events(ctx) and not waiver:
        return fail_case("success_after_irreversible_external_without_waiver")

    return pass_case()


def _tg_09_toctou_freshness_guard(ctx: TestExecutionContext):
    stale_denies = [
        event
        for event in _events(ctx, "TOOL_DENY")
        if str(event.get("deny_reason_code", "")).upper() == "STALE_STATE_HASH"
    ]
    if not stale_denies:
        return pass_case()

    step_commits = _events(ctx, "STEP_COMMIT")
    invalid_found = any(
        commit.get("valid") is False or commit.get("commit_status") == "missing_components"
        for commit in step_commits
    )
    if not invalid_found:
        return fail_case("stale_state_without_invalid_step_commit")

    if success_events(ctx):
        return fail_case("success_after_stale_state")

    return pass_case()


def _tg_10_summary_never_replaces_raw(ctx: TestExecutionContext):
    run_end = [event for event in _events(ctx, "run_END") if event.get("terminal_outcome") == "SUCCESS"]
    if not run_end:
        return pass_case()

    for event in run_end:
        refs = []
        receipt_ids = event.get("required_receipt_ids")
        manifest_ids = event.get("required_manifest_ids")
        if isinstance(receipt_ids, list):
            refs.extend([value for value in receipt_ids if isinstance(value, str)])
        if isinstance(manifest_ids, list):
            refs.extend([value for value in manifest_ids if isinstance(value, str)])

        for ref in refs:
            failure = require_hash_exists(ctx.artifact_store, ref)
            if failure is not None:
                return fail_case(failure.fail_signature, missing_ref=ref)

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="TG-01", name="Single Gateway Rule", objective="No execution outside ToolGateway.", required_event_types=["run_END"], checker=_tg_01_single_gateway_rule),
        make_case(pack=PACK, test_id="TG-02", name="Canonical Receipt Fields", objective="Tool receipts include required hash and side-effect fields.", required_event_types=["TOOL_CALL"], checker=_tg_02_canonical_receipt_fields),
        make_case(pack=PACK, test_id="TG-03", name="Dialect Adapter Lossless", objective="Model-native calls map to canonical semantics without policy bypass.", required_event_types=["TOOL_CALL"], checker=_tg_03_dialect_adapter_lossless),
        make_case(pack=PACK, test_id="TG-04", name="request_phase_transition Always Available", objective="Transition request action is always available and auditable.", required_event_types=["run_END"], checker=_tg_04_request_phase_transition_always_available),
        make_case(pack=PACK, test_id="TG-05", name="Path Sandbox Enforcement", objective="Traversal and out-of-root writes are denied deterministically.", required_event_types=["run_END"], checker=_tg_05_path_sandboxing),
        make_case(pack=PACK, test_id="TG-06", name="Network Control Enforcement", objective="Network egress is denied when policy disables network.", required_event_types=["run_START"], checker=_tg_06_network_control),
        make_case(pack=PACK, test_id="TG-07", name="Script Hash Allowlisting", objective="Interpreter execution requires allowlisted script hashes when interpreters are exposed.", required_event_types=["run_START"], checker=_tg_07_script_hash_allowlisting),
        make_case(pack=PACK, test_id="TG-08", name="Rollback Truth for External Side Effects", objective="External irreversible effects emit rollback limitation and gate success.", required_event_types=["TOOL_CALL", "ROLLBACK_LIMITATION"], checker=_tg_08_side_effect_rollback_truth),
        make_case(pack=PACK, test_id="TG-09", name="TOCTOU Freshness Guard", objective="Stale state hash denies execution and invalidates the step.", required_event_types=["TOOL_DENY", "STEP_COMMIT"], checker=_tg_09_toctou_freshness_guard),
        make_case(pack=PACK, test_id="TG-10", name="Summaries Never Replace Raw Truth", objective="Summaries are derived pointers and cannot replace raw CAS truth.", required_event_types=["run_END"], checker=_tg_10_summary_never_replaces_raw),
        make_case(pack=PACK, test_id="TG-11", name="Tool Timeout Receipt Correctness", objective="Timed-out TOOL_CALL receipts keep canonical timeout metadata.", required_event_types=["TOOL_CALL"], checker=_tg_11_tool_timeout_receipt_correctness),
    ]
