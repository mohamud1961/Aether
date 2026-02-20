from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from aether.evals.utils.events import canonicalize_event_type, load_events
from aether.evals.utils.hashes import canonical_json_dumps

from .episodes import extract_episodes_from_runs
from .ingest import COMPAT_ALIASES
from .ingest import summarize_harness_run

STRICT_PARSE_SCHEMA_VERSION = "frugal_strict_parse_scan.v2"
INGEST_SCAN_SCHEMA_VERSION = "frugal_ingest_compatibility_scan.v2"
EPISODE_SCAN_SCHEMA_VERSION = "frugal_episode_extraction_scan.v2"
SCAN_BUNDLE_SCHEMA_VERSION = "frugal_run_scan_bundle.v1"


class RunScanError(RuntimeError):
    pass


def run_scan_suite(
    *,
    runs_root: str | Path,
    out_dir: str | Path,
    top_buckets: int = 10,
) -> Dict[str, Any]:
    root = Path(runs_root)
    if not root.exists() or not root.is_dir():
        raise RunScanError(f"runs_root does not exist or is not a directory: {root}")
    if top_buckets < 1:
        raise RunScanError("top_buckets must be >= 1")

    run_dirs = _discover_run_dirs(root)
    if not run_dirs:
        raise RunScanError(f"No telemetry-bearing run directories found under: {root}")

    strict_entries: List[Dict[str, Any]] = []
    ingest_entries: List[Dict[str, Any]] = []
    episode_entries: List[Dict[str, Any]] = []

    strict_buckets: Counter[str] = Counter()
    ingest_buckets: Counter[str] = Counter()
    episode_buckets: Counter[str] = Counter()

    for run_dir in run_dirs:
        strict_entry, strict_bucket = _scan_strict_parse(run_dir)
        strict_entries.append(strict_entry)
        if strict_bucket is not None:
            strict_buckets[strict_bucket] += 1

        ingest_entry, ingest_bucket = _scan_ingest(run_dir)
        ingest_entries.append(ingest_entry)
        if ingest_bucket is not None:
            ingest_buckets[ingest_bucket] += 1

        episode_entry, episode_bucket = _scan_episode_viability(run_dir)
        episode_entries.append(episode_entry)
        if episode_bucket is not None:
            episode_buckets[episode_bucket] += 1

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    strict_path = out_root / "strict_parse_scan.json"
    ingest_path = out_root / "ingest_compatibility_scan.json"
    episode_path = out_root / "episode_extraction_scan.json"
    bundle_path = out_root / "scan_runs_report.json"

    strict_payload = {
        "schema_version": STRICT_PARSE_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "runs_root": root.as_posix(),
        "run_count": len(run_dirs),
        "summary": _build_summary(
            entries=strict_entries,
            error_buckets=strict_buckets,
            ok_field="parsable",
            top_buckets=top_buckets,
        ),
        "entries": strict_entries,
    }
    ingest_payload = {
        "schema_version": INGEST_SCAN_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "runs_root": root.as_posix(),
        "run_count": len(run_dirs),
        "summary": _build_summary(
            entries=ingest_entries,
            error_buckets=ingest_buckets,
            ok_field="ingestable",
            top_buckets=top_buckets,
        ),
        "entries": ingest_entries,
    }
    episode_payload = {
        "schema_version": EPISODE_SCAN_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "runs_root": root.as_posix(),
        "run_count": len(run_dirs),
        "summary": _build_summary(
            entries=episode_entries,
            error_buckets=episode_buckets,
            ok_field="extractable",
            top_buckets=top_buckets,
        ),
        "entries": episode_entries,
    }
    bundle_payload = {
        "schema_version": SCAN_BUNDLE_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "runs_root": root.as_posix(),
        "run_count": len(run_dirs),
        "artifacts": {
            "strict_parse_scan_path": strict_path.as_posix(),
            "ingest_compatibility_scan_path": ingest_path.as_posix(),
            "episode_extraction_scan_path": episode_path.as_posix(),
        },
        "summary": {
            "strict_parse": strict_payload["summary"],
            "ingest_compatibility": ingest_payload["summary"],
            "episode_extraction": episode_payload["summary"],
        },
    }

    _write_json(strict_path, strict_payload)
    _write_json(ingest_path, ingest_payload)
    _write_json(episode_path, episode_payload)
    _write_json(bundle_path, bundle_payload)

    return {
        "runs_root": root.as_posix(),
        "run_count": len(run_dirs),
        "strict_parse_scan_path": strict_path.as_posix(),
        "ingest_compatibility_scan_path": ingest_path.as_posix(),
        "episode_extraction_scan_path": episode_path.as_posix(),
        "scan_runs_report_path": bundle_path.as_posix(),
        "strict_ok_count": int(strict_payload["summary"]["ok_count"]),
        "ingest_ok_count": int(ingest_payload["summary"]["ok_count"]),
        "episode_ok_count": int(episode_payload["summary"]["ok_count"]),
        "internal_exception_count": (
            int(strict_payload["summary"]["internal_exception_count"])
            + int(ingest_payload["summary"]["internal_exception_count"])
            + int(episode_payload["summary"]["internal_exception_count"])
        ),
    }


