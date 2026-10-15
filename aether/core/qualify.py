"""Which acceptance checks may be trusted to hold a finish: SpecHarness's disposition rule (arXiv 2609.29921).

A check written before the work (``contract``) can be wrong in ways the trial on the unfinished state cannot show:
it can assume where things are, re-implement a tool the task names, or read the task more literally than the task
needs (A1, 13 Oct 2026: 42% of correct states held). SpecHarness lets an obligation block completion only when its
parameters are grounded in the source and its validator is qualified on cases with known outcomes; everything else
stays advisory. Here, mechanically, a check is **hard** only if all of these hold:

- **grounded**: it names at least one anchor, and every anchor is the task's own words (whitespace and case aside);
- **accepts a correct result**: it passes the writer's invented finished state, twice (deterministic);
- **rejects a violation**: after the writer's violation command (which breaks exactly this requirement in that
  invented state) it fails, and it still runs.

Each check is tried in its own sibling of the untouched clone, since a violation changes the state. A check whose
only problem is a missing tool that the task itself names (primer3's ``oligotm``, absent until the work installs
it) is **pending**, not dropped: rejecting it pushed every A1 dna writer into re-implementing the tool, wrongly.
A pending check cannot be qualified before the work, so it is advisory.

What it cannot do: an anchor shows the words are the task's, not that the check reads them as the grader does
(A1's literal ``to,from``), and a violation the writer invents tests the check against the writer's own idea of
wrong. It screens out checks that rest on invented facts; it does not make a check right.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable

from .env import Environment, run

CHECK_TIMEOUT_S = 60
_MISSING = re.compile(r"(?:^|[\s:])([\w.+-]+): (?:command )?not found")


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def pending_tool(code: int | None, output: str, task: str) -> str:
    """The missing command, if the check could not run only because a tool the task names is not installed yet."""
    if code not in (126, 127) and "not found" not in output:
        return ""
    words = set(re.findall(r"[\w.+-]+", task.lower()))
    for name in _MISSING.findall(output):
        if name.lower() in words:
            return name
    return ""


def grounded(anchors: Iterable[Any], task: str) -> tuple[bool, list[str]]:
    """All anchors are the task's words; at least one is given. Returns (grounded, anchors not found)."""
    anchors = [a for a in anchors if _norm(a)]
    task_n = _norm(task)
    missing = [str(a)[:120] for a in anchors if _norm(a) not in task_n]
    return bool(anchors) and not missing, missing


@dataclass(frozen=True)
class Disposition:
    check: int
    hard: bool
    grounded: bool
    accepts_example: bool
    rejects_violation: bool
    reason: str

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


def _failed(code: int | None, output: str) -> bool:
    """Ran and said no: a non-zero exit that is not a missing tool, a timeout or an interpreter error."""
    from .contract import _cannot_run  # one definition of "cannot run"

    return code not in (0, None, 124) and not _cannot_run(code, output)


async def _trial(
    env: Environment, command: str, example: str, violation: str, workdir: str
) -> tuple[bool, bool, str]:
    sibling = await env.sibling()
    try:
        made = await run(sibling, example, timeout_s=CHECK_TIMEOUT_S * 2, cwd=workdir)
        if made.code != 0:
            return False, False, f"example did not run (exit {made.code})"
        first = await run(sibling, command, timeout_s=CHECK_TIMEOUT_S, cwd=workdir)
        second = await run(sibling, command, timeout_s=CHECK_TIMEOUT_S, cwd=workdir)
        accepts = first.code == 0 and second.code == 0
        if not violation.strip():
            return accepts, False, "no violation given"
        broke = await run(sibling, violation, timeout_s=CHECK_TIMEOUT_S, cwd=workdir)
        if broke.code != 0:
            return accepts, False, f"violation did not run (exit {broke.code})"
        after = await run(sibling, command, timeout_s=CHECK_TIMEOUT_S, cwd=workdir)
        rejects = _failed(after.code, after.stdout + after.stderr)
        return (
            accepts,
            rejects,
            "" if rejects else f"passes the violation (exit {after.code})",
        )
    finally:
        await sibling.close()


async def qualify(
    env: Environment,
    checks: list[tuple[int, str, dict[str, Any]]],
    *,
    example: str,
    task: str,
    workdir: str,
) -> list[Disposition]:
    """Dispositions for ``(id, command, raw submission)`` triples, tried on siblings of the untouched clone ``env``."""
    out = []
    for cid, command, raw in checks:
        is_grounded, missing = grounded(raw.get("anchors") or [], task)
        accepts, rejects, why = await _trial(
            env, command, example, str(raw.get("violation") or ""), workdir
        )
        reasons = (
            []
            if is_grounded
            else [f"anchors not in the task: {missing or 'none given'}"]
        )
        if not accepts:
            reasons.append("does not pass the example twice")
        if why and accepts:
            reasons.append(why)
        hard = is_grounded and accepts and rejects
        out.append(
            Disposition(cid, hard, is_grounded, accepts, rejects, "; ".join(reasons))
        )
    return out
