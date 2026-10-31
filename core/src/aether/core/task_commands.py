"""Commands the task statement shows, and whether the run has executed them (AETHER_CORE_RECORD=coverage).

Why (semantic-context relationship audit, 31 Oct): on configure-git-webserver every failing Luna run (17/17)
finished without ever running the task's own `git clone user@server:/git/server`; running it would have shown
that no SSH server was listening. Elsewhere Luna does run the commands the task shows (qemu, extract-elf, mips:
0 misses), so the fact is silent there. It relates the task's text to the run's own actions; it never says
whether a command is needed, only that none of the run's commands contained it.

A command is what the task shows in a code span (`...`), an indented line or a fenced block, when it starts like a
shell command. It counts as run when one executed command contains at least RUN_SHARE of its words, after hosts in
user@host and scheme://host are replaced (the task's host is the user's view of the machine). Placeholders such as
<input_dir> or a lone capital letter match anything.
"""

from __future__ import annotations

import re

RUN_SHARE = 0.8
MAX_COMMANDS = 8
_SPAN = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
_INDENT = re.compile(r"^(?: {4}|\t)(\S.*)$", re.M)
_HOSTS = ((re.compile(r"(\w)@[\w.-]+(:)"), r"\1@HOST\2"), (re.compile(r"(\w)@[\w.-]+\b"), r"\1@HOST"),
          (re.compile(r"(://)[\w.-]+"), r"\1HOST"))
_PLACEHOLDER = re.compile(r"^(<[^>]*>|[A-Z])$")
_PROGRAMS = frozenset(
    "ssh scp sftp git curl wget gcc g++ cc clang make cmake python python3 pip pip3 uv node npm npx cargo rustc go "
    "java javac mvn bash sh cat echo ls sqlite3 psql mysql redis-cli nc telnet docker pytest ruby perl Rscript julia "
    "gzip tar unzip openssl jq diff".split())


def shown(task: str) -> list[str]:
    """Shell commands the task statement shows, in order, at most MAX_COMMANDS."""
    lines = _SPAN.findall(task) + _INDENT.findall(task)
    for block in _FENCE.findall(task):
        lines += block.splitlines()
    out: list[str] = []
    for line in (x.strip() for x in lines):
        words = line.split()
        if len(words) < 2 or line in out:
            continue
        if words[0] in _PROGRAMS or words[0].startswith("./") or " && " in line or " | " in line:
            out.append(line)
    return out[:MAX_COMMANDS]


def _norm(text: str) -> str:
    for pattern, repl in _HOSTS:
        text = pattern.sub(repl, text)
    return text.replace('"', "").replace("'", "")


def ran(command: str, executed: list[str]) -> bool:
    """Whether one executed command contains at least RUN_SHARE of the shown command's words."""
    words = [w for w in _norm(command).split() if not _PLACEHOLDER.match(w)]
    if not words:
        return True
    for text in executed:
        seen = _norm(text)
        tokens = set(seen.split())
        if sum(w in tokens or w in seen for w in words) >= RUN_SHARE * len(words):
            return True
    return False


def not_run(task_commands: list[str], executed: list[str]) -> list[str]:
    return [c for c in task_commands if not ran(c, executed)]
