#!/usr/bin/env python3
"""Replay bounded captured terminal action/result sequences through the real Core loop.

This is a deterministic offline qualification helper. It reads only the exact selected trace and
call-log paths named by ``CORE_REAL_WORLD_REPLAY_CORPUS_V1.json``. Archived commands are never
executed: ``run_scripted`` patches ``Terminals.use`` and both asyncio subprocess APIs. The output
contains source/action/observation digests and counts, never prompt, command, or observation text.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "research/CORE_REAL_WORLD_REPLAY_CORPUS_V1.json"
DEFAULT_ROOT_MAP = Path("/tmp/aether-c1-root-map.json")
DEFAULT_OUT = REPO_ROOT / "research/core_mechanical_qualification_20261025/TERMINAL_SEQUENCE_REPLAY.json"
CORPUS_SHA256 = "4d9cd234683b4f8775774bd2a3cb6a1e96e6c55293c48f670caa38d794321f7d"
MAX_ACTIONS_PER_CASE = 12
EXPECTED_CASES = 15
PROTECTED_TASK_NAMES = ("rolling-shutter", "extract-elf", "make-doom")
SYNTHETIC_ACTION = "synthetic replay action with no host execution"
SYNTHETIC_OBSERVATIONS = (
    "synthetic observation one\n",
    "synthetic observation two\n",
)
BLOCKED_OBSERVATION = "[playback blocked: no exact recorded observation; action not executed]"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_text(value: str) -> str:
    return _sha256(value.encode("utf-8"))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode()


def _module():
    path = Path(__file__).with_name("replay_corpus.py")
    spec = importlib.util.spec_from_file_location("aether_core_replay_corpus", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("REPLAY_CORPUS_MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _protected_cases(cases: list[dict]) -> list[dict]:
    """Check every corpus name before resolving any symbolic archive source."""
    protected = tuple(_normalized_name(name) for name in PROTECTED_TASK_NAMES)
    denied = []
    for case in cases:
        name_fields = (
            str(case.get("archive_case") or ""),
            str(case.get("case_key") or ""),
            str(case.get("source_symbol") or ""),
        )
        if any(token in _normalized_name(value) for value in name_fields for token in protected):
            denied.append(case)
    return denied


def _action_candidates(event: dict, replay: Any) -> tuple[list[tuple[str, dict]], str]:
    actions, protocol = replay.selected_actions(event)
    return [(name, args if isinstance(args, dict) else {}) for name, args in actions], protocol


def _terminal_pairs_for_case(case: dict, root_map: dict, replay: Any) -> dict:
    path, reason = replay.resolve_symbol(case["source_symbol"], root_map)
    if path is None:
        return {"status": "UNAVAILABLE", "reason": reason, "pairs": []}
    call_path = path.with_name("core_calls.jsonl")
    if call_path.is_symlink() or not call_path.is_file():
        return {"status": "UNAVAILABLE", "reason": "CALL_LOG_UNAVAILABLE", "pairs": []}

    trace_raw = path.read_bytes()
    calls_raw = call_path.read_bytes()
    expected = case.get("expected") or {}
    observed_trace_sha = _sha256(trace_raw)
    observed_calls_sha = _sha256(calls_raw)
    if observed_trace_sha != expected.get("trace_sha256"):
        return {
            "status": "FAIL",
            "reason": "TRACE_DIGEST_MISMATCH",
            "pairs": [],
            "trace_sha256": observed_trace_sha,
            "call_log_sha256": observed_calls_sha,
        }
    if observed_calls_sha != expected.get("client_calls_sha256"):
        return {
            "status": "FAIL",
            "reason": "CALL_LOG_DIGEST_MISMATCH",
            "pairs": [],
            "trace_sha256": observed_trace_sha,
            "call_log_sha256": observed_calls_sha,
        }

    events, malformed_trace = replay.read_jsonl(trace_raw)
    call_rows, malformed_calls = replay.read_jsonl(calls_raw)
    parsed = replay.parse_call_log(call_rows)
    if malformed_trace or malformed_calls:
        return {
            "status": "FAIL",
            "reason": "MALFORMED_ARCHIVE_JSONL",
            "pairs": [],
            "trace_sha256": observed_trace_sha,
            "call_log_sha256": observed_calls_sha,
        }

    model_rows = sorted(case.get("requests") or [], key=lambda row: row.get("model_ordinal") or 0)
    pairs: list[dict] = []
    unavailable_actions: dict[str, int] = defaultdict(int)
    source_joins_verified = 0
    for request_row in model_rows:
        event_index = request_row.get("trace_event_index")
        if not isinstance(event_index, int) or not 0 <= event_index < len(events):
            continue
        event = events[event_index]
        actions, protocol = _action_candidates(event, replay)
        if not any(name == "terminal" for name, _ in actions):
            continue
        selected_names = [name for name, _ in actions]
        sequence = request_row.get("client_call_seq")
        start = parsed["starts"].get(sequence)
        end = parsed["ends"].get(sequence)
        response = replay.resolved_response(end, parsed["blobs"])
        response_signature = replay.provider_action_signature(response) if response else None
        trace_signature = replay.provider_action_signature(event)
        if (
            request_row.get("fidelity") != replay.EXACT_FIDELITY
            or not start
            or not end
            or not end.get("ok")
            or start.get("role") != request_row.get("role")
            or protocol != request_row.get("action_protocol")
            or selected_names != list(request_row.get("selected_action_names") or [])
            or response_signature is None
            or response_signature != request_row.get("response_action_signature")
            or response_signature != trace_signature
        ):
            unavailable_actions["SOURCE_ACTION_JOIN_FAILED"] += sum(
                1 for name, _ in actions if name == "terminal"
            )
            continue
        source_joins_verified += 1
        next_model_index = next(
            (
                candidate
                for candidate in range(event_index + 1, len(events))
                if events[candidate].get("event") == "model"
            ),
            len(events),
        )
        result_rows = [
            (index, result)
            for index, result in enumerate(events[event_index + 1 : next_model_index], start=event_index + 1)
            if result.get("event") == "tool"
        ]
        result_cursor = 0
        for name, args in actions:
            match_index = None
            for offset in range(result_cursor, len(result_rows)):
                _trace_index, tool_row = result_rows[offset]
                if tool_row.get("name") == name and _canonical(tool_row.get("args") or {}) == _canonical(args):
                    match_index = offset
                    break
            if match_index is None:
                if name == "terminal":
                    unavailable_actions["NO_EXACT_TRACE_ACTION_RESULT_PAIR"] += 1
                continue
            trace_index, tool_row = result_rows[match_index]
            result_cursor = match_index + 1
            if name != "terminal":
                continue
            action = args.get("input")
            if not isinstance(action, str) or not action:
                unavailable_actions["NO_NONEMPTY_STRING_INPUT"] += 1
                continue
            if args.get("mode", "command") != "command" or bool(args.get("interrupt")):
                unavailable_actions["NON_COMMAND_OR_INTERRUPT"] += 1
                continue
            observation = tool_row.get("result")
            if not isinstance(observation, str):
                unavailable_actions["NO_STRING_RESULT"] += 1
                continue
            pairs.append(
                {
                    "action": action,
                    "args": args,
                    "observation": observation,
                    "action_sha256": _sha_text(action),
                    "observation_sha256": _sha_text(observation),
                    "observation_bytes": len(observation.encode("utf-8")),
                    "trace_event_index": trace_index,
                    "model_ordinal": request_row.get("model_ordinal"),
                    "action_protocol": protocol,
                }
            )
            if len(pairs) >= MAX_ACTIONS_PER_CASE:
                break
        if len(pairs) >= MAX_ACTIONS_PER_CASE:
            break

    fatal_join_errors = sum(
        unavailable_actions.get(reason, 0)
        for reason in ("SOURCE_ACTION_JOIN_FAILED", "NO_EXACT_TRACE_ACTION_RESULT_PAIR", "NO_STRING_RESULT")
    )
    status = "FAIL" if fatal_join_errors else "PASS" if pairs else "UNAVAILABLE"
    return {
        "status": status,
        "reason": None if pairs else "NO_REPLAYABLE_TERMINAL_ACTIONS",
        "pairs": pairs,
        "source_joins_verified": source_joins_verified,
        "unavailable_actions": dict(sorted(unavailable_actions.items())),
        "trace_sha256": observed_trace_sha,
        "call_log_sha256": observed_calls_sha,
        "trace_bytes": len(trace_raw),
        "call_log_bytes": len(calls_raw),
        "malformed_trace_lines": malformed_trace,
        "malformed_call_lines": malformed_calls,
    }


def _scripted_call(replay: Any, name: str, args: dict, call_id: str) -> list:
    return replay.scripted_call(name, args, call_id=call_id)


def _tool_message_for_call(requests: list[dict], request_index: int, call_id: str) -> str | None:
    if request_index >= len(requests):
        return None
    messages = requests[request_index].get("messages") or []
    for message in messages:
        if message.get("role") == "tool" and message.get("tool_call_id") == call_id:
            content = message.get("content")
            return content if isinstance(content, str) else None
    return None


def _run_core_sequence(pairs: list[dict], replay: Any, *, label: str) -> dict:
    sequences: dict[str, list[str]] = {}
    for pair in pairs:
        sequences.setdefault(pair["action"], []).append(pair["observation"])
    script = [
        _scripted_call(replay, "terminal", pair["args"], f"replay-{index}")
        for index, pair in enumerate(pairs)
    ]
    script.append(_scripted_call(replay, "finish", {"summary": "scripted replay"}, "replay-finish"))

    process_calls = {"shell": 0, "exec": 0}
    original_shell = asyncio.create_subprocess_shell
    original_exec = asyncio.create_subprocess_exec

    def blocked_process(kind: str):
        def fail_closed(*_args: Any, **_kwargs: Any):
            process_calls[kind] += 1
            raise AssertionError("historical replay attempted process creation")

        return fail_closed

    asyncio.create_subprocess_shell = blocked_process("shell")
    asyncio.create_subprocess_exec = blocked_process("exec")
    try:
        run = replay.run_scripted(
            script,
            "SYNTHETIC REPLAY TASK: return each supplied tool observation, then finish.",
            playback_sequences=sequences,
            capture_provider_requests=True,
            timeout_s=90.0,
        )
    finally:
        asyncio.create_subprocess_shell = original_shell
        asyncio.create_subprocess_exec = original_exec

    env = run["env"]
    tool_rows = [row for row in run["trace"] if row.get("event") == "tool" and row.get("name") == "terminal"]
    observed_results = [row.get("result") for row in tool_rows]
    expected_results = [pair["observation"] for pair in pairs]
    observed_action_hashes = [_sha_text(str(row.get("args", {}).get("input", ""))) for row in tool_rows]
    expected_action_hashes = [pair["action_sha256"] for pair in pairs]
    requests = run.get("provider_requests") or []
    model_visible_rows = []
    for index, pair in enumerate(pairs):
        content = _tool_message_for_call(requests, index + 1, f"replay-{index}")
        prefix_matches = content is not None and content.startswith(pair["observation"])
        suffix = content[len(pair["observation"]):] if prefix_matches else None
        model_visible_rows.append(
            {
                "content_present": content is not None,
                "result_prefix_matches": prefix_matches,
                "clock_suffix_valid": suffix is not None
                and re.fullmatch(r"\n\[t=\d+s of 90s\]", suffix) is not None,
                "content_sha256": _sha_text(content) if content is not None else None,
                "content_bytes": len(content.encode("utf-8")) if content is not None else None,
            }
        )
    checks = {
        "run_finished": run["result"] is not None and run["result"].status == "finished",
        "trace_results_equal_source_sequence": observed_results == expected_results,
        "terminal_action_order_equal_source": observed_action_hashes == expected_action_hashes,
        "all_sequence_observations_consumed": all(value == 0 for value in env.remaining_playback_sequences().values()),
        "all_results_reached_next_model_request": len(model_visible_rows) == len(pairs)
        and all(
            row["content_present"] and row["result_prefix_matches"] and row["clock_suffix_valid"]
            for row in model_visible_rows
        ),
        "no_action_blocked": not env.blocked_actions,
        "no_host_process_creation": env.process_launches == 0 and process_calls == {"shell": 0, "exec": 0},
        "no_file_transfer": env.upload_calls == 0 and env.download_calls == 0,
        "temporary_workdirs_removed": run["temporary_workdirs_removed"],
    }
    return {
        "case_hash": _sha_text(label),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "counts": {
            "actions_replayed": len(pairs),
            "distinct_actions": len(set(expected_action_hashes)),
            "repeated_action_occurrences": len(expected_action_hashes) - len(set(expected_action_hashes)),
            "repeated_action_groups_with_distinct_observations": sum(
                1
                for action_hash in set(expected_action_hashes)
                if sum(value == action_hash for value in expected_action_hashes) > 1
                and len({pair["observation_sha256"] for pair in pairs if pair["action_sha256"] == action_hash}) > 1
            ),
            "model_visible_observations_verified": sum(
                1 for row in model_visible_rows if row["content_present"] and row["result_prefix_matches"]
            ),
        },
        "actions": [
            {
                "action_sha256": pair["action_sha256"],
                "observation_sha256": pair["observation_sha256"],
                "observation_bytes": pair["observation_bytes"],
                "model_visible_content_sha256": model_visible_rows[index]["content_sha256"],
                "model_visible_content_bytes": model_visible_rows[index]["content_bytes"],
                "model_visible_prefix_matches": model_visible_rows[index]["result_prefix_matches"],
                "model_visible_clock_suffix_valid": model_visible_rows[index]["clock_suffix_valid"],
            }
            for index, pair in enumerate(pairs)
        ],
        "process_guard_calls": process_calls,
        "process_launches": env.process_launches,
        "playback_hits": len(env.playback_hits),
        "blocked_actions": len(env.blocked_actions),
        "remaining_sequence_observations": sum(env.remaining_playback_sequences().values()),
        "temporary_trace_and_workdirs_removed": run["temporary_workdirs_removed"],
        "limit": "scripted current Core loop with exact archived terminal action/result fixtures; no archived command execution, model inference, task-filesystem effects, grading, or task-success claim",
    }


def _synthetic_queue_control(replay: Any) -> dict:
    mutated_action = SYNTHETIC_ACTION + " __AETHER_REPLAY_MUTATION__"
    script = [
        _scripted_call(replay, "terminal", {"input": mutated_action}, "synthetic-mutated"),
        _scripted_call(replay, "terminal", {"input": SYNTHETIC_ACTION}, "synthetic-1"),
        _scripted_call(replay, "terminal", {"input": SYNTHETIC_ACTION}, "synthetic-2"),
        _scripted_call(replay, "terminal", {"input": SYNTHETIC_ACTION}, "synthetic-exhausted"),
        _scripted_call(replay, "finish", {"summary": "scripted control"}, "synthetic-finish"),
    ]
    run = replay.run_scripted(
        script,
        "SYNTHETIC QUEUE CONTROL: preserve observation order and block mismatches.",
        playback_sequences={SYNTHETIC_ACTION: list(SYNTHETIC_OBSERVATIONS)},
        capture_provider_requests=True,
        timeout_s=90.0,
    )
    terminal_rows = [row for row in run["trace"] if row.get("event") == "tool" and row.get("name") == "terminal"]
    results = [row.get("result") for row in terminal_rows]
    expected = [BLOCKED_OBSERVATION, *SYNTHETIC_OBSERVATIONS, BLOCKED_OBSERVATION]
    env = run["env"]
    expected_action_hashes = [_sha_text(mutated_action), *([_sha_text(SYNTHETIC_ACTION)] * 3)]
    observed_action_hashes = [_sha_text(str(row.get("args", {}).get("input", ""))) for row in terminal_rows]
    queues = env.remaining_playback_sequences()

    # The former scalar map necessarily collapses repeated identical actions to one result.
    broken = replay.run_scripted(
        [
            _scripted_call(replay, "terminal", {"input": SYNTHETIC_ACTION}, "broken-1"),
            _scripted_call(replay, "terminal", {"input": SYNTHETIC_ACTION}, "broken-2"),
            _scripted_call(replay, "finish", {"summary": "scripted negative control"}, "broken-finish"),
        ],
        "SYNTHETIC NEGATIVE CONTROL: detect scalar collapse of duplicate actions.",
        playback={SYNTHETIC_ACTION: SYNTHETIC_OBSERVATIONS[0]},
        capture_provider_requests=True,
        timeout_s=90.0,
    )
    broken_rows = [row for row in broken["trace"] if row.get("event") == "tool" and row.get("name") == "terminal"]
    broken_results = [row.get("result") for row in broken_rows]
    broken_queue_collapse_detected = broken_results != list(SYNTHETIC_OBSERVATIONS)
    checks = {
        "synthetic_run_finished": run["result"] is not None and run["result"].status == "finished",
        "all_expected_results_match": results == expected,
        "mutated_action_blocked": bool(terminal_rows) and results[0] == BLOCKED_OBSERVATION,
        "mutation_did_not_consume_original_queue": results[1:3] == list(SYNTHETIC_OBSERVATIONS),
        "duplicate_action_got_distinct_results": results[1:3] == list(SYNTHETIC_OBSERVATIONS)
        and results[1] != results[2],
        "exhausted_queue_blocks_without_reusing_stale_result": results[3] == BLOCKED_OBSERVATION,
        "action_order_preserved": observed_action_hashes == expected_action_hashes,
        "queue_fully_consumed": bool(queues) and all(remaining == 0 for remaining in queues.values()),
        "blocked_queue_collapse_was_detected": broken_queue_collapse_detected,
        "temporary_workdirs_removed": run["temporary_workdirs_removed"]
        and broken["temporary_workdirs_removed"],
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "counts": {
            "synthetic_actions": len(terminal_rows),
            "distinct_action_sha256": 2,
            "sequence_results": len(SYNTHETIC_OBSERVATIONS),
            "blocked_or_exhausted_attempts": len(env.blocked_actions),
            "broken_scalar_replay_actions": len(broken_rows),
        },
        "actions": [
            {
                "action_sha256": expected_action_hashes[index],
                "observation_sha256": _sha_text(result),
                "observation_bytes": len(result.encode("utf-8")),
            }
            for index, result in enumerate(results)
        ],
        "broken_scalar_observation_sha256": [_sha_text(value) for value in broken_results],
        "expected_distinct_observation_sha256": [_sha_text(value) for value in SYNTHETIC_OBSERVATIONS],
        "temporary_trace_and_workdirs_removed": run["temporary_workdirs_removed"]
        and broken["temporary_workdirs_removed"],
        "limit": "synthetic scripted control; the intentionally scalar legacy playback is the known-bad duplicate-action collapse control",
    }


def run_qualification(corpus_path: Path, root_map_path: Path) -> dict:
    corpus_raw = corpus_path.read_bytes()
    corpus_sha = _sha256(corpus_raw)
    if corpus_sha != CORPUS_SHA256:
        raise ValueError("CORPUS_DIGEST_MISMATCH")
    manifest = json.loads(corpus_raw)
    cases = manifest.get("cases") or []
    if manifest.get("schema") != "aether.core.replay_corpus.v1" or len(cases) != EXPECTED_CASES:
        raise ValueError("CORPUS_SCHEMA_OR_CASE_COUNT_MISMATCH")

    # Protection preflight occurs over all 15 corpus metadata entries before any archive path resolution.
    denied = _protected_cases(cases)
    if denied:
        raise PermissionError("PROTECTED_CASE_DENIED_BEFORE_SOURCE_RESOLUTION")

    captured_cases = [case for case in cases if (case.get("expected") or {}).get("client_capture_present")]
    selected = [
        case
        for case in captured_cases
        if any("terminal" in (row.get("selected_action_names") or []) for row in case.get("requests") or [])
    ]
    no_terminal_cases = [case for case in captured_cases if case not in selected]
    event_only = len(cases) - sum(1 for case in cases if (case.get("expected") or {}).get("client_capture_present"))
    root_map_raw = root_map_path.read_bytes()
    root_map = json.loads(root_map_raw)
    replay = _module()
    case_rows = [
        {
            "case_key_sha256": _sha_text(str(case.get("case_key") or "")),
            "source_symbol_sha256": _sha_text(str(case.get("source_symbol") or "")),
            "status": "UNAVAILABLE",
            "reason": "NO_CAPTURED_TERMINAL_ACTIONS",
            "source_identity": {"trace_sha256": None, "call_log_sha256": None},
            "unavailable_actions": {"NO_CAPTURED_TERMINAL_ACTIONS": 1},
            "replay": None,
        }
        for case in no_terminal_cases
    ]
    for case in selected:
        source = _terminal_pairs_for_case(case, root_map, replay)
        case_identity = _sha_text(str(case.get("case_key") or ""))
        symbol_identity = _sha_text(str(case.get("source_symbol") or ""))
        entry = {
            "case_key_sha256": case_identity,
            "source_symbol_sha256": symbol_identity,
            "status": source["status"],
            "reason": source.get("reason"),
            "source_joins_verified": source.get("source_joins_verified", 0),
            "source_identity": {
                "trace_sha256": source.get("trace_sha256"),
                "call_log_sha256": source.get("call_log_sha256"),
                "trace_bytes": source.get("trace_bytes"),
                "call_log_bytes": source.get("call_log_bytes"),
            },
            "unavailable_actions": source.get("unavailable_actions", {}),
        }
        if source["status"] == "PASS":
            entry["replay"] = _run_core_sequence(source["pairs"], replay, label=case_identity)
            entry["status"] = entry["replay"]["status"]
        else:
            entry["replay"] = None
        case_rows.append(entry)

    synthetic = _synthetic_queue_control(replay)
    runtime_files = {}
    runtime_mode = "unavailable"
    for module_name in (
        "aether.core",
        "aether.core.loop",
        "aether.core.provider",
        "aether.core.tools",
        "aether.core.terminal",
        "aether.core.context",
        "aether.core.env",
    ):
        try:
            module = importlib.import_module(module_name)
            module_path = Path(module.__file__).resolve()
            runtime_files[module_name] = {
                "path": str(module_path),
                "sha256": _sha256(module_path.read_bytes()),
            }
            runtime_mode = "source" if REPO_ROOT / "aether-core/src" in module_path.parents else "installed"
        except Exception as exc:
            runtime_files[module_name] = {"error": type(exc).__name__}
    available = sum(1 for row in case_rows if row["source_identity"]["trace_sha256"])
    replayed_cases = sum(1 for row in case_rows if row["replay"] is not None)
    failed_cases = sum(1 for row in case_rows if row["status"] == "FAIL")
    unavailable_cases = sum(1 for row in case_rows if row["status"] == "UNAVAILABLE")
    not_replayed_cases = len(case_rows) - replayed_cases
    verdict = {
        "ok": failed_cases == 0 and unavailable_cases == 0 and not_replayed_cases == 0 and synthetic["status"] == "PASS",
        "problems": [],
    }
    if failed_cases:
        verdict["problems"].append("HISTORICAL_SEQUENCE_REPLAY_FAILED")
    if unavailable_cases:
        verdict["problems"].append("HISTORICAL_SEQUENCE_DENOMINATOR_INCOMPLETE")
    if not_replayed_cases and not unavailable_cases:
        verdict["problems"].append("HISTORICAL_SEQUENCE_SOURCE_OR_EXECUTION_NOT_REPLAYED")
    if synthetic["status"] != "PASS":
        verdict["problems"].append("SYNTHETIC_QUEUE_CONTROL_FAILED")
    return {
        "schema": "aether.core.terminal_sequence_replay.v1",
        "corpus": {
            "path": str(corpus_path),
            "sha256": corpus_sha,
            "archive_commit": manifest.get("archive_commit"),
            "cases_total": len(cases),
            "event_only_excluded": event_only,
            "selected_captured_terminal_cases": len(selected),
            "captured_cases_without_terminal_actions": len(no_terminal_cases),
            "max_actions_per_case": MAX_ACTIONS_PER_CASE,
        },
        "root_map": {"path": str(root_map_path), "sha256": _sha256(root_map_raw)},
        "protected_name_preflight": {
            "case_metadata_entries_checked_before_resolution": len(cases),
            "denied_entries": 0,
            "authority_source": "AGENTS.md and tracking/collab/aether_glm_benchmark_program_20260924/CURRENT_PROGRAM.md:84",
        },
        "runtime": {"import_mode": runtime_mode, "module_files": runtime_files},
        "counts": {
            "source_available": available,
            "cases_replayed": replayed_cases,
            "cases_failed": failed_cases,
            "cases_unavailable": unavailable_cases,
            "cases_not_replayed": not_replayed_cases,
            "historical_actions_replayed": sum(
                row["replay"]["counts"]["actions_replayed"]
                for row in case_rows
                if row["replay"] is not None
            ),
            "historical_model_visible_observations_verified": sum(
                row["replay"]["counts"]["model_visible_observations_verified"]
                for row in case_rows
                if row["replay"] is not None
            ),
        },
        "cases": case_rows,
        "synthetic_duplicate_action_control": synthetic,
        "verdict": verdict,
        "scope_limit": "selected source-bound historical terminal action/result subsequences, at most 12 actions per selected captured case; no complete historical VM/task execution, task-filesystem execution, grading, model inference, or task-performance claim",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--root-map", type=Path, default=DEFAULT_ROOT_MAP)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        report = run_qualification(args.corpus, args.root_map)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": type(exc).__name__}, sort_keys=True))
        return 1
    _write_json(args.out, report)
    print(json.dumps({"status": "PASS" if report["verdict"]["ok"] else "FAIL", "counts": report["counts"], "out": str(args.out)}, sort_keys=True))
    return 0 if report["verdict"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
