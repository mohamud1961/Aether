from __future__ import annotations

from aether.providers.azure_model import _PCR_VERIFIER_DIRECT_TURN_SCHEMA
from aether.verifier import SOLVER_REPAIR_VERDICTS, parse_model_verifier_result
from aether.verifier_recovery import EvidenceClass
from aether.verify_completion_protocol import (
    _solver_repair_is_fully_directly_grounded,
    _verdict_admissibility_problem,
)


def _repair_result(*, verdict: str = "incomplete_state_wrong", required: str = "independent_semantic", ref: str = "inspection:process"):
    return parse_model_verifier_result({
        "verdict": verdict,
        "confidence": 0.98,
        "summary": "current state is wrong",
        "findings": [{
            "finding_id": "git_deployment_not_observed",
            "verdict": "violated",
            "priority": "high",
            "summary": "repository and deployment were not observed",
            "evidence": ["process probe returned zero matches"],
            "supporting_inspection_ids": [ref],
            "repair_instruction": "repair the deployment",
            "applies_to": ["raw_task"],
            "required_evidence_route": required,
        }],
        "method_validity": None,
    })


def test_solver_repair_preserves_factual_finding_when_declared_strength_is_overstated() -> None:
    result = _repair_result()
    assert _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:process"},
        derived_refs=set(),
        actual_classes={"inspection:process": "metadata_proxy"},
    ) == ""


def test_every_solver_repair_verdict_uses_same_direct_grounding_rule() -> None:
    for verdict in SOLVER_REPAIR_VERDICTS:
        result = _repair_result(verdict=verdict, required="metadata_proxy")
        assert _solver_repair_is_fully_directly_grounded(
            result, {"inspection:process"}
        ) is True
        assert _solver_repair_is_fully_directly_grounded(result, set()) is False


def test_solver_repair_finding_accepts_cited_strength_at_or_above_declared_requirement() -> None:
    result = _repair_result(required="behavioral", ref="inspection:http")
    assert _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:http"},
        derived_refs=set(),
        actual_classes={"inspection:http": "behavioral"},
    ) == ""


def test_thin_completed_cannot_claim_behavioral_strength_from_metadata_proxy() -> None:
    result = parse_model_verifier_result({
        "verdict": "completed",
        "confidence": "high",
        "summary": "complete",
        "findings": [],
        "missing_evidence_requests": [],
        "completion_evidence": [{
            "requirement": "service works",
            "observed": "process metadata exists",
            "falsification_check": "look for process",
            "inspection_refs": ["inspection:process"],
            "clause_ids": ["raw_task"],
            "proof_ids": [],
            "evidence_class": "behavioral",
            "risk_refs": [],
            "requirement_status": "satisfied",
        }],
        "method_validity": None,
    })
    problem = _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:process"},
        derived_refs=set(),
        actual_classes={"inspection:process": "metadata_proxy"},
    )
    assert "completion_evidence[0] cites evidence below required evidence class behavioral" in problem
    assert "metadata_proxy" in problem


def test_pcr_provider_repair_strength_is_constrained_to_existing_evidence_classes() -> None:
    field = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["finding"]["properties"]["required_evidence_route"]
    assert field["type"] == "string"
    assert set(field["enum"]) == {item.value for item in EvidenceClass}



def test_solver_repair_mixed_current_refs_preserve_negative_finding_despite_strength_label() -> None:
    result = parse_model_verifier_result({
        "verdict": "incomplete_state_wrong",
        "confidence": "high",
        "summary": "repair required",
        "findings": [{
            "finding_id": "mixed-strength-repair",
            "verdict": "violated",
            "priority": "high",
            "summary": "mixed evidence",
            "evidence": ["weak process metadata plus unrelated HTTP behavior"],
            "supporting_inspection_ids": ["inspection:process", "inspection:http"],
            "repair_instruction": "repair state",
            "applies_to": ["raw_task"],
            "required_evidence_route": "behavioral",
        }],
        "method_validity": None,
    })
    assert _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:process", "inspection:http"},
        derived_refs=set(),
        actual_classes={
            "inspection:process": "metadata_proxy",
            "inspection:http": "behavioral",
        },
    ) == ""


def test_completed_mixed_refs_cannot_launder_weak_ref_with_strong_ref() -> None:
    result = parse_model_verifier_result({
        "verdict": "completed",
        "confidence": "high",
        "summary": "complete",
        "findings": [],
        "missing_evidence_requests": [],
        "completion_evidence": [{
            "requirement": "service works and configuration is correct",
            "observed": "mixed metadata and behavioral observations",
            "falsification_check": "mixed check",
            "inspection_refs": ["inspection:hook", "inspection:http"],
            "clause_ids": ["raw_task"],
            "proof_ids": [],
            "evidence_class": "behavioral",
            "risk_refs": [],
            "requirement_status": "satisfied",
        }],
        "method_validity": None,
    })
    problem = _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:hook", "inspection:http"},
        derived_refs=set(),
        actual_classes={
            "inspection:hook": "metadata_proxy",
            "inspection:http": "behavioral",
        },
    )
    assert "completion_evidence[0]" in problem
    assert "inspection:hook" in problem
    assert "metadata_proxy" in problem
    assert "below required evidence class behavioral" in problem


def test_mixed_refs_are_valid_when_every_ref_reaches_declared_strength() -> None:
    result = parse_model_verifier_result({
        "verdict": "completed",
        "confidence": "high",
        "summary": "complete",
        "findings": [],
        "missing_evidence_requests": [],
        "completion_evidence": [{
            "requirement": "two behavioral observations",
            "observed": "both behavioral",
            "falsification_check": "two independent live checks",
            "inspection_refs": ["inspection:http-a", "inspection:http-b"],
            "clause_ids": ["raw_task"],
            "proof_ids": [],
            "evidence_class": "behavioral",
            "risk_refs": [],
            "requirement_status": "satisfied",
        }],
        "method_validity": None,
    })
    assert _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:http-a", "inspection:http-b"},
        derived_refs=set(),
        actual_classes={
            "inspection:http-a": "behavioral",
            "inspection:http-b": "exact_contract",
        },
    ) == ""


def test_mixed_refs_may_combine_when_declared_strength_is_no_higher_than_weakest_ref() -> None:
    result = parse_model_verifier_result({
        "verdict": "incomplete_state_wrong",
        "confidence": "high",
        "summary": "repair required",
        "findings": [{
            "finding_id": "mixed-low-strength",
            "verdict": "violated",
            "priority": "high",
            "summary": "mixed evidence",
            "evidence": ["metadata plus behavior"],
            "supporting_inspection_ids": ["inspection:process", "inspection:http"],
            "repair_instruction": "repair state",
            "applies_to": ["raw_task"],
            "required_evidence_route": "metadata_proxy",
        }],
        "method_validity": None,
    })
    assert _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:process", "inspection:http"},
        derived_refs=set(),
        actual_classes={
            "inspection:process": "metadata_proxy",
            "inspection:http": "behavioral",
        },
    ) == ""


def test_solver_repair_cannot_use_dns_limited_http_probe_as_admissible_negative() -> None:
    result = _repair_result(required="metadata_proxy", ref="inspection:http-dns")
    problem = _verdict_admissibility_problem(
        result,
        direct_refs=set(),
        derived_refs=set(),
        actual_classes={"inspection:http-dns": "metadata_proxy"},
    )
    assert "http-dns" in problem
    assert "non-admissible evidence" in problem or "no current admissible evidence" in problem
