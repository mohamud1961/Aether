"""The harness-side context file: text, Aether-appended entries, edits, forced trim.

The file lives under the run's evidence directory, never in the task workspace
or container.  Aether appends entries; the model may rewrite anything.  Aether
only ever removes text it appended itself and that is still present verbatim.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .tools import edit_arguments_error

TEXT_NAME = "context_file.txt"
EVENTS_NAME = "events.jsonl"
EVENT_ARG_CAP = 2_000


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


@dataclass(frozen=True)
class Entry:
    entry_id: int
    text: str


@dataclass(frozen=True)
class EditResult:
    ok: bool
    mode: str
    error: str
    before_sha256: str
    after_sha256: str
    before_bytes: int
    after_bytes: int

    def fact(self) -> str:
        if not self.ok:
            return f"context_file_edit: rejected ({self.error}); file unchanged at {self.after_bytes} bytes"
        return f"context_file_edit: applied {self.mode}, {self.before_bytes} -> {self.after_bytes} bytes"


@dataclass(frozen=True)
class TrimResult:
    removed_entry_ids: tuple[int, ...]
    before_bytes: int
    after_bytes: int
    target_bytes: int

    @property
    def reached_target(self) -> bool:
        return self.after_bytes <= self.target_bytes


class ContextFile:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._events_path = self.directory / EVENTS_NAME
        if self._events_path.exists():
            raise FileExistsError(f"context file evidence already exists: {self._events_path}")
        self.text = ""
        self._entries: list[Entry] = []
        self._next_id = 1
        self._persist()

    @property
    def size(self) -> int:
        return byte_len(self.text)

    def append(self, kind: str, body: str, *, step: int) -> Entry:
        entry = Entry(self._next_id, f"[#{self._next_id} step {int(step)} {kind}]\n{body}\n\n")
        self._next_id += 1
        self._entries.append(entry)
        self.text += entry.text
        self._persist()
        self._event({"event": "append", "entry_id": entry.entry_id, "kind": kind, "step": int(step),
                     "entry_bytes": byte_len(entry.text), "file_bytes": self.size})
        return entry

    def apply_edit(self, arguments: Mapping[str, Any], *, step: int) -> EditResult:
        before, error, mode = self.text, edit_arguments_error(arguments), "invalid"
        new_text = before
        if not error and "replace_all_text" in arguments:
            mode, new_text = "replace_all_text", arguments["replace_all_text"]
        elif not error:
            mode, old = "str_replace", arguments["old"]
            matches = before.count(old)
            if matches == 0:
                error = "old text not found in the context file"
            elif matches > 1:
                error = f"old text matches {matches} places; include more surrounding text so it is unique"
            else:
                new_text = before.replace(old, arguments["new"], 1)
        if not error:
            self.text = new_text
            self._persist()
        result = EditResult(
            ok=not error, mode=mode, error=error, before_sha256=sha256_text(before),
            after_sha256=sha256_text(self.text), before_bytes=byte_len(before), after_bytes=self.size,
        )
        self._event({
            "event": "edit", "step": int(step), "ok": result.ok, "mode": mode, "error": error,
            "before_sha256": result.before_sha256, "after_sha256": result.after_sha256,
            "before_bytes": result.before_bytes, "after_bytes": result.after_bytes,
            "arguments": _event_arguments(arguments),
        })
        return result

    def forced_trim(self, target_bytes: int) -> TrimResult:
        """Drop the oldest Aether-appended entries still present verbatim, never model text."""
        before = self.size
        removed: list[int] = []
        marker_done = False
        for entry in list(self._entries):
            if self.size <= target_bytes:
                break
            if entry.text not in self.text:
                continue
            replacement = ""
            if not marker_done:
                replacement, marker_done = "[earlier entries removed to fit the size budget]\n\n", True
            self.text = self.text.replace(entry.text, replacement, 1)
            self._entries.remove(entry)
            removed.append(entry.entry_id)
        self._persist()
        result = TrimResult(tuple(removed), before, self.size, int(target_bytes))
        self._event({"event": "forced_trim", "removed_entry_ids": removed, "before_bytes": before,
                     "after_bytes": result.after_bytes, "target_bytes": int(target_bytes),
                     "reached_target": result.reached_target})
        return result

    def _persist(self) -> None:
        tmp = self.directory / (TEXT_NAME + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(self.text)
        os.replace(tmp, self.directory / TEXT_NAME)

    def _event(self, row: Mapping[str, Any]) -> None:
        line = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fd = os.open(self._events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def log_event(self, row: Mapping[str, Any]) -> None:
        self._event(row)


def _event_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in arguments.items():
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        out[str(key)] = text if len(text) <= EVENT_ARG_CAP else {
            "sha256": sha256_text(text), "chars": len(text), "head": text[:EVENT_ARG_CAP // 4],
        }
    return out
