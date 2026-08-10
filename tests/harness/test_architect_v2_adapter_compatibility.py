from __future__ import annotations

import copy
import json

import pytest

from aether.architect_v2_contract import (
    ArchitectV2CompatibilityError,
    ArchitectV2ProofSeam,
    assert_current_runtime_compatibility_is_ready,
    bind_architect_v2_proof_seam,
    project_architect_v2_shadow,
    validate_architect_v2,
)
from aether.proof_contract import PROOF_KINDS, proof_requirements_identity
from aether.model_hooks import ModelOutputError


def _payload(*, proof_kind: str = "public_behavior") -> dict[str, object]:
    return {
        "schema_version": "aether_architect.v2",
        "method_constraints": [],
        "task_contract": {
            "exact_facts": [{
                "fact_id": "fact_interface",
                "statement": "The visible interface exposes val.",
                "source": "task_prompt",
                    "verbatim_anchors": ["val"],
            }],
            "obligations": [
                {
                    "obligation_id": "obligation_a",
                    "statement": "The interface returns the required value.",
                    "fact_refs": ["fact_interface"],
                },
                {
                    "obligation_id": "obligation_b",
                    "statement": "The result preserves the required type.",
                    "fact_refs": ["fact_interface"],
                },
            ],
        },
        "proof_intent": [{
            "proof_id": "proof_interface_behavior",
            "obligation_refs": ["obligation_a", "obligation_b"],
            "proof_kind": proof_kind,
            "acceptance_observation": "One independent observation establishes both obligations.",
            "falsification_observation": "A mismatched observed value or type disproves the group.",
        }],
        "solver_design": {
            "mission": "Build the requested result.",
            "strategy": "Inspect current state, act incrementally, and adapt.",
        },
        "verifier_design": {
            "mission": "Determine whether every obligation is satisfied.",
            "verification_strategy": "Use the strongest eligible independent observation.",
        },
    }


def test_v2_proof_intent_binds_to_existing_kernel_type_and_identity() -> None:
    seam = bind_architect_v2_proof_seam(_payload())

    assert isinstance(seam, ArchitectV2ProofSeam)
    assert seam.status == "shadow_only"
    assert seam.requirements[0].proof_id == "proof_interface_behavior"
    assert seam.requirements[0].obligation_ids == ("obligation_a", "obligation_b")
    assert seam.requirements_identity == proof_requirements_identity(seam.requirements)
    assert seam.as_dict()["activation"] == "not_runtime_eligible"


@pytest.mark.parametrize("proof_kind", PROOF_KINDS)
def test_every_v2_proof_kind_uses_the_same_canonical_seam(proof_kind: str) -> None:
    seam = bind_architect_v2_proof_seam(_payload(proof_kind=proof_kind))
    assert seam.requirements[0].proof_kind == proof_kind
    assert "route_kinds" not in seam.requirements[0].as_dict()


def test_binding_accepts_a_prevalidated_contract_without_reparsing_or_mutating() -> None:
    payload = _payload()
    before = copy.deepcopy(payload)
    contract = validate_architect_v2(payload)

    seam = bind_architect_v2_proof_seam(contract)

    assert seam.contract is contract
    assert payload == before


def test_v2_validation_still_fails_before_binding_for_unknown_proof_kind() -> None:
    payload = _payload(proof_kind="not_a_kernel_kind")
    with pytest.raises(ModelOutputError, match="proof_kind must be one of"):
        bind_architect_v2_proof_seam(payload)


def test_binding_wraps_kernel_compilation_failure_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = validate_architect_v2(_payload())

    def fail_compile(_rows):
        raise ValueError("synthetic kernel seam failure")

    monkeypatch.setattr(
        "aether.architect_v2_contract.compile_proof_requirements",
        fail_compile,
    )
    with pytest.raises(ArchitectV2CompatibilityError, match="synthetic kernel seam failure"):
        bind_architect_v2_proof_seam(contract)


