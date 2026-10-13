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
# One tool call blocks the loop at most this long, so scheduled reviews and the elapsed-time readout reach the
# model while long jobs run (D1 extract-moves: one 902 s wait skipped a progress review and left 20 s at the end).
MAX_WAIT_S = 300.0
_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[=>()][0-9A-Za-z]?")
_HEX = re.compile(r"\\x([0-9a-fA-F]{2})")
_MARK = re.compile(r"__AETHER_DONE_(\d+)_(\d+)__ ?([^\n]*)\n?")
# util-linux / busybox ``script`` gives the shell a pseudo-terminal; anything else falls back to a plain pipe.
_PTY_TEST = "command -v bash >/dev/null 2>&1 && script -qfc true /dev/null >/dev/null 2>&1 </dev/null"
# One line per process: /proc/<pid>/stat, wait channel, command line. Plain sh + /proc, because many task images
# have no procps. Used to say what a still-running command is doing (D1 compcert: `opam install ... | tail` sat
# silent and asleep for 1300 s and the model saw only "(no new output)" five times before it looked).
_PROCS = ("cut -d' ' -f1 /proc/uptime 2>/dev/null; getconf CLK_TCK 2>/dev/null || echo 100; "
          "for d in /proc/[0-9]*; do s=$(cat $d/stat 2>/dev/null) || continue; w=$(cat $d/wchan 2>/dev/null); "
          "c=$(tr '\\0' ' ' < $d/cmdline 2>/dev/null | cut -c1-90); printf '%s\\t%s\\t%s\\n' \"$s\" \"$w\" \"$c\"; done")
# Every descendant of the given pids (plain sh + /proc: many task images have no procps), then TERM, then KILL.
# The parent pid is read after the ") " that ends the command name, which may itself contain spaces. Without
# /proc (macOS tests) it falls back to the process groups and direct children.
_KILL_TREE = ("if [ ! -d /proc/1 ]; then for r in {roots}; do kill -TERM -$r 2>/dev/null; pkill -TERM -P $r "
              "2>/dev/null; kill -TERM $r 2>/dev/null; done; exit 0; fi; "
              "all='{roots}'; frontier='{roots}'; while [ -n \"$frontier\" ]; do next=''; "
              "for d in /proc/[0-9]*; do p=${{d#/proc/}}; "
              "pp=$(sed 's/.*) //' $d/stat 2>/dev/null | cut -d' ' -f2) || continue; "
              "for f in $frontier; do [ \"$pp\" = \"$f\" ] && next=\"$next $p\"; done; done; "
              "all=\"$all $next\"; frontier=$next; done; kill -TERM $all 2>/dev/null; sleep 0.5; "
              "kill -KILL $all 2>/dev/null; true")
_WRAPPERS = ("run.sh", "script -qfc", "bash --noprofile --norc")
_STATES = {"R": "running", "S": "sleeping", "D": "in uninterruptible I/O", "T": "stopped", "t": "stopped by a tracer",
           "Z": "exited (zombie)"}
_INIT = ("stty -echo 2>/dev/null; export PS1='' PS2='' PROMPT_COMMAND='' TERM=dumb PAGER=cat "
         "GIT_PAGER=cat SYSTEMD_PAGER=cat DEBIAN_FRONTEND=noninteractive; "
         "bind 'set enable-bracketed-paste off' 2>/dev/null; true\n")


class TerminalGone(RuntimeError):
    """The terminal's shell or its log is gone."""


