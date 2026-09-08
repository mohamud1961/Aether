from __future__ import annotations

import tempfile
from pathlib import Path

from aether.envmap_builder import build_envmap_from_task
from aether.ledger import ExecutionLedger
from aether.pcr_context import compile_pcr_context
from aether.pcr_runtime import build_pcr_runtime


def test_pcr_packet_exposes_factual_dynamic_wall_clock_budget() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "instruction.md").write_text("Create result.txt", encoding="utf-8")
        env = build_envmap_from_task(
            str(root), "Create result.txt", workspace_root="/app", projection_mode="factual_only"
        )
    compiled = build_pcr_runtime(env).compiled
    assert compiled is not None

    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "task",
        "run_id": "run",
        "primary_agent_id": "primary",
        "workspace_id": "/app",
        "environment_id": "env",
        "budgets": {"max_kernel_steps": None, "agent_timeout_sec": 900.0},
    })
    ledger.update_runtime_budget_state({
        "run_timeout_sec": 900.0,
        "elapsed_run_sec": 100.0,
        "remaining_run_sec": 800.0,
        "wall_clock_authority": "runtime_supplied_timeout",
    })

    packet = compile_pcr_context(compiled, ledger, {})
    assert packet["budgets"] == {
        "max_kernel_steps": None,
        "agent_timeout_sec": 900.0,
        "run_timeout_sec": 900.0,
        "elapsed_run_sec": 100.0,
        "remaining_run_sec": 800.0,
        "wall_clock_authority": "runtime_supplied_timeout",
        "remaining_kernel_steps": None,
    }
