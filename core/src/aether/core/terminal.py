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

from .env import CONTROL_DIR, Environment, alive_test, run
from . import facts_probe, facts_replay
from .terminal_procs import describe_processes
from .terminal_session import (  # noqa: F401 (some names re-exported)
    MAX_TERMINALS, Session, TerminalGone, TerminalLifecycle, _ASKS, _text, clean,
)
from .transfer import INLINE_BYTES, atomic_write, put_bytes

VIEW_HEAD = 3_000
VIEW_TAIL = 8_000
# One tool call blocks the loop at most this long, so scheduled reviews and the elapsed-time readout reach the
# model while long jobs run (D1 extract-moves: one 902 s wait skipped a progress review and left 20 s at the end).
MAX_WAIT_S = 300.0
KEYS_SILENT_S = 10.0  # keys with no output at all return after this; empty input still waits the full wait_s
PROMPT_QUIET_S = 5.0  # a running command quiet this long with a prompt as its last line returns early
_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_HEX = re.compile(r"\\x([0-9a-fA-F]{2})")
# seq, exit, optional per-stage exits of the command's last pipeline (bash only, joined by "."), cwd
_MARK = re.compile(r"__AETHER_DONE_(\d+)_(\d+)(?:_([\d.]+))?__ ?([^\n]*)\n?")
# bash: a RETURN trap fires as the sourced command file finishes, while PIPESTATUS still holds the stage exits of
# its last pipeline. The body is run unchanged (an appended capture line would land inside an unterminated
# heredoc) and the exit is the file's own. It is installed only when the model has no RETURN trap and removed only
# if the command left it unchanged (see _send), so a RETURN trap of the model's survives.
_PIPE_TRAP = "builtin trap '{ __aether_ps=\"${PIPESTATUS[*]}\"; } 2>/dev/null' RETURN"
_PROMPT_RECEIPT = (
    "$({ __aether_prompt_status=$?; set +x; } 2>/dev/null; builtin declare -F __aether_prompt_receipt >/dev/null "
    '&& __aether_prompt_receipt "$__aether_prompt_status")'
)
# A model's `set -x` persists in its shell and traced every line Aether adds around a command into the result; with
# head/tail truncation the trace of our own bookkeeping was all the model saw (configure-git, 30 Oct). Our lines run
# with xtrace off ({ ...; } 2>/dev/null hides the switch itself); the model's xtrace state is restored on its command
# file's first line and after it. The test of $- is POSIX, so it works in sh as well as bash.
_XSTATE = '__aether_x=; [ "${-#*x}" = "$-" ] || __aether_x=1; set +x; '
_QUIET = "{ " + _XSTATE + "} 2>/dev/null; "
_TRACE_BACK = '{ [ -z "$__aether_x" ] || set -x; } 2>/dev/null; '
_CAPTURE = "{ __aether_s=$?; " + _XSTATE + "} 2>/dev/null"  # re-read: the command may have run set -x or set +x


