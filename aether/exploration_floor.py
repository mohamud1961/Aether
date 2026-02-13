from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

from .event_log import EventLog

_READ_ONLY_EXPLORATION_COMMANDS = frozenset(
    {
        "cat",
        "find",
        "head",
        "ls",
        "pwd",
        "rg",
        "sed",
        "stat",
        "tail",
        "wc",
    }
)


@dataclass(frozen=True)
class ExplorationFloorResult:
    passed: bool
    missing_conditions: List[str]


def check_exploration_floor(run_state: Mapping[str, Any]) -> ExplorationFloorResult:
    """Must pass before transitioning to Implement phase."""
    missing: List[str] = []

    workspace_digest = run_state.get("workspace_digest") or run_state.get("workspace_hash")
    if not isinstance(workspace_digest, str) or not workspace_digest:
        missing.append("workspace_digest")

    if not compute_explore_floor_passed(run_state):
        missing.append("workspace_exploration_missing")

    if not _has_plan_artifact(run_state):
        missing.append("plan_artifact_missing")

    return ExplorationFloorResult(passed=len(missing) == 0, missing_conditions=missing)


def emit_exploration_floor_eval(
    *,
    event_log: EventLog,
    result: ExplorationFloorResult,
    timestamp: str,
    cwd: str,
) -> Dict[str, Any]:
    return event_log.append_event(
        {
            "event_type": "EXPLORATION_FLOOR_EVAL",
            "timestamp": timestamp,
            "cwd": cwd,
            "pass": result.passed,
            "missing_conditions": sorted(result.missing_conditions),
        }
    )


def _has_workspace_exploration_evidence(run_state: Mapping[str, Any]) -> bool:
    explicit = run_state.get("explore_floor_passed")
    if isinstance(explicit, bool):
        return explicit

    # Backward-compatible alias for older callers.
    legacy_explicit = run_state.get("workspace_explored")
    if isinstance(legacy_explicit, bool):
        return legacy_explicit

    events = run_state.get("events", [])
    return _has_workspace_exploration_evidence_from_events(events)


def compute_explore_floor_passed(run_state: Mapping[str, Any]) -> bool:
    """Derive Explore floor readiness from concrete exploration evidence."""
    return _has_workspace_exploration_evidence(run_state)


def _has_workspace_exploration_evidence_from_events(events: Any) -> bool:
    if not isinstance(events, Sequence):
        return False
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_type = str(event.get("event_type", "")).upper()
        if event_type != "TOOL_CALL":
            continue
        exit_code = event.get("exit_code")
        if exit_code not in (0, "0"):
            continue
        tool_name = str(event.get("tool_name", "")).strip().lower()
        if tool_name in {"read_file", "list_directory", "search_files"}:
            return True
        args = event.get("tool_args")
        if not isinstance(args, Mapping):
            continue
        if _run_command_shows_exploration(args.get("command")):
            return True
    return False


def _run_command_shows_exploration(command: Any) -> bool:
    if isinstance(command, str):
        parts = command.split()
    elif isinstance(command, list):
        parts = [str(part) for part in command]
    else:
        return False
    if not parts:
        return False
    first = parts[0].strip().lower()
    binary_name = first.split("/")[-1]
    if binary_name in {"bash", "sh"}:
        for i, arg in enumerate(parts):
            arg_str = str(arg)
            if arg_str.startswith("-") and "c" in arg_str and i + 1 < len(parts):
                inner_cmd = str(parts[i + 1]).strip()
                for segment in _split_shell_segments(inner_cmd):
                    inner_bin = segment.split()[0].split("/")[-1].lower()
                    if inner_bin in _READ_ONLY_EXPLORATION_COMMANDS:
                        return True
                return False
        return False
    return binary_name in _READ_ONLY_EXPLORATION_COMMANDS


def _split_shell_segments(command: str) -> List[str]:
    chunks = command.replace("&&", ";").replace("||", ";").replace("|", ";").split(";")
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _has_plan_artifact(run_state: Mapping[str, Any]) -> bool:
    explicit = run_state.get("plan_artifact_present")
    if isinstance(explicit, bool):
        return explicit

    plan_status = run_state.get("plan_status")
    if isinstance(plan_status, str) and bool(plan_status.strip()):
        return True

    plan_ref = run_state.get("plan_artifact_ref")
    if isinstance(plan_ref, str) and bool(plan_ref.strip()):
        return True

    events = run_state.get("events", [])
    if isinstance(events, Sequence):
        for event in events:
            if not isinstance(event, Mapping):
                continue
            event_type = str(event.get("event_type", "")).upper()
            if event_type in {"PLAN_DEFINED", "PLAN_UPDATE", "PLAN_STATUS_CHANGED"}:
                return True
    return False
