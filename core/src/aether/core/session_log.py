"""One append-only session log outside the controller: the run's recovery object (master checklist H10).

Switch: ``AETHER_CORE_SESSION_LOG=on`` (default off). The adapter points it at ``<logs>/session``, on the host, so it
outlives the controller process (the "brain/hands" split: the sandbox keeps the effects, the log keeps the run).

Two records per model turn, each written only after its snapshot is durable:
- ``asked``: the model's turn (with its tool calls) is in the context; no call has run yet;
- ``done``:  every call of that turn has returned and its result is in the context.

A snapshot is the context object (CLM or message list) plus the run counters, pickled to ``<n>-<kind>.pkl`` with a
temporary file, fsync and rename; then one JSON line ``{seq, kind, turn, file, sha256, bytes}`` is appended to
``log.jsonl`` and fsynced. A record is trusted only when its line parses and its file has that hash, so a torn last
line or a missing snapshot falls back to the previous record; nothing is repaired or guessed.

``recover`` gives a new controller the context to resume with. After ``done`` it is the logged context. After
``asked`` the calls of that turn may or may not have run: each gets a tool result saying exactly that, and Core does
not run them again (no duplicate effect); the model decides, after checking the state if it needs to.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from pathlib import Path
import re
import stat
from typing import Any

LOG = "log.jsonl"
UNKNOWN = ("[controller restarted: this call was requested but its result was never recorded, so it may or may not "
           "have run. Core did not run it again. Check the current state before repeating it.]")


class SessionLogError(RuntimeError):
    """No trustworthy record to resume from."""


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class SessionLog:
    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.seq = sum(1 for _ in _lines(self.dir / LOG))

    def write(self, kind: str, turn: int, state: dict[str, Any]) -> dict[str, Any]:
        data = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
        name = f"{self.seq:06d}-{kind}.pkl"
        tmp = self.dir / (name + ".tmp")
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.dir / name)
        _fsync_dir(self.dir)
        row = {"seq": self.seq, "kind": kind, "turn": turn, "file": name,
               "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        with open(self.dir / LOG, "a") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.seq += 1
        return row


def _lines(path: Path):
    if not path.exists():
        return
    with open(path) as fh:
        for line in fh:
            yield line


# Trust boundary: the snapshots are pickles written by this controller to the host logs directory (never the
# sandbox). The sha256 only ties a snapshot to its log line; whoever can write the directory can write both, so the
# boundary is the directory itself: recover() refuses a directory or snapshot not owned by this user or writable by
# group/others, and any snapshot name that is not a plain ``NNNNNN-kind.pkl`` basename (no path escapes).
NAME = re.compile(r"^\d{6}-(asked|done)\.pkl$")


def _private(path: Path) -> str | None:
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        return f"{path} is a symlink"
    if st.st_uid != os.getuid():
        return f"{path} is not owned by this user"
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return f"{path} is writable by group or others"
    return None


def latest(directory: str | Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """The newest trusted record, its state, and why any newer lines were not trusted."""
    root = Path(directory)
    if root.exists() and (problem := _private(root)):
        raise SessionLogError(f"untrusted session directory: {problem}")
    rejected: list[str] = []
    rows = []
    for n, line in enumerate(_lines(root / LOG), 1):
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or {"seq", "kind", "file", "sha256"} - row.keys():
                raise ValueError("missing fields")
            rows.append(row)
        except ValueError as exc:
            rejected.append(f"line {n}: {exc}")
    for row in reversed(rows):
        if not isinstance(row["file"], str) or not NAME.match(row["file"]):
            rejected.append(f"seq {row['seq']}: snapshot name not allowed")
            continue
        path = root / row["file"]
        if not path.is_file():
            rejected.append(f"seq {row['seq']}: snapshot missing")
            continue
        if problem := _private(path):
            rejected.append(f"seq {row['seq']}: {problem}")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            rejected.append(f"seq {row['seq']}: snapshot hash differs")
            continue
        return row, pickle.loads(data), rejected
    raise SessionLogError("no trusted session record" + (f" ({'; '.join(rejected)})" if rejected else ""))


def _history(context: Any) -> list[dict[str, Any]]:
    return context.editable if hasattr(context, "editable") else context


def state_of(s: Any) -> dict[str, Any]:
    """What a new controller needs: the context object and the run counters (CLM's per-message reasoning-token
    bookkeeping is keyed by object id and does not survive a pickle; it is accounting only)."""
    return {"context": s.clm if s.clm else s.messages, "steps": s.result.steps, "calls": s.result.calls}


def recover(directory: str | Path) -> tuple[Any, dict[str, Any]]:
    """(context to resume with, account of the recovery). Calls of an ``asked`` turn are answered as unknown."""
    row, state, rejected = latest(directory)
    context = state["context"]
    unanswered: list[str] = []
    if row["kind"] == "asked":
        history = _history(context)
        last = next((m for m in reversed(history) if m.get("role") == "assistant"), None)
        answered = {m.get("tool_call_id") for m in history if m.get("role") == "tool"}
        unanswered = [c["id"] for c in (last or {}).get("tool_calls") or [] if c["id"] not in answered]
        notes = [{"role": "tool", "tool_call_id": cid, "content": UNKNOWN} for cid in unanswered]
        if hasattr(context, "append"):
            context.append(*notes)
        else:
            context.extend(notes)
    return context, {"seq": row["seq"], "kind": row["kind"], "turn": row.get("turn"), "unanswered": unanswered,
                     "rejected": rejected, "steps": state.get("steps"), "calls": state.get("calls")}
