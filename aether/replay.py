"""
Replay - Artifact and ContextSlice Semantic Verification

This module implements recorded-output replay for the agentic harness.

EXPLICIT SEMANTICS (Design Decision):
    Replay verifies recorded evidence semantics and does NOT:
    - Execute any subprocess or system calls
    - Read workspace filesystem state
    - Restore or modify files
    - Recompute ContextPacks from current filesystem

    Replay DOES:
    - Verify hash chain integrity of recorded events
    - Verify recorded artifacts exist in ArtifactStore
    - Compare recorded context_pack_hash and manifest_hash against expected
    - Validate ContextSlice bindings against CAS artifact bytes and model_request/compiler events
    - Fail closed on any mismatch

    This is a deliberate design choice. Replay validates that the recorded
    session is internally consistent and tamper-evident, but does NOT
    guarantee filesystem state matches. For workspace state verification,
    use workspace fingerprints at execution time.

See also: test_replay_no_filesystem.py for isolation tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .artifact_store import ArtifactStore
from .event_log import EventLog
from .hash_chain import NULL_EVENT_HASH, compute_event_id
from .hashing import sha256_hex

DECISION_EVENT_TYPES: Dict[str, List[str]] = {
    "MODEL_ROUTE_DECISION": ["from_model_id", "to_model_id", "signals_hash", "reason_codes"],
    "TOOL_DENY": ["tool_name", "deny_reason_code", "attempted_action_fingerprint"],
    "VERIFIER_run": ["verifier_id", "params_hash", "verifier_stage"],
}


@dataclass(frozen=True)
class ReplayOutcome:
    ok: bool
    mismatch_report_ref: Optional[str]
    event: Dict[str, Any]


def replay_recorded_output(
    *,
    events: List[Dict[str, Any]],
    artifact_store: ArtifactStore,
    event_log: EventLog,
    expected_context_pack_hash: Optional[str],
    expected_manifest_hash: Optional[str],
    timestamp: str,
    cwd: str,
) -> ReplayOutcome:
    policy_hash = _recorded_policy_hash(events)
    replay_id = sha256_hex(
        json.dumps(
            {
                "run_id": event_log.run_id,
                "events_count": len(events),
                "policy_hash": policy_hash,
                "timestamp": timestamp,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )[:16]
    replay_start = event_log.append_event(
        {
            "event_type": "REPLAY_START",
            "timestamp": timestamp,
            "cwd": cwd,
            "run_id": event_log.run_id,
            "replay_id": replay_id,
            "policy_hash": policy_hash,
            "replay_mode": "recorded",
        }
    )

    tool_attempts = _deny_replay_tool_attempts(
        events=events,
        event_log=event_log,
        timestamp=timestamp,
        cwd=cwd,
    )

    hash_chain_issue = _verify_hash_chain(events)
    if hash_chain_issue is not None:
        return _fail_replay(
            event_log=event_log,
            artifact_store=artifact_store,
            mismatch=hash_chain_issue,
            timestamp=timestamp,
            cwd=cwd,
            replay_id=replay_id,
            total_decisions=0,
            divergent_decisions=0,
            divergence_rate=0.0,
        )

    recorded_context_pack_hash, recorded_manifest_hash = _latest_hashes(events)
    if expected_context_pack_hash != recorded_context_pack_hash:
        mismatch = {
            "mismatch_type": "context_pack_mismatch",
            "expected_hash": expected_context_pack_hash,
            "observed_hash": recorded_context_pack_hash,
            "first_bad_step_id": _first_step_id(events),
        }
        return _fail_replay(
            event_log=event_log,
            artifact_store=artifact_store,
            mismatch=mismatch,
            timestamp=timestamp,
            cwd=cwd,
            replay_id=replay_id,
            total_decisions=0,
            divergent_decisions=0,
            divergence_rate=0.0,
        )

    if expected_manifest_hash != recorded_manifest_hash:
        mismatch = {
            "mismatch_type": "manifest_mismatch",
            "expected_hash": expected_manifest_hash,
            "observed_hash": recorded_manifest_hash,
            "first_bad_step_id": _first_step_id(events),
        }
        return _fail_replay(
            event_log=event_log,
            artifact_store=artifact_store,
            mismatch=mismatch,
            timestamp=timestamp,
            cwd=cwd,
            replay_id=replay_id,
            total_decisions=0,
            divergent_decisions=0,
            divergence_rate=0.0,
        )

    missing = _verify_artifacts(events, artifact_store)
    if missing is not None:
        return _fail_replay(
            event_log=event_log,
            artifact_store=artifact_store,
            mismatch=missing,
            timestamp=timestamp,
            cwd=cwd,
            replay_id=replay_id,
            total_decisions=0,
            divergent_decisions=0,
            divergence_rate=0.0,
        )

    context_slice_issue = _verify_context_slice_bindings(events, artifact_store)
    if context_slice_issue is not None:
        return _fail_replay(
            event_log=event_log,
            artifact_store=artifact_store,
            mismatch=context_slice_issue,
            timestamp=timestamp,
            cwd=cwd,
            replay_id=replay_id,
            total_decisions=0,
            divergent_decisions=0,
            divergence_rate=0.0,
        )

    total_decisions, divergent_decisions = _compare_decisions_and_emit_divergence(
        events=events,
        event_log=event_log,
        timestamp=timestamp,
        cwd=cwd,
        replay_id=replay_id,
    )
    divergence_rate = 0.0 if total_decisions == 0 else (divergent_decisions / total_decisions)

    event_log.append_event(
        {
            "event_type": "REPLAY_END",
            "timestamp": timestamp,
            "cwd": cwd,
            "run_id": event_log.run_id,
            "replay_id": replay_id,
            "pass": divergent_decisions == 0,
            "divergence_rate": divergence_rate,
            "total_decisions": total_decisions,
            "divergent_decisions": divergent_decisions,
            "tool_execution_attempts_denied": tool_attempts,
        }
    )
    event = event_log.append_event(
        {
            "event_type": "replay_gate",
            "timestamp": timestamp,
            "cwd": cwd,
            "termination_reason": None,
            "replay_id": replay_id,
        }
    )
    return ReplayOutcome(ok=True, mismatch_report_ref=None, event=event)


def _deny_replay_tool_attempts(
    *,
    events: List[Dict[str, Any]],
    event_log: EventLog,
    timestamp: str,
    cwd: str,
) -> int:
    attempts = 0
    for event in events:
        event_type = str(event.get("event_type", "")).strip()
        if event_type not in {"TOOL_CALL", "tool_call"}:
            continue
        attempts += 1
        event_log.append_event(
            {
                "event_type": "TOOL_DENY",
                "timestamp": timestamp,
                "cwd": cwd,
                "tool_name": event.get("tool_name"),
                "deny_reason_code": "UNKNOWN",
                "attempted_action_fingerprint": event.get("attempted_action_fingerprint"),
                "replay_mode": True,
            }
        )
    return attempts


def _compare_decisions_and_emit_divergence(
    *,
    events: List[Dict[str, Any]],
    event_log: EventLog,
    timestamp: str,
    cwd: str,
    replay_id: str,
) -> Tuple[int, int]:
    total_decisions = 0
    divergent_decisions = 0

    for event_type, fields in DECISION_EVENT_TYPES.items():
        matching = [event for event in events if str(event.get("event_type")) == event_type]
        for recorded in matching:
            total_decisions += 1
            replayed = _derive_decision(event_type=event_type, recorded=recorded)
            decision_diverged = False
            for field in fields:
                recorded_value = recorded.get(field)
                replayed_value = replayed.get(field)
                if recorded_value == replayed_value:
                    continue
                decision_diverged = True
                event_log.append_event(
                    {
                        "event_type": "DIVERGENCE_DETECTED",
                        "timestamp": timestamp,
                        "cwd": cwd,
                        "run_id": event_log.run_id,
                        "replay_id": replay_id,
                        "step_id": recorded.get("step_id"),
                        "divergence_type": "decision",
                        "event_type_name": event_type,
                        "decision_event_type": event_type,
                        "field": field,
                        "recorded_value": recorded_value,
                        "replayed_value": replayed_value,
                        "recorded_value_hash": sha256_hex(
                            json.dumps(recorded_value, sort_keys=True, separators=(",", ":")).encode("utf-8")
                        ),
                        "replay_value_hash": sha256_hex(
                            json.dumps(replayed_value, sort_keys=True, separators=(",", ":")).encode("utf-8")
                        ),
                    }
                )
            if decision_diverged:
                divergent_decisions += 1
    return total_decisions, divergent_decisions


def _derive_decision(*, event_type: str, recorded: Dict[str, Any]) -> Dict[str, Any]:
    if event_type == "MODEL_ROUTE_DECISION":
        return {
            "from_model_id": recorded.get("from_model_id"),
            "to_model_id": recorded.get("to_model_id"),
            "signals_hash": recorded.get("signals_hash"),
            "reason_codes": recorded.get("reason_codes"),
        }
    if event_type == "TOOL_DENY":
        return {
            "tool_name": recorded.get("tool_name"),
            "deny_reason_code": recorded.get("deny_reason_code"),
            "attempted_action_fingerprint": recorded.get("attempted_action_fingerprint"),
        }
    if event_type == "VERIFIER_run":
        return {
            "verifier_id": recorded.get("verifier_id"),
            "params_hash": recorded.get("params_hash"),
            "verifier_stage": recorded.get("verifier_stage"),
        }
    return {}


def _verify_hash_chain(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    previous_hash = NULL_EVENT_HASH
    previous_step = None

    for event in events:
        step_id = event.get("step_id")
        event_id = event.get("event_id")
        prev_hash = event.get("prev_event_hash")

        if event_id is None or prev_hash is None:
            return {
                "mismatch_type": "hash_chain_mismatch",
                "expected_hash": previous_hash if prev_hash is not None else None,
                "observed_hash": prev_hash,
                "first_bad_step_id": step_id,
            }

        if prev_hash != previous_hash:
            return {
                "mismatch_type": "hash_chain_mismatch",
                "expected_hash": previous_hash,
                "observed_hash": prev_hash,
                "first_bad_step_id": step_id,
            }

        expected_event_id = compute_event_id(event)
        if event_id != expected_event_id:
            return {
                "mismatch_type": "hash_chain_mismatch",
                "expected_hash": expected_event_id,
                "observed_hash": event_id,
                "first_bad_step_id": step_id,
            }

        if previous_step is not None and step_id is not None and step_id <= previous_step:
            return {
                "mismatch_type": "hash_chain_mismatch",
                "expected_hash": None,
                "observed_hash": None,
                "first_bad_step_id": step_id,
            }

        previous_hash = event_id
        if step_id is not None:
            previous_step = step_id

    return None


def _latest_hashes(events: List[Dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
    context_pack_hash = None
    manifest_hash = None
    for event in events:
        if event.get("context_pack_hash"):
            context_pack_hash = event.get("context_pack_hash")
        if event.get("manifest_hash"):
            manifest_hash = event.get("manifest_hash")
    return context_pack_hash, manifest_hash


def _verify_artifacts(
    events: List[Dict[str, Any]],
    artifact_store: ArtifactStore,
) -> Optional[Dict[str, Any]]:
    for event in events:
        step_id = event.get("step_id")
        refs: List[Any] = []
        refs.extend([event.get("stdout_ref"), event.get("stderr_ref"), event.get("artifact_ref")])
        artifact_refs = event.get("artifact_refs")
        if isinstance(artifact_refs, list):
            refs.extend(artifact_refs)

        for ref in refs:
            if ref is None:
                continue
            if not isinstance(ref, str) or not ref:
                return {
                    "mismatch_type": "missing_artifact",
                    "expected_hash": ref,
                    "observed_hash": None,
                    "first_bad_step_id": step_id,
                }
            try:
                artifact_store.read_bytes(ref)
            except Exception:
                return {
                    "mismatch_type": "missing_artifact",
                    "expected_hash": ref,
                    "observed_hash": None,
                    "first_bad_step_id": step_id,
                }
    return None


def _verify_context_slice_bindings(
    events: List[Dict[str, Any]],
    artifact_store: ArtifactStore,
) -> Optional[Dict[str, Any]]:
    bytes_cache: Dict[str, bytes] = {}
    hash_cache: Dict[str, str] = {}
    json_cache: Dict[str, Dict[str, Any]] = {}
    indexed = list(enumerate(events))
    for idx, event in indexed:
        if event.get("event_type") != "context_slice_bound":
            continue

        step_id = event.get("step_id")
        ref_error = _validate_context_slice_event_refs(event, artifact_store, bytes_cache)
        if ref_error is not None:
            ref_error["first_bad_step_id"] = step_id
            return ref_error

        hash_error = _validate_context_slice_event_hashes(event, artifact_store, bytes_cache, hash_cache)
        if hash_error is not None:
            hash_error["first_bad_step_id"] = step_id
            return hash_error

        payload_error = _validate_context_slice_payload_alignment(event, artifact_store, bytes_cache, json_cache)
        if payload_error is not None:
            payload_error["first_bad_step_id"] = step_id
            return payload_error

        cross_event_error = _validate_context_slice_cross_event_alignment(indexed, idx, event)
        if cross_event_error is not None:
            cross_event_error["first_bad_step_id"] = step_id
            return cross_event_error

    return None


def _validate_context_slice_event_refs(
    event: Dict[str, Any],
    artifact_store: ArtifactStore,
    bytes_cache: Dict[str, bytes],
) -> Optional[Dict[str, Any]]:
    required_refs = {
        "context_pack_ref": event.get("context_pack_ref"),
        "manifest_ref": event.get("manifest_ref"),
        "model_request_ref": event.get("model_request_ref"),
        "context_slice_ref": event.get("context_slice_ref"),
    }
    for field, ref in required_refs.items():
        if not isinstance(ref, str) or not ref:
            return {
                "mismatch_type": "context_slice_binding_mismatch",
                "reason": "context_slice_missing_ref",
                "binding_field": field,
                "expected_hash": ref,
                "observed_hash": None,
            }
        try:
            _artifact_bytes(artifact_store, ref, bytes_cache)
        except Exception:
            return {
                "mismatch_type": "context_slice_binding_mismatch",
                "reason": "missing_ref_artifact",
                "binding_field": field,
                "expected_hash": ref,
                "observed_hash": None,
            }

    return None


def _validate_context_slice_event_hashes(
    event: Dict[str, Any],
    artifact_store: ArtifactStore,
    bytes_cache: Dict[str, bytes],
    hash_cache: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    checks = (
        ("context_pack_ref", "context_pack_hash"),
        ("manifest_ref", "manifest_hash"),
        ("model_request_ref", "model_request_hash"),
    )
    for ref_field, hash_field in checks:
        ref = event.get(ref_field)
        expected_hash = event.get(hash_field)
        if not isinstance(ref, str) or not ref or not isinstance(expected_hash, str) or not expected_hash:
            return {
                "mismatch_type": "context_slice_binding_mismatch",
                "reason": "missing_hash_or_ref",
                "binding_field": hash_field,
                "expected_hash": expected_hash,
                "observed_hash": None,
            }
        observed_hash = _artifact_hash(artifact_store, ref, bytes_cache, hash_cache)
        if observed_hash != expected_hash:
            return {
                "mismatch_type": "context_slice_binding_mismatch",
                "reason": "artifact_hash_mismatch",
                "binding_field": hash_field,
                "expected_hash": expected_hash,
                "observed_hash": observed_hash,
            }
    return None


def _validate_context_slice_payload_alignment(
    event: Dict[str, Any],
    artifact_store: ArtifactStore,
    bytes_cache: Dict[str, bytes],
    json_cache: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    slice_ref = event.get("context_slice_ref")
    if not isinstance(slice_ref, str) or not slice_ref:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "missing_context_slice_ref",
            "binding_field": "context_slice_ref",
            "expected_hash": slice_ref,
            "observed_hash": None,
        }

    try:
        payload = _artifact_json(artifact_store, slice_ref, bytes_cache, json_cache)
    except Exception:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "invalid_context_slice_payload",
            "binding_field": "context_slice_ref",
            "expected_hash": slice_ref,
            "observed_hash": None,
        }

    comparisons = (
        "context_pack_ref",
        "context_pack_hash",
        "manifest_ref",
        "manifest_hash",
        "model_request_ref",
        "model_request_hash",
    )
    for field in comparisons:
        event_value = event.get(field)
        payload_value = payload.get(field)
        if event_value != payload_value:
            return {
                "mismatch_type": "context_slice_binding_mismatch",
                "reason": "event_payload_mismatch",
                "binding_field": field,
                "expected_hash": payload_value,
                "observed_hash": event_value,
            }

    return None


def _artifact_bytes(
    artifact_store: ArtifactStore,
    artifact_id: str,
    bytes_cache: Dict[str, bytes],
) -> bytes:
    cached = bytes_cache.get(artifact_id)
    if cached is not None:
        return cached
    data = artifact_store.read_bytes(artifact_id)
    bytes_cache[artifact_id] = data
    return data


def _artifact_hash(
    artifact_store: ArtifactStore,
    artifact_id: str,
    bytes_cache: Dict[str, bytes],
    hash_cache: Dict[str, str],
) -> str:
    cached = hash_cache.get(artifact_id)
    if cached is not None:
        return cached
    digest = sha256_hex(_artifact_bytes(artifact_store, artifact_id, bytes_cache))
    hash_cache[artifact_id] = digest
    return digest


def _artifact_json(
    artifact_store: ArtifactStore,
    artifact_id: str,
    bytes_cache: Dict[str, bytes],
    json_cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    cached = json_cache.get(artifact_id)
    if cached is not None:
        return cached
    value = json.loads(_artifact_bytes(artifact_store, artifact_id, bytes_cache).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("artifact JSON payload must be an object")
    json_cache[artifact_id] = value
    return value


def _validate_context_slice_cross_event_alignment(
    indexed_events: List[tuple[int, Dict[str, Any]]],
    slice_idx: int,
    context_slice_event: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    model_request_ref = context_slice_event.get("model_request_ref")
    model_request_hash = context_slice_event.get("model_request_hash")

    matching_model_requests: List[tuple[int, Dict[str, Any]]] = []
    for idx, event in indexed_events:
        if event.get("event_type") != "model_request":
            continue
        if event.get("model_request_ref") != model_request_ref:
            continue
        if event.get("model_request_hash") != model_request_hash:
            continue
        matching_model_requests.append((idx, event))

    if not matching_model_requests:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "missing_matching_model_request_event",
            "binding_field": "model_request_ref",
            "expected_hash": model_request_ref,
            "observed_hash": None,
        }

    if not any(idx < slice_idx for idx, _ in matching_model_requests):
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "model_request_event_not_before_context_slice",
            "binding_field": "model_request_ref",
            "expected_hash": model_request_ref,
            "observed_hash": None,
        }

    candidate = max(
        ((idx, event) for idx, event in matching_model_requests if idx < slice_idx),
        key=lambda pair: pair[0],
    )
    model_idx, model_event = candidate

    previous_compiler_event = None
    for idx, event in indexed_events:
        if idx >= model_idx:
            break
        if event.get("event_type") == "context_compiler":
            previous_compiler_event = event

    if previous_compiler_event is None:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "missing_preceding_context_compiler_event",
            "binding_field": "context_compiler",
            "expected_hash": None,
            "observed_hash": None,
        }

    expected_cp_ref = previous_compiler_event.get("context_pack_ref")
    expected_cp_hash = previous_compiler_event.get("context_pack_hash")
    expected_manifest_ref = previous_compiler_event.get("manifest_ref")
    expected_manifest_hash = previous_compiler_event.get("manifest_hash")

    if context_slice_event.get("context_pack_ref") != expected_cp_ref:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "compiler_context_pack_ref_mismatch",
            "binding_field": "context_pack_ref",
            "expected_hash": expected_cp_ref,
            "observed_hash": context_slice_event.get("context_pack_ref"),
        }
    if context_slice_event.get("context_pack_hash") != expected_cp_hash:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "compiler_context_pack_hash_mismatch",
            "binding_field": "context_pack_hash",
            "expected_hash": expected_cp_hash,
            "observed_hash": context_slice_event.get("context_pack_hash"),
        }
    if context_slice_event.get("manifest_ref") != expected_manifest_ref:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "compiler_manifest_ref_mismatch",
            "binding_field": "manifest_ref",
            "expected_hash": expected_manifest_ref,
            "observed_hash": context_slice_event.get("manifest_ref"),
        }
    if context_slice_event.get("manifest_hash") != expected_manifest_hash:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "compiler_manifest_hash_mismatch",
            "binding_field": "manifest_hash",
            "expected_hash": expected_manifest_hash,
            "observed_hash": context_slice_event.get("manifest_hash"),
        }

    # Ensure model_request event itself is bound to the same compiler outputs.
    if model_event.get("context_pack_ref") != expected_cp_ref:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "model_request_context_pack_ref_mismatch",
            "binding_field": "context_pack_ref",
            "expected_hash": expected_cp_ref,
            "observed_hash": model_event.get("context_pack_ref"),
        }
    if model_event.get("context_pack_hash") != expected_cp_hash:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "model_request_context_pack_hash_mismatch",
            "binding_field": "context_pack_hash",
            "expected_hash": expected_cp_hash,
            "observed_hash": model_event.get("context_pack_hash"),
        }
    if model_event.get("manifest_ref") != expected_manifest_ref:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "model_request_manifest_ref_mismatch",
            "binding_field": "manifest_ref",
            "expected_hash": expected_manifest_ref,
            "observed_hash": model_event.get("manifest_ref"),
        }
    if model_event.get("manifest_hash") != expected_manifest_hash:
        return {
            "mismatch_type": "context_slice_binding_mismatch",
            "reason": "model_request_manifest_hash_mismatch",
            "binding_field": "manifest_hash",
            "expected_hash": expected_manifest_hash,
            "observed_hash": model_event.get("manifest_hash"),
        }

    return None


def _fail_replay(
    *,
    event_log: EventLog,
    artifact_store: ArtifactStore,
    mismatch: Dict[str, Any],
    timestamp: str,
    cwd: str,
    replay_id: str,
    total_decisions: int,
    divergent_decisions: int,
    divergence_rate: float,
) -> ReplayOutcome:
    report_artifact, _ = artifact_store.write_json_canonical(mismatch)
    event_log.append_event(
        {
            "event_type": "REPLAY_END",
            "timestamp": timestamp,
            "cwd": cwd,
            "run_id": event_log.run_id,
            "replay_id": replay_id,
            "pass": False,
            "divergence_rate": divergence_rate,
            "total_decisions": total_decisions,
            "divergent_decisions": divergent_decisions,
            "first_divergent_step_id": mismatch.get("first_bad_step_id"),
        }
    )
    event = event_log.append_event(
        {
            "event_type": "replay_gate",
            "timestamp": timestamp,
            "cwd": cwd,
            "termination_reason": "replay_mismatch_detected",
            "artifact_refs": [report_artifact.artifact_id],
            "replay_id": replay_id,
        }
    )
    return ReplayOutcome(ok=False, mismatch_report_ref=report_artifact.artifact_id, event=event)


def _first_step_id(events: List[Dict[str, Any]]) -> Optional[int]:
    if not events:
        return None
    step = events[0].get("step_id")
    return step if isinstance(step, int) else None


def _recorded_policy_hash(events: List[Dict[str, Any]]) -> Optional[str]:
    for event in events:
        if str(event.get("event_type")) not in {"run_START", "run_start"}:
            continue
        policy_hash = event.get("policy_hash")
        if isinstance(policy_hash, str) and policy_hash:
            return policy_hash
    return None
