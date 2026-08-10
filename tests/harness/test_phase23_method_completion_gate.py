from __future__ import annotations

from types import SimpleNamespace

from aether.architect_v2_adapter import adapt_architect_v2_to_runtime
from aether.architect_v2_canary import build_neutral_canary_baseline
from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger, Receipt
from aether.proof_contract import evaluate_compiled_proof_requirements
from aether.verifier import CompletionEvidenceEntry
from aether.verifier_inspector import VerifierInspectionRequest
from aether.verifier_recovery import (
    CompiledEvidenceRequirement,
    EvidenceClass,
    validate_compiled_evidence,
)
from aether.verify_completion_gates import _completion_record_problem
from aether.verify_completion_protocol import verify_with_inspector
from aether.verify_inspection_requests import _default_completion_inspection_requests


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Use `worker.py` to create `done.txt`.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file")
            ),
            "shell": CapabilityDescriptor(
                "shell", "commands", tool_names=("run_command",)
            ),
            "managed_process": CapabilityDescriptor(
                "managed_process", "processes", tool_names=("launch_process",)
            ),
        },
    )


def _payload() -> dict:
    return {
        "schema_version": "aether_architect.v2",
        "method_constraints": [{
            "constraint_id": "use_worker",
            "statement": "Use `worker.py` to produce done.txt.",
            "verbatim_anchors": ["worker.py"],
            "obligation_refs": ["deliver"],
            "acceptance_observation": "Immutable action history shows worker.py was launched.",
            "falsification_observation": "Immutable action history shows a different implementation or no compliant launch.",
        }],
        "task_contract": {
            "exact_facts": [
                {"fact_id": "artifact", "statement": "Create `done.txt`.", "source": "task_prompt", "verbatim_anchors": ["done.txt"]},
            ],
            "obligations": [{"obligation_id": "deliver", "statement": "Create done.txt.", "fact_refs": ["artifact"]}],
        },
        "verifier_design": {"mission": "Verify the artifact.", "verification_strategy": "Inspect current state."},
        "proof_intent": [{
            "proof_id": "file", "obligation_refs": ["deliver"], "risk_refs": [],
            "proof_kind": "exact_state", "acceptance_observation": "done.txt exists.",
            "falsification_observation": "done.txt is absent.",
        }],
        "solver_design": {
            "mission": "Create the artifact.",
            "strategy": "Use the required method and inspect the result.",
        },
    }


def _compiled():
    env = _env()
    adapted = adapt_architect_v2_to_runtime(
        _payload(), baseline=build_neutral_canary_baseline(env), envmap=env
    )
    return ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(
        adapted.runtime_ir, env
    )


def _entry(*, inspection_ref: str) -> CompletionEvidenceEntry:
    return CompletionEvidenceEntry(
        requirement="Use worker.py.", observed="The action history shows worker.py.",
        falsification_check="No different implementation was launched.",
        inspection_refs=(inspection_ref,), clause_ids=("use_worker",),
        proof_ids=(), evidence_class="exact_contract", risk_refs=(),
    )


def test_compiler_emits_method_requirement_without_v1_semantic_mirrors() -> None:
    compiled = _compiled()
    requirements = compiled.config_realization["compiled_evidence_requirements"]
    assert requirements == [{
        "clause_id": "use_worker",
        "minimum_class": "exact_contract",
        "inspection_route": "inspect_action_receipts",
        "fallback_route": None,
        "falsification_check": "Immutable action history shows a different implementation or no compliant launch.",
        "allowed_route_kinds": ["inspect_action_receipts"],
    }]
    assert compiled.config_realization["method_evidence_status"] == "compiled"
    assert compiled.task_contract.as_payload()["method_constraints"][0]["constraint_id"] == "use_worker"


def test_method_clause_requires_action_history_route() -> None:
    requirement = CompiledEvidenceRequirement(
        "use_worker", EvidenceClass.EXACT_CONTRACT, ("inspect_action_receipts",)
    )
    wrong = validate_compiled_evidence(
        (_entry(inspection_ref="file-read"),), requirements=(requirement,),
        known_inspection_ids=("file-read",),
        inspection_ceilings={"file-read": "exact_contract"},
        inspection_routes={"file-read": "read_file"},
    )
    assert any(error.code == "wrong_evidence_route" for error in wrong)
    correct = validate_compiled_evidence(
        (_entry(inspection_ref="history"),), requirements=(requirement,),
        known_inspection_ids=("history",),
        inspection_ceilings={"history": "exact_contract"},
        inspection_routes={"history": "inspect_action_receipts"},
    )
    assert correct == ()