def _scan_strict_parse(run_dir: Path) -> Tuple[Dict[str, Any], str | None]:
    try:
        events = load_events(run_dir)
        _reject_compat_alias_event_types(events, run_dir=run_dir)
        _require_mandatory_signals(events, required_event_types=("run_START", "run_END"), run_dir=run_dir)
        run_id = _extract_run_id_from_events(events, fallback=run_dir.name)
        return (
            {
                "run_dir": run_dir.as_posix(),
                "name": run_dir.name,
                "run_id": run_id,
                "event_count": len(events),
                "parsable": True,
                "error_code": None,
                "error_message": None,
            },
            None,
        )
    except Exception as exc:
        code, internal = _bucket_exception(exc)
        return (
            {
                "run_dir": run_dir.as_posix(),
                "name": run_dir.name,
                "run_id": None,
                "event_count": 0,
                "parsable": False,
                "error_code": code,
                "error_message": str(exc),
                "internal_exception": internal,
            },
            code,
        )


def _scan_ingest(run_dir: Path) -> Tuple[Dict[str, Any], str | None]:
    try:
        summary = summarize_harness_run(run_dir)
        compat_issues = summary.get("compat_issues", [])
        alias_count = 0
        unknown_count = 0
        if isinstance(compat_issues, list):
            alias_count = sum(1 for issue in compat_issues if isinstance(issue, Mapping) and issue.get("code") == "event_type_compat_alias_applied")
            unknown_count = sum(1 for issue in compat_issues if isinstance(issue, Mapping) and issue.get("code") == "unknown_event_type")

        ingestable = bool(summary.get("hash_chain_ok", False))
        error_code = None if ingestable else "hash_chain_invalid"
        return (
            {
                "run_dir": run_dir.as_posix(),
                "name": run_dir.name,
                "run_id": summary.get("run_id"),
                "event_count": int(summary.get("event_count", 0)),
                "ingestable": ingestable,
                "hash_chain_ok": bool(summary.get("hash_chain_ok", False)),
                "first_bad_event_id": summary.get("first_bad_event_id"),
                "cas_roots": list(summary.get("cas_roots", [])),
                "compat_alias_count": alias_count,
                "unknown_event_type_count": unknown_count,
                "error_code": error_code,
                "error_message": None,
            },
            error_code,
        )
    except Exception as exc:
        code, internal = _bucket_exception(exc)
        return (
            {
                "run_dir": run_dir.as_posix(),
                "name": run_dir.name,
                "run_id": None,
                "event_count": 0,
                "ingestable": False,
                "hash_chain_ok": False,
                "first_bad_event_id": None,
                "cas_roots": [],
                "compat_alias_count": 0,
                "unknown_event_type_count": 0,
                "error_code": code,
                "error_message": str(exc),
                "internal_exception": internal,
            },
            code,
        )


def _scan_episode_viability(run_dir: Path) -> Tuple[Dict[str, Any], str | None]:
    try:
        result = extract_episodes_from_runs(run_dir)
        episodes_extracted = len(result.episodes)
        runs_processed = len(result.run_dirs)
        extractable = episodes_extracted > 0
        error_code = None if extractable else "no_episodes_extracted"
        return (
            {
                "run_dir": run_dir.as_posix(),
                "name": run_dir.name,
                "runs_processed": runs_processed,
                "episodes_extracted": episodes_extracted,
                "extractable": extractable,
                "error_code": error_code,
                "error_message": None,
            },
            error_code,
        )
    except Exception as exc:
        code, internal = _bucket_exception(exc)
        return (
            {
                "run_dir": run_dir.as_posix(),
                "name": run_dir.name,
                "runs_processed": 0,
                "episodes_extracted": 0,
                "extractable": False,
                "error_code": code,
                "error_message": str(exc),
                "internal_exception": internal,
            },
            code,
        )


