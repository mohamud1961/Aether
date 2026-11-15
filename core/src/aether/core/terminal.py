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
import uuid

from .env import CONTROL_DIR, Environment, run
from . import facts_probe, facts_replay, operations, terminal_adopt
from .terminal_procs import describe_processes
from .terminal_session import (  # noqa: F401 (some names re-exported)
    MAX_TERMINALS, Session, TerminalGone, TerminalLifecycle, _ASKS, _text, clean,
)
from .tool_validate import unsendable_text
from .transfer import INLINE_BYTES, put_bytes

from .terminal_io import TerminalIO, _TerminalSequenceClaimed

# One tool call blocks the loop at most this long, so scheduled reviews and the elapsed-time readout reach the
# model while long jobs run (D1 extract-moves: one 902 s wait skipped a progress review and left 20 s at the end).
MAX_WAIT_S = 300.0
KEYS_SILENT_S = 10.0  # keys with no output at all return after this; empty input still waits the full wait_s
PROMPT_QUIET_S = 5.0  # a running command quiet this long with a prompt as its last line returns early
_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_HEX = re.compile(r"\\x([0-9a-fA-F]{2})")
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


class Terminals(TerminalIO, TerminalLifecycle):
    def __init__(
        self, env: Environment, workdir: str, clock, control_dir: str = CONTROL_DIR,
        command_names: tuple[str, ...] = (), capture_state: bool = False, preserve_existing: bool = False,
        deliver_results: bool = False, fast_process_scan: bool = False,
    ) -> None:
        facts_probe.terminal_scope(command_names)
        self._env = env
        self._command_names = command_names
        self._capture_state = capture_state
        self._preserve_existing = preserve_existing
        self._deliver_results = deliver_results
        self._fast_process_scan = fast_process_scan
        self._control_dir = control_dir
        self._workdir = workdir
        self._clock = clock  # callable -> remaining seconds
        self.cleanup_uncertainties: list[str] = []
        self.cleanup_receipt: dict = {}
        self._sessions: dict[str, Session] = {}
        self._name_locks: dict[str, asyncio.Lock] = {}
        self._generations: dict[str, int] = {}
        self.adoptions: list[dict] = []  # terminals rebuilt from an earlier controller's records (terminal_adopt)
        # Local result tokens acknowledged by the continued conversation.
        self.delivery_tag = lambda: ""
        self.conversation: set[str] | None = None
        self._launching: set[str] = (
            set()
        )  # PID files resolve a lost launch reply during cleanup
        self.left_running: list[
            str
        ] = []  # close(keep=True): processes left alive at run end

    @property
    def names(self) -> list[str]:
        return sorted(self._sessions)

    def pending_names(self) -> list[str]:
        return sorted(name for name, session in self._sessions.items() if session.pending)

    async def wait_events(self, names: list[str], *, mode: str, wait_s: float, quiet_s: float | None = None) -> dict:
        """Observe an explicitly selected set of existing commands."""
        from .terminal_wait import wait

        return await wait(self, names, mode=mode, wait_s=wait_s, quiet_s=quiet_s)

    def observed_session(self, name: str) -> dict | None:
        """Return only session facts established by its last terminal observation."""
        return facts_probe.terminal_observation(self._sessions.get(name), self._generations.get(name))


    async def use(
        self, *, name: str = "main", input: str = "", mode: str = "command",
        wait_s: float = 30.0, interrupt: bool = False,
    ) -> str:
        if not _NAME.fullmatch(name):
            raise ValueError("terminal name must be 1-32 chars of letters, digits, _ or -")
        if reason := unsendable_text(input, shell=mode == "command"):
            raise ValueError(f"terminal {name}: input not sent, nothing ran: {reason}")
        async with self._name_locks.setdefault(name, asyncio.Lock()):
            return await self._use(name=name, input=input, mode=mode, wait_s=wait_s, interrupt=interrupt)

    async def _use(
        self,
        *,
        name: str = "main",
        input: str = "",
        mode: str = "command",
        wait_s: float = 30.0,
        interrupt: bool = False,
    ) -> str:
        if mode not in ("command", "keys"):
            raise ValueError("mode must be 'command' or 'keys'")
        note = await terminal_adopt.ensure(self, name)
        session = self._sessions.get(name)
        if note and self.adoptions[-1]["state"] == "revoked" and (input or interrupt):
            # Whatever the model sends next may assume the cancelled command ran.
            return note + "[input not sent: an earlier command was cancelled unrun; decide with that known.]"
        if session is not None and session.dispatch_unconfirmed and self._preserve_existing:
            cancelled = await terminal_adopt.resolve(self, session)
            if cancelled:
                return note + cancelled
        if session is not None and session.unseen and session.pending:
            # The model has not been shown this command (adopted, or its dispatch reply was lost). Show it before
            # any new input: the model may be re-sending the same command because it does not know it ran.
            observe = 0.0 if input or interrupt else max(0.0, min(float(wait_s), MAX_WAIT_S, self._clock() - 5))
            observed = await self._collect(session, time.monotonic(), observe)
            held = ("\n[input not sent: this command's outcome had not been shown to you yet; "
                    "use it before sending new input.]") if input or interrupt else ""
            return note + observed + held
        if session is not None and not session.ready:
            if session.dispatch_unconfirmed and (input or interrupt):
                return note + (f"[input not sent: terminal {name} is not running and its earlier command's effect is unknown. "
                               "An empty observation starts a fresh shell. Check the earlier effect before resending.]")
            session = await self._restart(session)
            note += f"[terminal {name} startup was incomplete; a fresh terminal was started]\n"
            if mode == "keys":
                return (
                    note
                    + session.cleanup_warning
                    + "[Your keystrokes were not sent; start the intended program again before sending keys.]"
                )
        if session is None:
            session = await self._start(name)
            note += (
                f"[terminal {name} started{'' if session.pty else ' without a pty'}]\n"
            )
        facts_replay.reset_terminal_pre(session, self._capture_state)
        if input and mode == "command" and not input.strip("\x03 \n"):
            # Ctrl-C as a command is an interrupt (P2 10-22: "\x03" refused as "input not sent" again and again)
            input, interrupt = "", True
            note += "[Ctrl-C in command input was sent as interrupt=true]\n"
        if session.dispatch_unconfirmed and input and mode == "keys" and not interrupt:
            return note + f"[input not sent: terminal {name} has an unconfirmed dispatch. Observe its exit or explicitly interrupt it first.]"
        if input and mode == "command" and not interrupt and session.pending:
            # Look at the running command first. Writing the new one into the busy shell queued it unseen and
            # moved `pending` to it, so "still running" then described a command that had not started
            # (overfull-hbox e1: the model's kill commands waited ~100 s behind the solver).
            try:
                earlier = await self._collect(session, time.monotonic(), 0.0)
            except TerminalGone as gone:
                if session.dispatch_unconfirmed:
                    return note + f"[input not sent: terminal {name} disappeared with an unconfirmed dispatch. Check its effect and use a new terminal.]"
                session = await self._restart(session)
                earlier = f"[{gone}; its previous command's output is lost. A fresh terminal {name} was started]"
            if session.pending and name in self._sessions:
                reason = ("has an unconfirmed dispatch" if session.dispatch_unconfirmed
                          else "is still running its previous command")
                return (
                    note
                    + (
                        f"[input not sent: terminal {name} {reason}. To run it now, call "
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
        except _TerminalSequenceClaimed:
            self._sessions.pop(name, None)
            return note + f"[input not sent: terminal {name} has a newer command claim. Observe it before sending input.]"
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
        if input or interrupt:
            session.prompt_offset = max(session.cursor, session.last_size)
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
            payload = body.encode()
            # A large transfer precedes the claim. Give it a private name so
            # it cannot replace the script belonging to a claimed sequence.
            staging = f"-{uuid.uuid4().hex}" if self._preserve_existing and len(payload) > INLINE_BYTES else ""
            cmd_file = f"{session.root}/cmd_{session.seq}{staging}.sh"
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
            inline = (cmd_file, payload)
            if len(payload) > INLINE_BYTES:  # one argv string is capped at 128 KiB on Linux
                await put_bytes(self._env, payload, cmd_file)
                inline = None
            marker = f"{session.root}/done_{session.seq}"
            temporary_marker = f"{marker}.tmp"
            resolution_format, resolution_arg = facts_replay.terminal_receipt(self._command_names, self._capture_state)
            session.pending_resolution = None
            run_and_receipt = (
                f"{prompt}{src}; command printf '\\n__AETHER_DONE_%s_%s{'%s' if stages else ''}__ %s\\n{resolution_format}' "
                f'{session.seq} "$__aether_s" {stages} "$PWD"{resolution_arg} > {shlex.quote(temporary_marker)} '
                f"&& command mv -f {shlex.quote(temporary_marker)} {shlex.quote(marker)}"
            )
            if self._preserve_existing:
                # The shell runs the command only if it takes the start token first (operations.py), so a dispatch
                # whose reply was lost can be cancelled for certain instead of staying undecided.
                run_and_receipt = f"if {operations.start_gate(session.root, session.seq)}; then {run_and_receipt}; fi"
            return await self._write(
                session,
                f"{_QUIET}{run_and_receipt}; {_TRACE_BACK.strip().rstrip(';')}\n",
                cmd=inline,
                wait=(session.seq, wait_s),
            )
        elif input:
            keys = _HEX.sub(lambda m: chr(int(m.group(1), 16)), input)
            # Raw Ctrl-C might be swallowed by a foreground program. As with
            # interrupt=true, retain pending until the original marker proves
            # the shell actually resumed execution.
            await self._write(session, keys)

    @staticmethod
    def _unobserved(session: Session, seq: int | None, exc: Exception, mark: re.Match | None) -> None:
        """A poll or read of pending command ``seq`` failed: the next call shows it before any new input (T2, 15 Nov:
        told only that a read failed, a model re-sent the command and it ran twice)."""
        if seq is None:
            return
        session.unseen = True
        state = f"finished (exit {mark.group(2)})" if mark is not None else "was still running when last observed"
        raise RuntimeError(f"{exc}. Command #{seq} {state}; its outcome was not shown and comes with the next call to "
                           f"terminal {session.name}, before any new input is sent.") from None

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
                try:
                    size, mark, alive = await self._poll(session, seq)
                except RuntimeError as exc:
                    if not isinstance(exc, TerminalGone):
                        self._unobserved(session, seq, exc, None)
                    raise
            now = time.monotonic()
            if size != session.last_size:
                session.last_size, session.grew_at = size, now
            if mark is not None or not alive or (seq is not None and session.revoked == seq):
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
        try:
            text = clean(await self._read(session, session.cursor, size, int(mark.group(1)) if mark is not None else 0))
        except RuntimeError as exc:
            if not isinstance(exc, TerminalGone):
                self._unobserved(session, seq, exc, mark)
            raise
        session.unseen = False
        revoked = mark is None and seq is not None and session.revoked == seq
        if revoked:
            session.pending = 0
            session.dispatch_unconfirmed = False
        if mark is not None:
            session.pending = 0
            session.dispatch_unconfirmed = False
            session.exit_receipt = (int(mark.group(1)), int(mark.group(2)))
            facts_replay.record_terminal_receipt(session, mark, self._capture_state)
            session.command_resolution = session.pending_resolution
            session.resolution_receipt_seq = int(mark.group(1)) if session.command_resolution is not None else None
        session.cursor = size
        # Runtime completion receipts are out-of-band. Keep user/program
        # stdout verbatim even if it resembles our completion protocol.
        text = text.strip("\n")
        elapsed = time.monotonic() - started
        if not alive:
            if self._preserve_existing and mark is None and not revoked and seq is not None:
                # Keep the lost generation until the model has a chance to
                # reconcile the effect and explicitly observes the terminal.
                session.ready, session.pending, session.dispatch_unconfirmed = False, 0, True
                session.last_observed_cwd, session.cwd_receipt_seq = None, None
            else:
                self._sessions.pop(name, None)
        if mark is not None:
            stages = (mark.group(3) or "").split(".")
            piped = (
                f" · last pipeline's stage exits {' | '.join(stages)}"
                if set(stages) - {"0"} and len(stages) > 1
                else ""
            )
            cwd = (session.last_observed_cwd if session.last_observed_cwd is not None
                   else "unknown (ambiguous receipt)") if self._command_names else mark.group(4).strip()
            status = f"[exit {mark.group(2)}{piped} · {elapsed:.1f}s · terminal {name} · cwd {cwd}]"
            if not alive:
                status += f"\n[terminal {name} exited; it restarts on next use]"
        elif revoked:
            status = (f"[command #{seq} in terminal {name} was never started: another controller cancelled it before "
                      "the shell took it. Nothing from it ran; send it again if it is still needed.]")
        elif not alive:
            status = f"[terminal {name} exited; it restarts on next use]"
            if self._preserve_existing and seq is not None:
                status = (f"[terminal {name} exited. Command #{seq} left no completion receipt; its effect is unknown. "
                          "Use an empty observation to start a fresh shell after checking the effect.]")
        elif session.dispatch_unconfirmed:
            status = (f"[terminal {name}: dispatch of command #{seq} is unconfirmed and no exit has been observed. "
                      "Wait, explicitly interrupt, or do unrelated work in another terminal.]")
        elif seq is not None:
            quiet = time.monotonic() - session.grew_at
            guidance = "call again with empty input to keep waiting, use interrupt=true to stop it, or work in another terminal"
            if self._deliver_results:
                guidance = "Core will deliver the result after exit with a subsequent tool result"
                if session.delivery_announced != seq:
                    session.delivery_announced = seq
                    guidance += "; work elsewhere if you can, or wait here if you need the result now"
                else:
                    guidance = "Core is tracking this command"
            status = (
                "[its last line looks like a prompt waiting for input; answer it with mode=\"keys\" (end with \\n) "
                "or interrupt it]\n" if asking else ""
            ) + (
                f"[still running after {elapsed:.0f}s · "
                + (f"no new output for {quiet:.0f}s · " if quiet >= 10 else "")
                + f"terminal {name}; {guidance}]"
            )
            procs = await describe_processes(self._env, session.pid, fast=self._fast_process_scan)
            if procs:
                status += "\n[its processes: " + "; ".join(procs) + "]"
        else:
            status = f"[{elapsed:.1f}s · terminal {name}]"
        return (text + "\n" if text else "(no new output)\n") + status
