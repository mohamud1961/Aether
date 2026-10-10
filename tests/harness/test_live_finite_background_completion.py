from __future__ import annotations

from aether.completion import CompletionGate
from aether.ledger import ExecutionLedger, Receipt
from aether.runtime_ir import (
    BootstrapPolicy,
    CompiledRuntime,
    CompletionPolicy,
    ContextPolicy,
    EvalIndex,
    HelperToolPolicy,
    ObjectiveGraph,
    ProcessPolicy,
    RefusalPolicy,
    ServiceRequirement,
)


def _compiled(objective_graph: ObjectiveGraph | None = None) -> CompiledRuntime:
    return CompiledRuntime(
        task_prompt="test task",
        env_digest="env",
        objective_graph=objective_graph or ObjectiveGraph(),
        eval_index=EvalIndex(),
        selected_capabilities=(),
        stable_prefix_sections=(),
        context_policy=ContextPolicy(),
        process_policy=ProcessPolicy(),
        helper_tool_policy=HelperToolPolicy(),
        bootstrap_policy=BootstrapPolicy(),
        completion_policy=CompletionPolicy(),
        refusal_policy=RefusalPolicy(),
        enforced_monitors=(),
        check_plan_ids=(),
        forbidden_paths=(),
    )


def _record_evidence(
    ledger: ExecutionLedger,
    *,
    step: int,
    receipt_id: str,
    kind: str = "check_result",
    success: bool = True,
) -> None:
    payload = {**ledger.current_snapshot_binding_payload()}
    if kind == "check_result":
        payload.update({"check_id": receipt_id, "passed": success})
    elif kind == "run_command":
        payload.update({
            "command": "python validate.py",
            "exit_code": 0 if success else 1,
            "timed_out": False,
        })
    ledger.record(Receipt(
        receipt_id=receipt_id,
        step=step,
        kind=kind,
        success=success,
        summary="post-job evidence",
        payload=payload,
    ))


def _record_claim(
    ledger: ExecutionLedger,
    *,
    step: int,
    evidence_receipt_ids: tuple[str, ...] = (),
) -> None:
    generation = ledger.task_state_generation()
    ledger.record(Receipt(
        receipt_id=f"claim-{step}",
        step=step,
        kind="primary_submission_claim",
        success=True,
        summary="candidate ready",
        payload={
            "claim_id": "claim",
            "claim": "candidate ready",
            "evidence_refs": [f"evidence:{index:016x}" for index, _ in enumerate(evidence_receipt_ids, 1)],
            "evidence_receipt_ids": list(evidence_receipt_ids),
            "evidence_bindings": [
                {
                    "receipt_id": receipt_id,
                    "role": "current_anchor",
                    "task_state_generation": generation,
                }
                for receipt_id in evidence_receipt_ids
            ],
            "current_anchor_count": len(evidence_receipt_ids),
            **ledger.current_snapshot_binding_payload(),
        },
    ))


def _launch_job(
    ledger: ExecutionLedger,
    *,
    process_id: str = "job-1",
    name: str = "finite",
    generation: str = "gen-1",
    step: int = 1,
) -> None:
    ledger.record(Receipt(
        receipt_id=f"launch-{process_id}",
        step=step,
        kind="process_launch",
        success=True,
        summary="started detached job",
        state_change=True,
        payload={
            "process_id": process_id,
            "service_name": name,
            "command": "python validate.py",
            "launch_mode": "background_job",
            "detached": True,
            "live": True,
            "job_status": "running",
            "process_generation": generation,
        },
    ))


def _probe_job(
    ledger: ExecutionLedger,
    *,
    status: str,
    completed: bool,
    succeeded: bool | None,
    exit_code: int | None,
    step: int,
    process_id: str = "job-1",
    generation: str = "gen-1",
) -> None:
    ledger.record(Receipt(
        receipt_id=f"probe-{process_id}-{step}",
        step=step,
        kind="job_probe",
        success=True,
        summary=f"job {status}",
        payload={
            "job_id": process_id,
            "process_id": process_id,
            "job_status": status,
            "completed": completed,
            "job_succeeded": succeeded,
            "exit_code": exit_code,
            "process_generation": generation,
            "process_generation_verified": True,
        },
    ))


