from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from aether.evals.utils.hashes import canonical_json_dumps, sha256_bytes, stable_hash

from .ingest import HarnessRunView, open_harness_run_view


BOUND_EVENT_TYPE = "CONTEXT_SLICE_BOUND"
TOOL_PATTERN_EVENT_TYPES = {"TOOL_CALL"}
TOOL_DENY_EVENT_TYPE = "TOOL_DENY"
VERIFIER_RESULT_EVENT_TYPE = "VERIFIER_RESULT"
REANCHOR_START_EVENT_TYPE = "REANCHOR_START"
REANCHOR_REPEAT_EVENT_TYPE = "REANCHOR_REPEAT_DETECTED"
PHASE_TRANSITION_EVENT_TYPE = "PHASE_TRANSITION"
PHASE_TRANSITION_DENIED_EVENT_TYPE = "PHASE_TRANSITION_DENIED"
RISK_CLASS_FIELD = "risk_class"
CONTEXT_SLICE_EPISODE_TYPE = "context_slice"

DECISION_EPISODE_TYPE_TOOL_DENY = "decision_tool_deny"
DECISION_EPISODE_TYPE_VERIFIER_FAIL = "decision_verifier_fail"
DECISION_EPISODE_TYPE_REANCHOR = "decision_reanchor"
DECISION_EPISODE_TYPE_REANCHOR_REPEAT = "decision_reanchor_repeat"
DECISION_EPISODE_TYPE_PHASE_DENY = "decision_phase_deny"

DECISION_TRIGGER_PRELUDE_WINDOWS: Dict[str, int] = {
    DECISION_EPISODE_TYPE_TOOL_DENY: 3,
    DECISION_EPISODE_TYPE_VERIFIER_FAIL: 3,
    DECISION_EPISODE_TYPE_REANCHOR: 5,
    DECISION_EPISODE_TYPE_REANCHOR_REPEAT: 5,
    DECISION_EPISODE_TYPE_PHASE_DENY: 3,
}


class EpisodeExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedEvent:
    event_id: str
    event_type: str
    step_id: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class Episode:
    episode_id: str
    run_id: str
    step_id: int
    run_dir: str
    episode_type: str
    source_event_id: str
    source_event_type_raw: str
    prelude_event_ids: List[str]
    context_slice_ref: Optional[str] = None
    context_slice_hash: Optional[str] = None
    context_pack_ref: Optional[str] = None
    context_pack_hash: Optional[str] = None
    manifest_ref: Optional[str] = None
    manifest_hash: Optional[str] = None
    model_request_ref: Optional[str] = None
    model_request_hash: Optional[str] = None
    workspace_fingerprint_hash: Optional[str] = None
    policy_profile_id: Optional[str] = None
    intent_contract_id: Optional[str] = None
    completion_contract_id: Optional[str] = None
    plan_id: Optional[str] = None
    plan_version_id: Optional[str] = None
    context_utilization_pct: Optional[float] = None
    contract_digest_in_context: bool = False
    tool_deny_count_before: int = 0
    retry_fingerprint_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "run_dir": self.run_dir,
            "episode_type": self.episode_type,
            "source_event_id": self.source_event_id,
            "source_event_type_raw": self.source_event_type_raw,
            "prelude_event_ids": list(self.prelude_event_ids),
            "context_slice_ref": self.context_slice_ref,
            "context_slice_hash": self.context_slice_hash,
            "context_pack_ref": self.context_pack_ref,
            "context_pack_hash": self.context_pack_hash,
            "manifest_ref": self.manifest_ref,
            "manifest_hash": self.manifest_hash,
            "model_request_ref": self.model_request_ref,
            "model_request_hash": self.model_request_hash,
            "workspace_fingerprint_hash": self.workspace_fingerprint_hash,
            "policy_profile_id": self.policy_profile_id,
            "intent_contract_id": self.intent_contract_id,
            "completion_contract_id": self.completion_contract_id,
            "plan_id": self.plan_id,
            "plan_version_id": self.plan_version_id,
            "context_utilization_pct": self.context_utilization_pct,
            "contract_digest_in_context": self.contract_digest_in_context,
            "tool_deny_count_before": self.tool_deny_count_before,
            "retry_fingerprint_count": self.retry_fingerprint_count,
        }

    def binding_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "run_id": self.run_id,
            "step_id": self.step_id,
            "episode_type": self.episode_type,
            "source_event_id": self.source_event_id,
        }
        for key, value in (
            ("context_slice_ref", self.context_slice_ref),
            ("context_slice_hash", self.context_slice_hash),
            ("context_pack_ref", self.context_pack_ref),
            ("context_pack_hash", self.context_pack_hash),
            ("manifest_ref", self.manifest_ref),
            ("manifest_hash", self.manifest_hash),
            ("model_request_ref", self.model_request_ref),
            ("model_request_hash", self.model_request_hash),
            ("workspace_fingerprint_hash", self.workspace_fingerprint_hash),
            ("policy_profile_id", self.policy_profile_id),
        ):
            if value is not None:
                payload[key] = value
        if self.prelude_event_ids:
            payload["prelude_event_ids"] = list(self.prelude_event_ids)
        for key, value in (
            ("intent_contract_id", self.intent_contract_id),
            ("completion_contract_id", self.completion_contract_id),
            ("plan_id", self.plan_id),
            ("plan_version_id", self.plan_version_id),
        ):
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class EpisodeIndexEntry:
    episode_id: str
    run_id: str
    step_id: int
    run_dir: str
    episode_type: str
    prelude_event_ids: List[str]
    policy_profile_id: Optional[str]
    event_type_counts_up_to_step: Dict[str, int]
    truncation_flags_present: List[str]
    context_utilization_pct: Optional[float]
    contract_digest_in_context: bool
    tool_deny_count_before: int
    retry_fingerprint_count: int
    risk_class_distribution: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "episode_id": self.episode_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "run_dir": self.run_dir,
            "episode_type": self.episode_type,
            "prelude_event_ids": list(self.prelude_event_ids),
            "policy_profile_id": self.policy_profile_id,
            "event_type_counts_up_to_step": dict(self.event_type_counts_up_to_step),
            "truncation_flags_present": list(self.truncation_flags_present),
            "context_utilization_pct": self.context_utilization_pct,
            "contract_digest_in_context": self.contract_digest_in_context,
            "tool_deny_count_before": self.tool_deny_count_before,
            "retry_fingerprint_count": self.retry_fingerprint_count,
        }
        if self.risk_class_distribution:
            payload["risk_class_distribution"] = dict(self.risk_class_distribution)
        return payload


