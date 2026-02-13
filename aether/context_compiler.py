from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .artifact_store import ArtifactStore
from .context_pack import (
    ContextPackProjection,
    LAYER_ORDER,
    SECTION_CONFLICTS,
    SECTION_CONTRACTS,
    SECTION_DOCTRINE,
    SECTION_EVIDENCE,
    SECTION_EVIDENCE_V11,
    SECTION_POLICY,
    SECTION_POLICY_V11,
    SECTION_PLAN,
    SECTION_PLAN_V11,
    SECTION_SCRATCH,
    SECTION_SCRATCH_V11,
    SECTION_STATE,
    SECTION_STATE_V11,
    SECTION_SYSTEM_V11,
    SECTION_TASK,
    SECTION_TASK_V11,
    SECTION_UNTRUSTED,
    SECTION_VERIFICATION,
)
from .control_plane import (
    export_readiness_vector,
    last_verified_fingerprint_hash,
    latest_phase_transition_denial_code,
    latest_plan_status,
)
from .event_log import EventLog
from .hashing import hash_canonical_json
from .policy_config import PolicyConfig

UNTRUSTED_START = "[UNTRUSTED_BASE64_START]"
UNTRUSTED_END = "[UNTRUSTED_BASE64_END]"

SWEET_ZONE_MIN_PCT = 10
SWEET_ZONE_MAX_PCT = 35
HARD_CAP_NORMAL_PCT = 40
HARD_CAP_OVERDRIVE_PCT = 60
MAX_OVERDRIVE_STEPS_PER_RUN = 3
DEFAULT_CONTEXT_WINDOW_TOKENS = 128_000
COMPILER_VERSION = "context_compiler_v1_1"
ADVISORY_MEMO_MAX_NOTES = 5

_AUTHORITY_PRIORITY = {
    "doctrine": 0,
    "eval": 1,
    "spine": 2,
    "runtime": 3,
    "untrusted": 4,
}

REQUIRED_PROVENANCE_FIELDS = {
    "source_ref",
    "observed_at",
    "authority_tier",
    "validity_ttl",
    "content_hash",
}

_TOOL_OUTPUT_UNTRUSTED_KINDS = {
    "tool_output_excerpt",
    "tool_output_summary",
    "tool_output_summary_rollup",
    "tool_blocked_summary",
    "tool_output",
    "tool_result",
    "terminal_output",
}

_UNTRUSTED_PREFIX_PATTERNS = (
    "system:",
    "important:",
    "instruction:",
    "you must:",
    "override:",
    "admin:",
    "directive:",
    "[system]",
    "[important]",
    "[instruction]",
    "[override]",
    "[admin]",
)

_LAYER_TO_LEGACY_SECTION = {
    SECTION_POLICY_V11: SECTION_POLICY,
    SECTION_SYSTEM_V11: SECTION_DOCTRINE,
    SECTION_CONTRACTS: SECTION_CONTRACTS,
    SECTION_TASK_V11: SECTION_TASK,
    SECTION_PLAN_V11: SECTION_PLAN,
    SECTION_EVIDENCE_V11: SECTION_EVIDENCE,
    SECTION_STATE_V11: SECTION_STATE,
    SECTION_SCRATCH_V11: SECTION_SCRATCH,
}

_PHASE_CARD_TEXT: Dict[str, str] = {
    "Orient": (
        "PHASE CARD — ORIENT\n\n"
        "Goal: Produce a precise understanding of the task, constraints, and what evidence you must collect next.\n\n"
        "Allowed tools: list_dir, search_files, read_file, stat_paths, run(read-only allowlist), request_phase_transition.\n"
        "Forbidden tools: write_file, apply_patch, pipeline_run.\n\n"
        "Hard rules:\n"
        "- Do not modify source files in this phase.\n"
        "- Prefer native tools (list_dir/read_file/search_files) over run.\n"
        "- If a tool is denied, read STATE.missing_conditions + resolution_hint and adjust.\n\n"
        "Exit criteria (must be true before requesting Explore):\n"
        "- You can name the 3–8 most relevant files/symbols to inspect next.\n"
        "- You can state 1–3 concrete hypotheses and what evidence would confirm/falsify each."
    ),
    "Explore": (
        "PHASE CARD — EXPLORE\n\n"
        "Goal: Gather concrete repo evidence required to write an implementation plan. Falsify hypotheses.\n\n"
        "Allowed tools: list_dir, search_files, read_file, stat_paths, run(read-only allowlist), "
        "write_file(sandbox-only), request_phase_transition.\n"
        "Forbidden tools: apply_patch, pipeline_run, write_file(outside /.tb_sandbox/).\n\n"
        "Hard rules:\n"
        "- Do not request Verify or Review from Explore (it will be denied).\n"
        "- If you hit repetitive-read denials, pivot: summarize what you learned and transition to Plan.\n"
        "- If you must write a probe, write only under /.tb_sandbox/ and make it easy to delete.\n\n"
        "Exit criteria (must be true before requesting Plan):\n"
        "- You can point to exact file paths + symbol names (and line ranges where possible) for the change.\n"
        "- You can state the minimal change strategy and the verification approach (what will be run in Verify)."
    ),
    "Plan": (
        "PHASE CARD — PLAN\n\n"
        "Goal: Produce a deterministic, testable implementation plan that the harness can execute without guesswork.\n\n"
        "Allowed tools: list_dir, search_files, read_file, stat_paths, run(read-only allowlist), "
        "write_file(plan-artifact-only), request_phase_transition.\n"
        "Forbidden tools: apply_patch, pipeline_run, source edits.\n\n"
        "Hard rules:\n"
        "- Plan must be stepwise and dependency-ordered (CHUNK-like), and include: files touched, exact commands to verify, and stop conditions.\n"
        "- If Implement is denied due to plan status, fix the plan status first (do not brute force with more reads).\n\n"
        "Exit criteria (must be true before requesting Implement):\n"
        "- Plan has 3–10 steps, each with: goal, exact files, exact tests, and evidence outputs.\n"
        "- Risks and rollback are stated."
    ),
    "Implement": (
        "PHASE CARD — IMPLEMENT\n\n"
        "Goal: Apply the minimal correct change aligned to the approved plan.\n\n"
        "Allowed tools: all (including apply_patch, pipeline_run) except destructive operations; request_phase_transition.\n\n"
        "Hard rules:\n"
        "- Make small, reversible edits. Prefer apply_patch over rewriting full files.\n"
        "- Do not re-run exploratory reads that were already captured unless new evidence is required.\n"
        "- After any meaningful change, proceed toward Verify (do not loop).\n\n"
        "Exit criteria (must be true before requesting Verify):\n"
        "- Work product exists (code/config changes) and a concrete verification command is ready."
    ),
    "Verify": (
        "PHASE CARD — VERIFY\n\n"
        "Goal: Run verifiers/tests and collect evidence required to commit.\n\n"
        "Notes:\n"
        "- Verify/repair is runner-driven. If verification fails, you will be routed back to Implement with failure evidence."
    ),
    "Review": (
        "PHASE CARD — REVIEW\n\n"
        "Goal: Assemble completion evidence bundle and finalize.\n\n"
        "Notes:\n"
        "- Review is harness-only; no tools are available."
    ),
}


@dataclass(frozen=True)
class CompilerOutputs:
    context_pack: Dict[str, Any]
    manifest: Dict[str, Any]
    context_pack_hash: str
    manifest_hash: str
    context_pack_ref: Optional[str] = None
    manifest_ref: Optional[str] = None
    context_pack_content_hash: Optional[str] = None
    manifest_content_hash: Optional[str] = None


