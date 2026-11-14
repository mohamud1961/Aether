"""A restarted controller adopts the Python REPL server an earlier controller left running (operation tracking on).

Before, a new controller wiped the REPL directory and launched a fresh interpreter, so every variable the model had
built was lost, and a cell the earlier controller had submitted could still run in the old server unseen. Now the
launch records the server's pid and process identity (``server.rec``). A new controller that finds that same process
alive adopts it: variables survive, cell numbers continue from the sandbox, and the last cell is decided from its
records (operations.py):

- a cell file with no start token yet: the server will run it (dispatched), so it is pending and unseen;
- a submission that never became a cell file (only ``<n>.tmp``): its token is taken as ``revoked``, so it never runs;
- a token ``run`` and no ``<n>.done``: running, unseen; with ``<n>.done``: completed, shown once unless its delivery
  is in the conversation this controller continues (``operations.seen``).

A different or dead process is not adopted: the caller launches a fresh server as before.
"""

from __future__ import annotations

import json
import re
import shlex

from . import operations
from .env import alive_test, process_identities, run

RECORD = "server.rec"


def record_script(base: str, pid: int, identity: dict, python: str) -> str:
    q = shlex.quote
    body = json.dumps({"pid": pid, "identity": identity, "python": python})
    return f"printf %s {q(body)} > {q(base + '/' + RECORD + '.tmp')} && mv {q(base + '/' + RECORD + '.tmp')} {q(base + '/' + RECORD)}"


async def adopt(repl) -> str | None:
    """Adopt the recorded server if it is the same live process. Returns a note for the model, or None."""
    q, base = shlex.quote, repl.base
    res = await run(repl._env, f"cat {q(base + '/' + RECORD)} 2>/dev/null; echo; echo __SEP__; "
                               f"ls {q(base)}/in 2>/dev/null")
    raw, _, listing = res.stdout.partition("__SEP__\n")
    try:
        rec = json.loads(raw.strip())
        pid, identity, python = int(rec["pid"]), dict(rec["identity"]), str(rec["python"])
    except (ValueError, KeyError, TypeError):
        return None
    alive = await run(repl._env, f"{alive_test(pid)} && echo yes || echo no")
    if alive.stdout.strip() != "yes" or not identity or await process_identities(repl._env, [pid]) != identity:
        return None
    cells = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.py$", listing, re.M)]
    staged = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.tmp$", listing, re.M)]
    seq = max(cells + staged, default=0)
    repl.pid, repl.identity, repl.python = pid, identity, python
    repl.generation += 1
    repl.seq, repl.pending, repl.cursor = seq, 0, 0
    repl.unconfirmed = repl.unseen = False
    head = "[python REPL adopted from an earlier controller of this task: its variables are kept"
    if not seq:
        return head + "]"
    records = await run(repl._env, operations.resolve_script(f"{base}/ops", seq, revoke=seq not in cells))
    parsed = operations.parse(records.stdout)
    if records.code != 0 or parsed is None:
        repl.pending, repl.unconfirmed = seq, True
        return head + f"; cell {seq} records could not be read, so its state is unknown]"
    token, done_text, tag = parsed
    done_file = await run(repl._env, f"[ -f {q(f'{base}/out/{seq}.done')} ] && echo yes || echo no")
    done = done_file.stdout.strip() == "yes"
    if token == operations.REVOKED:
        return head + (f"; cell {seq} was never started: the REPL had not taken it, and it is now cancelled, so it "
                       "cannot run later. Nothing from it ran]")
    if done and operations.seen(tag, repl.conversation):
        return head + f"; cell {seq} completed and was already shown]"
    repl.pending, repl.unseen = seq, True
    return head + (f"; cell {seq} completed and its result follows]" if done else
                   f"; cell {seq} is still running or about to run]")
