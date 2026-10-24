"""Action/evidence truth across terminal interrupts.

Offline integration tests. No model calls, network or benchmark execution.
"""
from __future__ import annotations

import asyncio

from aether.core.record import Record
from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv


def test_interrupt_with_command_does_not_submit_it(tmp_path):
    async def scenario():
        work = tmp_path / "work"
        work.mkdir()
        terminal = Terminals(
            LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl")
        )
        try:
            first = await terminal.use(input="sleep 20", wait_s=0.2)
            assert "still running" in first
            second = await terminal.use(
                input="echo SHOULD_NOT_HAVE_RUN", interrupt=True, wait_s=3
            )
            assert "supplied input was not submitted" in second
            assert "SHOULD_NOT_HAVE_RUN" not in second
            third = await terminal.use(input="echo NEXT_COMMAND", wait_s=3)
            assert "NEXT_COMMAND" in third or "[input not sent" in third
        finally:
            await terminal.close()

    asyncio.run(scenario())


def test_interrupt_alone_reports_observed_result(tmp_path):
    async def scenario():
        work = tmp_path / "work"
        work.mkdir()
        terminal = Terminals(
            LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl")
        )
        try:
            await terminal.use(input="sleep 20", wait_s=0.2)
            response = await terminal.use(interrupt=True, wait_s=3)
            assert "still running" in response or "[exit " in response
        finally:
            await terminal.close()

    asyncio.run(scenario())


def test_record_does_not_claim_unsent_command_passed():
    record = Record.__new__(Record)
    record.pending = {"main": "sleep 20"}
    out = record.completed(
        {"name": "main", "input": "echo NEVER_SENT", "mode": "command", "interrupt": True},
        "[interrupt requested; supplied input was not submitted because shell readiness is unconfirmed]\n"
        "[exit 0 · 0.2s · terminal main · cwd /app]",
    )
    # The exit, when genuine, belongs to the PREVIOUS command, never
    # to the post-interrupt text that was not submitted.
    assert out is not None and out[0] == "sleep 20"


def test_record_normal_exit_still_associates_with_command():
    record = Record.__new__(Record)
    record.pending = {}
    out = record.completed(
        {"name": "main", "input": "echo yes", "mode": "command", "interrupt": False},
        "[exit 0 · 0.2s · terminal main · cwd /app]",
    )
    assert out is not None and out[0] == "echo yes" and out[1] == 0


def test_record_pending_survives_interrupt_until_true_completion():
    record = Record.__new__(Record)
    record.pending = {"main": "run_actual_checker"}
    stalled = record.completed(
        {"name": "main", "input": "", "mode": "command", "interrupt": True},
        "[still running after 1s · terminal main]",
    )
    assert stalled is None
    assert record.pending.get("main") == "run_actual_checker"
    done = record.completed(
        {"name": "main", "input": "", "mode": "command", "interrupt": False},
        "[exit 0 · 0.4s · terminal main · cwd /app]",
    )
    assert done is not None and done[0] == "run_actual_checker"
    assert record.pending == {}


def test_record_pending_after_interrupt_with_unsent_command():
    record = Record.__new__(Record)
    record.pending = {"main": "run_actual_checker"}
    result = record.completed(
        {"name": "main", "input": "echo UNSENT", "mode": "command", "interrupt": True},
        "[interrupt requested; supplied input was not submitted because shell readiness is unconfirmed]\\n"
        "[still running after 1s · terminal main]",
    )
    assert result is None
    assert record.pending == {"main": "run_actual_checker"}
