"""Adversarial closure tests for inspection identity and proof freshness."""
from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace

from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger, Receipt
from aether.proof_contract import (
    CertifiedProofClause,
    evaluate_proof_contract,
    record_clause_evidence,
    record_verifier_result_evidence,
)
from aether.verifier import CompletionEvidenceEntry, ModelVerifierResult
from aether.verifier_inspector import VerifierInspectionRequest
from aether.verifier_recovery import (
    CompiledEvidenceRequirement,
    EvidenceClass,
    validate_compiled_evidence,
)


class _Executor:
    pass


def _clause(route: str = "read_file:out.txt") -> CertifiedProofClause:
    return CertifiedProofClause(
        clause_id="result",
        requirement="out.txt contains the exact result",
        solver_handling="write exact result",
        verifier_route=route,
        fallback_route="",
        falsification_check="a different current value disproves the clause",
        required_evidence_class="exact_contract",
        route_kind=route.split(":", 1)[0],
        route_evidence_ceiling="exact_contract",
        requires_independent_evidence=True,
    )


def test_registry_binds_actual_route_target_generation_tool_hash_and_ceiling() -> None:
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(
        request_id="read-current",
        kind="read_file",
        path="out.txt",
    )
    rows = register_inspection_results(
        (request,),
        ({
            "request_id": "read-current",
            "kind": "read_file",
            "path": "out.txt",
            "content_hash": "abc123",
            "excerpt": "42",
            "read_only": True,
        },),
        ledger=ledger,
        step=3,
        requester="model_verifier",
        executor=_Executor(),
        overlay=None,
        packet_signature="packet-generation-3",
    )

    row = rows[0]
    inspection_id = row["inspection_id"]
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection_id)
    assert receipt.kind == "inspection_record"
    assert receipt.payload["route"] == "read_file:out.txt"
    assert receipt.payload["target_identity"] == "path:out.txt"
    assert receipt.payload["target_generation"] == "content_hash:abc123"
    assert receipt.payload["task_state_generation"] == 0
    assert receipt.payload["tool_identity"].endswith(":task_executor")
    assert receipt.payload["result_hash"]
    assert receipt.payload["evidence_ceiling"] == "exact_contract"
    assert row["eligible_for_proof"] is True


def test_overlay_registry_route_binds_exact_executed_command() -> None:
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(
        request_id="client",
        kind="overlay_run_command",
        command="python3 independent_client.py",
    )
    rows = register_inspection_results(
        (request,),
        ({
            "request_id": "client",
            "kind": "overlay_run_command",
            "command": "python3 independent_client.py",
            "exit_code": 0,
            "stdout": "ok",
            "executed_in": "verifier_overlay",
        },),
        ledger=ledger,
        step=1,
        requester="model_verifier",
        executor=_Executor(),
        overlay=_Executor(),
        packet_signature="packet",
    )
    expected = sha256(b"python3 independent_client.py").hexdigest()[:16]
    assert rows[0]["registered_route"] == f"overlay_run_command:command_sha256:{expected}"
    receipt = next(item for item in ledger.all_receipts() if item.kind == "inspection_record")
    assert receipt.payload["route_parameters"]["command"] == "python3 independent_client.py"
    assert rows[0]["target_identity"] == "target:opaque"
    assert rows[0]["observation_type"] == "execution_result"
    assert rows[0]["admissibility"] == "exploratory"


def test_typed_probe_identity_comes_from_observed_normalized_result() -> None:
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(
        request_id="port", kind="probe_port", target="localhost:5328",
    )
    rows = register_inspection_results(
        (request,),
        ({
            "request_id": "port", "kind": "probe_port",
            "host": "127.0.0.1", "port": 5328, "state": "open",
        },),
        ledger=ledger, step=1, requester="model_verifier",
        executor=_Executor(), overlay=None, packet_signature="packet",
    )
    assert rows[0]["target_identity"] == "socket:127.0.0.1:5328"
    assert rows[0]["canonical_targets"] == ["socket:127.0.0.1:5328"]
    assert rows[0]["admissibility"] == "direct_admissible"
    assert rows[0]["eligible_for_proof"] is True