@dataclass(frozen=True)
class EpisodeExtractionResult:
    episodes: List[Episode]
    index_entries: List[EpisodeIndexEntry]
    run_dirs: List[str]
    risk_class_distribution: Dict[str, int]


def extract_episodes_from_runs(runs_root: str | Path) -> EpisodeExtractionResult:
    root = Path(runs_root)
    if not root.exists() or not root.is_dir():
        raise EpisodeExtractionError(f"runs_root does not exist or is not a directory: {root}")

    run_dirs = _discover_run_dirs(root)
    if not run_dirs:
        raise EpisodeExtractionError(f"No harness run directories found under: {root}")

    episodes: List[Episode] = []
    index_entries: List[EpisodeIndexEntry] = []
    global_risk_counts: Counter[str] = Counter()

    for run_dir in run_dirs:
        view = open_harness_run_view(run_dir)
        run_episodes, run_index_entries, run_risk_counts = _extract_from_run_view(view)
        episodes.extend(run_episodes)
        index_entries.extend(run_index_entries)
        global_risk_counts.update(run_risk_counts)

    ordered_episodes = sorted(episodes, key=lambda item: (item.run_id, item.step_id, item.episode_id))
    index_by_episode = {entry.episode_id: entry for entry in index_entries}
    ordered_index_entries = [index_by_episode[episode.episode_id] for episode in ordered_episodes]

    return EpisodeExtractionResult(
        episodes=ordered_episodes,
        index_entries=ordered_index_entries,
        run_dirs=[run_dir.as_posix() for run_dir in run_dirs],
        risk_class_distribution=dict(sorted(global_risk_counts.items())),
    )


def extract_and_write_episodes(
    *,
    runs_root: str | Path,
    out_path: str | Path,
    index_out_path: str | Path | None = None,
) -> Dict[str, Any]:
    result = extract_episodes_from_runs(runs_root)
    out = Path(out_path)
    index_out = Path(index_out_path) if index_out_path is not None else out.with_name("episode_index.json")

    write_episodes_jsonl(result.episodes, out)
    index_payload = _build_index_payload(
        runs_root=runs_root,
        episodes=result.episodes,
        index_entries=result.index_entries,
        risk_class_distribution=result.risk_class_distribution,
    )
    write_episode_index(index_payload, index_out)

    return {
        "runs_processed": len(result.run_dirs),
        "episodes_written": len(result.episodes),
        "out_path": out.as_posix(),
        "index_out_path": index_out.as_posix(),
    }


