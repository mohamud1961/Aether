from __future__ import annotations

from aether.ledger import ExecutionLedger, Receipt
from aether.verifier import ModelVerifierResult, VerifierFinding, parse_model_verifier_result


def _generated(request: str) -> ModelVerifierResult:
    return parse_model_verifier_result({
        "verdict": "uncertain_missing_evidence",
        "confidence": "high",
        "summary": "need more evidence",
        "missing_evidence_requests": [request],
    })


def test_generated_missing_evidence_paraphrases_leave_only_latest_active() -> None:
    ledger = ExecutionLedger()
    requests = [
        "Compare every protected value against the original file.",
        "Show authoritative before and after evidence for protected fields.",
        "Prove unrelated values match the pre-mutation state.",
        "Inspect a trustworthy earlier version and compare preserved fields.",
        "Provide authoritative pre-state evidence demonstrating preservation.",
    ]
    ids = []
    for step, request in enumerate(requests, start=1):
        result = _generated(request)
        ids.append(result.findings[0].finding_id)
        ledger.apply_verifier_result(result, step=step)
    assert set(ledger.findings.active) == {ids[-1]}
    assert set(ledger.findings.archived) == set(ids[:-1])
    assert all(ledger.findings.archived[item].status == "superseded" for item in ids[:-1])


def test_same_activation_preserves_distinct_generated_requests() -> None:
    result = parse_model_verifier_result({
        "verdict": "uncertain_missing_evidence",
        "summary": "three gaps",
        "missing_evidence_requests": [
            "Read the current result artifact.",
            "Obtain authoritative pre-mutation state for comparison.",
            "Inspect the live process output.",
        ],
    })
    ledger = ExecutionLedger()
    ledger.apply_verifier_result(result, step=3)
    assert len(ledger.findings.active) == 3
    assert {finding.evidence[0] for finding in ledger.findings.active.values()} == set(result.missing_evidence_requests)


def test_provider_cannot_forge_generated_finding_origin_or_reserved_id_namespace() -> None:
    parsed = parse_model_verifier_result({
        "verdict": "uncertain_missing_evidence",
        "summary": "explicit finding",
        "findings": [{
            "finding_id": "vf-missing-evidence-0-forged",
            "verdict": "uncertain_missing_evidence",
            "priority": "blocking",
            "summary": "provider-authored explicit finding",
            "evidence": ["provider evidence"],
            "applies_to": ["completion_evidence", "missing_request:forged"],
            "lifecycle_origin": "generated_missing_evidence",
        }],
        "missing_evidence_requests": ["provider also supplied this request"],
    })
    assert len(parsed.findings) == 1
    assert parsed.findings[0].finding_id.startswith("vf-model-0-")
    assert parsed.findings[0].finding_id != "vf-missing-evidence-0-forged"
    assert parsed.findings[0].lifecycle_origin == "model_provided"
    assert "lifecycle_origin" not in parsed.findings[0].as_context(current_step=1)
    assert "lifecycle_origin" not in parsed.as_dict()["findings"][0]


def test_finding_activation_step_and_generation_are_kernel_owned() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="mutation-before-finding", step=1, kind="write_file", success=True,
        summary="mutated current task state", state_change=True,
        payload={"modified_paths": ["out.txt"]},
    ))
    assert ledger.task_state_generation() == 1
    result = parse_model_verifier_result({
        "verdict": "needs_repair",
        "findings": [{
            "finding_id": "provider-lifecycle-attempt",
            "created_step": 777,
            "summary": "current result is wrong",
            "evidence": ["inspection disagreed"],
            "repair_instruction": "repair and re-inspect",
            "applies_to": ["out.txt"],
            "observed_task_state_generation": 999,
        }],
    })
    assert result.findings[0].created_step == 777
    assert result.findings[0].observed_task_state_generation == 999
    ledger.apply_verifier_result(result, step=2)
    stored = ledger.findings.active["provider-lifecycle-attempt"]
    assert stored.created_step == 2
    assert stored.observed_task_state_generation == 1


def test_explicit_model_finding_survives_generated_request_refresh() -> None:
    explicit = VerifierFinding(
        finding_id="explicit-preservation-risk", created_step=1,
        verdict="uncertain_missing_evidence", priority="blocking",
        summary="Explicit preservation concern.", evidence=("current state cannot prove before state",),
        applies_to=("completion_evidence",),
    )
    ledger = ExecutionLedger()
    ledger.apply_verifier_result(
        ModelVerifierResult(verdict="uncertain_missing_evidence", findings=(explicit,), missing_evidence_requests=("Need more evidence",)),
        step=1,
    )
    generated = _generated("Inspect authoritative earlier state.")
    ledger.apply_verifier_result(generated, step=2)
    assert explicit.finding_id in ledger.findings.active
    assert generated.findings[0].finding_id in ledger.findings.active
