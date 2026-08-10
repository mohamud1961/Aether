from __future__ import annotations

import copy

import pytest

from aether.architect_v2_canary import score_architect_v2_candidate
from aether.architect_v2_model import build_architect_v2_model_request
from aether.architect_v2_contract import (
    architect_v2_provider_schema,
    bind_architect_v2_proof_seam,
    validate_architect_v2,
)
from aether.model_hooks import ModelOutputError
from aether.runtime_ir import CapabilityDescriptor, EnvMap


def _payload() -> dict:
    return {
        "schema_version": "aether_architect.v2",
        "method_constraints": [],
        "task_contract": {
            "exact_facts": [{
                "fact_id": "f1",
                "statement": "Use `server.py` and return `ok`.",
                "source": "task_prompt",
                    "verbatim_anchors": ["server.py", "ok"],
            }],
            "obligations": [{
                "obligation_id": "o1",
                "statement": "The required server implementation returns ok.",
                "fact_refs": ["f1"],
            }],
        },
        "verifier_design": {
            "mission": "Independently verify the required implementation and behavior.",
            "verification_strategy": "Falsify identity and behavior separately.",
            "false_positive_risks": [{
                "risk_id": "wrong_process",
                "statement": "A different process could return ok.",
                "obligation_refs": ["o1"],
            }],
        },
        "proof_intent": [
            {
                "proof_id": "p_state",
                "obligation_refs": ["o1"],
                "risk_refs": ["wrong_process"],
                "proof_kind": "exact_state",
                "acceptance_observation": "The active implementation is server.py.",
                "falsification_observation": "A different active implementation falsifies identity.",
            },
            {
                "proof_id": "p_behavior",
                "obligation_refs": ["o1"],
                "risk_refs": [],
                "proof_kind": "public_behavior",
                "acceptance_observation": "A fresh public request returns ok.",
                "falsification_observation": "A failed request or different response falsifies behavior.",
            },
        ],
        "solver_design": {
            "mission": "Implement the required server.",
            "strategy": "Repair from observed state and test the public behavior.",
        },
    }


def test_declared_risk_requires_formal_proof_coverage() -> None:
    raw = _payload()
    raw["proof_intent"][0]["risk_refs"] = []
    with pytest.raises(ModelOutputError, match="does not formally close"):
        validate_architect_v2(raw)


def test_unknown_duplicate_and_unbound_risk_refs_fail_closed() -> None:
    unknown = _payload()
    unknown["proof_intent"][0]["risk_refs"] = ["unknown"]
    with pytest.raises(ModelOutputError, match="unknown references"):
        validate_architect_v2(unknown)

    duplicate = _payload()
    duplicate["proof_intent"][0]["risk_refs"] = ["wrong_process", "wrong_process"]
    with pytest.raises(ModelOutputError, match="must be unique"):
        validate_architect_v2(duplicate)

    unbound = _payload()
    unbound["task_contract"]["obligations"].append({
        "obligation_id": "o2", "statement": "A separate artifact exists.", "fact_refs": ["f1"]
    })
    unbound["proof_intent"][0]["obligation_refs"] = ["o2"]
    with pytest.raises(ModelOutputError, match="share no obligation_refs"):
        validate_architect_v2(unbound)


def test_compiled_proof_requirement_preserves_risk_ids_and_identity() -> None:
    contract = validate_architect_v2(_payload())
    seam = bind_architect_v2_proof_seam(contract)
    assert seam.requirements[0].risk_ids == ("wrong_process",)
    assert seam.requirements[1].risk_ids == ()
    assert seam.as_dict()["proof_requirements"][0]["risk_ids"] == ["wrong_process"]


def test_no_declared_risks_allows_empty_or_omitted_refs() -> None:
    raw = _payload()
    raw["verifier_design"].pop("false_positive_risks")
    raw["proof_intent"][0].pop("risk_refs")
    contract = validate_architect_v2(raw)
    assert contract.proof_ids == ("p_state", "p_behavior")


def test_provider_schema_generates_verifier_risks_before_proof_intent() -> None:
    schema = architect_v2_provider_schema()
    order = list(schema["properties"])
    assert order.index("verifier_design") < order.index("proof_intent")
    proof = schema["properties"]["proof_intent"]["items"]
    assert "risk_refs" in proof["required"]
    assert "risk_refs" in proof["properties"]


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Use `server.py` and return `ok`.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file")
            ),
            "shell": CapabilityDescriptor(
                "shell", "commands", tool_names=("run_command",)
            ),
        },
    )


def test_scorer_requires_reference_risk_authority_but_allows_renaming() -> None:
    reference = _payload()
    no_risks = copy.deepcopy(reference)
    no_risks["verifier_design"].pop("false_positive_risks")
    for proof in no_risks["proof_intent"]:
        proof["risk_refs"] = []
    env = _env()
    request = build_architect_v2_model_request(env)
    missing = score_architect_v2_candidate(
        no_risks,
        reference=reference,
        request=request,
        envmap=env,
    )
    assert missing.passed is False
    assert missing.checks["reference_risk_authority_preserved"] is False

    renamed = copy.deepcopy(reference)
    renamed["verifier_design"]["false_positive_risks"][0] = {
        "risk_id": "alternate_identity_risk",
        "statement": "A coincidental responder could satisfy the public check.",
        "obligation_refs": ["o1"],
    }
    renamed["proof_intent"][0]["risk_refs"] = ["alternate_identity_risk"]
    preserved = score_architect_v2_candidate(
        renamed,
        reference=reference,
        request=request,
        envmap=env,
    )
    assert preserved.checks["reference_risk_authority_preserved"] is True


def test_scorer_rejects_weaker_risk_closure_kind() -> None:
    reference = _payload()
    candidate = copy.deepcopy(reference)
    candidate["proof_intent"][0]["proof_kind"] = "public_behavior"
    env = _env()
    score = score_architect_v2_candidate(
        candidate,
        reference=reference,
        request=build_architect_v2_model_request(env),
        envmap=env,
    )
    assert score.checks["reference_risk_authority_preserved"] is False