def test_shadow_binding_does_not_unlock_production_activation() -> None:
    seam = bind_architect_v2_proof_seam(_payload())
    assert seam.status == "shadow_only"
    with pytest.raises(ArchitectV2CompatibilityError, match="production dispatch remains blocked"):
        assert_current_runtime_compatibility_is_ready()


def test_shadow_projection_preserves_facts_anchors_and_emphasis_losslessly() -> None:
    payload = _payload()
    payload["task_contract"]["exact_facts"].append({  # type: ignore[index]
        "fact_id": "fact_anchor",
        "statement": "The response field is named value, not val.",
        "source": "visible_material",
                    "verbatim_anchors": ["value", "val"],
    })
    payload["information_emphasis"] = [{  # type: ignore[index]
        "topic": "exact response spelling",
        "rationale": "The names are easy to confuse.",
        "fact_refs": ["fact_anchor"],
    }]

    projection = project_architect_v2_shadow(payload)
    material = json.loads(projection.task_material)

    assert material["exact_facts"] == payload["task_contract"]["exact_facts"]
    assert material["obligations"] == payload["task_contract"]["obligations"]
    assert "information_emphasis" not in material
    assert "exact response spelling" in projection.solver_prompt
    assert "visible_contract is intentionally unused" in projection.deferred_projections[0]
    assert projection.status == "shadow_only"


def test_shadow_projection_does_not_repeat_task_contract_in_role_prompts() -> None:
    projection = project_architect_v2_shadow(_payload())
    obligation_statement = _payload()["task_contract"]["obligations"][0]["statement"]  # type: ignore[index]

    assert obligation_statement not in projection.solver_prompt
    assert obligation_statement not in projection.verifier_prompt
    assert "Mission: Build the requested result." in projection.solver_prompt
    assert "Strategy: Inspect current state, act incrementally, and adapt." in projection.solver_prompt
    assert "Mission: Determine whether every obligation is satisfied." in projection.verifier_prompt


def test_shadow_projection_renders_all_declared_role_design_fields() -> None:
    payload = _payload()
    payload["solver_design"] = {  # type: ignore[index]
        "mission": "Build the requested result.",
        "strategy": "Inspect first and adapt.",
        "priorities": ["Preserve exact identifiers."],
        "task_specific_rules": [{
            "rule_id": "rule_a",
            "statement": "Check the public interface.",
        }],
        "failure_response": "Repair only from the observed failure.",
        "self_verification_emphasis": ["Use an independent observation."],
        "completion_emphasis": ["Submit only after current evidence."],
    }
    payload["proof_intent"][0]["risk_refs"] = ["risk_a"]  # type: ignore[index]
    payload["verifier_design"] = {  # type: ignore[index]
        "mission": "Judge the result.",
        "verification_strategy": "Inspect current state directly.",
        "falsification_priorities": ["Reject stale evidence."],
        "false_positive_risks": [{
            "risk_id": "risk_a",
            "statement": "A label may repeat the expected value.",
            "obligation_refs": ["obligation_a"],
        }],
        "completion_emphasis": ["Return all material findings."],
    }

    projection = project_architect_v2_shadow(payload)

    for expected in (
        "Preserve exact identifiers.",
        "rule_a: Check the public interface.",
        "Repair only from the observed failure.",
        "Use an independent observation.",
        "Submit only after current evidence.",
    ):
        assert expected in projection.solver_prompt
    for expected in (
        "Reject stale evidence.",
        "Return all material findings.",
    ):
        assert expected in projection.verifier_prompt
    assert "A label may repeat the expected value." not in projection.verifier_prompt


def test_shadow_projection_is_input_immutable_and_has_no_runtime_activation() -> None:
    payload = _payload()
    before = copy.deepcopy(payload)

    projection = project_architect_v2_shadow(payload)

    assert payload == before
    assert projection.as_dict()["activation"] == "not_runtime_eligible"
