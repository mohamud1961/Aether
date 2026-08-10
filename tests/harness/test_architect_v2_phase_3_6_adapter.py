from __future__ import annotations

import json
from dataclasses import replace

import pytest

from aether.architect_v2_adapter import adapt_architect_v2_to_runtime
from aether.architect_v2_contract import (
    ArchitectV2CompatibilityError,
    assert_current_runtime_compatibility_is_ready,
)
from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger
from aether.proof_contract import (
    proof_requirements_identity,
    record_shadow_proof_evidence_admission,
)
from aether.runtime_ir import (
    CapabilityDescriptor,
    CompletionPolicy,
    EnvMap,
    RuntimeConfigIR,
)
from aether.task_contract import TaskClause, TaskContract
from aether.verifier import CompletionEvidenceEntry, ModelVerifierResult
from aether.verifier_inspector import VerifierInspectionRequest
from aether.verifier_packets import build_verifier_packet


class _Executor:
    pass


def _env() -> EnvMap:
    return EnvMap(
        task_prompt=(
            "Implement the KVStore task. SetValRequest uses int32 val and the service "
            "must complete a live set/get round trip."
        ),
        workspace_root="/app",
        visible_files=("kv-store.proto", "server.py"),
        capabilities={
            "filesystem": CapabilityDescriptor(
                capability_id="filesystem",
                summary="read and write workspace files",
                tool_names=("read_file", "write_file"),
            ),
            "shell": CapabilityDescriptor(
                capability_id="shell",
                summary="run local commands",
                tool_names=("run_command",),
            ),
        },
        task_metadata={"required_artifacts": ["server.py"]},
    )


def _baseline() -> RuntimeConfigIR:
    return RuntimeConfigIR(
        architect_summary="",
        solver_identity_prompt="",
        selected_capabilities=("filesystem", "shell"),
        completion_policy=CompletionPolicy(
            require_authoritative_check=False,
            allow_evidence_fallback=True,
            require_all_obligations=True,
            require_recent_progress=False,
            require_clean_integrity=True,
        ),
    )


def _payload(*, one_proof: bool = False) -> dict[str, object]:
    obligations = [
        {
            "obligation_id": "interface_contract",
            "statement": "The generated interface preserves SetValRequest.val as int32.",
            "fact_refs": ["fact_proto_field"],
        },
        {
            "obligation_id": "round_trip_behavior",
            "statement": "A fresh client can set and retrieve the same integer value.",
            "fact_refs": ["fact_service_port"],
        },
    ]
    proof_intent = [{
        "proof_id": "proof_all" if one_proof else "proof_interface",
        "obligation_refs": ["interface_contract", "round_trip_behavior"] if one_proof else ["interface_contract"],
        "risk_refs": ["port_only"] if one_proof else [],
        "proof_kind": "exact_state",
        "acceptance_observation": "Current generated state preserves the exact declared field contract.",
        "falsification_observation": "A missing, renamed, or differently typed field falsifies the contract.",
    }]
    if not one_proof:
        proof_intent.append({
            "proof_id": "proof_round_trip",
            "obligation_refs": ["round_trip_behavior"],
            "risk_refs": ["port_only"],
            "proof_kind": "public_behavior",
            "acceptance_observation": "A current independent client stores and retrieves the same integer.",
            "falsification_observation": "Connection failure or a different returned value falsifies behavior.",
        })
    return {
        "schema_version": "aether_architect.v2",
        "method_constraints": [],
        "task_contract": {
            "exact_facts": [
                {
                    "fact_id": "fact_proto_field",
                    "statement": "SetValRequest contains int32 val = 2.",
                    "source": "task_prompt",
                    "verbatim_anchors": ["SetValRequest", "int32 val = 2"],
                },
                {
                    "fact_id": "fact_service_port",
                    "statement": "The KVStore service listens on port 5328.",
                    "source": "visible_material",
                    "verbatim_anchors": ["5328"],
                },
            ],
            "obligations": obligations,
        },
        "proof_intent": proof_intent,
        "solver_design": {
            "mission": "Implement a working KVStore service without changing the declared interface.",
            "strategy": "Inspect the declaration and generated code, repair causally, then exercise the live interface.",
            "priorities": ["Preserve exact protobuf names and types."],
            "self_verification_emphasis": ["Use a fresh client round trip before submitting."],
        },
        "verifier_design": {
            "mission": "Independently determine whether the generated interface and live service satisfy the task.",
            "verification_strategy": "Inspect exact generated state separately from live behavior.",
            "false_positive_risks": [{
                "risk_id": "port_only",
                "statement": "A listening port does not prove RPC semantics.",
                "obligation_refs": ["round_trip_behavior"],
            }],
        },
        "information_emphasis": [{
            "topic": "protobuf field spelling",
            "rationale": "val and value are easy to confuse.",
            "fact_refs": ["fact_proto_field"],
            "obligation_refs": ["interface_contract"],
        }],
    }


