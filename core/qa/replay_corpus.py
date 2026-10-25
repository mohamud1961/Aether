#!/usr/bin/env python3
"""Configurable, source-bound offline replay foundation for archived Aether Core runs.

What this module is for (C1 of the Core consolidation programme)
---------------------------------------------------------------
It answers three separable questions, each with an explicit tier and no inference:

T0  Source identity and join. Does a named archive case still exist at the operator's
    configured root, do its trace/call-log bytes match the frozen digests, and does every
    captured model decision join to exactly one archived provider call (client sequence ->
    recorded request -> recorded response -> the action signature in the trace)?
T1  Request reconstruction. Expanding the content-addressed captured request (messages, tool
    schema, sampling parameters) with the archived blobs must reproduce, byte for byte, the
    canonical structured request whose SHA the frozen request index recorded.
T2  Harness mechanics. Selected scripted turns through the *real* ``run_agent`` and
    ``ChatProvider`` with recorded historical tool observations played back INERTLY (the
    archived command is never executed on this host). Generated files are labelled
    SYNTHETIC/RECREATED; nothing here proves a model's reaction, a task outcome or a grade.

What it never does
------------------
* No model/API call, no network, no VM, no container, no task execution, no grader.
* No write to any archive: historical payloads are opened read-only and only for the exact
  symbolic paths the corpus names.
* No raw prompt/task/tool-output text in its output: evidence is digests, counts, roles,
  protocol names and booleans. (Archived payloads exist only in the operator's archive.)
* No Git at replay time: the manifest carries the frozen expected SHAs.

Provenance of reused logic
--------------------------
The canonical serialization, content-addressed blob expansion, provider action-signature and
selected-action parsing below are re-implemented from
``research/semantic_archive_coverage_index_20261025.py`` at archive commit
``3d5fd06582432ddcfb5c76ea139d3247a268434b``. That script enumerates operator paths at import
and writes result files from ``main()``, so it is reproduced here with explicit provenance
instead of imported. The scripted provider/environment doubles mirror
``aether-core/tests/core_fakes.py`` (chunk/tool_chunk/ScriptedClient/LocalEnv interface); the
loop itself is the installed ``aether.core.loop.run_agent``, never a second implementation.

Operator usage (root map and manifest are external; nothing operator-specific is committed)::

    python aether-core/qa/replay_corpus.py build --seed SEED.json --selection SELECTION.json \\
        --dashboard DASH.json --index INDEX.json --root-map ROOTMAP.json --out CORPUS.json
    python aether-core/qa/replay_corpus.py all --manifest CORPUS.json --root-map ROOTMAP.json \\
        --index INDEX.json --out RESULTS.json

``build`` needs the archive metadata files (frozen index + coverage dashboard) and the archive
roots. ``all`` needs only the committed manifest, the operator root map, and - for T2 - an
installed ``aether.core``; the optional ``--index`` re-checks manifest expectations against a
second copy of the frozen index.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import shutil
import shlex
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

TOOL_VERSION = "aether.core.replay_corpus.v1"
CORPUS_SCHEMA = "aether.core.replay_corpus.v1"
RESULTS_SCHEMA = "aether.core.replay_results.v1"
ARCHIVE_COMMIT = "3d5fd06582432ddcfb5c76ea139d3247a268434b"
INDEX_SCHEMA = "aether.archived_core_model_requests.v1"
DASHBOARD_SCHEMA = "aether.historical_core_coverage_dashboard.v1"

# Indexed pre-send fidelities that carry a real structured request object.
EXACT_FIDELITY = "EXACT_ARCHIVED_STRUCTURED_CLIENT_OBJECT"
NO_CAPTURE = "NO_MATCHED_PROVIDER_CLIENT_REQUEST"

SAMPLING_KEYS = (
    "temperature",
    "top_p",
    "tool_choice",
    "parallel_tool_calls",
    "reasoning_effort",
    "top_k",
)

# Limits for evidence size (counts are always reported; lists are bounded samples).
MAX_FAILURES_PER_CASE = 12


# --------------------------------------------------------------------------------------------
# Digests and canonical serialization (provenance: semantic_archive_coverage_index @ 3d5fd065)
# --------------------------------------------------------------------------------------------


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical(value: Any) -> bytes:
    """The archive's canonical JSON form: sorted keys, no whitespace, ASCII, ``default=str``."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    ).encode("utf8")


def read_jsonl(raw: bytes) -> tuple[list[dict], int]:
    rows: list[dict] = []
    malformed = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (ValueError, UnicodeDecodeError):
            malformed += 1
    return rows, malformed


def load_jsonl(path: Path) -> tuple[list[dict], int]:
    return read_jsonl(path.read_bytes())


# --------------------------------------------------------------------------------------------
# Captured-request parsing (same semantics as the archive index generator)
# --------------------------------------------------------------------------------------------


def expand_request(request: dict, blobs: dict) -> tuple[dict, list[str]]:
    """Replace content-addressed references with their archived values; report unresolved ones.

    An unresolved reference is a *miss*, never silently kept as data: the T1 row then fails.
    """
    obj = dict(request)
    misses: list[str] = []
    for key in ("tools", "params"):
        if isinstance(obj.get(key), str):
            if obj[key] in blobs:
                obj[key] = blobs[obj[key]]
            else:
                misses.append(key)
    for key in ("messages", "input"):
        if isinstance(obj.get(key), list):
            resolved: list[Any] = []
            for index, item in enumerate(obj[key]):
                if isinstance(item, str):
                    if item in blobs:
                        resolved.append(blobs[item])
                    else:
                        misses.append(f"{key}:{index}")
                        resolved.append(
                            {"unresolved_source_ref_sha256": sha256_text(item)}
                        )
                else:
                    resolved.append(item)
            obj[key] = resolved
    return obj, misses


def call_function(call: dict) -> tuple[str, Any]:
    fn = call.get("function") or {}
    args = fn.get("arguments") or "{}"
    try:
        parsed = json.loads(args) if isinstance(args, str) else args
    except (ValueError, TypeError):
        parsed = {"unparsed_args_sha256": sha256_text(str(args))}
    return str(fn.get("name") or ""), parsed


def provider_action_signature(response: dict) -> str | None:
    """The response's action identity: native tool calls, JSON text, or reasoning only."""
    native = response.get("tool_calls") or []
    if native:
        return "native:" + sha256_bytes(canonical(native))
    body = response.get("content")
    if isinstance(body, str) and body:
        return "json_text:" + sha256_bytes(
            canonical({"content": body, "reasoning": response.get("reasoning")})
        )
    reasoning = response.get("reasoning")
    if isinstance(reasoning, str) and reasoning:
        return "reasoning_only:" + sha256_bytes(reasoning.encode())
    return None


def selected_actions(message: dict) -> tuple[list[tuple[str, Any]], str]:
    native = message.get("tool_calls") or []
    if native:
        return [(call_function(call)[0], call_function(call)[1]) for call in native], "native"
    body = message.get("content") or ""
    if not isinstance(body, str):  # pragma: no cover - defensive
        return [], "unparsed_text"
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        return [], "unparsed_text"
    if not isinstance(parsed, dict):
        return [], "unparsed_text"
    actions: list[tuple[str, Any]] = []
    for action in parsed.get("actions") or []:
        if not isinstance(action, dict):
            continue
        actions.append(
            (
                str(action.get("tool") or ""),
                action.get("args") if isinstance(action.get("args"), dict) else {},
            )
        )
    return actions, "json_content"


def parse_call_log(rows: list[dict]) -> dict:
    """Split a ``core_calls.jsonl`` recording into starts, ends and content-addressed blobs."""
    return {
        "starts": {r["seq"]: r for r in rows if r.get("kind") == "start" and "seq" in r},
        "ends": {r["seq"]: r for r in rows if r.get("kind") == "end" and "seq" in r},
        "blobs": {
            r["key"]: r["value"] for r in rows if r.get("kind") == "blob" and "key" in r
        },
    }


def model_events(events: list[dict]) -> list[tuple[int, dict]]:
    return [(i, e) for i, e in enumerate(events) if e.get("event") == "model"]


def resolved_response(end: dict | None, blobs: dict) -> dict | None:
    """The end row's ``response`` is a content-addressed reference; resolve it, never assume a dict."""
    if not end:
        return None
    value = end.get("response")
    if isinstance(value, str):
        value = blobs.get(value)
    return value if isinstance(value, dict) else None


# --------------------------------------------------------------------------------------------
# Symbolic sources (no operator path is ever asserted here)
# --------------------------------------------------------------------------------------------


def resolve_symbol(symbol: str, root_map: dict) -> tuple[Path | None, str]:
    """Resolve archive metadata within its root; never follow trace/client-log aliases."""
    if not symbol.startswith("$") or "/" not in symbol:
        return None, "MALFORMED_SYMBOL"
    name, _, relative = symbol[1:].partition("/")
    root = root_map.get(name)
    if not root:
        return None, f"ROOT_NOT_CONFIGURED:{name}"
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        return None, "SOURCE_PATH_TRAVERSAL_DENIED"
    base = Path(root).resolve()
    path = base / relative
    # Archives are immutable during qualification. Reject symlink components
    # for BOTH payload files before is_file/read_bytes can follow either one.
    for source in (path, path.with_name("core_calls.jsonl")):
        for component in (source, *source.parents):
            if component == base:
                break
            if component.is_symlink():
                return None, "SOURCE_SYMLINK_DENIED"
        if not source.resolve().is_relative_to(base):
            return None, "SOURCE_OUTSIDE_ROOT_DENIED"
    if not path.is_file():
        return None, "SOURCE_NOT_FOUND"
    return path, ""


