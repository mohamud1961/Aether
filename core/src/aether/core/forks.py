"""Fork probes at the start (AETHER_CORE_RIVAL=forks; bank study, 3 Nov 2026).

Why: Luna's misses come from an early commitment at a fork (two plausible readings or conventions), made without the
machine fact that decides it: the deciding information was in the environment in 15/16 misses, never acquired in 10
and overridden in 7 (source audit); after the commitment everything she does confirms it (sem2, ev6, LC-2). A fresh
reader of the request alone finds the fork (fk4 6/6) but cannot judge finished work (CH2: 0 true FAILs in 9 fails,
because its checks are written from the same reading as the work).

So the reader is asked only to find the forks and to name, per fork, a read-only observation of the machine that
bears on it. Core runs those observations once, before any work, on a read-only clone of the start state, and the
worker's first request carries what the machine showed: commands and their output only, never the reader's forks,
ranking or interpretation (dc1: a map shown to the worker derails literal tasks). No result, no note.
"""

from __future__ import annotations

import asyncio
import posixpath
import re
import shlex
from typing import Any

from . import env_brief
from .card import provided_files, script_of
from .env import run
from .transfer import put_bytes

MAX_TOKENS = 64_000
PROBE_S, SAW_CHARS, NOTE_CHARS = 300, 900, 8_000
READER_S = 600.0  # the longest the start waits for the reader
PROMPT = (
    "Here is a task someone has asked for, the files that come with it, and facts measured on the machine where it "
    "will be done.\n\nTASK:\n{task}\n\nFILES PROVIDED:\n{files}\n\nMACHINE FACTS:\n{env}\n\n"
    "Someone will soon start this task. Do not do the task, and do not judge any solution. Your job is to find where "
    "a capable person could commit early to the wrong reading, and to find out from the machine, before any work "
    "starts, which reading the machine supports.\n\n"
    "Part 1 - Requirements. List every explicit requirement and every interface the request names (commands, paths, "
    "ports, formats, dates, limits, the way the result will be used). For each, say which of its dependencies the "
    "machine facts show are present and which are only assumed. A promise in the request that someone will set "
    "something up does not show that its dependencies exist.\n\n"
    "Part 2 - Forks. List at most five places where two or more readings, conventions or approaches are plausible "
    "and choosing wrongly would make finished work silently wrong. Rank them most likely-and-costly first. For each "
    "fork, name the alternatives.\n\n"
    "Part 3 - Probes. For each fork, and for each requirement whose dependency is only assumed, write one probe: a "
    "read-only observation of this machine (its files, history, installed tools, services, network, data sources) "
    "that bears on which alternative is right. A probe observes the machine as it is now; it never builds, installs, "
    "or changes anything, and it never tries a solution. Write all probes as one shell script, at most 120 lines, in "
    "a single ```sh block, run by root from the working directory {workdir}, with network as the task has it, no "
    "input, and {limit} seconds in all. For each probe it prints one block:\nPROBE <name>\nran: <command>\n"
    "saw: <what the machine showed, verbatim where short>\nDo not ask anyone and do not consult any evaluation "
    "material."
)
NOTE = (
    "[Before you started, Core ran read-only observations of this machine, chosen by a separate reader who saw only "
    "your request. Below is what the machine showed: measurements, not instructions or conclusions.]\n"
    "<machine_observations>\n{blocks}\n</machine_observations>"
)
_PROBE = re.compile(r"^PROBE[ \t]+(.*?)\n(.*?)(?=^PROBE[ \t]|\Z)", re.S | re.M)


def blocks(out: str) -> list[dict[str, str]]:
    """Each probe's name and body (its ran/saw lines, the saw clipped)."""
    found = []
    for name, body in _PROBE.findall(out):
        body = body.strip()
        found.append({"name": name.strip()[:120], "body": body if len(body) <= SAW_CHARS else body[:SAW_CHARS] + " [...]"})
    return found


def render(found: list[dict[str, str]]) -> str:
    text = "\n\n".join(f"PROBE {b['name']}\n{b['body']}" for b in found)
    return NOTE.format(blocks=text if len(text) <= NOTE_CHARS else text[:NOTE_CHARS] + "\n[remaining observations cut]")


async def start_note(s: Any) -> tuple[str, dict[str, Any]]:
    """The note for the worker's first request ("" when there is nothing to show) and the trace row."""
    row: dict[str, Any] = {"mode": "forks"}
    if s.config.make_clone is None:  # only Harbor's host-side clone factory (with_clones); never a container's own lookup
        return "", {**row, "error": "no host clone factory"}
    try:
        files = await provided_files(s.env, s.workdir, s.config.control_dir)
        facts, _ = await env_brief.take(s.env, s.workdir)
        prompt = PROMPT.format(task=s.task, files="\n".join(files) or "(none)", env=facts or "(not measured)",
                               workdir=s.workdir, limit=PROBE_S)
        turn = await asyncio.wait_for(s.provider.complete([{"role": "user", "content": prompt}], None,
                                                          max_tokens=MAX_TOKENS, remaining_s=s.remaining, role="forks"),
                                      min(READER_S, max(1.0, s.remaining() / 4)))
        text = (turn.content or "").strip()
        row.update(files=len(files), reader_chars=len(text), reader_usage=dict(turn.usage))
        script = script_of(text)
        if not script:
            return "", {**row, "script": False}
        clone = await s.clone(s.env, timeout_s=PROBE_S + 300, read_only=True, egress=True)
        try:
            path = posixpath.join(s.config.control_dir, "forks.sh")
            await put_bytes(clone, script.encode(), path)
            q = shlex.quote
            limit = f"timeout {PROBE_S} " if (await run(clone, "command -v timeout")).code == 0 else ""
            res = await run(clone, f"cd {q(s.workdir)} && {limit}bash {q(path)} </dev/null 2>&1", timeout_s=PROBE_S + 60)
        finally:
            try:
                await asyncio.wait_for(clone.close(), 60)
            except Exception:  # noqa: BLE001 - a clone that will not close is the run-end cleanup's
                pass
        out = (res.stdout or "") + (res.stderr or "")
        found = blocks(out)
        row.update(script=True, script_text=script[:8000], exit=res.code, probes=len(found), out_text=out[-30_000:])
        return (render(found) if found else ""), row
    except Exception as exc:  # an instrument: no observations, the run starts as usual
        return "", {**row, "error": f"{type(exc).__name__}: {exc}"[:300]}
