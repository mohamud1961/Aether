from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from aether.evals.utils.artifacts import ArtifactStoreView, open_artifact_store
from aether.evals.utils.events import Event, canonicalize_event_type, validate_hash_chain


# Explicit compatibility aliases for legacy telemetry event_type values observed in paid Phase 3 runs.
# These mappings are narrow and one-to-one; all applications are recorded in compat_issues.
COMPAT_ALIASES: Dict[str, str] = {
    "state_transition": "PHASE_TRANSITION",
    "model_request": "MODEL_CALL",
    "model_response": "MODEL_CALL",
    "governance_decision": "APPROVAL_GRANTED",
    "model_error": "POLICY_VIOLATION",
    "replay_gate": "REPLAY_END",
}


@dataclass(frozen=True)
class HarnessRunView:
    run_dir: Path
    artifact_dir: Path
    events_path: Path
    cas_roots: Sequence[Path]
    artifact_store: ArtifactStoreView

    def load_events(self) -> List[Event]:
        events, _ = load_events_with_compat(self.events_path)
        return events

    def load_events_with_compat_issues(self) -> Tuple[List[Event], List[Dict[str, Any]]]:
        return load_events_with_compat(self.events_path)


def _lookup_compat_alias(raw_event_type: Any) -> str | None:
    if not isinstance(raw_event_type, str):
        return None
    candidate = raw_event_type.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    alias = COMPAT_ALIASES.get(lowered)
    if alias is not None:
        return alias
    upper = candidate.upper()
    return COMPAT_ALIASES.get(upper)


def _canonicalize_event_type_with_compat(
    *,
    raw_event_type: Any,
    source_name: str,
    line_no: int,
    compat_issues: List[Dict[str, Any]],
) -> str:
    try:
        return canonicalize_event_type(raw_event_type)
    except ValueError:
        compat_alias = _lookup_compat_alias(raw_event_type)
        if compat_alias is not None:
            compat_issues.append(
                {
                    "code": "event_type_compat_alias_applied",
                    "source": source_name,
                    "line_no": line_no,
                    "raw_event_type": raw_event_type,
                    "canonical_event_type": compat_alias,
                }
            )
            return compat_alias

        compat_issues.append(
            {
                "code": "unknown_event_type",
                "source": source_name,
                "line_no": line_no,
                "raw_event_type": raw_event_type,
            }
        )
        if isinstance(raw_event_type, str) and raw_event_type.strip():
            return raw_event_type.strip().upper()
        return "UNKNOWN_EVENT_TYPE"


def load_events_with_compat(events_path_or_dir: str | Path) -> Tuple[List[Event], List[Dict[str, Any]]]:
    root = Path(events_path_or_dir)
    events_path = _resolve_events_path(root) if root.is_dir() else root
    source_name = events_path.name

    compat_issues: List[Dict[str, Any]] = []
    events: List[Event] = []
    for line_no, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
        except Exception as exc:
            raise ValueError(f"{source_name} line {line_no}: invalid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{source_name} line {line_no}: event must be a JSON object")

        event_type = _canonicalize_event_type_with_compat(
            raw_event_type=raw.get("event_type"),
            source_name=source_name,
            line_no=line_no,
            compat_issues=compat_issues,
        )
        step_raw = raw.get("step_id")
        step_id = int(step_raw) if isinstance(step_raw, int) else -1
        events.append(
            Event(
                event_id=str(raw.get("event_id", "")),
                prev_event_hash=str(raw.get("prev_event_hash", "")),
                event_type=event_type,
                step_id=step_id,
                timestamp=str(raw.get("timestamp", "")),
                cwd=str(raw.get("cwd", "")),
                payload=raw,
            )
        )
    return events, compat_issues


def _resolve_events_path(run_dir: Path) -> Path:
    for name in ("events.jsonl", "event_log.jsonl"):
        path = run_dir / name
        if path.exists() and path.is_file():
            return path
    raise FileNotFoundError(
        f"Missing telemetry file in {run_dir}: expected events.jsonl or event_log.jsonl"
    )


def open_harness_run_view(run_dir: str | Path) -> HarnessRunView:
    root = Path(run_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Run directory does not exist: {root}")

    events_path = _resolve_events_path(root)
    artifact_store = open_artifact_store(root)
    existing_cas_roots = tuple(
        path for path in artifact_store.cas_roots if path.exists() and path.is_dir()
    )
    if not existing_cas_roots:
        expected = ", ".join(path.as_posix() for path in artifact_store.cas_roots)
        raise FileNotFoundError(
            f"Missing CAS roots for run directory {root}. Expected one of: {expected}"
        )

    return HarnessRunView(
        run_dir=root,
        artifact_dir=root,
        events_path=events_path,
        cas_roots=existing_cas_roots,
        artifact_store=artifact_store,
    )


def summarize_harness_run(run_dir: str | Path) -> Dict[str, Any]:
    view = open_harness_run_view(run_dir)
    events, compat_issues = view.load_events_with_compat_issues()
    hash_ok, first_bad_event_id = validate_hash_chain(events)

    run_ids = sorted(
        {
            run_id
            for run_id in (event.payload.get("run_id") for event in events)
            if isinstance(run_id, str) and run_id
        }
    )
    run_id: str | None
    if not run_ids:
        run_id = None
    elif len(run_ids) == 1:
        run_id = run_ids[0]
    else:
        run_id = ",".join(run_ids)

    first_step_id: int | None = None
    last_step_id: int | None = None
    if events:
        first_raw = events[0].payload.get("step_id")
        last_raw = events[-1].payload.get("step_id")
        first_step_id = first_raw if isinstance(first_raw, int) else None
        last_step_id = last_raw if isinstance(last_raw, int) else None

    return {
        "run_dir": view.run_dir.as_posix(),
        "run_id": run_id,
        "event_count": len(events),
        "first_step_id": first_step_id,
        "last_step_id": last_step_id,
        "hash_chain_ok": hash_ok,
        "first_bad_event_id": first_bad_event_id,
        "events_path": view.events_path.as_posix(),
        "cas_roots": [path.as_posix() for path in view.cas_roots],
        "compat_issues": compat_issues,
    }