# --------------------------------------------------------------------------------------------
# Check helpers
# --------------------------------------------------------------------------------------------


def _check(check: str, expected: Any, observed: Any) -> dict:
    return {"check": check, "expected": expected, "observed": observed, "ok": expected == observed}


def _check_true(check: str, condition: bool, observed: Any = None) -> dict:
    return {"check": check, "expected": True, "observed": (observed if observed is not None else condition), "ok": bool(condition)}


def _status(checks: list[dict]) -> str:
    return "PASS" if all(c["ok"] for c in checks) else "FAIL"


# --------------------------------------------------------------------------------------------
# Frozen-index lookup used by build and by the optional second oracle at replay time
# --------------------------------------------------------------------------------------------


def index_rows_for(index_rows: list[dict], cohort: str, case: str, trace_sha: str) -> list[dict]:
    rows = [
        r
        for r in index_rows
        if r.get("cohort") == cohort
        and r.get("archive_case") == case
        and r.get("trace_sha256") == trace_sha
    ]
    return sorted(rows, key=lambda r: r.get("model_ordinal") or 0)


# --------------------------------------------------------------------------------------------
# Corpus construction (T0/T1 expectations come from the archives AND the frozen index)
# --------------------------------------------------------------------------------------------


class BuildError(RuntimeError):
    pass


def _expected_case_from_archive(
    case: dict, calls: dict, events: list[dict], index_rows: list[dict], raw_trace: bytes
) -> tuple[dict, list[dict]]:
    """Derive the corpus expectations, cross-checking the frozen index against the archive.

    The canonical request SHA written into the corpus is the frozen index value; the archive is
    expanded here only to *prove* that value is reproducible. Disagreement is a build error, not
    a best-effort value.
    """
    starts, ends, blobs = calls["starts"], calls["ends"], calls["blobs"]
    roles = sorted(
        {str(r.get("role")) for r in starts.values() if r.get("role") is not None}
    )
    role_counts: dict[str, int] = {}
    for row in starts.values():
        role = str(row.get("role"))
        role_counts[role] = role_counts.get(role, 0) + 1
    models = model_events(events)
    rows: list[dict] = []
    first_worker_tools: list[str] | None = None
    captured_sampling: dict | None = None
    for index_row in index_rows:
        ordinal = index_row.get("model_ordinal")
        fidelity = index_row.get("pre_send_request_fidelity")
        trace_index = index_row.get("trace_event_index")
        if trace_index is None or trace_index >= len(events):
            raise BuildError(f"{case['case_key']}: ordinal {ordinal} trace index out of range")
        event = events[trace_index]
        if event.get("event") != "model":
            raise BuildError(f"{case['case_key']}: ordinal {ordinal} does not point at a model event")
        actions, protocol = selected_actions(event)
        if protocol != index_row.get("action_protocol"):
            raise BuildError(f"{case['case_key']}: ordinal {ordinal} action protocol disagrees with index")
        if [a[0] for a in actions] != list(index_row.get("selected_action_names") or []):
            raise BuildError(f"{case['case_key']}: ordinal {ordinal} action names disagree with index")
        row: dict[str, Any] = {
            "model_ordinal": ordinal,
            "trace_event_index": trace_index,
            "action_protocol": protocol,
            "selected_action_names": [a[0] for a in actions],
            "reasoning_field_present": row_bool(event.get("reasoning")),
            "fidelity": fidelity,
            "client_call_seq": index_row.get("client_call_seq"),
            "request_record_sha256": None,
            "resolved_request_sha256": None,
            "resolved_request_json_utf8_bytes": None,
            "message_count": None,
            "tool_schema_sha256": None,
            "role": None,
            "tools_present": None,
            "response_action_signature": None,
        }
        if fidelity == EXACT_FIDELITY:
            seq = index_row.get("client_call_seq")
            start = starts.get(seq)
            if start is None:
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} seq {seq} has no start row")
            end = ends.get(seq)
            if end is None or not end.get("ok"):
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} seq {seq} has no successful end")
            response = resolved_response(end, blobs)
            if response is None:
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} response blob is unresolved")
            signature_calls = provider_action_signature(response)
            signature_trace = provider_action_signature(event)
            if signature_calls is None or signature_calls != signature_trace:
                raise BuildError(
                    f"{case['case_key']}: ordinal {ordinal} response/action signature does not join"
                )
            record_sha = sha256_bytes(canonical(start.get("request") or {}))
            if record_sha != index_row.get("request_record_sha256"):
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} request record SHA differs from index")
            resolved, misses = expand_request(start.get("request") or {}, blobs)
            if misses:
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} has unresolved blobs {misses[:3]}")
            resolved_bytes = canonical(resolved)
            resolved_sha = sha256_bytes(resolved_bytes)
            if resolved_sha != index_row.get("resolved_request_sha256"):
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} canonical request SHA differs from index")
            if len(resolved_bytes) != index_row.get("resolved_request_json_utf8_bytes"):
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} request size differs from index")
            tools = resolved.get("tools") or []
            tools_sha = sha256_bytes(canonical(tools))
            if tools_sha != index_row.get("tool_schema_sha256"):
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} tool schema SHA differs from index")
            messages = resolved.get("messages", resolved.get("input", []))
            if len(messages) != index_row.get("message_count"):
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} message count differs from index")
            row.update(
                {
                    "request_record_sha256": record_sha,
                    "resolved_request_sha256": resolved_sha,
                    "resolved_request_json_utf8_bytes": len(resolved_bytes),
                    "message_count": len(messages),
                    "tool_schema_sha256": tools_sha,
                    "role": str(start.get("role")),
                    "tools_present": isinstance(resolved.get("tools"), list),
                    "response_action_signature": signature_trace,
                }
            )
            if str(start.get("role")) == "worker" and first_worker_tools is None:
                first_worker_tools = [t.get("function", {}).get("name") for t in tools]
                params = resolved.get("params")
                if isinstance(params, dict):
                    captured_sampling = {
                        k: params[k] for k in SAMPLING_KEYS if k in params
                    }
        elif fidelity == NO_CAPTURE:
            if index_row.get("request_record_sha256") is not None:
                raise BuildError(f"{case['case_key']}: ordinal {ordinal} has a request SHA without a capture")
        else:  # pragma: no cover - the index only has the two fidelities
            raise BuildError(f"{case['case_key']}: ordinal {ordinal} unknown fidelity {fidelity!r}")
        rows.append(row)
    expected = {
        "trace_sha256": sha256_bytes(raw_trace),
        "trace_bytes": len(raw_trace),
        "event_count": len(events),
        "model_selected_turns": len(models),
        "client_capture_present": bool(calls["starts"]),
        "client_calls_sha256": None,
        "role_counts": dict(sorted(role_counts.items())),
        "roles": roles,
        "index_rows": len(index_rows),
        "tool_names_first_worker": first_worker_tools,
        "captured_sampling": captured_sampling,
    }
    return expected, rows


def row_bool(value: Any) -> bool:
    return bool(value)