def write_episodes_jsonl(episodes: Sequence[Episode], out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        for episode in episodes:
            handle.write(canonical_json_dumps(episode.to_dict()))
            handle.write("\n")


def write_episode_index(index_payload: Mapping[str, Any], out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical_json_dumps(dict(index_payload)) + "\n", encoding="utf-8")


def _build_index_payload(
    *,
    runs_root: str | Path,
    episodes: Sequence[Episode],
    index_entries: Sequence[EpisodeIndexEntry],
    risk_class_distribution: Mapping[str, int],
) -> Dict[str, Any]:
    episodes_by_run: Counter[str] = Counter()
    episodes_by_policy: Counter[str] = Counter()
    truncation_flag_counts: Counter[str] = Counter()

    for episode, entry in zip(episodes, index_entries):
        episodes_by_run[episode.run_id] += 1
        policy_key = episode.policy_profile_id if episode.policy_profile_id is not None else "UNKNOWN_POLICY_PROFILE"
        episodes_by_policy[policy_key] += 1
        for flag in entry.truncation_flags_present:
            truncation_flag_counts[flag] += 1

    summary: Dict[str, Any] = {
        "episodes_by_run": dict(sorted(episodes_by_run.items())),
        "episodes_by_policy_profile": dict(sorted(episodes_by_policy.items())),
        "truncation_flag_counts": dict(sorted(truncation_flag_counts.items())),
    }
    if risk_class_distribution:
        summary["risk_class_distribution"] = dict(sorted(risk_class_distribution.items()))

    return {
        "schema_version": "frugal_episode_index.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs_root": Path(runs_root).as_posix(),
        "episode_count": len(episodes),
        "run_count": len(episodes_by_run),
        "episodes": [entry.to_dict() for entry in index_entries],
        "summary": summary,
    }


def _extract_from_run_view(
    view: HarnessRunView,
) -> Tuple[List[Episode], List[EpisodeIndexEntry], Dict[str, int]]:
    events = _load_events_for_extraction(view)
    episodes: List[Episode] = []
    index_entries: List[EpisodeIndexEntry] = []
    risk_counts: Counter[str] = Counter()

    cumulative_event_counts: Counter[str] = Counter()
    cumulative_truncation_flags: set[str] = set()
    cumulative_risk_distribution: Counter[str] = Counter()
    tool_deny_count_before = 0
    canonical_event_ids: List[str] = []
    seen_context_slice_refs: set[str] = set()
    retry_pattern_counts: Counter[str] = Counter()
    tool_pattern_buffer: List[Dict[str, Any]] = []

    artifact_json_cache: Dict[str, Dict[str, Any]] = {}
    artifact_bytes_cache: Dict[str, bytes] = {}
    contract_digest_cache: Dict[str, bool] = {}
    utilization_cache: Dict[str, Optional[float]] = {}

    for event in events:
        payload = event.payload
        tool_deny_count_before_event = tool_deny_count_before

        cumulative_event_counts[event.event_type] += 1
        cumulative_truncation_flags.update(_extract_truncation_flags(payload))

        risk_class = _optional_identifier(payload.get(RISK_CLASS_FIELD))
        if risk_class is not None:
            normalized_risk = risk_class.upper()
            cumulative_risk_distribution[normalized_risk] += 1
            risk_counts[normalized_risk] += 1

        if event.event_type in TOOL_PATTERN_EVENT_TYPES:
            tool_pattern_buffer.append(_tool_pattern_entry(event))

        episode_type = _episode_type_for_event(event)
        if episode_type is not None and episode_type == CONTEXT_SLICE_EPISODE_TYPE:
            context_slice_ref = _optional_identifier(payload.get("context_slice_ref"))
            if context_slice_ref and context_slice_ref in seen_context_slice_refs:
                episode_type = None

        if episode_type is not None:
            retry_fingerprint_count = _retry_fingerprint_count(
                tool_pattern_buffer,
                retry_pattern_counts,
            )
            prelude_window = DECISION_TRIGGER_PRELUDE_WINDOWS.get(episode_type, 0)
            prelude_event_ids = canonical_event_ids[-prelude_window:] if prelude_window > 0 else []

            episode = _build_episode_from_event(
                view=view,
                event=event,
                episode_type=episode_type,
                prelude_event_ids=prelude_event_ids,
                tool_deny_count_before=tool_deny_count_before_event,
                retry_fingerprint_count=retry_fingerprint_count,
                artifact_json_cache=artifact_json_cache,
                artifact_bytes_cache=artifact_bytes_cache,
                contract_digest_cache=contract_digest_cache,
                utilization_cache=utilization_cache,
            )
            if episode.context_slice_ref is not None:
                seen_context_slice_refs.add(episode.context_slice_ref)
            episodes.append(episode)

            risk_snapshot = dict(sorted(cumulative_risk_distribution.items()))
            index_entries.append(
                EpisodeIndexEntry(
                    episode_id=episode.episode_id,
                    run_id=episode.run_id,
                    step_id=episode.step_id,
                    run_dir=episode.run_dir,
                    episode_type=episode.episode_type,
                    prelude_event_ids=list(episode.prelude_event_ids),
                    policy_profile_id=episode.policy_profile_id,
                    event_type_counts_up_to_step=dict(sorted(cumulative_event_counts.items())),
                    truncation_flags_present=sorted(cumulative_truncation_flags),
                    context_utilization_pct=episode.context_utilization_pct,
                    contract_digest_in_context=episode.contract_digest_in_context,
                    tool_deny_count_before=episode.tool_deny_count_before,
                    retry_fingerprint_count=episode.retry_fingerprint_count,
                    risk_class_distribution=risk_snapshot or None,
                )
            )
            tool_pattern_buffer = []

        if event.event_type == TOOL_DENY_EVENT_TYPE:
            tool_deny_count_before += 1
        canonical_event_ids.append(event.event_id)

    return episodes, index_entries, dict(sorted(risk_counts.items()))


def _episode_type_for_event(event: LoadedEvent) -> Optional[str]:
    if event.event_type == BOUND_EVENT_TYPE:
        return CONTEXT_SLICE_EPISODE_TYPE
    if event.event_type == TOOL_DENY_EVENT_TYPE:
        return DECISION_EPISODE_TYPE_TOOL_DENY
    if event.event_type == VERIFIER_RESULT_EVENT_TYPE and _is_verifier_failure(event.payload):
        return DECISION_EPISODE_TYPE_VERIFIER_FAIL
    if event.event_type == REANCHOR_START_EVENT_TYPE:
        return DECISION_EPISODE_TYPE_REANCHOR
    if event.event_type == REANCHOR_REPEAT_EVENT_TYPE:
        return DECISION_EPISODE_TYPE_REANCHOR_REPEAT
    if _is_phase_transition_denied(event):
        return DECISION_EPISODE_TYPE_PHASE_DENY
    return None


def _is_verifier_failure(payload: Mapping[str, Any]) -> bool:
    if payload.get("passed") is False:
        return True
    if payload.get("ok") is False:
        return True

    for key in ("status", "result", "outcome"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip().lower() in {
            "fail",
            "failed",
            "error",
            "timeout",
            "crash",
            "denied",
        }:
            return True

    verifier_result = payload.get("verifier_result")
    if isinstance(verifier_result, dict):
        if verifier_result.get("passed") is False:
            return True
        status = verifier_result.get("status")
        if isinstance(status, str) and status.strip().lower() in {"fail", "failed", "error"}:
            return True

    exit_code = payload.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    return False


def _is_phase_transition_denied(event: LoadedEvent) -> bool:
    if event.event_type == PHASE_TRANSITION_DENIED_EVENT_TYPE:
        return True
    if event.event_type != PHASE_TRANSITION_EVENT_TYPE:
        return False

    payload = event.payload
    if payload.get("denied") is True:
        return True
    if payload.get("allowed") is False:
        return True
    if _optional_identifier(payload.get("deny_reason_code")) is not None:
        return True
    for key in ("transition_result", "status", "decision", "result"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip().lower() in {"deny", "denied", "blocked", "rejected", "fail"}:
            return True
    return False


def _build_episode_from_event(
    *,
    view: HarnessRunView,
    event: LoadedEvent,
    episode_type: str,
    prelude_event_ids: Sequence[str],
    tool_deny_count_before: int,
    retry_fingerprint_count: int,
    artifact_json_cache: Dict[str, Dict[str, Any]],
    artifact_bytes_cache: Dict[str, bytes],
    contract_digest_cache: Dict[str, bool],
    utilization_cache: Dict[str, Optional[float]],
) -> Episode:
    if episode_type == CONTEXT_SLICE_EPISODE_TYPE:
        return _build_context_slice_episode(
            view=view,
            event=event,
            episode_type=episode_type,
            prelude_event_ids=prelude_event_ids,
            tool_deny_count_before=tool_deny_count_before,
            retry_fingerprint_count=retry_fingerprint_count,
            artifact_json_cache=artifact_json_cache,
            artifact_bytes_cache=artifact_bytes_cache,
            contract_digest_cache=contract_digest_cache,
            utilization_cache=utilization_cache,
        )
    return _build_decision_episode(
        view=view,
        event=event,
        episode_type=episode_type,
        prelude_event_ids=prelude_event_ids,
        tool_deny_count_before=tool_deny_count_before,
        retry_fingerprint_count=retry_fingerprint_count,
        artifact_json_cache=artifact_json_cache,
        artifact_bytes_cache=artifact_bytes_cache,
        contract_digest_cache=contract_digest_cache,
        utilization_cache=utilization_cache,
    )


def _build_context_slice_episode(
    *,
    view: HarnessRunView,
    event: LoadedEvent,
    episode_type: str,
    prelude_event_ids: Sequence[str],
    tool_deny_count_before: int,
    retry_fingerprint_count: int,
    artifact_json_cache: Dict[str, Dict[str, Any]],
    artifact_bytes_cache: Dict[str, bytes],
    contract_digest_cache: Dict[str, bool],
    utilization_cache: Dict[str, Optional[float]],
) -> Episode:
    payload = event.payload
    run_dir = view.run_dir.as_posix()
    step_id = _require_step_id(event)
    run_id = _require_non_empty_str(payload, "run_id", run_dir=run_dir, step_id=step_id)

    context_slice_ref = _require_non_empty_str(payload, "context_slice_ref", run_dir=run_dir, step_id=step_id)
    context_slice_hash = _require_non_empty_str(payload, "context_slice_hash", run_dir=run_dir, step_id=step_id)
    context_pack_ref = _require_non_empty_str(payload, "context_pack_ref", run_dir=run_dir, step_id=step_id)
    context_pack_hash = _require_non_empty_str(payload, "context_pack_hash", run_dir=run_dir, step_id=step_id)
    manifest_ref = _require_non_empty_str(payload, "manifest_ref", run_dir=run_dir, step_id=step_id)
    manifest_hash = _require_non_empty_str(payload, "manifest_hash", run_dir=run_dir, step_id=step_id)
    model_request_ref = _require_non_empty_str(payload, "model_request_ref", run_dir=run_dir, step_id=step_id)
    model_request_hash = _require_non_empty_str(payload, "model_request_hash", run_dir=run_dir, step_id=step_id)

    context_slice_bytes = _read_artifact_bytes(
        view=view,
        ref=context_slice_ref,
        run_dir=run_dir,
        step_id=step_id,
        field="context_slice_ref",
        cache=artifact_bytes_cache,
    )
    _assert_hash_match(
        expected_hash=context_slice_hash,
        observed_bytes=context_slice_bytes,
        run_dir=run_dir,
        step_id=step_id,
        field="context_slice_hash",
    )
    _assert_ref_hash_binding(
        view=view,
        ref=context_pack_ref,
        expected_hash=context_pack_hash,
        run_dir=run_dir,
        step_id=step_id,
        ref_field="context_pack_ref",
        hash_field="context_pack_hash",
        cache=artifact_bytes_cache,
    )
    _assert_ref_hash_binding(
        view=view,
        ref=manifest_ref,
        expected_hash=manifest_hash,
        run_dir=run_dir,
        step_id=step_id,
        ref_field="manifest_ref",
        hash_field="manifest_hash",
        cache=artifact_bytes_cache,
    )
    _assert_ref_hash_binding(
        view=view,
        ref=model_request_ref,
        expected_hash=model_request_hash,
        run_dir=run_dir,
        step_id=step_id,
        ref_field="model_request_ref",
        hash_field="model_request_hash",
        cache=artifact_bytes_cache,
    )

    context_slice_payload = _artifact_json_from_bytes(
        ref=context_slice_ref,
        data=context_slice_bytes,
        run_dir=run_dir,
        step_id=step_id,
        field="context_slice_ref",
        cache=artifact_json_cache,
    )
    _assert_payload_match(
        context_slice_payload,
        payload_value=context_pack_ref,
        payload_field="context_pack_ref",
        run_dir=run_dir,
        step_id=step_id,
    )
    _assert_payload_match(
        context_slice_payload,
        payload_value=context_pack_hash,
        payload_field="context_pack_hash",
        run_dir=run_dir,
        step_id=step_id,
    )
    _assert_payload_match(
        context_slice_payload,
        payload_value=manifest_ref,
        payload_field="manifest_ref",
        run_dir=run_dir,
        step_id=step_id,
    )
    _assert_payload_match(
        context_slice_payload,
        payload_value=manifest_hash,
        payload_field="manifest_hash",
        run_dir=run_dir,
        step_id=step_id,
    )
    _assert_payload_match(
        context_slice_payload,
        payload_value=model_request_ref,
        payload_field="model_request_ref",
        run_dir=run_dir,
        step_id=step_id,
    )
    _assert_payload_match(
        context_slice_payload,
        payload_value=model_request_hash,
        payload_field="model_request_hash",
        run_dir=run_dir,
        step_id=step_id,
    )

    workspace_fingerprint_hash = _coalesce_required_identifier(
        event_value=_optional_identifier(payload.get("workspace_fingerprint_hash")),
        slice_value=_optional_identifier(context_slice_payload.get("workspace_fingerprint_hash")),
        field_name="workspace_fingerprint_hash",
        run_dir=run_dir,
        step_id=step_id,
    )
    policy_profile_id = _coalesce_required_identifier(
        event_value=_optional_identifier(payload.get("policy_profile_id")),
        slice_value=_optional_identifier(context_slice_payload.get("policy_profile_id")),
        field_name="policy_profile_id",
        run_dir=run_dir,
        step_id=step_id,
    )

    completion_contract_id = _coalesce_optional_identifier(
        event_value=_optional_identifier(payload.get("completion_contract_id")),
        slice_value=_optional_identifier(context_slice_payload.get("completion_contract_id")),
        field_name="completion_contract_id",
        run_dir=run_dir,
        step_id=step_id,
    )
    plan_version_id = _coalesce_optional_identifier(
        event_value=_optional_identifier(payload.get("plan_version_id")),
        slice_value=_optional_identifier(context_slice_payload.get("plan_version_id")),
        field_name="plan_version_id",
        run_dir=run_dir,
        step_id=step_id,
    )

    intent_contract_id = _optional_identifier(payload.get("intent_contract_id"))
    plan_id = _optional_identifier(payload.get("plan_id"))

    context_pack_payload = _load_json_artifact(
        view=view,
        ref=context_pack_ref,
        run_dir=run_dir,
        step_id=step_id,
        field="context_pack_ref",
        json_cache=artifact_json_cache,
        bytes_cache=artifact_bytes_cache,
    )
    manifest_payload = _load_json_artifact(
        view=view,
        ref=manifest_ref,
        run_dir=run_dir,
        step_id=step_id,
        field="manifest_ref",
        json_cache=artifact_json_cache,
        bytes_cache=artifact_bytes_cache,
    )

    contract_digest_in_context = _contract_digest_in_context(
        context_pack_ref=context_pack_ref,
        context_pack=context_pack_payload,
        cache=contract_digest_cache,
    )
    context_utilization_pct = _context_utilization_pct(
        manifest_ref=manifest_ref,
        manifest=manifest_payload,
        cache=utilization_cache,
    )

    episode = Episode(
        episode_id="",
        run_id=run_id,
        step_id=step_id,
        run_dir=run_dir,
        episode_type=episode_type,
        source_event_id=event.event_id,
        source_event_type_raw=str(payload.get("event_type", "")),
        prelude_event_ids=list(prelude_event_ids),
        context_slice_ref=context_slice_ref,
        context_slice_hash=context_slice_hash,
        context_pack_ref=context_pack_ref,
        context_pack_hash=context_pack_hash,
        manifest_ref=manifest_ref,
        manifest_hash=manifest_hash,
        model_request_ref=model_request_ref,
        model_request_hash=model_request_hash,
        workspace_fingerprint_hash=workspace_fingerprint_hash,
        policy_profile_id=policy_profile_id,
        intent_contract_id=intent_contract_id,
        completion_contract_id=completion_contract_id,
        plan_id=plan_id,
        plan_version_id=plan_version_id,
        context_utilization_pct=context_utilization_pct,
        contract_digest_in_context=contract_digest_in_context,
        tool_deny_count_before=tool_deny_count_before,
        retry_fingerprint_count=retry_fingerprint_count,
    )
    episode_id = stable_hash(episode.binding_payload())
    return Episode(**{**episode.to_dict(), "episode_id": episode_id})


def _build_decision_episode(
    *,
    view: HarnessRunView,
    event: LoadedEvent,
    episode_type: str,
    prelude_event_ids: Sequence[str],
    tool_deny_count_before: int,
    retry_fingerprint_count: int,
    artifact_json_cache: Dict[str, Dict[str, Any]],
    artifact_bytes_cache: Dict[str, bytes],
    contract_digest_cache: Dict[str, bool],
    utilization_cache: Dict[str, Optional[float]],
) -> Episode:
    payload = event.payload
    run_dir = view.run_dir.as_posix()
    step_id = _require_step_id(event)
    run_id = _require_non_empty_str(payload, "run_id", run_dir=run_dir, step_id=step_id)

    context_slice_ref = _optional_identifier(payload.get("context_slice_ref"))
    context_slice_hash = _optional_identifier(payload.get("context_slice_hash"))
    context_pack_ref = _optional_identifier(payload.get("context_pack_ref"))
    context_pack_hash = _optional_identifier(payload.get("context_pack_hash"))
    manifest_ref = _optional_identifier(payload.get("manifest_ref"))
    manifest_hash = _optional_identifier(payload.get("manifest_hash"))
    model_request_ref = _optional_identifier(payload.get("model_request_ref"))
    model_request_hash = _optional_identifier(payload.get("model_request_hash"))

    if context_slice_ref and context_slice_hash:
        context_slice_bytes = _read_artifact_bytes(
            view=view,
            ref=context_slice_ref,
            run_dir=run_dir,
            step_id=step_id,
            field="context_slice_ref",
            cache=artifact_bytes_cache,
        )
        _assert_hash_match(
            expected_hash=context_slice_hash,
            observed_bytes=context_slice_bytes,
            run_dir=run_dir,
            step_id=step_id,
            field="context_slice_hash",
        )
        context_slice_payload = _artifact_json_from_bytes(
            ref=context_slice_ref,
            data=context_slice_bytes,
            run_dir=run_dir,
            step_id=step_id,
            field="context_slice_ref",
            cache=artifact_json_cache,
        )
    else:
        context_slice_payload = {}

    if context_pack_ref and context_pack_hash:
        _assert_ref_hash_binding(
            view=view,
            ref=context_pack_ref,
            expected_hash=context_pack_hash,
            run_dir=run_dir,
            step_id=step_id,
            ref_field="context_pack_ref",
            hash_field="context_pack_hash",
            cache=artifact_bytes_cache,
        )
    if manifest_ref and manifest_hash:
        _assert_ref_hash_binding(
            view=view,
            ref=manifest_ref,
            expected_hash=manifest_hash,
            run_dir=run_dir,
            step_id=step_id,
            ref_field="manifest_ref",
            hash_field="manifest_hash",
            cache=artifact_bytes_cache,
        )
    if model_request_ref and model_request_hash:
        _assert_ref_hash_binding(
            view=view,
            ref=model_request_ref,
            expected_hash=model_request_hash,
            run_dir=run_dir,
            step_id=step_id,
            ref_field="model_request_ref",
            hash_field="model_request_hash",
            cache=artifact_bytes_cache,
        )

    workspace_fingerprint_hash = _coalesce_optional_identifier(
        event_value=_optional_identifier(payload.get("workspace_fingerprint_hash")),
        slice_value=_optional_identifier(context_slice_payload.get("workspace_fingerprint_hash")),
        field_name="workspace_fingerprint_hash",
        run_dir=run_dir,
        step_id=step_id,
    )
    policy_profile_id = _coalesce_optional_identifier(
        event_value=_optional_identifier(payload.get("policy_profile_id")),
        slice_value=_optional_identifier(context_slice_payload.get("policy_profile_id")),
        field_name="policy_profile_id",
        run_dir=run_dir,
        step_id=step_id,
    )
    completion_contract_id = _coalesce_optional_identifier(
        event_value=_optional_identifier(payload.get("completion_contract_id")),
        slice_value=_optional_identifier(context_slice_payload.get("completion_contract_id")),
        field_name="completion_contract_id",
        run_dir=run_dir,
        step_id=step_id,
    )
    plan_version_id = _coalesce_optional_identifier(
        event_value=_optional_identifier(payload.get("plan_version_id")),
        slice_value=_optional_identifier(context_slice_payload.get("plan_version_id")),
        field_name="plan_version_id",
        run_dir=run_dir,
        step_id=step_id,
    )
    intent_contract_id = _optional_identifier(payload.get("intent_contract_id"))
    plan_id = _optional_identifier(payload.get("plan_id"))

    context_pack_payload = (
        _load_json_artifact(
            view=view,
            ref=context_pack_ref,
            run_dir=run_dir,
            step_id=step_id,
            field="context_pack_ref",
            json_cache=artifact_json_cache,
            bytes_cache=artifact_bytes_cache,
        )
        if context_pack_ref is not None
        else {}
    )
    manifest_payload = (
        _load_json_artifact(
            view=view,
            ref=manifest_ref,
            run_dir=run_dir,
            step_id=step_id,
            field="manifest_ref",
            json_cache=artifact_json_cache,
            bytes_cache=artifact_bytes_cache,
        )
        if manifest_ref is not None
        else {}
    )
    contract_digest_in_context = (
        _contract_digest_in_context(
            context_pack_ref=context_pack_ref,
            context_pack=context_pack_payload,
            cache=contract_digest_cache,
        )
        if context_pack_ref is not None
        else False
    )
    context_utilization_pct = (
        _context_utilization_pct(
            manifest_ref=manifest_ref,
            manifest=manifest_payload,
            cache=utilization_cache,
        )
        if manifest_ref is not None
        else None
    )

    episode = Episode(
        episode_id="",
        run_id=run_id,
        step_id=step_id,
        run_dir=run_dir,
        episode_type=episode_type,
        source_event_id=event.event_id,
        source_event_type_raw=str(payload.get("event_type", "")),
        prelude_event_ids=list(prelude_event_ids),
        context_slice_ref=context_slice_ref,
        context_slice_hash=context_slice_hash,
        context_pack_ref=context_pack_ref,
        context_pack_hash=context_pack_hash,
        manifest_ref=manifest_ref,
        manifest_hash=manifest_hash,
        model_request_ref=model_request_ref,
        model_request_hash=model_request_hash,
        workspace_fingerprint_hash=workspace_fingerprint_hash,
        policy_profile_id=policy_profile_id,
        intent_contract_id=intent_contract_id,
        completion_contract_id=completion_contract_id,
        plan_id=plan_id,
        plan_version_id=plan_version_id,
        context_utilization_pct=context_utilization_pct,
        contract_digest_in_context=contract_digest_in_context,
        tool_deny_count_before=tool_deny_count_before,
        retry_fingerprint_count=retry_fingerprint_count,
    )
    episode_id = stable_hash(episode.binding_payload())
    return Episode(**{**episode.to_dict(), "episode_id": episode_id})


def _discover_run_dirs(runs_root: Path) -> List[Path]:
    if (runs_root / "event_log.jsonl").exists() or (runs_root / "events.jsonl").exists():
        return [runs_root]

    run_dirs: List[Path] = []
    for entry in sorted(runs_root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        if (entry / "event_log.jsonl").exists() or (entry / "events.jsonl").exists():
            run_dirs.append(entry)
    return run_dirs


def _read_artifact_bytes(
    *,
    view: HarnessRunView,
    ref: str,
    run_dir: str,
    step_id: int,
    field: str,
    cache: Dict[str, bytes],
) -> bytes:
    cached = cache.get(ref)
    if cached is not None:
        return cached
    try:
        data = view.artifact_store.read_bytes(ref)
    except Exception as exc:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: missing or unreadable artifact ref for {field}: {ref}"
        ) from exc
    cache[ref] = data
    return data


def _artifact_json_from_bytes(
    *,
    ref: str,
    data: bytes,
    run_dir: str,
    step_id: int,
    field: str,
    cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    cached = cache.get(ref)
    if cached is not None:
        return cached
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: artifact for {field} is not valid JSON object: {ref}"
        ) from exc
    if not isinstance(payload, dict):
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: artifact for {field} must be a JSON object: {ref}"
        )
    cache[ref] = payload
    return payload


def _load_json_artifact(
    *,
    view: HarnessRunView,
    ref: str,
    run_dir: str,
    step_id: int,
    field: str,
    json_cache: Dict[str, Dict[str, Any]],
    bytes_cache: Dict[str, bytes],
) -> Dict[str, Any]:
    data = _read_artifact_bytes(
        view=view,
        ref=ref,
        run_dir=run_dir,
        step_id=step_id,
        field=field,
        cache=bytes_cache,
    )
    return _artifact_json_from_bytes(
        ref=ref,
        data=data,
        run_dir=run_dir,
        step_id=step_id,
        field=field,
        cache=json_cache,
    )


def _assert_hash_match(
    *,
    expected_hash: str,
    observed_bytes: bytes,
    run_dir: str,
    step_id: int,
    field: str,
) -> None:
    observed_hash = sha256_bytes(observed_bytes)
    if observed_hash != expected_hash:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: {field} mismatch. expected={expected_hash} observed={observed_hash}"
        )


def _assert_ref_hash_binding(
    *,
    view: HarnessRunView,
    ref: str,
    expected_hash: str,
    run_dir: str,
    step_id: int,
    ref_field: str,
    hash_field: str,
    cache: Dict[str, bytes],
) -> None:
    data = _read_artifact_bytes(
        view=view,
        ref=ref,
        run_dir=run_dir,
        step_id=step_id,
        field=ref_field,
        cache=cache,
    )
    observed_hash = sha256_bytes(data)
    if observed_hash != expected_hash:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: {hash_field} mismatch for {ref_field}. "
            f"expected={expected_hash} observed={observed_hash}"
        )


