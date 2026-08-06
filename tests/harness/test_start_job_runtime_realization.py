from __future__ import annotations

from types import SimpleNamespace

from aether.automatic_memory import automatic_memory_receipt
from aether.envmap_builder import build_envmap_from_task
from aether.execution import MemoryExecutor, ProcessOrchestratorV2
from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger
from aether.proof_contract import (
    compile_proof_requirements,
    evaluate_compiled_proof_requirements,
    proof_requirements_identity,
)
from aether.runtime_ir import (
    ACTION_SCHEMA,
    FIXED_KERNEL_TOOL_SURFACE,
    ActionRequest,
    EnvMap,
)
from aether.verifier_inspector import (
    execute_verifier_inspection_requests,
    parse_verifier_inspection_requests,
)


def _action(kind: str, action_id: str = "launch") -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id="managed_process",
        arguments={"service_name": "server_ok", "command": "python3 server_ok.py"},
        intent="start the required managed service",
        expected_observation="a durable registered process identity",
        if_fail_next="inspect the launch failure and pivot",
    )


def _requirements():
    return compile_proof_requirements((
        {
            "proof_id": "proof_start_job",
            "obligation_refs": ["service_persists"],
            "risk_refs": [],
            "proof_kind": "exact_state",
            "target_type": "constraint",
            "target_id": "use_start_job",
            "acceptance_observation": "Immutable action history identifies start_job.",
            "falsification_observation": "No start_job launch exists.",
        },
        {
            "proof_id": "proof_persistence",
            "obligation_refs": ["service_persists"],
            "risk_refs": [],
            "proof_kind": "exact_state",
            "target_type": "outcome",
            "target_id": "service_persists",
            "acceptance_observation": "The kernel job contract guarantees persistence after the loop exits.",
            "falsification_observation": "The launch contract has no post-loop persistence guarantee.",
        },
    ))


def test_start_job_is_a_first_class_fixed_kernel_action(tmp_path) -> None:
    schema = dict(ACTION_SCHEMA)
    assert schema["start_job"] == ("service_name", "command")
    assert "start_job" in FIXED_KERNEL_TOOL_SURFACE
    env = build_envmap_from_task(str(tmp_path), "Start a service with start_job.")
    assert "start_job" in env.capabilities["managed_process"].tool_names
    affordances = env.task_metadata["available_action_affordances"]
    assert any(row["action"] == "start_job" and row["available"] for row in affordances)


def test_start_job_receipt_preserves_identity_and_lifecycle_contract() -> None:
    receipt = ProcessOrchestratorV2().launch(
        _action("start_job"),
        1,
        MemoryExecutor(workspace_root="/app"),
        workspace_root="/app",
        interactive=False,
    )
    assert receipt.kind == "process_launch"
    assert receipt.success is True
    assert receipt.payload["launch_tool"] == "start_job"
    assert receipt.payload["launch_mode"] == "background_job"
    assert receipt.payload["detached"] is True
    assert receipt.payload["job_id"] == receipt.payload["process_id"]
    assert receipt.payload["contract_guarantees"] == [
        "detached_background_job",
        "persists_after_agent_loop_exit",
    ]


def test_automatic_memory_does_not_confuse_launch_process_with_start_job() -> None:
    env = EnvMap(task_prompt="task", workspace_root="/app")
    ledger = ExecutionLedger()
    executor = MemoryExecutor(workspace_root="/app")
    ledger.record(ProcessOrchestratorV2().launch(
        _action("launch_process", "ordinary"), 1, executor,
        workspace_root="/app", interactive=False,
    ))
    assert automatic_memory_receipt(
        _action("start_job", "durable"), step=2, envmap=env, ledger=ledger,
    ) is None
    ledger.record(ProcessOrchestratorV2().launch(
        _action("start_job", "durable"), 2, executor,
        workspace_root="/app", interactive=False,
    ))
    memory = automatic_memory_receipt(
        _action("start_job", "repeat"), step=3, envmap=env, ledger=ledger,
    )
    assert memory is not None
    assert memory.payload["target"]["action_kind"] == "start_job"
    assert memory.payload["match_count"] == 1