def build_corpus(
    *,
    seed: dict,
    selection: dict,
    dashboard: dict,
    index: dict,
    root_map: dict,
) -> dict:
    """Build the committed corpus: family metadata from the seed, identity from the archives."""
    if dashboard.get("schema") != DASHBOARD_SCHEMA:
        raise BuildError(f"unexpected dashboard schema {dashboard.get('schema')!r}")
    if index.get("schema") != INDEX_SCHEMA:
        raise BuildError(f"unexpected index schema {index.get('schema')!r}")
    episodes = {
        (e["cohort"], e["case_id"], e["trace_sha256"]): e for e in dashboard["episodes"]
    }
    index_rows = index["rows"]
    seed_families = {f["id"]: f for f in seed["case_families"]}
    selection_families = selection.get("families") or {}
    synthetic = selection.get("synthetic_families") or {}
    unknown = (set(selection_families) | set(synthetic)) - set(seed_families)
    if unknown:
        raise BuildError(f"selection names families absent from the seed: {sorted(unknown)}")
    cases: list[dict] = []

    def add_case(family: str, spec: dict, *, focus: list[int] | None = None) -> None:
        cohort, case_id, trace_sha = spec["cohort"], spec["case_id"], spec["trace_sha256"]
        episode = episodes.get((cohort, case_id, trace_sha))
        if episode is None:
            raise BuildError(f"case {cohort}/{case_id} is not in the frozen dashboard")
        symbol = episode["trace_source"]
        path, reason = resolve_symbol(symbol, root_map)
        if path is None:
            raise BuildError(f"case {cohort}/{case_id} source unavailable: {reason} ({symbol})")
        raw_trace = path.read_bytes()
        if sha256_bytes(raw_trace) != trace_sha:
            raise BuildError(f"case {cohort}/{case_id} trace digest differs from the frozen dashboard")
        calls_path = path.with_name("core_calls.jsonl")
        calls_present = calls_path.is_file()
        if calls_present != bool(episode["client_capture_present"]):
            raise BuildError(f"case {cohort}/{case_id} client-capture presence differs from the dashboard")
        rows_for_index = index_rows_for(index_rows, cohort, case_id, trace_sha)
        events, malformed_events = read_jsonl(raw_trace)
        if calls_present:
            raw_calls = calls_path.read_bytes()
            if sha256_bytes(raw_calls) != episode["client_calls_sha256"]:
                raise BuildError(f"case {cohort}/{case_id} call-log digest differs from the frozen dashboard")
            calls_rows, malformed_calls = read_jsonl(raw_calls)
        else:
            raw_calls, calls_rows, malformed_calls = None, [], 0
        case = {
            "case_key": f"{cohort}:{case_id}:{trace_sha[:16]}",
            "family": family,
            "cohort": cohort,
            "archive_case": case_id,
            "label": spec.get("label"),
            "label_note": spec.get("label_note"),
            "as_replay_input": False,
            "source_symbol": symbol,
            "focus_ordinals": focus or [],
        }
        expected, rows = _expected_case_from_archive(
            case, parse_call_log(calls_rows), events, rows_for_index, raw_trace
        )
        expected.update(
            {
                "case_id": case_id,
                "cohort": cohort,
                "client_calls_sha256": sha256_bytes(raw_calls) if raw_calls else None,
                "client_calls_bytes": len(raw_calls) if raw_calls else None,
                "malformed_event_lines": malformed_events,
                "malformed_call_lines": malformed_calls,
            }
        )
        case["expected"] = expected
        case["requests"] = rows
        if not calls_present:
            case["tier_reason"] = "EVENT_ONLY_NO_CLIENT_REQUEST_CAPTURE"
        cases.append(case)

    for family_id, spec in selection_families.items():
        for entry in spec.get("cases") or []:
            add_case(family_id, entry, focus=entry.get("focus_ordinals"))
    for entry in selection.get("coverage_cases") or []:
        add_case(entry.get("family", "coverage"), entry, focus=entry.get("focus_ordinals"))

    keys = [c["case_key"] for c in cases]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise BuildError(f"duplicate case keys in the corpus: {duplicates}")

    families: list[dict] = []
    for family_id, seed_family in seed_families.items():
        family_cases = [c for c in cases if c["family"] == family_id]
        tiers = _family_tiers(family_id, family_cases, synthetic.get(family_id, {}), selection)
        families.append(
            {
                "id": family_id,
                "source_class": seed_family.get("source_class_expected"),
                "historical_mechanism": seed_family.get("historical_mechanism"),
                "recorded_evidence_to_pin": seed_family.get("recorded_evidence_to_pin"),
                "seed_max_legitimate_tier": seed_family.get("max_legitimate_offline_tier"),
                "positive_control": seed_family.get("positive_control"),
                "cases": [c["case_key"] for c in family_cases],
                "tiers": tiers,
                "note": (synthetic.get(family_id) or {}).get("note"),
            }
        )
    return {
        "schema": CORPUS_SCHEMA,
        "tool": TOOL_VERSION,
        "archive_commit": ARCHIVE_COMMIT,
        "root_symbols": sorted({c["source_symbol"][1:].split("/", 1)[0] for c in cases}),
        "sources": selection.get("sources") or {},
        "label_policy": "labels are selection metadata (casebook/asset references); never replay input",
        "families": families,
        "cases": cases,
        "synthetic_t2_controls": selection.get("t2_controls") or [],
        "notes": [
            "Case keys are source identity: cohort + archive case + trace SHA prefix.",
            "Display names may repeat across arms; they are never used as identity.",
            "T1 expectations are the frozen request index SHAs, proven reproducible at build time.",
            "Event-only cases keep T1 unavailable; no request is invented for them.",
            "No grade, trial result or hidden answer is read; labels cite casebook evidence only.",
        ],
    }


def _family_tiers(family_id: str, cases: list[dict], synthetic: dict, selection: dict) -> dict:
    available = [c for c in cases if c["expected"]["client_capture_present"]]
    tiers: dict[str, dict] = {}
    if cases:
        tiers["T0"] = {"status": "available"}
        if available:
            tiers["T1"] = {"status": "available", "cases": len(available)}
            if len(available) < len(cases):
                tiers["T1"]["note"] = "event-only arms stay unavailable"
        else:
            tiers["T1"] = {
                "status": "unavailable",
                "reason": "EVENT_ONLY_NO_CLIENT_REQUEST_CAPTURE",
            }
    else:
        reason = synthetic.get("t01_unavailable_reason") or "NO_ARCHIVAL_CLIENT_OBJECT"
        tiers["T0"] = {"status": "unavailable", "reason": reason}
        tiers["T1"] = {"status": "unavailable", "reason": reason}
    if synthetic.get("t2_controls"):
        tiers["T2"] = {"status": "covered_by_synthetic_controls", "controls": synthetic["t2_controls"]}
    elif cases:
        tiers["T2"] = {
            "status": "unavailable",
            "reason": "NO_ISOLATED_DISPOSABLE_TASK_ENVIRONMENT; recorded tool effects stay inert",
        }
    else:
        tiers["T2"] = {
            "status": "unavailable",
            "reason": synthetic.get("t2_unavailable_reason") or "NO_CONTROL_IN_THIS_SLICE",
        }
    tiers["T3"] = {
        "status": "unavailable",
        "reason": "C1-LINUX-BLOCKED: no native Linux x86 backend and no historical VM snapshot",
    }
    if family_id == "installed-harbor" or synthetic.get("t4"):
        tiers["T4"] = {
            "status": "unavailable",
            "reason": synthetic.get("t4") or "C1-LINUX-BLOCKED_NATIVE_X86_ADMISSION",
        }
    tiers["T6"] = {"status": "not_authorized", "reason": "C1 does not authorize inference"}
    return tiers


# --------------------------------------------------------------------------------------------
# T0/T1 evaluation (the same function serves real runs and every negative control)
# --------------------------------------------------------------------------------------------


