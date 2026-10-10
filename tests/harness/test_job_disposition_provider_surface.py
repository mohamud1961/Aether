from __future__ import annotations

import pytest

from aether.persistent_capabilities import persistent_capability_contract
from aether.persistent_provider_protocol import PCRProviderProtocolError, validate_persistent_inner_turn
from aether.runtime_ir import ACTION_SCHEMA, CapabilityDescriptor, CompiledRuntime, EnvMap
from aether.persistent_runtime import build_persistent_runtime


def _compiled():
    env = EnvMap(
        task_prompt="manage a finite diagnostic",
        workspace_root="/app",
        capabilities={
            "managed_process": CapabilityDescriptor(
                capability_id="managed_process", summary="managed processes", available=True,
            )
        },
    )
    resolved = build_persistent_runtime(env)
    assert resolved.compiled is not None and not resolved.config_invalid_blockers
    return resolved.compiled


def test_job_disposition_is_on_canonical_action_and_provider_surface() -> None:
    assert dict(ACTION_SCHEMA)["set_job_disposition"] == ("job_id", "relevance", "reason")
    turn = validate_persistent_inner_turn({
        "kind": "act",
        "action": {
            "kind": "set_job_disposition",
            "arguments": {
                "job_id": "job-1",
                "relevance": "optional",
                "reason": "diagnostic no longer needed",
            },
        },
    })
    assert turn["action"]["kind"] == "set_job_disposition"
    assert turn["action"]["arguments"]["relevance"] == "optional"
    assert persistent_capability_contract(_compiled())["set_job_disposition"] == ("kernel",)


def test_job_disposition_provider_schema_rejects_unclassified_model_claim() -> None:
    with pytest.raises(PCRProviderProtocolError):
        validate_persistent_inner_turn({
            "kind": "act",
            "action": {
                "kind": "set_job_disposition",
                "arguments": {
                    "job_id": "job-1",
                    "relevance": "unclassified",
                    "reason": "invalid explicit model disposition",
                },
            },
        })


def test_start_job_can_declare_required_or_optional_relevance_at_launch() -> None:
    for relevance in ("required", "optional"):
        turn = validate_persistent_inner_turn({
            "kind": "act",
            "action": {
                "kind": "start_job",
                "arguments": {
                    "service_name": "finite-check",
                    "command": "python validate.py",
                    "relevance": relevance,
                    "reason": "task validation" if relevance == "required" else "diagnostic only",
                },
            },
        })
        assert turn["action"]["arguments"]["relevance"] == relevance


def test_start_job_rejects_abandoned_relevance_at_launch() -> None:
    with pytest.raises(PCRProviderProtocolError):
        validate_persistent_inner_turn({
            "kind": "act",
            "action": {
                "kind": "start_job",
                "arguments": {
                    "service_name": "finite-check",
                    "command": "python validate.py",
                    "relevance": "abandoned",
                    "reason": "nonsensical at launch",
                },
            },
        })


def test_set_job_disposition_dispatches_end_to_end() -> None:
    """Parse -> kernel dispatch -> job_disposition receipt, all real interfaces."""
    import json

    from aether.execution import MemoryExecutor
    from aether.kernel import AetherNextKernel
    from aether.kernel_dispatch import dispatch_action
    from aether.ledger import ExecutionLedger
    from aether.model_parse import parse_solver_turn
    from aether.persistent_provider_protocol import canonicalize_persistent_direct_tool_call
    from aether.persistent_runtime import build_persistent_runtime
    from aether.runtime_ir import ActionRequest, EnvMap

    envmap = EnvMap(
        task_prompt="manage a finite diagnostic",
        workspace_root="/app",
        capabilities={
            "managed_process": CapabilityDescriptor(
                capability_id="managed_process", summary="managed processes", available=True,
            )
        },
    )
    resolved = build_persistent_runtime(envmap)
    assert resolved.compiled is not None and not resolved.config_invalid_blockers
    compiled = resolved.compiled
    kernel = AetherNextKernel(
        max_steps=4,
        runtime_identity={
            "task_id": "disposition-dispatch",
            "run_id": "disposition-dispatch-run",
            "primary_agent_id": "primary",
        },
    )
    ledger = ExecutionLedger()
    ledger.install_runtime_identity(dict(kernel.runtime_identity))
    executor = MemoryExecutor(workspace_root="/app")

    # Launch a real managed job through the kernel dispatch boundary.
    launch_action = ActionRequest(
        action_id="launch", kind="start_job", capability_id="managed_process",
        arguments={"service_name": "finite", "command": "sleep 1; exit 0"},
        intent="start the diagnostic",
        expected_observation="a registered job",
        if_fail_next="inspect the launch receipt",
    )
    launch_receipts = dispatch_action(
        kernel, launch_action, step=1, compiled=compiled,
        executor=executor, envmap=envmap, ledger=ledger,
    )
    assert launch_receipts and launch_receipts[0].success
    for receipt in launch_receipts:
        ledger.record(receipt)  # mirror the kernel act-turn recording boundary
    job_id = str((launch_receipts[0].payload or {}).get("job_id", "")).strip()
    assert job_id and job_id in ledger.registered_processes()

    # Parse a set_job_disposition act through the canonical solver turn parser.
    canonical, _ = canonicalize_persistent_direct_tool_call(
        "set_job_disposition",
        json.dumps({"arguments": {
            "job_id": job_id,
            "relevance": "optional",
            "reason": "diagnostic is no longer needed",
        }}),
    )
    turn = parse_solver_turn(canonical)
    assert turn.kind == "act"
    assert turn.actions[0].kind == "set_job_disposition"

    disposition_receipts = dispatch_action(
        kernel, turn.actions[0], step=3, compiled=compiled,
        executor=executor, envmap=envmap, ledger=ledger,
    )
    for receipt in disposition_receipts:
        ledger.record(receipt)  # mirror the kernel act-turn recording boundary
    rows = [r for r in ledger.all_receipts() if r.kind == "job_disposition"]
    assert len(rows) == 1
    row = rows[0]
    assert row.success is True
    assert row.payload["job_id"] == job_id
    assert row.payload["relevance"] == "optional"
    assert row.payload["outcome"] == "success"
    assert row.payload["execution"] == "not_started"
    assert row.payload["replay_safe"] is True
    process = ledger.registered_processes()[job_id]
    assert process["relevance"] == "optional"
    assert process["relevance_source"] == "model_declared"
