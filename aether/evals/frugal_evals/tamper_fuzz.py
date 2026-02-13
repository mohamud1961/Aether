from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from aether.evals.utils.events import Event, validate_hash_chain
from aether.evals.utils.hashes import canonical_json_dumps, stable_hash

from .episodes import EpisodeExtractionError, extract_episodes_from_runs
from .ingest import open_harness_run_view

EXPECTED_FAIL_HASH = "FAIL_CLOSED_HASH"
EXPECTED_FAIL_CAS = "FAIL_CLOSED_CAS"
EXPECTED_FAIL_BINDING = "FAIL_CLOSED_BINDING"
ACTUAL_NO_FAIL = "NO_FAIL_CLOSED"

SCHEMA_VERSION = "frugal_tamper_fuzz.v1"


class TamperFuzzError(RuntimeError):
    pass


@dataclass(frozen=True)
class FuzzCaseResult:
    case_id: str
    fuzz_category: str
    mutation_description: str
    expected_outcome: str
    actual_outcome: str
    passed: bool
    evidence_refs: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actual_outcome": self.actual_outcome,
            "case_id": self.case_id,
            "evidence_refs": list(self.evidence_refs),
            "expected_outcome": self.expected_outcome,
            "fuzz_category": self.fuzz_category,
            "mutation_description": self.mutation_description,
            "pass": self.passed,
        }


def run_tamper_fuzz_suite(
    *,
    run_dir: str | Path,
    out_dir: str | Path,
    truncation_events: int = 1,
) -> Dict[str, Any]:
    if truncation_events < 1:
        raise TamperFuzzError("truncation_events must be >= 1")

    source = Path(run_dir)
    view = open_harness_run_view(source)
    baseline_events = view.load_events()
    if len(baseline_events) < 3:
        raise TamperFuzzError("Need at least 3 events for deterministic tamper fuzzing")

    run_id = _extract_run_id(baseline_events, fallback=source.name)
    baseline_event_ids = [event.event_id for event in baseline_events if event.event_id]

    suite_root = Path(out_dir) / f"tamper_fuzz_{run_id}"
    suite_root.mkdir(parents=True, exist_ok=True)

    case_results: List[FuzzCaseResult] = []

    case_results.append(
        _run_case(
            source_run_dir=source,
            case_root=suite_root / "field_mutation",
            case_id="FIELD_MUTATION",
            category="event_field_mutation",
            expected=EXPECTED_FAIL_HASH,
            mutator=lambda case_dir: _mutate_field(case_dir),
            baseline_event_ids=baseline_event_ids,
        )
    )
    case_results.append(
        _run_case(
            source_run_dir=source,
            case_root=suite_root / "event_swap",
            case_id="EVENT_SWAP",
            category="event_swap",
            expected=EXPECTED_FAIL_HASH,
            mutator=lambda case_dir: _mutate_swap_adjacent_events(case_dir),
            baseline_event_ids=baseline_event_ids,
        )
    )
    case_results.append(
        _run_case(
            source_run_dir=source,
            case_root=suite_root / "event_truncation",
            case_id="EVENT_TRUNCATION",
            category="event_truncation",
            expected=EXPECTED_FAIL_BINDING,
            mutator=lambda case_dir: _mutate_truncate_events(case_dir, truncation_events=truncation_events),
            baseline_event_ids=baseline_event_ids,
        )
    )
    case_results.append(
        _run_case(
            source_run_dir=source,
            case_root=suite_root / "cas_corruption",
            case_id="CAS_CORRUPTION",
            category="cas_blob_corruption",
            expected=EXPECTED_FAIL_CAS,
            mutator=lambda case_dir: _mutate_corrupt_blob(case_dir),
            baseline_event_ids=baseline_event_ids,
        )
    )
    case_results.append(
        _run_case(
            source_run_dir=source,
            case_root=suite_root / "cas_deletion",
            case_id="CAS_DELETION",
            category="cas_blob_deletion",
            expected=EXPECTED_FAIL_CAS,
            mutator=lambda case_dir: _mutate_delete_blob(case_dir),
            baseline_event_ids=baseline_event_ids,
        )
    )

    report_payload: Dict[str, Any] = {
        "cases": [item.to_dict() for item in case_results],
        "run_dir": source.resolve().as_posix(),
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "case_count": len(case_results),
            "failed_cases": sum(1 for item in case_results if not item.passed),
            "passed_cases": sum(1 for item in case_results if item.passed),
        },
    }
    report_hash = stable_hash(_normalized_report_payload_for_hash(report_payload))
    report = {**report_payload, "report_hash": report_hash}

    report_path = suite_root / "tamper_fuzz_report.json"
    report_path.write_text(canonical_json_dumps(report) + "\n", encoding="utf-8")

    return {
        "report_hash": report_hash,
        "report_path": report_path.as_posix(),
        "suite_root": suite_root.as_posix(),
        "case_count": len(case_results),
        "passed_cases": report_payload["summary"]["passed_cases"],
    }