def evaluate_case(
    case: dict, data: dict, *, expected: dict | None = None
) -> dict:
    """Evaluate one case's T0 and T1 claims against supplied bytes.

    ``data`` keys: ``path`` (resolved source), ``trace_bytes``, ``calls_bytes``,
    ``calls_present``, and the optional mutations used by negative controls:
    ``drop_blob_keys`` (list), ``role_patch`` ({seq: role}), ``response_swap`` (seq, seq).
    """
    expected = expected or case["expected"]
    t0: list[dict] = []
    t1: list[dict] = []
    trace_bytes = data.get("trace_bytes")
    present = data.get("present", trace_bytes is not None)
    t0.append(_check_true("source_present", present, present))
    if not present:
        return {
            "t0": {"status": "FAIL", "checks": t0, "reason": data.get("reason") or "SOURCE_NOT_FOUND"},
            "t1": {"status": "NOT_RUN", "reason": "SOURCE_NOT_FOUND", "rows": _row_counts(case)},
            "rows": [],
        }
    t0.append(_check("trace_sha256", expected["trace_sha256"], sha256_bytes(trace_bytes)))
    path = data.get("path")
    t0.append(
        _check(
            "case_id",
            expected["case_id"],
            path.parent.parent.name if path is not None else None,
        )
    )
    events, malformed_events = read_jsonl(trace_bytes)
    t0.append(_check("event_count", expected["event_count"], len(events)))
    t0.append(_check("malformed_event_lines", expected["malformed_event_lines"], malformed_events))
    t0.append(
        _check(
            "model_selected_turns",
            expected["model_selected_turns"],
            len(model_events(events)),
        )
    )
    calls_present = data.get("calls_present", data.get("calls_bytes") is not None)
    t0.append(
        _check("client_capture_present", expected["client_capture_present"], calls_present)
    )
    declared_rows = case.get("requests") or []
    rows_out: list[dict] = []
    if not expected["client_capture_present"]:
        # Event-only: T1 must be unavailable and the absence must be real.
        t0.append(_check_true("event_only_absence", True, not calls_present))
        for row in declared_rows:
            ok = row.get("fidelity") == NO_CAPTURE and row.get("request_record_sha256") is None
            t0.append(
                _check_true(
                    f"event_only_row_{row.get('model_ordinal')}",
                    ok,
                    {"fidelity": row.get("fidelity"), "has_request_sha": row.get("request_record_sha256") is not None},
                )
            )
            t1.append(
                {
                    "model_ordinal": row.get("model_ordinal"),
                    "status": "UNAVAILABLE",
                    "reason": case.get("tier_reason") or "EVENT_ONLY_NO_CLIENT_REQUEST_CAPTURE",
                }
            )
        return {
            "t0": {"status": _status(t0), "checks": t0},
            "t1": {
                "status": "UNAVAILABLE",
                "reason": case.get("tier_reason") or "EVENT_ONLY_NO_CLIENT_REQUEST_CAPTURE",
                "rows": _row_counts(case, evaluated=t1),
            },
            "rows": [],
        }
    calls_bytes = data.get("calls_bytes")
    if calls_bytes is not None:
        t0.append(
            _check("client_calls_sha256", expected["client_calls_sha256"], sha256_bytes(calls_bytes))
        )
        calls_rows, malformed_calls = read_jsonl(calls_bytes)
    else:  # pragma: no cover - a captured case always supplies bytes
        calls_rows, malformed_calls = data.get("calls_rows") or [], 0
    t0.append(_check("malformed_call_lines", expected["malformed_call_lines"], malformed_calls))
    parsed = parse_call_log(calls_rows)
    for key in data.get("drop_blob_keys") or []:
        parsed["blobs"].pop(key, None)
    for seq, role in (data.get("role_patch") or {}).items():
        if seq in parsed["starts"]:
            parsed["starts"][seq] = {**parsed["starts"][seq], "role": role}
    swap = data.get("response_swap")
    if swap:
        left, right = swap
        if left in parsed["ends"] and right in parsed["ends"]:
            parsed["ends"][left], parsed["ends"][right] = (
                {**parsed["ends"][right], "seq": left},
                {**parsed["ends"][left], "seq": right},
            )
    role_counts: dict[str, int] = {}
    for row in parsed["starts"].values():
        role = str(row.get("role"))
        role_counts[role] = role_counts.get(role, 0) + 1
    t0.append(_check("role_counts", expected["role_counts"], dict(sorted(role_counts.items()))))
    t0.append(
        _check_true(
            "index_rows_declared",
            expected["index_rows"] == len(declared_rows),
            {"expected": expected["index_rows"], "rows": len(declared_rows)},
        )
    )
    failures: list[dict] = []
    for row in declared_rows:
        ordinal = row.get("model_ordinal")
        row_checks: list[dict] = []
        seq = row.get("client_call_seq")
        start = parsed["starts"].get(seq)
        end = parsed["ends"].get(seq)
        row_checks.append(_check_true("seq_present", start is not None and end is not None, seq))
        if start is None or end is None:
            failures.append(_failure(ordinal, row_checks))
            continue
        row_checks.append(_check("role", row.get("role"), str(start.get("role"))))
        request = start.get("request") or {}
        row_checks.append(
            _check("tools_present", row.get("tools_present"), "tools" in request)
        )
        row_checks.append(
            _check(
                "request_record_sha256",
                row.get("request_record_sha256"),
                sha256_bytes(canonical(request)),
            )
        )
        trace_index = row.get("trace_event_index")
        event = events[trace_index] if isinstance(trace_index, int) and trace_index < len(events) else None
        row_checks.append(
            _check_true(
                "trace_event_index_is_model",
                bool(event and event.get("event") == "model"),
                {"trace_event_index": trace_index},
            )
        )
        if event is not None:
            signature_trace = provider_action_signature(event)
            response = resolved_response(end, parsed["blobs"])
            signature_calls = provider_action_signature(response) if response is not None else None
            row_checks.append(
                _check_true(
                    "action_signature_join",
                    row.get("response_action_signature") is not None
                    and row.get("response_action_signature") == signature_trace == signature_calls,
                    {
                        "row": row.get("response_action_signature"),
                        "trace": signature_trace,
                        "calls": signature_calls,
                    },
                )
            )
            actions, protocol = selected_actions(event)
            row_checks.append(_check("action_protocol", row.get("action_protocol"), protocol))
            row_checks.append(
                _check(
                    "selected_action_names",
                    row.get("selected_action_names"),
                    [a[0] for a in actions],
                )
            )
            row_checks.append(
                _check(
                    "reasoning_field_present",
                    row.get("reasoning_field_present"),
                    row_bool(event.get("reasoning")),
                )
            )
        row_checks.append(_check("fidelity", row.get("fidelity"), EXACT_FIDELITY))
        row_t0_status = _status(row_checks)
        # T1: expand the captured request and compare the canonical form against the frozen SHA.
        resolved, misses = expand_request(request, parsed["blobs"])
        resolved_bytes = canonical(resolved)
        tools = resolved.get("tools") or []
        messages = resolved.get("messages", resolved.get("input", []))
        t1_checks = [
            _check_true("blobs_resolved", not misses, {"misses": misses[:4], "count": len(misses)}),
            _check("resolved_request_sha256", row.get("resolved_request_sha256"), sha256_bytes(resolved_bytes)),
            _check(
                "resolved_request_json_utf8_bytes",
                row.get("resolved_request_json_utf8_bytes"),
                len(resolved_bytes),
            ),
            _check("message_count", row.get("message_count"), len(messages)),
            _check("tool_schema_sha256", row.get("tool_schema_sha256"), sha256_bytes(canonical(tools))),
        ]
        row_t1_status = _status(t1_checks)
        rows_out.append(
            {
                "model_ordinal": ordinal,
                "client_call_seq": seq,
                "t0": row_t0_status,
                "t1": row_t1_status,
                "t0_checks": [c for c in row_checks if not c["ok"]],
                "t1_checks": [c for c in t1_checks if not c["ok"]],
            }
        )
        if row_t0_status != "PASS" or row_t1_status != "PASS":
            failures.append(_failure(ordinal, row_checks + t1_checks))
    row_t0_failures = [r for r in rows_out if r["t0"] != "PASS"]
    t0.append(
        _check_true(
            "rows_t0_all_pass",
            not row_t0_failures,
            {"rows": len(rows_out), "failed": len(row_t0_failures)},
        )
    )
    t0_status = _status(t0)
    t1_failures = [r for r in rows_out if r["t1"] != "PASS"]
    t1_status = "PASS" if t0_status == "PASS" and not t1_failures else "FAIL"
    return {
        "t0": {"status": t0_status, "checks": t0},
        "t1": {"status": t1_status, "rows": _row_counts(case, rows_out=rows_out)},
        "rows": rows_out,
        "failures": failures[:MAX_FAILURES_PER_CASE],
        "failure_count": len(failures),
    }


def _failure(ordinal: Any, checks: list[dict]) -> dict:
    return {
        "model_ordinal": ordinal,
        "failed_checks": [c for c in checks if not c["ok"]][:6],
    }


def _row_counts(case: dict, *, rows_out: list[dict] | None = None, evaluated: list[dict] | None = None) -> dict:
    expected_rows = len(case.get("requests") or [])
    if evaluated is not None:
        unavailable = sum(1 for r in evaluated if r.get("status") == "UNAVAILABLE")
        return {
            "expected": expected_rows,
            "checked": 0,
            "pass": 0,
            "fail": 0,
            "unavailable": unavailable,
        }
    rows_out = rows_out or []
    return {
        "expected": expected_rows,
        "checked": len(rows_out),
        "pass": sum(1 for r in rows_out if r["t0"] == "PASS" and r["t1"] == "PASS"),
        "fail": sum(1 for r in rows_out if r["t0"] != "PASS" or r["t1"] != "PASS"),
        "unavailable": 0,
    }


def evaluate_manifest(
    manifest: dict, root_map: dict, *, index_rows: list[dict] | None = None
) -> dict:
    """Run T0/T1 over the whole manifest; returns the results section (no writes)."""
    corpus_problems = validate_manifest(manifest)
    t0_cases: list[dict] = []
    t1_cases: list[dict] = []
    t0_counts = {"cases": 0, "pass": 0, "fail": 0, "unavailable": 0}
    t1_counts = {"rows_expected": 0, "rows_checked": 0, "pass": 0, "fail": 0, "unavailable": 0}
    for case in manifest["cases"]:
        path, reason = resolve_symbol(case["source_symbol"], root_map)
        data: dict = {"path": path, "present": path is not None}
        if path is not None:
            data["trace_bytes"] = path.read_bytes()
            calls_path = path.with_name("core_calls.jsonl")
            data["calls_present"] = calls_path.is_file()
            if data["calls_present"]:
                data["calls_bytes"] = calls_path.read_bytes()
        else:
            data["reason"] = reason
        evaluated = evaluate_case(case, data)
        # Optional second oracle: the manifest's expected row values against a fresh index copy.
        oracle_checks = []
        if index_rows is not None and data.get("present"):
            fresh = index_rows_for(
                index_rows, case["cohort"], case["archive_case"], case["expected"]["trace_sha256"]
            )
            by_ordinal = {r.get("model_ordinal"): r for r in fresh}
            mismatches = 0
            for row in case["requests"]:
                fresh_row = by_ordinal.get(row["model_ordinal"])
                if fresh_row is None:
                    mismatches += 1
                    continue
                for field in (
                    "client_call_seq",
                    "request_record_sha256",
                    "resolved_request_sha256",
                    "message_count",
                    "tool_schema_sha256",
                    "action_protocol",
                ):
                    if fresh_row.get(field) != row.get(field):
                        mismatches += 1
            oracle_checks.append(
                _check_true(
                    "frozen_index_agrees",
                    mismatches == 0,
                    {"mismatches": mismatches, "rows": len(case["requests"])},
                )
            )
        record = {
            "case_key": case["case_key"],
            "family": case["family"],
            "t0": evaluated["t0"],
            "t1": evaluated["t1"],
            "oracle": oracle_checks,
            "failures": evaluated.get("failures", []),
            "failure_count": evaluated.get("failure_count", 0),
            "rows": evaluated.get("rows", []),
        }
        t0_cases.append(record)
        t1_cases.append(record)
        t0_counts["cases"] += 1
        t0_status = evaluated["t0"]["status"]
        oracle_ok = all(c["ok"] for c in oracle_checks)
        if t0_status == "PASS" and oracle_ok:
            t0_counts["pass"] += 1
        elif t0_status == "UNAVAILABLE":
            t0_counts["unavailable"] += 1
        else:
            t0_counts["fail"] += 1
        counts = evaluated["t1"]["rows"]
        t1_counts["rows_expected"] += counts["expected"]
        t1_counts["rows_checked"] += counts["checked"]
        t1_counts["pass"] += counts["pass"]
        t1_counts["fail"] += counts["fail"]
        t1_counts["unavailable"] += counts["unavailable"]
        if evaluated["t1"]["status"] == "UNAVAILABLE":
            t1_counts["unavailable_cases"] = t1_counts.get("unavailable_cases", 0) + 1
    return {
        "corpus_problems": corpus_problems,
        "t0": {"counts": t0_counts, "cases": t0_cases},
        "t1": {"counts": t1_counts},
    }


