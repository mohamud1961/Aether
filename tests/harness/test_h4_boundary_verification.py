from __future__ import annotations

from copy import deepcopy

import pytest

from aether.boundary_verification import (
    BOUNDARY_VERIFICATION_V1,
    CONTROL,
    project_boundary_verification_checkpoint,
)
from aether.harbor_runtime import (
    H4_BOUNDARY_VERIFICATION_ARM,
    H4_BOUNDARY_VERIFICATION_ARM_ENV,
    H4_CONTROL_ARM,
    build_selected_frontier_models,
    selected_h4_boundary_verification_mode,
)
from aether.kernel import AetherNextKernel


def _packet() -> dict[str, object]:
    return {
        "budgets": {"remaining_run_sec": 120.0},
        "latest_primary_result": {"kind": "run_command", "success": True},
        "open_completion_findings": [
            {
                "finding_id": "F1",
                "state": "unproven",
                "currentness": "current_candidate",
                "review_claim_summary": "central requirement is not established",
                # Deliberately include strategy-like fields to prove the new
                # checkpoint itself never copies them.
                "repair_instruction": "perform a task-specific magic test",
                "required_evidence_route": "invented_route",
            }
        ],
    }


def test_h4_control_is_exact_object_identity_even_with_open_finding() -> None:
    packet = _packet()
    assert project_boundary_verification_checkpoint(packet, mode=CONTROL) is packet
    assert "completion_boundary_checkpoint" not in packet


def test_h4_treatment_is_noop_without_open_finding() -> None:
    packet = {"budgets": {"remaining_run_sec": 120.0}, "open_completion_findings": []}
    assert (
        project_boundary_verification_checkpoint(
            packet, mode=BOUNDARY_VERIFICATION_V1,
        )
        is packet
    )


def test_h4_checkpoint_adds_only_neutral_salience_not_repair_strategy() -> None:
    packet = _packet()
    before = deepcopy(packet)
    projected = project_boundary_verification_checkpoint(
        packet, mode=BOUNDARY_VERIFICATION_V1,
    )
    assert packet == before
    assert projected is not packet
    checkpoint = projected["completion_boundary_checkpoint"]
    assert checkpoint["schema_version"] == "aether.boundary_verification_checkpoint.v1"
    assert checkpoint["trigger"] == "open_completion_finding_present"
    assert checkpoint["unresolved_finding_ids"] == ["F1"]
    assert checkpoint["finding_currentness"] == {"F1": "current_candidate"}
    assert checkpoint["semantic_authority"] == "primary_solver_against_raw_task_and_observed_reality"
    assert checkpoint["review_claim_authority"] == "advisory_not_truth"
    rendered = str(checkpoint).lower()
    assert "magic test" not in rendered
    assert "invented_route" not in rendered
    assert "review_claim_summary" not in checkpoint
    assert "repair_instruction" not in checkpoint
    assert "required_evidence_route" not in checkpoint
    assert "you choose" in checkpoint["guidance"].lower()
    assert "raw task" in checkpoint["guidance"].lower()


def test_h4_selector_is_default_off_scoped_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(H4_BOUNDARY_VERIFICATION_ARM_ENV, raising=False)
    assert selected_h4_boundary_verification_mode(build_selected_frontier_models) == H4_CONTROL_ARM

    monkeypatch.setenv(H4_BOUNDARY_VERIFICATION_ARM_ENV, H4_BOUNDARY_VERIFICATION_ARM)
    assert (
        selected_h4_boundary_verification_mode(build_selected_frontier_models)
        == H4_BOUNDARY_VERIFICATION_ARM
    )
    # Offline/custom model factories can never accidentally activate the live
    # research arm from ambient environment state.
    assert selected_h4_boundary_verification_mode(object()) == H4_CONTROL_ARM

    monkeypatch.setenv(H4_BOUNDARY_VERIFICATION_ARM_ENV, "invent_strategy")
    with pytest.raises(RuntimeError, match=H4_BOUNDARY_VERIFICATION_ARM_ENV):
        selected_h4_boundary_verification_mode(build_selected_frontier_models)


def test_kernel_rejects_unknown_boundary_verification_mode() -> None:
    with pytest.raises(ValueError, match="unsupported boundary verification mode"):
        AetherNextKernel(boundary_verification_mode="invent_strategy")
