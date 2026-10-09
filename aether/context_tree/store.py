"""Append-only task-local event and tree streams [OptChat §2]."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import threading
from typing import Any, Iterable, Mapping

EVENT_KINDS = frozenset({"task", "talk", "tool", "echo", "note"})
CAP = 30_000


class StoreError(RuntimeError):
    """Run storage could not preserve append-only custody."""


def _ensure_private_directory(path: Path) -> None:
    """Create one evidence directory chain and make its components private."""
    path = Path(path)
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    if not cursor.is_dir():
        raise StoreError(f"evidence directory parent is not a directory: {cursor}")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise StoreError(f"evidence path is not a directory: {directory}")
        os.chmod(directory, 0o700)
    if path.is_symlink() or not path.is_dir():
        raise StoreError(f"evidence path is not a regular directory: {path}")
    os.chmod(path, 0o700)


def _open_private_file(path: Path, flags: int) -> int:
    if path.is_symlink():
        raise StoreError(f"evidence stream must not be a symlink: {path}")
    fd = os.open(
        path,
        flags | os.O_NOFOLLOW,
        0o600,
    )
    os.fchmod(fd, 0o600)
    return fd


def cap_tool_result(text: str, cap: int = CAP) -> str:
    if cap < 32:
        raise ValueError("cap must leave room for an omission note")
    if len(text) <= cap:
        return text
    note_template = "\n...[omitted {count} characters]...\n"
    # The final note length depends on the number omitted, so settle it twice.
    keep = cap
    while True:
        head = keep // 2
        tail = keep - head
        omitted = len(text) - keep
        note = note_template.format(count=omitted)
        new_keep = max(0, cap - len(note))
        if new_keep == keep:
            return text[:head] + note + (text[-tail:] if tail else "")
        keep = new_keep


class RunStore:
    """Own the two append-only streams for exactly one task run."""

    def __init__(self, run_dir: Path, *, create: bool, task_text: str | None = None,
                 task_workspace: Path | None = None) -> None:
        self.run_dir = Path(run_dir).resolve()
        if task_workspace is not None and _is_within(self.run_dir, Path(task_workspace).resolve()):
            raise StoreError("context-tree evidence must be outside the task workspace")
        if create:
            _ensure_private_directory(self.run_dir.parent)
            try:
                self.run_dir.mkdir(mode=0o700)
            except FileExistsError:
                raise
            os.chmod(self.run_dir, 0o700)
        elif not self.run_dir.is_dir():
            raise StoreError(f"run directory does not exist: {self.run_dir}")
        else:
            os.chmod(self.run_dir, 0o700)
        self.log_dir = self.run_dir / "log"
        self.tree_dir = self.run_dir / "tree"
        self.log_path = self.log_dir / "events.jsonl"
        self.tree_path = self.tree_dir / "nodes.jsonl"
        _ensure_private_directory(self.log_dir)
        _ensure_private_directory(self.tree_dir)
        self._lock = threading.RLock()
        self._lock_path = self.run_dir / ".writer.lock"
        self._lock_fd = _open_private_file(
            self._lock_path, os.O_CREAT | os.O_RDWR,
        )
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self._lock_fd)
            raise StoreError("another writer owns this task run") from exc
        self._repair_and_read(self.log_path)
        self._repair_and_read(self.tree_path)
        if create:
            if task_text is None:
                raise StoreError("new run requires the raw task instruction")
            if self.read_events():
                raise StoreError("new run is not empty")
            self.append_event("task", task_text)

    @classmethod
    def create(cls, evidence_root: Path, run_id: str, task_text: str,
               *, task_workspace: Path | None = None) -> "RunStore":
        if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
            raise StoreError("run_id must be one safe path component")
        return cls(Path(evidence_root) / run_id, create=True, task_text=task_text,
                   task_workspace=task_workspace)

    @classmethod
    def open(cls, run_dir: Path, *, task_workspace: Path | None = None) -> "RunStore":
        return cls(run_dir, create=False, task_workspace=task_workspace)

    def _repair_and_read(self, path: Path) -> list[dict[str, Any]]:
        fd = _open_private_file(path, os.O_CREAT | os.O_RDWR)
        os.close(fd)
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            fd = _open_private_file(path, os.O_WRONLY | os.O_APPEND)
            try:
                if os.write(fd, b"\n") != 1:
                    raise StoreError("failed to repair torn final line")
                os.fsync(fd)
            finally:
                os.close(fd)
            raw += b"\n"
        rows: list[dict[str, Any]] = []
        for number, line in enumerate(raw.splitlines(), 1):
            if not line:
                continue
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                # Torn/invalid records remain in place and are reported by index.
                self.recovery_errors.append(f"{path.name}:{number}: invalid JSON skipped")
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    @property
    def recovery_errors(self) -> list[str]:
        if not hasattr(self, "_recovery_errors"):
            self._recovery_errors: list[str] = []
        return self._recovery_errors

    def _append(self, path: Path, value: Mapping[str, Any]) -> None:
        line = (json.dumps(dict(value), ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            fd = _open_private_file(path, os.O_WRONLY | os.O_APPEND)
            try:
                written = os.write(fd, line)
                if written != len(line):
                    raise StoreError("short append would violate one-write record durability")
                os.fsync(fd)
            finally:
                os.close(fd)

    def read_events(self) -> list[dict[str, Any]]:
        return self._repair_and_read(self.log_path)

    def read_nodes(self) -> list[dict[str, Any]]:
        return self._repair_and_read(self.tree_path)

    def append_event(self, kind: str, text: str) -> dict[str, Any]:
        if kind not in EVENT_KINDS:
            raise StoreError(f"unsupported event kind: {kind!r}")
        if not isinstance(text, str):
            raise TypeError("event text must be a string")
        with self._lock:
            events = self.read_events()
            row = {"i": max((int(item.get("i", -1)) for item in events), default=-1) + 1,
                   "kind": kind, "text": text,
                   "size": len(f"{kind}: {text}".encode("utf-8"))}
            self._append(self.log_path, row)
            return row

    def append_node(self, level: int, index: int, text: str, *,
                    event_count: int, phase: str, source: str) -> dict[str, Any]:
        row = {"l": int(level), "i": int(index), "text": str(text),
               "size": len(str(text).encode("utf-8")),
               "event_count": int(event_count), "phase": str(phase),
               "source": str(source)}
        self._append(self.tree_path, row)
        return row

    def close(self) -> None:
        if getattr(self, "_lock_fd", -1) >= 0:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = -1

    def __enter__(self) -> "RunStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