def _build_summary(
    *,
    entries: Sequence[Mapping[str, Any]],
    error_buckets: Counter[str],
    ok_field: str,
    top_buckets: int,
) -> Dict[str, Any]:
    ok_count = sum(1 for entry in entries if bool(entry.get(ok_field)))
    run_count = len(entries)
    internal_exception_count = sum(1 for entry in entries if bool(entry.get("internal_exception", False)))
    bucket_rows = [
        {"error_code": code, "count": count}
        for code, count in sorted(error_buckets.items(), key=lambda item: (-item[1], item[0]))[:top_buckets]
    ]
    return {
        "run_count": run_count,
        "ok_count": ok_count,
        "error_count": run_count - ok_count,
        "internal_exception_count": internal_exception_count,
        "top_error_buckets": bucket_rows,
    }


def _discover_run_dirs(runs_root: Path) -> List[Path]:
    discovered: set[Path] = set()
    for name in ("event_log.jsonl", "events.jsonl"):
        for event_path in runs_root.rglob(name):
            parent = event_path.parent
            if parent.is_dir():
                discovered.add(parent)
    return sorted(discovered, key=lambda item: item.as_posix())


def _extract_run_id_from_events(events: Sequence[Any], fallback: str) -> str:
    run_ids: set[str] = set()
    for event in events:
        payload = getattr(event, "payload", {})
        if isinstance(payload, Mapping):
            run_id = payload.get("run_id")
            if isinstance(run_id, str) and run_id:
                run_ids.add(run_id)
    if not run_ids:
        return fallback
    if len(run_ids) == 1:
        return next(iter(run_ids))
    return ",".join(sorted(run_ids))


def _bucket_exception(exc: Exception) -> Tuple[str, bool]:
    message = str(exc)
    lowered = message.lower()
    exc_name = exc.__class__.__name__.lower()

    if isinstance(exc, AttributeError):
        return "internal_attribute_error", True
    if "unknown event_type" in lowered:
        return "unknown_event_type", False
    if "missing required event type" in lowered or "missing mandatory signal" in lowered:
        return "missing_mandatory_signal", False
    if "missing required field" in lowered:
        return "missing_required_field", False
    if "missing cas roots" in lowered or "cas object not found" in lowered:
        return "missing_cas_roots", False
    if "hash-chain" in lowered or "hash chain" in lowered:
        return "hash_chain_invalid", False
    if "missing telemetry file" in lowered:
        return "missing_telemetry", False
    if "invalid json" in lowered:
        return "invalid_json", False
    if "filenotfounderror" in exc_name:
        return "file_not_found", False
    if "valueerror" in exc_name:
        return "value_error", False
    return "other_error", False


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json_dumps(dict(payload)) + "\n", encoding="utf-8")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_mandatory_signals(
    events: Sequence[Any],
    *,
    required_event_types: Sequence[str],
    run_dir: Path,
) -> None:
    seen_event_types: set[str] = set()
    for event in events:
        if hasattr(event, "event_type"):
            seen_event_types.add(str(getattr(event, "event_type")))
    missing = [event_type for event_type in required_event_types if event_type not in seen_event_types]
    if missing:
        raise ValueError(
            f"{run_dir}: missing required event type(s): {', '.join(missing)}; missing mandatory signals"
        )


def _reject_compat_alias_event_types(events: Sequence[Any], *, run_dir: Path) -> None:
    for event in events:
        payload = getattr(event, "payload", {})
        if not isinstance(payload, Mapping):
            continue
        raw_event_type = payload.get("event_type")
        if not isinstance(raw_event_type, str) or not raw_event_type.strip():
            continue
        lowered = raw_event_type.strip().lower()
        if lowered not in COMPAT_ALIASES:
            continue

        canonical_event_type = canonicalize_event_type(raw_event_type)
        raise ValueError(
            f"{run_dir}: Unknown event_type in strict parse: {raw_event_type} "
            f"(compat alias for {canonical_event_type})"
        )