def test_free_form_probe_target_without_normalized_result_remains_opaque() -> None:
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(
        request_id="port", kind="probe_port", target="claimed-host:5328",
    )
    rows = register_inspection_results(
        (request,),
        ({
            "request_id": "port", "kind": "probe_port",
            "state": "unknown",
        },),
        ledger=ledger, step=1, requester="model_verifier",
        executor=_Executor(), overlay=None, packet_signature="packet",
    )
    assert rows[0]["target_identity"] == "target:opaque"
    assert rows[0]["canonical_targets"] == []


def test_unclassified_inspection_route_cannot_become_proof() -> None:
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(request_id="unknown", kind="unknown_route")
    rows = register_inspection_results(
        (request,),
        ({"request_id": "unknown", "kind": "unknown_route", "value": "x"},),
        ledger=ledger,
        step=0,
        requester="model_verifier",
        executor=_Executor(),
        overlay=None,
        packet_signature="packet",
    )
    assert rows[0]["evidence_ceiling"] == ""
    assert rows[0]["eligible_for_proof"] is False


def test_missing_inspection_ceiling_fails_closed() -> None:
    evidence = (SimpleNamespace(
        inspection_refs=("inspection:1",),
        clause_ids=("result",),
        evidence_class="exact_contract",
        falsification_check="different result",
    ),)
    errors = validate_compiled_evidence(
        evidence,
        requirements=(CompiledEvidenceRequirement("result", EvidenceClass.EXACT_CONTRACT),),
        known_inspection_ids=("inspection:1",),
        inspection_ceilings={},
    )
    assert any(error.code == "missing_inspection_ceiling" for error in errors)


def test_current_proof_becomes_stale_after_any_task_mutation() -> None:
    ledger = ExecutionLedger()
    clause = _clause()
    record_clause_evidence(
        ledger,
        receipt_id="proof:0",
        step=0,
        clause_id="result",
        route="read_file:out.txt",
        evidence_class="exact_contract",
        provenance="verifier_inspection",
        supports_clause=True,
        observation="current out.txt is 42",
        inspection_ids=("inspection:0",),
    )
    assert evaluate_proof_contract((clause,), ledger)[0].satisfied is True

    ledger.record(Receipt(
        receipt_id="mutation:1",
        step=1,
        kind="write_file",
        success=True,
        summary="rewrote out.txt",
        state_change=True,
        payload={"modified_paths": ["out.txt"]},
    ))

    decision = evaluate_proof_contract((clause,), ledger)[0]
    assert decision.satisfied is False
    assert decision.code == "stale_clause_evidence"
    assert "current generation=1" in decision.detail


def test_control_plane_receipts_do_not_invalidate_current_proof() -> None:
    ledger = ExecutionLedger()
    clause = _clause()
    record_clause_evidence(
        ledger,
        receipt_id="proof:0",
        step=0,
        clause_id="result",
        route="read_file:out.txt",
        evidence_class="exact_contract",
        provenance="verifier_inspection",
        supports_clause=True,
        observation="current out.txt is 42",
    )
    ledger.record(Receipt(
        receipt_id="solver-decision:1",
        step=1,
        kind="solver_decision_state",
        success=True,
        summary="model authored a control-plane decision",
        state_change=True,
    ))
    assert ledger.task_state_generation() == 0
    assert evaluate_proof_contract((clause,), ledger)[0].satisfied is True


def test_proof_bridge_cannot_substitute_compiler_route_for_actual_inspection() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="inspection:port",
        step=2,
        kind="inspection_record",
        success=True,
        summary="port is open",
        payload={
            "inspection_id": "inspection:port",
            "route_kind": "probe_port",
            "route": "probe_port:5328",
            "target_identity": "target:5328",
            "target_generation": "result:open",
            "task_state_generation": 0,
            "tool_identity": "test.probe",
            "result_hash": "open-hash",
            "evidence_ceiling": "metadata_proxy",
            "eligible_for_proof": True,
        },
    ))
    compiled = SimpleNamespace(proof_contract=({
        "clause_id": "protocol",
        "verifier_route": "overlay_run_command:python3 independent_client.py",
        "fallback_route": "",
        "required_evidence_class": "exact_contract",
    },))
    result = ModelVerifierResult(
        verdict="completed",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="exact protocol round trip",
            observed="port is open",
            falsification_check="client mismatch",
            inspection_refs=("inspection:port",),
            clause_ids=("protocol",),
            evidence_class="exact_contract",
        ),),
    )

    receipts = record_verifier_result_evidence(
        ledger,
        result=result,
        compiled=compiled,
        step=2,
    )

    assert receipts
    assert receipts[0].success is False
    assert receipts[0].payload["route"] == "unregistered_inspection"
    assert receipts[0].payload["source"] == "model_verifier_completion_evidence_rejected"



