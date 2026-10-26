"""Persistent named terminals inside the task container.

Each terminal is one long-lived bash fed through a FIFO. When ``script`` exists
the shell runs on a pseudo-terminal, so interactive programs (python, gdb, node)
and Ctrl-C behave normally. All output is appended to a log that stays in the
container; the model sees new output since its last look (head and tail when
large) and can grep the full log itself.
"""

from __future__ import annotations

import asyncio
import re
import shlex
import time
from dataclasses import dataclass, field

from .env import (
    CONTROL_DIR,
    Environment,
    ProcessCleanupError,
    alive_test,
    atomic_write,
    list_process_tree,
    process_identities,
    put_bytes,
    run,
    stop_process_tree,
)

VIEW_HEAD = 3_000
VIEW_TAIL = 8_000
MAX_TERMINALS = 8
# One tool call blocks the loop at most this long, so scheduled reviews and the elapsed-time readout reach the
# model while long jobs run (D1 extract-moves: one 902 s wait skipped a progress review and left 20 s at the end).
MAX_WAIT_S = 300.0
_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_ANSI = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[=>()][0-9A-Za-z]?"
)
_HEX = re.compile(r"\\x([0-9a-fA-F]{2})")
# seq, exit, optional per-stage exits of the command's last pipeline (bash only, joined by "."), cwd
_MARK = re.compile(r"__AETHER_DONE_(\d+)_(\d+)(?:_([\d.]+))?__ ?([^\n]*)\n?")
# bash: a RETURN trap fires as the sourced command file finishes, while PIPESTATUS still holds the stage exits of
# its last pipeline. The body is run unchanged (an appended capture line would land inside an unterminated
# heredoc) and the exit is the file's own. The trap is removed again, so a RETURN trap of the model's is lost.
_PIPE_TRAP = "builtin trap '__aether_ps=\"${PIPESTATUS[*]}\"' RETURN"
# util-linux / busybox ``script`` gives the shell a pseudo-terminal; anything else falls back to a plain pipe.
_PTY_TEST = "command -v bash >/dev/null 2>&1 && script -qfc true /dev/null >/dev/null 2>&1 </dev/null"
_PROMPT_RECEIPT = (
    "$(__aether_prompt_status=$?; builtin declare -F __aether_prompt_receipt >/dev/null "
    '&& __aether_prompt_receipt "$__aether_prompt_status")'
)
# One line per process: /proc/<pid>/stat, wait channel, command line. Plain sh + /proc, because many task images
# have no procps. Used to say what a still-running command is doing (D1 compcert: `opam install ... | tail` sat
# silent and asleep for 1300 s and the model saw only "(no new output)" five times before it looked).
_PROCS = (
    "cut -d' ' -f1 /proc/uptime 2>/dev/null; getconf CLK_TCK 2>/dev/null || echo 100; "
    "for d in /proc/[0-9]*; do s=$(cat $d/stat 2>/dev/null) || continue; w=$(cat $d/wchan 2>/dev/null); "
    "c=$(tr '\\0' ' ' < $d/cmdline 2>/dev/null | cut -c1-90); printf '%s\\t%s\\t%s\\n' \"$s\" \"$w\" \"$c\"; done"
)
# Every descendant of the given pids (plain sh + /proc: many task images have no procps), then TERM, then KILL.
# The parent pid is read after the ") " that ends the command name, which may itself contain spaces. Without
# /proc (macOS tests) it falls back to the process groups and direct children.

_WRAPPERS = ("run.sh", "script -qfc", "bash --noprofile --norc")
_STATES = {
    "R": "running",
    "S": "sleeping",
    "D": "in uninterruptible I/O",
    "T": "stopped",
    "t": "stopped by a tracer",
    "Z": "exited (zombie)",
}

_INIT = (
    "stty -echo 2>/dev/null; export PS1='' PS2='' PROMPT_COMMAND='' TERM=dumb PAGER=cat "
    "GIT_PAGER=cat SYSTEMD_PAGER=cat DEBIAN_FRONTEND=noninteractive; "
    "bind 'set enable-bracketed-paste off' 2>/dev/null; true\n"
)


class TerminalGone(RuntimeError):
    """The terminal's shell or its log is gone."""