def compile_context(
    candidates: Iterable[Dict[str, Any]],
    *,
    policy_config: PolicyConfig,
    section_budgets: Optional[Dict[str, int]] = None,
    compiler_mode: str = "normal",
    overdrive_count: int = 0,
    overdrive_reason_code: Optional[str] = None,
    context_window_tokens: Optional[int] = None,
    intent_contract: Optional[Any] = None,
    completion_contract: Optional[Any] = None,
    implementation_plan: Optional[Any] = None,
    current_plan_step_id: Optional[str] = None,
    task_understanding: Optional[Any] = None,
) -> CompilerOutputs:
    projected_candidates = _project_tool_candidates(list(candidates))
    normalized_candidates = _normalize_candidates(projected_candidates)
    contract_candidates = _build_contract_candidates(
        intent_contract=intent_contract,
        completion_contract=completion_contract,
        implementation_plan=implementation_plan,
        current_plan_step_id=current_plan_step_id,
    )
    plan_candidates = _build_plan_candidates(
        implementation_plan=implementation_plan,
    )
    understanding_candidates = _build_task_understanding_candidates(
        task_understanding=task_understanding,
    )
    memo_candidates = _build_advisory_memo_candidates(normalized_candidates)
    phase_card_candidates = _build_phase_card_candidates(normalized_candidates)
    all_candidates = _normalize_candidates(
        normalized_candidates
        + contract_candidates
        + plan_candidates
        + understanding_candidates
        + memo_candidates
        + phase_card_candidates
    )
    conflicts = _detect_conflicts(all_candidates)

    _validate_compiler_mode(
        compiler_mode=compiler_mode,
        overdrive_count=overdrive_count,
        overdrive_reason_code=overdrive_reason_code,
    )

    layer_sections: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in LAYER_ORDER}
    legacy_sections: Dict[str, List[Dict[str, Any]]] = {
        SECTION_DOCTRINE: [],
        SECTION_POLICY: [],
        SECTION_CONTRACTS: [],
        SECTION_TASK: [],
        SECTION_PLAN: [],
        SECTION_VERIFICATION: [],
        SECTION_EVIDENCE: [],
        SECTION_STATE: [],
        SECTION_SCRATCH: [],
        SECTION_UNTRUSTED: [],
        SECTION_CONFLICTS: [],
    }

    untrusted_items_count = 0
    wrapped_candidate_ids: Dict[int, int] = {}
    for candidate in all_candidates:
        target_layer = _map_candidate_to_layer(candidate)
        if _is_untrusted(candidate, policy_config):
            _validate_untrusted_tagging(candidate)
            wrapped = _wrap_untrusted_content(candidate)
            layer_sections[SECTION_SCRATCH_V11].append(wrapped)
            wrapped_candidate_ids[id(wrapped)] = id(candidate)
            untrusted_items_count += 1
            continue

        layer_sections[target_layer].append(candidate)
        legacy_target = _LAYER_TO_LEGACY_SECTION[target_layer]
        legacy_sections[legacy_target].append(candidate)
        if target_layer == SECTION_EVIDENCE_V11 and candidate.get("kind") == "verifier_structured":
            legacy_sections[SECTION_VERIFICATION].append(candidate)

    _apply_section_budgets(layer_sections, section_budgets or {})
    _sync_legacy_budgets(legacy_sections, layer_sections)

    formatted_conflicts = _format_conflicts(conflicts)
    if formatted_conflicts:
        conflict_content = _render_conflicts_text(formatted_conflicts)
        conflict_item = {
            "source_ref": "compiler/conflicts",
            "observed_at": "",
            "authority_tier": "runtime",
            "validity_ttl": "P0D",
            "content_hash": hash_canonical_json(conflict_content),
            "kind": "conflicts",
            "content": conflict_content,
            "conflicts": formatted_conflicts,
            "conflicts_hash": hash_canonical_json(formatted_conflicts),
        }
        layer_sections[SECTION_SCRATCH_V11].append(conflict_item)
    legacy_sections[SECTION_CONFLICTS] = formatted_conflicts

    total_tokens_estimate = _estimate_total_tokens(layer_sections)
    resolved_context_window_tokens = _resolve_context_window_tokens(
        policy_config=policy_config,
        context_window_tokens=context_window_tokens,
    )
    sweet_zone_pct = _compute_percentage(total_tokens_estimate, resolved_context_window_tokens)
    _enforce_hard_cap(total_tokens_estimate, resolved_context_window_tokens, compiler_mode)

    input_candidate_hashes = [
        hash_canonical_json(_candidate_hash_payload(candidate))
        for candidate in all_candidates
    ]

    context_pack: Dict[str, Any] = {}
    for layer in LAYER_ORDER:
        context_pack[layer] = layer_sections[layer]
    for legacy_name in (
        SECTION_DOCTRINE,
        SECTION_POLICY,
        SECTION_CONTRACTS,
        SECTION_TASK,
        SECTION_PLAN,
        SECTION_VERIFICATION,
        SECTION_EVIDENCE,
        SECTION_STATE,
        SECTION_SCRATCH,
        SECTION_UNTRUSTED,
        SECTION_CONFLICTS,
    ):
        context_pack[legacy_name] = legacy_sections[legacy_name]

    selected_candidate_ids: set[int] = set()
    for items in layer_sections.values():
        for item in items:
            selected_candidate_ids.add(wrapped_candidate_ids.get(id(item), id(item)))

    manifest = _build_manifest(
        candidates=all_candidates,
        layer_sections=layer_sections,
        selected_candidate_ids=selected_candidate_ids,
        conflicts=formatted_conflicts,
        compiler_mode=compiler_mode,
        overdrive_reason_code=overdrive_reason_code,
        total_tokens_estimate=total_tokens_estimate,
        sweet_zone_pct=sweet_zone_pct,
        context_window_tokens=resolved_context_window_tokens,
        input_candidate_hashes=input_candidate_hashes,
        untrusted_items_count=untrusted_items_count,
    )

    context_pack_hash = hash_canonical_json(context_pack)
    manifest_hash = hash_canonical_json(manifest)
    return CompilerOutputs(
        context_pack=context_pack,
        manifest=manifest,
        context_pack_hash=context_pack_hash,
        manifest_hash=manifest_hash,
    )


def compile_and_log(
    candidates: Iterable[Dict[str, Any]],
    *,
    policy_config: PolicyConfig,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
    workspace_fingerprint_hash: Optional[str] = None,
    intent_digest: Optional[str] = None,
    intent_contract_id: Optional[str] = None,
    section_budgets: Optional[Dict[str, int]] = None,
    artifact_store: Optional[ArtifactStore] = None,
    compiler_mode: str = "normal",
    overdrive_count: int = 0,
    overdrive_reason_code: Optional[str] = None,
    context_window_tokens: Optional[int] = None,
    intent_contract: Optional[Any] = None,
    completion_contract: Optional[Any] = None,
    implementation_plan: Optional[Any] = None,
    current_plan_step_id: Optional[str] = None,
    task_understanding: Optional[Any] = None,
) -> CompilerOutputs:
    outputs, _compile_ms = compile_and_log_with_metrics(
        candidates,
        policy_config=policy_config,
        event_log=event_log,
        timestamp=timestamp,
        cwd=cwd,
        workspace_fingerprint_hash=workspace_fingerprint_hash,
        intent_digest=intent_digest,
        intent_contract_id=intent_contract_id,
        section_budgets=section_budgets,
        artifact_store=artifact_store,
        compiler_mode=compiler_mode,
        overdrive_count=overdrive_count,
        overdrive_reason_code=overdrive_reason_code,
        context_window_tokens=context_window_tokens,
        intent_contract=intent_contract,
        completion_contract=completion_contract,
        implementation_plan=implementation_plan,
        current_plan_step_id=current_plan_step_id,
        task_understanding=task_understanding,
    )
    return outputs