def test_f79_verifier_cannot_record_exact_claim_from_behavioral_actual_observation() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="inspection:http", step=2, kind="inspection_record", success=True,
        summary="HTTP response observed", payload={
            "inspection_id": "inspection:http",
            "route_kind": "probe_http",
            "route": "probe_http:http://127.0.0.1:80",
            "route_parameters": {},
            "target_identity": "url:http://127.0.0.1:80",
            "target_generation": "result:http",
            "task_state_generation": ledger.task_state_generation(),
            "tool_identity": "test.http",
            "result_hash": "http-hash",
            "evidence_ceiling": "behavioral",
            "actual_evidence_class": "behavioral",
            "eligible_for_proof": True,
            "admissibility": "direct_admissible",
        },
    ))
    compiled = SimpleNamespace(proof_contract=({
        "clause_id": "result",
        "verifier_route": "probe_http:http://127.0.0.1:80",
        "fallback_route": "",
        "required_evidence_class": "behavioral",
        "proof_obligation": "public_behavior",
        "route_kind": "probe_http",
        "route_evidence_ceiling": "behavioral",
        "requires_independent_evidence": True,
    },))
    result = ModelVerifierResult(
        verdict="completed",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="exact state claim",
            observed="HTTP 200",
            falsification_check="response mismatch",
            inspection_refs=("inspection:http",),
            clause_ids=("result",),
            evidence_class="exact_contract",
        ),),
    )
    receipts = record_verifier_result_evidence(ledger, result=result, compiled=compiled, step=2)
    assert len(receipts) == 1
    assert receipts[0].success is False
    assert receipts[0].payload["source"] == "model_verifier_completion_evidence_rejected"


def test_f79_durable_verifier_proof_claim_above_actual_strength_cannot_satisfy_clause() -> None:
    ledger = ExecutionLedger()
    clause = _clause()
    receipt = record_clause_evidence(
        ledger,
        receipt_id="proof:inflated",
        step=1,
        clause_id="result",
        route="read_file:out.txt",
        evidence_class="exact_contract",
        provenance="verifier_inspection",
        supports_clause=True,
        observation="partial read",
        inspection_ids=("inspection:weak",),
    )
    receipt.payload.update({
        "source": "model_verifier_completion_evidence",
        "actual_evidence_class": "metadata_proxy",
        "actual_evidence_ceiling": "exact_contract",
    })
    decision = evaluate_proof_contract((clause,), ledger)[0]
    assert decision.satisfied is False
    assert decision.code == "insufficient_clause_evidence"


def test_older_same_generation_observation_is_superseded_by_new_conflicting_read() -> None:
    ledger = ExecutionLedger()
    first = register_inspection_results(
        (VerifierInspectionRequest(request_id="old", kind="read_file", path="out.txt"),),
        ({
            "request_id": "old", "kind": "read_file", "path": "out.txt",
            "bytes": 2, "offset": 0, "excerpt": "42", "content_hash": "oldhash",
            "observation_origin": "executor_read",
        },),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-2",
    )[0]
    register_inspection_results(
        (VerifierInspectionRequest(request_id="new", kind="read_file", path="out.txt"),),
        ({
            "request_id": "new", "kind": "read_file", "path": "out.txt",
            "bytes": 2, "offset": 0, "excerpt": "99", "content_hash": "newhash",
            "observation_origin": "executor_read",
        },),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-2",
    )
    compiled = SimpleNamespace(proof_contract=({
        "clause_id": "result", "verifier_route": "read_file:out.txt",
        "fallback_route": "", "required_evidence_class": "exact_contract",
    },))
    result = ModelVerifierResult(
        verdict="completed",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="out.txt contains 42", observed="older read says 42",
            falsification_check="different bytes", inspection_refs=(first["inspection_id"],),
            clause_ids=("result",), evidence_class="exact_contract",
        ),),
    )
    receipts = record_verifier_result_evidence(ledger, result=result, compiled=compiled, step=2)
    assert len(receipts) == 1
    assert receipts[0].success is False
    assert receipts[0].payload["source"] == "model_verifier_completion_evidence_rejected"


