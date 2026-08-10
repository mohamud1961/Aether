from __future__ import annotations

import copy

import pytest

from aether.architect_v2_adapter import adapt_architect_v2_to_runtime
from aether.architect_v2_canary import (
    build_neutral_canary_baseline,
    score_architect_v2_candidate,
)
from aether.architect_v2_contract import validate_architect_v2
from aether.architect_v2_model import (
    ARCHITECT_V2_SYSTEM_PROMPT,
    build_architect_v2_model_request,
)
from aether.model_hooks import ModelOutputError
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.task_contract import MethodConstraint, TaskClause, TaskContract, TaskFact


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
            "statement": "Use `worker.py` to produce done.txt.",
            "verbatim_anchors": ["worker.py"],
            "obligation_refs": ["deliver"],
            "acceptance_observation": (
                "Immutable action history shows the required implementation was launched."
            ),
            "falsification_observation": (
                "Immutable action history shows a substitute or no compliant launch."
            ),
        }],
        "verifier_design": {
            "mission": "Verify the final artifact and required method.",
            "verification_strategy": (
                "Inspect current artifact state and immutable action history."
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
            "strategy": "Follow the formal method constraint and inspect the result.",
            "task_specific_rules": [{
                "rule_id": "inspect_result",
                "statement": "Inspect the artifact before submission.",
            }],
        },
    }


def test_required_method_becomes_immutable_task_authority() -> None:
    env = _env()
    contract = validate_architect_v2(_payload())
    adapted = adapt_architect_v2_to_runtime(
        contract, baseline=build_neutral_canary_baseline(env), envmap=env
    )
    method = adapted.task_contract.method_constraints[0]
    assert method.constraint_id == "use_worker"
    assert method.verbatim_anchors == ("worker.py",)
    assert method.acceptance_observation.startswith("Immutable action history")
    assert method.falsification_observation.startswith("Immutable action history")
    payload = adapted.task_contract.as_payload()
    assert payload["method_constraints"][0]["constraint_id"] == "use_worker"
    assert payload["method_constraints"][0]["verbatim_anchors"] == ["worker.py"]
    assert adapted.realization_manifest["structured_method_constraint_count"] == 1


def test_advisory_rule_stays_out_of_formal_task_authority() -> None:
    env = _env()
    raw = _payload()
    raw["method_constraints"] = []
    raw["solver_design"]["task_specific_rules"] = [{
        "rule_id": "worker_hint",
        "statement": "Consider worker.py as a useful starting point.",
    }]
    contract = validate_architect_v2(raw)
    adapted = adapt_architect_v2_to_runtime(
        contract, baseline=build_neutral_canary_baseline(env), envmap=env
    )
    assert adapted.task_contract.method_constraints == ()
    assert "worker.py as a useful starting point" in (
        adapted.runtime_ir.solver_identity_prompt
    )


def test_method_constraint_requires_complete_fields() -> None:
    cases = (
        ("verbatim_anchors", [], "at least 1"),
        ("obligation_refs", [], "at least 1"),
        ("acceptance_observation", "", "non-empty string"),
        ("falsification_observation", "", "non-empty string"),
    )
    for field, value, pattern in cases:
        raw = _payload()
        raw["method_constraints"][0][field] = value
        with pytest.raises(ModelOutputError, match=pattern):
            validate_architect_v2(raw)


def test_task_specific_rules_cannot_smuggle_formal_authority() -> None:
    raw = _payload()
    raw["solver_design"]["task_specific_rules"][0]["authority"] = (
        "required_method"
    )
    with pytest.raises(ModelOutputError, match="unsupported fields"):
        validate_architect_v2(raw)


def test_runtime_method_constraint_preserves_legacy_fact_refs_compatibility() -> None:
    fact = TaskFact(
        "f", "Use worker.py", "task_prompt", ("worker.py",), "method"
    )
    clause = TaskClause("o", "Create result", (), ())
    method = MethodConstraint(
        "m", "Use worker.py", ("o",), ("f",),
        ("worker.py",), "Action history shows compliance.",
        "Action history shows noncompliance.",
    )
    contract = TaskContract.create(
        "prompt", (clause,), facts=(fact,), method_constraints=(method,)
    )
    assert contract.method_constraints == (method,)


def test_runtime_method_anchor_need_not_repeat_in_statement() -> None:
    method = MethodConstraint(
        "method", "Use the required implementation.", ("deliver",), (),
        ("worker.py",), "Action history establishes compliance.",
        "Action history establishes noncompliance.",
    )
    assert method.verbatim_anchors == ("worker.py",)


def test_prompt_describes_self_contained_method_authority() -> None:
    prompt = ARCHITECT_V2_SYSTEM_PROMPT
    assert "method_constraints: the only formal method authority" in prompt
    assert "different method must count as failure" in prompt
    assert "verbatim_anchors" in prompt
    assert "acceptance_observation/falsification_observation" in prompt
    assert "task_specific_rules are advisory-only" in prompt
    assert "Method counterexamples belong in the method falsification field" in prompt


def test_scorer_requires_method_authority_but_allows_renaming() -> None:
    reference = _payload()
    env = _env()
    request = build_architect_v2_model_request(env)

    omitted = copy.deepcopy(reference)
    omitted["method_constraints"] = []
    missing = score_architect_v2_candidate(
        omitted, reference=reference, request=request, envmap=env
    )
    assert missing.passed is False
    assert missing.checks["reference_required_methods_preserved"] is False

    renamed = copy.deepcopy(reference)
    method = renamed["method_constraints"][0]
    method["constraint_id"] = "managed_worker_method"
    method["statement"] = "Launch `worker.py` using an equivalent compliant method."
    preserved = score_architect_v2_candidate(
        renamed, reference=reference, request=request, envmap=env
    )
    assert preserved.checks["reference_required_methods_preserved"] is True


def test_scorer_rejects_method_bound_to_unrelated_outcome() -> None:
    reference = _payload()
    candidate = copy.deepcopy(reference)
    candidate["task_contract"]["exact_facts"].append({
        "fact_id": "other",
        "statement": "A separate artifact is `other.txt`.",
        "source": "task_prompt",
        "verbatim_anchors": ["other.txt"],
    })
    candidate["task_contract"]["obligations"].append({
        "obligation_id": "other_outcome",
        "statement": "Create other.txt.",
        "fact_refs": ["other"],
    })
    candidate["proof_intent"].append({
        "proof_id": "other_state",
        "obligation_refs": ["other_outcome"],
        "risk_refs": [],
        "proof_kind": "exact_state",
        "acceptance_observation": "Current other.txt exists.",
        "falsification_observation": "A missing other.txt falsifies that outcome.",
    })
    candidate["method_constraints"][0]["obligation_refs"] = ["other_outcome"]
    env = EnvMap(
        task_prompt="Use `worker.py` to create `done.txt` and `other.txt`.",
        workspace_root="/app",
        capabilities=_env().capabilities,
    )
    score = score_architect_v2_candidate(
        candidate,
        reference=reference,
        request=build_architect_v2_model_request(env),
        envmap=env,
    )
    assert score.checks["reference_required_methods_preserved"] is False


def test_scorer_rejects_invented_method_when_reference_has_none() -> None:
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
