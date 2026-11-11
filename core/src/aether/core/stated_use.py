"""The task's own literal commands, run once when the work first becomes usable (AETHER_CORE_STATED_USE=on).

Why (11 Nov, g3/MISSION_LOG.md STATED-USE and P1): a run that never executed the command the task says the
requester will run passed 0 of 21 times outside one task, and showing that command's real output changed the next
action only where it had not been seen before. The harness does not decide what the task means. It takes command
text that is literally present in the task, by lexical rules only, and runs it as written.

Mechanics, all lexical or measured:
- commands(): indented lines, backticked spans with arguments, and an absolute path followed by arguments
  that are not plain words (a file name, a quoted string, an option). Nothing is inferred; text that is not a command is dropped at run time because its first word does
  not resolve to a program or file.
- It fires once, after a tool call that names a path the task mentions which did not exist when first checked and
  exists now. Commands run in a scratch directory, each with a time limit; raw output is appended to that tool
  result. Never blocks, never judges.
"""

from __future__ import annotations

import json
import re
import shlex
from typing import Any

from .env import run

ENV_FLAG = "AETHER_CORE_STATED_USE"
SCRATCH = "/tmp/aether-stated-use"
EACH_TIMEOUT_S = 60
OUTPUT_LIMIT = 1600

_ARG = r"(?:\"[^\"\n]*\"|'[^'\n]*'|[\w./:@=+-]+)"
_ABS_COMMAND = re.compile(rf"(?<![\w.@:/-])(/[\w./-]+(?:[ \t]+{_ARG}){{2,}})")
_PATH = re.compile(r"(?<![\w.@/-])(/[\w.-]+(?:/[\w.-]+)+)")
_UNSAFE = re.compile(r"(^|[\s;&|])(rm|sudo|mkfs|dd|shutdown|reboot|kill|killall)\b")
_FIRST_WORD = re.compile(r"^[A-Za-z0-9_./-]+$")


def commands(task: str) -> list[str]:
    """Command text literally present in the task, in order of appearance, at most eight."""
    found: list[tuple[int, str]] = []
    offset = 0
    for line in task.splitlines(keepends=True):
        text = line.rstrip("\n")
        if re.match(r"^(?: {4,}|\t)\S", text) and " " in text.strip():
            found.append((offset, text.strip()))
        offset += len(line)
    for match in re.finditer(r"`([^`\n]+)`", task):
        if " " in match.group(1).strip():
            found.append((match.start(), match.group(1).strip()))
    for match in _ABS_COMMAND.finditer(task):
        words = shlex.split(match.group(1), posix=False)
        args = []
        for word in words[1:]:  # arguments end at the first plain word: prose, not a command line
            if word.isalpha():
                break
            args.append(word)
        if args:
            found.append((match.start(), " ".join([words[0], *args])))
    kept: list[str] = []
    for _, text in sorted(found):
        first = text.split()[0]
        if text in kept or any(text in other for other in kept) or _UNSAFE.search(text) or not _FIRST_WORD.match(first):
            continue
        kept.append(text)
    return kept[:8]


def paths(task: str) -> list[str]:
    """Absolute paths written in the task."""
    return list(dict.fromkeys(p.rstrip(".,;:)") for p in _PATH.findall(task)))[:16]


async def after(s: Any, name: str, args: dict[str, Any]) -> str:
    """Text to append to this tool result: the task's commands and their raw output, once; '' otherwise."""
    state = s.__dict__.setdefault("_stated_use", {"cmds": commands(s.task), "missing": None, "fired": False})
    if state["fired"] or not state["cmds"]:
        return ""
    q = shlex.quote
    if state["missing"] is None:
        absent = []
        for path in paths(s.task):
            if (await run(s.env, f"test -e {q(path)}", timeout_s=20)).code != 0:
                absent.append(path)
        state["missing"] = absent
        s.trace("stated_use_setup", commands=state["cmds"], absent_paths=absent)
    mentioned = json.dumps(args, ensure_ascii=False)
    now = [p for p in state["missing"] if p in mentioned and (await run(s.env, f"test -e {q(p)}", timeout_s=20)).code == 0]
    if not now:
        return ""
    runnable = []
    for text in state["cmds"]:  # a command whose program does not exist yet cannot be run; wait for it
        first = text.split()[0]
        if (await run(s.env, f"command -v {q(first)} >/dev/null 2>&1 || [ -x {q(first)} ]", timeout_s=20)).code == 0:
            runnable.append(text)
    if not runnable:
        return ""
    state["fired"] = True
    lines = [f"rm -rf {SCRATCH} && mkdir -p {SCRATCH} && cd {SCRATCH} || exit 0"]
    for text in runnable:
        lines.append(
            f"echo {q('$ ' + text)}; timeout {EACH_TIMEOUT_S} bash -c {q(text + ' </dev/null')} 2>&1 | tail -c 400; "
            'echo "[exit ${PIPESTATUS[0]}]"'
        )
    result = await run(s.env, "\n".join(lines), timeout_s=EACH_TIMEOUT_S * len(runnable) + 30, cwd="/")
    output = ((result.stdout or "") + (result.stderr or "")).strip()[-OUTPUT_LIMIT:]
    s.trace("stated_use_run", became_present=now, output=output)
    if not output:
        return ""
    return f"\n\n[The commands written in the task, run just now as they are written, in {SCRATCH}]\n{output}"