def _assert_payload_match(
    payload: Mapping[str, Any],
    *,
    payload_value: str,
    payload_field: str,
    run_dir: str,
    step_id: int,
) -> None:
    observed_value = payload.get(payload_field)
    if observed_value != payload_value:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: context slice payload mismatch for {payload_field}. "
            f"expected={payload_value!r} observed={observed_value!r}"
        )


def _require_non_empty_str(
    payload: Mapping[str, Any],
    field_name: str,
    *,
    run_dir: str,
    step_id: int,
) -> str:
    value = payload.get(field_name)
    if isinstance(value, str) and value:
        return value
    raise EpisodeExtractionError(
        f"{run_dir} step={step_id}: missing required field {field_name}"
    )


def _require_step_id(event: LoadedEvent) -> int:
    if isinstance(event.step_id, int) and event.step_id >= 0:
        return event.step_id
    raise EpisodeExtractionError(
        f"Invalid step_id in event {event.event_id}: {event.step_id!r}"
    )


def _optional_identifier(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _coalesce_required_identifier(
    *,
    event_value: Optional[str],
    slice_value: Optional[str],
    field_name: str,
    run_dir: str,
    step_id: int,
) -> str:
    if event_value and slice_value and event_value != slice_value:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: conflicting {field_name} values "
            f"(event={event_value!r}, context_slice={slice_value!r})"
        )
    value = event_value or slice_value
    if value is None:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: missing required field {field_name}"
        )
    return value


