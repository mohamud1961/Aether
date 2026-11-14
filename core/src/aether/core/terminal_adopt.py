"""Adopt a terminal left running by an earlier controller of the same task sandbox.

Used only when terminals preserve existing control directories (``CoreConfig.terminal_events``). A controller can
die after a command was written to a shell, before its reply reached the model. The shell and its command keep
running in the sandbox. Without adoption the next controller saw no session, reported "no outstanding terminal
command", and refused the name because its ownership was unverified, so the dispatched command's identity and
eventual exit were lost (restart witness, 13 Nov).

Everything here comes from the sandbox, never from controller memory:

- ``pid`` and ``birth`` are written by the shell wrapper at launch. Adoption requires the process to be alive and its
  current start time to equal ``birth``, so a reused PID is never adopted.
- ``mode`` (pty/bash) is written at launch when existing directories are preserved. Without it, adoption is refused.
- ``pending`` holds the last command line written to the shell. Its sequence number is parsed from the completion
  receipt it carries. ``sent_<seq>`` is written in the same container exec after the line reached the shell's input,
  and holds the log offset where that command's output starts.
- ``done_<seq>`` is the shell's own completion receipt.

The adopted state of the latest dispatched command is one of: ``completed`` (receipt present, with its exit),
``running`` (delivered, no receipt, shell alive), ``dispatch_unconfirmed`` (written but never confirmed delivered),
or ``lost`` (shell gone, no valid receipt). Adoption never resends, retries or stops anything.
"""

from __future__ import annotations

import re
import shlex
import time

from .env import alive_test, process_identities, run
from .terminal_session import Session

_SEQ = re.compile(r"__AETHER_DONE_%s_%s[^']*' (\d+) \"\$__aether_s\"")
_DONE = re.compile(r"__AETHER_DONE_(\d+)_(\d+)")
_BIRTH = "if [ -r /proc/{pid}/stat ]; then sed 's/.*) //' /proc/{pid}/stat | awk '{{print $20}}'; " \
         "else ps -p {pid} -o lstart= | awk '{{$1=$1;print}}'; fi"


def with_delivery_record(steps: list[str], root: str, seq: int) -> list[str]:
    """Add the delivery record to a command write: ``sent_<seq>`` is written in the same container exec, only after
    the line reached the shell's input, and holds the log offset taken before it, where the output begins."""
    q = shlex.quote
    sent = q(f"{root}/sent_{seq}")
    return [*steps[:-1], f"__aether_at=$(wc -c < {q(root + '/out.log')}) || exit 6; {steps[-1]}",
            f"printf '%s\\n' \"$__aether_at\" > {sent}.tmp && mv -f {sent}.tmp {sent} || exit 8"]


def latest_root(control_dir: str, name: str, listing: list[str]) -> tuple[str, int] | None:
    """The newest generation directory for ``name``: ``name``, then ``name.1``, ``name.2`` ..."""
    best = None
    for entry in listing:
        if entry == name:
            generation = 0
        elif entry.startswith(name + ".") and entry[len(name) + 1:].isdigit():
            generation = int(entry[len(name) + 1:])
        else:
            continue
        if best is None or generation > best[1]:
            best = (entry, generation)
    return None if best is None else (f"{control_dir}/term/{best[0]}", best[1])


def parse_seq(pending_text: str) -> int | None:
    match = _SEQ.search(pending_text)
    return int(match.group(1)) if match else None


def state_of(seq: int | None, sent: str | None, done: str | None, alive: bool) -> tuple[str, int | None]:
    """Classify the latest dispatched command from sandbox records alone. Returns (state, exit)."""
    if seq is None:
        return "idle", None
    if done is not None:
        mark = _DONE.search(done)
        if mark is None or int(mark.group(1)) != seq:
            return "lost", None
        return "completed", int(mark.group(2))
    if not alive:
        return "lost", None
    return ("dispatch_unconfirmed", None) if sent is None else ("running", None)


