"""Sandbox records of one dispatched operation, and the single state machine read from them.

A controller can lose a dispatch anywhere: the container exec dies part-way, or it completes and its reply is lost,
or the controller itself dies. Whether the operation ran must then be decided from the sandbox alone, and exactly one
answer may ever be given. Every record lives in the operation owner's directory, keyed by sequence ``N``:

- ``claim_N/``   one controller reserved ``N`` (``mkdir``), before anything was staged. ``claim_N/offset`` is the
  output offset where the operation's output begins.
- ``start_N``    the start token: a symlink whose target says who took it. The executor creates it as ``run`` as its
  first action, and runs the operation only if that creation succeeded. A controller that can no longer tell whether
  the operation was handed over creates it as ``revoked``. ``symlink(2)`` is atomic and fails when the name exists,
  so exactly one of them wins: an operation either ran or never will.
- ``done_N``     the executor's completion receipt, written after the operation returned.
- ``delivered_N`` a controller consumed the receipt to show the result. A later controller does not show it again.

States (``classify``)::

    claimed --revoke--> revoked                      (never ran, never will)
    claimed --executor takes token--> running --> completed --> delivered
                                        \\--executor dies--> lost        (effect unknown)

There is no state in which a crashed dispatch stays undecided while its directory exists: a controller that finds no
token takes it as ``revoked``. Effects outside the sandbox are not covered: an operation that ran and then lost its
executor is ``lost``, its effect unknown, never retried here.
"""

from __future__ import annotations

import re
import shlex

RUN = "run"
REVOKED = "revoked"
DONE = re.compile(r"__AETHER_DONE_(\d+)_(\d+)")
_SEP = "__AETHER_OP__"


def start_gate(root: str, seq: int) -> str:
    """Shell condition true for the executor only when it took the token. A missing directory cannot be revoked
    either, so the operation runs (its receipt then cannot be written, as before tracking existed)."""
    q = shlex.quote
    return f"{{ command ln -s {RUN} {q(f'{root}/start_{seq}')} 2>/dev/null || [ ! -d {q(root)} ]; }}"


def resolve_script(root: str, seq: int, *, revoke: bool) -> str:
    """Print the token, the receipt and the delivery record of ``seq``. With ``revoke``, an absent token is first taken
    as ``revoked``. Output: token, receipt, delivered flag, separated by ``_SEP`` lines; ``missing`` if no directory."""
    q = shlex.quote
    token = f"start_{seq}"
    take = f"command ln -s {REVOKED} {token} 2>/dev/null; " if revoke else ""
    return (
        f"cd {q(root)} 2>/dev/null || {{ echo missing; exit 0; }}; {take}"
        f"readlink {token} 2>/dev/null; echo {_SEP}; cat done_{seq} 2>/dev/null; echo {_SEP}; "
        f"[ -e delivered_{seq} ] && echo yes; true"
    )


def parse(stdout: str) -> tuple[str | None, str | None, bool] | None:
    """(token, receipt, delivered) from ``resolve_script`` output; None when the directory is missing."""
    parts = stdout.split(_SEP + "\n")
    if len(parts) != 3:
        return None
    token, done, delivered = (part.strip() for part in parts)
    return token or None, done or None, delivered == "yes"


def mark_delivered(root: str, seq: int) -> str:
    return f": > {shlex.quote(f'{root}/delivered_{seq}')}"


def classify(seq: int | None, token: str | None, done: str | None, delivered: bool, alive: bool) -> tuple[str, int | None]:
    """The state of operation ``seq`` from its records. Returns (state, exit)."""
    if seq is None:
        return "idle", None
    if done is not None:
        mark = DONE.search(done)
        if mark is None or int(mark.group(1)) != seq:
            return "lost", None
        return ("delivered" if delivered else "completed"), int(mark.group(2))
    if token == REVOKED:
        return "revoked", None
    if token == RUN:
        return ("running", None) if alive else ("lost", None)
    return "unresolved", None  # no token: only before a revoke was attempted
