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
- ``pending`` holds the last command line written to the shell; its sequence number is parsed from the completion
  receipt it carries. A ``claim_<seq>`` newer than ``pending`` is the latest command.
- The command's state is read from its operation records (:mod:`operations`): the start token, ``done_<seq>`` and
  ``delivered_<seq>``. A command with no start token is revoked during adoption, so it can never run later.

The adopted state of the latest command is one of: ``delivered`` (its result was already shown), ``completed``
(receipt present, not yet shown), ``running`` (the shell took it and is alive), ``revoked`` (the shell never took it;
it can no longer run) or ``lost`` (the shell took it and died without a receipt: its effect is unknown). Adoption
never resends, retries or stops anything.
"""

from __future__ import annotations

import re
import shlex
import time

from . import operations
from .env import alive_test, process_identities, run
from .terminal_session import Session

_SEQ = re.compile(r"__AETHER_DONE_%s_%s[^']*' (\d+) \"\$__aether_s\"")
_BIRTH = "if [ -r /proc/{pid}/stat ]; then sed 's/.*) //' /proc/{pid}/stat | awk '{{print $20}}'; " \
         "else ps -p {pid} -o lstart= | awk '{{$1=$1;print}}'; fi"


def with_offset_record(steps: list[str], root: str, seq: int) -> list[str]:
    """Record, under ``claim_<seq>`` and before the line is offered to the shell, the log offset where the command's
    output begins, so a later controller delivers its output from there."""
    q = shlex.quote
    offset = q(f"{root}/claim_{seq}/offset")
    return [*steps[:-1], f"__aether_at=$(wc -c < {q(root + '/out.log')}) || exit 6; "
            f"printf '%s\\n' \"$__aether_at\" > {offset}.tmp && mv -f {offset}.tmp {offset} || exit 8; {steps[-1]}"]


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
        "echo __SEP__; cat pending 2>/dev/null; echo __SEP__; wc -c < out.log; "
        "echo __SEP__; printf '%s\\n' claim_*",
    )
    parts = read.stdout.split("__SEP__\n")
    if read.code != 0 or len(parts) != 6 or not parts[0].strip().isdigit():
        raise RuntimeError(f"terminal {name}: its control directory {root} is incomplete; ownership is unverified")
    pid, birth, mode = int(parts[0]), parts[1].strip(), parts[2].split()
    pending_text, size, claims = parts[3:]
    if len(mode) != 2 or mode[0] not in ("pty", "nopty") or mode[1] not in ("bash", "sh"):
        raise RuntimeError(f"terminal {name}: no launch mode record in {root}; ownership is unverified")
    now = await run(terminals._env, f"{alive_test(pid)} && {{ {_BIRTH.format(pid=pid)}; }} || echo __DEAD__")
    alive = now.code == 0 and "__DEAD__" not in now.stdout
    if alive and now.stdout.strip() != birth:
        raise RuntimeError(f"terminal {name}: process {pid} is not the shell recorded in {root}; not adopted")
    latest_claim = max((int(line[6:]) for line in claims.splitlines() if line.startswith("claim_")
                        and line[6:].isascii() and line[6:].isdigit()), default=0)
    seq = max(parse_seq(pending_text) or 0, latest_claim) or None
    token = done = offset = None
    delivered = None
    if seq is not None:
        records = await run(
            terminals._env,
            f"{operations.resolve_script(root, seq, revoke=True)}; echo __SEP__; cat {q(f'{root}/claim_{seq}/offset')} 2>/dev/null; true",
        )
        found, _, offset_text = records.stdout.rpartition("__SEP__\n")
        parsed = operations.parse(found)
        if records.code != 0 or parsed is None:
            raise RuntimeError(f"terminal {name}: command #{seq} records could not be read")
        token, done, delivered = parsed
        offset = offset_text.strip()
    state, exit_status = operations.classify(seq, token, done, operations.seen(delivered, terminals.conversation), alive)
    session = Session(name, root, pid, mode[0] == "pty", bash=mode[1] == "bash", grew_at=time.monotonic())
    session.seq = seq or 0
    unseen = state in ("running", "completed")
    session.cursor = int(offset) if unseen and offset and offset.isdigit() else int(size.strip() or 0)
    session.last_size = session.cursor
    session.prompt_offset = session.cursor
    if unseen:
        # The model has not seen this command's outcome. The normal observation path reads the receipt (now or
        # later) and delivers the output from the recorded offset exactly once; new input waits until it has.
        session.pending, session.unseen = seq, True
    session.dispatch_unconfirmed = state in ("lost", "unresolved")
    session.ready = alive
    if alive:
        session.identity = await process_identities(terminals._env, [pid])
    terminals._generations[name] = generation + 1
    return session, {"name": name, "root": root, "pid": pid, "sequence": seq, "state": state, "exit": exit_status,
                     "shell_alive": alive, "source": "sandbox terminal records"}


async def resolve(terminals, session: Session) -> str:
    """Decide a command whose dispatch reply was lost, from its operation records: the shell took it (then it is
    observed like any running command, as unseen), or it is cancelled now and can never run. Returns the model-facing
    note when it was cancelled. Lost or unreadable records leave it unconfirmed."""
    seq = session.pending or session.seq
    res = await run(terminals._env, f"{{ {alive_test(session.pid)} && echo __ALIVE__ || echo __DEAD__; }}; "
                                    f"{operations.resolve_script(session.root, seq, revoke=True)}")
    alive, _, records = res.stdout.partition("\n")
    parsed = operations.parse(records)
    if res.code != 0 or parsed is None:
        return ""
    token, done, tag = parsed
    state, _ = operations.classify(seq, token, done, operations.seen(tag, terminals.conversation), alive == "__ALIVE__")
    if state == "revoked":
        session.pending, session.dispatch_unconfirmed = 0, False
        return (f"[command #{seq} in terminal {session.name} was never started: its dispatch failed before the "
                "shell took it, and it is now cancelled, so it cannot run later. Nothing from it ran; send it "
                "again if it is still needed.]")
    if state == "delivered":  # another controller already showed its result
        session.pending, session.dispatch_unconfirmed = 0, False
    elif state in ("running", "completed"):
        session.pending, session.dispatch_unconfirmed, session.unseen = seq, False, True
    return ""


def describe(record: dict) -> str:
    """One line for the model: what the earlier controller left, as recorded in the sandbox."""
    name, seq, state = record["name"], record["sequence"], record["state"]
    head = f"[terminal {name} was adopted from an earlier controller of this task"
    if state == "idle":
        return head + "; it had no command recorded]"
    if state == "delivered":
        return head + f"; its command #{seq} completed with exit {record['exit']}, already reported]"
    if state == "completed":
        return head + f"; its command #{seq} completed with exit {record['exit']} (the shell's own receipt)]"
    if state == "running":
        return head + f"; its command #{seq} is still running. Wait on it or interrupt it before reusing {name}]"
    if state == "revoked":
        return head + (f"; command #{seq} was never started: the shell had not taken it, and it is now cancelled, "
                       "so it cannot run later. Nothing from it ran; send it again if it is still needed]")
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
