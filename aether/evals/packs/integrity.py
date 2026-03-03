from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Mapping

from ..models import TestCase, TestExecutionContext
from ._common import events_of, fail_case, make_case, pass_case


PACK = "integrity"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _load_integrity_report(ctx: TestExecutionContext) -> tuple[Path, dict[str, Any] | None, str | None]:
    report_path = ctx.artifact_dir / "integrity_report.json"
    if not report_path.exists():
        return report_path, None, "integrity_report_missing"

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return report_path, None, "integrity_report_invalid_json"

    if not isinstance(payload, dict):
        return report_path, None, "integrity_report_not_object"

    return report_path, payload, None


def _fixture_na(ctx: TestExecutionContext):
    if ctx.fixture_name is not None:
        return pass_case(applicability="NOT_APPLICABLE", reason="fixture_artifact_source")
    return None


def _i1_integrity_report_present_and_oracle_isolated(ctx: TestExecutionContext):
    fixture_na = _fixture_na(ctx)
    if fixture_na is not None:
        return fixture_na

    report_path, payload, error = _load_integrity_report(ctx)
    if error is not None:
        return fail_case(error, report_path=report_path.as_posix())
    assert payload is not None

    explicit_claim = payload.get("claims_no_oracle_access")
    if isinstance(explicit_claim, bool):
        if not explicit_claim:
            return fail_case("integrity_report_claims_oracle_access")
        return pass_case(report_path=report_path.as_posix(), claim_source="explicit")

    checks = payload.get("agent_container_checks")
    if not isinstance(checks, Mapping):
        return fail_case("integrity_report_missing_oracle_checks")

    if checks.get("tests_path_exists") is not False:
        return fail_case("integrity_report_tests_path_exposed")
    if checks.get("verifier_artifacts_accessible") is not False:
        return fail_case("integrity_report_verifier_artifacts_exposed")

    return pass_case(report_path=report_path.as_posix(), claim_source="agent_container_checks")


def _i2_run_start_surface_profile_present_non_empty(ctx: TestExecutionContext):
    fixture_na = _fixture_na(ctx)
    if fixture_na is not None:
        return fixture_na

    starts = _events(ctx, "run_START")
    if not starts:
        return fail_case("run_start_missing")

    surface = starts[-1].get("tool_surface_profile")
    if not isinstance(surface, Mapping):
        return fail_case("tool_surface_profile_missing")

    tools = surface.get("tools")
    if not isinstance(tools, list) or not tools:
        return fail_case("tool_surface_profile_empty")

    return pass_case(tool_count=len(tools))


def _i3_transition_request_in_surface(ctx: TestExecutionContext):
    fixture_na = _fixture_na(ctx)
    if fixture_na is not None:
        return fixture_na

    starts = _events(ctx, "run_START")
    if not starts:
        return fail_case("run_start_missing")

    surface = starts[-1].get("tool_surface_profile")
    if not isinstance(surface, Mapping):
        return fail_case("tool_surface_profile_missing")

    tools = surface.get("tools")
    if not isinstance(tools, list) or not tools:
        return fail_case("tool_surface_profile_empty")
    if "request_phase_transition" not in tools:
        return fail_case("request_phase_transition_missing_from_surface")

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(
            pack=PACK,
            test_id="I1",
            name="Integrity report + oracle isolation",
            objective="Run directory contains integrity_report.json and asserts no oracle access.",
            required_event_types=["run_END"],
            checker=_i1_integrity_report_present_and_oracle_isolated,
        ),
        make_case(
            pack=PACK,
            test_id="I2",
            name="run_START tool surface profile",
            objective="run_START includes a non-empty tool_surface_profile.",
            required_event_types=["run_START"],
            checker=_i2_run_start_surface_profile_present_non_empty,
        ),
        make_case(
            pack=PACK,
            test_id="I3",
            name="Transition request tool present",
            objective="request_phase_transition appears in the run_START tool surface.",
            required_event_types=["run_START"],
            checker=_i3_transition_request_in_surface,
        ),
    ]
