"""Finish settle check: are the delivered files still changing when the model asks to finish?

Off by default (``CoreConfig.finish_settle``). A background process the model started can keep writing after the
model's last check, so the state it checked is not the state that is delivered and graded. Core sees this only in
the post-run report, which the model never reads. Continuation capture already treats a file whose before and after
hashes differ as unstable; this applies the same rule at the moment of finishing.

At the first finish request: hash the files the run changed (the finish report's scan: newer than the start marker,
plus file-tool writes), wait ``SETTLE_S``, and hash again. If any file appeared, disappeared or changed while no
foreground command ran, the finish is returned once with the facts: the files, their before/after sizes, and the
processes still running under the terminals. The model decides whether to wait, stop the writer or finish anyway.
A second finish always proceeds. Measurement failures are reported as unmeasured and never hold the finish.
"""

from __future__ import annotations

import asyncio
from typing import Any

from .env import list_process_tree
from .finish_report import _files

SETTLE_S = 2.0
MAX_LISTED = 12

NOTE = (
    "Finish not yet taken: files this run changed were still changing {wait:g} s after your finish request, while no "
    "foreground command of yours was running. The delivered state is what gets used, so it may differ from what you "
    "last checked.\n{files}\n{processes}\nDecide whether to wait for the writer, stop it, or finish as it is. "
    "Calling finish again ends the work."
)


def compare(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Files that appeared, disappeared or changed content between two measurements."""
    old = {row["path"]: row for row in before}
    new = {row["path"]: row for row in after}
    changed = []
    for path in sorted(old.keys() | new.keys()):
        a, b = old.get(path), new.get(path)
        if a is None or b is None or a["sha256"] != b["sha256"]:
            changed.append({"path": path, "bytes_before": a and a["bytes"], "bytes_after": b and b["bytes"]})
    return changed


async def measure(env, workdir: str, control_dir: str, written: set[str], wait_s: float = SETTLE_S) -> dict[str, Any]:
    first, first_total = await _files(env, workdir, control_dir, written, check_absence=True)
    if isinstance(first, str):
        return {"status": "unmeasured", "reason": first}
    await asyncio.sleep(wait_s)
    second, second_total = await _files(env, workdir, control_dir, written, check_absence=True)
    if isinstance(second, str):
        return {"status": "unmeasured", "reason": second}
    changed = compare(first, second)
    from .finish_report import MAX_FILES

    partial = max(first_total, second_total) > MAX_FILES
    return {"status": "changing" if changed else "unmeasured" if partial else "settled",
            "changed": changed, "files": len(second), "partial": partial, "wait_s": wait_s}


def render(row: dict[str, Any], processes: list[str]) -> str:
    files = "\n".join(
        f"- {c['path']}: " + ("appeared" if c["bytes_before"] is None else
                              "disappeared" if c["bytes_after"] is None else
                              f"{c['bytes_before']} -> {c['bytes_after']} bytes")
        for c in row["changed"][:MAX_LISTED]
    )
    more = len(row["changed"]) - MAX_LISTED
    if more > 0:
        files += f"\n- and {more} more"
    running = ("Processes still running under your terminals:\n" + "\n".join(f"- {p}" for p in processes[:MAX_LISTED])
               if processes else "No process under your terminals was observed running.")
    return NOTE.format(wait=row["wait_s"], files=files, processes=running)


async def at_finish(s) -> str | None:
    """The hold text for this finish, or None to proceed. Holds at most once per run."""
    if not s.config.finish_settle or s.result.extras.get("finish_settle") or s.remaining() < SETTLE_S + 15:
        return None
    written = {step.wrote for step in s.report_steps if step.wrote and not step.failed}
    row = await measure(s.env, s.workdir, s.config.control_dir, written)
    processes: list[str] = []
    if row["status"] == "changing":
        try:
            processes = await list_process_tree(s.env, [t.pid for t in s.terminals._sessions.values()])
        except OSError as exc:
            processes = [f"(process listing unavailable: {exc})"]
    s.result.extras["finish_settle"] = {**row, "processes": processes}
    s.trace("finish_settle", **row, processes=processes)
    return render(row, processes) if row["status"] == "changing" else None
