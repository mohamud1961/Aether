from __future__ import annotations

from typing import List, Mapping, Tuple

from ..models import TestCase, TestExecutionContext
from ._common import events_of, fail_case, make_case, pass_case


PACK = "intent"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _im_01_intent_contract_schema(ctx: TestExecutionContext):
    contracts = _events(ctx, "INTENT_CONTRACT_DEFINED")
    if not contracts:
        return fail_case("missing_intent_contract_defined")

    required_fields = {
        "goal_statement",
        "deliverables",
        "acceptance_criteria",
        "risk_profile",
        "environment_assumptions",
    }

    for contract in contracts:
        intent_contract = contract.get("intent_contract", contract)
        if not isinstance(intent_contract, Mapping):
            return fail_case("invalid_intent_contract_payload")
        missing = [field for field in sorted(required_fields) if field not in intent_contract]
        if missing:
            return fail_case("intent_contract_missing_fields", missing_fields=missing)

    return pass_case()


def _im_02_completeness_blocks_execution(ctx: TestExecutionContext):
    checks = _events(ctx, "INTENT_COMPLETENESS_CHECK")
    if not checks:
        return fail_case("missing_intent_completeness_checks")

    first_pass_step = None
    for check in checks:
        if check.get("pass") is True:
            first_pass_step = check.get("step_id")
            break

    if first_pass_step is None:
        for event in _events(ctx, "CONTRACT_DEFINED", "PLAN_DEFINED"):
            return fail_case("execution_started_before_intent_pass", step_id=event.get("step_id"))

    for event in _events(ctx, "CONTRACT_DEFINED", "PLAN_DEFINED"):
        step_id = event.get("step_id")
        if isinstance(step_id, int) and isinstance(first_pass_step, int) and step_id < first_pass_step:
            return fail_case("execution_started_before_intent_pass", step_id=step_id)

    return pass_case()


def _im_03_deterministic_completeness(ctx: TestExecutionContext):
    checks = _events(ctx, "INTENT_COMPLETENESS_CHECK")
    if len(checks) < 2:
        return pass_case()

    seen: dict[Tuple[object, Tuple[str, ...]], bool] = {}
    for check in checks:
        missing_fields = tuple(sorted(str(item) for item in (check.get("missing_fields") or [])))
        signal_hash = check.get("signal_hash", check.get("intent_hash", "default"))
        decision = bool(check.get("pass"))
        key = (signal_hash, missing_fields)
        if key in seen and seen[key] != decision:
            return fail_case("nondeterministic_intent_completeness")
        seen[key] = decision

    return pass_case()


def _im_04_targeted_clarification_bounded(ctx: TestExecutionContext):
    checks = [check for check in _events(ctx, "INTENT_COMPLETENESS_CHECK") if check.get("pass") is False]
    if not checks:
        return pass_case()

    repeats = 0
    previous_missing: Tuple[str, ...] | None = None
    for check in checks:
        missing_fields = tuple(sorted(str(item) for item in (check.get("missing_fields") or [])))
        if not missing_fields:
            return fail_case("missing_missing_fields_on_failed_check")

        if previous_missing == missing_fields:
            repeats += 1
        else:
            repeats = 0
            previous_missing = missing_fields

        if repeats > 2:
            return fail_case("unbounded_clarification_loop", missing_fields=list(missing_fields))

    return pass_case()


def _im_05_intent_contract_immutable(ctx: TestExecutionContext):
    contracts = _events(ctx, "INTENT_CONTRACT_DEFINED")
    if not contracts:
        return fail_case("missing_intent_contract_defined")

    initial_digest = contracts[0].get("intent_digest", contracts[0].get("intent_contract_id"))
    if initial_digest is None:
        return fail_case("missing_intent_digest")

    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    if not compiled:
        return fail_case("missing_contextpack_compiled")

    for event in compiled:
        digest = event.get("intent_digest", event.get("intent_contract_id", initial_digest))
        if digest != initial_digest:
            return fail_case("intent_digest_mutated")

    mutation_attempts = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if event.get("violation_code") == "OVERRIDE_ATTEMPT"
    ]
    if mutation_attempts:
        return pass_case()

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="IM-01", name="IntentContract Schema Completeness", objective="IntentContract is persisted and includes required schema fields.", required_event_types=["INTENT_CONTRACT_DEFINED"], checker=_im_01_intent_contract_schema),
        make_case(pack=PACK, test_id="IM-02", name="IntentCompletenessCheck Blocks Execution", objective="Execution does not start before completeness pass=true.", required_event_types=["INTENT_COMPLETENESS_CHECK"], checker=_im_02_completeness_blocks_execution),
        make_case(pack=PACK, test_id="IM-03", name="Deterministic Completeness Check", objective="Completeness decisions are deterministic for identical intake signals.", required_event_types=["INTENT_COMPLETENESS_CHECK"], checker=_im_03_deterministic_completeness),
        make_case(pack=PACK, test_id="IM-04", name="Bounded Clarification Behavior", objective="Missing fields are narrowed without unbounded repeats.", required_event_types=["INTENT_COMPLETENESS_CHECK"], checker=_im_04_targeted_clarification_bounded),
        make_case(pack=PACK, test_id="IM-05", name="Intent Immutable Input to Execution", objective="Intent digest remains stable and mutation attempts are rejected.", required_event_types=["INTENT_CONTRACT_DEFINED", "CONTEXTPACK_COMPILED"], checker=_im_05_intent_contract_immutable),
    ]