def validate_manifest(manifest: dict) -> list[dict]:
    """Structural and identity problems that make a manifest unusable (never silently ignored)."""
    problems: list[dict] = []
    if manifest.get("schema") != CORPUS_SCHEMA:
        problems.append({"problem": "SCHEMA", "observed": manifest.get("schema")})
    keys: dict[str, int] = {}
    seen_identity: dict[str, str] = {}
    for case in manifest.get("cases") or []:
        keys[case["case_key"]] = keys.get(case["case_key"], 0) + 1
        identity = f"{case['cohort']}:{case['archive_case']}:{case['expected']['trace_sha256']}"
        if identity in seen_identity and seen_identity[identity] != case["case_key"]:
            problems.append(
                {
                    "problem": "DUPLICATE_SOURCE_IDENTITY",
                    "identity": identity,
                    "cases": [seen_identity[identity], case["case_key"]],
                }
            )
        seen_identity[identity] = case["case_key"]
        expected = case["expected"]
        if expected["client_capture_present"] and not expected.get("client_calls_sha256"):
            problems.append({"problem": "CAPTURE_WITHOUT_DIGEST", "case": case["case_key"]})
        if not expected["client_capture_present"]:
            for row in case.get("requests") or []:
                if row.get("request_record_sha256") is not None or row.get("resolved_request_sha256") is not None:
                    problems.append(
                        {
                            "problem": "FABRICATED_EVENT_ONLY_REQUEST",
                            "case": case["case_key"],
                            "model_ordinal": row.get("model_ordinal"),
                        }
                    )
    for key, count in keys.items():
        if count > 1:
            problems.append({"problem": "DUPLICATE_CASE_KEY", "case_key": key, "count": count})
    return problems


# --------------------------------------------------------------------------------------------
# Negative controls: corrupt one input, require the same evaluator to report failure
# --------------------------------------------------------------------------------------------


def run_negative_controls(manifest: dict, root_map: dict) -> dict:
    controls: list[dict] = []
    captured = [
        c for c in manifest["cases"] if c["expected"]["client_capture_present"] and c.get("requests")
    ]
    event_only = [c for c in manifest["cases"] if not c["expected"]["client_capture_present"]]
    if not captured:
        return {"controls": [], "counts": {"expected_fail": 0, "detected": 0}, "reason": "NO_CAPTURED_CASE"}

    def load(case: dict) -> dict:
        path, reason = resolve_symbol(case["source_symbol"], root_map)
        if path is None:
            return {"present": False, "reason": reason}
        calls_path = path.with_name("core_calls.jsonl")
        return {
            "path": path,
            "present": True,
            "trace_bytes": path.read_bytes(),
            "calls_present": calls_path.is_file(),
            "calls_bytes": calls_path.read_bytes() if calls_path.is_file() else None,
        }

    def record(control: str, case: dict, observed: dict, detail: dict | None = None) -> None:
        status = observed["status"]
        controls.append(
            {
                "control": control,
                "case_key": case["case_key"],
                "expected": "FAIL",
                "observed": status,
                "detected": status == "FAIL",
                "detail": detail or {},
            }
        )

    base = captured[0]
    data = load(base)

    # 1. One changed source byte must break the source digest.
    mutated = bytearray(data["trace_bytes"])
    position = len(mutated) // 2
    mutated[position] = (mutated[position] + 1) % 256
    observed = evaluate_case(base, {**data, "trace_bytes": bytes(mutated)})
    t0_ok = observed["t0"]["status"] == "FAIL"
    record(
        "changed_source_byte",
        base,
        {"status": "FAIL" if t0_ok else observed["t0"]["status"]},
        {"mutated_offset": position},
    )

    # 2. A removed blob must make T1 unresolved (never silently accepted).
    expired: dict | None = None
    for row in base["requests"]:
        start_seq = row.get("client_call_seq")
        observed_calls = parse_call_log(read_jsonl(data["calls_bytes"])[0]) if data["calls_bytes"] else None
        if observed_calls and start_seq in observed_calls["starts"]:
            request = observed_calls["starts"][start_seq].get("request") or {}
            for candidate in [request.get("messages"), request.get("tools"), request.get("params")]:
                if isinstance(candidate, list):
                    for item in candidate:
                        if isinstance(item, str) and item in observed_calls["blobs"]:
                            expired = {"seq": start_seq, "key": item}
                            break
                elif isinstance(candidate, str) and candidate in observed_calls["blobs"]:
                    expired = {"seq": start_seq, "key": candidate}
                if expired:
                    break
        if expired:
            break
    if expired:
        observed = evaluate_case(base, {**data, "drop_blob_keys": [expired["key"]]})
        record(
            "unresolved_blob",
            base,
            {"status": observed["t1"]["status"]},
            {"client_call_seq": expired["seq"], "dropped_blob_digest": sha256_text(expired["key"])},
        )
    else:  # pragma: no cover - captured cases always carry blob references
        record("unresolved_blob", base, {"status": "NOT_RUN"}, {"reason": "NO_BLOB_REFERENCE_FOUND"})

    # 3. A role swap must be caught.
    worker_seq = next(
        (row["client_call_seq"] for row in base["requests"] if row.get("role") == "worker"), None
    )
    if worker_seq is not None:
        observed = evaluate_case(
            base, {**data, "role_patch": {worker_seq: "checkpoint"}}
        )
        record("incorrect_role", base, {"status": observed["t0"]["status"]}, {"client_call_seq": worker_seq})

    # 4. Swapping two decisions' responses must break the action association.
    pairs = [r["client_call_seq"] for r in base["requests"]][:2]
    if len(pairs) == 2:
        observed = evaluate_case(base, {**data, "response_swap": (pairs[0], pairs[1])})
        record(
            "wrong_action_association",
            base,
            {"status": observed["t0"]["status"]},
            {"client_call_seqs": pairs},
        )

    # 5. A duplicated case key must be rejected structurally.
    if len(manifest["cases"]) >= 2:
        doubled = copy.deepcopy(manifest)
        doubled["cases"][1]["case_key"] = doubled["cases"][0]["case_key"]
        problems = validate_manifest(doubled)
        detected = any(p["problem"] == "DUPLICATE_CASE_KEY" for p in problems)
        record(
            "duplicate_case_alias",
            manifest["cases"][1],
            {"status": "FAIL" if detected else "PASS"},
            {"problems": [p["problem"] for p in problems]},
        )

    # 6. A modified expected canonical SHA must be caught (the frozen SHA is the oracle).
    patched = copy.deepcopy(base)
    target = patched["requests"][0]
    original = target["resolved_request_sha256"]
    target["resolved_request_sha256"] = ("0" if original[:1] != "0" else "1") + original[1:]
    observed = evaluate_case(patched, data)
    record(
        "mismatched_expected_request_sha",
        base,
        {"status": observed["t1"]["status"]},
        {"model_ordinal": target.get("model_ordinal")},
    )

    # 7. An event-only case must never accept an invented request.
    if event_only:
        fabricated = copy.deepcopy(event_only[0])
        fabricated["requests"][0]["resolved_request_sha256"] = "0" * 64
        problems = validate_manifest({"schema": CORPUS_SCHEMA, "cases": [fabricated]})
        detected = any(p["problem"] == "FABRICATED_EVENT_ONLY_REQUEST" for p in problems)
        record(
            "fabricated_event_only_request",
            event_only[0],
            {"status": "FAIL" if detected else "PASS"},
            {"problems": [p["problem"] for p in problems]},
        )

    detected = sum(1 for c in controls if c["detected"])
    return {
        "controls": controls,
        "counts": {"expected_fail": len(controls), "detected": detected},
    }


# --------------------------------------------------------------------------------------------
# T2: the real Core loop with scripted provider responses and inert historical playback
# --------------------------------------------------------------------------------------------


