"""Study arm (12 Nov): the solver writes an investigation agenda before it acts.

One extra call, same model, no tools, task text only. The model lists what the task leaves open and, for each point,
what settles it: the task's words (follow them), something on the machine (name the check and what each outcome will
mean, no answer yet), or nothing (add nothing). The list is appended to the task message for the run.

Why this shape (g3/MISSION_LOG.md, 11-12 Nov): a list of early choices lost 6 of 34 untouched tasks; a harness-written
map derails literal tasks (dc1) and a hold changes nothing (pilot1). A model-written agenda names the deciding point
as a machine question in 31 of 32 lists and removed those losses. Core writes none of the content and never reads it.
A second mode (``consensus``) asks five times and has the model keep only what at least four lists agree on.
The wording is frozen from g3/gp/step0_list_v8.txt so the graded small-set runs describe this module.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

ROLE = "agenda"
MAX_TOKENS = 16_000  # 6,000 returned no text on 5 of 10 calls: the reasoning used the whole allowance

QUESTION = "Here is a task you are about to do in a Linux container. Do not start it. List every point where the task text leaves something open or could be read in more than one way. For each point, say what settles it, using exactly one of these:\n- TEXT: the task's own words settle it. Write the reading you will follow.\n- MACHINE: something in the container settles it, such as a file, a README, a package, a schema or how a program behaves. Nothing on the machine has been seen yet, so do not write an answer. Write the check you will run, and decide now what each outcome will mean: `if <outcome> then <what you will do>; otherwise <what you will do>`. What you decide now is what you will do when the outcome arrives.\n- NOTHING: neither settles it. Then add nothing: do not set, restrict, convert, quote or assume anything the task did not name, and leave it as the files and tools already have it. Write what you will leave alone.\nRules, in this order:\n1. A command the task says will be run is run exactly as written, with exactly the account, host, path and names it writes. Your result must make it work as written.\n2. Do everything the task names, and nothing wider. Do not rewrite history, restructure, rename, reformat, add quoting, or clean up anything the task did not name.\n3. Every reading is a way of completing the task. Do not decide now to stop, skip a part, or leave a named part undone.\n4. An example in the task shows form. Whether its particular values apply here is a MACHINE point: the check is whether those values can be reproduced on this machine. If they cannot, the example was not made from this machine, and nothing but its form is taken from it.\nOne per line, in the form `<point> -> TEXT: <reading>`, `<point> -> MACHINE: <check>; if <outcome> then <action>; otherwise <action>` or `<point> -> NOTHING: <what you will leave alone>`. At most eight lines. Include only points that would change the result.\n\n"

HEADER = (
    "Before starting, you listed the points this task leaves open, what settles each, and what you will do for each "
    "outcome of a check. TEXT: follow the task's words as written. MACHINE: run the check, then do what you wrote "
    "for the outcome you get. NOTHING: add nothing the task did not name."
)


MERGE = 'Below are five lists that were written independently for the same task, each in answer to the same question. Write one list that keeps only the points on which at least four of the five lists agree in substance: the same point, resolved the same way (the same reading, the same check, or the same thing left alone), whatever label each list gave it. Use the wording of one of the agreeing lists for each kept point, and the label most of them use. Do not add points, do not combine different resolutions and do not write a compromise. Where the lists resolve a point differently, or fewer than four have it, leave the point out. For a MACHINE point, keep its `if ... then ...; otherwise ...` part only when at least four lists give the same one in substance; when they do not, keep the check alone. Use the same line format. Output only the list.\n\n'

LISTS = 5  # the merge keeps a point only when at least four of these agree


async def _one(provider: Any, prompt: str, remaining: Callable[[], float]) -> Any:
    return await provider.complete(
        [{"role": "user", "content": prompt}], None, max_tokens=MAX_TOKENS, remaining_s=remaining, role=ROLE
    )


def _add(total: dict[str, int], usage: dict[str, int]) -> None:
    for key, value in usage.items():
        total[key] = total.get(key, 0) + (value or 0)


async def ask(
    provider: Any, task: str, remaining: Callable[[], float], trace: Callable[..., Any], mode: str = "on"
) -> str:
    """The text to place after the task, or "" when the model returned no list (traced either way).

    ``on``: one list. ``consensus``: five lists written independently, then one merge call that keeps only the
    points at least four of them resolve the same way. AG1 (g3/MISSION_LOG.md) found the losing lines in 2-3 of 7
    lists for a task and the helpful one in 10 of 10; the merge is the model's own, Core only counts the lists.
    """
    started = time.monotonic()
    usage: dict[str, int] = {}
    if mode == "consensus":
        turns = await asyncio.gather(*(_one(provider, QUESTION + task.strip(), remaining) for _ in range(LISTS)))
        lists = [(turn.content or "").strip() for turn in turns]
        for turn in turns:
            _add(usage, dict(turn.usage))
        text = ""
        if all(lists):  # a missing list would turn "four of five" into something else; then there is no agenda
            body = "\n\n".join(f"List {index + 1}:\n{one}" for index, one in enumerate(lists))
            merged = await _one(provider, MERGE + body, remaining)
            _add(usage, dict(merged.usage))
            text = (merged.content or "").strip()
        trace("agenda", mode=mode, text=text, lists=lists, usage=usage, empty=not text,
              seconds=round(time.monotonic() - started, 2))
    else:
        turn = await _one(provider, QUESTION + task.strip(), remaining)
        text = (turn.content or "").strip()
        trace("agenda", text=text, usage=dict(turn.usage), seconds=round(time.monotonic() - started, 2), empty=not text)
    return f"\n\n{HEADER}\n{text}" if text else ""
