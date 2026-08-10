from __future__ import annotations

import copy

import pytest

from aether.architect_v2_adapter import adapt_architect_v2_to_runtime
from aether.architect_v2_canary import (
    build_neutral_canary_baseline,
    score_architect_v2_candidate,
)
from aether.architect_v2_contract import validate_architect_v2
from aether.architect_v2_model import build_architect_v2_model_request
from aether.model_hooks import ModelOutputError
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.task_contract import MethodConstraint


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Use `worker.py` to create `done.txt`.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file")
            ),
            "managed_process": CapabilityDescriptor(
                "managed_process", "processes", tool_names=("launch_process",)
            ),
        },
    )


def _payload() -> dict:
    return {
        "schema_version": "aether_architect.v2",
        "task_contract": {
            "exact_facts": [{
                "fact_id": "artifact",
                "statement": "The required artifact is `done.txt`.",
                "source": "task_prompt",
                "verbatim_anchors": ["done.txt"],
            }],
            "obligations": [{
                "obligation_id": "deliver",
                "statement": "Create done.txt with the required result.",
                "fact_refs": ["artifact"],
            }],
        },
        "method_constraints": [{
            "constraint_id": "use_worker",
            "statement": "Use `worker.py` to produce the artifact.",
            "verbatim_anchors": ["worker.py"],
            "obligation_refs": ["deliver"],
            "acceptance_observation": (
                "Immutable action history shows the required worker implementation was used."
            ),
            "falsification_observation": (
                "Immutable action history shows a different implementation or no compliant launch."
            ),
        }],
        "verifier_design": {
            "mission": "Verify the final artifact and formal method clause.",
            "verification_strategy": (
                "Inspect current artifact state and immutable action history separately."
            ),
        },
        "proof_intent": [{
            "proof_id": "artifact_state",
            "obligation_refs": ["deliver"],
            "risk_refs": [],
            "proof_kind": "exact_state",
            "acceptance_observation": "Current done.txt has the required result.",
            "falsification_observation": "A missing or wrong artifact falsifies completion.",
        }],
        "solver_design": {
            "mission": "Create the required artifact.",
            "strategy": "Follow the formal method clause and inspect the result.",
            "task_specific_rules": [{
                "rule_id": "inspect_after_write",
                "statement": "Inspect the artifact before submission.",
            }],
        },
    }


def test_method_anchor_cannot_enter_outcome_obligation() -> None:
    raw = _payload()
    raw["task_contract"]["obligations"][0]["statement"] = (
        "Use worker.py and create done.txt."
    )
    with pytest.raises(ModelOutputError, match="method-only exact anchors"):
        validate_architect_v2(raw)


@pytest.mark.parametrize(
    ("mutate", "pattern"),
    [
        (
            lambda raw: raw["proof_intent"][0].update(
                acceptance_observation="worker.py created done.txt."
            ),
            "acceptance_observation repeats method-only exact anchors",
        ),
        (
            lambda raw: raw["proof_intent"][0].update(
                falsification_observation="worker.py was not used."
            ),
            "falsification_observation repeats method-only exact anchors",
        ),
        (
            lambda raw: raw.update(
                verifier_design={
                    "mission": "Verify output.",
                    "verification_strategy": "Inspect current state.",
                    "false_positive_risks": [{
                        "risk_id": "wrong_method",
                        "statement": "A different implementation than worker.py could pass.",
                        "obligation_refs": ["deliver"],
                    }],
                },
                proof_intent=[{
                    "proof_id": "artifact_state",
                    "obligation_refs": ["deliver"],
                    "risk_refs": ["wrong_method"],
                    "proof_kind": "exact_state",
                    "acceptance_observation": "Current done.txt has the required result.",
                    "falsification_observation": "A missing artifact falsifies completion.",
                }],
            ),
            "false_positive_risks\\[0\\].statement repeats method-only exact anchors",
        ),
    ],
)
def test_method_anchor_is_excluded_from_outcome_proof_and_risk(
    mutate, pattern: str
) -> None:
    raw = _payload()
    mutate(raw)
    with pytest.raises(ModelOutputError, match=pattern):
        validate_architect_v2(raw)


def test_method_clause_requires_self_contained_authority_and_evidence() -> None:
    for missing, pattern in (
        ("verbatim_anchors", "verbatim_anchors must contain at least 1"),
        ("obligation_refs", "obligation_refs must contain at least 1"),
        ("acceptance_observation", "acceptance_observation must be a non-empty"),
        ("falsification_observation", "falsification_observation must be a non-empty"),
    ):
        raw = _payload()
        raw["method_constraints"][0][missing] = [] if missing.endswith("refs") or missing == "verbatim_anchors" else ""
        with pytest.raises(ModelOutputError, match=pattern):
            validate_architect_v2(raw)