def compile_and_log_with_metrics(
    candidates: Iterable[Dict[str, Any]],
    *,
    policy_config: PolicyConfig,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
    workspace_fingerprint_hash: Optional[str] = None,
    intent_digest: Optional[str] = None,
    intent_contract_id: Optional[str] = None,
    section_budgets: Optional[Dict[str, int]] = None,
    artifact_store: Optional[ArtifactStore] = None,
    compiler_mode: str = "normal",
    overdrive_count: int = 0,
    overdrive_reason_code: Optional[str] = None,
    context_window_tokens: Optional[int] = None,
    intent_contract: Optional[Any] = None,
    completion_contract: Optional[Any] = None,
    implementation_plan: Optional[Any] = None,
    current_plan_step_id: Optional[str] = None,
    task_understanding: Optional[Any] = None,
) -> Tuple[CompilerOutputs, int]:
    compile_started_ns = time.monotonic_ns()
    candidate_list = list(candidates)
    candidate_list = _scope_tool_receipts_to_current_phase(
        candidates=candidate_list,
        event_log=event_log,
    )
    include_state_readiness = (
        section_budgets is None
        or _state_budget_requested(section_budgets)
    )
    if include_state_readiness:
        candidate_list.extend(
            _build_state_readiness_candidates(
                candidates=candidate_list,
                event_log=event_log,
                timestamp=timestamp,
                workspace_fingerprint_hash=workspace_fingerprint_hash,
            )
        )
    outputs = compile_context(
        candidate_list,
        policy_config=policy_config,
        section_budgets=section_budgets,
        compiler_mode=compiler_mode,
        overdrive_count=overdrive_count,
        overdrive_reason_code=overdrive_reason_code,
        context_window_tokens=context_window_tokens,
        intent_contract=intent_contract,
        completion_contract=completion_contract,
        implementation_plan=_resolve_implementation_plan_from_artifacts(
            implementation_plan=implementation_plan,
            event_log=event_log,
            artifact_store=artifact_store,
        ),
        current_plan_step_id=current_plan_step_id,
        task_understanding=task_understanding,
    )
    compile_ms = max(0, int((time.monotonic_ns() - compile_started_ns) / 1_000_000))
    artifact_refs: List[str] = []
    context_pack_ref: Optional[str] = None
    manifest_ref: Optional[str] = None
    context_pack_content_hash: Optional[str] = None
    manifest_content_hash: Optional[str] = None

    if artifact_store is not None:
        context_pack_artifact, context_pack_content_hash = artifact_store.write_json_canonical(
            outputs.context_pack,
            content_type="application/json",
        )
        manifest_artifact, manifest_content_hash = artifact_store.write_json_canonical(
            outputs.manifest,
            content_type="application/json",
        )
        context_pack_ref = context_pack_artifact.artifact_id
        manifest_ref = manifest_artifact.artifact_id
        artifact_refs = [context_pack_ref, manifest_ref]

    event_log.append_event(
        {
            "event_type": "CONTEXTPACK_COMPILED",
            "timestamp": timestamp,
            "cwd": cwd,
            "context_pack_hash": outputs.context_pack_hash,
            "manifest_hash": outputs.manifest_hash,
            "workspace_fingerprint_hash": workspace_fingerprint_hash,
            "artifact_refs": artifact_refs,
            "context_pack_ref": context_pack_ref,
            "manifest_ref": manifest_ref,
            "intent_digest": intent_digest,
            "intent_contract_id": intent_contract_id,
            "compiler_mode": outputs.manifest["compiler_mode"],
            "untrusted_items_count": outputs.manifest["untrusted_items_count"],
            "layer_order": outputs.manifest["layer_order"],
            "total_tokens_estimate": outputs.manifest["total_tokens_estimate"],
            "sweet_zone_pct": outputs.manifest["sweet_zone_pct"],
        }
    )

    if outputs.manifest["compiler_mode"] == "overdrive":
        overdrive_token_delta = max(
            0,
            outputs.manifest["total_tokens_estimate"]
            - int(outputs.manifest["context_window_tokens"] * (HARD_CAP_NORMAL_PCT / 100)),
        )
        overdrive_cost_delta_usd = round(overdrive_token_delta * 0.000002, 8)
        score_value = float(overdrive_cost_delta_usd)
        event_log.append_event(
            {
                "event_type": "METRIC_SUMMARY",
                "timestamp": timestamp,
                "cwd": cwd,
                "judge_type": "objective",
                "mean": score_value,
                "worst": score_value,
                "stdev": 0.0,
                "scenario_family": "context_overdrive",
                "recovery_competence": False,
                "efficiency_ceiling_penalty": float(overdrive_token_delta),
                "overdrive_reason_code": outputs.manifest.get("overdrive_reason_code"),
                "overdrive_cost_delta_usd": overdrive_cost_delta_usd,
                "overdrive_token_delta": overdrive_token_delta,
                "overdrive_cost_impact": "INCREASED",
            }
        )

    resolved_outputs = CompilerOutputs(
        context_pack=outputs.context_pack,
        manifest=outputs.manifest,
        context_pack_hash=outputs.context_pack_hash,
        manifest_hash=outputs.manifest_hash,
        context_pack_ref=context_pack_ref,
        manifest_ref=manifest_ref,
        context_pack_content_hash=context_pack_content_hash,
        manifest_content_hash=manifest_content_hash,
    )
    return resolved_outputs, compile_ms