def test_default_completion_inspection_requests_action_history_for_methods() -> None:
    compiled = _compiled()
    packet = {
        "task_contract": compiled.task_contract.as_payload(),
        "dynamic_state": {"files": {"done.txt": {"exists": True}}},
    }
    requests = _default_completion_inspection_requests(packet)
    method = next(row for row in requests if row.kind == "inspect_action_receipts")
    assert method.clause_ids == ("use_worker",)
    assert method.limit == 64
    assert any(row.kind == "read_file" for row in requests)


class _StopAfterCorrection:
    def __init__(self, first: str) -> None:
        self.first = first
        self.calls = 0
        self.last_parse_errors: list[str] = []

    def call_verifier(self, _messages, *, max_output_tokens: int) -> str:
        del max_output_tokens
        self.calls += 1
        if self.calls == 1:
            return self.first
        raise RuntimeError("stop-after-protocol-correction")


def _assert_rejected_before_inspection(first: str, expected_error: str) -> None:
    hooks = _StopAfterCorrection(first)
    inspections = 0

    def inspector(_requests):
        nonlocal inspections
        inspections += 1
        return []

    try:
        verify_with_inspector(
            hooks,
            {"task_contract": _compiled().task_contract.as_payload()},
            _compiled(),
            ExecutionLedger(),
            inspector,
        )
    except RuntimeError as exc:
        assert str(exc) == "stop-after-protocol-correction"
    else:
        raise AssertionError("expected correction boundary to stop the test")
    assert inspections == 0
    assert any(expected_error in item for item in hooks.last_parse_errors)


def test_unknown_method_clause_is_rejected_before_inspection() -> None:
    _assert_rejected_before_inspection(
        '{"kind":"inspect","requests":[{"request_id":"history",'
        '"kind":"inspect_action_receipts","clause_ids":["invented_method"]}]}',
        "unknown method clause_ids=invented_method",
    )


def test_action_history_cannot_bind_outcome_proof_ids() -> None:
    _assert_rejected_before_inspection(
        '{"kind":"inspect","requests":[{"request_id":"history",'
        '"kind":"inspect_action_receipts","clause_ids":["use_worker"],'
        '"proof_ids":["file"]}]}',
        "inspect_action_receipts cannot bind outcome proof_ids",
    )


def test_failed_action_history_cannot_satisfy_method_completion() -> None:
    problem = _completion_record_problem(
        SimpleNamespace(completion_evidence=(_entry(inspection_ref="history"),)),
        set(),
        packet={
            "compiled_evidence_requirements": [{
                "clause_id": "use_worker",
                "minimum_class": "exact_contract",
                "allowed_route_kinds": ["inspect_action_receipts"],
            }],
        },
        inspection_ceilings={"history": "exact_contract"},
        inspection_routes={"history": "inspect_action_receipts"},
    )
    assert "do not match any inspection performed this round" in problem
    assert "unknown inspection IDs" in problem


def test_action_history_route_is_rejected_for_outcome_proof_admission() -> None:
    compiled = _compiled()
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="launch", step=1, kind="process_launch", success=True,
        summary="launched worker", state_change=True,
        payload={
            "command": "python3 worker.py", "service_name": "worker",
            "process_id": "process:worker", "live": True,
        },
    ))
    request = VerifierInspectionRequest(
        request_id="history", kind="inspect_action_receipts",
        clause_ids=("use_worker",), proof_ids=("file",),
    )
    result = {
        "request_id": "history", "kind": "inspect_action_receipts",
        "rows": [{"receipt_id": "launch", "success": True}],
        "success": True, "error": "", "method_evidence_only": True,
        "observation_origin": "ledger_action_history", "read_only": True,
    }
    enriched = register_inspection_results(
        (request,), (result,), ledger=ledger, step=2,
        requester="model_verifier", executor=SimpleNamespace(), overlay=None,
        packet_signature="packet",
        proof_contract_identity=compiled.proof_requirements_identity,
    )
    decision = evaluate_compiled_proof_requirements(
        compiled.proof_requirements,
        ledger,
        {"file": (enriched[0]["inspection_id"],)},
        packet_signature="packet",
        proof_contract_identity=compiled.proof_requirements_identity,
    )[0]
    assert decision.admitted is False
    assert decision.code == "proof_evidence_not_admitted"
