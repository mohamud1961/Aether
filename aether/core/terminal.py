"""Persistent named terminals inside the task container.

Each terminal is one long-lived bash fed through a FIFO. When ``script`` exists
the shell runs on a pseudo-terminal, so interactive programs (python, gdb, node)
and Ctrl-C behave normally. All output is appended to a log that stays in the
container; the model sees new output since its last look (head and tail when
large) and can grep the full log itself.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
import shlex
import time

from .env import CONTROL_DIR, Environment, put_bytes, run

VIEW_HEAD = 3_000
VIEW_TAIL = 8_000
MAX_TERMINALS = 8
_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[=>()][0-9A-Za-z]?")
_HEX = re.compile(r"\\x([0-9a-fA-F]{2})")
_MARK = re.compile(r"__AETHER_DONE_(\d+)_(\d+)__ ?([^\n]*)\n?")
# util-linux / busybox ``script`` gives the shell a pseudo-terminal; anything else falls back to a plain pipe.
_PTY_TEST = "command -v bash >/dev/null 2>&1 && script -qfc true /dev/null >/dev/null 2>&1 </dev/null"
_INIT = ("stty -echo 2>/dev/null; export PS1='' PS2='' PROMPT_COMMAND='' TERM=dumb PAGER=cat "
         "GIT_PAGER=cat SYSTEMD_PAGER=cat DEBIAN_FRONTEND=noninteractive; "
         "bind 'set enable-bracketed-paste off' 2>/dev/null; true\n")


@dataclass
class Session:
    name: str
    root: str
    pid: int
    pty: bool
    cursor: int = 0
    seq: int = 0
    pending: int = 0  # command whose completion marker has not been seen yet

    @property
    def log(self) -> str:
        return f"{self.root}/out.log"

    @property
    def fifo(self) -> str:
        return f"{self.root}/in"


def clean(text: str) -> str:
    text = _ANSI.sub("", text).replace("\r\n", "\n").replace("\r", "")
    return text


class Terminals:
    def __init__(self, env: Environment, workdir: str, clock, control_dir: str = CONTROL_DIR) -> None:
        self._env = env
        self._control_dir = control_dir
        self._workdir = workdir
        self._clock = clock  # callable -> remaining seconds
        self._sessions: dict[str, Session] = {}

    @property
    def names(self) -> list[str]:
        return sorted(self._sessions)

    async def _start(self, name: str) -> Session:
        if len(self._sessions) >= MAX_TERMINALS:
            raise ValueError(f"at most {MAX_TERMINALS} terminals; reuse one of {self.names}")
        root = f"{self._control_dir}/term/{name}"
        q = shlex.quote
        wrapper = "\n".join([
            "#!/bin/sh",
            f"cd {q(self._workdir)} 2>/dev/null || cd /",
            f"exec 3<> {q(root + '/in')}",
            f"if {_PTY_TEST}; then",
            f"  script -qfc 'bash --noprofile --norc -i' /dev/null <&3 >> {q(root + '/out.log')} 2>&1",
            "elif command -v bash >/dev/null 2>&1; then",
            f"  bash --noprofile --norc <&3 >> {q(root + '/out.log')} 2>&1",
            "else",
            f"  sh <&3 >> {q(root + '/out.log')} 2>&1",
            "fi",
            f"echo $? > {q(root + '/exit')}",
            "",
        ])
        res = await run(self._env, f"rm -rf {q(root)} && mkdir -p {q(root)} && mkfifo {q(root + '/in')} "
                                   f"&& : > {q(root + '/out.log')}")
        if res.code != 0:
            raise RuntimeError(f"terminal setup failed: {(res.stderr or res.stdout).strip()[:300]}")
        await put_bytes(self._env, wrapper.encode(), f"{root}/run.sh")
        res = await run(self._env,
            f"if command -v setsid >/dev/null 2>&1; then nohup setsid sh {q(root + '/run.sh')} >/dev/null 2>&1 </dev/null & "
            f"else nohup sh {q(root + '/run.sh')} >/dev/null 2>&1 </dev/null & fi; echo $!; "
            f"{_PTY_TEST} && echo pty || echo nopty")
        lines = res.stdout.split()
        if res.code != 0 or len(lines) < 2 or not lines[0].isdigit():
            raise RuntimeError(f"terminal launch failed: {(res.stderr or res.stdout).strip()[:300]}")
        session = Session(name, root, int(lines[0]), lines[1] == "pty")
        await self._write(session, _INIT + "printf '\\n__AETHER_DONE_%s_%s__ %s\\n' 0 \"$?\" \"$PWD\"\n")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            size, mark, _alive = await self._poll(session, 0)
            if mark:
                session.cursor = size
                break
            await asyncio.sleep(0.2)
        else:
            raise RuntimeError("terminal did not become ready within 15 s")
        self._sessions[name] = session
        return session

    async def _write(self, session: Session, text: str) -> None:
        await put_bytes(self._env, text.encode(), f"{session.root}/pending")
        q = shlex.quote
        res = await run(self._env, f"kill -0 {session.pid} 2>/dev/null || {{ echo dead; exit 3; }}; "
                                   f"cat {q(session.root + '/pending')} > {q(session.fifo)}", timeout_s=20)
        if res.code != 0:
            raise RuntimeError("terminal is not running")

    async def _poll(self, session: Session, seq: int | None) -> tuple[int, re.Match | None, bool]:
        q = shlex.quote
        probe = ("true" if seq is None else f"tail -c +{session.cursor + 1} {q(session.log)} "
                 f"| grep -a -o '__AETHER_DONE_{seq}_[0-9]*__ [^[:cntrl:]]*' | tail -n 1")
        res = await run(self._env, f"wc -c < {q(session.log)}; {probe}; "
                                   f"kill -0 {session.pid} 2>/dev/null && echo __ALIVE__ || echo __DEAD__")
        first, _, rest = res.stdout.partition("\n")
        size = int(first.strip() or 0)
        mark = None if seq is None else _MARK.search(clean(rest))
        return size, mark, "__ALIVE__" in rest

    async def _read(self, session: Session, start: int, end: int) -> str:
        q = shlex.quote
        n = end - start
        if n <= VIEW_HEAD + VIEW_TAIL:
            res = await run(self._env, f"tail -c +{start + 1} {q(session.log)} | head -c {n}")
            return res.stdout
        res = await run(self._env, f"tail -c +{start + 1} {q(session.log)} | head -c {VIEW_HEAD}; "
                                   f"printf '\\n\\x00SPLIT\\x00\\n'; tail -c +{start + 1} {q(session.log)} "
                                   f"| head -c {n} | tail -c {VIEW_TAIL}")
        head, _, tail = res.stdout.partition("\n\x00SPLIT\x00\n")
        return (f"{head}\n…[{n - VIEW_HEAD - VIEW_TAIL} bytes omitted; full output is in {session.log} "
                f"at byte offsets {start}-{end}; use grep/sed/tail on it]…\n{tail}")

    async def use(self, *, name: str = "main", input: str = "", mode: str = "command",
                  wait_s: float = 30.0, interrupt: bool = False) -> str:
        if not _NAME.match(name):
            raise ValueError("terminal name must be 1-32 chars of letters, digits, _ or -")
        if mode not in ("command", "keys"):
            raise ValueError("mode must be 'command' or 'keys'")
        session = self._sessions.get(name)
        note = ""
        if session is None:
            session = await self._start(name)
            note = f"[terminal {name} started{'' if session.pty else ' without a pty'}]\n"
        started = time.monotonic()
        wait_s = max(0.0, min(float(wait_s), 900.0, max(0.0, self._clock() - 5)))
        if interrupt:
            await self._write(session, "\x03")
            if not session.pty:  # no line discipline: signal the shell's children directly
                await run(self._env, f"for c in $(pgrep -P {session.pid}); do pkill -INT -P $c; sleep 0.3; pkill -TERM -P $c; done; true")
            await asyncio.sleep(0.5)
            session.pending = 0  # Ctrl-C discards queued input, including the old completion marker
            if not input:
                input, mode = "true", "command"
        if input and mode == "command":
            session.seq += 1
            session.pending = session.seq
            body = input if input.endswith("\n") else input + "\n"
            await self._write(session, body + f"printf '\\n__AETHER_DONE_%s_%s__ %s\\n' {session.seq} \"$?\" \"$PWD\"\n")
        elif input:
            await self._write(session, _HEX.sub(lambda m: chr(int(m.group(1), 16)), input))
        seq = session.pending or None
        size, mark, alive, last_size, stable_since = session.cursor, None, True, -1, time.monotonic()
        delay = 0.2
        while True:
            size, mark, alive = await self._poll(session, seq)
            if mark is not None or not alive:
                break
            now = time.monotonic()
            if size != last_size:
                last_size, stable_since = size, now
            if seq is None and now - started >= 0.5 and now - stable_since >= 1.5:
                break
            if now - started >= wait_s:
                break
            await asyncio.sleep(delay)
            delay = min(1.0, delay * 1.5)
        if mark is not None:
            session.pending = 0
        text = clean(await self._read(session, session.cursor, size))
        session.cursor = size
        text = _MARK.sub("", text).strip("\n")
        elapsed = time.monotonic() - started
        if not alive:
            self._sessions.pop(name, None)
            status = f"[terminal {name} exited; it restarts on next use]"
        elif mark is not None:
            status = f"[exit {mark.group(2)} · {elapsed:.1f}s · terminal {name} · cwd {mark.group(3).strip()}]"
        elif seq is not None:
            status = (f"[still running after {elapsed:.0f}s · terminal {name}; call again with empty input to "
                      f"keep waiting, use interrupt=true to stop it, or work in another terminal]")
        else:
            status = f"[{elapsed:.1f}s · terminal {name}]"
        return note + (text + "\n" if text else "(no new output)\n") + status