def _compile(payload: dict[str, object]):
    env = _env()
    adapted = adapt_architect_v2_to_runtime(payload, baseline=_baseline(), envmap=env)
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(env))
    return adapted, compiler.compile(adapted.runtime_ir, env)


def test_v1_task_contract_payload_is_unchanged_when_not_enriched() -> None:
    contract = TaskContract.create("Do the task", (TaskClause("task:prompt", "Do the task"),))
    assert contract.as_payload() == {
        "raw_task_prompt": "Do the task",
        "clauses": [{"clause_id": "task:prompt", "text": "Do the task", "exact_atoms": []}],
    }


def test_adapter_realizes_existing_owners_without_v1_semantic_mirrors() -> None:
    env = _env()
    baseline = _baseline()
    adapted = adapt_architect_v2_to_runtime(_payload(), baseline=baseline, envmap=env)
    ir = adapted.runtime_ir

    assert adapted.status == "shadow_only"
    assert ir.selected_capabilities == baseline.selected_capabilities
    assert ir.context_policy == baseline.context_policy
    assert ir.process_policy == baseline.process_policy
    assert ir.completion_policy == baseline.completion_policy
    assert ir.visible_contract == ()
    assert ir.inspection_plan == ()
    assert ir.proof_plan == ()
    assert ir.semantic_clause_coverage == ()
    assert ir.semantic_verifier_checks == ()
    assert ir.success_definition == ""
    assert ir.task_contract is adapted.task_contract
    assert ir.task_contract.contract_identity == adapted.realization_manifest["task_contract_identity"]
    assert adapted.realization_manifest["task_contract_sha256"] == ir.task_contract.contract_identity
    assert "protobuf field spelling" in ir.solver_identity_prompt
    assert "protobuf field spelling" not in ir.verifier_identity_prompt
    assert "A fresh client can set" not in ir.solver_identity_prompt
    assert "A fresh client can set" not in ir.verifier_identity_prompt
    assert ir.false_positive_risks == (
        "A listening port does not prove RPC semantics.",
    )
    assert "A listening port does not prove RPC semantics." not in ir.verifier_identity_prompt
    assert adapted.realization_manifest["structured_false_positive_risk_count"] == 1
    dispositions = {
        row["path"]: row["owner"]
        for row in adapted.realization_manifest["field_dispositions"]
    }
    assert dispositions[
        "verifier_design.false_positive_risks[0].statement"
    ] == "structured_false_positive_risks"


def test_structured_v2_risks_reach_compiler_and_verifier_packet_once() -> None:
    adapted, compiled = _compile(_payload())
    risk = "A listening port does not prove RPC semantics."
    assert adapted.runtime_ir.false_positive_risks == (risk,)
    assert compiled.false_positive_risks == (risk,)
    packet = build_verifier_packet(compiled, ExecutionLedger(), envmap=_env())
    assert packet["evidence_requirements"]["false_positive_risks"] == [risk]
    assert risk not in adapted.runtime_ir.verifier_identity_prompt
    assert risk not in compiled.verifier_identity_prompt


def test_sparse_v2_contract_keeps_identity_and_empty_field_dispositions() -> None:
    payload = _payload()
    payload["task_contract"]["exact_facts"] = []
    for obligation in payload["task_contract"]["obligations"]:
        obligation.pop("fact_refs", None)
    payload.pop("information_emphasis", None)
    adapted = adapt_architect_v2_to_runtime(payload, baseline=_baseline(), envmap=_env())
    task_payload = adapted.task_contract.as_payload()
    paths = {
        item["path"] for item in adapted.realization_manifest["field_dispositions"]
    }
    assert task_payload["schema_version"] == "task_contract.v2"
    assert task_payload["contract_identity"] == adapted.task_contract.contract_identity
    assert "task_contract.exact_facts" in paths


def test_information_emphasis_realizes_fact_and_obligation_refs() -> None:
    adapted = adapt_architect_v2_to_runtime(
        _payload(), baseline=_baseline(), envmap=_env()
    )
    prompt = adapted.runtime_ir.solver_identity_prompt
    assert "facts: fact_proto_field" in prompt
    assert "obligations: interface_contract" in prompt


def test_v2_compiler_has_no_legacy_plan_warnings() -> None:
    env = _env()
    adapted = adapt_architect_v2_to_runtime(
        _payload(), baseline=_baseline(), envmap=env
    )
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(env))
    codes = {issue.code for issue in compiler.validate(adapted.runtime_ir, env)}
    assert "missing_inspection_plan" not in codes
    assert "missing_proof_plan" not in codes