def test_method_anchor_is_independent_of_method_statement_wording() -> None:
    raw = _payload()
    raw["method_constraints"][0]["statement"] = "Use the required implementation."
    contract = validate_architect_v2(raw)
    assert contract.payload["method_constraints"][0]["verbatim_anchors"] == [
        "worker.py"
    ]


def test_same_anchor_may_be_owned_by_both_lanes_explicitly() -> None:
    raw = _payload()
    raw["task_contract"]["exact_facts"].append({
        "fact_id": "worker_identity",
        "statement": "The final recorded identity is `worker.py`.",
        "source": "task_prompt",
        "verbatim_anchors": ["worker.py"],
    })
    raw["task_contract"]["obligations"][0]["fact_refs"].append("worker_identity")
    raw["task_contract"]["obligations"][0]["statement"] = (
        "Create done.txt and preserve worker.py as the final recorded identity."
    )
    raw["proof_intent"][0]["acceptance_observation"] = (
        "done.txt exists and the recorded identity is worker.py."
    )
    assert validate_architect_v2(raw)


def test_scorer_preserves_anchor_ownership_and_method_authority() -> None:
    reference = _payload()
    env = _env()
    request = build_architect_v2_model_request(env)

    omitted = copy.deepcopy(reference)
    omitted["method_constraints"] = []
    score = score_architect_v2_candidate(
        omitted, reference=reference, request=request, envmap=env
    )
    assert score.checks["reference_fact_authority_preserved"] is False
    assert score.checks["reference_required_methods_preserved"] is False

    renamed = copy.deepcopy(reference)
    renamed["method_constraints"][0]["constraint_id"] = "managed_worker"
    renamed["method_constraints"][0]["statement"] = (
        "Launch `worker.py` through an equivalent compliant execution method."
    )
    score = score_architect_v2_candidate(
        renamed, reference=reference, request=request, envmap=env
    )
    assert score.checks["reference_fact_authority_preserved"] is True
    assert score.checks["reference_required_methods_preserved"] is True


def test_method_anchor_span_refinement_is_allowed_but_unrelated_spans_fail() -> None:
    reference = _payload()
    env = _env()
    request = build_architect_v2_model_request(env)

    broader = copy.deepcopy(reference)
    broader["method_constraints"][0]["statement"] = "Use the required implementation."
    broader["method_constraints"][0]["verbatim_anchors"] = ["Use `worker.py`"]
    score = score_architect_v2_candidate(
        broader, reference=reference, request=request, envmap=env
    )
    assert score.checks["candidate_anchors_grounded"] is True
    assert score.checks["reference_fact_authority_preserved"] is True
    assert score.checks["reference_required_methods_preserved"] is True

    unrelated = copy.deepcopy(reference)
    unrelated["method_constraints"][0]["statement"] = "Use the visible artifact detail."
    unrelated["method_constraints"][0]["verbatim_anchors"] = ["done.txt"]
    score = score_architect_v2_candidate(
        unrelated, reference=reference, request=request, envmap=env
    )
    assert score.checks["candidate_anchors_grounded"] is True
    assert score.checks["reference_required_methods_preserved"] is False


def test_ungrounded_method_anchor_fails_canary_grounding() -> None:
    reference = _payload()
    candidate = copy.deepcopy(reference)
    candidate["method_constraints"][0]["statement"] = "Use the hidden implementation."
    candidate["method_constraints"][0]["verbatim_anchors"] = ["secret.py"]
    env = _env()
    score = score_architect_v2_candidate(
        candidate,
        reference=reference,
        request=build_architect_v2_model_request(env),
        envmap=env,
    )
    assert score.checks["candidate_anchors_grounded"] is False


def test_scorer_rejects_invented_method_on_negative_control() -> None:
    reference = _payload()
    reference["method_constraints"] = []
    candidate = copy.deepcopy(reference)
    candidate["method_constraints"] = _payload()["method_constraints"]
    env = _env()
    score = score_architect_v2_candidate(
        candidate,
        reference=reference,
        request=build_architect_v2_model_request(env),
        envmap=env,
    )
    assert score.checks["reference_required_methods_preserved"] is False


def test_adapter_preserves_complete_method_clause() -> None:
    env = _env()
    contract = validate_architect_v2(_payload())
    adapted = adapt_architect_v2_to_runtime(
        contract, baseline=build_neutral_canary_baseline(env), envmap=env
    )
    method = adapted.task_contract.method_constraints[0]
    assert method == MethodConstraint(
        "use_worker",
        "Use `worker.py` to produce the artifact.",
        ("deliver",),
        (),
        ("worker.py",),
        "Immutable action history shows the required worker implementation was used.",
        "Immutable action history shows a different implementation or no compliant launch.",
    )
    assert "[Architect v2 required methods]" in adapted.runtime_ir.solver_identity_prompt
    dispositions = {
        row["path"]: row["owner"]
        for row in adapted.realization_manifest["field_dispositions"]
    }
    assert dispositions["method_constraints[0].acceptance_observation"] == (
        "structured_method_constraint"
    )