def _coalesce_optional_identifier(
    *,
    event_value: Optional[str],
    slice_value: Optional[str],
    field_name: str,
    run_dir: str,
    step_id: int,
) -> Optional[str]:
    if event_value and slice_value and event_value != slice_value:
        raise EpisodeExtractionError(
            f"{run_dir} step={step_id}: conflicting {field_name} values "
            f"(event={event_value!r}, context_slice={slice_value!r})"
        )
    return event_value or slice_value


def _extract_truncation_flags(payload: Mapping[str, Any]) -> set[str]:
    flags: set[str] = set()
    truncation = payload.get("truncation")
    if isinstance(truncation, dict):
        for stream in ("stdout", "stderr"):
            stream_meta = truncation.get(stream)
            if not isinstance(stream_meta, dict):
                continue
            if stream_meta.get("unknown") is True:
                flags.add(f"{stream.upper()}_UNKNOWN")
            if stream_meta.get("truncated") is True:
                flags.add(f"{stream.upper()}_TRUNCATED")
    raw_flags = payload.get("truncation_flags")
    if isinstance(raw_flags, str) and raw_flags:
        flags.add(raw_flags)
    elif isinstance(raw_flags, list):
        for value in raw_flags:
            if isinstance(value, str) and value:
                flags.add(value)
    return flags


