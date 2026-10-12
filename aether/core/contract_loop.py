"""The acceptance contract inside the agent loop (``loop._Session`` is passed in as ``s``).

start: clone the untouched container before any work and write the contract there in the background.
show: pin the checks after the task as soon as they exist.
finish: run the checks on a clone of the final state; hold with the failing checks, resolve disputes.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from . import contract as acceptance

MAX_CONTRACT_HOLDS = 3


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


async def finish(s: Any, args: dict[str, Any]) -> tuple[str, bool]:
    if s.contract_task and not s.contract_task.done() and s.remaining() > 150:
        await asyncio.wait({s.contract_task}, timeout=min(180.0, s.remaining() - 150))
    c = s.contract
    skip = ("no_contract" if not c or not c.checks else "hold_limit" if s.contract_holds >= MAX_CONTRACT_HOLDS
            else "low_time" if s.remaining() < 90 else "")
    if skip:
        s.trace("finish", summary=args.get("summary", ""), review="skipped", reason=skip)
        return "finished", True
    disputes = [d for d in args.get("disputes") or [] if isinstance(d, dict)]
    try:
        out = await acceptance.finish_checks(s.provider, s.env, c, task=s.task, workdir=s.workdir,
                                             disputes=disputes, make_clone=s.clone, remaining_s=s.remaining)
    except Exception as exc:  # substrate failure: reported, the finish proceeds
        row = {"kind": "finish", "at": "finish", "mode": "contract", "status": "error", "unmet": [],
               "reason": f"{type(exc).__name__}: {exc}"}
        s.result.reviews.append(row)
        s.trace("review", summary=args.get("summary", ""), **row)
        return "finished", True
    for ruling in out["rulings"].values():
        for key, value in ruling.pop("usage", {}).items():
            s.result.sub_usage[key] = s.result.sub_usage.get(key, 0) + value
    row = {"kind": "finish", "at": "finish", "mode": "contract", "status": out["status"],
           "unmet": [r.check.requirement for r in out["failed"]], "results": out["results"],
           "disputes": disputes, "rulings": out["rulings"], "latency_s": out["seconds"]}
    s.result.reviews.append(row)
    s.trace("review", summary=args.get("summary", ""), **row)
    if out["status"] == "hold":
        s.contract_holds += 1
        return acceptance.feedback(out["failed"], out["rulings"]), False
    return "finished", True
