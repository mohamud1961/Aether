from __future__ import annotations

from pathlib import Path
from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_enum
from ._common import events_of, fail_case, make_case, pass_case, success_events


PACK = "interface"
_PATH_DENY_CODES = {
    "PATH_SANDBOX_VIOLATION",
    "PATH_TRAVERSAL",
    "RELATIVE_ESCAPE",
    "ABSOLUTE_OUTSIDE_ROOT",
}


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _workspace_root(ctx: TestExecutionContext) -> str | None:
    starts = _events(ctx, "run_START")
    if not starts:
        return None
    value = starts[-1].get("workspace_root") or starts[-1].get("cwd")
    if isinstance(value, str) and value:
        return value
    return None


def _extract_cwd(event: Mapping[str, object]) -> str | None:
    args = event.get("tool_args")
    if isinstance(args, Mapping):
        cwd = args.get("cwd")
        if isinstance(cwd, str) and cwd:
            return cwd
    cwd = event.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    return None


def _a1_path_sandbox_in_root_allowed_outside_denied(ctx: TestExecutionContext):
    root = _workspace_root(ctx)
    denied = [
        event
        for event in _events(ctx, "TOOL_DENY", "POLICY_VIOLATION")
        if str(event.get("deny_reason_code", event.get("violation_code", ""))).upper() == "PATH_SANDBOX_VIOLATION"
    ]

    if root:
        for event in denied:
            cwd = _extract_cwd(event)
            if not cwd:
                continue
            try:
                p = Path(cwd)
            except Exception:
                continue
            if p.is_absolute() and cwd.startswith(root):
                return fail_case("in_root_absolute_cwd_denied", cwd=cwd)

    if denied and success_events(ctx):
        return fail_case("success_after_path_sandbox_violation")

    return pass_case(path_sandbox_violations=len(denied))


def _a2_path_escape_fuzz_closed(ctx: TestExecutionContext):
    suspicious = []
    for event in _events(ctx, "TOOL_CALL", "TOOL_DENY"):
        args = event.get("tool_args")
        if not isinstance(args, Mapping):
            continue
        for key, value in args.items():
            if not isinstance(value, str):
                continue
            if ".." in value or "/../" in value or value.startswith("/app"):
                suspicious.append((event, key, value))

    if not suspicious:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_path_escape_attempts")

    denied_codes = {
        str(event.get("deny_reason_code", "")).upper()
        for event in _events(ctx, "TOOL_DENY")
    }
    if _PATH_DENY_CODES.isdisjoint(denied_codes):
        return fail_case("path_escape_attempt_not_denied", attempts=len(suspicious))

    return pass_case(path_escape_attempts=len(suspicious))


def _a3_schema_prompt_alignment(ctx: TestExecutionContext):
    by_cwd: dict[str, set[str]] = {}
    for event in _events(ctx, "TOOL_CALL"):
        cwd = _extract_cwd(event)
        if cwd:
            by_cwd.setdefault(cwd, set()).add("call")
    for event in _events(ctx, "TOOL_DENY"):
        if str(event.get("deny_reason_code", "")).upper() != "PATH_SANDBOX_VIOLATION":
            continue
        cwd = _extract_cwd(event)
        if cwd:
            by_cwd.setdefault(cwd, set()).add("deny")

    for cwd, states in by_cwd.items():
        if states == {"call", "deny"}:
            return fail_case("cwd_semantics_nondeterministic", cwd=cwd)

    return pass_case(distinct_cwd_values=len(by_cwd))


def _a4_tool_denial_taxonomy_closed_enum(ctx: TestExecutionContext):
    denials = _events(ctx, "TOOL_DENY", "PHASE_TRANSITION_DENIED")
    if not denials:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_denials")

    for denial in denials:
        reason_code = denial.get("deny_reason_code")
        if reason_code in (None, ""):
            return fail_case("missing_deny_reason_code", step_id=denial.get("step_id"))
        failure = require_enum(ctx.enum_registry, "deny_reason_code", reason_code)
        if failure is not None:
            return fail_case(failure.fail_signature, code=reason_code)

    return pass_case(denials=len(denials))


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="A1", name="PATH_SANDBOX semantics", objective="Absolute cwd under workspace is allowed; outside-root is denied.", required_event_types=["run_END"], checker=_a1_path_sandbox_in_root_allowed_outside_denied),
        make_case(pack=PACK, test_id="A2", name="Path escape fuzz", objective="Traversal and escape attempts fail closed.", required_event_types=["run_END"], checker=_a2_path_escape_fuzz_closed),
        make_case(pack=PACK, test_id="A3", name="Schema and prompt alignment", objective="cwd semantics are deterministic across schema/prompt/gateway behavior.", required_event_types=["run_END"], checker=_a3_schema_prompt_alignment),
        make_case(pack=PACK, test_id="A4", name="Closed denial taxonomy", objective="deny_reason_code is always present and in closed enum.", required_event_types=["run_END"], checker=_a4_tool_denial_taxonomy_closed_enum),
    ]
