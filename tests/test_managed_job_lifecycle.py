from __future__ import annotations

from dataclasses import replace
import time
from types import SimpleNamespace

from aether.execution import JobProbeResult, MemoryExecutor, ProcessOrchestratorV2
from aether.inspection_registry import register_inspection_results
from aether.context_views import latest_solver_transition, latest_tool_receipt
from aether.kernel_turns import _update_world_from_receipt
from aether.ledger import ExecutionLedger, Receipt
from aether.proof_contract import (
    INDEPENDENT_ROUTE_KINDS, PROOF_KIND_REGISTRY, PROOF_REGISTRY_VERSION,
    compile_proof_requirements, evaluate_compiled_proof_requirements, proof_requirements_identity,
)
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ACTION_SCHEMA, FIXED_KERNEL_TOOL_SURFACE, ActionRequest, EnvMap
from aether.solver_progress import build_progress_receipt
from aether.submission_coherence import evaluate_submission_coherence
from aether.task_contract import TaskClause, TaskContract
from aether.world import WorldState
from aether.verifier_inspector import execute_verifier_inspection_requests, parse_verifier_inspection_requests


def _action(kind: str, *, target: str = "") -> ActionRequest:
    arguments = ({"service_name": "finite", "command": "sleep 1; exit 0"} if kind == "start_job" else {"target": target})
    return ActionRequest(
        action_id=kind, kind=kind, capability_id="managed_process", arguments=arguments,
        intent="observe the registered finite job", expected_observation="an exact lifecycle state",
        if_fail_next="inspect the registered launch receipt",
    )


def test_probe_job_is_first_class_read_only_action() -> None:
    assert dict(ACTION_SCHEMA)["probe_job"] == ("target",)
    assert "probe_job" in FIXED_KERNEL_TOOL_SURFACE


def test_memory_executor_reports_running_then_completed_generation() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    launch = ProcessOrchestratorV2().launch(_action("start_job"), 1, executor, workspace_root="/app", interactive=False)
    job_id = launch.payload["job_id"]
    running = executor.probe_job(job_id)
    assert running.found is True and running.status == "running" and running.completed is False
    handle = executor.processes[job_id]
    executor.processes[job_id] = replace(handle, live=False, status="completed", exit_code=0, detail="exited 0")
    completed = executor.probe_job(job_id)
    assert completed.status == "completed" and completed.completed is True
    assert completed.succeeded is True and completed.exit_code == 0
    assert completed.process_generation_verified is True


def test_orchestrator_probe_job_observation_is_successful_even_for_failed_job() -> None:
    class FailedJobExecutor(MemoryExecutor):
        def probe_job(self, target: str) -> JobProbeResult:
            return JobProbeResult(
                target=target, found=True, status="failed", completed=True, succeeded=False,
                exit_code=7, detail="exit 7", job_id="job-1", process_id="job-1",
                process_generation="gen-1", process_generation_verified=True, pid=123,
            )
    receipt = ProcessOrchestratorV2().probe_job(_action("probe_job", target="job-1"), 2, FailedJobExecutor(workspace_root="/app"))
    assert receipt.kind == "job_probe" and receipt.success is True
    assert receipt.payload["job_status"] == "failed"
    assert receipt.payload["job_succeeded"] is False and receipt.payload["exit_code"] == 7


