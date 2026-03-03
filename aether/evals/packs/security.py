from __future__ import annotations

from typing import Iterable, List, Mapping, Tuple

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_enum
from ._common import events_of, fail_case, make_case, pass_case, success_events


PACK = "security"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _enum_field_values(events: Iterable[Mapping[str, object]]) -> List[Tuple[str, object]]:
    values: List[Tuple[str, object]] = []

    for event in events:
        event_type = str(event.get("event_type", ""))

        if "deny_reason_code" in event:
            values.append(("deny_reason_code", event.get("deny_reason_code")))
        if "violation_code" in event:
            values.append(("violation_code", event.get("violation_code")))
        if "approval_type" in event:
            values.append(("approval_type", event.get("approval_type")))
        if "approval_reason_code" in event:
            values.append(("approval_reason_code", event.get("approval_reason_code")))
        if "risk_class" in event:
            values.append(("risk_class", event.get("risk_class")))
        if "tool_category" in event:
            values.append(("tool_category", event.get("tool_category")))
        if "truncation_flags" in event:
            values.append(("truncation_flags", event.get("truncation_flags")))
        if "update_reason_code" in event:
            values.append(("plan_update_reason_code", event.get("update_reason_code")))
        if "verifier_stage" in event:
            values.append(("verifier_stage", event.get("verifier_stage")))
        if "trigger_code" in event:
            values.append(("reanchor_trigger_code", event.get("trigger_code")))
        if "summary_reason_code" in event:
            values.append(("summary_reason_code", event.get("summary_reason_code")))

        if event_type == "PLAN_DEFINED" and "status" in event:
            values.append(("plan_status", event.get("status")))
        if event_type == "PLAN_STATUS_CHANGED" and "from_status" in event:
            values.append(("plan_status", event.get("from_status")))
        if event_type == "PLAN_STATUS_CHANGED" and "to_status" in event:
            values.append(("plan_status", event.get("to_status")))

        slices = event.get("slice_list")
        if isinstance(slices, list):
            for item in slices:
                if isinstance(item, Mapping) and "trust_level" in item:
                    values.append(("trust_level", item.get("trust_level")))

    return values


def _sd_01_enum_registry_loaded_hashed(ctx: TestExecutionContext):
    run_start = _events(ctx, "run_START")
    if not run_start:
        return pass_case()

    for event in run_start:
        enum_hash = event.get("enum_registry_hash")
        policy_hash = event.get("policy_hash")
        if enum_hash in (None, ""):
            return fail_case("missing_enum_registry_hash")
        if policy_hash in (None, ""):
            return fail_case("missing_policy_hash")

    return pass_case()


def _sd_02_unknown_enum_blocks_success(ctx: TestExecutionContext):
    unknown_detected = False
    for enum_name, enum_value in _enum_field_values([event.payload for event in ctx.events]):
        failure = require_enum(ctx.enum_registry, enum_name, enum_value)
        if failure is not None:
            unknown_detected = True

    if unknown_detected and success_events(ctx):
        return fail_case("success_allowed_with_unknown_enum")

    if unknown_detected:
        violations = _events(ctx, "POLICY_VIOLATION")
        if not any(event.get("violation_code") == "UNKNOWN_ENUM" for event in violations):
            return fail_case("unknown_enum_missing_policy_violation")

    return pass_case()


def _sd_03_redaction_before_persistence(ctx: TestExecutionContext):
    redaction_events = _events(ctx, "REDACTION_APPLIED")
    if not redaction_events:
        return pass_case()

    for event in redaction_events:
        count = event.get("count")
        types = event.get("types")
        if not isinstance(count, int) or count < 0:
            return fail_case("invalid_redaction_count")
        if not isinstance(types, list):
            return fail_case("invalid_redaction_types")

    blocked = any(event.get("blocked") is True for event in _events(ctx, "DLP_SCAN_RESULT"))
    if blocked and not any(int(event.get("count", 0)) > 0 for event in redaction_events):
        return fail_case("dlp_block_without_redaction")

    return pass_case()


def _sd_04_dlp_blocks_without_approval(ctx: TestExecutionContext):
    scans = _events(ctx, "DLP_SCAN_RESULT")
    if not scans:
        return pass_case()

    blocked = any(event.get("blocked") is True for event in scans)
    if not blocked:
        return pass_case()

    approvals = _events(ctx, "APPROVAL_GRANTED")
    has_override = any(event.get("approval_type") in {"DLP_OVERRIDE", "PLAN_WAIVER"} for event in approvals)

    if success_events(ctx) and not has_override:
        return fail_case("success_despite_dlp_block_without_approval")

    return pass_case()


def _sd_05_untrusted_steering_isolation(ctx: TestExecutionContext):
    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    for event in compiled:
        slices = event.get("slice_list")
        if not isinstance(slices, list):
            continue
        for slice_item in slices:
            if not isinstance(slice_item, Mapping):
                continue
            content = str(slice_item.get("content_preview", ""))
            trust = str(slice_item.get("trust_level", "")).upper()
            if "SYSTEM:" in content or "IMPORTANT:" in content:
                if trust not in {"UNTRUSTED", "LOW"}:
                    return fail_case("injection_text_in_trusted_slice")

    return pass_case()


def _sd_06_override_attempts_rejected(ctx: TestExecutionContext):
    override = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if event.get("violation_code") == "OVERRIDE_ATTEMPT"
    ]
    if not override:
        return pass_case()

    if success_events(ctx):
        return fail_case("override_attempt_reached_success")

    return pass_case()


def _sd_07_role_based_approval(ctx: TestExecutionContext):
    approvals = _events(ctx, "APPROVAL_GRANTED")
    for approval in approvals:
        actor_id = approval.get("actor_id")
        if actor_id in (None, ""):
            return fail_case("approval_missing_actor_id")

        required_role = approval.get("required_role")
        actor_role = approval.get("actor_role")
        if required_role and actor_role != required_role:
            return fail_case("approval_granted_with_wrong_role")

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="SD-01", name="Enum Registry Loaded and Hashed", objective="run start includes enum_registry_hash and policy_hash.", required_event_types=["run_START"], checker=_sd_01_enum_registry_loaded_hashed),
        make_case(pack=PACK, test_id="SD-02", name="Unknown Enum Blocks SUCCESS", objective="Unknown enum values produce policy violations and block success.", required_event_types=["run_END"], checker=_sd_02_unknown_enum_blocks_success),
        make_case(pack=PACK, test_id="SD-03", name="Redaction Before Persistence", objective="Secrets are redacted before artifact persistence.", required_event_types=["REDACTION_APPLIED"], checker=_sd_03_redaction_before_persistence),
        make_case(pack=PACK, test_id="SD-04", name="DLP Blocks Without Approval", objective="DLP blocks success unless explicit approval override exists.", required_event_types=["DLP_SCAN_RESULT"], checker=_sd_04_dlp_blocks_without_approval),
        make_case(pack=PACK, test_id="SD-05", name="Untrusted Steering Isolation", objective="Untrusted injection content does not cross trust boundaries.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_sd_05_untrusted_steering_isolation),
        make_case(pack=PACK, test_id="SD-06", name="Policy Override Attempts Rejected", objective="Policy/tool surface cannot be widened by override attempts.", required_event_types=["POLICY_VIOLATION"], checker=_sd_06_override_attempts_rejected),
        make_case(pack=PACK, test_id="SD-07", name="Role-based Approvals Enforced", objective="Approvals require correct actor_id/actor_role authorization.", required_event_types=["APPROVAL_GRANTED"], checker=_sd_07_role_based_approval),
    ]