def _tool_pattern_entry(event: LoadedEvent) -> Dict[str, Any]:
    payload = event.payload
    entry: Dict[str, Any] = {
        "event_type": event.event_type,
        "tool_name": _optional_identifier(payload.get("tool_name")),
        "tool_args": payload.get("tool_args") if isinstance(payload.get("tool_args"), dict) else None,
    }
    attempted = _optional_identifier(payload.get("attempted_action_fingerprint"))
    if attempted is not None:
        entry["attempted_action_fingerprint"] = attempted
    return entry


def _retry_fingerprint_count(
    pattern_buffer: Sequence[Dict[str, Any]],
    pattern_counts: Counter[str],
) -> int:
    if not pattern_buffer:
        return 0
    signature = stable_hash(list(pattern_buffer))
    seen_before = pattern_counts[signature]
    pattern_counts[signature] += 1
    return int(seen_before)


def _contract_digest_in_context(
    *,
    context_pack_ref: str,
    context_pack: Mapping[str, Any],
    cache: Dict[str, bool],
) -> bool:
    cached = cache.get(context_pack_ref)
    if cached is not None:
        return cached

    present = False
    for value in context_pack.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            if _is_completion_contract_digest_item(item):
                present = True
                break
        if present:
            break

    cache[context_pack_ref] = present
    return present


