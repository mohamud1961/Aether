"""Deterministic V1 replay classification for verifier evidence admissibility."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether.inspection_registry import admissible_verdict_refs, register_inspection_results
from aether.ledger import ExecutionLedger, Receipt
from aether.verifier import MethodValidityShapeError, parse_model_verifier_result
from aether.verifier_inspector import VerifierInspectionRequest, execute_verifier_inspection_requests
from aether.runtime_ir import EnvMap
from aether.verify_completion_protocol import _method_authority_problem, _verdict_admissibility_problem


class _Executor:
    pass


def test_legacy_behavioral_basis_is_rejected_not_silently_ignored() -> None:
    with pytest.raises(MethodValidityShapeError) as exc_info:
        parse_model_verifier_result({
            "verdict": "completed",
            "summary": "done",
            "method_validity": {
                "observed_structure": "field",
                "executed_rule": "parse field",
                "method_alignment": "the rule measures the field",
                "behavioral_basis": "legacy field",
                "authoritative_source_refs": ["direct"],
                "execution_ref": "derived",
            },
        })
    assert exc_info.value.invalid == (
        "method_validity.behavioral_basis is not accepted",
    )


def _register(ledger: ExecutionLedger, request: VerifierInspectionRequest, result: dict, *, step: int = 1) -> str:
    return register_inspection_results(
        (request,), (result,), ledger=ledger, step=step, requester="model_verifier",
        executor=_Executor(), overlay=_Executor(), packet_signature="packet",
    )[0]["inspection_id"]


def test_arbitrary_overlay_stdout_is_exploratory_and_cannot_ground_follow_up() -> None:
    ledger = ExecutionLedger()
    execution = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="unsafe", kind="overlay_run_command", command="python3 inspect.py",
            evidence_mode="derived", basis_refs=("task:prompt",), bound_input_refs=("task:prompt",),
        ),
        {"request_id": "unsafe", "kind": "overlay_run_command", "stdout": "[WARNING] source-looking text", "exit_code": 0},
    )
    direct, derived = admissible_verdict_refs(ledger)
    assert not direct
    assert execution not in derived
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == execution)
    assert receipt.payload["admissibility"] == "exploratory"
    assert receipt.payload["eligible_for_proof"] is False


def test_direct_read_then_bound_derived_execution_is_verdict_eligible() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="logs/raw.log"),
        {"request_id": "source", "kind": "read_file", "path": "logs/raw.log", "content_hash": "raw-v1", "excerpt": "[WARNING]"},
    )
    execution = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="python3 recompute.py",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
        ),
        {"request_id": "derive", "kind": "overlay_run_command", "stdout": "counts", "exit_code": 0},
        step=2,
    )
    direct, derived = admissible_verdict_refs(ledger)
    assert source in direct
    assert execution in derived
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == execution)
    assert receipt.payload["admissibility"] == "verdict_eligible"
    assert receipt.payload["eligible_for_proof"] is True


def test_typed_port_probe_can_ground_a_fresh_derived_interface_check() -> None:
    ledger = ExecutionLedger()
    proto = _register(
        ledger,
        VerifierInspectionRequest(request_id="proto", kind="read_file", path="kv-store.proto"),
        {
            "request_id": "proto", "kind": "read_file",
            "path": "kv-store.proto", "content_hash": "proto-v1",
            "excerpt": "service KVStore",
        },
    )
    port = _register(
        ledger,
        VerifierInspectionRequest(request_id="port", kind="probe_port", target="127.0.0.1:5328"),
        {
            "request_id": "port", "kind": "probe_port",
            "host": "127.0.0.1", "port": 5328, "state": "open",
        },
    )

    # A bound input omitted from the declared basis still fails closed.
    first = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive-incomplete", kind="overlay_run_command",
            command="python3 client.py", evidence_mode="derived",
            basis_refs=(proto,), bound_input_refs=(proto, port),
        ),
        {
            "request_id": "derive-incomplete", "kind": "overlay_run_command",
            "stdout": "SET 73\nGET 73\n", "exit_code": 0,
        },
        step=2,
    )
    first_receipt = next(item for item in ledger.all_receipts() if item.receipt_id == first)
    assert first_receipt.payload["admissibility"] == "exploratory"

    # Once the exact observed socket is part of both basis and binding, the
    # same independent execution is provenance-complete and verdict-eligible.
    second = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive-complete", kind="overlay_run_command",
            command="python3 client.py", evidence_mode="derived",
            basis_refs=(proto, port), bound_input_refs=(proto, port),
        ),
        {
            "request_id": "derive-complete", "kind": "overlay_run_command",
            "stdout": "SET 91\nGET 91\n", "exit_code": 0,
        },
        step=2,
    )
    direct, derived = admissible_verdict_refs(ledger)
    assert proto in direct
    assert port in direct
    assert second in derived
    second_receipt = next(item for item in ledger.all_receipts() if item.receipt_id == second)
    assert second_receipt.payload["admissibility"] == "verdict_eligible"
    assert second_receipt.payload["eligible_for_proof"] is True


def test_negative_bound_derived_execution_remains_verdict_eligible_observation() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="text.gcode"),
        {"request_id": "source", "kind": "read_file", "content_hash": "raw-v1", "excerpt": "source"},
    )
    rows = register_inspection_results(
        (VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="python3 recompute.py",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
        ),),
        ({
            "request_id": "derive", "kind": "overlay_run_command", "exit_code": 1,
            "success": False, "stderr": "assertion mismatch", "stderr_bytes": 18,
        },),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )
    execution = rows[0]["inspection_id"]
    # Raw producer polarity must survive the enrichment boundary seen by the Verifier.
    assert rows[0]["success"] is False
    assert rows[0]["observation_valid"] is True
    assert rows[0]["observed_outcome_success"] is False
    direct, derived = admissible_verdict_refs(ledger)
    assert source in direct
    assert execution in derived
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == execution)
    assert receipt.payload["admissibility"] == "verdict_eligible"
    assert receipt.payload["eligible_for_proof"] is False
    assert receipt.payload["observation_valid"] is True
    assert receipt.payload["observed_outcome_success"] is False
    assert receipt.payload["observed_exit_code"] == 1
    assert receipt.payload["success"] is False
    assert receipt.success is False
    assert receipt.failure_class == ""
    assert receipt.payload["observed_stderr_bytes"] == 18
    assert len(receipt.payload["observed_stderr_sha256"]) == 64


def test_negative_derived_observation_can_ground_blocking_needs_repair_verdict() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="source.txt"),
        {"request_id": "source", "kind": "read_file", "content_hash": "v1", "excerpt": "required=ready"},
    )
    negative = register_inspection_results(
        (VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="python3 verify.py",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
        ),),
        ({
            "request_id": "derive", "kind": "overlay_run_command", "exit_code": 1,
            "success": False, "stderr": "AssertionError: observed != required",
        },),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )[0]
    result = parse_model_verifier_result({
        "verdict": "needs_repair",
        "confidence": "high",
        "summary": "independent check falsified the completion claim",
        "findings": [{
            "finding_id": "vf-negative-check",
            "verdict": "needs_repair",
            "priority": "blocking",
            "summary": "independent assertion failed",
            "evidence": ["AssertionError: observed != required"],
            "supporting_inspection_ids": [negative["inspection_id"]],
            "repair_instruction": "repair the observed mismatch",
            "applies_to": ["result"],
        }],
        "method_validity": {
            "observed_structure": "direct source plus independent execution",
            "executed_rule": "compare observed behavior to required behavior",
            "method_alignment": "the independent assertion directly measures the claimed behavior",
            "authoritative_source_refs": [source],
            "execution_ref": negative["inspection_id"],
        },
    })
    direct, derived = admissible_verdict_refs(ledger)
    assert negative["inspection_id"] in derived
    assert _verdict_admissibility_problem(result, direct, derived) == ""


def test_completed_verdict_cannot_hitchhike_non_admissible_ref_beside_good_ref() -> None:
    result = parse_model_verifier_result({
        "verdict": "completed",
        "confidence": "high",
        "summary": "done",
        "completion_evidence": [{
            "requirement": "result", "observed": "observed",
            "inspection_refs": ["direct-good", "stale-or-exploratory"],
            "falsification_check": "a mismatch would fail",
        }],
    })
    problem = _verdict_admissibility_problem(
        result, {"direct-good"}, set(),
    )
    assert problem == "completed cites non-admissible evidence: stale-or-exploratory"


def test_completed_verdict_cannot_use_exploratory_method_execution() -> None:
    result = parse_model_verifier_result({
        "verdict": "completed",
        "confidence": "high",
        "summary": "done",
        "completion_evidence": [{
            "requirement": "result", "observed": "observed", "inspection_refs": ["direct"],
            "falsification_check": "a mismatch would fail",
        }],
        "method_validity": {
            "observed_structure": "field", "executed_rule": "parse field",
            "method_alignment": "the rule measures the field rather than a descriptive proxy",
            "authoritative_source_refs": ["direct"], "execution_ref": "exploratory",
        },
    })
    assert "not a current verdict-eligible" in _verdict_admissibility_problem(
        result, {"direct"}, set(),
    )


def test_model_declared_target_cannot_create_continuity() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="metadata", kind="inspect_artifact", path="summary.csv", target="/app/logs/raw.log"),
        {"request_id": "metadata", "kind": "inspect_artifact", "path": "summary.csv", "sha256": "x"},
    )
    execution = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="python3 fake.py",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=("task:prompt",),
        ),
        {"request_id": "derive", "kind": "overlay_run_command", "stdout": "ok", "exit_code": 0},
        step=2,
    )
    assert execution not in admissible_verdict_refs(ledger)[1]


def test_superseded_direct_basis_cannot_authorize_derived_execution() -> None:
    ledger = ExecutionLedger()
    old = _register(
        ledger,
        VerifierInspectionRequest(request_id="old", kind="read_file", path="source.txt"),
        {"request_id":"old","kind":"read_file","path":"source.txt","bytes":3,"offset":0,
         "excerpt":"old","content_hash":"oldhash","observation_origin":"executor_read"},
    )
    _register(
        ledger,
        VerifierInspectionRequest(request_id="new", kind="read_file", path="source.txt"),
        {"request_id":"new","kind":"read_file","path":"source.txt","bytes":3,"offset":0,
         "excerpt":"new","content_hash":"newhash","observation_origin":"executor_read"},
    )
    derived = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="python3 verify.py",
            evidence_mode="derived", basis_refs=(old,), bound_input_refs=(old,),
        ),
        {"request_id":"derive","kind":"overlay_run_command","exit_code":0,"success":True,
         "stdout":"ok","observation_origin":"verifier_overlay"},
        step=2,
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == derived)
    assert receipt.payload["admissibility"] == "exploratory"
    assert receipt.payload["eligible_for_proof"] is False
    assert derived not in admissible_verdict_refs(ledger)[1]


def test_stale_direct_receipt_is_rejected() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="raw.log"),
        {"request_id": "source", "kind": "read_file", "path": "raw.log", "content_hash": "old"},
    )
    ledger.record(Receipt(
        receipt_id="mutation", step=2, kind="write_file", success=True, summary="changed source",
        state_change=True, payload={"modified_paths": ["raw.log"]},
    ))
    assert source not in admissible_verdict_refs(ledger)[0]


def test_task_fact_alone_cannot_ground_an_opaque_derived_execution() -> None:
    ledger = ExecutionLedger()
    execution = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command", command="python3 check.py",
            evidence_mode="derived", basis_refs=("task-fact:structured-input",),
            bound_input_refs=("task-fact:structured-input",),
        ),
        {"request_id": "derive", "kind": "overlay_run_command", "stdout": "verified", "exit_code": 0},
    )
    assert execution not in admissible_verdict_refs(ledger)[1]


def test_tooling_error_is_not_admitted_as_negative_evidence() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="source.txt"),
        {"request_id": "source", "kind": "read_file", "content_hash": "v1", "excerpt": "source"},
    )
    row = register_inspection_results(
        (VerifierInspectionRequest(
            request_id="broken", kind="overlay_run_command", command="python3 check.py",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
        ),),
        ({"request_id": "broken", "kind": "overlay_run_command", "error": "overlay setup failed"},),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )[0]
    assert row["observation_valid"] is False
    assert row["inspection_id"] not in admissible_verdict_refs(ledger)[1]
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == row["inspection_id"])
    assert receipt.success is False
    assert receipt.payload["eligible_for_proof"] is False


def test_timed_out_derived_execution_is_partial_not_negative_evidence() -> None:
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="source.txt"),
        {"request_id": "source", "kind": "read_file", "content_hash": "v1", "excerpt": "source"},
    )
    row = register_inspection_results(
        (VerifierInspectionRequest(
            request_id="timeout", kind="overlay_run_command", command="python3 check.py",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
        ),),
        ({
            "request_id": "timeout", "kind": "overlay_run_command",
            "exit_code": 124, "success": False, "timed_out": True,
            "stdout": "partial observation", "stderr": "deadline exceeded",
        },),
        ledger=ledger, step=2, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )[0]
    assert row["observation_valid"] is False
    assert row["observed_timed_out"] is True
    assert row["admissibility"] == "exploratory"
    assert row["inspection_id"] not in admissible_verdict_refs(ledger)[1]
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == row["inspection_id"])
    assert receipt.payload["eligible_for_proof"] is False
    assert receipt.failure_class == "verifier_inspection_failed"


def test_http_dns_failure_is_substrate_limited_not_service_negative_evidence() -> None:
    ledger = ExecutionLedger()
    row = register_inspection_results(
        (VerifierInspectionRequest(request_id="http-dns", kind="probe_http", target="http://client-alias:8080/health"),),
        ({
            "request_id": "http-dns", "kind": "probe_http",
            "url": "http://client-alias:8080/health",
            "reachable": False, "response_observed": False,
            "failure_class": "dns_resolution",
            "probe_namespace": "executor_environment",
            "detail": "Temporary failure in name resolution",
            "observation_origin": "executor_probe",
        },),
        ledger=ledger, step=1, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )[0]
    assert row["observation_valid"] is True
    assert row["admissibility"] == "exploratory"
    assert row["eligible_for_proof"] is False
    assert row["method_domain_status"] == "substrate_limited"
    assert row["method_domain_missing"] == ["requested_hostname_resolution_in_probe_namespace"]
    assert row["inspection_id"] not in admissible_verdict_refs(ledger)[0]


def test_http_connection_refused_remains_addressed_negative_metadata() -> None:
    ledger = ExecutionLedger()
    row = register_inspection_results(
        (VerifierInspectionRequest(request_id="http-refused", kind="probe_http", target="http://127.0.0.1:8080/health"),),
        ({
            "request_id": "http-refused", "kind": "probe_http",
            "url": "http://127.0.0.1:8080/health",
            "reachable": False, "response_observed": False,
            "failure_class": "connection_refused",
            "probe_namespace": "executor_environment",
            "detail": "Connection refused",
            "observation_origin": "executor_probe",
        },),
        ledger=ledger, step=1, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )[0]
    assert row["observation_valid"] is True
    assert row["admissibility"] == "direct_admissible"
    assert row["eligible_for_proof"] is True
    assert row["actual_evidence_class"] == "metadata_proxy"


def test_http_error_status_is_valid_negative_behavioral_observation() -> None:
    ledger = ExecutionLedger()
    row = register_inspection_results(
        (VerifierInspectionRequest(request_id="http", kind="probe_http", target="http://svc/health"),),
        ({
            "request_id": "http", "kind": "probe_http", "url": "http://svc/health",
            "reachable": True, "response_observed": True, "status": 503,
            "body_head": "not ready", "observation_origin": "executor_probe",
        },),
        ledger=ledger, step=1, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )[0]
    assert row["observation_valid"] is True
    assert row["observed_http_status"] == 503
    assert row["inspection_id"] in admissible_verdict_refs(ledger)[0]



def test_f79_full_file_snapshot_is_exact_but_partial_file_is_metadata_proxy() -> None:
    for request_id, result, expected in (
        ("full", {"request_id":"full","kind":"read_file","path":"config.txt","bytes":5,"offset":0,"span":4000,"excerpt":"hello","content_hash":"a"*16,"observation_origin":"executor_read"}, "exact_contract"),
        ("partial", {"request_id":"partial","kind":"read_file","path":"config.txt","bytes":10,"offset":0,"span":5,"excerpt":"hello","content_hash":"b"*16,"observation_origin":"executor_read"}, "metadata_proxy"),
    ):
        ledger = ExecutionLedger()
        inspection = _register(ledger, VerifierInspectionRequest(request_id=request_id, kind="read_file", path="config.txt"), result)
        receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection)
        assert receipt.payload["actual_evidence_class"] == expected
        assert receipt.payload["evidence_ceiling"] == "exact_contract"


def test_f79_full_ledger_output_is_behavioral_but_partial_output_is_metadata_proxy() -> None:
    for request_id, result, expected in (
        ("full-out", {"request_id":"full-out","kind":"read_output","handle":"stdout:1","source_receipt_id":"step-1:cmd","stream":"stdout","bytes":2,"offset":0,"span":4000,"excerpt":"OK","content_hash":"a"*16,"observation_origin":"ledger_output"}, "behavioral"),
        ("partial-out", {"request_id":"partial-out","kind":"read_output","handle":"stdout:1","source_receipt_id":"step-1:cmd","stream":"stdout","bytes":10,"offset":0,"span":2,"excerpt":"OK","content_hash":"a"*16,"observation_origin":"ledger_output"}, "metadata_proxy"),
    ):
        ledger = ExecutionLedger()
        inspection = _register(ledger, VerifierInspectionRequest(request_id=request_id, kind="read_output", handle="stdout:1"), result)
        receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection)
        assert receipt.payload["actual_evidence_class"] == expected
        assert receipt.payload["evidence_ceiling"] == "behavioral"


def test_f79_artifact_hash_reaches_exact_contract_but_absence_is_metadata_only() -> None:
    ledger = ExecutionLedger()
    exact = _register(
        ledger,
        VerifierInspectionRequest(request_id="artifact", kind="inspect_artifact", path="out.bin"),
        {"request_id":"artifact","kind":"inspect_artifact","path":"out.bin","exists":True,"sha256":"a"*64,"observation_origin":"executor_probe"},
    )
    absent = _register(
        ledger,
        VerifierInspectionRequest(request_id="absent", kind="inspect_artifact", path="missing.bin"),
        {"request_id":"absent","kind":"inspect_artifact","path":"missing.bin","exists":False,"observation_origin":"executor_probe"},
    )
    by_id = {item.receipt_id:item for item in ledger.all_receipts()}
    assert by_id[exact].payload["actual_evidence_class"] == "exact_contract"
    assert by_id[absent].payload["actual_evidence_class"] == "metadata_proxy"


def test_f79_derived_exact_strength_requires_exact_current_basis() -> None:
    strong_ledger = ExecutionLedger()
    strong = _register(
        strong_ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="source.txt"),
        {"request_id":"source","kind":"read_file","path":"source.txt","bytes":6,"offset":0,"span":4000,"excerpt":"source","content_hash":"a"*16,"observation_origin":"executor_read"},
    )
    strong_derived = _register(
        strong_ledger,
        VerifierInspectionRequest(request_id="derive", kind="overlay_run_command", command="python3 check.py", evidence_mode="derived", basis_refs=(strong,), bound_input_refs=(strong,)),
        {"request_id":"derive","kind":"overlay_run_command","stdout":"ok","exit_code":0,"observation_origin":"verifier_overlay"},
        step=2,
    )
    strong_receipt = next(item for item in strong_ledger.all_receipts() if item.receipt_id == strong_derived)
    assert strong_receipt.payload["admissibility"] == "verdict_eligible"
    assert strong_receipt.payload["actual_evidence_class"] == "exact_contract"

    weak_ledger = ExecutionLedger()
    weak = _register(
        weak_ledger,
        VerifierInspectionRequest(request_id="port", kind="probe_port", target="127.0.0.1:99"),
        {"request_id":"port","kind":"probe_port","host":"127.0.0.1","port":99,"state":"open","observation_origin":"executor_probe"},
    )
    weak_derived = _register(
        weak_ledger,
        VerifierInspectionRequest(request_id="derive", kind="overlay_run_command", command="python3 check.py", evidence_mode="derived", basis_refs=(weak,), bound_input_refs=(weak,)),
        {"request_id":"derive","kind":"overlay_run_command","stdout":"ok","exit_code":0,"observation_origin":"verifier_overlay"},
        step=2,
    )
    weak_receipt = next(item for item in weak_ledger.all_receipts() if item.receipt_id == weak_derived)
    assert weak_receipt.payload["admissibility"] == "verdict_eligible"
    assert weak_receipt.payload["actual_evidence_class"] == "behavioral"
    assert weak_receipt.payload["evidence_ceiling"] == "exact_contract"


def test_f79_metadata_probe_actual_strength_never_exceeds_route_ceiling() -> None:
    ledger = ExecutionLedger()
    ref = _register(
        ledger,
        VerifierInspectionRequest(request_id="port", kind="probe_port", target="127.0.0.1:80"),
        {"request_id":"port","kind":"probe_port","host":"127.0.0.1","port":80,"state":"open","observation_origin":"executor_probe"},
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == ref)
    assert receipt.payload["actual_evidence_class"] == "metadata_proxy"
    assert receipt.payload["evidence_ceiling"] == "metadata_proxy"


def test_probe_port_dns_failure_is_substrate_limited_and_exploratory() -> None:
    ledger = ExecutionLedger()
    ref = _register(
        ledger,
        VerifierInspectionRequest(request_id="dns-port", kind="probe_port", target="client-alias.invalid:8080"),
        {
            "request_id": "dns-port", "kind": "probe_port",
            "host": "client-alias.invalid", "port": 8080, "state": "unknown",
            "probe_namespace": "executor_environment", "failure_class": "dns_resolution",
            "error": "socket.gaierror: Name or service not known",
        },
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == ref)
    assert receipt.payload["method_domain_status"] == "substrate_limited"
    assert receipt.payload["method_domain_missing"] == ["requested_hostname_resolution_in_probe_namespace"]
    assert receipt.payload["admissibility"] == "exploratory"
    assert receipt.payload["eligible_for_proof"] is False



def test_s5c3_descriptive_source_marker_cannot_be_semantic_method_authority() -> None:
    """A grep of a source marker is not proof of the effect that marker describes."""
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source", kind="read_file", path="source.gcode", span=24),
        {
            "request_id": "source", "kind": "read_file", "path": "source.gcode",
            "bytes": 1000, "offset": 0, "span": 24,
            "excerpt": "M486 AEmbossed text\n", "content_hash": "a" * 16,
            "observation_origin": "executor_read",
        },
    )
    derived = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive", kind="overlay_run_command",
            command="grep -E 'text|marker|label' source.gcode",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
        ),
        {
            "request_id": "derive", "kind": "overlay_run_command",
            "stdout": "Embossed text\n", "exit_code": 0,
            "observation_origin": "verifier_overlay",
        },
        step=2,
    )
    method_validity = SimpleNamespace(
        observed_structure=(
            "The supplied artifact contains a text marker named `Embossed text`."
        ),
        executed_rule=(
            "Search the artifact for text-related markers and report the matching marker."
        ),
        method_alignment=(
            "The reported marker directly identifies the result requested by the task."
        ),
        execution_ref=derived,
        authoritative_source_refs=(source,),
    )

    problem = _method_authority_problem(
        ledger, {derived}, method_validity=method_validity,
    )

    assert "descriptive metadata" in problem
    assert "independent executable or counterfactual effect check" in problem



def test_descriptive_source_marker_is_allowed_with_independent_effect_method() -> None:
    """Metadata may seed verification when the method checks the operative effect."""
    ledger = ExecutionLedger()
    source = _register(
        ledger,
        VerifierInspectionRequest(request_id="source-effect", kind="read_file", path="source.gcode", span=24),
        {
            "request_id": "source-effect", "kind": "read_file", "path": "source.gcode",
            "bytes": 1000, "offset": 0, "span": 24,
            "excerpt": "M486 AEmbossed text\n", "content_hash": "b" * 16,
            "observation_origin": "executor_read",
        },
    )
    derived = _register(
        ledger,
        VerifierInspectionRequest(
            request_id="derive-effect", kind="overlay_run_command",
            command="python3 render_and_measure.py source.gcode",
            evidence_mode="derived", basis_refs=(source,), bound_input_refs=(source,),
        ),
        {
            "request_id": "derive-effect", "kind": "overlay_run_command",
            "stdout": "visible effect measured\n", "exit_code": 0,
            "observation_origin": "verifier_overlay",
        },
        step=2,
    )
    method_validity = SimpleNamespace(
        observed_structure="The artifact contains a descriptive text marker plus operative geometry.",
        executed_rule="Render the operative geometry and measure the produced visible effect.",
        method_alignment="The rendered behavior checks the effect independently of the descriptive marker.",
        execution_ref=derived,
        authoritative_source_refs=(source,),
    )

    assert _method_authority_problem(
        ledger, {derived}, method_validity=method_validity,
    ) == ""


def test_s6_binary_read_file_snapshot_cannot_be_exact_contract() -> None:
    """A lossy text rendering of binary bytes is not exact semantic evidence."""
    ledger = ExecutionLedger()
    rendered = "PAR1\ufffdBINARY\x00DATA"
    inspection = _register(
        ledger,
        VerifierInspectionRequest(request_id="binary", kind="read_file", path="table.parquet"),
        {
            "request_id": "binary",
            "kind": "read_file",
            "path": "table.parquet",
            "bytes": len(rendered),
            "content_chars": len(rendered),
            "offset": 0,
            "span": 4000,
            "excerpt": rendered,
            "content_hash": "c" * 16,
            "content_identity_basis": "captured_bytes",
            "text_decode_lossless": False,
            "observation_origin": "executor_read",
        },
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection)
    assert receipt.payload["actual_evidence_class"] == "metadata_proxy"
    assert receipt.payload["actual_evidence_reason"] == "binary_or_non_utf8_snapshot"


class _BinarySnapshotExecutor:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def read_file_bytes(self, path: str) -> bytes:
        assert path == "table.parquet"
        return self.raw

    def read_file(self, path: str) -> str:
        # Path resolution may perform a read probe; the authoritative inspection
        # result must still come from read_file_bytes and preserve raw identity.
        assert path == "table.parquet"
        return self.raw.decode("utf-8", "replace")


def test_s6_verifier_read_file_preserves_raw_binary_identity_and_marks_lossy_decode() -> None:
    raw = b"PAR1\xff\x00compressed\x80payloadPAR1"
    executor = _BinarySnapshotExecutor(raw)
    rows = execute_verifier_inspection_requests(
        (VerifierInspectionRequest(request_id="binary-read", kind="read_file", path="table.parquet", span=4000),),
        compiled=SimpleNamespace(planned_checks=lambda: ()),
        ledger=ExecutionLedger(),
        executor=executor,
        envmap=EnvMap(task_prompt="binary custody", workspace_root="/app"),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["bytes"] == len(raw)
    assert row["content_hash"] == __import__("hashlib").sha256(raw).hexdigest()[:16]
    assert row["content_identity_basis"] == "captured_bytes"
    assert row["text_decode_lossless"] is False
    assert "\ufffd" in row["excerpt"]


def test_s6_verifier_read_file_keeps_lossless_text_exact_identity() -> None:
    raw = "hello π\n".encode("utf-8")
    executor = _BinarySnapshotExecutor(raw)
    # The fixture asserts a fixed path, so use the same logical name; semantic
    # classification is based on bytes/decoding, never the extension.
    rows = execute_verifier_inspection_requests(
        (VerifierInspectionRequest(request_id="text-read", kind="read_file", path="table.parquet", span=4000),),
        compiled=SimpleNamespace(planned_checks=lambda: ()),
        ledger=ExecutionLedger(), executor=executor,
        envmap=EnvMap(task_prompt="text custody", workspace_root="/app"),
    )
    row = rows[0]
    assert row["bytes"] == len(raw)
    assert row["content_chars"] == len("hello π\n")
    assert row["text_decode_lossless"] is True
    ledger = ExecutionLedger()
    inspection = _register(
        ledger,
        VerifierInspectionRequest(request_id="text-strength", kind="read_file", path="table.parquet"),
        row | {"request_id": "text-strength"},
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection)
    assert receipt.payload["actual_evidence_class"] == "exact_contract"


class _AbsoluteBinarySnapshotExecutor:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def resolve_verifier_read_path(self, path: str) -> str:
        assert path == "/data/table.parquet"
        return path

    def read_verifier_file_bytes(self, path: str) -> bytes:
        assert path == "/data/table.parquet"
        return self.raw

    def read_verifier_file(self, path: str) -> str:
        raise AssertionError("guarded exact-byte verifier route should be preferred")


def test_s6_absolute_task_world_binary_read_uses_guarded_exact_byte_route() -> None:
    raw = b"PAR1\xff\x00task-world\x80payloadPAR1"
    rows = execute_verifier_inspection_requests(
        (VerifierInspectionRequest(
            request_id="absolute-binary", kind="read_file",
            path="/data/table.parquet", span=8192,
        ),),
        compiled=SimpleNamespace(planned_checks=lambda: ()),
        ledger=ExecutionLedger(),
        executor=_AbsoluteBinarySnapshotExecutor(raw),
        envmap=EnvMap(task_prompt="absolute binary custody", workspace_root="/app"),
    )
    row = rows[0]
    assert row["path"] == "/data/table.parquet"
    assert row["bytes"] == len(raw)
    assert row["content_hash"] == __import__("hashlib").sha256(raw).hexdigest()[:16]
    assert row["content_identity_basis"] == "captured_bytes"
    assert row["text_decode_lossless"] is False


def test_s6_completed_exact_contract_claim_is_rejected_for_binary_read_proxy() -> None:
    ledger = ExecutionLedger()
    inspection = _register(
        ledger,
        VerifierInspectionRequest(request_id="binary-completion", kind="read_file", path="table.parquet"),
        {
            "request_id": "binary-completion",
            "kind": "read_file",
            "path": "table.parquet",
            "bytes": 32,
            "content_chars": 24,
            "offset": 0,
            "span": 8192,
            "excerpt": "PAR1\ufffdsemantic-looking-data",
            "content_hash": "d" * 16,
            "content_identity_basis": "captured_bytes",
            "text_decode_lossless": False,
            "observation_origin": "executor_read",
        },
    )
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection)
    assert receipt.payload["actual_evidence_class"] == "metadata_proxy"
    result = parse_model_verifier_result({
        "verdict": "completed",
        "confidence": "high",
        "summary": "binary output is semantically correct",
        "findings": [],
        "missing_evidence_requests": [],
        "completion_evidence": [{
            "requirement": "binary output semantic content",
            "observed": "replacement-decoded bytes appear to contain expected values",
            "falsification_check": "compare decoded byte rendering",
            "inspection_refs": [inspection],
            "clause_ids": ["raw_task"],
            "proof_ids": [],
            "evidence_class": "exact_contract",
            "risk_refs": [],
            "requirement_status": "satisfied",
        }],
        "method_validity": None,
    })
    problem = _verdict_admissibility_problem(
        result,
        direct_refs={inspection},
        derived_refs=set(),
        actual_classes={inspection: receipt.payload["actual_evidence_class"]},
    )
    assert "below required evidence class exact_contract" in problem
    assert "metadata_proxy" in problem
