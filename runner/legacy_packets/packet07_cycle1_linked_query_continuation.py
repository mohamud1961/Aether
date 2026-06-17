"""Packet 07 Cycle 1 linked-record query-state continuation board."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.packet07_cycle1_context_targeted_autoresearch import (
    BACKBONE_INCUMBENT,
    CUSTOM_LONG_HANDOFF_EVAL_ID,
    LONG_ROW_EVAL_ID,
    MODEL_TIER_SELECTORS,
    PRICE,
    _authority,
    _azure_dns_network_preflight,
    _bfcl_specs,
    _completion_specs,
    _context_specs,
    _counts,
    _docker_or_fallback_preflight,
    _grade_spec,
    _interpretation_class,
    _is_adapter_invalid,
    _is_infrastructure_invalid,
    _long_horizon_spec,
    _record_ledger,
    _seed_workspace,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
    resolve_packet07_context_model_route,
)

MISSION_ID = "packet07_cycle1_linked_query_continuation"
APP_EVIDENCE_VARIANT = "candidate_plus_path_normalized_app_evidence_projection_01"
LINKED_QUERY_VARIANT = "candidate_plus_linked_record_query_state_01"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-11_packet07_cycle1_linked_query_continuation"
)
ROUTES = (BACKBONE_INCUMBENT, APP_EVIDENCE_VARIANT, LINKED_QUERY_VARIANT)
ROUTE_ROLES = {
    BACKBONE_INCUMBENT: "backbone_incumbent",
    APP_EVIDENCE_VARIANT: "carry_forward_app_evidence_projection",
    LINKED_QUERY_VARIANT: "linked_record_query_state_successor",
}
LOCAL_ROUTE_OVERRIDES = {
    APP_EVIDENCE_VARIANT: {
        "base_variant": BACKBONE_INCUMBENT,
        "modules": {
            "tools_getter": {
                "file_rel": "blocks/tools/app_evidence_projection_normalizer.py",
                "module_import_path": "blocks.tools.app_evidence_projection_normalizer:get_tools",
            },
            "tool_executor": {
                "file_rel": "blocks/tools/app_evidence_projection_normalizer.py",
                "module_import_path": "blocks.tools.app_evidence_projection_normalizer:execute_tool_call",
            },
        },
    },
    LINKED_QUERY_VARIANT: {
        "base_variant": BACKBONE_INCUMBENT,
        "modules": {
            "orientation": {
                "file_rel": "blocks/orientation/packet07_context_doctrine.py",
                "module_import_path": "blocks.orientation.packet07_context_doctrine:orient_linked_record_query_state",
            },
            "tools_getter": {
                "file_rel": "blocks/tools/semistructured_record_bundle_parser.py",
                "module_import_path": "blocks.tools.semistructured_record_bundle_parser:get_tools",
            },
            "tool_executor": {
                "file_rel": "blocks/tools/semistructured_record_bundle_parser.py",
                "module_import_path": "blocks.tools.semistructured_record_bundle_parser:execute_tool_call",
            },
            "context": {
                "file_rel": "blocks/context/linked_record_query_state.py",
                "module_import_path": "blocks.context.linked_record_query_state:manage",
            },
        },
    },
}
FOCUSED_EVAL_IDS = (
    "contextbench_verified_03",
    "letta_filesystem_001_easy",
    "letta_filesystem_002_medium",
    CUSTOM_LONG_HANDOFF_EVAL_ID,
    LONG_ROW_EVAL_ID,
    "tb_style_verifier_fail_then_repair_v1",
    "bfcl_v3_strict_multi_turn_composite_97",
)
MEASUREMENT_CLASSES = {"derived_field_policy_failure", "proxy_shaped_failure"}
REAL_CONTEXT_CLASSES = {"closure_contract_failure", "source_grounded_extraction_failure", "task_truth_failure"}
_QUOTE_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")
_ID_VALUE_RE = re.compile(r"^[A-Za-z]+[-_][A-Za-z0-9]+$")
_ID_KEY_RE = re.compile(r"(?:^|_)(?:id|owner|account|record|person|pet|vehicle)(?:$|_)", re.IGNORECASE)
_DATE_KEY_RE = re.compile(r"(?:date|dob|birth|year|time)", re.IGNORECASE)
_NUMERIC_KEY_RE = re.compile(r"(?:count|total|sum|amount|balance|score|age|rank|size)", re.IGNORECASE)
_LOCATION_KEY_RE = re.compile(r"(?:state|city|country|region|address)", re.IGNORECASE)
_COMPARISON_MARKERS = ("same", "among", "highest", "lowest", "most", "least", "oldest", "youngest", "top", "tie")


def launch_linked_query_continuation(
    *,
    output_dir: str | Path,
    execute: bool = True,
    max_workers: int = 2,
    model_tier_selector: str = "screening_default",
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = _build_specs()
    board_manifest = {
        "mission_id": MISSION_ID,
        "comparison_set": list(ROUTES),
        "route_roles": ROUTE_ROLES,
        "required_eval_ids": list(FOCUSED_EVAL_IDS),
        "required_trace_proofs": [
            "linked_records_formed",
            "query_slots_tracked",
            "reduction_ready",
            "fact_based_answer_or_artifact_use",
        ],
        "authority": _authority(),
    }
    preflight = {
        "mission_id": MISSION_ID,
        "checks": {
            "route_availability": _route_availability_check(),
            "azure_dns_network_preflight": _azure_dns_network_preflight(),
            "docker_or_fallback": _docker_or_fallback_preflight(specs),
        },
    }
    blockers = _collect_preflight_blockers(preflight)
    preflight["status"] = "pass" if not blockers else "blocked"
    preflight["blockers"] = blockers
    preflight["planned_model_backed_runs"] = len(specs) * len(ROUTES)
    preflight["authority"] = _authority()
    _write_json(out / "packet07_cycle1_linked_query_continuation_board_manifest.json", board_manifest)
    if not execute or preflight["status"] != "pass":
        return _write_artifacts(out, [], [], preflight, board_manifest, blocked=True)
    records, traces = _execute_board(out, specs, max_workers=max_workers, model_tier_selector=model_tier_selector)
    return _write_artifacts(out, records, traces, preflight, board_manifest, blocked=False)


def _build_specs() -> list[dict[str, Any]]:
    library = {row["eval_id"]: row for row in [*_completion_specs(), *_context_specs(), *_bfcl_specs(), _long_horizon_spec()]}
    specs: list[dict[str, Any]] = []
    for eval_id in FOCUSED_EVAL_IDS:
        spec = dict(library[eval_id])
        if eval_id == LONG_ROW_EVAL_ID:
            lane, admission = "long_running_internal_tb_style", "diagnostic"
        elif eval_id == "tb_style_verifier_fail_then_repair_v1":
            lane, admission = "completion_closure", "certified"
        elif eval_id.startswith("bfcl_v3_"):
            lane, admission = "tooling_bfcl", "certified"
        else:
            lane, admission = "context_handoff_answer_extraction", "certified"
        spec["lane"] = lane
        spec["admission_level"] = admission
        spec["variant_ids"] = list(ROUTES)
        specs.append(spec)
    return specs


def _route_availability_check() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows, blockers = [], []
    for route_id in ROUTES:
        try:
            manifest = _build_route_manifest(route_id)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            rows.append({"route_id": route_id, "status": "pass", "route_manifest_fingerprint": manifest["route_manifest_fingerprint"]})
        except Exception as exc:
            rows.append({"route_id": route_id, "status": "fail", "error": str(exc)})
            blockers.append(f"route_unavailable:{route_id}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _build_route_manifest(route_id: str) -> dict[str, Any]:
    if route_id not in LOCAL_ROUTE_OVERRIDES:
        return build_packet04_route_manifest(route_id, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    override = LOCAL_ROUTE_OVERRIDES[route_id]
    manifest = deepcopy(build_packet04_route_manifest(override["base_variant"], scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE))
    for entry in manifest["routed_modules"]:
        entry["variant_id"] = route_id
        module_override = override["modules"].get(entry["runtime_key"])
        if not module_override:
            continue
        file_rel = Path(module_override["file_rel"])
        real_path = (Path.cwd() / file_rel).resolve()
        entry["declared_card_path"] = str(file_rel)
        entry["real_file_path"] = str(real_path)
        entry["module_import_path"] = str(module_override["module_import_path"])
        entry["file_sha256"] = hashlib.sha256(real_path.read_bytes()).hexdigest()
    manifest["variant_id"] = route_id
    manifest["variant_card_ref"] = None
    manifest["route_manifest_fingerprint"] = hashlib.sha256(json.dumps(manifest["routed_modules"], sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return manifest


def _collect_preflight_blockers(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    for name, check in preflight.get("checks", {}).items():
        if check.get("status") == "pass":
            continue
        for item in check.get("blockers", ["unspecified"]):
            cls = "infrastructure_invalid_result" if name == "azure_dns_network_preflight" else "adapter_invalid_result"
            if name == "docker_or_fallback":
                cls = "substrate_unavailable_result"
            blockers.append({"check": name, "blocker": item, "interpretation_class": cls})
    return blockers


def _execute_board(
    out: Path,
    specs: list[dict[str, Any]],
    *,
    max_workers: int,
    model_tier_selector: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    plan = [(index, spec, route) for index, (spec, route) in enumerate((spec, route) for spec in specs for route in ROUTES)]
    completed: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 3))) as executor:
        future_map = {
            executor.submit(_run_one, out, spec, route, index, model_tier_selector=model_tier_selector): index
            for index, spec, route in plan
        }
        for future in as_completed(future_map):
            completed.append((future_map[future], *future.result()))
    completed.sort(key=lambda row: row[0])
    return [row[1] for row in completed], [row[2] for row in completed]


def _run_one(
    out: Path,
    spec: dict[str, Any],
    variant: str,
    plan_index: int,
    *,
    model_tier_selector: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    run_started = perf_counter()
    _seed_workspace(workspace, spec)
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"] + "\nPrefer source-grounded inspection before schema-assuming compute. Do not close early.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=resolve_packet07_context_model_route(model_tier_selector=model_tier_selector),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(variant),
        enforce_packet04_route_contract=True,
    )
    grade = _grade_spec(spec, result, workspace)
    infra_invalid = _is_infrastructure_invalid(run_dir)
    adapter_invalid = _is_adapter_invalid(run_dir)
    verdict = "invalid" if infra_invalid or adapter_invalid else grade.get("verdict", "fail")
    reason_codes = list(grade.get("reason_codes", []))
    if infra_invalid:
        reason_codes = sorted(set(reason_codes + ["model_or_network_infra_failure"]))
    if adapter_invalid:
        reason_codes = sorted(set(reason_codes + ["adapter_contract_invalid"]))
    linked_query_proof = _linked_query_proof(result, run_dir, workspace, spec["task_prompt"], verdict)
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "lane": spec["lane"],
        "benchmark_class": spec["benchmark_class"],
        "task_id": spec["task_id"],
        "variant_id": variant,
        "route_role": ROUTE_ROLES[variant],
        "attempt": 0,
        "plan_index": plan_index,
        "admission_level": spec["admission_level"],
        "diagnostic_only": bool(spec["eval_id"] == LONG_ROW_EVAL_ID),
        "model_backed": True,
        "run_dir": str(run_dir),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "score_summary": {"final_verdict": verdict, "grade": grade},
        "scoreboard_verdict": verdict,
        "interpretation_class": _interpretation_class(spec, grade, infra_invalid=infra_invalid, adapter_invalid=adapter_invalid),
        "reason_codes": reason_codes,
        "token_and_cost_summary": _usage(result),
        "authority": _authority(),
        "timing_summary": {"run_wall_sec": perf_counter() - run_started},
        "linked_query_proof": linked_query_proof,
    }
    trace = {
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "variant_id": variant,
        "route_role": ROUTE_ROLES[variant],
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "scoreboard_verdict": verdict,
        "interpretation_class": record["interpretation_class"],
        "reason_codes": reason_codes,
        "linked_query_proof": linked_query_proof,
    }
    return record, trace


def _linked_query_proof(
    result: dict[str, Any],
    run_dir: Path,
    workspace: Path,
    task_prompt: str,
    verdict: str,
) -> dict[str, Any]:
    facts = _all_facts(result)
    records = _group_records(facts)
    joins = _join_links(records)
    anchors = _anchor_terms(task_prompt)
    unresolved = _unresolved_slots(task_prompt, anchors, records, joins)
    grouping = _grouping_keys(records)
    ranking = _ranking_keys(records)
    marker_text = (run_dir / "run_events.jsonl").read_text(encoding="utf-8") if (run_dir / "run_events.jsonl").exists() else ""
    linked_records_formed = bool(joins) or "linked_records_formed=true" in marker_text
    query_slots_tracked = bool(anchors or grouping or ranking or unresolved or "query_slots_tracked=true" in marker_text)
    reduction_ready = bool(joins and not {"needs_anchor_match", "needs_link_join"} & set(unresolved)) or "reduction_ready=true" in marker_text
    used = _facts_used(facts, str(result.get("execution", {}).get("last_completion", {}).get("text") or ""), _artifact_texts(workspace))
    return {
        "linked_records_formed": linked_records_formed,
        "linked_record_count": len(records),
        "joined_record_count": len({join["left"] for join in joins} | {join["right"] for join in joins}),
        "join_keys": sorted({join["join_key"] for join in joins})[:6],
        "query_slots_tracked": query_slots_tracked,
        "anchor_terms": anchors[:5],
        "unresolved_slots": unresolved[:5],
        "grouping_keys": grouping[:4],
        "ranking_keys": ranking[:4],
        "reduction_ready": reduction_ready,
        "fact_based_answer_or_artifact_use": used,
        "answer_or_artifact_improved": used and reduction_ready and verdict == "pass",
        "state_marker_seen": "[linked_record_query_state]" in marker_text,
    }


def _all_facts(result: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for step in result.get("execution", {}).get("steps", []):
        for tool_result in step.get("results", []):
            payload = tool_result.get("normalized_tool_call_payload") if isinstance(tool_result, dict) else None
            grounded = payload.get("semistructured_evidence_facts") if isinstance(payload, dict) else None
            if isinstance(grounded, list):
                facts.extend(item for item in grounded if isinstance(item, dict))
    return facts


def _group_records(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for fact in facts:
        source_path = str(fact.get("source_path") or "")
        source_span = str(fact.get("source_span") or "")
        if not source_path:
            continue
        key = (source_path, source_span)
        record = grouped.setdefault(key, {"source_path": source_path, "source_span": source_span, "family": Path(source_path).stem, "fields": {}})
        value = fact.get("value")
        if fact.get("fact_type") == "record_bundle" and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                record["fields"][str(sub_key)] = sub_value
        else:
            fact_key = str(fact.get("key") or "")
            if fact_key:
                record["fields"][fact_key] = value
    return [record for record in grouped.values() if record["fields"]]


def _join_links(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for left_index, left in enumerate(records):
        for right in records[left_index + 1 :]:
            for left_key, left_value in left["fields"].items():
                if not _join_candidate(left_key, left_value):
                    continue
                for right_key, right_value in right["fields"].items():
                    if left_value == right_value and _join_candidate(right_key, right_value):
                        links.append({"left": _record_id(left), "right": _record_id(right), "join_key": _prefer_join_key(left_key, right_key)})
                        break
    return links[:12]


def _unresolved_slots(prompt: str, anchors: list[str], records: list[dict[str, Any]], joins: list[dict[str, str]]) -> list[str]:
    lowered = prompt.lower()
    unresolved: list[str] = []
    if anchors and _anchor_match_count(records, anchors) == 0:
        unresolved.append("needs_anchor_match")
    if any(marker in lowered for marker in _COMPARISON_MARKERS) and not joins:
        unresolved.append("needs_link_join")
    if any(token in lowered for token in ("most", "least", "highest", "lowest", "total", "count")) and not _grouping_keys(records):
        unresolved.append("needs_grouping_key")
    if any(token in lowered for token in ("oldest", "youngest", "highest", "lowest", "tie")) and not _ranking_keys(records):
        unresolved.append("needs_ranking_key")
    return unresolved


def _grouping_keys(records: list[dict[str, Any]]) -> list[str]:
    return sorted({key for record in records for key in record["fields"] if _LOCATION_KEY_RE.search(key) or _ID_KEY_RE.search(key)})


def _ranking_keys(records: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            key
            for record in records
            for key, value in record["fields"].items()
            if _DATE_KEY_RE.search(key) or (_NUMERIC_KEY_RE.search(key) and isinstance(value, (int, float)))
        }
    )


def _anchor_terms(prompt: str) -> list[str]:
    terms = [left or right for left, right in _QUOTE_RE.findall(prompt)]
    return [term.strip() for term in terms if term.strip()]


def _anchor_match_count(records: list[dict[str, Any]], anchors: list[str]) -> int:
    if not anchors:
        return 0
    count = 0
    for record in records:
        values = {str(value) for value in record["fields"].values()}
        if any(anchor in values for anchor in anchors):
            count += 1
    return count


def _join_candidate(key: str, value: Any) -> bool:
    text = str(value).strip()
    return bool(text and (_ID_KEY_RE.search(key) or _LOCATION_KEY_RE.search(key) or _ID_VALUE_RE.fullmatch(text)))


def _prefer_join_key(left_key: str, right_key: str) -> str:
    return left_key if left_key == right_key else f"{left_key}<=>{right_key}"


def _record_id(record: dict[str, Any]) -> str:
    return f"{record['family']}@{record['source_span']}"


def _artifact_texts(workspace: Path) -> list[str]:
    texts: list[str] = []
    for relpath in ("artifacts/work_pocket.json", "artifacts/final_report.json"):
        path = workspace / relpath
        if path.exists():
            texts.append(path.read_text(encoding="utf-8"))
    return texts


def _facts_used(facts: list[dict[str, Any]], final_answer: str, artifacts: list[str]) -> bool:
    haystacks = [final_answer, *artifacts]
    for fact in facts:
        for token in _fact_tokens(fact):
            if token and any(token in haystack for haystack in haystacks):
                return True
    return False


def _fact_tokens(fact: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for value in (fact.get("source_path"), fact.get("key"), fact.get("value")):
        tokens.extend(_flatten_tokens(value))
    seen, unique = set(), []
    for token in tokens:
        cleaned = token.strip()
        if len(cleaned) < 2 or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique[:24]


def _flatten_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        tokens: list[str] = []
        for key, nested in value.items():
            tokens.append(str(key))
            tokens.extend(_flatten_tokens(nested))
        return tokens
    if isinstance(value, list):
        tokens: list[str] = []
        for nested in value:
            tokens.extend(_flatten_tokens(nested))
        return tokens
    return [str(value)]


def _write_artifacts(out: Path, records: list[dict[str, Any]], traces: list[dict[str, Any]], preflight: dict[str, Any], board_manifest: dict[str, Any], *, blocked: bool) -> dict[str, Any]:
    _write_jsonl(out / "packet07_cycle1_linked_query_continuation_result_records.jsonl", records)
    score = _score_envelope(records, preflight, board_manifest, blocked=blocked)
    failure_report = _failure_source_report(records)
    variant_delta = _variant_delta(records)
    trace_report = {
        "mission_id": MISSION_ID,
        "run_count": len(traces),
        "traces": traces,
        "linked_query_proof_counts": _linked_query_proof_counts(records),
        "preflight_blockers": preflight.get("blockers", []),
    }
    cost_report = _cost_report(records)
    recommendation = _recommendation(score, failure_report, variant_delta, trace_report)
    deep_trace = _deep_trace(score, failure_report, variant_delta, trace_report)
    handoff = _handoff(score, variant_delta, trace_report)
    ledger = _raw_ledger_update(out, score, failure_report, variant_delta, trace_report)
    _write_json(out / "packet07_cycle1_linked_query_continuation_score_envelope.json", score)
    _write_json(out / "packet07_cycle1_linked_query_continuation_trace_report.json", trace_report)
    _write_json(out / "packet07_cycle1_linked_query_continuation_failure_source_report.json", failure_report)
    _write_json(out / "packet07_cycle1_linked_query_continuation_variant_delta_report.json", variant_delta)
    _write_json(out / "packet07_cycle1_linked_query_continuation_cost_report.json", cost_report)
    _write_text(out / "packet07_cycle1_linked_query_continuation_recommendation.md", recommendation)
    _write_text(out / "packet07_cycle1_linked_query_continuation_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_cycle1_linked_query_continuation_handoff.md", handoff)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    _record_ledger(ledger)
    return {"output_dir": str(out), "run_count": len(records), "model_backed_runs": score["model_backed_runs"], "selected_recommendation": score["selected_recommendation"], "blocked": blocked}


def _linked_query_proof_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "linked_records_formed_runs": sum(1 for row in records if row.get("linked_query_proof", {}).get("linked_records_formed")),
        "query_slots_tracked_runs": sum(1 for row in records if row.get("linked_query_proof", {}).get("query_slots_tracked")),
        "reduction_ready_runs": sum(1 for row in records if row.get("linked_query_proof", {}).get("reduction_ready")),
        "fact_based_answer_or_artifact_use_runs": sum(
            1 for row in records if row.get("linked_query_proof", {}).get("fact_based_answer_or_artifact_use")
        ),
        "improved_runs": sum(1 for row in records if row.get("linked_query_proof", {}).get("answer_or_artifact_improved")),
    }


def _score_envelope(records: list[dict[str, Any]], preflight: dict[str, Any], board_manifest: dict[str, Any], *, blocked: bool) -> dict[str, Any]:
    admitted = [row for row in records if row["interpretation_class"] not in {"infrastructure_invalid_result", "adapter_invalid_result", "substrate_unavailable_result"}]
    certified = [row for row in admitted if row["admission_level"] == "certified"]
    selected = "context_measurement_or_eval_blocked" if blocked else _selected_recommendation(certified)
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": sum(1 for row in records if row.get("model_backed")),
        "behaviorally_admissible_run_count": len(admitted),
        "selected_recommendation": selected,
        "route_summary_certified_only": {route: _route_eval_summary(certified, route) for route in ROUTES},
        "preflight": preflight,
        "board_manifest": board_manifest,
    }


def _failure_source_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    certified = [row for row in records if row["admission_level"] == "certified"]
    failures = [row for row in certified if row["scoreboard_verdict"] != "pass"]
    return {
        "mission_id": MISSION_ID,
        "failure_count": len(failures),
        "dominant_failure_lane": max(_counts(row["lane"] for row in failures).items(), key=lambda item: (item[1], item[0]))[0] if failures else "none",
        "failure_counts_by_interpretation_class": _counts(row["interpretation_class"] for row in failures),
        "measurement_blocked_rows": [row["run_id"] for row in failures if row["interpretation_class"] in MEASUREMENT_CLASSES],
        "real_context_failure_rows": [row["run_id"] for row in failures if row["lane"] == "context_handoff_answer_extraction" and row["interpretation_class"] in REAL_CONTEXT_CLASSES],
        "closure_contract_rows": [row["run_id"] for row in failures if row["interpretation_class"] == "closure_contract_failure"],
    }


def _variant_delta(records: list[dict[str, Any]]) -> dict[str, Any]:
    certified = [row for row in records if row["admission_level"] == "certified"]
    backbone = _route_eval_summary(certified, BACKBONE_INCUMBENT)
    app = _route_eval_summary(certified, APP_EVIDENCE_VARIANT)
    linked = _route_eval_summary(certified, LINKED_QUERY_VARIANT)
    linked_status = (
        "earned_carry_forward"
        if linked["letta_pass"] > app["letta_pass"]
        and linked["completion_regression_fail"] == 0
        and linked["bfcl_regression_fail"] == 0
        and linked["custom_long_handoff_pass"] >= app["custom_long_handoff_pass"]
        and linked["linked_records_formed_runs"] > 0
        and linked["reduction_ready_runs"] > 0
        else "partial_signal"
        if linked["linked_records_formed_runs"] > 0
        and linked["query_slots_tracked_runs"] > 0
        and linked["completion_regression_fail"] == 0
        and linked["custom_long_handoff_pass"] >= app["custom_long_handoff_pass"]
        else "not_earned"
    )
    return {
        "mission_id": MISSION_ID,
        "backbone": backbone,
        "app_evidence_projection": app,
        "linked_record_query_state": linked,
        "linked_query_status": linked_status,
    }


def _route_eval_summary(records: list[dict[str, Any]], route_id: str) -> dict[str, int]:
    scoped = [row for row in records if row["variant_id"] == route_id]
    return {
        "certified_pass": sum(1 for row in scoped if row["scoreboard_verdict"] == "pass"),
        "certified_fail": sum(1 for row in scoped if row["scoreboard_verdict"] != "pass"),
        "context_pass": sum(1 for row in scoped if row["lane"] == "context_handoff_answer_extraction" and row["scoreboard_verdict"] == "pass"),
        "letta_pass": sum(1 for row in scoped if row["eval_id"].startswith("letta_filesystem_") and row["scoreboard_verdict"] == "pass"),
        "contextbench_pass": sum(1 for row in scoped if row["eval_id"] == "contextbench_verified_03" and row["scoreboard_verdict"] == "pass"),
        "completion_regression_fail": sum(1 for row in scoped if row["eval_id"] == "tb_style_verifier_fail_then_repair_v1" and row["scoreboard_verdict"] != "pass"),
        "bfcl_regression_fail": sum(1 for row in scoped if row["eval_id"] == "bfcl_v3_strict_multi_turn_composite_97" and row["scoreboard_verdict"] != "pass"),
        "custom_long_handoff_pass": sum(1 for row in scoped if row["eval_id"] == CUSTOM_LONG_HANDOFF_EVAL_ID and row["scoreboard_verdict"] == "pass"),
        "linked_records_formed_runs": sum(1 for row in scoped if row.get("linked_query_proof", {}).get("linked_records_formed")),
        "query_slots_tracked_runs": sum(1 for row in scoped if row.get("linked_query_proof", {}).get("query_slots_tracked")),
        "reduction_ready_runs": sum(1 for row in scoped if row.get("linked_query_proof", {}).get("reduction_ready")),
        "fact_based_answer_or_artifact_use_runs": sum(
            1 for row in scoped if row.get("linked_query_proof", {}).get("fact_based_answer_or_artifact_use")
        ),
    }


def _selected_recommendation(certified: list[dict[str, Any]]) -> str:
    if not certified:
        return "context_measurement_or_eval_blocked"
    app = _route_eval_summary(certified, APP_EVIDENCE_VARIANT)
    linked = _route_eval_summary(certified, LINKED_QUERY_VARIANT)
    if linked["letta_pass"] > app["letta_pass"] and linked["completion_regression_fail"] == 0 and linked["bfcl_regression_fail"] == 0:
        return "context_repair_viable_continue_packet07"
    if (
        linked["linked_records_formed_runs"] > 0
        and linked["query_slots_tracked_runs"] > 0
        and linked["reduction_ready_runs"] > 0
        and linked["completion_regression_fail"] == 0
        and linked["custom_long_handoff_pass"] >= app["custom_long_handoff_pass"]
    ):
        return "context_repair_partial_continue_one_more_context_cycle"
    return "context_no_signal_shift_target"


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = sum(int(row.get("token_and_cost_summary", {}).get("total_tokens", 0) or 0) for row in records)
    usd = sum(float(row.get("token_and_cost_summary", {}).get("usd_estimate", 0.0) or 0.0) for row in records)
    return {"mission_id": MISSION_ID, "run_count": len(records), "total_tokens": tokens, "total_usd_estimate": usd, "price_table": PRICE}


def _recommendation(score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any], trace_report: dict[str, Any]) -> str:
    selected = score["selected_recommendation"]
    linked = variant_delta["linked_record_query_state"]
    app = variant_delta["app_evidence_projection"]
    lines = [
        "# Packet 07 Cycle 1 Linked Query Continuation Recommendation",
        "",
        f"1. Did the linked-record query-state variant improve the context lane? {'Yes.' if linked['context_pass'] > app['context_pass'] else 'No.'}",
        f"2. Did Letta improve on real behavioral grounds? {'Yes.' if linked['letta_pass'] > app['letta_pass'] else 'No.'}",
        f"3. Did the route form linked grounded records? {'Yes.' if linked['linked_records_formed_runs'] > 0 else 'No.'}",
        f"4. Did the route track query slots across those records? {'Yes.' if linked['query_slots_tracked_runs'] > 0 else 'No.'}",
        f"5. Did the route reach reduction-ready state? {'Yes.' if linked['reduction_ready_runs'] > 0 else 'No.'}",
        f"6. Did grounded facts reach the final answer or artifact path? {'Yes.' if linked['fact_based_answer_or_artifact_use_runs'] > 0 else 'No.'}",
        f"7. Did app-evidence projection remain intact? {'Yes.' if linked['custom_long_handoff_pass'] >= app['custom_long_handoff_pass'] else 'No.'}",
        f"8. Did the blocker move after linked query-state grounding, or remain upstream? {'Moved.' if linked['letta_pass'] > app['letta_pass'] else 'Remained upstream.'}",
        f"9. Were remaining misses real context failures or measurement-shaped? real_context={len(failure_report['real_context_failure_rows'])}; measurement_shaped={len(failure_report['measurement_blocked_rows'])}.",
        f"10. What is now the best carry-forward route? {'candidate_plus_linked_record_query_state_01' if variant_delta['linked_query_status']=='earned_carry_forward' else 'candidate_plus_path_normalized_app_evidence_projection_01'}.",
        f"11. Should Packet 07 continue one more bounded context continuation, or shift target? {selected}.",
        "",
        selected,
        "",
        f"linked_query_proof_counts={trace_report['linked_query_proof_counts']}",
    ]
    return "\n".join(lines) + "\n"


def _deep_trace(score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any], trace_report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Cycle 1 Linked Query Continuation Deep Trace Analysis",
            "",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- backbone: `{variant_delta['backbone']}`",
            f"- app_evidence_projection: `{variant_delta['app_evidence_projection']}`",
            f"- linked_record_query_state: `{variant_delta['linked_record_query_state']}`",
            f"- linked_query_status: `{variant_delta['linked_query_status']}`",
            f"- linked_query_proof_counts: `{trace_report['linked_query_proof_counts']}`",
            "",
            "## Failure Clustering",
            "",
            f"- failure_counts_by_interpretation_class: `{failure_report['failure_counts_by_interpretation_class']}`",
            f"- real_context_failure_rows: `{len(failure_report['real_context_failure_rows'])}`",
            f"- measurement_blocked_rows: `{len(failure_report['measurement_blocked_rows'])}`",
            f"- closure_contract_rows: `{len(failure_report['closure_contract_rows'])}`",
            "",
            "## Required Answers",
            "",
            f"1. linked-record variant improved lane: `{variant_delta['linked_record_query_state']['context_pass'] > variant_delta['app_evidence_projection']['context_pass']}`",
            f"2. Letta improved on real grounds: `{variant_delta['linked_record_query_state']['letta_pass'] > variant_delta['app_evidence_projection']['letta_pass']}`",
            f"3. linked grounded records formed: `{variant_delta['linked_record_query_state']['linked_records_formed_runs'] > 0}`",
            f"4. query slots tracked: `{variant_delta['linked_record_query_state']['query_slots_tracked_runs'] > 0}`",
            f"5. reduction-ready state reached: `{variant_delta['linked_record_query_state']['reduction_ready_runs'] > 0}`",
            f"6. fact-based answer/artifact use: `{variant_delta['linked_record_query_state']['fact_based_answer_or_artifact_use_runs'] > 0}`",
            f"7. app-evidence projection remained intact: `{variant_delta['linked_record_query_state']['custom_long_handoff_pass'] >= variant_delta['app_evidence_projection']['custom_long_handoff_pass']}`",
            f"8. blocker moved after linked query state: `{variant_delta['linked_record_query_state']['letta_pass'] > variant_delta['app_evidence_projection']['letta_pass']}`",
            f"9. remaining misses real vs measurement: `{len(failure_report['real_context_failure_rows'])}` real | `{len(failure_report['measurement_blocked_rows'])}` measurement",
            f"10. best carry-forward route now: `{'candidate_plus_linked_record_query_state_01' if variant_delta['linked_query_status']=='earned_carry_forward' else 'candidate_plus_path_normalized_app_evidence_projection_01'}`",
            f"11. next recommendation: `{score['selected_recommendation']}`",
        ]
    ) + "\n"


def _handoff(score: dict[str, Any], variant_delta: dict[str, Any], trace_report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Cycle 1 Linked Query Continuation Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- app_evidence_projection: `{variant_delta['app_evidence_projection']}`",
            f"- linked_record_query_state: `{variant_delta['linked_record_query_state']}`",
            f"- linked_query_status: `{variant_delta['linked_query_status']}`",
            f"- linked_query_proof_counts: `{trace_report['linked_query_proof_counts']}`",
        ]
    ) + "\n"


def _raw_ledger_update(
    out: Path,
    score: dict[str, Any],
    failure_report: dict[str, Any],
    variant_delta: dict[str, Any],
    trace_report: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 Cycle 1 linked query continuation",
            "- event_type: implementation",
            f"- summary: Added Packet 07 Cycle 1 linked-record query-state continuation runner and reporting with recommendation `{score['selected_recommendation']}`.",
            f"- observations: run_count `{score['run_count']}`; linked_route `{variant_delta['linked_record_query_state']}`; linked_query_proof_counts `{trace_report['linked_query_proof_counts']}`; real_context_failure_rows `{len(failure_report['real_context_failure_rows'])}`; measurement_blocked_rows `{len(failure_report['measurement_blocked_rows'])}`.",
            "- inference: The continuation formalizes the hypothesis that parser-grounded record bundles plus linked query-state tracking can preserve the safe app-evidence base while improving reduction discipline on context-heavy tasks.",
            f"- evidence_paths: {out / 'packet07_cycle1_linked_query_continuation_result_records.jsonl'}; {out / 'packet07_cycle1_linked_query_continuation_score_envelope.json'}; {out / 'packet07_cycle1_linked_query_continuation_trace_report.json'}; {out / 'packet07_cycle1_linked_query_continuation_failure_source_report.json'}; {out / 'packet07_cycle1_linked_query_continuation_variant_delta_report.json'}; {out / 'packet07_cycle1_linked_query_continuation_deep_trace_analysis.md'}",
            "- affected_components: blocks/tools/semistructured_record_bundle_parser.py; blocks/context/linked_record_query_state.py; blocks/orientation/packet07_context_doctrine.py; runner/packet07_cycle1_linked_query_continuation.py; linked query continuation board artifacts; tests/test_packet07_cycle1_linked_query_continuation.py",
            "- decision_change: Continued Packet 07 on the safe app-evidence carry-forward route with one linked-record query-state successor variant.",
            "- unresolved_questions: Whether linked query-state tracking alone is enough to move the Letta rows, or whether the next slice needs a narrower reduction executor on top of the new context state.",
            "- confidence: medium",
            "- commit_message: HOLD - add Packet 07 linked query continuation runner and tests",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--model-tier-selector", choices=MODEL_TIER_SELECTORS, default="screening_default")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_linked_query_continuation(
                output_dir=args.output_dir,
                execute=not args.no_execute,
                max_workers=args.max_workers,
                model_tier_selector=args.model_tier_selector,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
