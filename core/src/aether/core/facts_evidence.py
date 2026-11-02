"""Compare bounded post-action workspace samples without asserting correctness."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def workspace_digest(workspace: dict[str, Any] | None) -> str | None:
    if workspace is None:
        return None
    metadata = json.dumps({"root": workspace["root"], "files": workspace["files"]},
                          sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(metadata).hexdigest()


def observation_state(events: list[dict[str, Any]], omitted_events: int, call_id: str,
                      workspace: dict[str, Any] | None, latest_step: int | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown", "call_id": call_id, "latest_step": latest_step,
        "scope": ("Bounded post-action metadata samples only; not proof of content, "
                  "tool input state, uninterrupted continuity, or external state."),
    }
    if omitted_events:
        result["reason"] = "history_truncated"
        return result
    matches = [event for event in events if isinstance(call_id, str) and event.get("call_id") == call_id]
    if len(matches) != 1:
        result["reason"] = "missing_or_ambiguous_call_id"
        return result
    event = matches[0]
    result.update(observation_step=event["step"], observation_complete=event["workspace_complete"])
    current = workspace_digest(workspace)
    result["latest_complete"] = workspace["complete"] if workspace is not None else None
    if event["workspace_metadata_sha256"] is None or current is None:
        result["reason"] = "workspace_unobserved"
        return result
    result["status"] = ("sample_matches" if event["workspace_metadata_sha256"] == current
                        else "sample_differs")
    return result