class NoProcessReplayEnv:
    """Fail-closed environment for scripted Core-loop playback; it never launches a process."""

    def __init__(
        self,
        root: Path,
        playback: dict[str, str],
        playback_sequences: dict[str, list[str]] | None = None,
    ) -> None:
        self.root = root
        self.playback = {sha256_text(action): observation for action, observation in playback.items()}
        self.playback_sequences = {
            sha256_text(action): list(observations)
            for action, observations in (playback_sequences or {}).items()
        }
        overlap = self.playback.keys() & self.playback_sequences.keys()
        if overlap:
            raise ValueError("an exact action cannot use both scalar and sequence playback")
        self.playback_sequence_positions = {key: 0 for key in self.playback_sequences}
        self.setup_command = f"mkdir -p {shlex.quote(str(root / 'control'))}"
        self.exec_request_hashes: list[str] = []
        self.blocked_exec_hashes: list[str] = []
        self.terminal_action_hashes: list[str] = []
        self.playback_hits: list[str] = []
        self.blocked_actions: list[str] = []
        self.playback_sequence_hits: list[dict[str, Any]] = []
        self.upload_calls = 0
        self.download_calls = 0
        self.process_launches = 0

    def terminal_observation(self, action: str, *, mode: str, interrupt: bool) -> str:
        """Return a scalar or next exact-action observation; mismatches never advance a queue."""
        action_hash = sha256_text(action)
        self.terminal_action_hashes.append(action_hash)
        if mode != "command" or interrupt:
            self.blocked_actions.append(action_hash)
            return "[playback blocked: no exact recorded observation; action not executed]"
        if action_hash in self.playback_sequences:
            position = self.playback_sequence_positions[action_hash]
            observations = self.playback_sequences[action_hash]
            if position >= len(observations):
                self.blocked_actions.append(action_hash)
                return "[playback blocked: no exact recorded observation; action not executed]"
            observation = observations[position]
            self.playback_sequence_positions[action_hash] = position + 1
            self.playback_hits.append(action_hash)
            self.playback_sequence_hits.append(
                {
                    "action_sha256": action_hash,
                    "sequence_index": position,
                    "observation_sha256": sha256_text(observation),
                }
            )
            return observation
        if action_hash in self.playback:
            self.playback_hits.append(action_hash)
            return self.playback[action_hash]
        self.blocked_actions.append(action_hash)
        return "[playback blocked: no exact recorded observation; action not executed]"

    def remaining_playback_sequences(self) -> dict[str, int]:
        return {
            action_hash: len(observations) - self.playback_sequence_positions[action_hash]
            for action_hash, observations in self.playback_sequences.items()
        }

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        digest = sha256_text(command)
        self.exec_request_hashes.append(digest)
        if command == self.setup_command:
            return SimpleNamespace(return_code=0, stdout="", stderr="")
        self.blocked_exec_hashes.append(digest)
        return SimpleNamespace(
            return_code=125,
            stdout="",
            stderr="process execution disabled in replay environment",
        )

    async def upload_file(self, source_path: Any, target_path: str) -> None:
        self.upload_calls += 1
        raise RuntimeError("file transfer disabled in scripted playback")

    async def download_file(self, source_path: str, target_path: Any) -> None:
        self.download_calls += 1
        raise RuntimeError("file transfer disabled in scripted playback")


def chunk(
    content: str = "",
    reasoning: str = "",
    tool_calls: list | None = None,
    finish: str | None = None,
    usage: dict | None = None,
) -> Any:
    delta = SimpleNamespace(
        content=content or None,
        reasoning_content=reasoning or None,
        tool_calls=tool_calls,
        model_extra={},
    )
    choices = (
        [SimpleNamespace(delta=delta, finish_reason=finish)]
        if (content or reasoning or tool_calls or finish)
        else []
    )
    return SimpleNamespace(
        choices=choices,
        usage=SimpleNamespace(model_dump=lambda: usage) if usage else None,
    )


def tool_chunk(name: str, args: dict, index: int = 0, call_id: str = "c1") -> Any:
    return chunk(
        tool_calls=[
            SimpleNamespace(
                index=index,
                id=call_id,
                function=SimpleNamespace(name=name, arguments=json.dumps(args)),
            )
        ]
    )


class _Stream:
    def __init__(self, chunks: list) -> None:
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class ScriptedClient:
    """``client.chat.completions.create`` returning scripted streams; never touches a network."""

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any):
        self.requests.append(kwargs)
        if not self.script:
            raise RuntimeError("scripted provider exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Stream(item)


def scripted_call(name: str, args: dict, call_id: str = "c1") -> list:
    return [
        chunk(reasoning="scripted turn"),
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 100, "completion_tokens": 10}),
    ]


def run_scripted(
    script: list,
    task: str,
    *,
    playback: dict[str, str] | None = None,
    playback_sequences: dict[str, list[str]] | None = None,
    capture_provider_requests: bool = False,
    model: str = "flint",
    params: dict | None = None,
    timeout_s: float = 60.0,
) -> dict:
    """Run the actual Core loop with scripted provider turns and no process-capable environment."""
    from aether.core.loop import CoreConfig, Trace, run_agent
    from aether.core.provider import ChatProvider
    from aether.core.terminal import Terminals

    root = Path(tempfile.mkdtemp(prefix="aether-c1-t2-"))
    (root / "work").mkdir()
    env = NoProcessReplayEnv(root, playback or {}, playback_sequences)
    client = ScriptedClient(script)
    provider = ChatProvider(
        client,
        model=model,
        params=dict(params or {}),
        sleep=lambda _delay: asyncio.sleep(0),
        log=None,
    )
    trace_path = root / "core_trace.jsonl"
    started = time.monotonic()
    error = None
    result = None

    async def inert_terminal_use(
        terminal: Any,
        *,
        name: str = "main",
        input: str = "",
        mode: str = "command",
        wait_s: float = 30.0,
        interrupt: bool = False,
    ) -> str:
        return env.terminal_observation(str(input), mode=mode, interrupt=interrupt)

    original_use = Terminals.use
    original_shell = asyncio.create_subprocess_shell
    original_exec = asyncio.create_subprocess_exec

    def forbidden_process(*_args: Any, **_kwargs: Any) -> Any:
        env.process_launches += 1
        raise RuntimeError("process creation disabled in scripted playback")

    Terminals.use = inert_terminal_use
    asyncio.create_subprocess_shell = forbidden_process
    asyncio.create_subprocess_exec = forbidden_process
    try:
        result = asyncio.run(
            run_agent(
                env=env,
                task=task,
                workdir=str(root / "work"),
                provider=provider,
                timeout_s=timeout_s,
                trace=Trace(trace_path),
                config=CoreConfig(control_dir=str(root / "control")),
            )
        )
    except Exception as exc:
        # Keep errors useful for diagnosis without exposing task/provider payloads.
        error = type(exc).__name__
    finally:
        Terminals.use = original_use
        asyncio.create_subprocess_shell = original_shell
        asyncio.create_subprocess_exec = original_exec

    trace_rows = []
    try:
        if trace_path.is_file():
            trace_rows = [json.loads(line) for line in trace_path.read_text().split("\n") if line.strip()]
    except Exception as exc:
        error = error or f"TRACE_READ_{type(exc).__name__}"
        trace_rows = []
    elapsed = round(time.monotonic() - started, 3)
    shutil.rmtree(root, ignore_errors=True)
    temporary_workdirs_removed = not root.exists()
    return {
        "env": env,
        "result": result,
        "error": error,
        "trace": trace_rows,
        "elapsed_s": elapsed,
        "provider_requests": client.requests if capture_provider_requests else None,
        "temporary_workdirs_removed": temporary_workdirs_removed,
    }


def _tool_messages(trace: list[dict]) -> list[dict]:
    return [r for r in trace if r.get("event") == "tool"]


def _load_case_for_t2(manifest: dict, root_map: dict, family: str | None = None) -> dict | None:
    for case in manifest["cases"]:
        if not case["expected"]["client_capture_present"]:
            continue
        if family and case["family"] != family:
            continue
        path, _ = resolve_symbol(case["source_symbol"], root_map)
        if path is None or not path.with_name("core_calls.jsonl").is_file():
            continue
        return case
    return None


def _case_archive(case: dict, root_map: dict) -> dict:
    path, reason = resolve_symbol(case["source_symbol"], root_map)
    if path is None:
        raise RuntimeError(reason)
    calls_path = path.with_name("core_calls.jsonl")
    events, _ = read_jsonl(path.read_bytes())
    calls_rows, _ = read_jsonl(calls_path.read_bytes())
    parsed = parse_call_log(calls_rows)
    first = next(r for r in case["requests"] if r.get("fidelity") == EXACT_FIDELITY)
    start = parsed["starts"][first["client_call_seq"]]
    resolved, misses = expand_request(start.get("request") or {}, parsed["blobs"])
    if misses:
        raise RuntimeError(f"unresolved blobs for {case['case_key']}")
    return {
        "events": events,
        "parsed": parsed,
        "first_row": first,
        "resolved": resolved,
        "start_role": start.get("role"),
    }