def _registered_action_history(*, kind: str):
    ledger = ExecutionLedger()
    executor = MemoryExecutor(workspace_root="/app")
    ledger.record(ProcessOrchestratorV2().launch(
        _action(kind), 1, executor, workspace_root="/app", interactive=False,
    ))
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "launch-history",
            "kind": "inspect_action_receipts",
            "receipt_kind": "process_launch",
            "limit": 64,
            "clause_ids": ["use_start_job"],
            "proof_ids": ["proof_start_job", "proof_persistence"],
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests,
        compiled=SimpleNamespace(planned_checks=lambda: ()),
        ledger=ledger,
        executor=executor,
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    requirements = _requirements()
    identity = proof_requirements_identity(requirements)
    enriched = register_inspection_results(
        requests,
        raw,
        ledger=ledger,
        step=2,
        requester="model_verifier",
        executor=executor,
        overlay=None,
        packet_signature="packet",
        proof_contract_identity=identity,
    )
    return ledger, requirements, identity, enriched[0]


def test_complete_start_job_history_admits_constraint_and_persistence_proofs() -> None:
    ledger, requirements, identity, row = _registered_action_history(kind="start_job")
    inspection_id = row["inspection_id"]
    record = next(item for item in ledger.all_receipts() if item.receipt_id == inspection_id)
    assert record.payload["admissibility"] == "direct_admissible"
    assert record.payload["action_contract_guarantees"] == [
        "detached_background_job",
        "persists_after_agent_loop_exit",
    ]
    decisions = evaluate_compiled_proof_requirements(
        requirements,
        ledger,
        {
            "proof_start_job": (inspection_id,),
            "proof_persistence": (inspection_id,),
        },
        packet_signature="packet",
        proof_contract_identity=identity,
    )
    assert [item.admitted for item in decisions] == [True, True]


def test_ordinary_launch_history_cannot_prove_post_loop_persistence() -> None:
    ledger, requirements, identity, row = _registered_action_history(kind="launch_process")
    inspection_id = row["inspection_id"]
    decisions = evaluate_compiled_proof_requirements(
        requirements,
        ledger,
        {
            "proof_start_job": (inspection_id,),
            "proof_persistence": (inspection_id,),
        },
        packet_signature="packet",
        proof_contract_identity=identity,
    )
    assert decisions[0].admitted is True  # Mechanical constraint route; Verifier judges mismatch.
    assert decisions[1].admitted is False
    assert decisions[1].code == "proof_evidence_not_admitted"


def test_final_verdict_can_select_unbound_complete_action_history() -> None:
    ledger = ExecutionLedger()
    executor = MemoryExecutor(workspace_root="/app")
    ledger.record(ProcessOrchestratorV2().launch(
        _action("start_job"), 1, executor, workspace_root="/app", interactive=False,
    ))
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "launch-history",
            "kind": "inspect_action_receipts",
            "receipt_kind": "process_launch",
            "limit": 64,
            "clause_ids": ["use_start_job"],
            "proof_ids": [],
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests,
        compiled=SimpleNamespace(planned_checks=lambda: ()),
        ledger=ledger,
        executor=executor,
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    requirements = _requirements()
    identity = proof_requirements_identity(requirements)
    row = register_inspection_results(
        requests,
        raw,
        ledger=ledger,
        step=2,
        requester="model_verifier",
        executor=executor,
        overlay=None,
        packet_signature="packet",
        proof_contract_identity=identity,
    )[0]
    inspection_id = row["inspection_id"]
    decisions = evaluate_compiled_proof_requirements(
        requirements,
        ledger,
        {
            "proof_start_job": (inspection_id,),
            "proof_persistence": (inspection_id,),
        },
        packet_signature="packet",
        proof_contract_identity=identity,
    )
    assert [item.admitted for item in decisions] == [True, True]


def test_action_history_constraint_target_must_match_bound_clause() -> None:
    ledger = ExecutionLedger()
    executor = MemoryExecutor(workspace_root="/app")
    ledger.record(ProcessOrchestratorV2().launch(
        _action("start_job"), 1, executor, workspace_root="/app", interactive=False,
    ))
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "wrong-history",
            "kind": "inspect_action_receipts",
            "receipt_kind": "process_launch",
            "limit": 64,
            "clause_ids": ["different_constraint"],
            "proof_ids": [],
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests,
        compiled=SimpleNamespace(planned_checks=lambda: ()),
        ledger=ledger,
        executor=executor,
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    requirements = _requirements()[:1]
    identity = proof_requirements_identity(requirements)
    row = register_inspection_results(
        requests,
        raw,
        ledger=ledger,
        step=2,
        requester="model_verifier",
        executor=executor,
        overlay=None,
        packet_signature="packet",
        proof_contract_identity=identity,
    )[0]
    decision = evaluate_compiled_proof_requirements(
        requirements,
        ledger,
        {"proof_start_job": (row["inspection_id"],)},
        packet_signature="packet",
        proof_contract_identity=identity,
    )[0]
    assert decision.admitted is False
    assert decision.code == "proof_evidence_not_admitted"