def _stop_job(ledger: ExecutionLedger, *, step: int = 2, process_id: str = "job-1") -> None:
    ledger.record(Receipt(
        receipt_id=f"stop-{process_id}-{step}",
        step=step,
        kind="process_stop",
        success=True,
        summary="confirmed stop",
        state_change=True,
        payload={
            "process_id": process_id,
            "service_name": process_id,
            "live": False,
        },
    ))


def _codes(ledger: ExecutionLedger, graph: ObjectiveGraph | None = None) -> set[str]:
    return {
        item.code
        for item in CompletionGate().evaluate(_compiled(graph), ledger, []).blockers
    }


def test_running_finite_background_job_blocks_completion() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _record_evidence(ledger, step=2, receipt_id="current")
    _record_claim(ledger, step=3, evidence_receipt_ids=("current",))

    assert "live_finite_background_job" in _codes(ledger)
    process = ledger.registered_processes()["job-1"]
    assert process["launch_mode"] == "background_job"
    assert process["detached"] is True


def test_successful_terminal_generation_bound_probe_clears_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _probe_job(ledger, status="completed", completed=True, succeeded=True, exit_code=0, step=2)
    _record_evidence(ledger, step=3, receipt_id="current")
    _record_claim(ledger, step=4, evidence_receipt_ids=("current",))

    codes = _codes(ledger)
    assert "live_finite_background_job" not in codes
    assert "unsuccessful_finite_background_job" not in codes


def test_successful_terminal_job_lifecycle_remains_resolved_after_later_mutation() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _probe_job(ledger, status="completed", completed=True, succeeded=True, exit_code=0, step=2)
    ledger.record(Receipt(
        receipt_id="later-task-mutation",
        step=3,
        kind="write_file",
        success=True,
        summary="task state changed after completed finite work",
        state_change=True,
        payload={"path": "/app/candidate.py", "modified_paths": ["candidate.py"]},
    ))
    _record_evidence(ledger, step=4, receipt_id="current-after-mutation")
    _record_claim(ledger, step=5, evidence_receipt_ids=("current-after-mutation",))

    # The finite operation really did complete successfully. Its semantic
    # relevance to the later-mutated candidate is not invented by lifecycle
    # custody; completion-evidence/terminal review owns that question.
    assert "unsuccessful_finite_background_job" not in _codes(ledger)


def test_generation_verified_direct_job_probe_marks_runtime_status_current() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _probe_job(ledger, status="running", completed=False, succeeded=None, exit_code=None, step=2)

    operations = ledger.runtime_operation_statuses()
    assert len(operations) == 1
    assert operations[0]["status"] == "running"
    assert operations[0]["status_current"] is True
    assert operations[0]["status_authority"] == "mechanical_generation_verified_probe"


def test_pre_failure_same_command_success_cannot_discharge_later_refresh_failure() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _record_evidence(ledger, step=2, receipt_id="early-rerun-ok", kind="run_command", success=True)
    ledger.record(Receipt(
        receipt_id="terminal-refresh-failed",
        step=3,
        kind="runtime_operation_status_refresh",
        success=True,
        summary="background job later failed",
        payload={
            "job_id": "job-1",
            "process_id": "job-1",
            "job_status": "failed",
            "completed": True,
            "job_succeeded": False,
            "exit_code": 1,
            "process_generation": "gen-1",
            "process_generation_verified": True,
        },
    ))
    _record_claim(ledger, step=4, evidence_receipt_ids=("early-rerun-ok",))

    process = ledger.registered_processes()["job-1"]
    assert process["terminal_receipt_id"] == "terminal-refresh-failed"
    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_failed_terminal_job_does_not_become_completion_success() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _probe_job(ledger, status="failed", completed=True, succeeded=False, exit_code=1, step=2)
    _record_claim(ledger, step=3)

    assert "unsuccessful_finite_background_job" in _codes(ledger)
    process = ledger.registered_processes()["job-1"]
    assert process["job_succeeded"] is False
    assert process["terminal_receipt_id"] == "probe-job-1-2"


