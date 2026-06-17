#!/usr/bin/env python3
"""Observable decision-trace extraction and receipt bundling for HarnessEng.

This is analysis-only. It reconstructs visible action/observation chains from
result rows and actual receipts, but it is not private chain-of-thought and it
does not infer hidden intent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

NON_COT_NOTE = (
    "This is not private chain-of-thought. It is a post-run analysis artifact "
    "derived from visible actions, receipts, and verifier gaps."
)

__all__ = [
    "NON_COT_NOTE",
    "build_and_write_bundle",
    "build_parser",
    "collect_decision_trace_bundle",
    "main",
    "render_summary",
    "summarize_text",
]

_DIRECT_ROW_FILENAMES = (
    "result_rows.jsonl",
    "row.json",
)
_COMBINED_ROW_FILENAMES = (
    "attempt1_rows_combined.jsonl",
    "attempt2_rows_combined.jsonl",
)
_SEED_EVENT_TYPES = {"oriented", "sandbox_started"}
_PRIMARY_ROUTE_EVENT_TYPES = {"model_completion", "raw_bash_result"}
_VERIFICATION_EVENT_TYPES = {"verification_completed"}
_CLOSING_EVENT_TYPES = {"loop_completed", "terminal_outcome_finalized", "score_envelope_ready", "runtime_timing_summary"}

_ATTEMPT_FROM_TEXT_RE = re.compile(r"(?:^|/)(attempt[_-]?(\d+))(?:/|$)")
_COMBINED_MARKER_RE = re.compile(r"^### FILE: (.+)$", flags=re.MULTILINE)

_ACTION_KINDS = (
    ("finalize", re.compile(r"\b(task_done|finalize|complete|done)\b", re.I)),
    ("verify", re.compile(r"\b(pytest|uv\s+run\s+pytest|run-tests\.sh|test_outputs\.py)\b", re.I)),
    ("service_probe", re.compile(r"\b(curl|wget|nc\s+-z|http|browser|screenshot|vnc)\b", re.I)),
    ("inspect", re.compile(r"\b(cat|head|tail|grep|find|ls|sed)\b", re.I)),
    ("install", re.compile(r"\b(apt|apt-get|pip|pip3|npm|yarn|cargo|brew|apk|dnf|yum)\b", re.I)),
    ("build", re.compile(r"\b(make|cmake|gcc|g\+\+|cargo|go\s+test|go\s+build)\b", re.I)),
    ("execute", re.compile(r"\b(python|python3|node|ruby|perl|bash|sh)\b", re.I)),
)

_PASSTHROUGH_METADATA_FIELDS = (
    "persistent_blockers",
    "verifier_suppression_metrics",
    "verifier_suppression",
    "environment_contract_version",
    "environment_contract_digest",
    "environment_contract_ref",
    "reasoning_trace_ref",
)

_REASONING_TRACE_TERMINAL_KINDS = {
    "implicit_stop",
    "task_done",
    "verification_requested",
    "closing",
    "repair_task_done",
    "repair_implicit_stop",
    "repair_rebase_request",
}


def summarize_text(value: Any, *, limit: int = 220) -> str:
    if not isinstance(value, str):
        return ""
    text = value.replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    head = text[: max(0, limit - 24)].rstrip()
    tail = text[-8:].lstrip() if len(text) > 8 else ""
    suffix = f" … [truncated {len(text) - len(head) - len(tail)} chars]"
    return f"{head}{suffix}{tail}"


def _short_json(value: Any, *, limit: int = 4) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        out = [_short_json(item, limit=limit) for item in value[:limit]]
        if len(value) > limit:
            out.append({"truncated_items": len(value) - limit})
        return out
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value.keys())[:limit]:
            out[str(key)] = _short_json(value[key], limit=limit)
        if len(value) > limit:
            out["_truncated_keys"] = len(value) - limit
        return out
    return summarize_text(str(value), limit=120)


def _resolved(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def _read_text(path: Path) -> tuple[str | None, list[str]]:
    try:
        return path.read_text(encoding="utf-8"), []
    except OSError as exc:
        return None, [f"{path}: {type(exc).__name__}: {exc}"]


def _loads_json(text: str, *, source_ref: str) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(text), []
    except json.JSONDecodeError as exc:
        return None, [f"{source_ref}: JSONDecodeError: {exc}"]


def _extract_attempt_ref(row: dict[str, Any], source_ref: str) -> tuple[str | None, str]:
    for key in ("attempt", "attempt_id", "attempt_index", "attempt_number"):
        value = row.get(key)
        if value is None or value == "":
            continue
        return str(value), f"row_field:{key}"
    match = _ATTEMPT_FROM_TEXT_RE.search(source_ref)
    if match:
        return match.group(2), "source_path"
    return None, "absent"


def _infer_run_ref(input_ref: Path, row: dict[str, Any] | None, source_row_ref: str | None = None) -> dict[str, str]:
    run_id = ""
    run_path = ""

    if isinstance(row, dict):
        raw_run_id = row.get("run_id") or row.get("eval_id")
        if isinstance(raw_run_id, str) and raw_run_id:
            run_id = raw_run_id
        raw_run_dir = row.get("run_dir")
        if isinstance(raw_run_dir, str) and raw_run_dir:
            run_path = _resolved(raw_run_dir)
        raw_workspace = row.get("workspace")
        if not run_path and isinstance(raw_workspace, str) and raw_workspace:
            run_path = _resolved(Path(raw_workspace).parent if raw_workspace.endswith("/workspace") else raw_workspace)

    if not run_path and source_row_ref:
        marker_match = _ATTEMPT_FROM_TEXT_RE.search(source_row_ref)
        if marker_match:
            marker_path = Path(source_row_ref)
            run_path = _resolved(marker_path.parent.parent)

    if not run_path:
        if input_ref.is_file() and input_ref.name == "result_rows.jsonl":
            run_path = _resolved(input_ref.parent)
        elif input_ref.is_file() and input_ref.name.endswith("_rows_combined.jsonl"):
            run_path = _resolved(input_ref.parent.parent if input_ref.parent.name == "rows" else input_ref.parent)
        elif input_ref.is_file() and input_ref.name == "row.json":
            run_path = _resolved(input_ref.parent.parent)
        elif input_ref.is_dir():
            run_path = _resolved(input_ref)
        else:
            run_path = _resolved(input_ref.parent)

    if not run_id:
        run_id = Path(run_path).name or Path(input_ref).name

    if source_row_ref and not run_id:
        run_id = Path(source_row_ref).parent.name or Path(source_row_ref).name

    return {"run_id": run_id, "run_path": run_path}


def _parse_combined_rows(text: str, *, source_file: Path) -> list[dict[str, Any]]:
    parts = _COMBINED_MARKER_RE.split(text)
    if len(parts) <= 1:
        return []

    records: list[dict[str, Any]] = []
    iterator = iter(parts[1:])
    for marker, body in zip(iterator, iterator):
        marker = marker.strip()
        body = body.strip()
        row, issues = _loads_json(body, source_ref=marker)
        records.append(
            {
                "row": row if isinstance(row, dict) else None,
                "source_input_ref": _resolved(source_file),
                "source_row_ref": marker,
                "source_kind": "combined_row_file",
                "source_index": len(records),
                "parse_issues": issues,
            }
        )
    return records


def _parse_jsonl_rows(text: str, *, source_file: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        row, issues = _loads_json(stripped, source_ref=f"{source_file}#line:{line_no}")
        records.append(
            {
                "row": row if isinstance(row, dict) else None,
                "source_input_ref": _resolved(source_file),
                "source_row_ref": f"{_resolved(source_file)}#line:{line_no}",
                "source_kind": "result_rows_jsonl",
                "source_index": line_no,
                "parse_issues": issues,
            }
        )
    return records


def _parse_single_row(path: Path) -> list[dict[str, Any]]:
    text, issues = _read_text(path)
    if text is None:
        return [
            {
                "row": None,
                "source_input_ref": _resolved(path),
                "source_row_ref": _resolved(path),
                "source_kind": "row_json",
                "source_index": 0,
                "parse_issues": issues,
            }
        ]
    row, parse_issues = _loads_json(text, source_ref=str(path))
    return [
        {
            "row": row if isinstance(row, dict) else None,
            "source_input_ref": _resolved(path),
            "source_row_ref": _resolved(path),
            "source_kind": "row_json",
            "source_index": 0,
            "parse_issues": issues + parse_issues,
        }
    ]


def _direct_row_sources_for_dir(root: Path) -> list[Path]:
    candidates: list[Path] = []
    if root.name == "rows":
        for filename in _COMBINED_ROW_FILENAMES:
            candidate = root / filename
            if candidate.exists():
                candidates.append(candidate)
        return candidates

    for filename in _DIRECT_ROW_FILENAMES:
        candidate = root / filename
        if candidate.exists():
            candidates.append(candidate)
    for filename in _COMBINED_ROW_FILENAMES:
        candidate = root / "rows" / filename
        if candidate.exists():
            candidates.append(candidate)
    return candidates


def _load_row_records(inputs: Sequence[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for input_path in inputs:
        if input_path.is_dir():
            candidate_files = _direct_row_sources_for_dir(input_path)
            if not candidate_files:
                records.append(
                    {
                        "row": None,
                        "source_input_ref": _resolved(input_path),
                        "source_row_ref": _resolved(input_path),
                        "source_kind": "missing_index",
                        "source_index": 0,
                        "parse_issues": [f"{input_path}: no direct row index file found"],
                    }
                )
                continue
            for candidate in candidate_files:
                records.extend(_load_row_records([candidate]))
            continue

        text, issues = _read_text(input_path)
        if text is None:
            records.append(
                {
                    "row": None,
                    "source_input_ref": _resolved(input_path),
                    "source_row_ref": _resolved(input_path),
                    "source_kind": "missing_file",
                    "source_index": 0,
                    "parse_issues": issues,
                }
            )
            continue

        if input_path.name.endswith(".jsonl"):
            if "### FILE:" in text:
                parsed = _parse_combined_rows(text, source_file=input_path)
                if parsed:
                    records.extend(parsed)
                    continue
            records.extend(_parse_jsonl_rows(text, source_file=input_path))
            continue

        if input_path.name.endswith(".json"):
            records.extend(_parse_single_row(input_path))
            continue

        row, parse_issues = _loads_json(text, source_ref=str(input_path))
        records.append(
            {
                "row": row if isinstance(row, dict) else None,
                "source_input_ref": _resolved(input_path),
                "source_row_ref": _resolved(input_path),
                "source_kind": "unknown",
                "source_index": 0,
                "parse_issues": issues + parse_issues,
            }
        )
    return records


def _extract_embedded_tool_invocations(row: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(row, dict):
        return []
    for outer_key in ("run_result", "loop_result"):
        outer = row.get(outer_key)
        if not isinstance(outer, dict):
            continue
        invocations = outer.get("tool_invocations")
        if isinstance(invocations, list) and invocations:
            return [item for item in invocations if isinstance(item, dict)]
    invocations = row.get("tool_invocations")
    if isinstance(invocations, list):
        return [item for item in invocations if isinstance(item, dict)]
    return []


def _extract_row_discrepancy_reports(row: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(row, dict):
        return []
    for outer_key in ("run_result", "loop_result"):
        outer = row.get(outer_key)
        if isinstance(outer, dict):
            reports = outer.get("discrepancy_reports")
            if isinstance(reports, list):
                return [item for item in reports if isinstance(item, dict)]
    reports = row.get("discrepancy_reports")
    if isinstance(reports, list):
        return [item for item in reports if isinstance(item, dict)]
    return []


def _load_json_receipt(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    text, issues = _read_text(path)
    if text is None:
        return None, issues
    payload, parse_issues = _loads_json(text, source_ref=str(path))
    if isinstance(payload, dict):
        return payload, issues + parse_issues
    return None, issues + parse_issues + [f"{path}: expected a JSON object"]


def _extract_external_receipt_paths(
    row: dict[str, Any] | None,
    row_bundle: dict[str, Any],
    *,
    source_input_ref: str,
    source_row_ref: str,
) -> list[Path]:
    refs: list[str] = []
    inferred_run = _infer_run_ref(Path(source_input_ref), row, source_row_ref)
    inferred_run_path = inferred_run.get("run_path")
    if inferred_run_path:
        run_dir = Path(inferred_run_path)
        for context_path in sorted((run_dir / "verifier_context").glob("*.json")):
            refs.append(str(context_path))
    if isinstance(row, dict):
        for key in ("trace_refs", "artifact_refs"):
            value = row.get(key)
            if isinstance(value, list):
                refs.extend(str(item) for item in value if isinstance(item, (str, Path)) and str(item))
        for key in ("route_trace_ref", "verifier_ref", "grader_ref", "environment_ref", "reasoning_trace_ref", "result_ref"):
            value = row.get(key)
            if isinstance(value, str) and value:
                refs.append(value)
        if isinstance(row.get("artifacts"), str):
            artifact_path = Path(str(row["artifacts"]))
            if artifact_path.is_dir():
                for child_name in (
                    "artifact_bundle.json",
                    "grader_output.json",
                    "verifier_output.json",
                    "environment_contract.json",
                    "environment_manifest.json",
                    "service_evidence.json",
                    "aether2_result.json",
                    "grader_isolation_contract.json",
                ):
                    child = artifact_path / child_name
                    if child.exists():
                        refs.append(str(child))
            elif artifact_path.exists():
                refs.append(str(artifact_path))
        if isinstance(row.get("run_dir"), str):
            run_dir = Path(str(row["run_dir"]))
            for candidate in (
                run_dir / "route_trace" / "run_events.jsonl",
                run_dir / "route_trace" / "run_header.json",
                run_dir / "route_trace" / "score_envelope.json",
            ):
                if candidate.exists():
                    refs.append(str(candidate))
    for entry in row_bundle.get("receipt_bundle", []):
        if isinstance(entry, dict):
            ref = entry.get("receipt_ref")
            if isinstance(ref, str) and ref:
                refs.append(ref.split("#", 1)[0])
    unique: list[Path] = []
    seen: set[str] = set()
    for ref in refs:
        path = Path(ref)
        resolved = _resolved(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _known_json_summary_keys(filename: str) -> tuple[str, ...]:
    if filename == "artifact_bundle.json":
        return ("authority_label", "environment_manifest_ref", "grader_ref", "route_trace_ref", "trace_refs", "verifier_ref")
    if filename == "verifier_output.json":
        return ("benchmark_case_id", "returncode", "reward", "reward_path", "status", "stderr_tail", "stdout_tail")
    if filename == "grader_output.json":
        return ("benchmark_case_id", "failure_class", "reason_codes", "score", "verdict")
    if filename == "environment_manifest.json":
        return ("certification_mode", "container_workspace_path", "initial_cwd", "host_fixture_root")
    if filename == "run_header.json":
        return ("run_id", "task_id", "workspace_root")
    if filename == "score_envelope.json":
        return ("score", "reason_codes", "verdict")
    if filename == "trace.json":
        return ("events", "meta")
    if filename == "reasoning_trace.json":
        return ("schema_version", "step_count", "finalize_reason", "verifier_clean", "steps")
    return ()


def _summarize_json_receipt(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "receipt_ref": _resolved(path),
        "receipt_kind": "json_receipt",
        "receipt_name": path.name,
    }
    for key in _known_json_summary_keys(path.name):
        if key in payload:
            summary[key] = _short_json(payload[key], limit=4)
    if path.name not in {"artifact_bundle.json", "verifier_output.json", "grader_output.json", "environment_manifest.json", "run_header.json", "score_envelope.json", "trace.json"}:
        scalar_keys = [key for key in sorted(payload.keys()) if isinstance(payload[key], (str, int, float, bool))][:6]
        for key in scalar_keys:
            summary[key] = payload[key]
    return summary


def _extract_reasoning_trace_events(
    trace_payload: dict[str, Any] | None,
    *,
    trace_path: Path,
    provenance: dict[str, Any],
    row_gaps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    if not isinstance(trace_payload, dict):
        return [], [], [f"{trace_path}: expected a JSON object reasoning trace payload"]

    steps = trace_payload.get("steps")
    if not isinstance(steps, list):
        return [], [], [f"{trace_path}: reasoning trace missing steps list"]

    receipt_bundle: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    parse_issues: list[str] = []
    previous_observation: dict[str, Any] = {"status": "start_of_run", "note": "no prior observation recorded"}

    for index, step_payload in enumerate(steps):
        if not isinstance(step_payload, dict):
            parse_issues.append(f"{trace_path}: steps[{index}] is not an object")
            continue

        step_no = step_payload.get("step", index + 1)
        visible_context = step_payload.get("visible_context")
        if not isinstance(visible_context, dict):
            visible_context = {}
            parse_issues.append(f"{trace_path}: steps[{index}] missing visible_context object")

        model_exchange_ref = visible_context.get("model_exchange_ref")
        if not isinstance(model_exchange_ref, str) or not model_exchange_ref:
            parse_issues.append(f"{trace_path}: steps[{index}] missing model_exchange_ref")
        else:
            receipt_bundle.append(
                {
                    "receipt_ref": model_exchange_ref,
                    "receipt_kind": "reasoning_trace_model_exchange_ref",
                    "receipt_name": Path(model_exchange_ref).name,
                    "step": step_no,
                    "call_role": step_payload.get("call_role"),
                }
            )

        tool_calls = step_payload.get("tool_calls")
        if not isinstance(tool_calls, list):
            parse_issues.append(f"{trace_path}: steps[{index}] missing tool_calls list")
            tool_calls = []

        if not tool_calls:
            result_observation = {
                "status": step_payload.get("decision_kind") or "no_tool_calls",
                "finalize_reason": step_payload.get("finalize_reason"),
            }
            if step_payload.get("decision_kind") in _REASONING_TRACE_TERMINAL_KINDS:
                events.append(
                    {
                        "step": step_no,
                        "tool_call_index": None,
                        "tool_name": str(step_payload.get("decision_kind") or ""),
                        "visible_action": summarize_text(step_payload.get("assistant_text"), limit=220),
                        "preceding_observation": previous_observation,
                        "resulting_observation": result_observation,
                        "evidence_classification": {
                            "mode": "reasoning_trace",
                            "action_kind": "finalize",
                            "signal_scope": "visible",
                            "result_kind": result_observation["status"],
                            "result_reason_code": step_payload.get("finalize_reason"),
                            "result_exit_code": None,
                            "non_cot": True,
                        },
                        "source_provenance": provenance,
                        "receipt_refs": [str(trace_path)] + ([model_exchange_ref] if isinstance(model_exchange_ref, str) else []),
                    }
                )
                previous_observation = result_observation
            continue

        for tool_call_index, tool_call in enumerate(tool_calls):
            if not isinstance(tool_call, dict):
                parse_issues.append(f"{trace_path}: steps[{index}].tool_calls[{tool_call_index}] is not an object")
                continue
            tool_name = str(tool_call.get("tool_name") or "")
            arguments = tool_call.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}
            observation = tool_call.get("observation")
            if not isinstance(observation, dict):
                observation = {}
                parse_issues.append(
                    f"{trace_path}: steps[{index}].tool_calls[{tool_call_index}] missing observation object"
                )
            raw_log_path = observation.get("raw_log_path")
            receipt_refs = [str(trace_path)]
            if isinstance(model_exchange_ref, str) and model_exchange_ref:
                receipt_refs.append(model_exchange_ref)
            if isinstance(raw_log_path, str) and raw_log_path:
                receipt_refs.append(raw_log_path)
                receipt_bundle.append(
                    {
                        "receipt_ref": raw_log_path,
                        "receipt_kind": "tool_raw_log_ref",
                        "receipt_name": Path(raw_log_path).name,
                        "step": step_no,
                        "tool_name": tool_name,
                    }
                )

            command = ""
            for key in ("command", "cmd", "summary", "path", "session_id", "job_id"):
                value = arguments.get(key)
                if isinstance(value, str) and value:
                    command = value
                    break
            if not command and tool_name:
                command = tool_name

            result_observation = _summarize_embedded_observation(observation)
            event = {
                "step": step_no,
                "tool_call_index": tool_call_index,
                "tool_name": tool_name,
                "visible_action": summarize_text(command, limit=220),
                "preceding_observation": previous_observation,
                "resulting_observation": result_observation,
                "evidence_classification": {
                    "mode": "reasoning_trace",
                    "action_kind": _classify_action_kind(command, tool_name),
                    "signal_scope": "visible",
                    "result_kind": result_observation.get("status") or ("error" if result_observation.get("error") else "observation"),
                    "result_reason_code": (
                        result_observation.get("error", {}).get("reason_code")
                        if isinstance(result_observation.get("error"), dict)
                        else None
                    ),
                    "result_exit_code": result_observation.get("exit_code"),
                    "non_cot": True,
                },
                "source_provenance": provenance,
                "receipt_refs": receipt_refs,
                "call_role": step_payload.get("call_role"),
                "decision_kind": step_payload.get("decision_kind"),
                "model_visible_requirements": _short_json(
                    visible_context.get("model_visible_requirements"),
                    limit=6,
                ),
                "model_input_digests": _short_json(step_payload.get("model_input_digests"), limit=8),
            }
            events.append(event)
            previous_observation = result_observation

    if events:
        events[-1]["unresolved_verifier_gaps"] = row_gaps
    elif steps:
        parse_issues.append(f"{trace_path}: reasoning trace yielded zero visible events")
    return _dedupe_dicts(receipt_bundle), events, parse_issues


def _extract_command_from_tool_invocation(invocation: dict[str, Any]) -> str:
    arguments = invocation.get("arguments")
    if isinstance(arguments, dict):
        for key in ("command", "cmd", "summary", "path"):
            value = arguments.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _extract_command_from_route_details(details: dict[str, Any]) -> str:
    command = details.get("command")
    if isinstance(command, str) and command:
        return command
    normalized = details.get("normalized_payload")
    if isinstance(normalized, dict):
        value = normalized.get("command")
        if isinstance(value, str) and value:
            return value
    raw_payload = details.get("raw_payload")
    if isinstance(raw_payload, dict):
        arguments = raw_payload.get("arguments")
        if isinstance(arguments, dict):
            value = arguments.get("command")
            if isinstance(value, str) and value:
                return value
        value = raw_payload.get("command")
        if isinstance(value, str) and value:
            return value
    tool_calls = details.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        first = tool_calls[0]
        if isinstance(first, dict):
            arguments = first.get("arguments")
            if isinstance(arguments, dict):
                value = arguments.get("command")
                if isinstance(value, str) and value:
                    return value
    return ""


def _classify_action_kind(command: str, tool_name: str | None = None) -> str:
    text = command or ""
    if isinstance(tool_name, str) and tool_name:
        folded = tool_name.casefold()
        if folded in {"task_done", "finalize", "finish"}:
            return "finalize"
    for label, pattern in _ACTION_KINDS:
        if pattern.search(text):
            return label
    return "command"


def _summarize_embedded_observation(envelope: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {"status": "missing_observation"}
    observation: dict[str, Any] = {
        "exit_code": envelope.get("exit_code"),
        "raw_log_path": envelope.get("raw_log_path"),
    }
    for key in ("stdout_head", "stdout_tail", "stderr_head", "stderr_tail"):
        if key in envelope:
            observation[key] = summarize_text(envelope.get(key), limit=160)
    if "files_changed" in envelope:
        observation["files_changed"] = _short_json(envelope.get("files_changed"), limit=4)
    if "process_delta" in envelope:
        observation["process_delta"] = _short_json(envelope.get("process_delta"), limit=4)
    if envelope.get("error") is not None:
        observation["error"] = _short_json(envelope.get("error"), limit=4)
    return observation


def _summarize_route_observation(details: dict[str, Any]) -> dict[str, Any]:
    observation: dict[str, Any] = {}
    for key in (
        "exit_code",
        "result_class",
        "reason_code",
        "signal_attribution_scope",
        "proxy_runtime_signal_detected",
        "proxy_permission_signal_detected",
        "runtime_signal_detected",
        "permission_signal_detected",
        "tool_call_contract_class",
        "verified",
    ):
        if key in details:
            observation[key] = details.get(key)
    if "layer_statuses" in details:
        observation["layer_statuses"] = _short_json(details.get("layer_statuses"), limit=8)
    if "reason_codes" in details:
        observation["reason_codes"] = _short_json(details.get("reason_codes"), limit=8)
    return observation


def _summarize_route_receipt(event: dict[str, Any], *, source_path: Path) -> dict[str, Any]:
    details = event.get("payload", {}).get("details", {})
    if not isinstance(details, dict):
        details = {}
    summary: dict[str, Any] = {
        "receipt_ref": f"{_resolved(source_path)}#seq={event.get('seq')}",
        "receipt_kind": "route_trace_event",
        "seq": event.get("seq"),
        "event_type": event.get("event_type"),
        "phase": event.get("phase"),
        "step": details.get("step"),
    }
    tool_name = details.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        normalized = details.get("normalized_payload")
        if isinstance(normalized, dict):
            tool_name = normalized.get("tool_name") if isinstance(normalized.get("tool_name"), str) else ""
    summary["tool_name"] = tool_name or ""
    command = _extract_command_from_route_details(details)
    if command:
        summary["visible_action"] = summarize_text(command, limit=160)
    if "result_class" in details:
        summary["result_class"] = details.get("result_class")
    if "reason_code" in details:
        summary["reason_code"] = details.get("reason_code")
    if "exit_code" in details:
        summary["exit_code"] = details.get("exit_code")
    if "signal_attribution_scope" in details:
        summary["signal_attribution_scope"] = details.get("signal_attribution_scope")
    if "tool_call_contract_class" in details:
        summary["tool_call_contract_class"] = details.get("tool_call_contract_class")
    if "proxy_runtime_signal_detected" in details:
        summary["proxy_runtime_signal_detected"] = details.get("proxy_runtime_signal_detected")
    if "proxy_permission_signal_detected" in details:
        summary["proxy_permission_signal_detected"] = details.get("proxy_permission_signal_detected")
    if "runtime_signal_detected" in details:
        summary["runtime_signal_detected"] = details.get("runtime_signal_detected")
    if "permission_signal_detected" in details:
        summary["permission_signal_detected"] = details.get("permission_signal_detected")
    if "reason_codes" in details:
        summary["reason_codes"] = _short_json(details.get("reason_codes"), limit=6)
    if "layer_statuses" in details:
        summary["layer_statuses"] = _short_json(details.get("layer_statuses"), limit=6)
    if event.get("event_type") in _VERIFICATION_EVENT_TYPES | _CLOSING_EVENT_TYPES:
        summary["observation"] = _summarize_route_observation(details)
    return summary


def _summarize_embedded_invocation(invocation: dict[str, Any], *, source_ref: str) -> dict[str, Any]:
    envelope = invocation.get("envelope")
    if not isinstance(envelope, dict):
        envelope = {}
    step = invocation.get("step")
    tool_name = invocation.get("tool_name") or invocation.get("tool") or ""
    command = _extract_command_from_tool_invocation(invocation)
    summary: dict[str, Any] = {
        "receipt_ref": f"{source_ref}#tool_invocation:{step}",
        "receipt_kind": "embedded_tool_invocation",
        "step": step,
        "tool_name": tool_name,
        "visible_action": summarize_text(command, limit=160),
        "observation": _summarize_embedded_observation(envelope),
    }
    if isinstance(invocation.get("arguments"), dict):
        summary["arguments"] = _short_json(invocation.get("arguments"), limit=6)
    return summary


def _pair_embedded_invocations(
    invocations: list[dict[str, Any]],
    *,
    provenance: dict[str, Any],
    row_gaps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipt_bundle = [_summarize_embedded_invocation(inv, source_ref=provenance["source_row_ref"]) for inv in invocations]
    events: list[dict[str, Any]] = []
    previous_observation: dict[str, Any] = {"status": "start_of_run", "note": "no prior observation recorded"}
    last_index = len(invocations) - 1
    for index, inv in enumerate(invocations):
        envelope = inv.get("envelope") if isinstance(inv.get("envelope"), dict) else {}
        command = _extract_command_from_tool_invocation(inv)
        observation = _summarize_embedded_observation(envelope)
        tool_name = inv.get("tool_name") or inv.get("tool") or ""
        event = {
            "step": inv.get("step", index),
            "tool_name": tool_name,
            "visible_action": summarize_text(command, limit=220),
            "preceding_observation": previous_observation,
            "resulting_observation": observation,
            "evidence_classification": {
                "mode": "embedded_tool_invocation",
                "action_kind": _classify_action_kind(command, tool_name if isinstance(tool_name, str) else None),
                "signal_scope": "visible" if envelope.get("exit_code") == 0 else "gap",
                "result_kind": "success" if envelope.get("exit_code") == 0 else "nonzero_exit",
                "result_exit_code": envelope.get("exit_code"),
                "non_cot": True,
            },
            "unresolved_verifier_gaps": row_gaps if index == last_index else [],
            "source_provenance": provenance,
            "receipt_refs": [f"{provenance['source_row_ref']}#tool_invocation:{inv.get('step', index)}"],
        }
        events.append(event)
        previous_observation = observation
    return receipt_bundle, events


def _find_route_result_for_step(route_events: list[dict[str, Any]], *, step: Any, tool_call_id: str | None) -> dict[str, Any] | None:
    for event in route_events:
        if event.get("event_type") != "raw_bash_result":
            continue
        details = event.get("payload", {}).get("details", {})
        if not isinstance(details, dict):
            continue
        if details.get("step") != step:
            continue
        raw_payload = details.get("raw_payload")
        if tool_call_id and isinstance(raw_payload, dict):
            raw_id = raw_payload.get("id")
            if isinstance(raw_id, str) and raw_id and raw_id != tool_call_id:
                continue
        return event
    return None


def _route_seed_observation(route_receipts: list[dict[str, Any]]) -> dict[str, Any]:
    seed: dict[str, Any] | None = None
    for receipt in route_receipts:
        event_type = receipt.get("event_type")
        if event_type in _SEED_EVENT_TYPES:
            seed = {
                "receipt_ref": receipt.get("receipt_ref"),
                "event_type": event_type,
                "phase": receipt.get("phase"),
                "observation": receipt.get("observation", {}),
            }
            continue
        break
    return seed or {"status": "start_of_run", "note": "no seed observation receipts recorded"}


def _pair_route_trace_events(
    raw_events: list[dict[str, Any]],
    *,
    source_path: Path,
    provenance: dict[str, Any],
    row_gaps: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipt_bundle = [_summarize_route_receipt(event, source_path=source_path) for event in raw_events]
    seed_observation = _route_seed_observation(receipt_bundle)

    completions_by_step: dict[Any, list[dict[str, Any]]] = {}
    for event in raw_events:
        if event.get("event_type") != "model_completion":
            continue
        details = event.get("payload", {}).get("details", {})
        if not isinstance(details, dict):
            continue
        step = details.get("step")
        completions_by_step.setdefault(step, []).append(event)

    primary_events: list[dict[str, Any]] = []
    previous_observation = seed_observation
    ordered_steps = sorted(
        completions_by_step.keys(),
        key=lambda item: (item is None, item if isinstance(item, (int, float, str)) else str(item)),
    )
    for step in ordered_steps:
        for completion in completions_by_step.get(step, []):
            details = completion.get("payload", {}).get("details", {})
            if not isinstance(details, dict):
                continue
            tool_calls = details.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                continue
            for tool_call_index, tool_call in enumerate(tool_calls):
                if not isinstance(tool_call, dict):
                    continue
                arguments = tool_call.get("arguments")
                if not isinstance(arguments, dict):
                    arguments = {}
                command = arguments.get("command") if isinstance(arguments.get("command"), str) else ""
                tool_name = tool_call.get("name") if isinstance(tool_call.get("name"), str) else ""
                tool_call_id = tool_call.get("id") if isinstance(tool_call.get("id"), str) else None
                result_event = _find_route_result_for_step(raw_events, step=step, tool_call_id=tool_call_id)
                if result_event is None:
                    result_observation: dict[str, Any] = {
                        "status": "missing_result_receipt",
                        "step": step,
                        "tool_call_id": tool_call_id,
                    }
                    result_ref = None
                else:
                    result_details = result_event.get("payload", {}).get("details", {})
                    if not isinstance(result_details, dict):
                        result_details = {}
                    result_observation = _summarize_route_observation(result_details)
                    result_ref = f"{_resolved(source_path)}#seq={result_event.get('seq')}"
                event = {
                    "step": step,
                    "tool_call_index": tool_call_index,
                    "tool_name": tool_name,
                    "visible_action": summarize_text(command, limit=220),
                    "preceding_observation": previous_observation,
                    "resulting_observation": result_observation,
                    "evidence_classification": {
                        "mode": "route_trace",
                        "action_kind": _classify_action_kind(command, tool_name),
                        "signal_scope": result_observation.get("signal_attribution_scope", "unknown")
                        if isinstance(result_observation, dict)
                        else "unknown",
                        "result_kind": result_observation.get("result_class") or result_observation.get("status") or "unknown",
                        "result_reason_code": result_observation.get("reason_code"),
                        "result_exit_code": result_observation.get("exit_code"),
                        "non_cot": True,
                    },
                    "source_provenance": provenance,
                    "receipt_refs": [f"{_resolved(source_path)}#seq={completion.get('seq')}"] + ([result_ref] if result_ref else []),
                }
                primary_events.append(event)
                previous_observation = result_observation

    if primary_events:
        primary_events[-1]["unresolved_verifier_gaps"] = row_gaps
    return receipt_bundle, primary_events


def _extract_verification_gaps_from_route_receipts(route_receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for receipt in route_receipts:
        event_type = receipt.get("event_type")
        if event_type != "verification_completed":
            continue
        observation = receipt.get("observation")
        if not isinstance(observation, dict):
            details = receipt.get("payload", {}).get("details", {})
            observation = details if isinstance(details, dict) else {}
        if isinstance(observation, dict):
            layer_statuses = observation.get("layer_statuses")
            if isinstance(layer_statuses, dict):
                for layer, status in sorted(layer_statuses.items()):
                    if status != "pass":
                        gaps.append({"gap_type": "verification_layer", "layer": layer, "status": status})
            for reason_code in observation.get("reason_codes") or []:
                gaps.append({"gap_type": "verification_reason_code", "reason_code": reason_code})
        if receipt.get("verified") is False:
            gaps.append({"gap_type": "verification_unverified"})
        if receipt.get("verified") is None and event_type == "verification_completed" and not observation.get("verified", True):
            gaps.append({"gap_type": "verification_unverified"})
    return gaps


def _extract_verification_gaps_from_row(row: dict[str, Any] | None) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for report in _extract_row_discrepancy_reports(row):
        requirements = report.get("requirements")
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            verdict = requirement.get("verdict")
            verdict_text = str(verdict).casefold() if verdict is not None else ""
            if verdict_text and verdict_text not in {"pass", "passed", "satisfied", "ok"}:
                gaps.append(
                    {
                        "gap_type": "discrepancy_report",
                        "requirement": requirement.get("requirement"),
                        "verdict": verdict,
                        "evidence": requirement.get("evidence"),
                    }
                )
    return gaps


def _dedupe_dicts(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        marker = json.dumps(item, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(item)
    return deduped


def _collect_passthrough_metadata(*payloads: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for field in _PASSTHROUGH_METADATA_FIELDS:
            value = payload.get(field)
            if value is not None and field not in metadata:
                metadata[field] = value
        for outer_key in ("run_result", "loop_result"):
            outer = payload.get(outer_key)
            if not isinstance(outer, dict):
                continue
            for field in _PASSTHROUGH_METADATA_FIELDS:
                value = outer.get(field)
                if value is not None and field not in metadata:
                    metadata[field] = value
    return metadata


def _build_row_bundle(record: dict[str, Any]) -> dict[str, Any]:
    row = record.get("row") if isinstance(record.get("row"), dict) else None
    source_row_ref = str(record.get("source_row_ref") or record.get("source_input_ref") or "")
    source_input_ref = str(record.get("source_input_ref") or source_row_ref)
    source_run_ref = _infer_run_ref(Path(source_input_ref), row, source_row_ref)
    attempt_ref, attempt_provenance = _extract_attempt_ref(row or {}, source_row_ref)
    provenance = {
        "source_input_ref": source_input_ref,
        "source_row_ref": source_row_ref,
        "source_run_ref": source_run_ref,
        "attempt_ref": attempt_ref,
        "attempt_provenance": attempt_provenance,
        "source_kind": record.get("source_kind"),
    }

    parse_issues = list(record.get("parse_issues") or [])
    row_status = (row or {}).get("row_status") or (row or {}).get("verdict") or (row or {}).get("status")
    verifier_exit_code = (row or {}).get("verifier_exit_code")
    task_id = (row or {}).get("task_id") or (row or {}).get("task_pack_id")
    run_id = (row or {}).get("run_id")
    eval_id = (row or {}).get("eval_id")

    embedded_invocations = _extract_embedded_tool_invocations(row)
    primary_mode = "embedded_tool_invocations" if embedded_invocations else "route_trace_events"
    receipt_bundle: list[dict[str, Any]] = []
    primary_events: list[dict[str, Any]] = []
    route_receipts: list[dict[str, Any]] = []
    reasoning_trace_payload: dict[str, Any] | None = None
    reasoning_trace_path: Path | None = None

    external_receipt_paths = _extract_external_receipt_paths(
        row,
        {"receipt_bundle": []},
        source_input_ref=source_input_ref,
        source_row_ref=source_row_ref,
    )
    external_receipts: list[dict[str, Any]] = []
    external_parse_issues: list[str] = []
    route_trace_source_path: Path | None = None
    verifier_context_invocations: list[dict[str, Any]] = []
    passthrough_metadata = _collect_passthrough_metadata(row)

    for path in external_receipt_paths:
        if not path.exists():
            external_parse_issues.append(f"{path}: missing receipt file")
            continue
        if path.name == "run_events.jsonl":
            route_trace_source_path = path
            text, read_issues = _read_text(path)
            external_parse_issues.extend(read_issues)
            if text is None:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                payload, line_issues = _loads_json(stripped, source_ref=f"{path}#line:{line_no}")
                external_parse_issues.extend(line_issues)
                if isinstance(payload, dict):
                    route_receipts.append(payload)
                    external_receipts.append(_summarize_route_receipt(payload, source_path=path))
            continue

        payload, receipt_issues = _load_json_receipt(path)
        external_parse_issues.extend(receipt_issues)
        if isinstance(payload, dict):
            external_receipts.append(_summarize_json_receipt(path, payload))
            for field, value in _collect_passthrough_metadata(payload).items():
                passthrough_metadata.setdefault(field, value)
            if path.name == "reasoning_trace.json":
                reasoning_trace_payload = payload
                reasoning_trace_path = path
            if path.parent.name == "verifier_context":
                invocations = payload.get("tool_invocations")
                if isinstance(invocations, list):
                    verifier_context_invocations.extend(item for item in invocations if isinstance(item, dict))

    row_gaps = _extract_verification_gaps_from_row(row)

    if embedded_invocations:
        receipt_bundle, primary_events = _pair_embedded_invocations(
            embedded_invocations,
            provenance=provenance,
            row_gaps=row_gaps,
        )
    elif reasoning_trace_payload is not None and reasoning_trace_path is not None:
        receipt_bundle, primary_events, reasoning_parse_issues = _extract_reasoning_trace_events(
            reasoning_trace_payload,
            trace_path=reasoning_trace_path,
            provenance=provenance,
            row_gaps=row_gaps,
        )
        external_parse_issues.extend(reasoning_parse_issues)
        primary_mode = "reasoning_trace_steps"
    elif route_receipts:
        receipt_bundle, primary_events = _pair_route_trace_events(
            route_receipts,
            source_path=route_trace_source_path or Path(source_row_ref),
            provenance=provenance,
            row_gaps=row_gaps,
        )
        row_gaps = _dedupe_dicts(row_gaps + _extract_verification_gaps_from_route_receipts(route_receipts))
    elif verifier_context_invocations:
        receipt_bundle, primary_events = _pair_embedded_invocations(
            verifier_context_invocations,
            provenance=provenance,
            row_gaps=row_gaps,
        )
        primary_mode = "verifier_context_tool_invocations"
    else:
        receipt_bundle = []
        primary_events = []

    if external_receipts:
        receipt_bundle.extend(external_receipts)

    if route_receipts:
        row_gaps = _dedupe_dicts(row_gaps + _extract_verification_gaps_from_route_receipts(route_receipts))

    if not row_gaps and row_status not in (None, "pass", "passed", "ok"):
        row_gaps = [
            {
                "gap_type": "row_status",
                "row_status": row_status,
                "verifier_exit_code": verifier_exit_code,
            }
        ]

    if not row_gaps and verifier_exit_code not in (None, 0):
        row_gaps = [
            {
                "gap_type": "verifier_exit_code",
                "verifier_exit_code": verifier_exit_code,
            }
        ]

    if primary_events:
        primary_events[-1]["unresolved_verifier_gaps"] = row_gaps

    bundle = {
        "bundle_type": "observable_decision_trace",
        "analysis_scope": "post_run_analysis_only",
        "non_cot_note": NON_COT_NOTE,
        "source_input_ref": source_input_ref,
        "source_run_ref": source_run_ref,
        "source_row_ref": source_row_ref,
        "attempt_ref": attempt_ref,
        "attempt_provenance": attempt_provenance,
        "source_kind": record.get("source_kind"),
        "task_id": task_id,
        "run_id": run_id,
        "eval_id": eval_id,
        "row_status": row_status,
        "verifier_exit_code": verifier_exit_code,
        **passthrough_metadata,
        "primary_receipt_mode": primary_mode,
        "receipt_bundle": _dedupe_dicts(receipt_bundle),
        "events": primary_events,
        "unresolved_verifier_gaps": row_gaps,
        "parse_issues": _dedupe_dicts([{"parse_issue": issue} for issue in parse_issues + external_parse_issues]),
    }
    return bundle


def collect_decision_trace_bundle(inputs: Sequence[str | Path]) -> dict[str, Any]:
    input_paths = [Path(item) for item in inputs]
    records = _load_row_records(input_paths)
    row_bundles = [_build_row_bundle(record) for record in records]
    summary = _build_summary(row_bundles)
    return {
        "analysis_scope": "post_run_analysis_only",
        "non_cot_note": NON_COT_NOTE,
        "source_inputs": [_resolved(path) for path in input_paths],
        "rows": row_bundles,
        "summary": summary,
    }


def _build_summary(row_bundles: list[dict[str, Any]]) -> dict[str, Any]:
    row_count = len(row_bundles)
    event_count = sum(len(row.get("events") or []) for row in row_bundles)
    receipt_count = sum(len(row.get("receipt_bundle") or []) for row in row_bundles)
    parse_issue_count = sum(len(row.get("parse_issues") or []) for row in row_bundles)
    gap_count = sum(len(row.get("unresolved_verifier_gaps") or []) for row in row_bundles)
    missing_row_count = sum(
        1
        for row in row_bundles
        if row.get("source_kind") in {"missing_file", "missing_index"}
        or row.get("row_status") == "malformed"
        or row.get("row") is None
    )
    provenance_labels = sorted(
        {
            f"{row.get('source_run_ref', {}).get('run_id') if isinstance(row.get('source_run_ref'), dict) else row.get('source_run_ref')}::{row.get('attempt_provenance')}"
            for row in row_bundles
        }
    )
    evidence_kinds: dict[str, int] = {}
    for row in row_bundles:
        for event in row.get("events") or []:
            cls = event.get("evidence_classification")
            if not isinstance(cls, dict):
                continue
            label = f"{cls.get('mode', 'unknown')}::{cls.get('action_kind', 'unknown')}::{cls.get('signal_scope', 'unknown')}"
            evidence_kinds[label] = evidence_kinds.get(label, 0) + 1
    return {
        "row_count": row_count,
        "event_count": event_count,
        "receipt_count": receipt_count,
        "parse_issue_count": parse_issue_count,
        "unresolved_gap_count": gap_count,
        "missing_row_count": missing_row_count,
        "provenance_labels": provenance_labels,
        "evidence_classifications": dict(sorted(evidence_kinds.items())),
        "non_cot_note": NON_COT_NOTE,
    }


def render_summary(bundle: dict[str, Any]) -> str:
    rows = bundle.get("rows") if isinstance(bundle, dict) else []
    summary = bundle.get("summary") if isinstance(bundle, dict) else {}
    if not isinstance(rows, list):
        rows = []
    if not isinstance(summary, dict):
        summary = {}

    lines: list[str] = []
    lines.append("# Observable Decision Trace Summary")
    lines.append("")
    lines.append(NON_COT_NOTE)
    lines.append("")
    lines.append(f"- Rows: {summary.get('row_count', len(rows))}")
    lines.append(f"- Events: {summary.get('event_count', 0)}")
    lines.append(f"- Receipt bundle items: {summary.get('receipt_count', 0)}")
    lines.append(f"- Parse issues: {summary.get('parse_issue_count', 0)}")
    lines.append(f"- Unresolved verifier gaps: {summary.get('unresolved_gap_count', 0)}")
    lines.append(f"- Missing or malformed rows tolerated: {summary.get('missing_row_count', 0)}")
    lines.append("")
    if summary.get("provenance_labels"):
        lines.append("## Provenance Labels")
        lines.append("")
        for label in summary.get("provenance_labels", []):
            lines.append(f"- {label}")
        lines.append("")
    if summary.get("evidence_classifications"):
        lines.append("## Evidence Classifications")
        lines.append("")
        for label, count in sorted(summary.get("evidence_classifications", {}).items()):
            lines.append(f"- {label}: {count}")
        lines.append("")
    lines.append("## Rows")
    lines.append("")
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_run_ref = row.get("source_run_ref")
        run_label = source_run_ref.get("run_id") if isinstance(source_run_ref, dict) else source_run_ref
        lines.append(f"### {row.get('task_id') or row.get('source_row_ref')}")
        lines.append("")
        lines.append(f"- source_run: `{run_label}`")
        lines.append(f"- attempt: `{row.get('attempt_ref')}`")
        lines.append(f"- attempt_provenance: `{row.get('attempt_provenance')}`")
        lines.append(f"- receipt_mode: `{row.get('primary_receipt_mode')}`")
        lines.append(f"- events: `{len(row.get('events') or [])}`")
        lines.append(f"- receipt_bundle_items: `{len(row.get('receipt_bundle') or [])}`")
        lines.append(f"- unresolved_verifier_gaps: `{len(row.get('unresolved_verifier_gaps') or [])}`")
        lines.append(f"- parse_issues: `{len(row.get('parse_issues') or [])}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_decision_trace_bundle(bundle: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "decision_trace.jsonl"
    summary_path = out_dir / "decision_trace_summary.md"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in bundle.get("rows", []):
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n")
    summary_path.write_text(render_summary(bundle), encoding="utf-8")
    return {"decision_trace_jsonl": _resolved(jsonl_path), "decision_trace_summary": _resolved(summary_path)}


def build_and_write_bundle(inputs: Sequence[str | Path], out_dir: Path) -> dict[str, Any]:
    bundle = collect_decision_trace_bundle(inputs)
    output_files = write_decision_trace_bundle(bundle, out_dir)
    bundle["output_files"] = output_files
    return bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        nargs="+",
        required=True,
        help=(
            "One or more result-row roots or files. Direct index files are used if present "
            "(result_rows.jsonl, row.json, or attempt*_rows_combined.jsonl)."
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory for decision_trace.jsonl and decision_trace_summary.md.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    roots = [Path(item) for item in args.root]
    out_dir = Path(args.out) if args.out else _default_output_dir(roots)
    bundle = build_and_write_bundle(roots, out_dir)
    print(
        json.dumps(
            {
                "row_count": bundle.get("summary", {}).get("row_count", 0),
                "event_count": bundle.get("summary", {}).get("event_count", 0),
                "parse_issue_count": bundle.get("summary", {}).get("parse_issue_count", 0),
                "output_dir": _resolved(out_dir),
                "decision_trace_jsonl": bundle.get("output_files", {}).get("decision_trace_jsonl"),
                "decision_trace_summary": bundle.get("output_files", {}).get("decision_trace_summary"),
            },
            sort_keys=True,
        )
    )
    return 0


def _default_output_dir(roots: Sequence[Path]) -> Path:
    if len(roots) == 1:
        root = roots[0]
        if root.is_dir():
            return root / "decision_trace_bundle"
        return root.parent / "decision_trace_bundle"
    return Path.cwd() / "decision_trace_bundle"


if __name__ == "__main__":
    raise SystemExit(main())