def test_equivalent_reread_does_not_supersede_same_target_state() -> None:
    ledger = ExecutionLedger()
    first = register_inspection_results(
        (VerifierInspectionRequest(request_id="old", kind="read_file", path="out.txt"),),
        ({
            "request_id": "old", "kind": "read_file", "path": "out.txt",
            "bytes": 2, "offset": 0, "excerpt": "42", "content_hash": "samehash",
            "observation_origin": "executor_read",
        },),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-2",
    )[0]
    register_inspection_results(
        (VerifierInspectionRequest(request_id="new", kind="read_file", path="out.txt"),),
        ({
            "request_id": "new", "kind": "read_file", "path": "out.txt",
            "bytes": 2, "offset": 0, "excerpt": "42", "content_hash": "samehash",
            "observation_origin": "executor_read",
        },),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-2",
    )
    from aether.inspection_registry import admissible_verdict_refs
    assert first["inspection_id"] in admissible_verdict_refs(ledger)[0]


def test_read_file_candidate_elsewhere_is_exploratory_not_proof() -> None:
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(request_id="read-required", kind="read_file", path="out.txt")
    rows = register_inspection_results(
        (request,),
        ({
            "request_id": "read-required", "kind": "read_file",
            "requested_path": "out.txt", "path": "nested/out.txt",
            "bytes": 2, "content_hash": "abc123", "excerpt": "42",
            "observation_origin": "executor_read", "read_only": True,
        },),
        ledger=ledger, step=3, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-3",
    )
    row = rows[0]
    assert row["target_identity"] == "path:nested/out.txt"
    assert row["target_binding_valid"] is False
    assert row["admissibility"] == "exploratory"
    assert row["eligible_for_proof"] is False

    compiled = SimpleNamespace(proof_contract=({
        "clause_id": "result", "verifier_route": "read_file:out.txt",
        "fallback_route": "", "required_evidence_class": "exact_contract",
    },))
    result = ModelVerifierResult(
        verdict="completed",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="out.txt contains the exact result", observed="candidate contains 42",
            falsification_check="different bytes", inspection_refs=(row["inspection_id"],),
            clause_ids=("result",), evidence_class="exact_contract",
        ),),
    )
    receipts = record_verifier_result_evidence(ledger, result=result, compiled=compiled, step=3)
    assert len(receipts) == 1
    assert receipts[0].success is False
    assert receipts[0].payload["source"] == "model_verifier_completion_evidence_rejected"



def _register_full_file(ledger: ExecutionLedger, *, request_path: str, observed_path: str, step: int = 3) -> dict:
    return register_inspection_results(
        (VerifierInspectionRequest(request_id="route-bound", kind="read_file", path=request_path),),
        ({
            "request_id": "route-bound", "kind": "read_file",
            "requested_path": request_path, "path": observed_path,
            "bytes": 2, "offset": 0, "span": 4000,
            "content_hash": "a" * 16, "excerpt": "42",
            "observation_origin": "executor_read", "read_only": True,
        },),
        ledger=ledger, step=step, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-route-bound",
    )[0]


def _completed_for_result_clause(inspection_id: str) -> ModelVerifierResult:
    return ModelVerifierResult(
        verdict="completed",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="out.txt contains the exact result", observed="observed 42",
            falsification_check="different bytes", inspection_refs=(inspection_id,),
            clause_ids=("result",), evidence_class="exact_contract",
        ),),
    )