def t2_controls(manifest: dict, root_map: dict) -> dict:
    controls: list[dict] = []
    core_path = ""
    try:
        import aether.core as core_pkg
        from aether.core.provider import ChatProvider
        from aether.core.tools import tools as core_tools
        core_path = str(getattr(core_pkg, "__file__", ""))
    except Exception as exc:
        return {
            "controls": [],
            "counts": {"pass": 0, "fail": 0, "unavailable": 1},
            "reason": f"AETHER_CORE_UNAVAILABLE: {type(exc).__name__}: {exc}",
            "core_module": core_path,
        }

    serializer_case = _load_case_for_t2(manifest, root_map, "flint-polyglot") or _load_case_for_t2(
        manifest, root_map
    )
    if serializer_case is not None:
        controls.append(_t2_serializer(serializer_case, root_map, ChatProvider, core_tools))

    terminal_case = _load_case_for_t2(manifest, root_map, "flint-terminal") or serializer_case
    if terminal_case is None:
        controls.append({
            "control": "t2-exact-historical-terminal-observation",
            "status": "UNAVAILABLE",
            "reason": "NO_CAPTURED_TERMINAL_CASE",
            "checks": [],
            "evidence": {},
        })
    else:
        controls.append(_t2_inert_playback(terminal_case, root_map))

    passed = sum(1 for c in controls if c["status"] == "PASS")
    unavailable = sum(1 for c in controls if c["status"] == "UNAVAILABLE")
    return {
        "controls": controls,
        "counts": {"pass": passed, "fail": len(controls) - passed - unavailable, "unavailable": unavailable},
        "core_module": core_path,
        "core_module_sha256": sha256_bytes(Path(core_path).read_bytes()) if core_path and Path(core_path).is_file() else None,
        "execution_boundary": "in-process Terminal-use playback adapter; no host shell or process API",
    }


def _t2_serializer(case: dict, root_map: dict, ChatProvider, core_tools) -> dict:
    """The provider adapter preserves the captured context it is given and adds only its own stream flags."""
    checks: list[dict] = []
    evidence: dict[str, Any] = {"case_key": case["case_key"], "label": "SYNTHETIC/REPLAYED_REQUEST"}
    try:
        archive = _case_archive(case, root_map)
    except Exception as exc:
        return {"control": "t2-serializer-passthrough-and-sampling", "status": "FAIL", "checks": [_check_true("archive_loaded", False, {"error": str(exc)[:200]})], "evidence": evidence}
    resolved = archive["resolved"]
    messages = resolved.get("messages", resolved.get("input", []))
    archived_tools = resolved.get("tools") or []
    archived_params = resolved.get("params") or {}
    sampling = {k: archived_params[k] for k in SAMPLING_KEYS if k in archived_params}
    evidence["archived_sampling_keys"] = sorted(sampling)
    evidence["archived_has_top_k"] = "top_k" in archived_params
    provider = ChatProvider(ScriptedClient([]), model=str(resolved.get("model") or ""), params=sampling)
    request = provider._request(messages, archived_tools, 16_384, None)
    checks.append(_check_true("model_preserved", request.get("model") == resolved.get("model"), request.get("model")))
    checks.append(
        _check_true(
            "messages_preserved_canonical_sha",
            sha256_bytes(canonical(request.get("messages"))) == sha256_bytes(canonical(messages)),
        )
    )
    checks.append(
        _check_true(
            "tools_preserved_canonical_sha",
            sha256_bytes(canonical(request.get("tools"))) == sha256_bytes(canonical(archived_tools)),
        )
    )
    produced_params = request.get("params") or {}
    added = sorted(set(produced_params) - set(archived_params))
    evidence["core_added_param_keys"] = added
    checks.append(
        _check_true(
            "sampling_values_preserved",
            all(produced_params.get(k) == v for k, v in sampling.items()),
            {k: produced_params.get(k) for k in sorted(sampling)},
        )
    )
    checks.append(_check_true("no_invented_top_k", "top_k" not in produced_params, "top_k" in produced_params))
    checks.append(_check_true("stream_requested", produced_params.get("stream") is True))
    checks.append(
        _check_true(
            "usage_in_stream_options",
            produced_params.get("stream_options") == {"include_usage": True},
        )
    )
    current_tools = [t["function"]["name"] for t in core_tools(python=False, images=False, history=False, verdict=False)]
    archived_names = [t.get("function", {}).get("name") for t in archived_tools]
    evidence["archived_tool_names"] = archived_names
    evidence["current_core_tool_names"] = current_tools
    evidence["tool_name_set_equal"] = sorted(archived_names) == sorted(current_tools)
    return {
        "control": "t2-serializer-passthrough-and-sampling",
        "status": _status(checks),
        "checks": checks,
        "evidence": evidence,
        "limit": "proves adapter passthrough + sampling assembly, not that current Core builds the historical context",
    }


def _t2_scripted_action_playback(action: str, observation: str, label: str) -> dict:
    """Run exact and transformed actions through Core dispatch with a no-process playback adapter."""
    exact_hash = sha256_text(action)
    transformed = action + " __AETHER_REPLAY_MUTATION__"
    scripted_task = "Use the supplied terminal observation, then finish."
    exact = run_scripted(
        [
            scripted_call("terminal", {"input": action}, "exact-1"),
            scripted_call("finish", {"summary": "scripted"}, "exact-2"),
        ],
        scripted_task,
        playback={action: observation},
    )
    transformed_run = run_scripted(
        [
            scripted_call("terminal", {"input": transformed}, "mutated-1"),
            scripted_call("finish", {"summary": "scripted"}, "mutated-2"),
        ],
        scripted_task,
        playback={action: observation},
    )

    exact_tools = [row for row in _tool_messages(exact["trace"]) if row.get("name") == "terminal"]
    transformed_tools = [
        row for row in _tool_messages(transformed_run["trace"]) if row.get("name") == "terminal"
    ]
    exact_result = exact_tools[0].get("result") if exact_tools else None
    transformed_result = transformed_tools[0].get("result") if transformed_tools else None
    checks = [
        _check_true(
            "exact_replay_finishes",
            exact["result"] is not None and exact["result"].status == "finished",
            exact["result"].status if exact["result"] else exact["error"],
        ),
        _check("exact_action_hash", [exact_hash], exact["env"].playback_hits),
        _check("captured_observation_delivered_exactly", observation, exact_result),
        _check("transformed_action_blocked", [sha256_text(transformed)], transformed_run["env"].blocked_actions),
        _check_true(
            "transformed_run_does_not_receive_captured_observation",
            transformed_result != observation,
            sha256_text(str(transformed_result or "")),
        ),
        _check_true("no_file_transfers", exact["env"].upload_calls == 0 and exact["env"].download_calls == 0),
        _check_true(
            "no_environment_process_execution",
            exact["env"].process_launches == 0 and transformed_run["env"].process_launches == 0,
            {
                "exact_environment_requests": len(exact["env"].exec_request_hashes),
                "exact_blocked_requests": len(exact["env"].blocked_exec_hashes),
                "transformed_environment_requests": len(transformed_run["env"].exec_request_hashes),
            },
        ),
    ]
    return {
        "control": "t2-exact-historical-terminal-observation",
        "status": _status(checks),
        "checks": checks,
        "evidence": {
            "case_key": label,
            "action_sha256": exact_hash,
            "observation_sha256": sha256_text(observation),
            "observation_bytes": len(observation.encode("utf-8")),
            "exact_terminal_attempts": exact["env"].terminal_action_hashes,
            "transformed_terminal_attempts": transformed_run["env"].terminal_action_hashes,
            "playback_hits": len(exact["env"].playback_hits),
            "blocked_actions": len(transformed_run["env"].blocked_actions),
            "temporary_trace_and_workdirs_removed": True,
        },
        "limit": "actual Core provider/loop/tool-dispatch path with fixture-backed Terminal-use results; no host process, terminal, or task-filesystem effects, model reaction, task completion, or grade claim",
    }


def _t2_inert_playback(case: dict, root_map: dict) -> dict:
    """Play one captured terminal observation at Core dispatch; never invoke the host terminal."""
    evidence: dict[str, Any] = {"case_key": case["case_key"]}
    archive = _case_archive(case, root_map)
    events = archive["events"]
    for row in case["requests"]:
        event_index = row["trace_event_index"]
        event = events[event_index]
        for call in event.get("tool_calls") or []:
            name, args = call_function(call)
            if name != "terminal":
                continue
            action = str((args or {}).get("input") or "")
            if not action:
                continue
            matches = []
            for item in events[event_index + 1 :]:
                if item.get("event") == "model":
                    break
                if (
                    item.get("event") == "tool"
                    and item.get("name") == "terminal"
                    and canonical(item.get("args") or {}) == canonical(args or {})
                ):
                    matches.append(item)
            if len(matches) == 1 and matches[0].get("result"):
                result = _t2_scripted_action_playback(action, str(matches[0]["result"]), case["case_key"])
                result["evidence"].update(trace_event_index=event_index, matching_results=1)
                return result

    return {
        "control": "t2-exact-historical-terminal-observation",
        "status": "UNAVAILABLE",
        "reason": "NO_RECORDED_TERMINAL_ACTION_WITH_OBSERVATION",
        "checks": [],
        "evidence": evidence,
        "limit": "no command is executed when archived observation playback is unavailable",
    }


# --------------------------------------------------------------------------------------------
# Result assembly and CLI
# --------------------------------------------------------------------------------------------


def _count_families(manifest: dict) -> dict:
    counts = {"families": len(manifest.get("families") or []), "cases": len(manifest.get("cases") or [])}
    counts["rows"] = sum(len(c.get("requests") or []) for c in manifest.get("cases") or [])
    counts["cases_with_capture"] = sum(
        1 for c in manifest.get("cases") or [] if c["expected"]["client_capture_present"]
    )
    counts["cases_event_only"] = counts["cases"] - counts["cases_with_capture"]
    return counts


