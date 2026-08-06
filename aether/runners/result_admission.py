"""Fail-closed admission of runner records into performance analysis."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RunAdmissionDecision:
    run_valid: bool
    performance_row_admitted: bool
    grader_status: str
    process_leak: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_run_admission(
    *,
    source_identity: Mapping[str, Any],
    provider_valid: bool,
    protocol_valid: bool,
    grader_error: str | None,
    reward_source: str,
    task_package_sha256_start: str,
    task_package_sha256_grader: str,
    runtime_image_sha256_expected: str,
    runtime_image_sha256_container: str,
    teardown_verified_absent: bool,
    evidence_surfaces_clean: bool = True,
) -> RunAdmissionDecision:
    """Return whether one completed run may enter performance summaries.

    Official reward may be either pass or fail; admission concerns whether the
    measurement is trustworthy. A failed task with valid custody remains a
    valid performance row. Missing/stale grading, dirty source, protocol or
    provider failure, hidden-surface contamination, and unverified teardown do
    not.
    """
    reasons: list[str] = []
    if source_identity.get("clean") is not True:
        reasons.append("source_identity_not_clean")
    if provider_valid is not True:
        reasons.append("provider_invalid")
    if protocol_valid is not True:
        reasons.append("protocol_invalid")
    if grader_error is not None:
        reasons.append("grader_invalid")
    if reward_source not in {"reward_txt", "official_run_tests_exit_code"}:
        reasons.append("grader_reward_source_invalid")
    if not task_package_sha256_start or not task_package_sha256_grader:
        reasons.append("task_package_identity_missing")
    elif task_package_sha256_start != task_package_sha256_grader:
        reasons.append("grader_task_package_stale")
    if not runtime_image_sha256_expected or not runtime_image_sha256_container:
        reasons.append("runtime_image_identity_missing")
    elif runtime_image_sha256_expected != runtime_image_sha256_container:
        reasons.append("runtime_image_identity_mismatch")
    if evidence_surfaces_clean is not True:
        reasons.append("agent_visible_hidden_surface")
    process_leak = teardown_verified_absent is not True
    if process_leak:
        reasons.append("container_teardown_unverified")

    if grader_error is not None or "grader_reward_source_invalid" in reasons:
        grader_status = "invalid"
    elif "grader_task_package_stale" in reasons:
        grader_status = "stale"
    else:
        grader_status = "valid"
    valid = not reasons
    return RunAdmissionDecision(
        run_valid=valid,
        performance_row_admitted=valid,
        grader_status=grader_status,
        process_leak=process_leak,
        reasons=tuple(reasons),
    )