def test_verifier_probe_job_is_exact_state_and_admits_completion_proof() -> None:
    ledger = ExecutionLedger()
    executor = MemoryExecutor(workspace_root="/app")
    launch = ProcessOrchestratorV2().launch(_action("start_job"), 1, executor, workspace_root="/app", interactive=False)
    job_id = launch.payload["job_id"]
    ledger.record(launch)
    executor.processes[job_id] = replace(executor.processes[job_id], live=False, status="completed", exit_code=0, detail="exited 0")
    requirements = compile_proof_requirements(({
        "proof_id": "proof_job_completed", "obligation_refs": ["job_completed"], "risk_refs": [],
        "proof_kind": "exact_state", "target_type": "outcome", "target_id": "job_completed",
        "acceptance_observation": "The registered managed job completed successfully.",
        "falsification_observation": "The job is running, failed, unknown, or unregistered.",
    },))
    identity = proof_requirements_identity(requirements)
    requests = parse_verifier_inspection_requests({
        "kind": "inspect", "requests": [{
            "request_id": "job-status", "kind": "probe_job", "target": job_id,
            "proof_ids": ["proof_job_completed"],
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests, compiled=SimpleNamespace(planned_checks=lambda: ()), ledger=ledger,
        executor=executor, envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    assert raw[0]["status"] == "completed" and raw[0]["job_exit_code"] == 0
    row = register_inspection_results(
        requests, raw, ledger=ledger, step=2, requester="model_verifier", executor=executor,
        overlay=None, packet_signature="packet", proof_contract_identity=identity,
    )[0]
    assert row["evidence_ceiling"] == "exact_contract"
    assert row["admissibility"] == "direct_admissible"
    decision = evaluate_compiled_proof_requirements(
        requirements, ledger, {"proof_job_completed": (row["inspection_id"],)},
        packet_signature="packet", proof_contract_identity=identity,
    )[0]
    assert decision.admitted is True


def test_unregistered_job_and_service_non_liveness_cannot_prove_completion() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    missing = executor.probe_job("53436")
    assert missing.found is False and missing.status == "unknown"
    service = ProcessOrchestratorV2().probe(_action("probe_job", target="53436"), 1, executor)
    assert service.kind == "service_probe" and service.success is False
    assert "completed" not in service.payload


def test_verifier_missing_job_is_valid_negative_observation_not_tooling_failure() -> None:
    ledger = ExecutionLedger()
    executor = MemoryExecutor(workspace_root="/app")
    requests = parse_verifier_inspection_requests({
        "kind": "inspect", "requests": [{
            "request_id": "missing-job", "kind": "probe_job", "target": "job-does-not-exist",
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests, compiled=SimpleNamespace(planned_checks=lambda: ()), ledger=ledger,
        executor=executor, envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    assert raw[0]["found"] is False
    assert raw[0]["success"] is False
    assert raw[0]["error"] == ""
    row = register_inspection_results(
        requests, raw, ledger=ledger, step=1, requester="model_verifier",
        executor=executor, overlay=None, packet_signature="packet",
    )[0]
    assert row["observation_valid"] is True
    assert row["observed_outcome_success"] is False
    assert row["admissibility"] == "direct_admissible"
    assert row["eligible_for_proof"] is False


def test_subprocess_executor_observes_exact_finite_job_completion(tmp_path) -> None:
    executor = SubprocessExecutor(str(tmp_path))
    launch = ProcessOrchestratorV2().launch(
        ActionRequest(
            action_id="start", kind="start_job", capability_id="managed_process",
            arguments={
                "service_name": "finite",
                "command": "python3 -c \"import time; time.sleep(0.1)\"",
            },
            intent="start one finite managed job",
            expected_observation="a registered job generation",
            if_fail_next="inspect launch failure",
        ),
        1, executor, workspace_root=str(tmp_path), interactive=False,
    )
    assert launch.success is True
    job_id = launch.payload["job_id"]
    deadline = time.monotonic() + 3.0
    observed = executor.probe_job(job_id)
    while observed.status == "running" and time.monotonic() < deadline:
        time.sleep(0.02)
        observed = executor.probe_job(job_id)
    assert observed.found is True
    assert observed.status == "completed"
    assert observed.completed is True
    assert observed.succeeded is True
    assert observed.exit_code == 0
    assert observed.process_generation == launch.payload["process_generation"]
    assert observed.process_generation_verified is True



def _terminal_job_receipt() -> tuple[ActionRequest, Receipt]:
    class CompletedJobExecutor(MemoryExecutor):
        def probe_job(self, target: str) -> JobProbeResult:
            return JobProbeResult(
                target=target, found=True, status="completed", completed=True,
                succeeded=True, exit_code=0, detail="exit 0", job_id="job-1",
                process_id="job-1", process_generation="gen-1",
                process_generation_verified=True,
                lifecycle_authority="host_process_handle", pid=123,
            )
    action = _action("probe_job", target="job-1")
    receipt = ProcessOrchestratorV2().probe_job(
        action, 2, CompletedJobExecutor(workspace_root="/app"),
    )
    return action, receipt


def test_terminal_probe_job_rearms_progress_and_submission() -> None:
    action, receipt = _terminal_job_receipt()
    ledger = ExecutionLedger()
    ledger.record(receipt)
    progress = build_progress_receipt(
        action, step=2, step_receipts=(receipt,), ledger=ledger,
    )
    ledger.record(progress)
    assert progress.payload["classification"] == "successful_result_no_state_change"
    assert "new_evidence" in progress.payload["progress_signals"]
    assert "verification" in progress.payload["progress_signals"]
    assert "requirement_evidence" in progress.payload["progress_signals"]
    assert evaluate_submission_coherence(ledger, current_step=3).allowed is True


def test_job_probe_reaches_transition_tool_and_world_state_views() -> None:
    action, receipt = _terminal_job_receipt()
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-1:start_job:process_launch", step=1,
        kind="process_launch", success=True, state_change=True,
        summary="registered finite job generation",
        payload={
            "process_id": "job-1", "job_id": "job-1", "service_name": "finite",
            "process_generation": "gen-1", "live": True,
            "launch_mode": "background_job",
        },
    ))
    ledger.record(Receipt(
        receipt_id="step-2:probe_job:solver_decision_state", step=2,
        kind="solver_decision_state", success=True, summary="observe job",
        payload={
            "current_subgoal": "observe job", "evidence_gap": "job state unknown",
            "action_id": action.action_id, "action_kind": action.kind,
            "intent": action.intent, "expected_observation": action.expected_observation,
            "if_fail_next": action.if_fail_next, "mutation_generation": 0,
        },
    ))
    ledger.record(receipt)
    progress = build_progress_receipt(action, step=2, step_receipts=(receipt,), ledger=ledger)
    ledger.record(progress)
    latest = latest_tool_receipt(ledger)
    assert latest["kind"] == "job_probe"
    assert latest["job_status"] == "completed"
    assert latest["process_generation"] == "gen-1"
    assert ledger.recent_progress(1)[0].kind == "job_probe"
    assert ledger.no_progress_streak() == 0
    transition = latest_solver_transition(ledger)
    assert transition is not None
    assert transition["results"][0]["job_id"] == "job-1"
    assert transition["results"][0]["job_status"] == "completed"
    assert transition["results"][0]["process_generation"] == "gen-1"
    contract = TaskContract.create("Observe the job.", (TaskClause("job", "The job completed."),))
    world = WorldState(task_contract=contract)
    _update_world_from_receipt(world, receipt, step=2, ledger=ledger)
    snapshot = world.dynamic_snapshot()
    assert snapshot["jobs"]["job-1"]["state"] == "completed"
    assert snapshot["latest_result"]["kind"] == "job_probe"


def test_probe_job_proof_rejects_wrong_launch_generation_substitution() -> None:
    ledger = ExecutionLedger()
    executor = MemoryExecutor(workspace_root="/app")
    launch = ProcessOrchestratorV2().launch(
        _action("start_job"), 1, executor, workspace_root="/app", interactive=False,
    )
    ledger.record(launch)
    other_action = ActionRequest(
        action_id="start-other", kind="start_job", capability_id="managed_process",
        arguments={"service_name": "other", "command": "sleep 1; exit 0"},
        intent="launch another job", expected_observation="another generation",
        if_fail_next="inspect launch failure",
    )
    other_launch = ProcessOrchestratorV2().launch(
        other_action, 1, executor, workspace_root="/app", interactive=False,
    )
    ledger.record(other_launch)
    requirements = compile_proof_requirements(({
        "proof_id": "proof_job_completed", "obligation_refs": ["job_completed"], "risk_refs": [],
        "proof_kind": "exact_state", "target_type": "outcome", "target_id": "job_completed",
        "acceptance_observation": "The original registered job completed.",
        "falsification_observation": "A different job or generation was observed.",
    },))
    identity = proof_requirements_identity(requirements)
    requests = parse_verifier_inspection_requests({
        "kind": "inspect", "requests": [{
            "request_id": "job-status", "kind": "probe_job",
            "target": launch.payload["job_id"], "proof_ids": ["proof_job_completed"],
        }],
    })
    wrong = [{
        "request_id": "job-status", "kind": "probe_job", "target": launch.payload["job_id"],
        "found": True, "job_id": other_launch.payload["job_id"],
        "process_id": other_launch.payload["process_id"],
        "status": "completed", "completed": True, "job_succeeded": True,
        "job_exit_code": 0,
        "process_generation": other_launch.payload["process_generation"],
        "process_generation_verified": True, "lifecycle_authority": "host_process_handle",
        "observation_origin": "executor_probe", "success": True,
    }]
    row = register_inspection_results(
        requests, wrong, ledger=ledger, step=2, requester="model_verifier",
        executor=executor, overlay=None, packet_signature="packet",
        proof_contract_identity=identity,
    )[0]
    assert row["admissibility"] == "exploratory"
    assert row["lifecycle_binding_verified"] is False
    decision = evaluate_compiled_proof_requirements(
        requirements, ledger, {"proof_job_completed": (row["inspection_id"],)},
        packet_signature="packet", proof_contract_identity=identity,
    )[0]
    assert decision.admitted is False


def test_probe_job_is_exact_state_only_not_independent_derivation() -> None:
    assert PROOF_REGISTRY_VERSION == "aether-proof-registry.v5"
    assert "probe_job" in PROOF_KIND_REGISTRY["exact_state"].eligible_route_kinds
    assert "probe_job" not in INDEPENDENT_ROUTE_KINDS