def _compiled_result_route(route: str = "read_file:out.txt") -> SimpleNamespace:
    return SimpleNamespace(proof_contract=({
        "clause_id": "result", "verifier_route": route, "fallback_route": "",
        "required_evidence_class": "exact_contract", "proof_obligation": "exact_state",
        "route_kind": "read_file", "route_evidence_ceiling": "exact_contract",
        "requires_independent_evidence": True,
    },))


def test_direct_wrong_file_cannot_satisfy_different_certified_file_route() -> None:
    ledger = ExecutionLedger()
    row = _register_full_file(
        ledger, request_path="nested/out.txt", observed_path="nested/out.txt",
    )
    assert row["target_binding_valid"] is True
    assert row["eligible_for_proof"] is True
    receipts = record_verifier_result_evidence(
        ledger, result=_completed_for_result_clause(row["inspection_id"]),
        compiled=_compiled_result_route("read_file:out.txt"), step=3,
    )
    assert len(receipts) == 1
    assert receipts[0].success is False
    assert receipts[0].payload["source"] == "model_verifier_completion_evidence_rejected"
    assert receipts[0].payload["certified_routes"] == ["read_file:out.txt"]


def test_workspace_absolute_and_relative_certified_file_routes_are_equivalent() -> None:
    ledger = ExecutionLedger()
    row = _register_full_file(
        ledger, request_path="/app/out.txt", observed_path="/app/out.txt",
    )
    receipts = record_verifier_result_evidence(
        ledger, result=_completed_for_result_clause(row["inspection_id"]),
        compiled=_compiled_result_route("read_file:out.txt"), step=3,
    )
    assert len(receipts) == 1
    assert receipts[0].success is True
    assert receipts[0].payload["target_identity"] == "path:/app/out.txt"


def test_http_probe_target_substitution_is_exploratory_not_proof() -> None:
    ledger = ExecutionLedger()
    row = register_inspection_results(
        (VerifierInspectionRequest(
            request_id="http-a", kind="probe_http", target="http://127.0.0.1:8000/a",
        ),),
        ({
            "request_id": "http-a", "kind": "probe_http",
            "url": "http://127.0.0.1:8000/b", "reachable": True,
            "status": 200, "response_observed": True,
            "observation_origin": "executor_probe",
        },),
        ledger=ledger, step=4, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-http",
    )[0]
    assert row["target_identity"] == "url:http://127.0.0.1:8000/b"
    assert row["target_binding_valid"] is False
    assert row["admissibility"] == "exploratory"
    assert row["eligible_for_proof"] is False


def test_process_probe_target_substitution_is_exploratory_not_proof() -> None:
    ledger = ExecutionLedger()
    row = register_inspection_results(
        (VerifierInspectionRequest(request_id="proc-a", kind="probe_process", target="worker-a"),),
        ({
            "request_id": "proc-a", "kind": "probe_process",
            "pattern": "worker-b", "running": True, "match_count": 1,
            "matches": ["123 worker-b"], "observation_origin": "executor_probe",
        },),
        ledger=ledger, step=4, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-proc",
    )[0]
    assert row["target_identity"] == "process_pattern:worker-b"
    assert row["target_binding_valid"] is False
    assert row["eligible_for_proof"] is False


def test_probe_port_default_host_binding_accepts_same_socket_and_rejects_other_port() -> None:
    request = VerifierInspectionRequest(request_id="port", kind="probe_port", target="8080")
    ledger = ExecutionLedger()
    good = register_inspection_results(
        (request,), ({
            "request_id": "port", "kind": "probe_port", "host": "127.0.0.1",
            "port": 8080, "state": "open", "observation_origin": "executor_probe",
        },), ledger=ledger, step=1, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-port",
    )[0]
    assert good["target_binding_valid"] is True
    bad = register_inspection_results(
        (request,), ({
            "request_id": "port", "kind": "probe_port", "host": "127.0.0.1",
            "port": 9090, "state": "open", "observation_origin": "executor_probe",
        },), ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=None, packet_signature="packet-port",
    )[0]
    assert bad["target_binding_valid"] is False
    assert bad["eligible_for_proof"] is False
