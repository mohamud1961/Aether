"""Bounded initial-workspace metadata used by the Core facts service."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


class ManagedFactsText(str):
    """In-process provenance that cannot be supplied by a serialized user message."""


def install_project_note(messages: list[dict[str, Any]], content: str) -> int:
    indexes = [i for i, msg in enumerate(messages) if msg.get("role") == "user"
               and isinstance(msg.get("content"), ManagedFactsText)]
    if len(indexes) > 1:
        raise ValueError("multiple Core-owned state notes in project context")
    note = {"role": "user", "content": ManagedFactsText(content)}
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

    def capture(self, workspace: dict[str, Any] | None) -> None:
        if workspace is not None:
            self.initial = {"root": list(workspace["root"]), "files": deepcopy(workspace["files"]),
                            "complete": workspace["complete"]}

    def observe(self, workspace: dict[str, Any] | None, step: int) -> list[str]:
        if self.initial is None or workspace is None or workspace["root"] != self.initial["root"]:
            return []
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
            self.changes[path] = row
            new.append(row)
        notices = [self.describe(row) for row in new[:8]]
        if len(new) > 8:
            notices.append(f"{len(new) - 8} additional initial workspace differences are not listed.")
        return notices

    @staticmethod
    def describe(row: dict[str, Any]) -> str:
        path, step = json.dumps(row["path"], ensure_ascii=True), row["first_observed_step"]
        if row["kind"] == "metadata_changed":
            return (f"Compared with the initial workspace observation, metadata for {path} differed "
                    f"when observed at step {step}; content is not established by metadata.")
        return (f"A file from the initial workspace observation, {path}, was not in the complete "
                f"metadata scan at step {step}.")

    def context(self) -> list[str]:
        rows = list(self.changes.values())
        notices = [self.describe(row) for row in rows[-8:]]
        if len(rows) > 8:
            notices.append(f"{len(rows) - 8} earlier initial workspace differences are not listed.")
        return notices

    def record(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if self.initial is None:
            return {"status": "unknown"}, []
        initial = {"status": "observed", "complete": self.initial["complete"],
                   "file_count": len(self.initial["files"]), "observation_step": 0}
        return initial, deepcopy(list(self.changes.values()))