def _is_completion_contract_digest_item(item: Mapping[str, Any]) -> bool:
    kind = item.get("kind")
    if isinstance(kind, str) and kind == "completion_contract_digest":
        return True
    source_ref = item.get("source_ref")
    if isinstance(source_ref, str) and (
        source_ref == "completion_contract_digest"
        or source_ref.endswith("/completion_contract_digest")
    ):
        return True
    return False


def _context_utilization_pct(
    *,
    manifest_ref: str,
    manifest: Mapping[str, Any],
    cache: Dict[str, Optional[float]],
) -> Optional[float]:
    if manifest_ref in cache:
        return cache[manifest_ref]

    total = manifest.get("total_tokens_estimate")
    window = manifest.get("context_window_tokens")
    if isinstance(total, (int, float)) and isinstance(window, (int, float)) and window > 0:
        value = round(float(total) / float(window), 6)
    else:
        value = None
    cache[manifest_ref] = value
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract frugal episodes from aether runs")
    parser.add_argument(
        "--runs_root",
        required=True,
        help="Root directory containing harness run directories",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for episodes JSONL",
    )
    parser.add_argument(
        "--index_out",
        default=None,
        help="Optional output path for episode index JSON (default: sibling episode_index.json)",
    )
    return parser


def _load_events_for_extraction(view: HarnessRunView) -> List[LoadedEvent]:
    loaded = view.load_events()
    filtered: List[LoadedEvent] = []
    for event in loaded:
        if event.event_type in {"REPLAY_START", "REPLAY_END"}:
            continue
        if event.payload.get("replay_mode") is True:
            continue
        filtered.append(
            LoadedEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                step_id=event.step_id,
                payload=event.payload,
            )
        )
    return filtered


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        summary = extract_and_write_episodes(
            runs_root=args.runs_root,
            out_path=args.out,
            index_out_path=args.index_out,
        )
    except EpisodeExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        "runs_processed={runs_processed} episodes_written={episodes_written} out={out_path} index={index_out_path}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
