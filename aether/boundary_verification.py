"""Default-off Solver boundary-verification research projection.

This module never decides whether a task is complete and never supplies a
reviewer-authored repair strategy.  It only makes an existing unresolved
completion finding salient to Primary at the point where Primary chooses its
next action.
"""
from __future__ import annotations

from typing import Any, Mapping


CONTROL = "control"
BOUNDARY_VERIFICATION_V1 = "boundary_verification_v1"
SUPPORTED_MODES = frozenset({CONTROL, BOUNDARY_VERIFICATION_V1})

_GUIDANCE = (
    "A completion claim still has unresolved evidence. Before requesting completion again, "
    "decide whether the current evidence could look successful while the exact raw-task "
    "requirement is still false. If so, choose one practical observation at the actual "
    "requested behavior boundary whose possible outcomes would discriminate that failure. "
    "You choose the possible failure, the check, the interpretation, and the next action. "
    "Do not treat the independent-review claim as truth; the raw task and observed reality "
    "remain authoritative. If no additional check is warranted, proceed according to your judgment."
)


def project_boundary_verification_checkpoint(
    packet: Mapping[str, Any], *, mode: str = CONTROL,
) -> Mapping[str, Any]:
    """Add a neutral completion-boundary checkpoint only when explicitly enabled.

    Control is object-identical.  Treatment is mechanically triggered only by
    an already-present open completion finding.  No finding summary, repair
    instruction, hypothesis, or task-specific strategy is copied into the new
    section; those semantics remain with Primary and the raw task.
    """
    selected = str(mode or CONTROL).strip().lower()
    if selected not in SUPPORTED_MODES:
        raise ValueError(f"unsupported boundary verification mode: {mode}")
    if selected == CONTROL:
        return packet

    raw_findings = packet.get("open_completion_findings")
    if not isinstance(raw_findings, list) or not raw_findings:
        return packet

    finding_ids: list[str] = []
    currentness: dict[str, str] = {}
    for index, raw in enumerate(raw_findings):
        if not isinstance(raw, Mapping):
            continue
        finding_id = str(raw.get("finding_id") or f"finding-{index + 1}").strip()
        if not finding_id:
            continue
        finding_ids.append(finding_id)
        value = str(raw.get("currentness") or "").strip()
        if value:
            currentness[finding_id] = value

    if not finding_ids:
        return packet

    out = dict(packet)
    checkpoint: dict[str, Any] = {
        "schema_version": "aether.boundary_verification_checkpoint.v1",
        "trigger": "open_completion_finding_present",
        "unresolved_finding_ids": finding_ids,
        "semantic_authority": "primary_solver_against_raw_task_and_observed_reality",
        "review_claim_authority": "advisory_not_truth",
        "guidance": _GUIDANCE,
    }
    if currentness:
        checkpoint["finding_currentness"] = currentness
    out["completion_boundary_checkpoint"] = checkpoint
    return out


__all__ = [
    "BOUNDARY_VERIFICATION_V1",
    "CONTROL",
    "SUPPORTED_MODES",
    "project_boundary_verification_checkpoint",
]
