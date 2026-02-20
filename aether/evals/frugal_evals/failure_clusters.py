from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from aether.evals.utils.events import Event, validate_hash_chain
from aether.evals.utils.hashes import canonical_json_dumps, stable_hash

from .context_dump import dump_context_diagnostics
from .episodes import Episode, extract_episodes_from_runs, write_episodes_jsonl
from .ingest import HarnessRunView, open_harness_run_view


RUN_ROOTS: Dict[str, Path] = {
    "claude": Path("runs/phase_3_runs/results/claude/runs"),
    "gemini": Path("runs/phase_3_runs/results/gemini/runs"),
}

REQUIRED_EVENT_FIELDS: Tuple[str, ...] = (
    "run_id",
    "event_type",
    "step_id",
    "timestamp",
    "cwd",
    "event_id",
    "prev_event_hash",
)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ND-1 failure-map forensic pipeline")
    parser.add_argument(
        "--out-root",
        default="runs/eval_output/frugal_evals/nd1",
        help="Output root for ND-1 artifacts",
    )
    return parser.parse_args(argv)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_name_from_run_dir(run_dir_name: str) -> str:
    parts = run_dir_name.rsplit("_", 2)
    if len(parts) == 3 and len(parts[1]) == 8 and len(parts[2]) == 6 and parts[1].isdigit() and parts[2].isdigit():
        return parts[0]
    return run_dir_name


def _discover_target_runs() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for provider, root in sorted(RUN_ROOTS.items()):
        if not root.exists():
            continue
        for run_dir in sorted(root.iterdir(), key=lambda item: item.name):
            if not run_dir.is_dir():
                continue
            if not ((run_dir / "event_log.jsonl").exists() or (run_dir / "events.jsonl").exists()):
                continue
            rows.append(
                {
                    "provider": provider,
                    "run_dir": run_dir.as_posix(),
                    "task_name": _task_name_from_run_dir(run_dir.name),
                    "run_name": run_dir.name,
                }
            )
    return rows


def _event_field_missing(payload: Mapping[str, Any], field: str) -> bool:
    value = payload.get(field)
    if field == "step_id":
        return not isinstance(value, int)
    return not (isinstance(value, str) and bool(value))


def _missing_required_fields(events: Sequence[Event]) -> List[str]:
    missing: set[str] = set()
    for event in events:
        payload = event.payload
        for field in REQUIRED_EVENT_FIELDS:
            if _event_field_missing(payload, field):
                missing.add(field)
    return sorted(missing)


def _scan_run(run_dir: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Event]]:
    view = open_harness_run_view(run_dir)
    events, compat_issues = view.load_events_with_compat_issues()
    run_id: Optional[str] = None
    for event in events:
        if event.event_type != "run_START":
            continue
        value = event.payload.get("run_id")
        if isinstance(value, str) and value:
            run_id = value
            break
    if run_id is None:
        run_ids = sorted(
            {
                value
                for value in (event.payload.get("run_id") for event in events)
                if isinstance(value, str) and value
            }
        )
        run_id = run_ids[0] if run_ids else None
    hash_chain_ok, first_bad_event_id = validate_hash_chain(events)
    missing_fields = _missing_required_fields(events)
    missing_cas_roots = [
        path.as_posix()
        for path in view.artifact_store.cas_roots
        if not (path.exists() and path.is_dir())
    ]
    ingest_status = "ok"
    if not hash_chain_ok or missing_fields:
        ingest_status = "fail_closed"

    note_parts: List[str] = []
    alias_count = sum(1 for item in compat_issues if item.get("code") == "event_type_compat_alias_applied")
    unknown_count = sum(1 for item in compat_issues if item.get("code") == "unknown_event_type")
    if alias_count:
        note_parts.append(f"compat_aliases_applied={alias_count}")
    if unknown_count:
        note_parts.append(f"unknown_event_types={unknown_count}")
    if missing_fields:
        note_parts.append(f"missing_fields={','.join(missing_fields)}")
    if not hash_chain_ok:
        note_parts.append("hash_chain_invalid")
    if missing_cas_roots:
        note_parts.append(f"missing_cas_roots={len(missing_cas_roots)}")

    summary = {
        "run_id": run_id,
        "ingest_status": ingest_status,
        "hash_chain_ok": hash_chain_ok,
        "event_count": len(events),
        "missing_fields": missing_fields,
        "missing_cas_roots": missing_cas_roots,
        "first_bad_event_id": first_bad_event_id,
        "notes": "; ".join(note_parts),
    }
    return summary, compat_issues, events