class Terminals(TerminalLifecycle):
    def __init__(
        self, env: Environment, workdir: str, clock, control_dir: str = CONTROL_DIR,
        command_names: tuple[str, ...] = (), capture_state: bool = False,
    ) -> None:
        facts_probe.terminal_scope(command_names)
        self._env = env
        self._command_names = command_names
        self._capture_state = capture_state
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

    def observed_session(self, name: str) -> dict | None:
        """Return only session facts established by its last terminal observation."""
        return facts_probe.terminal_observation(self._sessions.get(name), self._generations.get(name))

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
        # A done_<seq> already on disk (stale, or planted before the send) must not complete this command.
        clear = [f"rm -f {q(f'{session.root}/done_{wait[0]}')} || exit 7"] if wait is not None and wait[0] else []
        steps = clear + ([atomic_write(*cmd, 4)] if cmd else []) + [
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
                f"{alive_test(session.pid)} && echo __ALIVE__ || echo __DEAD__; echo __SIZE__; wc -c < {log} 2>/dev/null; true"
            )
        res = await run(self._env, "; ".join(steps), timeout_s=20)
        if res.code == 3 and "dead" in res.stdout:
            raise TerminalGone(f"terminal {session.name} is not running")
        if res.code != 0:
            raise RuntimeError(
                f"could not send input to terminal {session.name}: {(res.stderr or res.stdout).strip()[:200]}"
            )
        if wait is None:
            return None
        try:
            return self._probe_result(session, wait[0], res.stdout)
        except TerminalGone:  # the input was delivered; _collect observes and reports the missing log itself
            return None

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
        cleaned = clean(rest)
        mark = None if seq is None else _MARK.search(cleaned)
        if mark is not None:
            suffix = mark.string[mark.end():]
            session.pending_resolution, session.pending_env_names = facts_replay.parse_terminal_receipt(self._command_names, suffix, self._capture_state)
            bare = suffix in ("__ALIVE__\n", "__DEAD__\n")
            session.cwd_receipt_ambiguous = cleaned != rest or not (bare or session.pending_resolution is not None)
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
        # The bytes travel as base64 and are decoded here: the environment decodes command output as strict UTF-8, so
        # one byte that is not (binary output, or a character cut by head -c) failed the read, and as the cursor did
        # not move every later call reread it and failed too (path-tracing baseline: 21 calls).
        q = shlex.quote
        n = end - start
        if n <= VIEW_HEAD + VIEW_TAIL:
            res = await run(
                self._env, f"tail -c +{start + 1} {q(session.log)} | head -c {n} | base64"
            )
            return _text(res.stdout)
        res = await run(
            self._env,
            f"tail -c +{start + 1} {q(session.log)} | head -c {VIEW_HEAD} | base64; "
            f"echo '#SPLIT#'; tail -c +{start + 1} {q(session.log)} "
            f"| head -c {n} | tail -c {VIEW_TAIL} | base64",
        )
        head, _, tail = res.stdout.partition("#SPLIT#")
        head, tail = _text(head), _text(tail)
        return (
            f"{head}\n…[{n - VIEW_HEAD - VIEW_TAIL} bytes omitted; full output is in {session.log} "
            f"at byte offsets {start}-{end}; use grep/sed/tail on it]…\n{tail}"
        )


    async def use(
        self,
        *,
        name: str = "main",
        input: str = "",
        mode: str = "command",
        wait_s: float = 30.0,
        interrupt: bool = False,
    ) -> str:
        if not _NAME.fullmatch(name):
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
        facts_replay.reset_terminal_pre(session, self._capture_state)
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
            except TerminalGone as gone:
                session = await self._restart(session)
                earlier = f"[{gone}; its previous command's output is lost. A fresh terminal {name} was started]"
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
        # An input that is only the interrupt key (54 mission calls sent "\x03" with interrupt=true) loses nothing.
        if interrupt and _HEX.sub(lambda m: chr(int(m.group(1), 16)), input).strip("\x03"):
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
            out = await self._collect(session, started, wait_s, first, settle=mode == "keys" and bool(input))
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


    async def _send(
        self, session: Session, input: str, mode: str, interrupt: bool, wait_s: float = 0.0
    ) -> tuple[int, re.Match | None, bool] | None:
        facts_replay.before_terminal(session, mode, interrupt, self._capture_state)
        if interrupt:
            if session.pty:
                await self._write(session, "\x03")
            else:  # no line discipline: a written \x03 is only a stray byte on the next line; signal the children
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
            body = _TRACE_BACK + body  # on line 1, so the shell's line numbers for the command are unchanged
            cmd_file = f"{session.root}/cmd_{session.seq}.sh"
            src, stages = f". {shlex.quote(cmd_file)}; {_CAPTURE}", ""
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
            inline = (cmd_file, body.encode())
            if len(inline[1]) > INLINE_BYTES:  # one argv string is capped at 128 KiB on Linux
                await put_bytes(self._env, inline[1], cmd_file)
                inline = None
            marker = f"{session.root}/done_{session.seq}"
            temporary_marker = f"{marker}.tmp"
            resolution_format, resolution_arg = facts_replay.terminal_receipt(self._command_names, self._capture_state)
            session.pending_resolution = None
            return await self._write(
                session,
                f"{_QUIET}{prompt}{src}; command printf '\\n__AETHER_DONE_%s_%s{'%s' if stages else ''}__ %s\\n{resolution_format}' "
                f'{session.seq} "$__aether_s" {stages} "$PWD"{resolution_arg} > {shlex.quote(temporary_marker)} '
                f"&& command mv -f {shlex.quote(temporary_marker)} {shlex.quote(marker)}; {_TRACE_BACK.strip().rstrip(';')}\n",
                cmd=inline,
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
        settle: bool = False,
    ) -> str:
        """``settle``: keystrokes were sent to a running program, so return once its output settles, as the tool
        promises (x0 2026-10-28: keys to a VM console behind a running command waited the full wait_s every call,
        334 s of one run). A running command whose last line asks for input returns early too."""
        name = session.name
        seq = session.pending or None
        size, mark, alive, last_size, stable_since = (
            session.cursor,
            None,
            True,
            -1,
            time.monotonic(),
        )
        delay, asking = 0.2, False
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
            if settle and now - started >= 0.5 and (
                (size != session.cursor and now - stable_since >= 2.0) or now - started >= KEYS_SILENT_S
            ):
                break
            if seq is not None and now - stable_since >= PROMPT_QUIET_S and size > session.cursor:
                tail = clean(await self._read(session, max(session.cursor, size - 300), size))
                if _ASKS.search(tail.rstrip("\n").rsplit("\n", 1)[-1]):
                    asking = True
                    break
            if now - started >= wait_s:
                break
            await asyncio.sleep(delay)
            delay = min(1.0, delay * 1.5)
        if mark is not None:
            session.pending = 0
            facts_replay.record_terminal_receipt(session, mark, self._capture_state)
            session.command_resolution = session.pending_resolution
            session.resolution_receipt_seq = int(mark.group(1)) if session.command_resolution is not None else None
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
            cwd = (session.last_observed_cwd if session.last_observed_cwd is not None
                   else "unknown (ambiguous receipt)") if self._command_names else mark.group(4).strip()
            status = f"[exit {mark.group(2)}{piped} · {elapsed:.1f}s · terminal {name} · cwd {cwd}]"
        elif seq is not None:
            quiet = time.monotonic() - session.grew_at
            status = (
                "[its last line looks like a prompt waiting for input; answer it with mode=\"keys\" (end with \\n) "
                "or interrupt it]\n" if asking else ""
            ) + (
                f"[still running after {elapsed:.0f}s · "
                + (f"no new output for {quiet:.0f}s · " if quiet >= 10 else "")
                + f"terminal {name}; call again with empty input to keep waiting, use interrupt=true to "
                f"stop it, or work in another terminal]"
            )
            procs = await describe_processes(self._env, session.pid)
            if procs:
                status += "\n[its processes: " + "; ".join(procs) + "]"
        else:
            status = f"[{elapsed:.1f}s · terminal {name}]"
        return (text + "\n" if text else "(no new output)\n") + status