@dataclass
class Session:
    name: str
    root: str
    pid: int
    pty: bool
    cursor: int = 0
    seq: int = 0
    pending: int = 0  # command whose completion marker has not been seen yet
    last_size: int = 0
    grew_at: float = 0.0  # monotonic time the log last grew

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
            f"echo $$ > {q(root + '/pid')}",
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
        # `setsid -f` forks without the shell's `&`: a background job of a non-interactive shell starts with
        # SIGINT ignored, that disposition is inherited by every command in the terminal, and Ctrl-C did
        # nothing (found on Linux in D1; the macOS tests use the pipe path and never saw it).
        run_sh, pid_file = q(root + "/run.sh"), q(root + "/pid")
        res = await run(self._env,
            f"if command -v setsid >/dev/null 2>&1 && setsid -f true >/dev/null 2>&1; then "
            f"nohup setsid -f sh {run_sh} >/dev/null 2>&1 </dev/null; "
            f"elif command -v setsid >/dev/null 2>&1; then nohup setsid sh {run_sh} >/dev/null 2>&1 </dev/null & "
            f"else nohup sh {run_sh} >/dev/null 2>&1 </dev/null & fi; "
            f"i=0; while [ ! -s {pid_file} ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done; cat {pid_file}; "
            f"{_PTY_TEST} && echo pty || echo nopty")
        lines = res.stdout.split()
        if res.code != 0 or len(lines) < 2 or not lines[0].isdigit():
            raise RuntimeError(f"terminal launch failed: {(res.stderr or res.stdout).strip()[:300]}")
        session = Session(name, root, int(lines[0]), lines[1] == "pty", grew_at=time.monotonic())
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

    async def close(self) -> None:
        """Stop every terminal and everything started in it. The shell runs under ``script`` in a session of its
        own, so a process-group kill does not reach it or its jobs; the whole process tree is collected from
        /proc first (while parents are alive, so nohup'd jobs are still descendants), then TERM, then KILL."""
        if self._sessions:
            roots = " ".join(str(s.pid) for s in self._sessions.values())
            await run(self._env, _KILL_TREE.format(roots=roots), timeout_s=30)
        self._sessions.clear()

    async def _write(self, session: Session, text: str) -> None:
        await put_bytes(self._env, text.encode(), f"{session.root}/pending")
        q = shlex.quote
        res = await run(self._env, f"kill -0 {session.pid} 2>/dev/null && [ -p {q(session.fifo)} ] || {{ echo dead; exit 3; }}; "
                                   f"cat {q(session.root + '/pending')} > {q(session.fifo)}", timeout_s=20)
        if res.code == 3 and "dead" in res.stdout:
            raise TerminalGone(f"terminal {session.name} is not running")
        if res.code != 0:
            raise RuntimeError(f"could not send input to terminal {session.name}: "
                               f"{(res.stderr or res.stdout).strip()[:200]}")

    async def _poll(self, session: Session, seq: int | None) -> tuple[int, re.Match | None, bool]:
        q = shlex.quote
        probe = ("true" if seq is None else f"tail -c +{session.cursor + 1} {q(session.log)} "
                 f"| grep -a -o '__AETHER_DONE_{seq}_[0-9]*__ [^[:cntrl:]]*' | tail -n 1")
        # The marker is looked for before the size is taken: the other way round, a command that finished in
        # between showed its marker with the output cut at the earlier size (the rest came with the next call).
        res = await run(self._env, f"{probe}; kill -0 {session.pid} 2>/dev/null && echo __ALIVE__ || echo __DEAD__; "
                                   f"echo __SIZE__; wc -c < {q(session.log)} 2>/dev/null")
        rest, _, size_text = res.stdout.rpartition("__SIZE__\n")
        if not size_text.strip().isdigit():  # the log is gone (the control directory was deleted)
            raise TerminalGone(f"the log of terminal {session.name} ({session.log}) is missing")
        size = int(size_text.strip())
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

    async def _processes(self, session: Session, limit: int = 4) -> list[str]:
        """What the terminal's command is doing: its live processes, busiest first (empty without /proc)."""
        res = await run(self._env, _PROCS)
        head = res.stdout.split("\n", 2)
        if res.code != 0 or len(head) < 3:
            return []
        try:
            uptime, hz = float(head[0]), float(head[1]) or 100.0
        except ValueError:
            return []
        procs: dict[int, tuple[int, str, float, float, str, str]] = {}
        for line in head[2].splitlines():
            stat, _, rest = line.partition("\t")
            wchan, _, cmd = rest.partition("\t")
            pid_s, _, after = stat.partition(" (")
            comm, _, fields = after.rpartition(") ")
            f = fields.split()
            if not pid_s.isdigit() or len(f) < 20:
                continue
            cpu = (int(f[11]) + int(f[12])) / hz
            procs[int(pid_s)] = (int(f[1]), f[0], cpu, uptime - int(f[19]) / hz, wchan.strip(), cmd.strip() or comm)
        tree, frontier = set(), {session.pid}
        while frontier:
            frontier = {p for p, v in procs.items() if v[0] in frontier and p not in tree}
            tree |= frontier
        shown = [(p, procs[p]) for p in tree if not any(w in procs[p][5] for w in _WRAPPERS)]
        shown.sort(key=lambda item: -item[1][2])
        out = []
        for pid, (_ppid, state, cpu, age, wchan, cmd) in shown[:limit]:
            what = _STATES.get(state, state) + (f" in {wchan}" if state in "SD" and wchan not in ("", "0") else "")
            out.append(f"{cmd} (pid {pid}, {what}, {cpu:.0f}s CPU in {age:.0f}s)")
        if len(shown) > limit:
            out.append(f"{len(shown) - limit} more")
        return out

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
        wait_s = max(0.0, min(float(wait_s), MAX_WAIT_S, max(0.0, self._clock() - 5)))
        try:
            await self._send(session, input, mode, interrupt)
        except TerminalGone as gone:
            # It died between calls (killed, `exit`, its files deleted). The input never reached it, so it goes
            # to a fresh terminal; left as it was, every later call failed the same way (V3: 45 such errors).
            session = await self._restart(session)
            note += (f"[{gone}; its shell state (cwd, variables, jobs) is gone. A fresh terminal {name} was "
                     "started and your input sent to it]\n")
            await self._send(session, input, mode, interrupt)
        try:
            return note + await self._collect(session, started, wait_s)
        except TerminalGone as gone:
            await self._restart(session, start=False)
            return note + f"[{gone}; output since then is lost. Terminal {name} restarts on next use]"

    async def _restart(self, session: Session, start: bool = True) -> Session:
        self._sessions.pop(session.name, None)
        await run(self._env, _KILL_TREE.format(roots=session.pid), timeout_s=30)
        return await self._start(session.name) if start else session

    async def _send(self, session: Session, input: str, mode: str, interrupt: bool) -> None:
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
            # The command runs from a file and the shell reads one line: `. file; printf marker`. Queuing the
            # body and the marker as separate stdin lines let any program that reads stdin (apt-get, dpkg,
            # read) swallow the marker, so the command looked "still running" until wait_s ran out.
            body = input if input.endswith("\n") else input + "\n"
            cmd_file = f"{session.root}/cmd_{session.seq}.sh"
            await put_bytes(self._env, body.encode(), cmd_file)
            await self._write(session, f". {shlex.quote(cmd_file)}; printf '\\n__AETHER_DONE_%s_%s__ %s\\n' "
                                       f"{session.seq} \"$?\" \"$PWD\"\n")
        elif input:
            keys = _HEX.sub(lambda m: chr(int(m.group(1), 16)), input)
            await self._write(session, keys)
            if "\x03" in keys:  # Ctrl-C typed as keys discards the pending marker just as interrupt=true does
                await asyncio.sleep(0.5)
                session.pending = 0

    async def _collect(self, session: Session, started: float, wait_s: float) -> str:
        name = session.name
        seq = session.pending or None
        size, mark, alive, last_size, stable_since = session.cursor, None, True, -1, time.monotonic()
        delay = 0.2
        while True:
            size, mark, alive = await self._poll(session, seq)
            now = time.monotonic()
            if size != session.last_size:
                session.last_size, session.grew_at = size, now
            if mark is not None or not alive:
                break
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
            quiet = time.monotonic() - session.grew_at
            status = (f"[still running after {elapsed:.0f}s · "
                      + (f"no new output for {quiet:.0f}s · " if quiet >= 10 else "")
                      + f"terminal {name}; call again with empty input to keep waiting, use interrupt=true to "
                      f"stop it, or work in another terminal]")
            procs = await self._processes(session)
            if procs:
                status += "\n[its processes: " + "; ".join(procs) + "]"
        else:
            status = f"[{elapsed:.1f}s · terminal {name}]"
        return (text + "\n" if text else "(no new output)\n") + status
