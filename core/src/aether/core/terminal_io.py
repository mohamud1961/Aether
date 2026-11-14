"""Low-level input and output of a named terminal: one exec per delivery, completion probes and log reads.

Split from terminal.py (module cap). ``Terminals`` inherits these; they use its environment, preserve mode and
receipt settings. Each method is one container exec, so every fault point is a whole exec (see the fault sweeps).
"""

from __future__ import annotations

import base64
import re
import shlex

from . import facts_replay, operations, terminal_adopt
from .env import alive_test, run
from .terminal_session import Session, TerminalGone, clean
from .transfer import atomic_write

VIEW_HEAD = 3_000
VIEW_TAIL = 8_000
# seq, exit, optional per-stage exits of the command's last pipeline (bash only, joined by "."), cwd
_MARK = re.compile(r"__AETHER_DONE_(\d+)_(\d+)(?:_([\d.]+))?__ ?([^\n]*)\n?")
_REVOKED = "__AETHER_REVOKED__"


class _TerminalSequenceClaimed(RuntimeError):
    """Another controller reserved this command sequence in the sandbox."""


class TerminalIO:
    """Delivery, probing and reading for ``Terminals`` (attributes set by its constructor)."""

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
        tracks_dispatch = self._preserve_existing and wait is not None and wait[0] != 0
        # A done_<seq> already on disk (stale, or planted before the send) must not complete this command.
        clear = [f"rm -f {q(f'{session.root}/done_{wait[0]}')} || exit 7"] if wait is not None and wait[0] else []
        # Preserve the last command's dispatch record when the user types into
        # it or interrupts it. The input itself has no command sequence.
        input_name = "input" if self._preserve_existing and wait is None else "pending"
        source = q(f"{session.root}/{input_name}")
        steps = clear + ([atomic_write(*cmd, 4)] if cmd else []) + [
            atomic_write(f"{session.root}/{input_name}", text.encode(), 5),
            f"{alive_test(session.pid)} && [ -p {q(session.fifo)} ] || {{ echo dead; exit 3; }}",
            f"cat {source} > {q(session.fifo)} || exit 6",
        ]
        if tracks_dispatch:
            steps = terminal_adopt.with_offset_record(steps, session.root, wait[0])
            claim = q(f"{session.root}/claim_{wait[0]}")
            # The in-memory lock does not coordinate resumed controllers. Take
            # the sequence before clearing its receipt or touching the FIFO.
            steps[:0] = [f"[ -p {q(session.fifo)} ] || exit 12",
                         f"mkdir {claim} 2>/dev/null || {{ if [ -d {claim} ]; then exit 10; fi; exit 11; }}"]
        if input_name == "input":
            steps.append(f"rm -f {source}")
        if wait is not None:
            seq, ticks = wait[0], int(max(0.0, min(wait[1], 3.0)) / 0.1)
            # The receipt is looked for before the size is taken, as in _poll.
            steps.append(
                f"i=0; m=''; while [ -r {log} ]; do m=$({self._probe(session, seq)});"
                f' [ -n "$m" ] && break; [ $i -ge {ticks} ] && break; {alive_test(session.pid)} || break; '
                f"sleep 0.1; i=$((i+1)); done; printf '%s\\n' \"$m\"; "
                f"{alive_test(session.pid)} && echo __ALIVE__ || echo __DEAD__; echo __SIZE__; wc -c < {log} 2>/dev/null; true"
            )
        if tracks_dispatch:
            session.dispatch_unconfirmed = True
        res = await run(self._env, "; ".join(steps), timeout_s=20)
        if tracks_dispatch and res.code == 10:
            raise _TerminalSequenceClaimed(session.name)
        if (tracks_dispatch and res.code == 12) or (res.code == 3 and "dead" in res.stdout):
            if tracks_dispatch:
                session.dispatch_unconfirmed = False  # failure preceded the FIFO write
            raise TerminalGone(f"terminal {session.name} is not running")
        if res.code != 0:
            raise RuntimeError(
                f"could not send input to terminal {session.name}: {(res.stderr or res.stdout).strip()[:200]}"
            )
        if tracks_dispatch:
            session.dispatch_unconfirmed = False
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
        done = f"cat {q(session.root + '/done_' + str(seq))} 2>/dev/null"
        if not self._preserve_existing:
            return done
        # Another controller may have cancelled this command before the shell took it (operations.py).
        token = q(f"{session.root}/start_{seq}")
        return f'{{ {done} || {{ [ "$(readlink {token} 2>/dev/null)" = {operations.REVOKED} ] && echo {_REVOKED}; }}; }}'

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
        if mark is not None and int(mark.group(1)) != seq:
            mark = None
        if mark is None and seq and _REVOKED in cleaned:
            session.revoked = seq
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

    async def _read(self, session: Session, start: int, end: int, delivered: int = 0) -> str:
        # The bytes travel as base64 and are decoded here: the environment decodes command output as strict UTF-8, so
        # one byte that is not (binary output, or a character cut by head -c) failed the read, and as the cursor did
        # not move every later call reread it and failed too (path-tracing baseline: 21 calls).
        q = shlex.quote
        n = end - start
        # The continued conversation will acknowledge the collection token.
        record = ""
        if delivered and self._preserve_existing:
            tag = self.delivery_tag()
            record = f" && {operations.mark_delivered(session.root, delivered, tag)}"
        if n < 0:
            raise TerminalGone(f"the log of terminal {session.name} was truncated")
        log = q(session.log)
        exists = f"[ -f {log} ] && [ ! -L {log} ] || exit 13; "
        def decode(encoded: str, expected: int) -> str:
            raw = base64.b64decode("".join(encoded.split()), validate=True)
            if len(raw) != expected:
                raise RuntimeError(f"terminal {session.name} output was incomplete")
            return raw.decode("utf-8", "replace")

        if n <= VIEW_HEAD + VIEW_TAIL:
            res = await run(
                self._env, f"{exists}tail -c +{start + 1} {log} | head -c {n} | base64{record}"
            )
            if res.code != 0:
                raise RuntimeError(f"terminal {session.name} output or delivery record could not be read")
            return decode(res.stdout, n)
        res = await run(
            self._env,
            f"{exists}tail -c +{start + 1} {log} | head -c {VIEW_HEAD} | base64; "
            f"echo '#SPLIT#'; tail -c +{start + 1} {log} "
            f"| head -c {n} | tail -c {VIEW_TAIL} | base64{record}",
        )
        head, separator, tail = res.stdout.partition("#SPLIT#")
        if res.code != 0 or not separator:
            raise RuntimeError(f"terminal {session.name} output or delivery record could not be read")
        head, tail = decode(head, VIEW_HEAD), decode(tail, VIEW_TAIL)
        return (
            f"{head}\n…[{n - VIEW_HEAD - VIEW_TAIL} bytes omitted; full output is in {session.log} "
            f"at byte offsets {start}-{end}; use grep/sed/tail on it]…\n{tail}"
        )
