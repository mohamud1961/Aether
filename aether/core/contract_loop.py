"""The acceptance checks inside the agent loop (``loop._Session`` is passed in as ``s``).

start: clone the untouched container before any work and write the checks there in the background.
show: pin the checks after the task as soon as they exist.
run_checks: the worker's tool to run them on a copy of its current state. Nothing here holds a finish.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from . import contract as acceptance

MAX_WAIT_S = 180.0  # longest run_checks waits for the writer
WAIT_RESERVE_S = 150.0  # time kept for the work itself

async def start(s: Any) -> None:
    """Clone the untouched container now (before any work); the contract is written there in the background."""
    t0 = time.monotonic()
    try:
        clone = await s.clone(s.env)
    except Exception as exc:  # substrate failure: reported; the run continues without a contract
        s.contract = acceptance.Contract(error=f"clone failed: {type(exc).__name__}: {exc}")
        s.trace("contract", ok=False, error=s.contract.error)
        return

    async def write() -> None:
        try:
            s.contract = await acceptance.write(s.provider, clone, task=s.task, workdir=s.workdir,
                                                log=lambda row: s.trace("contract_round", **row))
        finally:
            await clone.close()
        for key, value in s.contract.usage.items():
            s.result.sub_usage[key] = s.result.sub_usage.get(key, 0) + value
        s.trace("contract", ok=not s.contract.error, error=s.contract.error, rounds=s.contract.turns,
                checks=[c.__dict__ for c in s.contract.checks], dropped=s.contract.dropped,
                unconfirmed=s.contract.unconfirmed, seconds=round(time.monotonic() - t0, 1))
    s.contract_task = asyncio.create_task(write())


def show(s: Any, attach: Callable[[list[dict[str, Any]], str], None]) -> None:
    """Pin the checks after the task as soon as they exist (context edits and checkpoints keep them)."""
    if s.contract_shown or not s.contract or not s.contract.checks:
        return
    s.contract_shown = True
    message = {"role": "user", "content": s.contract.render()}
    if s.clm:
        s.clm.pinned.append(message)
    else:
        s.messages.insert(2, message)
    attach(s.history, "[acceptance checks received: they are pinned after the task]")
    s.trace("contract_shown", checks=len(s.contract.checks), elapsed_s=round(s.elapsed(), 1))


async def run_checks(s: Any) -> str:
    """The run_checks tool: the checks on a disposable copy of the current state, reported, never enforced.
    Checks still being written are waited for, as long as time allows."""
    if s.contract_task and not s.contract_task.done() and s.remaining() > WAIT_RESERVE_S:
        await asyncio.wait({s.contract_task}, timeout=min(MAX_WAIT_S, s.remaining() - WAIT_RESERVE_S))
    c = s.contract
    if not c or not c.checks:
        state = "still being written" if s.contract_task and not s.contract_task.done() else (
            f"not available ({c.error})" if c and c.error else "not available")
        return f"[acceptance checks] {state}."
    t0 = time.monotonic()
    try:
        results = await acceptance.check_state(s.env, c, s.workdir, s.clone)
    except Exception as exc:  # substrate failure: reported to the model and the trace, nothing assumed
        s.trace("contract_run", ok=False, error=f"{type(exc).__name__}: {exc}")
        return f"[acceptance checks] could not make a copy of the state to run them on: {type(exc).__name__}: {exc}"
    s.trace("contract_run", ok=True, seconds=round(time.monotonic() - t0, 1),
            results=[{"check": r.check.id, "exit": r.code, "output": r.output[-200:]} for r in results])
    return acceptance.report(results)
