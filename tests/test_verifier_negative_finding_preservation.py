from __future__ import annotations

import json

from aether.model_hooks import ModelHooks
from aether.pcr_runtime import build_pcr_runtime
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.verifier import parse_model_verifier_result


def _compiled():
    envmap = EnvMap(
        task_prompt="Generate primers satisfying the requested cloning contract.",
        workspace_root="/app",
        visible_files=("primers.fasta",),
        capabilities={
            "shell": CapabilityDescriptor(capability_id="shell", summary="run commands"),
            "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="read files"),
        },
    )
    resolved = build_pcr_runtime(envmap)
    assert resolved.compiled is not None
    return resolved.compiled


def test_negative_finding_survives_overstated_evidence_class() -> None:
    inspect = json.dumps({
        "kind": "inspect",
        "summary": "Inspect the current primer artifact.",
        "requests": [{"request_id": "probe-1", "kind": "read_file", "path": "primers.fasta"}],
    })
    finding = json.dumps({
        "verdict": "needs_repair",
        "confidence": "high",
        "summary": "The current candidate violates the clamp requirement.",
        "findings": [{
            "finding_id": "bsa1-5prime-clamp-missing",
            "verdict": "needs_repair",
            "priority": "blocking",
            "summary": "Every primer begins with GGTCTC and has no 5-prime clamp.",
            "evidence": ["current primer output begins with the BsaI site at position zero"],
            "supporting_inspection_ids": ["inspection:test:probe-1"],
            "repair_instruction": "add a clamp and re-verify",
            "applies_to": ["primers.fasta"],
            "required_evidence_route": "independent_semantic",
        }],
        "method_validity": None,
    })
    responses = [inspect, finding]
    calls: list[list[dict[str, str]]] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        calls.append(list(messages))
        return responses[min(len(calls) - 1, len(responses) - 1)]

    def inspector(requests):
        return [{
            "request_id": req.request_id,
            "inspection_id": f"inspection:test:{req.request_id}",
            "kind": req.kind,
            "path": req.path,
            "excerpt": "every primer begins GGTCTC; no upstream clamp is present",
            "eligible_for_proof": True,
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "exact_contract",
        } for req in requests]

    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )
    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()
    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Generate primers", "artifacts_present": ["primers.fasta"]},
        _compiled(),
        ledger=ledger,
        inspector=inspector,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "needs_repair"
    assert [row.finding_id for row in parsed.findings] == ["bsa1-5prime-clamp-missing"]
    assert parsed.findings[0].supporting_inspection_ids == ("inspection:test:probe-1",)
    assert parsed.findings[0].required_evidence_route == "independent_semantic"
    assert len(calls) == 2