def test_oversized_solver_role_prompt_fails_closed() -> None:
    payload = _payload()
    payload["solver_design"]["priorities"] = ["x" * 4000] * 4
    with pytest.raises(ArchitectV2CompatibilityError, match="Solver role prompt exceeds"):
        adapt_architect_v2_to_runtime(payload, baseline=_baseline(), envmap=_env())


def test_non_neutral_v1_semantic_baseline_fails_closed() -> None:
    baseline = replace(_baseline(), visible_contract=({"owner": "legacy"},))
    with pytest.raises(ArchitectV2CompatibilityError, match="semantic-neutral baseline"):
        adapt_architect_v2_to_runtime(_payload(), baseline=baseline, envmap=_env())


def test_compiler_uses_same_task_contract_identity_for_solver_and_verifier() -> None:
    adapted, compiled = _compile(_payload())
    sections = dict(compiled.stable_prefix_sections)
    task_payload = json.loads(sections["task_contract"])

    assert compiled.task_contract is adapted.task_contract
    assert compiled.task_contract_identity == adapted.task_contract.contract_identity
    assert task_payload["contract_identity"] == compiled.task_contract_identity
    assert "task_prompt" not in sections
    assert "architect_visible_contract" not in sections
    assert "solver_clause_contract" not in sections
    assert "proof_plan" not in sections
    assert compiled.verifier_identity_prompt not in "\n".join(sections.values())
    assert "field_dispositions" not in sections["config_realization"]

    packet = build_verifier_packet(compiled, ExecutionLedger(), envmap=_env())
    assert packet["task_contract_identity"] == compiled.task_contract_identity
    assert packet["task_contract"]["contract_identity"] == compiled.task_contract_identity
    assert "protobuf field spelling" not in json.dumps(packet, sort_keys=True)


def test_v2_obligations_replace_extracted_semantics_but_keep_integrity() -> None:
    _adapted, compiled = _compile(_payload())
    ids = {item.obligation_id for item in compiled.objective_graph.obligations}
    assert ids == {"interface_contract", "round_trip_behavior", "integrity:clean"}
    assert "artifact:server.py" not in ids
    assert compiled.objective_graph.deliverables == ()
    assert compiled.objective_graph.service_requirements == ()
    assert compiled.objective_graph.thresholds == ()
    assert compiled.objective_graph.output_schema == {}


def test_admitted_completed_proof_closes_canonical_task_obligations() -> None:
    adapted, compiled = _compile(_payload(one_proof=True))
    ledger = ExecutionLedger()
    ledger.ensure_objective(compiled.objective_graph)
    identity = proof_requirements_identity(compiled.proof_requirements)
    request = VerifierInspectionRequest(
        request_id="read-generated",
        kind="read_file",
        path="kv_store_pb2.py",
        proof_ids=("proof_all",),
    )
    inspection_id = register_inspection_results(
        (request,),
        ({
            "request_id": "read-generated",
            "kind": "read_file",
            "path": "kv_store_pb2.py",
            "bytes": 12,
            "offset": 0,
            "span": 4000,
            "excerpt": "generated-v1",
            "content_hash": "a" * 16,
            "observation_origin": "executor_read",
        },),
        ledger=ledger,
        step=2,
        requester="model_verifier",
        executor=_Executor(),
        overlay=_Executor(),
        packet_signature="packet-current",
        proof_contract_identity=identity,
    )[0]["inspection_id"]
    result = ModelVerifierResult(
        verdict="completed",
        summary="current state satisfies both obligations",
        completion_evidence=(CompletionEvidenceEntry(
            requirement="both obligations are satisfied",
            observed="the current generated interface matches the contract",
            falsification_check="a mismatched field would falsify it",
            inspection_refs=(inspection_id,),
            proof_ids=("proof_all",),
        ),),
    )
    admission = record_shadow_proof_evidence_admission(
        ledger,
        result=result,
        requirements=compiled.proof_requirements,
        step=2,
        packet_signature="packet-current",
        proof_contract_identity=identity,
        verifier_result_receipt_id="step-2:model_verifier",
    )
    assert admission.admitted is True
    assert {"interface_contract", "round_trip_behavior"}.issubset(
        set(ledger.satisfied_obligation_ids())
    )
    assert adapted.task_contract.clause_ids == frozenset({"interface_contract", "round_trip_behavior"})


def test_production_dispatch_guard_remains_closed() -> None:
    with pytest.raises(ArchitectV2CompatibilityError, match="production dispatch remains blocked"):
        assert_current_runtime_compatibility_is_ready()