def _project_tool_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    projected: List[Dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_copy = dict(candidate)
        tool_summary = _extract_tool_summary(candidate)
        if tool_summary is None:
            projected.append(candidate_copy)
            continue

        # Preserve raw untrusted tool payloads so they are still wrapped into SCRATCH
        # as inert data, then append a runtime summary candidate for safe projection.
        if _should_preserve_untrusted_raw(candidate_copy):
            projected.append(candidate_copy)

        rewritten = dict(candidate_copy)
        rewritten["section"] = SECTION_STATE_V11
        rewritten["kind"] = "tool_output_summary"
        rewritten["source_ref"] = "derived/tool_summary"
        rewritten["authority_tier"] = "runtime"
        rewritten.pop("trust_level", None)
        rewritten["content"] = tool_summary
        rewritten["tool_output_summary"] = dict(tool_summary)
        rewritten["content_hash"] = hash_canonical_json(tool_summary)
        projected.append(rewritten)
    return projected


def _should_preserve_untrusted_raw(candidate: Dict[str, Any]) -> bool:
    if not _is_untrusted_tool_payload(candidate):
        return False
    if _has_structured_tool_summary(candidate):
        return False
    trust_level = str(candidate.get("trust_level", "")).upper()
    authority_tier = str(candidate.get("authority_tier", "")).lower()
    section = str(candidate.get("section", ""))
    if trust_level == "UNTRUSTED" or authority_tier == "untrusted":
        return True
    return section in {SECTION_UNTRUSTED, SECTION_SCRATCH, SECTION_SCRATCH_V11}


def _has_structured_tool_summary(candidate: Dict[str, Any]) -> bool:
    for key in ("tool_output_summary", "tool_summary", "receipt_summary", "summary"):
        if isinstance(candidate.get(key), Mapping):
            return True
    return isinstance(candidate.get("content"), Mapping)


def _is_untrusted_tool_payload(candidate: Dict[str, Any]) -> bool:
    trust_level = str(candidate.get("trust_level", "")).upper()
    authority_tier = str(candidate.get("authority_tier", "")).lower()
    kind = str(candidate.get("kind", "")).lower()
    source_ref = str(candidate.get("source_ref", "")).lower()
    section = str(candidate.get("section", ""))

    if trust_level == "UNTRUSTED":
        return True
    if authority_tier == "untrusted":
        return True
    if section in {SECTION_UNTRUSTED, SECTION_SCRATCH, SECTION_SCRATCH_V11} and kind in _TOOL_OUTPUT_UNTRUSTED_KINDS:
        return True
    if kind in _TOOL_OUTPUT_UNTRUSTED_KINDS:
        return True
    if source_ref.startswith("tool_") or source_ref in {"tool_result", "tool_summary"}:
        return True
    return False


def _extract_tool_summary(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    kind = str(candidate.get("kind", "")).lower()
    source_ref = str(candidate.get("source_ref", "")).lower()
    if kind not in {
        "tool_output_excerpt",
        "tool_output_summary",
        "tool_output_summary_rollup",
        "tool_result",
    } and source_ref not in {"tool_result", "tool_summary"}:
        return None

    source_summary: Optional[Dict[str, Any]] = None
    for key in ("tool_output_summary", "tool_summary", "receipt_summary", "summary"):
        value = candidate.get(key)
        if isinstance(value, Mapping):
            source_summary = dict(value)
            break
    if source_summary is None and isinstance(candidate.get("content"), Mapping):
        source_summary = dict(candidate.get("content"))  # type: ignore[arg-type]

    content_text = candidate.get("content", "")
    if not isinstance(content_text, str):
        content_text = str(content_text)

    parsed = _parse_tool_summary_from_content(content_text)
    summary: Dict[str, Any] = {
        "tool_name": _bounded_text(
            _prefer_str(source_summary, "tool_name") or parsed.get("tool_name", ""),
            80,
        ),
        "exit_code": _normalize_exit_code(source_summary, parsed),
        "duration_ms": _normalize_duration(source_summary),
        "stdout_line_count": _normalize_non_negative_int(source_summary, "stdout_line_count"),
        "stderr_line_count": _normalize_non_negative_int(source_summary, "stderr_line_count"),
        "stderr_excerpt": _bounded_text(
            _prefer_str(source_summary, "stderr_excerpt") or parsed.get("stderr_excerpt", ""),
            240,
        ),
        "key_lines": _bounded_lines(_prefer_list(source_summary, "key_lines"), max_lines=6, max_chars=160),
        "stdout_tail": _bounded_lines(_prefer_list(source_summary, "stdout_tail"), max_lines=8, max_chars=160),
        "truncation_flags": _bounded_text(
            _prefer_str(source_summary, "truncation_flags") or "UNKNOWN",
            32,
        ),
    }
    assistant_note = _bounded_text(
        _prefer_str(source_summary, "assistant_note")
        or _prefer_str(candidate, "assistant_note")
        or parsed.get("assistant_note", ""),
        280,
    )
    if assistant_note:
        summary["assistant_note"] = assistant_note
    command_synopsis = _bounded_text(
        _prefer_str(source_summary, "command_synopsis") or parsed.get("command_synopsis", ""),
        120,
    )
    if command_synopsis:
        summary["command_synopsis"] = command_synopsis
    return summary


def _build_advisory_memo_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    memo_entries: List[Dict[str, str]] = []
    for candidate in candidates:
        if str(candidate.get("kind", "")) != "tool_output_summary":
            continue
        content = candidate.get("content")
        if not isinstance(content, Mapping):
            continue
        note = _bounded_text(str(content.get("assistant_note", "")), 280)
        if not note:
            continue
        memo_entries.append(
            {
                "observed_at": str(candidate.get("observed_at", "")),
                "tool_name": _bounded_text(str(content.get("tool_name", "")), 80),
                "assistant_note": note,
            }
        )

    if not memo_entries:
        return []

    ordered = sorted(
        memo_entries,
        key=lambda entry: (
            entry.get("observed_at", ""),
            entry.get("tool_name", ""),
            entry.get("assistant_note", ""),
        ),
    )
    bounded = ordered[-ADVISORY_MEMO_MAX_NOTES:]
    content = {
        "advisory": "non_authoritative_non_governance",
        "entries": bounded,
    }
    latest_observed = bounded[-1].get("observed_at", "")
    return [
        {
            "section": SECTION_STATE_V11,
            "kind": "advisory_memo",
            "content": content,
            "source_ref": "advisory_memo",
            "observed_at": latest_observed,
            "authority_tier": "runtime",
            "validity_ttl": "P1D",
            "content_hash": hash_canonical_json(content),
        }
    ]


def _parse_tool_summary_from_content(content: str) -> Dict[str, str]:
    first_line = content.splitlines()[0] if content else ""
    parsed: Dict[str, str] = {}
    for key in ("tool_name", "exit_code", "artifact_ref", "outcome"):
        marker = f"{key}="
        if marker not in first_line:
            continue
        segment = first_line.split(marker, 1)[1]
        parsed[key] = _bounded_text(segment.split(";", 1)[0], 120)

    if "command=" in first_line and "; exit_code=" in first_line:
        command_json = first_line.split("command=", 1)[1].split("; exit_code=", 1)[0].strip()
        try:
            command_args = json.loads(command_json)
            synopsis_source = ""
            if isinstance(command_args, dict):
                command_value = command_args.get("command")
                if isinstance(command_value, list) and command_value:
                    synopsis_source = " ".join(str(item) for item in command_value)
                elif isinstance(command_value, str):
                    synopsis_source = command_value
                if synopsis_source:
                    parsed["command_synopsis"] = _bounded_text(synopsis_source, 120)
            if isinstance(command_args, dict):
                for note_key in ("assistant_note", "rationale"):
                    note_value = command_args.get(note_key)
                    if isinstance(note_value, str):
                        parsed["assistant_note"] = _bounded_text(note_value, 280)
                        break
        except Exception:
            pass

    if "\nstderr:\n" in content:
        stderr_tail = content.split("\nstderr:\n", 1)[1]
        parsed["stderr_excerpt"] = _bounded_text(stderr_tail, 240)
    return parsed


def _prefer_str(mapping: Optional[Mapping[str, Any]], key: str) -> str:
    if not isinstance(mapping, Mapping):
        return ""
    value = mapping.get(key)
    if isinstance(value, str):
        return value
    return ""


def _prefer_list(mapping: Optional[Mapping[str, Any]], key: str) -> List[str]:
    if not isinstance(mapping, Mapping):
        return []
    value = mapping.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _normalize_duration(summary: Optional[Mapping[str, Any]]) -> Optional[int]:
    if not isinstance(summary, Mapping):
        return None
    value = summary.get("duration_ms")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    return None


def _normalize_non_negative_int(summary: Optional[Mapping[str, Any]], key: str) -> int:
    if not isinstance(summary, Mapping):
        return 0
    value = summary.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0


def _normalize_exit_code(summary: Optional[Mapping[str, Any]], parsed: Mapping[str, str]) -> Optional[Any]:
    if isinstance(summary, Mapping):
        if "exit_code" in summary:
            value = summary.get("exit_code")
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return _bounded_text(value, 40)
            return None
    parsed_exit = parsed.get("exit_code")
    if not parsed_exit:
        return None
    if parsed_exit.isdigit():
        try:
            return int(parsed_exit)
        except Exception:
            return parsed_exit
    return _bounded_text(parsed_exit, 40)


def _bounded_lines(lines: List[str], *, max_lines: int, max_chars: int) -> List[str]:
    bounded: List[str] = []
    for line in lines:
        cleaned = _bounded_text(line, max_chars)
        if cleaned:
            bounded.append(cleaned)
        if len(bounded) >= max_lines:
            break
    return bounded


def _bounded_text(text: str, max_chars: int) -> str:
    cleaned = " ".join(str(text).strip().split())
    sanitized = (
        cleaned
        .replace("<<SECTION:", "<SECTION:")
        .replace("[UNTRUSTED_BASE64_START]", "[UNTRUSTED_B64_START]")
        .replace("[UNTRUSTED_BASE64_END]", "[UNTRUSTED_B64_END]")
    )
    if len(sanitized) <= max_chars:
        return sanitized
    return sanitized[: max(0, max_chars - 1)] + "…"


def _normalize_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for candidate in candidates:
        copied = dict(candidate)
        missing = REQUIRED_PROVENANCE_FIELDS - copied.keys()
        if missing:
            raise ValueError(f"Missing provenance fields: {sorted(missing)}")
        _validate_pointer_metadata(copied)
        _validate_derived_pointer_metadata(copied)
        normalized.append(copied)

    def sort_key(item: Dict[str, Any]) -> Tuple[int, str, str]:
        authority = _AUTHORITY_PRIORITY.get(str(item.get("authority_tier", "")).lower(), 99)
        return (authority, _map_candidate_to_layer(item), str(item.get("source_ref", "")))

    return sorted(normalized, key=sort_key)


def _validate_compiler_mode(
    *,
    compiler_mode: str,
    overdrive_count: int,
    overdrive_reason_code: Optional[str],
) -> None:
    if compiler_mode not in {"normal", "overdrive"}:
        raise ValueError(f"Unknown compiler mode: {compiler_mode}")
    if compiler_mode == "overdrive":
        if overdrive_count >= MAX_OVERDRIVE_STEPS_PER_RUN:
            raise ValueError("Overdrive limit exceeded for run")
        if not overdrive_reason_code:
            raise ValueError("Overdrive mode requires overdrive_reason_code")


def _detect_conflicts(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for candidate in candidates:
        conflict_key = candidate.get("conflict_key")
        if not conflict_key:
            continue
        groups.setdefault(str(conflict_key), []).append(candidate)

    conflicts: List[Dict[str, Any]] = []
    for key, items in groups.items():
        unique_contents = {item["content_hash"] for item in items}
        if len(unique_contents) > 1:
            conflicts.append(
                {
                    "conflict_key": key,
                    "source_refs": [item["source_ref"] for item in items],
                }
            )
    return conflicts


def _format_conflicts(conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(conflicts, key=lambda item: item.get("conflict_key", ""))


def _render_conflicts_text(conflicts: List[Dict[str, Any]]) -> str:
    lines: List[str] = ["Conflict deltas (read-only evidence):"]
    for conflict in _format_conflicts(conflicts):
        key = str(conflict.get("conflict_key", ""))
        refs = sorted(
            str(source_ref)
            for source_ref in conflict.get("source_refs", [])
            if isinstance(source_ref, str) and source_ref
        )
        lines.append(f"- conflict_key={key}")
        lines.append(f"  source_refs={', '.join(refs)}")
    return "\n".join(lines)


def _apply_section_budgets(layer_sections: Dict[str, List[Dict[str, Any]]], section_budgets: Dict[str, int]) -> None:
    for layer in LAYER_ORDER:
        aliases = {layer, _LAYER_TO_LEGACY_SECTION.get(layer, "")}
        budget = None
        for key in aliases:
            if key in section_budgets:
                budget = section_budgets[key]
                break
        if budget is None:
            continue
        if budget < 0:
            raise ValueError("Budget must be non-negative")
        items = layer_sections[layer]
        if len(items) <= budget:
            continue
        if layer == SECTION_EVIDENCE_V11:
            structured = [item for item in items if item.get("kind") == "verifier_structured"]
            others = [item for item in items if item.get("kind") != "verifier_structured"]
            retained = structured[:]
            remaining_slots = max(budget - len(retained), 0)
            retained.extend(_drop_oldest(others, keep=remaining_slots))
            layer_sections[layer] = retained
        else:
            layer_sections[layer] = _drop_oldest(items, keep=budget)


def _state_budget_requested(section_budgets: Mapping[str, int]) -> bool:
    for key in (SECTION_STATE, SECTION_STATE_V11):
        if key in section_budgets:
            return True
    return False


def _sync_legacy_budgets(legacy: Dict[str, List[Dict[str, Any]]], layer_sections: Dict[str, List[Dict[str, Any]]]) -> None:
    legacy[SECTION_POLICY] = list(layer_sections[SECTION_POLICY_V11])
    legacy[SECTION_DOCTRINE] = list(layer_sections[SECTION_SYSTEM_V11])
    legacy[SECTION_CONTRACTS] = list(layer_sections[SECTION_CONTRACTS])
    legacy[SECTION_TASK] = list(layer_sections[SECTION_TASK_V11])
    legacy[SECTION_PLAN] = list(layer_sections[SECTION_PLAN_V11])
    legacy[SECTION_EVIDENCE] = list(layer_sections[SECTION_EVIDENCE_V11])
    legacy[SECTION_STATE] = list(layer_sections[SECTION_STATE_V11])
    scratch_items = list(layer_sections[SECTION_SCRATCH_V11])
    legacy_scratch_items = [item for item in scratch_items if _mirror_untrusted_to_legacy(item)]
    legacy[SECTION_SCRATCH] = legacy_scratch_items
    legacy[SECTION_UNTRUSTED] = [
        item for item in legacy_scratch_items if item.get("trust_level") == "UNTRUSTED"
    ]
    if not legacy[SECTION_VERIFICATION]:
        legacy[SECTION_VERIFICATION] = [
            item for item in layer_sections[SECTION_EVIDENCE_V11] if item.get("kind") == "verifier_structured"
        ]


def _mirror_untrusted_to_legacy(candidate: Dict[str, Any]) -> bool:
    authority_tier = str(candidate.get("authority_tier", "")).lower()
    if authority_tier != "untrusted":
        return True
    kind = str(candidate.get("kind", "")).lower()
    if kind in _TOOL_OUTPUT_UNTRUSTED_KINDS:
        return False
    source_ref = str(candidate.get("source_ref", "")).lower()
    return source_ref not in {"tool_result", "governance"}


def _drop_oldest(items: List[Dict[str, Any]], *, keep: int) -> List[Dict[str, Any]]:
    if keep <= 0:
        return []
    sorted_items = sorted(items, key=lambda item: (str(item.get("observed_at", "")), str(item.get("source_ref", ""))))
    return sorted_items[-keep:]


def _map_candidate_to_layer(candidate: Dict[str, Any]) -> str:
    section = str(candidate.get("section", "")).strip()
    if section in LAYER_ORDER:
        return section

    mapping = {
        SECTION_POLICY: SECTION_POLICY_V11,
        SECTION_DOCTRINE: SECTION_SYSTEM_V11,
        SECTION_CONTRACTS: SECTION_CONTRACTS,
        SECTION_TASK: SECTION_TASK_V11,
        SECTION_PLAN: SECTION_PLAN_V11,
        SECTION_VERIFICATION: SECTION_EVIDENCE_V11,
        SECTION_EVIDENCE: SECTION_EVIDENCE_V11,
        SECTION_STATE: SECTION_STATE_V11,
        SECTION_SCRATCH: SECTION_SCRATCH_V11,
        SECTION_UNTRUSTED: SECTION_SCRATCH_V11,
        SECTION_CONFLICTS: SECTION_SCRATCH_V11,
    }
    return mapping.get(section, SECTION_SCRATCH_V11)


def _is_untrusted(candidate: Dict[str, Any], policy_config: PolicyConfig) -> bool:
    trust_level = str(candidate.get("trust_level", "")).upper()
    authority_tier = str(candidate.get("authority_tier", "")).lower()
    kind = str(candidate.get("kind", "")).lower()
    source_ref = str(candidate.get("source_ref", "")).lower()

    if trust_level == "UNTRUSTED":
        return True
    if authority_tier == "untrusted":
        return True
    if kind in {"verifier_raw", "tool_output", "tool_result", "terminal_output", "web_response"}:
        return True
    if source_ref.startswith("tool_"):
        return True
    if kind == "verifier_structured" and not policy_config.feature_flags.cc_u01:
        return True
    return False


def _validate_untrusted_tagging(candidate: Dict[str, Any]) -> None:
    trust_level = str(candidate.get("trust_level", "")).upper()
    authority_tier = str(candidate.get("authority_tier", "")).lower()
    if trust_level == "UNTRUSTED":
        return
    if authority_tier == "untrusted":
        candidate["trust_level"] = "UNTRUSTED"
        return
    kind = str(candidate.get("kind", "")).lower()
    source_ref = str(candidate.get("source_ref", "")).lower()
    if (
        kind in _TOOL_OUTPUT_UNTRUSTED_KINDS
        or kind in {"verifier_raw", "tool_output", "tool_result", "terminal_output", "web_response", "verifier_structured"}
        or source_ref.startswith("tool_")
        or source_ref in {"tool_result", "tool_summary", "verifier_raw:stdout", "verifier_raw:stderr"}
    ):
        candidate["trust_level"] = "UNTRUSTED"
        return
    raise ValueError("UNTRUSTED content missing trust_level=UNTRUSTED tag")


def _wrap_untrusted_content(candidate: Dict[str, Any]) -> Dict[str, Any]:
    wrapped = dict(candidate)
    wrapped["trust_level"] = "UNTRUSTED"
    content = wrapped.get("content", "")
    if not isinstance(content, str):
        content = str(content)

    if _is_wrapped_untrusted(content):
        wrapped["content"] = content
    else:
        annotated = _annotate_untrusted_lines(content)
        encoded = base64.b64encode(annotated.encode("utf-8")).decode("ascii")
        wrapped["content"] = (
            f"{UNTRUSTED_START}\n"
            f"trust_level=UNTRUSTED; source_ref={wrapped.get('source_ref', '')}\n"
            "encoding=base64\n"
            f"{encoded}\n"
            f"{UNTRUSTED_END}"
        )
    return wrapped


def _annotate_untrusted_lines(content: str) -> str:
    lines = content.splitlines() or [content]
    annotated: List[str] = []
    for line in lines:
        annotated.append(_sanitize_untrusted_line(line))
    return "\n".join(annotated)


def _sanitize_untrusted_line(line: str) -> str:
    trimmed = line.lstrip()
    lowered = trimmed.lower()
    for prefix in _UNTRUSTED_PREFIX_PATTERNS:
        if lowered.startswith(prefix):
            leading = line[: len(line) - len(trimmed)]
            remainder = trimmed[len(prefix) :].lstrip()
            if remainder:
                return f"{leading}[UNTRUSTED_PREFIX]: {remainder}"
            return f"{leading}[UNTRUSTED_PREFIX]:"
    return line


def _is_wrapped_untrusted(content: str) -> bool:
    trimmed = content.strip()
    if not (trimmed.startswith(UNTRUSTED_START) and trimmed.endswith(UNTRUSTED_END)):
        return False

    lines = trimmed.splitlines()
    encoding_index = None
    for idx, line in enumerate(lines):
        if line.strip() == "encoding=base64":
            encoding_index = idx
            break
    if encoding_index is None:
        return False
    if encoding_index + 1 >= len(lines):
        return False

    payload = lines[encoding_index + 1].strip()
    if not payload:
        return False
    try:
        base64.b64decode(payload.encode("ascii"), validate=True)
    except Exception:
        return False
    return True


def _validate_pointer_metadata(candidate: Dict[str, Any]) -> None:
    source_artifact_id = candidate.get("source_artifact_id")
    source_hash = candidate.get("source_hash")
    span = candidate.get("span")

    if source_artifact_id is None and source_hash is None and span is None:
        return

    if not isinstance(source_artifact_id, str) or not source_artifact_id:
        raise ValueError("Pointer metadata requires non-empty source_artifact_id")
    if not isinstance(source_hash, str) or not source_hash:
        raise ValueError("Pointer metadata requires non-empty source_hash")
    if not isinstance(span, dict):
        raise ValueError("Pointer metadata requires span dict")

    offset = span.get("offset")
    length = span.get("length")
    if not isinstance(offset, int) or not isinstance(length, int):
        raise ValueError("Pointer span requires integer offset and length")
    if offset < 0 or length < 0:
        raise ValueError("Pointer span values must be non-negative")


def _validate_derived_pointer_metadata(candidate: Dict[str, Any]) -> None:
    trust_level = str(candidate.get("trust_level", "")).upper()
    authority_tier = str(candidate.get("authority_tier", "")).upper()
    if trust_level != "DERIVED_NON_STEERING" and authority_tier != "DERIVED_NON_STEERING":
        return

    source_artifact_ids = candidate.get("source_artifact_ids")
    span_pointers = candidate.get("span_pointers")
    source_hashes = candidate.get("source_hashes")
    if not isinstance(source_artifact_ids, list) or not source_artifact_ids:
        raise ValueError("Derived artifacts require source_artifact_ids[]")
    if not isinstance(span_pointers, list) or not span_pointers:
        raise ValueError("Derived artifacts require span_pointers[]")
    if not isinstance(source_hashes, list) or not source_hashes:
        raise ValueError("Derived artifacts require source_hashes[]")


def _estimate_total_tokens(layer_sections: Dict[str, List[Dict[str, Any]]]) -> int:
    projection = ContextPackProjection(layer_sections)
    rendered_parts: List[str] = []

    doctrine_text = "\n\n".join(
        item.get("content", "")
        for item in projection.get_tier_items("DOCTRINE")
        if isinstance(item.get("content"), str) and item.get("content")
    )
    if doctrine_text:
        rendered_parts.append(doctrine_text)

    conversation_blocks = [
        item.get("content", "")
        for item in projection.get_tier_items("CONVERSATION")
        if isinstance(item.get("content"), str) and item.get("content")
    ]
    rendered_parts.extend(conversation_blocks)

    rendered = "\n\n".join(rendered_parts)
    return max(1, (len(rendered.encode("utf-8")) + 3) // 4)


def _resolve_context_window_tokens(*, policy_config: PolicyConfig, context_window_tokens: Optional[int]) -> int:
    if isinstance(context_window_tokens, int) and context_window_tokens > 0:
        return context_window_tokens
    configured = getattr(policy_config, "context_window_tokens", None)
    if isinstance(configured, int) and configured > 0:
        return configured
    return DEFAULT_CONTEXT_WINDOW_TOKENS


def _compute_percentage(total: int, window: int) -> float:
    if window <= 0:
        raise ValueError("context window must be positive")
    return round((total / window) * 100, 4)


def _enforce_hard_cap(total_tokens: int, context_window_tokens: int, compiler_mode: str) -> None:
    cap_pct = HARD_CAP_OVERDRIVE_PCT if compiler_mode == "overdrive" else HARD_CAP_NORMAL_PCT
    cap_tokens = int((context_window_tokens * cap_pct) / 100)
    if total_tokens > cap_tokens:
        raise ValueError(f"context exceeds hard cap for mode={compiler_mode}")


def _candidate_hash_payload(candidate: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(candidate)
    payload.pop("content", None)
    payload["content_hash"] = candidate.get("content_hash")
    return payload


def _build_manifest(
    *,
    candidates: List[Dict[str, Any]],
    layer_sections: Dict[str, List[Dict[str, Any]]],
    selected_candidate_ids: set[int],
    conflicts: List[Dict[str, Any]],
    compiler_mode: str,
    overdrive_reason_code: Optional[str],
    total_tokens_estimate: int,
    sweet_zone_pct: float,
    context_window_tokens: int,
    input_candidate_hashes: List[str],
    untrusted_items_count: int,
) -> Dict[str, Any]:
    selected = [candidate for candidate in candidates if id(candidate) in selected_candidate_ids]
    dropped = [candidate for candidate in candidates if id(candidate) not in selected_candidate_ids]

    dropped_entries = [
        {
            "source_ref": candidate["source_ref"],
            "drop_reason": "budget_exceeded",
        }
        for candidate in dropped
    ]

    reasons: List[str] = []
    if sweet_zone_pct < SWEET_ZONE_MIN_PCT:
        reasons.append("below_sweet_zone_min")
    if sweet_zone_pct > SWEET_ZONE_MAX_PCT:
        reasons.append("above_sweet_zone_target")

    return {
        "compiler_version": COMPILER_VERSION,
        "candidates": candidates,
        "selected": selected,
        "dropped": dropped_entries,
        "section_budgets": {layer: len(items) for layer, items in layer_sections.items()},
        "conflicts": conflicts,
        "layer_order": list(LAYER_ORDER),
        "compiler_mode": compiler_mode,
        "overdrive_reason_code": overdrive_reason_code,
        "sweet_zone_pct": sweet_zone_pct,
        "total_tokens_estimate": total_tokens_estimate,
        "context_window_tokens": context_window_tokens,
        "input_candidate_hashes": input_candidate_hashes,
        "untrusted_items_count": untrusted_items_count,
        "reasons": reasons,
    }


def _build_contract_candidates(
    *,
    intent_contract: Optional[Any],
    completion_contract: Optional[Any],
    implementation_plan: Optional[Any],
    current_plan_step_id: Optional[str],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    intent_payload = _to_mapping(intent_contract)
    if intent_payload:
        digest = {
            "hash": hash_canonical_json(intent_payload),
            "intent_contract_id": intent_payload.get("intent_contract_id"),
            "goal_statement": intent_payload.get("goal_statement"),
            "deliverables": intent_payload.get("deliverables", []),
            "acceptance_criteria": intent_payload.get("acceptance_criteria", []),
            "risk_profile": intent_payload.get("risk_profile"),
        }
        candidates.append(_contract_candidate("intent_contract_digest", digest))

    completion_payload = _to_mapping(completion_contract)
    if completion_payload:
        digest = {
            "hash": hash_canonical_json(completion_payload),
            "completion_contract_id": completion_payload.get("completion_contract_id"),
            "intent_contract_ref": completion_payload.get("intent_contract_ref"),
            "risk_class": completion_payload.get("risk_class"),
            "required_verifiers": completion_payload.get("required_verifiers", []),
            "required_artifacts": completion_payload.get("required_artifacts", []),
        }
        candidates.append(_contract_candidate("completion_contract_digest", digest))

    plan_payload = _to_mapping(implementation_plan)
    if plan_payload:
        steps = plan_payload.get("steps", [])
        current_step = current_plan_step_id
        if current_step is None and isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict) and isinstance(step.get("step_id"), str):
                    current_step = step["step_id"]
                    break
        digest = {
            "hash": hash_canonical_json(plan_payload),
            "plan_id": plan_payload.get("plan_id"),
            "plan_version_id": plan_payload.get("plan_version_id"),
            "status": plan_payload.get("status"),
            "current_step": current_step,
        }
        candidates.append(_contract_candidate("plan_digest", digest))

    return candidates


def _build_plan_candidates(
    *,
    implementation_plan: Optional[Any],
) -> List[Dict[str, Any]]:
    plan_payload = _to_mapping(implementation_plan)
    if not plan_payload:
        return []

    normalized = _normalize_plan_payload(plan_payload)
    return [
        {
            "section": SECTION_PLAN_V11,
            "kind": "implementation_plan",
            "content": normalized,
            "source_ref": "plan/artifact",
            "observed_at": "",
            "authority_tier": "runtime",
            "validity_ttl": "P365D",
            "content_hash": hash_canonical_json(normalized),
            "trust_level": "TRUSTED",
        }
    ]


def _build_task_understanding_candidates(
    *,
    task_understanding: Optional[Any],
) -> List[Dict[str, Any]]:
    payload = _to_mapping(task_understanding)
    if not payload:
        return []

    content = str(payload.get("content", "")).strip()
    if not content:
        return []

    candidate: Dict[str, Any] = {
        "section": SECTION_TASK_V11,
        "kind": str(payload.get("kind", "task_understanding")),
        "content": content,
        "source_ref": str(payload.get("source_ref", "orient_handoff")),
        "observed_at": str(payload.get("observed_at", "")),
        "authority_tier": str(payload.get("authority_tier", "runtime")),
        "validity_ttl": payload.get("validity_ttl", "P1D"),
        "content_hash": str(payload.get("content_hash", hash_canonical_json(content))),
    }

    for optional in (
        "trust_level",
        "source_artifact_ids",
        "source_hashes",
        "span_pointers",
        "source_artifact_id",
        "source_hash",
        "span",
    ):
        if optional in payload:
            candidate[optional] = payload[optional]

    return [candidate]


def _contract_candidate(kind: str, digest: Dict[str, Any]) -> Dict[str, Any]:
    content = hash_canonical_json(digest)
    return {
        "section": SECTION_CONTRACTS,
        "kind": kind,
        "content": content,
        "source_ref": f"contracts/{kind}",
        "observed_at": "",
        "authority_tier": "runtime",
        "validity_ttl": "P365D",
        "content_hash": hash_canonical_json(content),
        "trust_level": "TRUSTED",
        kind: digest,
    }


def _build_phase_card_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    runtime_candidates = [
        item
        for item in candidates
        if isinstance(item, dict) and str(item.get("source_ref", "")) == "runtime_state"
    ]
    if not runtime_candidates:
        return []

    latest = sorted(
        runtime_candidates,
        key=lambda item: (
            str(item.get("observed_at", "")),
            str(item.get("content_hash", "")),
        ),
    )[-1]
    raw_content = latest.get("content")
    payload: Dict[str, Any] = {}
    if isinstance(raw_content, Mapping):
        payload = dict(raw_content)
    elif isinstance(raw_content, str):
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, Mapping):
                payload = dict(parsed)
        except Exception:
            payload = {}

    phase = str(payload.get("phase") or payload.get("state") or "").strip()
    if not phase:
        return []
    card_text = _PHASE_CARD_TEXT.get(phase)
    if not card_text:
        return []

    observed_at = str(latest.get("observed_at", ""))
    return [
        {
            "section": SECTION_POLICY_V11,
            "kind": "phase_card",
            "content": card_text,
            "source_ref": "phase_card",
            "observed_at": observed_at,
            "authority_tier": "runtime",
            "validity_ttl": "PT1S",
            "content_hash": hash_canonical_json(card_text),
            "phase": phase,
            "trust_level": "TRUSTED",
        }
    ]


def _resolve_implementation_plan_from_artifacts(
    *,
    implementation_plan: Optional[Any],
    event_log: EventLog,
    artifact_store: Optional[ArtifactStore],
) -> Optional[Dict[str, Any]]:
    fallback = _to_mapping(implementation_plan)
    if artifact_store is None:
        return fallback

    extracted = _extract_latest_plan_payload(event_log=event_log, artifact_store=artifact_store)
    if extracted:
        return extracted
    return fallback


def _extract_latest_plan_payload(
    *,
    event_log: EventLog,
    artifact_store: ArtifactStore,
) -> Optional[Dict[str, Any]]:
    plan_payload: Optional[Dict[str, Any]] = None

    for event in event_log.events:
        event_type = str(event.get("event_type", "")).upper()
        if event_type == "PLAN_DEFINED":
            artifact_id = _first_artifact_ref(event)
            loaded = _load_plan_defined_payload(artifact_store, artifact_id)
            if loaded:
                plan_payload = loaded
            continue

        if plan_payload is None:
            continue

        if event_type == "PLAN_UPDATE":
            diff_artifact = event.get("diff_artifact_id")
            artifact_id = diff_artifact if isinstance(diff_artifact, str) else _first_artifact_ref(event)
            plan_payload = _apply_plan_update_diff(
                base_payload=plan_payload,
                artifact_store=artifact_store,
                artifact_id=artifact_id,
                event=event,
            )
            continue

        if event_type == "PLAN_STATUS_CHANGED":
            to_status = event.get("to_status")
            if isinstance(to_status, str) and to_status:
                updated = dict(plan_payload)
                updated["status"] = to_status
                plan_payload = updated

    return _normalize_plan_payload(plan_payload) if plan_payload else None


def _build_state_readiness_candidates(
    *,
    candidates: List[Dict[str, Any]],
    event_log: EventLog,
    timestamp: str,
    workspace_fingerprint_hash: Optional[str],
) -> List[Dict[str, Any]]:
    runtime_state = _extract_runtime_state_payload(candidates)
    phase_value = str(runtime_state.get("phase") or runtime_state.get("state") or "UNKNOWN")
    normalized_phase = _bounded_text(phase_value, 24) or "UNKNOWN"

    dirty_value = runtime_state.get("dirty_since_last_verify", False)
    dirty_since_last_verify = bool(dirty_value) if isinstance(dirty_value, bool) else False

    denial_code = _extract_last_denial_code(runtime_state, event_log)
    plan_status_value = runtime_state.get("plan_status")
    plan_status = (
        str(plan_status_value).strip()
        if isinstance(plan_status_value, str) and plan_status_value.strip()
        else latest_plan_status(event_log.events)
    )
    readiness = export_readiness_vector(
        events=event_log.events,
        plan_status=plan_status,
        dirty_since_last_verify=dirty_since_last_verify,
        workspace_fingerprint_hash=workspace_fingerprint_hash,
        last_verified_fingerprint_hash=last_verified_fingerprint_hash(event_log.events),
    )
    state_summary = _build_state_summary_line(
        phase=normalized_phase,
        readiness=readiness,
        denial_code=denial_code,
    )
    content: Dict[str, Any] = {
        "state_summary": state_summary,
        "readiness": readiness,
        "last_denial_code": denial_code or "NONE",
        "phase": normalized_phase,
    }
    return [
        {
            "section": SECTION_STATE_V11,
            "kind": "state_readiness",
            "content": content,
            "source_ref": "derived/state_readiness",
            "observed_at": timestamp,
            "authority_tier": "runtime",
            "validity_ttl": "PT1S",
            "content_hash": hash_canonical_json(content),
        }
    ]


def _extract_runtime_state_payload(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    runtime_candidates = [
        item
        for item in candidates
        if isinstance(item, dict)
        and str(item.get("source_ref", "")) == "runtime_state"
    ]
    if not runtime_candidates:
        return {}
    latest = sorted(
        runtime_candidates,
        key=lambda item: (
            str(item.get("observed_at", "")),
            str(item.get("content_hash", "")),
        ),
    )[-1]
    content = latest.get("content")
    if isinstance(content, Mapping):
        return dict(content)
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, Mapping):
                return dict(parsed)
        except Exception:
            return {}
    return {}


def _extract_last_denial_code(runtime_state: Mapping[str, Any], event_log: EventLog) -> Optional[str]:
    denial = runtime_state.get("last_phase_transition_denied")
    if isinstance(denial, Mapping):
        deny_reason_code = denial.get("deny_reason_code")
        if isinstance(deny_reason_code, str) and deny_reason_code.strip():
            return deny_reason_code.strip()
    return latest_phase_transition_denial_code(event_log.events)


def _build_state_summary_line(
    *,
    phase: str,
    readiness: Mapping[str, Any],
    denial_code: Optional[str],
) -> str:
    e = 1 if bool(readiness.get("explore_floor_passed")) else 0
    p = 1 if bool(readiness.get("plan_approved")) else 0
    v = 1 if bool(readiness.get("needs_verify")) else 0
    r = 1 if bool(readiness.get("can_review")) else 0
    denial = _bounded_text(denial_code or "NONE", 48) or "NONE"
    return f"STATE_SUMMARY phase={phase} denial={denial} readiness=E{e}P{p}V{v}R{r}"


def _scope_tool_receipts_to_current_phase(
    *,
    candidates: List[Dict[str, Any]],
    event_log: EventLog,
) -> List[Dict[str, Any]]:
    current_phase = _extract_current_phase_from_runtime_state(candidates)
    if not current_phase:
        return list(candidates)
    phase_start = _latest_phase_entry_timestamp(events=event_log.events, phase=current_phase)
    if not phase_start:
        return list(candidates)

    scoped: List[Dict[str, Any]] = []
    for candidate in candidates:
        if _is_tool_receipt_candidate(candidate):
            observed_at = candidate.get("observed_at")
            if isinstance(observed_at, str) and observed_at and observed_at < phase_start:
                continue
        scoped.append(candidate)
    return scoped


def _extract_current_phase_from_runtime_state(candidates: List[Dict[str, Any]]) -> Optional[str]:
    runtime_candidates = [
        item
        for item in candidates
        if isinstance(item, dict) and str(item.get("source_ref", "")) == "runtime_state"
    ]
    if not runtime_candidates:
        return None
    latest = sorted(
        runtime_candidates,
        key=lambda item: (
            str(item.get("observed_at", "")),
            str(item.get("content_hash", "")),
        ),
    )[-1]
    content = latest.get("content")
    payload: Dict[str, Any] = {}
    if isinstance(content, Mapping):
        payload = dict(content)
    elif isinstance(content, str):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, Mapping):
                payload = dict(parsed)
        except Exception:
            payload = {}
    phase = payload.get("phase") or payload.get("state")
    if isinstance(phase, str) and phase.strip():
        return phase.strip()
    return None


def _latest_phase_entry_timestamp(*, events: List[Dict[str, Any]], phase: str) -> Optional[str]:
    for event in reversed(events):
        if str(event.get("event_type", "")).upper() != "PHASE_TRANSITION":
            continue
        to_phase = event.get("to_phase")
        if isinstance(to_phase, str) and to_phase == phase:
            timestamp = event.get("timestamp")
            if isinstance(timestamp, str) and timestamp:
                return timestamp
    return None


def _is_tool_receipt_candidate(candidate: Dict[str, Any]) -> bool:
    kind = str(candidate.get("kind", "")).lower()
    source_ref = str(candidate.get("source_ref", "")).lower()
    return kind in {
        "tool_output_excerpt",
        "tool_output_summary",
        "tool_output_summary_rollup",
        "tool_result",
    } or source_ref in {"tool_result", "tool_summary"}


def _first_artifact_ref(event: Mapping[str, Any]) -> Optional[str]:
    refs = event.get("artifact_refs")
    if not isinstance(refs, list):
        return None
    for ref in refs:
        if isinstance(ref, str) and ref:
            return ref
    return None


def _load_plan_defined_payload(
    artifact_store: ArtifactStore,
    artifact_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    payload = _load_artifact_json(artifact_store, artifact_id)
    if not isinstance(payload, Mapping):
        return None
    implementation_plan = payload.get("implementation_plan")
    if not isinstance(implementation_plan, Mapping):
        return None
    return dict(implementation_plan)


def _apply_plan_update_diff(
    *,
    base_payload: Dict[str, Any],
    artifact_store: ArtifactStore,
    artifact_id: Optional[str],
    event: Mapping[str, Any],
) -> Dict[str, Any]:
    updated = dict(base_payload)
    diff_payload = _load_artifact_json(artifact_store, artifact_id)
    if not isinstance(diff_payload, Mapping):
        return updated

    changes = diff_payload.get("changes")
    if isinstance(changes, Mapping):
        new_steps = changes.get("new_steps")
        if isinstance(new_steps, list):
            normalized_steps: List[Dict[str, Any]] = []
            for step in new_steps:
                if isinstance(step, Mapping):
                    normalized_steps.append(dict(step))
            if normalized_steps:
                updated["steps"] = normalized_steps

    to_version = diff_payload.get("to_plan_version_id")
    if isinstance(to_version, int):
        updated["plan_version_id"] = to_version
    elif isinstance(event.get("to_plan_version_id"), int):
        updated["plan_version_id"] = int(event["to_plan_version_id"])

    plan_id = diff_payload.get("plan_id")
    if isinstance(plan_id, str) and plan_id:
        updated["plan_id"] = plan_id
    elif isinstance(event.get("plan_id"), str) and event.get("plan_id"):
        updated["plan_id"] = str(event["plan_id"])
    return updated


def _load_artifact_json(
    artifact_store: ArtifactStore,
    artifact_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    try:
        payload = json.loads(artifact_store.read_bytes(artifact_id).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _normalize_plan_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    steps = normalized.get("steps")
    if isinstance(steps, list):
        normalized_steps: List[Dict[str, Any]] = []
        for step in steps:
            if isinstance(step, Mapping):
                normalized_steps.append(dict(step))
        normalized["steps"] = sorted(normalized_steps, key=lambda step: str(step.get("step_id", "")))
    return normalized


def _to_mapping(value: Optional[Any]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return None