def _root_resolution(manifest: dict, root_map: dict) -> list[dict]:
    rows = []
    for symbol in manifest.get("root_symbols") or []:
        configured = symbol in root_map
        present = configured and Path(root_map[symbol]).is_dir()
        rows.append({"symbol": f"${symbol}", "configured": configured, "present": bool(present)})
    return rows


def _manifest_digest(manifest: dict) -> str:
    return sha256_bytes(canonical(manifest))


def run_all(manifest: dict, root_map: dict, *, index_rows: list[dict] | None = None) -> dict:
    evaluation = evaluate_manifest(manifest, root_map, index_rows=index_rows)
    negatives = run_negative_controls(manifest, root_map)
    t2 = t2_controls(manifest, root_map)
    sources = manifest.get("sources") or {}
    results = {
        "schema": RESULTS_SCHEMA,
        "tool": TOOL_VERSION,
        "archive_commit": manifest.get("archive_commit"),
        "manifest_sha256": _manifest_digest(manifest),
        "sources": {
            "request_index_sha256": sources.get("request_index_sha256"),
            "coverage_dashboard_sha256": sources.get("coverage_dashboard_sha256"),
            "selection_sha256": sources.get("selection_sha256"),
            "trace_cases_seed_sha256": sources.get("trace_cases_seed_sha256"),
        },
        "corpus": _count_families(manifest),
        "root_resolution": _root_resolution(manifest, root_map),
        "corpus_problems": evaluation["corpus_problems"],
        "t0": evaluation["t0"],
        "t1": evaluation["t1"],
        "negative_controls": negatives,
        "t2": t2,
        "gates": {
            "T3": "UNAVAILABLE C1-LINUX-BLOCKED (no native Linux x86 host, no historical VM snapshot)",
            "T4": "UNAVAILABLE C1-LINUX-BLOCKED (native x86 admission not satisfiable here)",
            "T6": "NOT_AUTHORIZED (no inference)",
        },
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    results["verdict"] = _verdict(results)
    return results


REQUIRED_NEGATIVES = {
    "changed_source_byte", "unresolved_blob", "incorrect_role", "wrong_action_association",
    "duplicate_case_alias", "mismatched_expected_request_sha", "fabricated_event_only_request",
}
REQUIRED_T2 = {"t2-serializer-passthrough-and-sampling", "t2-exact-historical-terminal-observation"}


def _negative_proof(payload: dict) -> bool:
    controls = payload.get("controls", [])
    return REQUIRED_NEGATIVES == {c.get("control") for c in controls} and all(
        c.get("detected") is True for c in controls
    )


def _t2_proof(payload: dict) -> bool:
    controls = payload.get("controls", [])
    return REQUIRED_T2 == {c.get("control") for c in controls} and all(
        c.get("status") == "PASS" for c in controls
    )


def _verdict(results: dict) -> dict:
    problems = []
    if results["corpus_problems"]:
        problems.append("CORPUS_PROBLEMS")
    t0, t1 = results["t0"]["counts"], results["t1"]["counts"]
    if not t0["cases"] or t0["pass"] != t0["cases"] or t0["unavailable"] or t0["fail"]:
        problems.append("T0_REQUIRED_PROOF_MISSING")
    if not t1["pass"] or t1["fail"] or t1["pass"] != t1["rows_checked"]:
        problems.append("T1_REQUIRED_PROOF_MISSING")
    if t1["rows_checked"] + t1["unavailable"] != t1["rows_expected"]:
        problems.append("T1_DENOMINATOR_MISMATCH")
    if not _negative_proof(results["negative_controls"]):
        problems.append("NEGATIVE_CONTROL_PROOF_MISSING")
    if not _t2_proof(results["t2"]):
        problems.append("T2_REQUIRED_PROOF_MISSING")
    for symbol in results["root_resolution"]:
        if not symbol["present"]:
            problems.append(f"ROOT_MISSING{symbol['symbol']}")
    return {"ok": not problems, "problems": problems}



def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text())


def _load_root_map(path: str | None, pairs: list[str] | None) -> dict:
    mapping: dict[str, str] = {}
    if path:
        mapping.update(_load_json(path))
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--root must be SYMBOL=PATH, got {pair!r}")
        name, _, value = pair.partition("=")
        mapping[name.lstrip("$")] = value
    return mapping


def _write(path: str | None, payload: dict) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _summary(results: dict) -> dict:
    t0 = results["t0"]["counts"]
    t1 = results["t1"]["counts"]
    negatives = results["negative_controls"]["counts"]
    t2 = results["t2"]["counts"]
    return {
        "verdict": results["verdict"],
        "corpus": results["corpus"],
        "t0": t0,
        "t1": t1,
        "negative_controls": negatives,
        "t2": t2,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build the source-bound corpus from the archives")
    build.add_argument("--seed", required=True, help="TRACE_CASES_SEED.json")
    build.add_argument("--selection", required=True, help="selection spec (family -> cases)")
    build.add_argument("--dashboard", required=True, help="ARCHIVE_COVERAGE_DASHBOARD json")
    build.add_argument("--index", required=True, help="ARCHIVE_MODEL_REQUEST_INDEX json")
    build.add_argument("--root", action="append", help="SYMBOL=PATH (repeatable)")
    build.add_argument("--root-map", help="operator root-map json")
    build.add_argument("--out", required=True)

    verify = sub.add_parser("verify", help="T0 + T1 against the manifest")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--index", help="optional frozen index for a second oracle")
    verify.add_argument("--root", action="append")
    verify.add_argument("--root-map")
    verify.add_argument("--out")

    controls = sub.add_parser("controls", help="negative controls only")
    controls.add_argument("--manifest", required=True)
    controls.add_argument("--root", action="append")
    controls.add_argument("--root-map")
    controls.add_argument("--out")

    t2 = sub.add_parser("t2", help="scripted real-loop controls only")
    t2.add_argument("--manifest", required=True)
    t2.add_argument("--root", action="append")
    t2.add_argument("--root-map")
    t2.add_argument("--out")

    every = sub.add_parser("all", help="T0 + T1 + negative controls + T2")
    every.add_argument("--manifest", required=True)
    every.add_argument("--index", help="optional frozen index for a second oracle")
    every.add_argument("--root", action="append")
    every.add_argument("--root-map")
    every.add_argument("--out")

    args = parser.parse_args(argv)
    root_map = _load_root_map(getattr(args, "root_map", None), getattr(args, "root", None))

    if args.command == "build":
        seed = _load_json(args.seed)
        selection = _load_json(args.selection)
        dashboard = _load_json(args.dashboard)
        index = _load_json(args.index)
        selection = dict(selection)
        selection.setdefault("sources", {})
        selection["sources"].update(
            {
                "request_index_sha256": sha256_bytes(Path(args.index).read_bytes()),
                "coverage_dashboard_sha256": sha256_bytes(Path(args.dashboard).read_bytes()),
                "selection_sha256": sha256_bytes(Path(args.selection).read_bytes()),
                "trace_cases_seed_sha256": sha256_bytes(Path(args.seed).read_bytes()),
            }
        )
        manifest = build_corpus(
            seed=seed, selection=selection, dashboard=dashboard, index=index, root_map=root_map
        )
        _write(args.out, manifest)
        print(json.dumps({"built": _count_families(manifest), "out": args.out}, sort_keys=True))
        return 0

    manifest = _load_json(args.manifest)
    if args.command == "verify":
        index_rows = _load_json(args.index)["rows"] if getattr(args, "index", None) else None
        evaluation = evaluate_manifest(manifest, root_map, index_rows=index_rows)
        payload = {
            "schema": RESULTS_SCHEMA,
            "tool": TOOL_VERSION,
            "archive_commit": manifest.get("archive_commit"),
            "manifest_sha256": _manifest_digest(manifest),
            "corpus": _count_families(manifest),
            "root_resolution": _root_resolution(manifest, root_map),
            **evaluation,
        }
        _write(args.out, payload)
        print(json.dumps({"t0": payload["t0"]["counts"], "t1": payload["t1"]["counts"], "corpus_problems": len(payload["corpus_problems"])}, sort_keys=True))
        return 0 if payload["t0"]["counts"]["fail"] == 0 and payload["t1"]["counts"]["fail"] == 0 and not payload["corpus_problems"] else 1

    if args.command == "controls":
        payload = run_negative_controls(manifest, root_map)
        _write(args.out, payload)
        print(json.dumps(payload["counts"], sort_keys=True))
        return 0 if _negative_proof(payload) else 1

    if args.command == "t2":
        payload = t2_controls(manifest, root_map)
        _write(args.out, payload)
        print(json.dumps({"t2": payload["counts"], "reason": payload.get("reason")}, sort_keys=True))
        return 0 if _t2_proof(payload) else 1

    index_rows = _load_json(args.index)["rows"] if getattr(args, "index", None) else None
    results = run_all(manifest, root_map, index_rows=index_rows)
    _write(args.out, results)
    print(json.dumps(_summary(results), sort_keys=True))
    return 0 if results["verdict"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