def _faceted_end_to_end_payload() -> dict[str, object]:
    payload = _payload()
    payload["task_contract"]["obligations"] = [{
        "obligation_id": "end_to_end",
        "statement": "The declared KVStore interface and live round trip satisfy the task.",
        "fact_refs": ["fact_proto_field", "fact_service_port"],
    }]
    payload["proof_intent"] = [
        {
            "proof_id": "proof_exact",
            "obligation_refs": ["end_to_end"],
            "risk_refs": ["single_facet"],
            "proof_kind": "exact_state",
            "acceptance_observation": "Current generated state preserves the exact declared interface.",
            "falsification_observation": "A missing, renamed, or differently typed field falsifies the task.",
        },
        {
            "proof_id": "proof_behavior",
            "obligation_refs": ["end_to_end"],
            "risk_refs": ["single_facet"],
            "proof_kind": "public_behavior",
            "acceptance_observation": "A fresh client stores and retrieves the same integer.",
            "falsification_observation": "Connection failure or a different returned value falsifies the task.",
        },
    ]
    payload["information_emphasis"] = []
    payload["verifier_design"]["false_positive_risks"] = [{
        "risk_id": "single_facet",
        "statement": "Either exact interface state or live behavior alone is insufficient.",
        "obligation_refs": ["end_to_end"],
    }]
    return payload


def _register_faceted_evidence(ledger, compiled, *, include_behavior: bool):
    identity = proof_requirements_identity(compiled.proof_requirements)
    exact_request = VerifierInspectionRequest(
        request_id="read-generated-facet",
        kind="read_file",
        path="kv_store_pb2.py",
        proof_ids=("proof_exact",),
    )
    exact_id = register_inspection_results(
        (exact_request,),
        ({
            "request_id": "read-generated-facet",
            "kind": "read_file",
            "path": "kv_store_pb2.py",
            "bytes": 12,
            "offset": 0,
            "span": 4000,
            "excerpt": "generated-v2",
            "content_hash": "a" * 16,
            "observation_origin": "executor_read",
        },),
        ledger=ledger,
        step=2,
        requester="model_verifier",
        executor=_Executor(),
        overlay=_Executor(),
        packet_signature="packet-faceted",
        proof_contract_identity=identity,
    )[0]["inspection_id"]
    entries = [CompletionEvidenceEntry(
        requirement="the generated interface matches",
        observed="the exact generated state matches the declaration",
        falsification_check="a field mismatch would falsify it",
        inspection_refs=(exact_id,),
        proof_ids=("proof_exact",),
    )]
    if include_behavior:
        behavior_request = VerifierInspectionRequest(
            request_id="probe-live-facet",
            kind="probe_http",
            target="http://127.0.0.1:5328",
            proof_ids=("proof_behavior",),
        )
        behavior_id = register_inspection_results(
            (behavior_request,),
            ({
                "request_id": "probe-live-facet",
                "kind": "probe_http",
                "url": "http://127.0.0.1:5328",
                "status_code": 200,
                "response_observed": True,
                "observation_origin": "executor_probe",
            },),
            ledger=ledger,
            step=2,
            requester="model_verifier",
            executor=_Executor(),
            overlay=_Executor(),
            packet_signature="packet-faceted",
            proof_contract_identity=identity,
        )[0]["inspection_id"]
        entries.append(CompletionEvidenceEntry(
            requirement="the live round trip works",
            observed="a fresh public probe observed the required behavior",
            falsification_check="a failed probe would falsify it",
            inspection_refs=(behavior_id,),
            proof_ids=("proof_behavior",),
        ))
    result = ModelVerifierResult(
        verdict="completed",
        summary="submitted faceted proof evidence",
        completion_evidence=tuple(entries),
    )
    return record_shadow_proof_evidence_admission(
        ledger,
        result=result,
        requirements=compiled.proof_requirements,
        step=2,
        packet_signature="packet-faceted",
        proof_contract_identity=identity,
        verifier_result_receipt_id="step-2:model_verifier",
    )


def test_faceted_obligation_stays_open_until_every_linked_proof_is_admitted() -> None:
    adapted, compiled = _compile(_faceted_end_to_end_payload())
    assert len(compiled.proof_requirements) == 2
    assert all(
        requirement.obligation_ids == ("end_to_end",)
        for requirement in compiled.proof_requirements
    )

    incomplete = ExecutionLedger()
    incomplete.ensure_objective(compiled.objective_graph)
    incomplete_admission = _register_faceted_evidence(
        incomplete, compiled, include_behavior=False
    )
    assert incomplete_admission.admitted is False
    assert "end_to_end" not in incomplete.satisfied_obligation_ids()

    complete = ExecutionLedger()
    complete.ensure_objective(compiled.objective_graph)
    complete_admission = _register_faceted_evidence(
        complete, compiled, include_behavior=True
    )
    assert complete_admission.admitted is True
    assert "end_to_end" in complete.satisfied_obligation_ids()
    assert adapted.task_contract.clause_ids == frozenset({"end_to_end"})
