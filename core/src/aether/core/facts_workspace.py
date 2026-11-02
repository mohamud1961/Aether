"""Bounded initial-workspace metadata used by the Core facts service."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


class ManagedFactsText(str):
    """In-process provenance that cannot be supplied by a serialized user message."""

    def __new__(cls, value: str, checkpoint: Any = None):
        obj = super().__new__(cls, value)
        obj.checkpoint = deepcopy(checkpoint)
        return obj


def continuation_state(resume: Any) -> Any:
    """Read private state only from a Core-owned in-process context note."""
    pinned = getattr(resume, "pinned", None)
    if isinstance(pinned, list):
        index = getattr(resume, "_managed_facts_pin_index", None)
        notes = [pinned[index]] if type(index) is int and 0 <= index < len(pinned) else []
    else:
        notes = resume if isinstance(resume, list) else []
    matches = [msg.get("content") for msg in notes if isinstance(msg, dict)
               and isinstance(msg.get("content"), ManagedFactsText)]
    checkpoint = getattr(matches[0], "checkpoint", None) if len(matches) == 1 else None
    return deepcopy(checkpoint) if isinstance(checkpoint, InitialWorkspace) else None


def install_project_note(messages: list[dict[str, Any]], content: str) -> int:
    indexes = [i for i, msg in enumerate(messages) if msg.get("role") == "user"
               and isinstance(msg.get("content"), ManagedFactsText)]
    if len(indexes) > 1:
        raise ValueError("multiple Core-owned state notes in project context")
    note = {"role": "user", "content": content if isinstance(content, ManagedFactsText) else ManagedFactsText(content)}
    if indexes:
        messages[indexes[0]] = note
        return indexes[0]
    messages.append(note)
    return len(messages) - 1


class InitialWorkspace:
    """Remember only the initial observation; do not reconstruct a missing one."""

    def __init__(self) -> None:
        self.initial: dict[str, Any] | None = None
        self.changes: dict[str, dict[str, Any]] = {}
        self.scope = "run_start"
        self.continuations = 0
        self.origin_continuation = 0
        self.compatible: bool | None = True
        self.resuming = False

    def prepare_resume(self) -> None:
        self.continuations += 1
        self.resuming = True
        self.compatible = None
        if self.initial is None:
            self.scope = "continuation_start"
            self.origin_continuation = self.continuations

    def scope_note(self) -> str:
        if not self.continuations:
            return ""
        if self.initial is None:
            return "\nThe original starting state was not retained; the continuation baseline is unmeasured."
        if self.scope == "continuation_start":
            return f"\nThe original starting state was not retained; this baseline is from continuation {self.origin_continuation}."
        if not self.compatible:
            return "\nThe prior starting state is retained, but its relation to the current workspace is unverified."
        return "\nThe prior starting observation is retained for this same observed workspace identity."

    def capture(self, workspace: dict[str, Any] | None) -> None:
        if self.resuming:
            self.resuming = False
            if self.initial is not None and workspace is None:
                return
            if self.initial is not None and workspace["root"] == self.initial["root"]:
                self.compatible = True
                self.observe(workspace, 0)
                return
            self.initial, self.changes, self.scope = None, {}, "continuation_start"
            self.origin_continuation = self.continuations
        if workspace is not None:
            self.initial = {"root": list(workspace["root"]), "files": deepcopy(workspace["files"]),
                            "complete": workspace["complete"]}
            self.compatible = True

    def observe(self, workspace: dict[str, Any] | None, step: int) -> list[str]:
        if self.initial is None or workspace is None:
            return []
        if workspace["root"] != self.initial["root"]:
            self.compatible = False
            return []
        self.compatible = True
        new: list[dict[str, Any]] = []
        for path, initial_metadata in self.initial["files"].items():
            if path in self.changes:
                continue
            current = workspace["files"].get(path)
            if current is None and workspace["complete"]:
                kind = "not_in_complete_scan"
            elif current is not None and current != initial_metadata:
                kind = "metadata_changed"
            else:
                continue
            row = {"path": path, "first_observed_step": step, "kind": kind}
            if self.continuations:
                row["continuation"] = self.continuations
            self.changes[path] = row
            new.append(row)
        notices = [self.describe(row) for row in new[:8]]
        if len(new) > 8:
            notices.append(f"{len(new) - 8} additional initial workspace differences are not listed.")
        return notices

    def describe(self, row: dict[str, Any]) -> str:
        path, step = json.dumps(row["path"], ensure_ascii=True), row["first_observed_step"]
        label = "initial workspace observation" if self.scope == "run_start" else "continuation's initial workspace observation"
        when = f"continuation {row['continuation']} step {step}" if row.get("continuation") else f"step {step}"
        if row["kind"] == "metadata_changed":
            return (f"Compared with the {label}, metadata for {path} differed "
                    f"when observed at {when}; content is not established by metadata.")
        return (f"A file from the {label}, {path}, was not in the complete "
                f"metadata scan at {when}.")

    def context(self) -> list[str]:
        rows = list(self.changes.values())
        notices = [self.describe(row) for row in rows[-8:]]
        if len(rows) > 8:
            notices.append(f"{len(rows) - 8} earlier initial workspace differences are not listed.")
        return notices

    def record(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if self.initial is None:
            return {"status": "unknown", "scope": self.scope}, []
        initial = {"status": "observed" if self.compatible else "unknown", "complete": self.initial["complete"],
                   "file_count": len(self.initial["files"]), "observation_step": 0, "scope": self.scope,
                   "origin_continuation": self.origin_continuation}
        return initial, deepcopy(list(self.changes.values()))
