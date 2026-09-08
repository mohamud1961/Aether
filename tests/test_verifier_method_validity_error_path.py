from __future__ import annotations

import json

import pytest

from aether.model_hooks import ModelHooks, ModelOutputError
from aether.pcr_runtime import build_pcr_runtime
from aether.runtime_ir import CapabilityDescriptor, EnvMap


def _compiled():
    envmap = EnvMap(
        task_prompt="check output",
        workspace_root="/app",
        visible_files=("x.txt",),
        capabilities={
            "shell": CapabilityDescriptor(capability_id="shell", summary="run commands"),
            "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="read files"),
        },
    )
    resolved = build_pcr_runtime(envmap)
    assert resolved.compiled is not None
    return resolved.compiled


def _finding() -> dict[str, object]:
    return {
        "finding_id": "f1",
        "verdict": "needs_repair",
        "priority": "high",
        "summary": "bad",
        "evidence": ["bad"],
        "supporting_inspection_ids": ["inspection:test:d1"],
        "repair_instruction": "fix",
        "applies_to": ["x.txt"],
        "required_evidence_route": "behavioral",
    }


def test_exhausted_invalid_method_validity_fails_closed_without_runtime_typeerror() -> None:
    responses = [
        json.dumps({
            "kind": "inspect",
            "requests": [{"request_id": "r1", "kind": "read_file", "path": "x.txt"}],
        }),
        json.dumps({
            "kind": "inspect",
            "requests": [{
                "request_id": "d1",
                "kind": "overlay_run_command",
                "verification_plan": {
                    "claim": "derive",
                    "authoritative_source_refs": ["inspection:test:r1"],
                    "authoritative_structure": "x",
                    "method_summary": "check",
                    "proxy_risk": "none",
                },
                "execution": {"kind": "overlay_run_command", "command": "cat x.txt"},
            }],
        }),
        json.dumps({
            "verdict": "needs_repair",
            "confidence": "high",
            "summary": "repair",
            "findings": [_finding()],
            "method_validity": {"observed_structure": "x"},
        }),
        json.dumps({
            "verdict": "needs_repair",
            "confidence": "high",
            "summary": "repair",
            "findings": [_finding()],
            "method_validity": {
                "observed_structure": "x",
                "executed_rule": "cat",
                "method_alignment": "direct",
                "authoritative_source_refs": ["inspection:test:r1"],
                "execution_ref": "inspection:wrong",
            },
        }),
    ]
    calls = 0

    def verifier_model(messages, *, max_output_tokens=12000):
        del messages, max_output_tokens
        nonlocal calls
        response = responses[min(calls, len(responses) - 1)]
        calls += 1
        return response

    def inspector(requests):
        rows = []
        for request in requests:
            rows.append({
                "request_id": request.request_id,
                "inspection_id": f"inspection:test:{request.request_id}",
                "kind": request.kind,
                "path": request.path,
                "eligible_for_proof": True,
                "eligible_for_basis": True,
                "actual_evidence_class": "exact_contract",
                "evidence_ceiling": "exact_contract",
                "observation_valid": True,
                "error": "",
                "success": True,
                "excerpt": "hello" if request.kind == "read_file" else "",
                "stdout": "hello" if request.kind == "overlay_run_command" else "",
                "exit_code": 0 if request.kind == "overlay_run_command" else None,
            })
        return rows

    hooks = ModelHooks(lambda *_args, **_kwargs: "{}", verifier_model)
    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()

    with pytest.raises(ModelOutputError, match="invalid derived execution authority"):
        hooks.verify_with_inspector(
            {"reason": "solver_submit", "task_prompt": "check output", "artifacts_present": ["x.txt"]},
            _compiled(),
            ledger=ledger,
            inspector=inspector,
        )
    assert calls == 4
