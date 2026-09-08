from __future__ import annotations

from types import SimpleNamespace

from aether.execution import MemoryExecutor
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger, Receipt
from aether.pcr_context import evidence_alias
from aether.pcr_evidence import is_pcr_completion_evidence
from aether.runtime_ir import ActionRequest, EnvMap


def _action(action_id: str, kind: str, arguments: dict[str, object]) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        capability_id="filesystem",
        arguments=arguments,
        intent="",
        expected_observation="",
        if_fail_next="",
    )


def test_cold_historical_receipt_can_be_recovered_then_recited_as_fresh_evidence() -> None:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "cold-task",
        "run_id": "cold-run",
        "primary_agent_id": "cold-primary",
        "workspace_id": "/app",
        "environment_id": "cold-env",
    })
    historical = Receipt(
        receipt_id="step-2:old-check:cmd",
        step=2,
        kind="run_command",
        success=True,
        summary="command exit=0: python check_preservation.py",
        state_change=False,
        payload={
            "command": "python check_preservation.py",
            "exit_code": 0,
            "stdout": "preservation PASS",
            "stdout_full": "preservation PASS",
            "stderr_full": "",
            "stdout_handle": "2:old-check:stdout",
            "stderr_handle": "2:old-check:stderr",
            "stdout_bytes": 17,
            "stderr_bytes": 0,
        },
    )
    ledger.record(historical)

    envmap = EnvMap(task_prompt="Do the task.", workspace_root="/app", capabilities={})
    # The exact receipt handle is already the canonical cold-retrieval path.
    # No semantic memory-search action is required or exposed to the model.

    reread = dispatch_action(
        SimpleNamespace(),
        _action(
            "reread-old",
            "read_output",
            {"handle": f"receipt:{historical.receipt_id}"},
        ),
        8,
        SimpleNamespace(),
        MemoryExecutor(workspace_root="/app"),
        envmap,
        ledger,
    )
    assert len(reread) == 1
    recovered = reread[0]
    assert recovered.success is True
    assert recovered.kind == "read_output"
    assert recovered.payload["source_receipt_id"] == historical.receipt_id
    assert recovered.payload["stream"] == "receipt"
    assert "preservation PASS" in recovered.payload["chunk"]
    # The explicit fresh retrieval is admissible PCR completion evidence and
    # therefore receives a normal evidence alias when recorded/indexed.
    assert is_pcr_completion_evidence(recovered) is True
    assert evidence_alias(recovered.receipt_id).startswith("evidence:")