def _extract_combined_episodes(ingestable_run_dirs: set[str]) -> List[Episode]:
    episodes: List[Episode] = []
    for _, root in sorted(RUN_ROOTS.items()):
        if not root.exists():
            continue
        result = extract_episodes_from_runs(root)
        episodes.extend(ep for ep in result.episodes if ep.run_dir in ingestable_run_dirs)
    return sorted(episodes, key=lambda item: (item.run_id, item.step_id, item.episode_id))


def _last_run_end_event(events: Sequence[Event]) -> Event:
    run_end: Optional[Event] = None
    for event in events:
        if event.event_type == "run_END":
            run_end = event
    if run_end is None:
        return events[-1]
    return run_end


def _derive_terminal_outcome(run_end_payload: Mapping[str, Any]) -> str:
    terminal_raw = str(run_end_payload.get("terminal_outcome", "")).upper()
    if "SUCCESS" in terminal_raw:
        return "SUCCESS"
    if "TIMEOUT" in terminal_raw:
        return "TIMEOUT"
    if "CRASH" in terminal_raw:
        return "CRASH"
    if "FAIL" in terminal_raw:
        return "FAILED"

    termination_reason = str(run_end_payload.get("termination_reason", "")).lower()
    if "timeout" in termination_reason:
        return "TIMEOUT"
    if "crash" in termination_reason:
        return "CRASH"
    if termination_reason in {"success", "done", "completed"}:
        return "SUCCESS"
    if termination_reason in {"fail_state", "failed", "error"}:
        return "FAILED"
    return "FAILED"


