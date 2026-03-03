from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.events import validate_hash_chain
from ._common import events_of, fail_case, make_case, pass_case, success_events


PACK = "determinism"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _h1_replay_decision_divergence_zero(ctx: TestExecutionContext):
    replay_end = _events(ctx, "REPLAY_END")
    if not replay_end:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_replay_events")

    latest = replay_end[-1]
    if latest.get("pass") is False:
        return fail_case("replay_pass_false")
    divergence = latest.get("divergence_rate")
    if divergence is not None and float(divergence) != 0.0:
        return fail_case("replay_divergence_nonzero", divergence_rate=float(divergence))
    return pass_case(divergence_rate=float(divergence or 0.0))


def _h2_hash_chain_integrity_validates(ctx: TestExecutionContext):
    ok, first_bad = validate_hash_chain(ctx.events)
    if not ok:
        return fail_case("hash_chain_invalid", first_bad_event_id=first_bad)
    return pass_case()


def _h3_tamper_fuzz_fail_closed(ctx: TestExecutionContext):
    checks = _events(ctx, "LOG_INTEGRITY_CHECK")
    if not checks:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_integrity_checks")

    tamper_detected = any(event.get("pass") is False for event in checks)
    if not tamper_detected:
        return pass_case()

    if success_events(ctx):
        return fail_case("success_after_tamper_detected")

    return pass_case(tamper_events=len([event for event in checks if event.get("pass") is False]))


def _h4_evidence_access_logging(ctx: TestExecutionContext):
    reads = _events(ctx, "EVIDENCE_READ")
    if not reads:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_evidence_reads")

    for event in reads:
        for field in ("actor_id", "actor_role", "object_type", "object_id"):
            if event.get(field) in (None, ""):
                return fail_case("evidence_read_missing_field", field=field)

    return pass_case(evidence_reads=len(reads))


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="H1", name="Replay divergence 0%", objective="Replay decision surface divergence is zero.", required_event_types=["run_END"], checker=_h1_replay_decision_divergence_zero),
        make_case(pack=PACK, test_id="H2", name="Hash-chain integrity", objective="Hash-chain integrity validates for all runs.", required_event_types=["run_END"], checker=_h2_hash_chain_integrity_validates),
        make_case(pack=PACK, test_id="H3", name="Tamper fuzz fail-closed", objective="Mutations and corruption fail closed with classification.", required_event_types=["run_END"], checker=_h3_tamper_fuzz_fail_closed),
        make_case(pack=PACK, test_id="H4", name="Evidence access logging", objective="Evidence retrieval paths emit EVIDENCE_READ with roles.", required_event_types=["run_END"], checker=_h4_evidence_access_logging),
    ]