def _run_case(
    *,
    source_run_dir: Path,
    case_root: Path,
    case_id: str,
    category: str,
    expected: str,
    mutator: Any,
    baseline_event_ids: Sequence[str],
) -> FuzzCaseResult:
    if case_root.exists():
        shutil.rmtree(case_root)
    shutil.copytree(source_run_dir, case_root)

    mutation_description, mutation_refs = mutator(case_root)
    actual, eval_refs = _evaluate_case(case_root=case_root, baseline_event_ids=baseline_event_ids)
    evidence_refs = [case_root.as_posix(), *mutation_refs, *eval_refs]
    return FuzzCaseResult(
        case_id=case_id,
        fuzz_category=category,
        mutation_description=mutation_description,
        expected_outcome=expected,
        actual_outcome=actual,
        passed=(actual == expected),
        evidence_refs=evidence_refs,
    )


def _events_path(run_dir: Path) -> Path:
    for name in ("event_log.jsonl", "events.jsonl"):
        path = run_dir / name
        if path.exists():
            return path
    raise TamperFuzzError(f"Missing events log in {run_dir}")


def _read_raw_events(run_dir: Path) -> List[Dict[str, Any]]:
    events_path = _events_path(run_dir)
    events: List[Dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise TamperFuzzError(f"Event line is not an object: {events_path}")
        events.append(payload)
    if not events:
        raise TamperFuzzError(f"No events found in {events_path}")
    return events


def _write_raw_events(run_dir: Path, events: Sequence[Mapping[str, Any]]) -> Path:
    events_path = _events_path(run_dir)
    events_path.write_text(
        "\n".join(canonical_json_dumps(dict(event)) for event in events) + "\n",
        encoding="utf-8",
    )
    return events_path


def _mutate_field(run_dir: Path) -> Tuple[str, List[str]]:
    events = _read_raw_events(run_dir)
    protected = {
        "event_id",
        "prev_event_hash",
        "timestamp",
        "cwd",
        "step_id",
        "event_type",
    }

    event_index = -1
    field_name: Optional[str] = None

    preferred_fields = ("tool_name", "exit_code", "run_id")
    for idx, event in enumerate(events):
        for field in preferred_fields:
            if field in event:
                event_index = idx
                field_name = field
                break
        if field_name is not None:
            break

    if field_name is None:
        for idx, event in enumerate(events):
            for key in sorted(event.keys()):
                if key in protected:
                    continue
                if isinstance(event.get(key), (str, int, bool)) or event.get(key) is None:
                    event_index = idx
                    field_name = key
                    break
            if field_name is not None:
                break

    if field_name is None or event_index < 0:
        raise TamperFuzzError("Unable to find deterministic mutable event field")

    target = dict(events[event_index])
    old_value = target.get(field_name)
    target[field_name] = _tampered_scalar(old_value)
    events[event_index] = target

    events_path = _write_raw_events(run_dir, events)
    event_id = str(target.get("event_id", ""))
    description = (
        f"Mutated event field {field_name} for event_id={event_id} "
        f"from {old_value!r} to {target[field_name]!r} without recomputing event_id"
    )
    return description, [events_path.as_posix()]


def _tampered_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if value is None:
        return "tampered"
    return f"{value}__tampered"


def _mutate_swap_adjacent_events(run_dir: Path) -> Tuple[str, List[str]]:
    events = _read_raw_events(run_dir)
    if len(events) < 2:
        raise TamperFuzzError("Need at least 2 events for swap mutation")

    idx = 1 if len(events) > 2 else 0
    first = dict(events[idx])
    second = dict(events[idx + 1])
    events[idx], events[idx + 1] = second, first

    events_path = _write_raw_events(run_dir, events)
    description = (
        f"Swapped adjacent events at indices {idx} and {idx + 1} "
        f"(event_ids={first.get('event_id')}<->{second.get('event_id')})"
    )
    return description, [events_path.as_posix()]


def _mutate_truncate_events(run_dir: Path, *, truncation_events: int) -> Tuple[str, List[str]]:
    events = _read_raw_events(run_dir)
    if truncation_events >= len(events):
        raise TamperFuzzError("truncation_events removes all events; must keep at least one")

    remaining = events[: len(events) - truncation_events]
    removed = events[len(remaining) :]
    events_path = _write_raw_events(run_dir, remaining)
    removed_ids = [str(item.get("event_id", "")) for item in removed]

    description = (
        f"Truncated last {truncation_events} events; removed_event_ids={','.join(removed_ids)}"
    )
    return description, [events_path.as_posix()]


def _mutate_corrupt_blob(run_dir: Path) -> Tuple[str, List[str]]:
    ref, path = _select_artifact_for_mutation(run_dir)
    payload = bytearray(path.read_bytes())
    if not payload:
        payload = bytearray(b"\x00")
    payload[0] ^= 0x01
    path.write_bytes(bytes(payload))
    return (
        f"Corrupted CAS blob by flipping first byte for artifact_ref={ref}",
        [path.as_posix()],
    )


def _mutate_delete_blob(run_dir: Path) -> Tuple[str, List[str]]:
    ref, path = _select_artifact_for_mutation(run_dir)
    path.unlink()
    return (
        f"Deleted CAS blob for referenced artifact_ref={ref}",
        [path.as_posix()],
    )


def _select_artifact_for_mutation(run_dir: Path) -> Tuple[str, Path]:
    refs = _collect_referenced_artifacts(run_dir)
    if not refs:
        raise TamperFuzzError("No referenced artifact refs found for CAS tamper fuzzing")

    cas_roots = [run_dir / "artifacts" / "objects", run_dir / "cas"]
    for ref in refs:
        for root in cas_roots:
            candidate = root / ref
            if candidate.exists() and candidate.is_file():
                return ref, candidate
    raise TamperFuzzError("Referenced artifact refs did not resolve to CAS blob files")


def _collect_referenced_artifacts(run_dir: Path) -> List[str]:
    events = _read_raw_events(run_dir)
    refs: set[str] = set()
    for event in events:
        artifact_refs = event.get("artifact_refs")
        if isinstance(artifact_refs, list):
            for ref in artifact_refs:
                if isinstance(ref, str) and len(ref) == 64:
                    refs.add(ref)

        for key, value in event.items():
            if not key.endswith("_ref"):
                continue
            if isinstance(value, str) and len(value) == 64:
                refs.add(value)

    return sorted(refs)


def _evaluate_case(*, case_root: Path, baseline_event_ids: Sequence[str]) -> Tuple[str, List[str]]:
    events = open_harness_run_view(case_root).load_events()
    hash_ok, first_bad_event_id = validate_hash_chain(events)
    if not hash_ok:
        details = first_bad_event_id or "unknown"
        return EXPECTED_FAIL_HASH, [f"hash_chain_first_bad_event_id:{details}"]

    try:
        extract_episodes_from_runs(case_root)
    except EpisodeExtractionError as exc:
        message = str(exc)
        if _is_cas_failure(message):
            return EXPECTED_FAIL_CAS, [f"episode_extraction_error:{message}"]
        return EXPECTED_FAIL_BINDING, [f"episode_extraction_error:{message}"]

    observed_ids = {event.event_id for event in events if event.event_id}
    missing_ids = [event_id for event_id in baseline_event_ids if event_id not in observed_ids]
    if missing_ids:
        evidence = ",".join(missing_ids[:5])
        return EXPECTED_FAIL_BINDING, [f"missing_expected_event_ids:{evidence}"]

    return ACTUAL_NO_FAIL, []


def _is_cas_failure(message: str) -> bool:
    lowered = message.lower()
    if "missing or unreadable artifact ref" in lowered:
        return True
    if "mismatch for" in lowered and "hash" in lowered:
        return True
    if "artifact for" in lowered:
        return True
    return False


def _extract_run_id(events: Sequence[Event], *, fallback: str) -> str:
    run_ids = sorted(
        {
            str(run_id)
            for run_id in (event.payload.get("run_id") for event in events)
            if isinstance(run_id, str) and run_id
        }
    )
    if not run_ids:
        return fallback
    if len(run_ids) == 1:
        return run_ids[0]
    return "__".join(run_ids)


def _normalized_report_payload_for_hash(payload: Mapping[str, Any]) -> Dict[str, Any]:
    cases_payload = payload.get("cases")
    normalized_cases: List[Dict[str, Any]] = []
    if isinstance(cases_payload, list):
        for case in cases_payload:
            if not isinstance(case, Mapping):
                continue
            normalized_cases.append(
                {
                    "actual_outcome": case.get("actual_outcome"),
                    "case_id": case.get("case_id"),
                    "expected_outcome": case.get("expected_outcome"),
                    "fuzz_category": case.get("fuzz_category"),
                    "mutation_description": case.get("mutation_description"),
                    "pass": bool(case.get("pass")),
                }
            )
    normalized_cases.sort(key=lambda item: str(item.get("case_id", "")))

    return {
        "cases": normalized_cases,
        "run_id": payload.get("run_id"),
        "schema_version": payload.get("schema_version"),
        "summary": payload.get("summary", {}),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run deterministic tamper fuzzing against one harness run")
    parser.add_argument("--run-dir", required=True, help="Path to source harness run directory")
    parser.add_argument("--out-dir", required=True, help="Output directory for fuzz artifacts and report")
    parser.add_argument("--truncate-events", type=int, default=1, help="Number of trailing events to remove")
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = run_tamper_fuzz_suite(
        run_dir=args.run_dir,
        out_dir=args.out_dir,
        truncation_events=int(args.truncate_events),
    )
    print(
        "case_count={case_count} passed_cases={passed_cases} report={report_path} report_hash={report_hash}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
