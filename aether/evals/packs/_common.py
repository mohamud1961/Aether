from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

from ..models import TestCase, TestExecutionContext, TestResult
from ..utils.events import canonicalize_event_type, validate_required_fields, validate_step_atomicity


@dataclass(frozen=True)
class CaseOutcome:
    passed: bool
    fail_signature: str | None = None
    evidence_refs: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


def pass_case(evidence_refs: Sequence[str] | None = None, **details: Any) -> CaseOutcome:
    return CaseOutcome(
        passed=True,
        fail_signature=None,
        evidence_refs=list(evidence_refs or []),
        details=details,
    )


def fail_case(fail_signature: str, evidence_refs: Sequence[str] | None = None, **details: Any) -> CaseOutcome:
    return CaseOutcome(
        passed=False,
        fail_signature=fail_signature,
        evidence_refs=list(evidence_refs or []),
        details=details,
    )


def payload_of(event: Any) -> Mapping[str, Any]:
    if hasattr(event, "payload"):
        payload = getattr(event, "payload")
        if isinstance(payload, Mapping):
            return payload
    if isinstance(event, Mapping):
        return event
    return {}


def events_of(ctx: TestExecutionContext, event_type: str) -> List[Mapping[str, Any]]:
    canonical = canonicalize_event_type(event_type)
    return [payload_of(event) for event in ctx.events if payload_of(event).get("event_type") == canonical]


def latest_of(ctx: TestExecutionContext, event_type: str) -> Mapping[str, Any] | None:
    matches = events_of(ctx, event_type)
    if not matches:
        return None
    return matches[-1]


def collect_evidence_refs(events: Iterable[Mapping[str, Any]]) -> List[str]:
    refs: set[str] = set()
    for event in events:
        artifact_refs = event.get("artifact_refs")
        if isinstance(artifact_refs, list):
            for ref in artifact_refs:
                if isinstance(ref, str) and ref:
                    refs.add(ref)
        for key in ("stdout_ref", "stderr_ref", "artifact_ref"):
            ref = event.get(key)
            if isinstance(ref, str) and ref:
                refs.add(ref)
    return sorted(refs)


def event_types_present(ctx: TestExecutionContext) -> List[str]:
    return sorted({payload_of(event).get("event_type", "") for event in ctx.events if payload_of(event).get("event_type")})


def governance_reason(event: Mapping[str, Any]) -> str | None:
    governance = event.get("governance")
    if isinstance(governance, Mapping):
        reason = governance.get("reason_code")
        if isinstance(reason, str):
            return reason
    reason = event.get("reason_code")
    if isinstance(reason, str):
        return reason
    return None


def governance_allow(event: Mapping[str, Any]) -> bool | None:
    governance = event.get("governance")
    if isinstance(governance, Mapping):
        decision = governance.get("decision")
        if decision == "allow":
            return True
        if decision == "deny":
            return False
    allow = event.get("allow")
    if isinstance(allow, bool):
        return allow
    return None


def is_success_event(event: Mapping[str, Any]) -> bool:
    if event.get("event_type") == "run_END" and event.get("terminal_outcome") == "SUCCESS":
        return True
    termination_reason = event.get("termination_reason")
    if termination_reason in {"commit_success", "success", "completed", "done"}:
        return True
    if event.get("status") == "success":
        return True
    if event.get("capability_status") == "success":
        return True
    return False


def success_events(ctx: TestExecutionContext) -> List[Mapping[str, Any]]:
    return [payload_of(event) for event in ctx.events if is_success_event(payload_of(event))]


def make_case(
    *,
    pack: str,
    test_id: str,
    name: str,
    objective: str,
    required_event_types: Sequence[str],
    checker: Callable[[TestExecutionContext], CaseOutcome],
) -> TestCase:
    required = list(required_event_types)

    def _run(ctx: TestExecutionContext) -> TestResult:
        observed = event_types_present(ctx)
        violations = validate_required_fields(ctx.events, required)
        if violations:
            first = violations[0]
            signature = f"missing_telemetry:{first.get('code', 'unknown')}"
            return TestResult(
                test_id=test_id,
                name=name,
                pack=pack,
                profile=ctx.profile,
                mode=ctx.mode,
                passed=False,
                fail_signature=signature,
                required_events=required,
                observed_events=observed,
                evidence_refs=[],
                timings=None,
                details={"violations": violations},
            )

        step_violations = validate_step_atomicity(ctx.events, require_step_commit=False)
        if step_violations:
            first = step_violations[0]
            signature = f"invalid_step_atomicity:{first.get('code', 'unknown')}"
            return TestResult(
                test_id=test_id,
                name=name,
                pack=pack,
                profile=ctx.profile,
                mode=ctx.mode,
                passed=False,
                fail_signature=signature,
                required_events=required,
                observed_events=observed,
                evidence_refs=[],
                timings=None,
                details={"step_violations": step_violations},
            )

        try:
            outcome = checker(ctx)
        except Exception as exc:
            return TestResult(
                test_id=test_id,
                name=name,
                pack=pack,
                profile=ctx.profile,
                mode=ctx.mode,
                passed=False,
                fail_signature="internal_error",
                required_events=required,
                observed_events=observed,
                evidence_refs=[],
                timings=None,
                details={"exception": str(exc)},
            )

        return TestResult(
            test_id=test_id,
            name=name,
            pack=pack,
            profile=ctx.profile,
            mode=ctx.mode,
            passed=outcome.passed,
            fail_signature=outcome.fail_signature,
            required_events=required,
            observed_events=observed,
            evidence_refs=sorted(set(outcome.evidence_refs)),
            timings=None,
            details=outcome.details,
        )

    return TestCase(
        id=test_id,
        name=name,
        pack=pack,
        objective=objective,
        required_event_types=required,
        run=_run,
    )