def _is_verifier_failure(payload: Mapping[str, Any]) -> bool:
    if payload.get("passed") is False:
        return True
    if payload.get("ok") is False:
        return True
    for key in ("status", "result", "outcome"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip().lower() in {"fail", "failed", "error", "timeout", "crash", "denied"}:
            return True
    verifier_result = payload.get("verifier_result")
    if isinstance(verifier_result, dict):
        if verifier_result.get("passed") is False:
            return True
        value = verifier_result.get("status")
        if isinstance(value, str) and value.strip().lower() in {"fail", "failed", "error"}:
            return True
    exit_code = payload.get("exit_code")
    return isinstance(exit_code, int) and exit_code != 0


def _first_deny_reason(events: Sequence[Event]) -> Optional[str]:
    for event in events:
        if event.event_type != "TOOL_DENY":
            continue
        if event.payload.get("replay_mode") is True:
            continue
        value = event.payload.get("deny_reason_code")
        if isinstance(value, str) and value:
            return value
    return None


def _first_failed_verifier(events: Sequence[Event]) -> Optional[str]:
    for event in events:
        if event.event_type != "VERIFIER_RESULT":
            continue
        if not _is_verifier_failure(event.payload):
            continue
        verifier_id = event.payload.get("verifier_id")
        if isinstance(verifier_id, str) and verifier_id:
            return verifier_id
        return "unknown_verifier"
    return None


def _reanchor_repeat_signature(events: Sequence[Event]) -> Optional[str]:
    pattern_counts: Counter[str] = Counter()
    for event in events:
        if event.event_type != "TOOL_CALL":
            continue
        if event.payload.get("replay_mode") is True:
            continue
        pattern = {
            "tool_name": event.payload.get("tool_name"),
            "tool_args": event.payload.get("tool_args") if isinstance(event.payload.get("tool_args"), dict) else None,
        }
        pattern_counts[stable_hash(pattern)] += 1
    repeated = sorted(signature for signature, count in pattern_counts.items() if count > 1)
    if not repeated:
        return None
    return stable_hash(repeated)


def _cluster_tuple(features: Mapping[str, Any]) -> Tuple[str, str, str, str, str, bool, bool, bool]:
    return (
        str(features.get("terminal_outcome", "FAILED")),
        str(features.get("summary_reason_code") or "none"),
        str(features.get("first_deny_reason_code") or "none"),
        str(features.get("first_failed_verifier_id") or "none"),
        str(features.get("reanchor_repeat_signature") or "none"),
        bool(features.get("contract_digest_missing")),
        bool(features.get("tool_deny_gt5")),
        bool(features.get("retry_gt3")),
    )


def _cluster_label(features: Mapping[str, Any]) -> str:
    if features.get("terminal_outcome") == "TIMEOUT":
        return "timeout_with_denied_progress"
    if features.get("tool_deny_gt5"):
        return "tool_deny_loop_no_progress"
    if features.get("first_deny_reason_code") == "UNKNOWN":
        return "late_unknown_deny_failure"
    if features.get("first_deny_reason_code") == "none":
        return "early_model_failure_no_tool_attempt"
    return "general_failed_state_cluster"


def _cluster_signature_dict(features: Mapping[str, Any]) -> Dict[str, Any]:
    secondary: List[str] = []
    if features.get("summary_reason_code"):
        secondary.append(f"summary_reason_code={features['summary_reason_code']}")
    if features.get("first_deny_reason_code"):
        secondary.append(f"first_deny_reason_code={features['first_deny_reason_code']}")
    if features.get("first_failed_verifier_id"):
        secondary.append(f"first_failed_verifier_id={features['first_failed_verifier_id']}")
    if features.get("reanchor_repeat_signature"):
        secondary.append(f"reanchor_repeat_signature={features['reanchor_repeat_signature']}")
    if features.get("contract_digest_missing"):
        secondary.append("contract_digest_in_context=false")
    if features.get("tool_deny_gt5"):
        secondary.append("tool_deny_count_before>5")
    if features.get("retry_gt3"):
        secondary.append("retry_fingerprint_count>3")
    if not secondary:
        secondary.append("no_secondary_indicators")
    return {
        "terminal_outcome": features.get("terminal_outcome"),
        "primary_indicator": f"summary_reason_code={features.get('summary_reason_code') or 'none'}",
        "secondary_indicators": secondary,
    }


def _validate_evidence_refs(refs: Iterable[str]) -> None:
    event_id_cache: Dict[str, set[str]] = {}
    for ref in refs:
        if "#event:" not in ref:
            raise RuntimeError(f"Invalid evidence ref format: {ref}")
        run_part, event_part = ref.split("#event:", 1)
        event_id = event_part.strip()
        if len(event_id) != 64:
            raise RuntimeError(f"Invalid evidence event_id in ref: {ref}")
        run_dir = Path(run_part)
        if not run_dir.exists():
            raise RuntimeError(f"Evidence run path does not exist: {ref}")
        cache_key = run_dir.as_posix()
        if cache_key not in event_id_cache:
            events_path = run_dir / "event_log.jsonl"
            if not events_path.exists():
                events_path = run_dir / "events.jsonl"
            if not events_path.exists():
                raise RuntimeError(f"Evidence run is missing telemetry file: {ref}")
            known_event_ids: set[str] = set()
            for line in events_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                payload = None
                try:
                    payload = json.loads(stripped)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    value = payload.get("event_id")
                    if isinstance(value, str):
                        known_event_ids.add(value)
            event_id_cache[cache_key] = known_event_ids
        if event_id not in event_id_cache[cache_key]:
            raise RuntimeError(f"Evidence event_id is not present in telemetry: {ref}")


def run_nd1(out_root: str | Path) -> Dict[str, Any]:
    output_root = Path(out_root)
    output_root.mkdir(parents=True, exist_ok=True)

    run_rows = _discover_target_runs()
    sweep_entries: List[Dict[str, Any]] = []
    compat_entries: List[Dict[str, Any]] = []
    events_by_run_dir: Dict[str, List[Event]] = {}
    ingestable_run_dirs: set[str] = set()

    for row in run_rows:
        run_dir = row["run_dir"]
        entry: Dict[str, Any] = dict(row)
        try:
            summary, compat_issues, events = _scan_run(run_dir)
            entry.update(summary)
            events_by_run_dir[run_dir] = events
            if entry["ingest_status"] == "ok":
                ingestable_run_dirs.add(run_dir)
            for issue in compat_issues:
                compat_entries.append(
                    {
                        "run_dir": run_dir,
                        "provider": row["provider"],
                        "task_name": row["task_name"],
                        **issue,
                    }
                )
        except Exception as exc:
            entry.update(
                {
                    "ingest_status": "fail_closed",
                    "hash_chain_ok": False,
                    "event_count": 0,
                    "missing_fields": [],
                    "missing_cas_roots": [],
                    "first_bad_event_id": None,
                    "notes": str(exc),
                }
            )
            compat_entries.append(
                {
                    "run_dir": run_dir,
                    "provider": row["provider"],
                    "task_name": row["task_name"],
                    "code": "ingest_exception",
                    "message": str(exc),
                }
            )
        sweep_entries.append(entry)

    sweep_payload = {
        "schema_version": "frugal_ingest_sweep.v1",
        "generated_at": _now_iso(),
        "entries": sweep_entries,
    }
    (output_root / "ingest_sweep.json").write_text(canonical_json_dumps(sweep_payload) + "\n", encoding="utf-8")

    compat_payload = {
        "schema_version": "frugal_compat_report.v1",
        "generated_at": _now_iso(),
        "incompatibilities": sorted(
            compat_entries,
            key=lambda item: (
                str(item.get("provider", "")),
                str(item.get("task_name", "")),
                str(item.get("run_dir", "")),
                str(item.get("line_no", "")),
                str(item.get("code", "")),
            ),
        ),
    }
    (output_root / "compat_report.json").write_text(canonical_json_dumps(compat_payload) + "\n", encoding="utf-8")

    episodes_first = _extract_combined_episodes(ingestable_run_dirs)
    episodes_second = _extract_combined_episodes(ingestable_run_dirs)
    episode_bytes_first = ("\n".join(canonical_json_dumps(item.to_dict()) for item in episodes_first) + "\n").encode("utf-8")
    episode_bytes_second = ("\n".join(canonical_json_dumps(item.to_dict()) for item in episodes_second) + "\n").encode("utf-8")
    digest_first = hashlib.sha256(episode_bytes_first).hexdigest()
    digest_second = hashlib.sha256(episode_bytes_second).hexdigest()
    if digest_first != digest_second:
        raise RuntimeError("Episode extraction determinism check failed (hash mismatch)")

    episodes_path = output_root / "episodes.jsonl"
    write_episodes_jsonl(episodes_first, episodes_path)
    determinism_payload = {
        "schema_version": "frugal_episode_determinism.v1",
        "generated_at": _now_iso(),
        "episode_count": len(episodes_first),
        "first_hash": digest_first,
        "second_hash": digest_second,
        "hash_match": digest_first == digest_second,
    }
    (output_root / "episode_determinism.json").write_text(
        canonical_json_dumps(determinism_payload) + "\n",
        encoding="utf-8",
    )

    episodes_by_run: Dict[str, List[Episode]] = defaultdict(list)
    for episode in episodes_first:
        episodes_by_run[episode.run_dir].append(episode)

    features_by_run: Dict[str, Dict[str, Any]] = {}
    for row in sweep_entries:
        run_dir = row["run_dir"]
        if row.get("ingest_status") != "ok":
            continue
        events = events_by_run_dir.get(run_dir, [])
        if not events:
            continue
        run_end = _last_run_end_event(events)
        summary_reason_code = run_end.payload.get("summary_reason_code")
        if not isinstance(summary_reason_code, str) or not summary_reason_code:
            summary_reason_code = None

        first_deny_reason_code = _first_deny_reason(events)
        first_failed_verifier_id = _first_failed_verifier(events)
        reanchor_signature = _reanchor_repeat_signature(events)
        run_episodes = episodes_by_run.get(run_dir, [])
        max_tool_deny_before = max((episode.tool_deny_count_before for episode in run_episodes), default=0)
        max_retry = max((episode.retry_fingerprint_count for episode in run_episodes), default=0)
        contract_digest_missing = any(episode.contract_digest_in_context is False for episode in run_episodes)

        features_by_run[run_dir] = {
            "terminal_outcome": _derive_terminal_outcome(run_end.payload),
            "summary_reason_code": summary_reason_code,
            "first_deny_reason_code": first_deny_reason_code,
            "first_failed_verifier_id": first_failed_verifier_id,
            "reanchor_repeat_signature": reanchor_signature,
            "contract_digest_missing": contract_digest_missing,
            "tool_deny_gt5": max_tool_deny_before > 5,
            "retry_gt3": max_retry > 3,
        }

    clusters_by_key: Dict[Tuple[str, str, str, str, str, bool, bool, bool], List[str]] = defaultdict(list)
    for run_dir, features in features_by_run.items():
        key = _cluster_tuple(features)
        clusters_by_key[key].append(run_dir)

    clusters: List[Dict[str, Any]] = []
    for idx, key in enumerate(sorted(clusters_by_key.keys()), start=1):
        cluster_run_dirs = sorted(clusters_by_key[key])
        representative_features = features_by_run[cluster_run_dirs[0]]
        run_ids: List[str] = []
        evidence_refs: List[str] = []
        episode_ids: List[str] = []
        for run_dir in cluster_run_dirs:
            matching_rows = [row for row in sweep_entries if row["run_dir"] == run_dir]
            if not matching_rows:
                continue
            run_id = str(matching_rows[0].get("run_id") or matching_rows[0].get("run_name", run_dir))
            run_ids.append(run_id)
            for episode in episodes_by_run.get(run_dir, []):
                evidence_refs.append(f"{episode.run_dir}#event:{episode.source_event_id}")
                episode_ids.append(episode.episode_id)

        evidence_refs = sorted(set(evidence_refs))
        _validate_evidence_refs(evidence_refs)
        clusters.append(
            {
                "cluster_id": f"cluster_{idx:03d}",
                "label": _cluster_label(representative_features),
                "signature": _cluster_signature_dict(representative_features),
                "run_ids": sorted(run_ids),
                "evidence_refs": evidence_refs,
                "episode_ids": sorted(set(episode_ids)),
            }
        )

    failure_map = {
        "schema_version": "frugal_failure_map.v1",
        "generated_at": _now_iso(),
        "corpus_size": len(sweep_entries),
        "ingestable_count": len(ingestable_run_dirs),
        "clusters": clusters,
    }
    (output_root / "failure_map.json").write_text(canonical_json_dumps(failure_map) + "\n", encoding="utf-8")

    context_root = output_root / "context_forensics"
    context_root.mkdir(parents=True, exist_ok=True)
    context_manifest: List[Dict[str, Any]] = []
    for row in sorted((item for item in sweep_entries if item.get("ingest_status") == "ok"), key=lambda item: item["run_name"]):
        run_dir = row["run_dir"]
        run_name = row["run_name"]
        out_dir = context_root / run_name
        dump_result = dump_context_diagnostics(run_dir, max_steps=3, out_dir=out_dir)
        context_manifest.append(
            {
                "run_name": run_name,
                "run_dir": run_dir,
                "debug_context_path": dump_result["debug_context_path"],
                "context_diagnostic_path": dump_result["context_diagnostic_path"],
                "steps_analyzed": dump_result["steps_analyzed"],
            }
        )
    (output_root / "context_forensics_manifest.json").write_text(
        canonical_json_dumps(
            {
                "schema_version": "frugal_context_forensics_manifest.v1",
                "generated_at": _now_iso(),
                "entries": sorted(context_manifest, key=lambda item: item["run_name"]),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "out_root": output_root.as_posix(),
        "corpus_size": len(sweep_entries),
        "ingestable_count": len(ingestable_run_dirs),
        "cluster_count": len(clusters),
        "episodes_written": len(episodes_first),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result = run_nd1(args.out_root)
    print(
        "out_root={out_root} corpus_size={corpus_size} ingestable_count={ingestable_count} "
        "cluster_count={cluster_count} episodes_written={episodes_written}".format(**result)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