def test_confirmed_stop_does_not_count_as_successful_validation() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    # Artifact/currentness inspection alone is intentionally insufficient to
    # convert a canceled finite operation into successful validation.
    _record_evidence(ledger, step=3, receipt_id="artifact-current", kind="check_result")
    _record_claim(ledger, step=4, evidence_receipt_ids=())

    assert "unsuccessful_finite_background_job" in _codes(ledger)
    process = ledger.registered_processes()["job-1"]
    assert process["status"] == "stopped"
    assert process["job_succeeded"] is False


def test_stopped_job_requires_later_cited_execution_or_verification_evidence() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    _record_evidence(ledger, step=3, receipt_id="rerun-ok", kind="run_command", success=True)
    _record_claim(ledger, step=4, evidence_receipt_ids=("rerun-ok",))

    assert "unsuccessful_finite_background_job" not in _codes(ledger)


def test_incomplete_same_command_receipt_cannot_discharge_stopped_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    ledger.record(Receipt(
        receipt_id="incomplete-replay",
        step=3,
        kind="run_command",
        success=True,
        summary="malformed success receipt",
        payload={
            "command": "python validate.py",
            **ledger.current_snapshot_binding_payload(),
        },
    ))
    _record_claim(ledger, step=4, evidence_receipt_ids=("incomplete-replay",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_unrelated_successful_command_cannot_discharge_stopped_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    ledger.record(Receipt(
        receipt_id="unrelated-ok",
        step=3,
        kind="run_command",
        success=True,
        summary="unrelated command succeeded",
        payload={
            "command": "ls /app",
            "exit_code": 0,
            "timed_out": False,
            **ledger.current_snapshot_binding_payload(),
        },
    ))
    _record_claim(ledger, step=4, evidence_receipt_ids=("unrelated-ok",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_unrelated_passing_check_cannot_discharge_stopped_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    _record_evidence(ledger, step=3, receipt_id="unrelated-check", kind="check_result", success=True)
    _record_claim(ledger, step=4, evidence_receipt_ids=("unrelated-check",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_successful_exact_replay_lifecycle_remains_resolved_after_later_mutation() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    _record_evidence(ledger, step=3, receipt_id="rerun-ok-old", kind="run_command", success=True)
    # A later candidate mutation can make the replay stale as semantic
    # validation, but it does not undo the mechanical fact that the stopped
    # finite operation was successfully replayed to completion.
    ledger.record(Receipt(
        receipt_id="candidate-mutation",
        step=4,
        kind="write_file",
        success=True,
        summary="candidate changed after rerun",
        state_change=True,
        payload={
            "path": "/app/candidate.py",
            "modified_paths": ["candidate.py"],
        },
    ))
    ledger.record(Receipt(
        receipt_id="current-artifact",
        step=5,
        kind="read_file",
        success=True,
        summary="current artifact reread",
        payload={"path": "/app/candidate.py", **ledger.current_snapshot_binding_payload()},
    ))
    current_generation = ledger.task_state_generation()
    old_generation = ledger.receipt_task_state_generation("rerun-ok-old")
    assert old_generation is not None and old_generation < current_generation
    ledger.record(Receipt(
        receipt_id="claim-6",
        step=6,
        kind="primary_submission_claim",
        success=True,
        summary="candidate ready",
        payload={
            "claim_id": "claim",
            "claim": "candidate ready",
            "evidence_refs": ["evidence:old", "evidence:current"],
            "evidence_receipt_ids": ["rerun-ok-old", "current-artifact"],
            "evidence_bindings": [
                {
                    "receipt_id": "rerun-ok-old",
                    "role": "historical_support",
                    "task_state_generation": old_generation,
                },
                {
                    "receipt_id": "current-artifact",
                    "role": "current_anchor",
                    "task_state_generation": current_generation,
                },
            ],
            "current_anchor_count": 1,
            **ledger.current_snapshot_binding_payload(),
        },
    ))

    assert "unsuccessful_finite_background_job" not in _codes(ledger)


def test_nonexecution_artifact_read_cannot_discharge_stopped_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    ledger.record(Receipt(
        receipt_id="read-after-stop",
        step=3,
        kind="read_file",
        success=True,
        summary="artifact exists",
        payload={"path": "/app/output.txt", **ledger.current_snapshot_binding_payload()},
    ))
    _record_claim(ledger, step=4, evidence_receipt_ids=("read-after-stop",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)



def test_artifact_inspection_cannot_discharge_stopped_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    ledger.record(Receipt(
        receipt_id="inspect-after-stop",
        step=3,
        kind="artifact_inspection",
        success=True,
        summary="artifact metadata exists",
        payload={"path": "/app/output.txt", **ledger.current_snapshot_binding_payload()},
    ))
    _record_claim(ledger, step=4, evidence_receipt_ids=("inspect-after-stop",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_service_probe_cannot_discharge_stopped_finite_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    ledger.record(Receipt(
        receipt_id="service-after-stop",
        step=3,
        kind="service_probe",
        success=True,
        summary="unrelated service live",
        payload={
            "service_name": "unrelated",
            "live": True,
            "process_generation": "svc-gen",
            "process_generation_verified": True,
            **ledger.current_snapshot_binding_payload(),
        },
    ))
    _record_claim(ledger, step=4, evidence_receipt_ids=("service-after-stop",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)

def test_reprobing_failed_job_does_not_discharge_failure_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _probe_job(ledger, status="failed", completed=True, succeeded=False, exit_code=1, step=2)
    _probe_job(ledger, status="failed", completed=True, succeeded=False, exit_code=1, step=3)
    _record_claim(ledger, step=4, evidence_receipt_ids=("probe-job-1-3",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_unknown_terminal_state_fails_closed() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _probe_job(ledger, status="unknown", completed=False, succeeded=None, exit_code=None, step=2)
    _record_claim(ledger, step=3)

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_replaced_generation_obsoletes_old_job_but_new_generation_must_succeed() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger, process_id="job-old", generation="gen-old", step=1)
    _stop_job(ledger, process_id="job-old", step=2)
    _launch_job(ledger, process_id="job-new", generation="gen-new", step=3)
    _probe_job(
        ledger,
        process_id="job-new",
        generation="gen-new",
        status="completed",
        completed=True,
        succeeded=True,
        exit_code=0,
        step=4,
    )
    _record_evidence(ledger, step=5, receipt_id="current")
    _record_claim(ledger, step=6, evidence_receipt_ids=("current",))

    old = ledger.registered_processes()["job-old"]
    assert old["superseded_by"] == "job-new"
    assert "unsuccessful_finite_background_job" not in _codes(ledger)


def test_same_name_managed_process_cannot_supersede_failed_finite_job_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger, process_id="job-old", name="validation", generation="gen-old", step=1)
    _stop_job(ledger, process_id="job-old", step=2)
    ledger.record(Receipt(
        receipt_id="launch-managed",
        step=3,
        kind="process_launch",
        success=True,
        summary="same-name managed process",
        state_change=True,
        payload={
            "process_id": "managed-new",
            "service_name": "validation",
            "command": "python server.py",
            "launch_mode": "managed_process",
            "detached": False,
            "live": True,
            "job_status": "running",
            "process_generation": "managed-gen",
        },
    ))
    _record_evidence(ledger, step=4, receipt_id="current")
    _record_claim(ledger, step=5, evidence_receipt_ids=("current",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_same_name_finite_replacement_with_different_command_cannot_erase_old_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger, process_id="job-old", name="validation", generation="gen-old", step=1)
    _stop_job(ledger, process_id="job-old", step=2)
    ledger.record(Receipt(
        receipt_id="launch-job-new",
        step=3,
        kind="process_launch",
        success=True,
        summary="different same-name finite job",
        state_change=True,
        payload={
            "process_id": "job-new",
            "service_name": "validation",
            "command": "true",
            "launch_mode": "background_job",
            "detached": True,
            "live": True,
            "job_status": "running",
            "process_generation": "gen-new",
        },
    ))
    _probe_job(
        ledger, process_id="job-new", generation="gen-new",
        status="completed", completed=True, succeeded=True, exit_code=0, step=4,
    )
    _record_evidence(ledger, step=5, receipt_id="current")
    _record_claim(ledger, step=6, evidence_receipt_ids=("current",))

    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_replaced_generation_still_blocks_while_replacement_runs() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger, process_id="job-old", generation="gen-old", step=1)
    _stop_job(ledger, process_id="job-old", step=2)
    _launch_job(ledger, process_id="job-new", generation="gen-new", step=3)
    _record_evidence(ledger, step=4, receipt_id="current")
    _record_claim(ledger, step=5, evidence_receipt_ids=("current",))

    assert "live_finite_background_job" in _codes(ledger)


def test_declared_persistent_service_may_remain_live_at_completion() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger, name="server")
    _record_evidence(ledger, step=2, receipt_id="current")
    _record_claim(ledger, step=3, evidence_receipt_ids=("current",))
    graph = ObjectiveGraph(
        service_requirements=(ServiceRequirement(name="server", must_be_live=True),),
    )

    assert "live_finite_background_job" not in _codes(ledger, graph)


def test_legacy_detached_process_launch_fails_closed() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="legacy-launch",
        step=1,
        kind="process_launch",
        success=True,
        summary="legacy detached launch",
        state_change=True,
        payload={
            "process_id": "job-legacy",
            "service_name": "finite",
            "detached": True,
            "live": True,
            "job_status": "running",
            "process_generation": "gen-legacy",
        },
    ))
    _record_evidence(ledger, step=2, receipt_id="current")
    _record_claim(ledger, step=3, evidence_receipt_ids=("current",))

    assert "live_finite_background_job" in _codes(ledger)


def test_science_pattern_stop_then_artifact_evidence_still_cannot_finish() -> None:
    """Regression for the linked-cell failure shape, without task semantics."""
    ledger = ExecutionLedger()
    _launch_job(ledger, name="devsolve", step=1)
    _probe_job(
        ledger, status="running", completed=False, succeeded=None, exit_code=None, step=2
    )
    # Candidate/artifact evidence while the finite validation is still running
    # cannot make completion ready.
    ledger.record(Receipt(
        receipt_id="artifact-before-stop",
        step=3,
        kind="artifact_inspection",
        success=True,
        summary="artifact metadata",
        payload={"path": "/app/protect_tables.py", **ledger.current_snapshot_binding_payload()},
    ))
    _record_claim(ledger, step=4, evidence_receipt_ids=("artifact-before-stop",))
    assert "live_finite_background_job" in _codes(ledger)

    # Stopping the validation resolves liveness only. It does not turn the
    # interrupted validation into a pass, even if the artifact is then reread.
    _stop_job(ledger, step=5)
    ledger.record(Receipt(
        receipt_id="artifact-after-stop",
        step=6,
        kind="artifact_inspection",
        success=True,
        summary="artifact metadata after stop",
        payload={"path": "/app/protect_tables.py", **ledger.current_snapshot_binding_payload()},
    ))
    _record_claim(ledger, step=7, evidence_receipt_ids=("artifact-after-stop",))
    codes = _codes(ledger)
    assert "live_finite_background_job" not in codes
    assert "unsuccessful_finite_background_job" in codes


def test_optional_cancelled_job_disposition_removes_only_mechanical_replay_debt() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    disposition = ledger.set_job_disposition(
        "job-1", "optional", "diagnostic is no longer part of the chosen validation path",
        step=3,
    )
    assert disposition.success is True
    process = ledger.registered_processes()["job-1"]
    assert process["execution_state"] == "cancelled"
    assert process["relevance"] == "optional"
    assert process["job_succeeded"] is False
    _record_evidence(ledger, step=4, receipt_id="current")
    _record_claim(ledger, step=5, evidence_receipt_ids=("current",))
    assert "unsuccessful_finite_background_job" not in _codes(ledger)


def test_required_cancelled_job_disposition_still_blocks_completion() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    _stop_job(ledger)
    disposition = ledger.set_job_disposition(
        "job-1", "required", "this validation is still required by the current plan",
        step=3,
    )
    assert disposition.success is True
    _record_evidence(ledger, step=4, receipt_id="current")
    _record_claim(ledger, step=5, evidence_receipt_ids=("current",))
    assert "unsuccessful_finite_background_job" in _codes(ledger)


def test_job_disposition_rejects_unknown_job_without_mutating_lifecycle() -> None:
    ledger = ExecutionLedger()
    receipt = ledger.set_job_disposition(
        "missing-job", "optional", "nothing registered under this identity", step=1,
    )
    assert receipt.success is False
    assert receipt.payload["outcome"] == "rejected_before_execution"
    assert ledger.registered_processes() == {}


def test_optional_job_with_unknown_terminal_state_still_blocks_completion() -> None:
    ledger = ExecutionLedger()
    _launch_job(ledger)
    ledger.record(Receipt(
        receipt_id="lost-job-status",
        step=2,
        kind="job_probe",
        success=False,
        summary="job outcome could not be reconciled",
        payload={
            "job_id": "job-1",
            "process_id": "job-1",
            "process_generation": "gen-1",
            "process_generation_verified": True,
            "job_status": "unknown",
            "completed": False,
            "job_succeeded": None,
        },
    ))
    ledger.set_job_disposition(
        "job-1", "optional", "diagnostic only, but execution outcome is unknown", step=3,
    )
    _record_evidence(ledger, step=4, receipt_id="current")
    _record_claim(ledger, step=5, evidence_receipt_ids=("current",))
    process = ledger.registered_processes()["job-1"]
    assert process["execution_state"] == "unknown"
    assert "unsuccessful_finite_background_job" in _codes(ledger)


def _dispatch_disposition(
    ledger: ExecutionLedger,
    *,
    relevance: str,
    step: int,
) -> None:
    """Run set_job_disposition through the real kernel dispatch boundary."""
    from aether.execution import MemoryExecutor
    from aether.kernel import AetherNextKernel
    from aether.kernel_dispatch import dispatch_action
    from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap

    envmap = EnvMap(
        task_prompt="managed finite diagnostic",
        workspace_root="/app",
        capabilities={
            "managed_process": CapabilityDescriptor(
                capability_id="managed_process", summary="managed processes", available=True,
            )
        },
    )
    kernel = AetherNextKernel(
        max_steps=8,
        runtime_identity={
            "task_id": "stopped-verification-job",
            "run_id": "stopped-verification-job-run",
            "primary_agent_id": "primary",
        },
    )
    executor = MemoryExecutor(workspace_root="/app")
    turn = ActionRequest(
        action_id="disposition", kind="set_job_disposition", capability_id="managed_process",
        arguments={
            "job_id": "job-1", "relevance": relevance,
            "reason": "verification job stopped; relevance declared explicitly",
        },
        intent="reconcile the stopped verification job",
        expected_observation="a job_disposition receipt",
        if_fail_next="inspect the disposition receipt",
    )
    receipts = dispatch_action(
        kernel, turn, step=step, compiled=_compiled(),
        executor=executor, envmap=envmap, ledger=ledger,
    )
    for receipt in receipts:
        ledger.record(receipt)


def test_optional_cancelled_verification_job_via_dispatch_removes_replay_debt() -> None:
    """F05 sentinel: optional-cancelled stopped verification job is non-blocking
    through the real kernel dispatch boundary."""
    ledger = ExecutionLedger()
    _launch_job(ledger, process_id="job-1", name="verify", generation="gen-1", step=1)
    _probe_job(ledger, step=2, status="running", completed=False, succeeded=None, exit_code=None)
    _stop_job(ledger, step=3)
    _dispatch_disposition(ledger, relevance="optional", step=4)
    disposition = [
        r for r in ledger.all_receipts() if r.kind == "job_disposition"
    ]
    assert len(disposition) == 1 and disposition[-1].success is True
    process = ledger.registered_processes()["job-1"]
    assert process["execution_state"] == "cancelled"
    assert process["relevance"] == "optional"
    _record_evidence(ledger, step=5, receipt_id="current")
    _record_claim(ledger, step=6, evidence_receipt_ids=("current",))
    assert "unsuccessful_finite_background_job" not in _codes(ledger)


def test_required_cancelled_verification_job_via_dispatch_still_blocks() -> None:
    """F05 sentinel: required-cancelled stopped verification job remains blocking
    through the real kernel dispatch boundary."""
    ledger = ExecutionLedger()
    _launch_job(ledger, process_id="job-1", name="verify", generation="gen-1", step=1)
    _probe_job(ledger, step=2, status="running", completed=False, succeeded=None, exit_code=None)
    _stop_job(ledger, step=3)
    _dispatch_disposition(ledger, relevance="required", step=4)
    process = ledger.registered_processes()["job-1"]
    assert process["execution_state"] == "cancelled"
    assert process["relevance"] == "required"
    _record_evidence(ledger, step=5, receipt_id="current")
    _record_claim(ledger, step=6, evidence_receipt_ids=("current",))
    assert "unsuccessful_finite_background_job" in _codes(ledger)