@dataclass
class Session:
    name: str
    root: str
    pid: int
    pty: bool
    bash: bool = False  # the shell is bash (PIPESTATUS is available)
    cursor: int = 0
    seq: int = 0
    pending: int = 0  # command whose completion marker has not been seen yet
    last_size: int = 0
    grew_at: float = 0.0  # monotonic time the log last grew
    ready: bool = False
    identity: dict[str, str] = field(default_factory=dict)
    cleanup_warning: str = ""

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
    def __init__(
        self, env: Environment, workdir: str, clock, control_dir: str = CONTROL_DIR
    ) -> None:
        self._env = env
        self._control_dir = control_dir
        self._workdir = workdir
        self._clock = clock  # callable -> remaining seconds
        self.cleanup_uncertainties: list[str] = []
        self.cleanup_receipt: dict = {}
        self._sessions: dict[str, Session] = {}
        self._generations: dict[str, int] = {}
        self._launching: set[str] = (
            set()
        )  # PID files resolve a lost launch reply during cleanup
        self.left_running: list[
            str
        ] = []  # close(keep=True): processes left alive at run end

    @property
    def names(self) -> list[str]:
        return sorted(self._sessions)

    async def _start(self, name: str) -> Session:
        if len(self._sessions) + len(self._launching) >= MAX_TERMINALS:
            raise ValueError(
                f"at most {MAX_TERMINALS} terminals; reuse one of {self.names}"
            )
        generation = self._generations.get(name, 0)
        self._generations[name] = generation + 1
        # A dot is outside the accepted name alphabet, so generations cannot
        # collide with another model-chosen name (main-1 versus restarted main).
        suffix = name if generation == 0 else f"{name}.{generation}"
        root = f"{self._control_dir}/term/{suffix}"
        q = shlex.quote
        wrapper = "\n".join(
            [
                "#!/bin/sh",
                f"if [ -r /proc/$$/stat ]; then sed 's/.*) //' /proc/$$/stat | awk '{{print $20}}' > {q(root + '/birth')}; "
                f"else ps -p $$ -o lstart= | awk '{{$1=$1;print}}' > {q(root + '/birth')}; fi",
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
            ]
        )
        res = await run(
            self._env,
            f"rm -rf {q(root)} && mkdir -p {q(root)} && mkfifo {q(root + '/in')} && : > {q(root + '/out.log')}",
        )
        if res.code != 0:
            raise RuntimeError(
                f"terminal setup failed: {(res.stderr or res.stdout).strip()[:300]}"
            )
        await put_bytes(self._env, wrapper.encode(), f"{root}/run.sh")
        # `setsid -f` forks without the shell's `&`: a background job of a non-interactive shell starts with
        # SIGINT ignored, that disposition is inherited by every command in the terminal, and Ctrl-C did
        # nothing (found on Linux in D1; the macOS tests use the pipe path and never saw it).
        run_sh, pid_file = q(root + "/run.sh"), q(root + "/pid")
        # setsid changes sessions, not inherited ignored signal dispositions.
        # Reset the new shell's initial SIGINT, preserving later task traps.
        launch = (
            "python3 -c "
            + q(
                "import os,signal,sys;signal.signal(signal.SIGINT,signal.SIG_DFL);"
                'os.execvp("sh",["sh",*sys.argv[1:]])'
            )
            + " "
            + run_sh
        )
        self._launching.add(root)
        res = await run(
            self._env,
            f"if command -v setsid >/dev/null 2>&1 && setsid -f true >/dev/null 2>&1; then "
            f"nohup setsid -f {launch} >/dev/null 2>&1 </dev/null; "
            f"elif command -v setsid >/dev/null 2>&1; then nohup setsid {launch} >/dev/null 2>&1 </dev/null & "
            f"else nohup {launch} >/dev/null 2>&1 </dev/null & fi; "
            f"i=0; while [ ! -s {pid_file} ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done; cat {pid_file}; "
            f"{_PTY_TEST} && echo pty || echo nopty; command -v bash >/dev/null 2>&1 && echo bash || echo sh",
        )
        lines = res.stdout.split()
        if res.code != 0 or len(lines) < 2 or not lines[0].isdigit():
            raise RuntimeError(
                f"terminal launch failed: {(res.stderr or res.stdout).strip()[:300]}"
            )
        session = Session(
            name,
            root,
            int(lines[0]),
            lines[1] == "pty",
            bash=lines[2:3] == ["bash"],
            grew_at=time.monotonic(),
        )
        self._sessions[name] = session  # ownership precedes fallible initialization
        self._launching.remove(root)
        try:
            session.identity = await process_identities(self._env, [session.pid])
        except OSError as exc:
            session.cleanup_warning = (
                "[process identity unavailable; later cleanup may be unverified: "
                + str(exc)[:160]
                + "]\n"
            )
        init = _INIT
        if session.pty and session.bash:
            # SIGINT can skip the sourced line's normal completion writer.
            # A prompt callback proves Bash regained control and captures the
            # real exit status, without queuing text into a live interpreter.
            init += (
                "__aether_prompt_seq=0; __aether_prompt_owner=$$; __aether_prompt_receipt() { "
                "local __aether_prompt_rc=$1; "
                'if [ "${__aether_prompt_seq:-0}" -gt 0 ] && '
                '[ "$$" = "${__aether_prompt_owner:-0}" ]; then '
                f'local __aether_prompt_file={q(root)}/done_"$__aether_prompt_seq"; '
                'if [ ! -f "$__aether_prompt_file" ]; then '
                "builtin printf '__AETHER_DONE_%s_%s__ %s\\n' "
                '"$__aether_prompt_seq" "$__aether_prompt_rc" "$PWD" '
                '> "$__aether_prompt_file.tmp" && '
                'command mv -f "$__aether_prompt_file.tmp" "$__aether_prompt_file"; '
                'fi; fi; return "$__aether_prompt_rc"; };\n'
            )
        await self._write(
            session, init + 'printf \'\\n__AETHER_DONE_%s_%s__ %s\\n\' 0 "$?" "$PWD"\n'
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            size, mark, _alive = await self._poll(session, 0)
            if mark:
                session.cursor = size
                break
            await asyncio.sleep(0.2)
        else:
            raise RuntimeError("terminal did not become ready within 15 s")
        session.ready = True
        return session

    async def close(self, keep: bool = False) -> None:
        """Stop every terminal and everything started in it. The shell runs under ``script`` in a session of its
        own, so a process-group kill does not reach it or its jobs; the whole process tree is collected from
        /proc first (while parents are alive, so nohup'd jobs are still descendants), then TERM, then KILL.

        ``keep``: kill nothing. The processes still running under the terminals are recorded in ``left_running``
        (pid and command line, wrapper shells excluded) and the container is left as the agent left it."""
        pids = [s.pid for s in self._sessions.values()]
        unresolved = []
        identities = {
            k: v
            for session in self._sessions.values()
            for k, v in session.identity.items()
        }
        for root in list(self._launching):
            try:
                result = await run(
                    self._env,
                    f"cat {shlex.quote(root + '/pid')}; cat {shlex.quote(root + '/birth')}",
                )
                parts = result.stdout.splitlines()
                if (
                    result.code != 0
                    or len(parts) != 2
                    or not parts[0].isdigit()
                    or int(parts[0]) <= 1
                    or not parts[1].strip()
                ):
                    raise OSError("owned PID/birth identity unavailable")
                pids.append(int(parts[0]))
                identities[parts[0]] = parts[1].strip()
            except Exception as exc:
                unresolved.append(f"{root}: {type(exc).__name__}: {exc}")
        if pids and keep:
            self.left_running = await list_process_tree(
                self._env, list(set(pids)), identities=identities
            )
            self.cleanup_receipt = {
                "status": "retained",
                "observed_processes": self.left_running,
                "scope": "observed live descendants/groups; no signals sent",
            }
        elif pids:
            self.cleanup_receipt = await stop_process_tree(
                self._env, list(set(pids)), identities=identities
            )
        self._sessions.clear()
        if unresolved:
            raise OSError(
                "terminal cleanup could not resolve startup: " + "; ".join(unresolved)
            )
        self._launching.clear()
        if self.cleanup_uncertainties:
            self.cleanup_receipt = {
                **self.cleanup_receipt,
                "status": "partial_unverified",
                "prior_uncertainties": list(self.cleanup_uncertainties),
            }

    async def _write(
        self,
        session: Session,
        text: str,
        *,
        cmd: tuple[str, bytes] | None = None,
        wait: tuple[int, float] | None = None,
    ) -> tuple[int, re.Match | None, bool] | None:
        """Deliver input in one exec: the command file and the pending line (each written atomically, staged and
        committed bytes checked against their digest), then the fifo after the liveness check.

        With ``wait`` (seq, seconds) the same exec also waits in the container, up to 3 s, for that command's
        completion receipt and returns the (size, marker, alive) probe ``_poll`` would have returned.
        """
        q = shlex.quote
        log = q(session.log)
        steps = ([atomic_write(*cmd, 4)] if cmd else []) + [
            atomic_write(f"{session.root}/pending", text.encode(), 5),
            f"{alive_test(session.pid)} && [ -p {q(session.fifo)} ] || {{ echo dead; exit 3; }}",
            f"cat {q(session.root + '/pending')} > {q(session.fifo)} || exit 6",
        ]
        if wait is not None:
            seq, ticks = wait[0], int(max(0.0, min(wait[1], 3.0)) / 0.1)
            # The receipt is looked for before the size is taken, as in _poll.
            steps.append(
                f"i=0; m=''; while [ -r {log} ]; do m=$({self._probe(session, seq)});"
                f' [ -n "$m" ] && break; [ $i -ge {ticks} ] && break; {alive_test(session.pid)} || break; '
                f"sleep 0.1; i=$((i+1)); done; printf '%s\\n' \"$m\"; "
                f"{alive_test(session.pid)} && echo __ALIVE__ || echo __DEAD__; echo __SIZE__; wc -c < {log}"
            )
        res = await run(self._env, "; ".join(steps), timeout_s=20)
        if res.code == 3 and "dead" in res.stdout:
            raise TerminalGone(f"terminal {session.name} is not running")
        if res.code != 0:
            raise RuntimeError(
                f"could not send input to terminal {session.name}: {(res.stderr or res.stdout).strip()[:200]}"
            )
        return None if wait is None else self._probe_result(session, wait[0], res.stdout)

    def _probe(self, session: Session, seq: int | None) -> str:
        """Shell words printing the completion receipt of command ``seq`` (nothing while it runs)."""
        q = shlex.quote
        # Arbitrary command stdout must never be treated as an authoritative
        # shell completion receipt. Only the shell wrapper writes done_<seq>.
        # The startup marker (seq 0) predates this per-command mechanism.
        if seq is None:
            return "true"
        if seq == 0:
            return (
                f"tail -c +{session.cursor + 1} {q(session.log)} "
                f"| grep -a -o '__AETHER_DONE_0_[0-9._]*__ [^[:cntrl:]]*' | tail -n 1"
            )
        return f"cat {q(session.root + '/done_' + str(seq))} 2>/dev/null"

    def _probe_result(
        self, session: Session, seq: int | None, out: str
    ) -> tuple[int, re.Match | None, bool]:
        rest, _, size_text = out.rpartition("__SIZE__\n")
        if (
            not size_text.strip().isdigit()
        ):  # the log is gone (the control directory was deleted)
            raise TerminalGone(
                f"the log of terminal {session.name} ({session.log}) is missing"
            )
        size = int(size_text.strip())
        mark = None if seq is None else _MARK.search(clean(rest))
        return size, mark, "__ALIVE__" in rest

    async def _poll(
        self, session: Session, seq: int | None
    ) -> tuple[int, re.Match | None, bool]:
        q = shlex.quote
        # The marker is looked for before the size is taken: the other way round, a command that finished in
        # between showed its marker with the output cut at the earlier size (the rest came with the next call).
        res = await run(
            self._env,
            f"{self._probe(session, seq)}; {alive_test(session.pid)} && echo __ALIVE__ || echo __DEAD__; "
            f"echo __SIZE__; wc -c < {q(session.log)} 2>/dev/null",
        )
        return self._probe_result(session, seq, res.stdout)

    async def _read(self, session: Session, start: int, end: int) -> str:
        q = shlex.quote
        n = end - start
        if n <= VIEW_HEAD + VIEW_TAIL:
            res = await run(
                self._env, f"tail -c +{start + 1} {q(session.log)} | head -c {n}"
            )
            return res.stdout
        res = await run(
            self._env,
            f"tail -c +{start + 1} {q(session.log)} | head -c {VIEW_HEAD}; "
            f"printf '\\n\\x00SPLIT\\x00\\n'; tail -c +{start + 1} {q(session.log)} "
            f"| head -c {n} | tail -c {VIEW_TAIL}",
        )
        head, _, tail = res.stdout.partition("\n\x00SPLIT\x00\n")
        return (
            f"{head}\n…[{n - VIEW_HEAD - VIEW_TAIL} bytes omitted; full output is in {session.log} "
            f"at byte offsets {start}-{end}; use grep/sed/tail on it]…\n{tail}"
        )

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
            procs[int(pid_s)] = (
                int(f[1]),
                f[0],
                cpu,
                uptime - int(f[19]) / hz,
                wchan.strip(),
                cmd.strip() or comm,
            )
        tree, frontier = set(), {session.pid}
        while frontier:
            frontier = {
                p for p, v in procs.items() if v[0] in frontier and p not in tree
            }
            tree |= frontier
        shown = [
            (p, procs[p]) for p in tree if not any(w in procs[p][5] for w in _WRAPPERS)
        ]
        shown.sort(key=lambda item: -item[1][2])
        out = []
        for pid, (_ppid, state, cpu, age, wchan, cmd) in shown[:limit]:
            what = _STATES.get(state, state) + (
                f" in {wchan}" if state in "SD" and wchan not in ("", "0") else ""
            )
            out.append(f"{cmd} (pid {pid}, {what}, {cpu:.0f}s CPU in {age:.0f}s)")
        if len(shown) > limit:
            out.append(f"{len(shown) - limit} more")
        return out

    async def use(
        self,
        *,
        name: str = "main",
        input: str = "",
        mode: str = "command",
        wait_s: float = 30.0,
        interrupt: bool = False,
    ) -> str:
        if not _NAME.match(name):
            raise ValueError(
                "terminal name must be 1-32 chars of letters, digits, _ or -"
            )
        if mode not in ("command", "keys"):
            raise ValueError("mode must be 'command' or 'keys'")
        session = self._sessions.get(name)
        note = ""
        if session is not None and not session.ready:
            session = await self._restart(session)
            note = f"[terminal {name} startup was incomplete; a fresh terminal was started]\n"
            if mode == "keys":
                return (
                    note
                    + session.cleanup_warning
                    + "[Your keystrokes were not sent; start the intended program again before sending keys.]"
                )
        if session is None:
            session = await self._start(name)
            note = (
                f"[terminal {name} started{'' if session.pty else ' without a pty'}]\n"
            )
        if input and mode == "command" and not input.strip("\x03 \n"):
            # Ctrl-C as a command is an interrupt (P2 10-22: "\x03" refused as "input not sent" again and again)
            input, interrupt = "", True
            note += "[Ctrl-C in command input was sent as interrupt=true]\n"
        if input and mode == "command" and not interrupt and session.pending:
            # Look at the running command first. Writing the new one into the busy shell queued it unseen and
            # moved `pending` to it, so "still running" then described a command that had not started
            # (overfull-hbox e1: the model's kill commands waited ~100 s behind the solver).
            try:
                earlier = await self._collect(session, time.monotonic(), 0.0)
            except TerminalGone:
                earlier = ""
            if session.pending and name in self._sessions:
                return (
                    note
                    + (
                        f"[input not sent: terminal {name} is still running its previous command. To run it now, call "
                        f'terminal with name="{name}2" (a new terminal) or with interrupt=true to stop that command; '
                        f'to type into the running program instead, use mode="keys"]\n'
                    )
                    + earlier
                )
            note += earlier + "\n" if earlier else ""
        started = time.monotonic()
        wait_s = max(0.0, min(float(wait_s), MAX_WAIT_S, max(0.0, self._clock() - 5)))
        if interrupt and input:
            note += "[interrupt requested; supplied input was not submitted because shell readiness is unconfirmed]\n"
        try:
            first = await self._send(session, input, mode, interrupt, wait_s)
        except TerminalGone as gone:
            # It died between calls (killed, `exit`, its files deleted). The input never reached it, so it goes
            # to a fresh terminal; left as it was, every later call failed the same way (V3: 45 such errors).
            session = await self._restart(session)
            if mode == "keys":
                return (
                    note
                    + session.cleanup_warning
                    + (
                        f"[{gone}; its interactive program and shell state are gone. A fresh terminal "
                        f"{name} was started. Your keystrokes were not sent to the new shell; "
                        "start the intended program again before sending keys.]"
                    )
                )
            if interrupt:
                return (
                    note
                    + session.cleanup_warning
                    + (
                        f"[{gone}; a fresh terminal {name} was started. The interrupt targeted "
                        "the lost session, and supplied command input was not sent. Retry "
                        "the intended command explicitly.]"
                    )
                )
            note += (
                f"[{gone}; its shell state (cwd, variables, jobs) is gone. A fresh terminal {name} was "
                "started and your input sent to it]\n"
            )
            first = await self._send(session, input, mode, interrupt, wait_s)
        try:
            out = await self._collect(session, started, wait_s, first)
        except TerminalGone as gone:
            await self._restart(session, start=False)
            return (
                note
                + session.cleanup_warning
                + f"[{gone}; output since then is lost. Terminal {name} restarts on next use]"
            )
        keys = (
            _HEX.sub(lambda m: chr(int(m.group(1), 16)), input)
            if mode == "keys"
            else ""
        )
        if keys.strip() and keys.isprintable() and out.startswith("(no new output)"):
            # Silence does not reveal whether a foreground program consumed raw input.
            out += (
                "\n[no new output after these keys; the foreground program may have "
                "consumed them. Silence cannot show whether the input was accepted. "
                "Send \\n only if the current program expects it.]"
            )
        return note + session.cleanup_warning + out

    async def _restart(self, session: Session, start: bool = True) -> Session:
        warning = ""
        try:
            await stop_process_tree(
                self._env, [session.pid], identities=session.identity
            )
        except ProcessCleanupError as exc:
            if not exc.receipt.get("missing_roots"):
                raise
            warning = "[previous terminal root exited before cleanup observation; detached descendants unverified]\n"
            self.cleanup_uncertainties.append(str(exc))
        self._sessions.pop(session.name, None)
        fresh = await self._start(session.name) if start else session
        fresh.cleanup_warning += warning
        return fresh

    async def _send(
        self, session: Session, input: str, mode: str, interrupt: bool, wait_s: float = 0.0
    ) -> tuple[int, re.Match | None, bool] | None:
        if interrupt:
            await self._write(session, "\x03")
            if (
                not session.pty
            ):  # no line discipline: signal the shell's children directly
                await run(
                    self._env,
                    f"for c in $(pgrep -P {session.pid}); do pkill -INT -P $c; sleep 0.3; pkill -TERM -P $c; done; true",
                )
            # Interrupt delivery is not proof that the foreground program exited
            # or that the shell resumed reading commands. Keep the previous
            # completion marker pending until _collect actually observes it.
            # Never queue model shell text behind an unconfirmed foreground
            # interpreter: Python/REPLs can consume it as their own input.
            return
        if input and mode == "command":
            session.seq += 1
            session.pending = session.seq
            # The command runs from a file and the shell reads one line: `. file; printf marker`. Queuing the
            # body and the marker as separate stdin lines let any program that reads stdin (apt-get, dpkg,
            # read) swallow the marker, so the command looked "still running" until wait_s ran out.
            body = input if input.endswith("\n") else input + "\n"
            cmd_file = f"{session.root}/cmd_{session.seq}.sh"
            src, stages = f". {shlex.quote(cmd_file)}; __aether_s=$?", ""
            prompt = ""
            if session.pty and session.bash:
                # PS1 expansion sees the original command status even after
                # PROMPT_COMMAND. Leave that task-owned scalar/array untouched.
                # A quiet existence guard makes inherited PS1 harmless in a
                # nested Bash lacking our function; owner $$ prevents a child
                # that explicitly inherits the function from claiming recovery.
                # Replacing PS1/disabling promptvars inside the command can
                # remove this fallback: retain unverified pending, never infer
                # completion from interrupt delivery alone.
                prefix = shlex.quote(_PROMPT_RECEIPT)
                prompt = (
                    f"__aether_prompt_seq={session.seq}; "
                    f'case "$PS1" in {prefix}*) ;; *) PS1={prefix}"$PS1";; esac; '
                )
            if session.bash:
                # A RETURN trap is persistent model-owned Bash state. Prior code
                # installed ours unconditionally and removed it after sourcing
                # the command, destroying a user trap set before/during it.
                # Instrument only when no user RETURN trap is present, and
                # remove ours only if the sourced command left it unchanged.
                # With a user trap, overall shell exit is still authoritative;
                # optional per-stage PIPESTATUS is intentionally unavailable.
                src = (
                    "__aether_ps=; __aether_owns_return=0; "
                    'if [ -z "$(builtin trap -p RETURN)" ]; then '
                    f"{_PIPE_TRAP}; __aether_owns_return=1; "
                    '__aether_return_definition="$(builtin trap -p RETURN)"; '
                    "fi; "
                    f"{src}; "
                    'if [ "$__aether_owns_return" = 1 ] && '
                    '[ "$(builtin trap -p RETURN)" = "$__aether_return_definition" ]; '
                    "then builtin trap - RETURN; fi"
                )
                stages = "\"${__aether_ps:+_$(echo $__aether_ps | tr ' ' .)}\""
            # Write the completion receipt outside stdout, atomically AFTER
            # the original command returns to the shell. A program printing a
            # completion-looking line cannot forge command completion.
            marker = f"{session.root}/done_{session.seq}"
            temporary_marker = f"{marker}.tmp"
            return await self._write(
                session,
                f"{prompt}{src}; printf '\\n__AETHER_DONE_%s_%s{'%s' if stages else ''}__ %s\\n' "
                f'{session.seq} "$__aether_s" {stages} "$PWD" > {shlex.quote(temporary_marker)} '
                f"&& mv -f {shlex.quote(temporary_marker)} {shlex.quote(marker)}\n",
                cmd=(cmd_file, body.encode()),
                wait=(session.seq, wait_s),
            )
        elif input:
            keys = _HEX.sub(lambda m: chr(int(m.group(1), 16)), input)
            # Raw Ctrl-C might be swallowed by a foreground program. As with
            # interrupt=true, retain pending until the original marker proves
            # the shell actually resumed execution.
            await self._write(session, keys)

    async def _collect(
        self,
        session: Session,
        started: float,
        wait_s: float,
        first: tuple[int, re.Match | None, bool] | None = None,
    ) -> str:
        name = session.name
        seq = session.pending or None
        size, mark, alive, last_size, stable_since = (
            session.cursor,
            None,
            True,
            -1,
            time.monotonic(),
        )
        delay = 0.2
        while True:
            if first is not None:  # already waited for the receipt inside the send's own exec
                size, mark, alive = first
                first = None
            else:
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
        # Runtime completion receipts are out-of-band. Keep user/program
        # stdout verbatim even if it resembles our completion protocol.
        text = text.strip("\n")
        elapsed = time.monotonic() - started
        if not alive:
            self._sessions.pop(name, None)
            status = f"[terminal {name} exited; it restarts on next use]"
        elif mark is not None:
            stages = (mark.group(3) or "").split(".")
            piped = (
                f" · last pipeline's stage exits {' | '.join(stages)}"
                if set(stages) - {"0"} and len(stages) > 1
                else ""
            )
            status = f"[exit {mark.group(2)}{piped} · {elapsed:.1f}s · terminal {name} · cwd {mark.group(4).strip()}]"
        elif seq is not None:
            quiet = time.monotonic() - session.grew_at
            status = (
                f"[still running after {elapsed:.0f}s · "
                + (f"no new output for {quiet:.0f}s · " if quiet >= 10 else "")
                + f"terminal {name}; call again with empty input to keep waiting, use interrupt=true to "
                f"stop it, or work in another terminal]"
            )
            procs = await self._processes(session)
            if procs:
                status += "\n[its processes: " + "; ".join(procs) + "]"
        else:
            status = f"[{elapsed:.1f}s · terminal {name}]"
        return (text + "\n" if text else "(no new output)\n") + status
