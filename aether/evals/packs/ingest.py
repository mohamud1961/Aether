from __future__ import annotations

from typing import List, Mapping

from aether.event_log import REQUIRED_FIELDS

from ..models import TestCase, TestExecutionContext
from ..utils.events import ALLOWED_EVENT_TYPES
from ._common import events_of, fail_case, make_case, pass_case


PACK = "ingest"
_ALLOWED_TERMINALS = {
    "SUCCESS",
    "FAIL_POLICY",
    "FAIL_BUDGET",
    "FAIL_STUCK",
    "FAIL_ENV",
    "FAIL_ENVIRONMENT",
    "FAIL_VERIFICATION",
    "FAIL_UNKNOWN",
}


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _b1_strict_loader_ingests_run_dir(ctx: TestExecutionContext):
    if not ctx.events:
        return fail_case("ingest_empty_event_stream")
    return pass_case(ingested_events=len(ctx.events), artifact_dir=ctx.artifact_dir.as_posix())


def _b2_allowed_vs_required_types_enforced(ctx: TestExecutionContext):
    unknown = []
    for event in ctx.events:
        payload = getattr(event, "payload", event)
        event_type = payload.get("event_type") if isinstance(payload, Mapping) else None
        if event_type not in ALLOWED_EVENT_TYPES:
            unknown.append(str(event_type))
    if unknown:
        return fail_case("unknown_event_type_detected", unknown_event_types=sorted(set(unknown)))
    return pass_case(event_type_count=len({event.payload.get("event_type") for event in ctx.events}))


def _b3_required_baseline_fields_present(ctx: TestExecutionContext):
    for event in ctx.events:
        payload = event.payload
        missing = [field for field in REQUIRED_FIELDS if field not in payload]
        if missing:
            return fail_case(
                "missing_required_baseline_fields",
                event_type=payload.get("event_type"),
                step_id=payload.get("step_id"),
                missing_fields=missing,
            )
    return pass_case(required_fields=len(REQUIRED_FIELDS))


def _b4_canonical_run_end_terminal_outcome(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    if not run_end:
        return fail_case("missing_run_end")

    for event in run_end:
        outcome = event.get("terminal_outcome")
        if outcome not in _ALLOWED_TERMINALS:
            return fail_case("invalid_terminal_outcome", terminal_outcome=outcome)
        if event.get("summary_reason_code") in (None, ""):
            return fail_case("run_end_missing_summary_reason_code")

    return pass_case(run_end_count=len(run_end))


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="B1", name="Strict loader ingest", objective="Strict loader ingests run directories without crash.", required_event_types=["run_END"], checker=_b1_strict_loader_ingests_run_dir),
        make_case(pack=PACK, test_id="B2", name="Allowed and required types", objective="Unknown event types fail closed under strict ingest.", required_event_types=["run_END"], checker=_b2_allowed_vs_required_types_enforced),
        make_case(pack=PACK, test_id="B3", name="Required baseline fields", objective="Required baseline fields exist for runtime events.", required_event_types=["run_END"], checker=_b3_required_baseline_fields_present),
        make_case(pack=PACK, test_id="B4", name="Canonical run_END", objective="Terminal outcome uses canonical closed enum with required fields.", required_event_types=["run_END"], checker=_b4_canonical_run_end_terminal_outcome),
    ]