async def adopt(terminals, name: str) -> tuple[Session, dict] | None:
    """Rebuild ``name``'s session from its control directory. None when there is nothing to adopt."""
    q = shlex.quote
    listing = await run(terminals._env, f"ls -1 {q(terminals._control_dir + '/term')} 2>/dev/null; true")
    found = latest_root(terminals._control_dir, name, listing.stdout.split())
    if found is None:
        return None
    root, generation = found
    read = await run(
        terminals._env,
        f"cd {q(root)} || exit 4; cat pid; echo __SEP__; cat birth; echo __SEP__; cat mode 2>/dev/null; "
        f"echo __SEP__; cat pending 2>/dev/null; echo __SEP__; wc -c < out.log",
    )
    parts = read.stdout.split("__SEP__\n")
    if read.code != 0 or len(parts) != 5 or not parts[0].strip().isdigit():
        raise RuntimeError(f"terminal {name}: its control directory {root} is incomplete; ownership is unverified")
    pid, birth, mode, pending_text, size = int(parts[0]), parts[1].strip(), parts[2].split(), parts[3], parts[4]
    if len(mode) != 2 or mode[0] not in ("pty", "nopty") or mode[1] not in ("bash", "sh"):
        raise RuntimeError(f"terminal {name}: no launch mode record in {root}; ownership is unverified")
    now = await run(terminals._env, f"{alive_test(pid)} && {{ {_BIRTH.format(pid=pid)}; }} || echo __DEAD__")
    alive = now.code == 0 and "__DEAD__" not in now.stdout
    if alive and now.stdout.strip() != birth:
        raise RuntimeError(f"terminal {name}: process {pid} is not the shell recorded in {root}; not adopted")
    seq = parse_seq(pending_text)
    sent = done = None
    if seq is not None:
        records = await run(
            terminals._env,
            f"cd {q(root)} && cat sent_{seq} 2>/dev/null; echo __SEP__; cat done_{seq} 2>/dev/null; true",
        )
        sent_text, _, done_text = records.stdout.partition("__SEP__\n")
        sent = sent_text.strip() or None
        done = done_text.strip() or None
    state, exit_status = state_of(seq, sent, done, alive)
    session = Session(name, root, pid, mode[0] == "pty", bash=mode[1] == "bash", grew_at=time.monotonic())
    session.seq = seq or 0
    session.cursor = int(sent) if sent and sent.isdigit() else int(size.strip() or 0)
    session.last_size = session.cursor
    if state in ("running", "completed") or (state == "dispatch_unconfirmed" and alive):
        # The normal observation path reads the receipt (now or later) and delivers the output from the recorded
        # offset exactly once, as it would have for the original controller.
        session.pending = seq
    session.dispatch_unconfirmed = state == "dispatch_unconfirmed" or state == "lost"
    session.ready = alive
    if alive:
        session.identity = await process_identities(terminals._env, [pid])
    terminals._generations[name] = generation + 1
    return session, {"name": name, "root": root, "pid": pid, "sequence": seq, "state": state, "exit": exit_status,
                     "shell_alive": alive, "source": "sandbox terminal records"}


def describe(record: dict) -> str:
    """One line for the model: what the earlier controller left, as recorded in the sandbox."""
    name, seq, state = record["name"], record["sequence"], record["state"]
    head = f"[terminal {name} was adopted from an earlier controller of this task"
    if state == "idle":
        return head + "; it had no command recorded]"
    if state == "completed":
        return head + f"; its command #{seq} completed with exit {record['exit']} (the shell's own receipt)]"
    if state == "running":
        return head + f"; its command #{seq} is still running. Wait on it or interrupt it before reusing {name}]"
    if state == "dispatch_unconfirmed":
        return head + (f"; command #{seq} was written but never confirmed delivered, and has no completion "
                       "receipt. Check its intended effect before running it again]")
    return head + (f"; its shell is gone and command #{seq} left no completion receipt. Its effect is unknown; "
                   "check the result before running it again]")


async def ensure(terminals, name: str) -> str:
    """Register an adoptable session for ``name`` (caller holds the name lock). Returns a note for the model."""
    if not terminals._preserve_existing or name in terminals._sessions:
        return ""
    adopted = await adopt(terminals, name)
    if adopted is None:
        return ""
    session, record = adopted
    terminals._sessions[name] = session
    terminals.adoptions.append(record)
    return describe(record) + "\n"
