"""Completion-evidence record gates: detect problem -> retry instruction -> refusal.

Extracted from verify_completion_protocol.py (the structural record gate and
the independence-kind gate helpers) and verify_inspection_requests.py (the
matching refusal builders) for the 500-LOC cap. Grouped here because each
gate is a cohesive detect/retry/refuse triple used by
verify_completion_protocol.py's ``verify_with_inspector`` loop:

- structural record gate: ``_completion_record_problem`` ->
  ``_completion_record_retry_instruction`` -> ``_refuse_completion_record``
- independence-kind gate (Phase 1.5, FABLE5_BATCH_AUDIT_20260709T101515Z.md
  secs 4/6): ``_completion_independence_problem`` ->
  ``_independent_derivation_retry_instruction`` ->
  ``_refuse_completion_independence``

Both gates are content-blind: they check presence, non-emptiness,
inspection_refs provenance/kind, and (for PCR only) coherence between the
model-authored per-requirement status and a completed verdict. They never infer
status from reasoning content. Judging whether evidence is actually good stays
the verifier model's job.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from .verifier_recovery import CompiledEvidenceRequirement, EvidenceClass, validate_compiled_evidence


def _known_task_clause_ids(packet: Mapping[str, Any]) -> set[str]:
    """Return exact compiler/model-authored IDs already present in the V3 packet.

    This is identity plumbing only. It does not derive clauses from task text.
    """
    known: set[str] = set()
    task_contract = packet.get("task_contract", {})
    if isinstance(task_contract, Mapping):
        for field, key in (("clauses", "clause_id"), ("method_constraints", "constraint_id")):
            rows = task_contract.get(field, ())
            if not isinstance(rows, (list, tuple)):
                continue
            known.update(
                str(item.get(key, "")).strip()
                for item in rows
                if isinstance(item, Mapping) and str(item.get(key, "")).strip()
            )
    proof_rows = packet.get("compiled_proof_requirements", ())
    if isinstance(proof_rows, (list, tuple)):
        for row in proof_rows:
            if not isinstance(row, Mapping):
                continue
            target_id = str(row.get("target_id", "")).strip()
            if target_id:
                known.add(target_id)
            obligations = row.get("obligation_ids", ())
            if isinstance(obligations, str):
                obligations = (obligations,)
            if isinstance(obligations, (list, tuple)):
                known.update(str(item).strip() for item in obligations if str(item).strip())
    return known


def _completion_record_problem(
    result: Any,
    performed_refs: set[str],
    *,
    packet: Mapping[str, Any] | None = None,
    inspection_ceilings: Mapping[str, Any] | None = None,
    inspection_routes: Mapping[str, str] | None = None,
    inspection_actual_classes: Mapping[str, Any] | None = None,
    inspection_task_state_generations: Mapping[str, int | str] | None = None,
    current_task_state_generation: int | None = None,
    inspection_snapshot_digests: Mapping[str, str] | None = None,
    current_snapshot_digest: str | None = None,
    require_risk_coverage: bool = False,
    require_requirement_status: bool = False,
) -> str:
    """Structural validity of the completion_evidence record; '' when valid.

    Presence, non-emptiness, inspection_refs resolution, and optional
    model-authored status/verdict coherence only. The reasoning content is
    never evaluated -- judging evidence quality stays the verifier model's job.
    """
    entries = tuple(getattr(result, "completion_evidence", ()) or ())
    if not entries:
        return "completion_evidence is missing or empty"
    problems: list[str] = []
    for idx, entry in enumerate(entries):
        if require_requirement_status:
            status = str(getattr(entry, "requirement_status", "") or "").strip()
            if status != "satisfied":
                problems.append(
                    f"completion_evidence[{idx}].requirement_status={status or 'missing'} "
                    "is incompatible with completed; every entry must be satisfied"
                )
        if not entry.requirement or not entry.observed or not entry.falsification_check:
            problems.append(
                f"completion_evidence[{idx}] has an empty requirement/observed/falsification_check field"
            )
            continue
        if not entry.inspection_refs:
            problems.append(f"completion_evidence[{idx}].inspection_refs is empty")
            continue
        if not any(ref in performed_refs for ref in entry.inspection_refs):
            problems.append(
                f"completion_evidence[{idx}].inspection_refs {list(entry.inspection_refs)} "
                "do not match any inspection performed this round"
            )
        if require_requirement_status and inspection_actual_classes:
            claimed_class = str(getattr(entry, "evidence_class", "") or "").strip()
            actual_classes = [
                str(inspection_actual_classes.get(ref, "") or "").strip()
                for ref in entry.inspection_refs
                if str(inspection_actual_classes.get(ref, "") or "").strip()
            ]
            if claimed_class and actual_classes:
                ranks = {item.value: index for index, item in enumerate(EvidenceClass)}
                claimed_rank = ranks.get(claimed_class, -1)
                strongest_actual = max(actual_classes, key=lambda value: ranks.get(value, -1))
                if claimed_rank > ranks.get(strongest_actual, -1):
                    problems.append(
                        f"completion_evidence[{idx}].evidence_class={claimed_class} exceeds "
                        f"the strongest kernel-observed actual evidence class={strongest_actual}; "
                        "use the actual class or a weaker class"
                    )
    # V5 wiring may provide a compiled clause contract in the neutral packet.
    # Do not infer thresholds from model prose: absent a compiled contract the
    # legacy structural gate remains the only applicable check.
    if isinstance(packet, Mapping):
        known_task_clause_ids = _known_task_clause_ids(packet)
        if known_task_clause_ids:
            for index, entry in enumerate(entries):
                for clause_id in tuple(getattr(entry, "clause_ids", ()) or ()):
                    clause_id = str(clause_id).strip()
                    if clause_id and clause_id not in known_task_clause_ids:
                        problems.append(
                            f"evidence[{index}] cites unknown clause ID: {clause_id}"
                        )
        # PCR raw-task clauses are independently falsifiable obligations.  The
        # completed-verdict record must therefore bind every compiler-owned raw
        # task clause before leaving the Verifier loop.  This is identity/coverage
        # plumbing only: the model still decides which current inspection proves
        # each clause and at what evidence class.  Catching the omission here lets
        # the existing one-shot completion-record correction repair the Verifier's
        # own record instead of sending a semantically completed task back to the
        # Solver for another task action.
        if require_requirement_status:
            task_contract = packet.get("task_contract", {})
            raw_task_clause_ids = {
                str(item.get("clause_id", "")).strip()
                for item in (task_contract.get("clauses", ()) if isinstance(task_contract, Mapping) else ())
                if isinstance(item, Mapping) and str(item.get("clause_id", "")).strip()
            }
            if raw_task_clause_ids:
                covered_task_clause_ids = {
                    str(clause_id).strip()
                    for entry in entries
                    for clause_id in tuple(getattr(entry, "clause_ids", ()) or ())
                    if str(clause_id).strip() in raw_task_clause_ids
                }
                missing_task_clause_ids = sorted(raw_task_clause_ids - covered_task_clause_ids)
                if missing_task_clause_ids:
                    problems.append(
                        "completion_evidence is missing raw task clause coverage: "
                        + ", ".join(missing_task_clause_ids)
                    )
        raw_shadow_requirements = packet.get("compiled_proof_requirements")
        if isinstance(raw_shadow_requirements, (list, tuple)) and raw_shadow_requirements:
            problems.extend(_shadow_proof_id_problems(entries, raw_shadow_requirements))
        evidence_meta = packet.get("evidence_requirements")
        if require_risk_coverage and isinstance(evidence_meta, Mapping):
            raw_risks = evidence_meta.get("false_positive_risks", ())
            if isinstance(raw_risks, str):
                raw_risks = [raw_risks]
            required_risks = {
                str(risk).strip()
                for risk in raw_risks
                if str(risk).strip()
            } if isinstance(raw_risks, (list, tuple)) else set()
            if required_risks:
                cited_risks = {
                    str(risk).strip()
                    for entry in entries
                    for risk in tuple(getattr(entry, "risk_refs", ()) or ())
                    if str(risk).strip()
                }
                # Exact declared-risk coverage is mandatory. Additional
                # explanatory annotations are harmless and do not count toward
                # coverage; rejecting them caused correct completed verdicts to
                # become false blocks after successful independent proof.
                missing_risks = sorted(required_risks - cited_risks)
                if missing_risks:
                    problems.append(
                        "completion_evidence does not address every declared false_positive_risk: "
                        + "; ".join(missing_risks)
                    )
        raw_requirements = packet.get("compiled_evidence_requirements")
        if raw_requirements is None:
            if isinstance(evidence_meta, Mapping):
                raw_requirements = evidence_meta.get("compiled_clauses")
        requirements: list[CompiledEvidenceRequirement] = []
        if isinstance(raw_requirements, (list, tuple)):
            for item in raw_requirements:
                if not isinstance(item, Mapping):
                    continue
                clause_id = str(item.get("clause_id", "")).strip()
                minimum = str(item.get("minimum_class", item.get("required_evidence_class", ""))).strip()
                if not clause_id:
                    continue
                allowed_raw = item.get("allowed_route_kinds", ())
                if isinstance(allowed_raw, str):
                    allowed_raw = [allowed_raw]
                allowed = tuple(
                    str(value).strip()
                    for value in allowed_raw
                    if str(value).strip()
                ) if isinstance(allowed_raw, (list, tuple)) else ()
                try:
                    requirements.append(CompiledEvidenceRequirement(
                        clause_id, EvidenceClass(minimum), allowed
                    ))
                except ValueError:
                    problems.append(f"unknown compiled evidence class for clause {clause_id}: {minimum}")
        if requirements:
            packet_ceilings = packet.get("inspection_evidence_ceilings", {})
            if not isinstance(packet_ceilings, Mapping):
                packet_ceilings = {}
            ceilings_raw = dict(packet_ceilings)
            ceilings_raw.update(dict(inspection_ceilings or {}))
            errors = validate_compiled_evidence(
                entries,
                requirements=requirements,
                known_inspection_ids=performed_refs,
                inspection_ceilings=ceilings_raw,
                inspection_routes=inspection_routes,
                inspection_task_state_generations=inspection_task_state_generations,
                current_task_state_generation=current_task_state_generation,
                inspection_snapshot_digests=inspection_snapshot_digests,
                current_snapshot_digest=current_snapshot_digest,
                known_clause_ids=_known_task_clause_ids(packet),
            )
            problems.extend(error.message for error in errors)
    return "; ".join(dict.fromkeys(problems))


def _shadow_proof_id_problems(
    entries: tuple[Any, ...],
    requirements: list[Any] | tuple[Any, ...],
) -> list[str]:
    """Check exact proof-ID coverage without interpreting semantic prose."""
    known = {
        str(item.get("proof_id", "")).strip()
        for item in requirements
        if isinstance(item, Mapping) and str(item.get("proof_id", "")).strip()
    }
    counts: dict[str, int] = {}
    problems: list[str] = []
    for index, entry in enumerate(entries):
        proof_ids = tuple(str(item).strip() for item in getattr(entry, "proof_ids", ()) if str(item).strip())
        if not proof_ids:
            problems.append(f"completion_evidence[{index}].proof_ids is empty for active proof requirements")
            continue
        if len(set(proof_ids)) != len(proof_ids):
            problems.append(f"completion_evidence[{index}].proof_ids contains duplicates")
        for proof_id in proof_ids:
            if proof_id not in known:
                problems.append(f"unknown proof_id: {proof_id}")
            counts[proof_id] = counts.get(proof_id, 0) + 1
    missing = sorted(known - set(counts))
    duplicates = sorted(proof_id for proof_id, count in counts.items() if count > 1)
    if missing:
        problems.append("missing proof_ids: " + ", ".join(missing))
    if duplicates:
        problems.append("proof_ids appear more than once: " + ", ".join(duplicates))
    return problems


def _completion_record_retry_instruction(problem: str) -> dict[str, Any]:
    return {
        "instruction": (
            "Protocol requires a completed verdict to carry completion_evidence "
            "per verifier_runtime_contract.completion_evidence_shape: map each "
            "decisive requirement to what your own inspection observed, cite "
            "inspection_refs containing the registered inspection_id values returned "
            "by inspections performed this round, and state the falsification_check. "
            "For outcome evidence, cite exact clause_id values from task_contract.clauses. "
            "For every task_contract.method_constraints row, cite its exact constraint_id "
            "in clause_ids and include an inspect_action_receipts inspection_ref that exposes "
            "the immutable action history used to judge that method. "
            "For every false_positive_risk declared in verifier_packet.evidence_requirements, "
            "include that exact risk text in one or more completion_evidence.risk_refs. Extra "
            "explanatory annotations are ignored and do not satisfy missing declared risks. Use "
            "only current inspection evidence that actually addresses each risk; do not relabel a "
            "metadata or same-method proxy as an independent check. "
            f"Current problem: {problem}. Return your final verdict again "
            "with a valid record, or a different verdict if the inspected state "
            "does not actually support completion."
        ),
    }


def _refuse_completion_record(problem: str) -> str:
    """Build the uncertain_missing_evidence refusal for an invalid completion_evidence record.

    Shared by the structural gate (missing/empty/unresolved refs) and the
    malformed-shape path (present but wrong-typed record) -- same protocol
    event either way: the completed verdict is refused, never silently
    accepted or crashed on.
    """
    return json.dumps({
        "verdict": "uncertain_missing_evidence",
        "confidence": "high",
        "summary": (
            "Completion cannot be accepted: the completed verdict's "
            f"completion_evidence record is invalid ({problem})."
        ),
        "missing_evidence_requests": [
            "Return completed only with completion_evidence.inspection_refs containing registered inspection_id values from this verification round.",
        ],
        "findings": [
            {
                "finding_id": "vf-completion-evidence-record",
                "verdict": "uncertain_missing_evidence",
                "priority": "blocking",
                "summary": "Completed verdict lacked a valid requirement->observed completion_evidence record.",
                "evidence": [problem],
                "repair_instruction": (
                    "Surface inspectable current-state evidence for each completion requirement; "
                    "completion is accepted only with a resolvable completion_evidence record."
                ),
                "applies_to": ["completion_evidence"],
            },
        ],
    })


def _completion_independence_problem(result: Any, independent_refs: set[str]) -> str:
    """Whether a completed verdict cites an independent-derivation inspection.

    '' when at least one completion_evidence.inspection_refs entry (anywhere
    in the record) resolves to an independent-derivation inspection kind.
    Callers gate this on the runtime evidence contract having flagged the task's claims as
    machine-re-derivable
    (packet.evidence_requirements.re_derivable_claims) -- when not flagged,
    this check is not consulted and behavior is unchanged.

    Content-blind: this checks only the KIND of the cited inspection
    (already resolved into ``independent_refs`` by
    ``_independent_derivation_refs``), never whether the reasoning in the
    record is correct.
    """
    entries = tuple(getattr(result, "completion_evidence", ()) or ())
    cited: set[str] = set()
    for entry in entries:
        cited |= set(getattr(entry, "inspection_refs", ()) or ())
    if cited & independent_refs:
        return ""
    return (
        "no completion_evidence.inspection_refs resolve to an independent-derivation "
        "inspection performed this round (compare_initial_path, overlay_run_command, rerun_check, probe_port, "
        "probe_http, probe_process, or perceive_artifact); this task flags its decisive "
        "claim(s) as machine-re-derivable, so reading a solver-produced artifact alone "
        "is not sufficient"
    )


def _independent_derivation_retry_instruction(problem: str) -> dict[str, Any]:
    return {
        "instruction": (
            "This task's evidence_requirements.re_derivable_claims marks its decisive claim(s) as "
            "machine-re-derivable. Protocol requires at least one completion_evidence "
            "inspection_ref to resolve to an inspection you performed independently -- "
            "compare_initial_path, overlay_run_command, rerun_check, a probe_port/probe_http/probe_process live "
            "check, or your own perceive_artifact reading -- not only read_file, "
            "read_output, or receipt/history inspection of a solver-produced artifact. "
            f"Current problem: {problem}. Submit a bounded inspection request performing "
            "that independent derivation, then return your final verdict."
        ),
    }


def _refuse_completion_independence(problem: str) -> str:
    """Build the uncertain_missing_evidence refusal for a missing independent-derivation ref.

    Phase 1.5 closure for the false-clean failure mode: a completed verdict
    whose record is structurally valid but backed only by inspection of
    solver-produced artifacts, on a task whose decisive claims are flagged
    machine-re-derivable, is refused rather than accepted.
    """
    return json.dumps({
        "verdict": "uncertain_missing_evidence",
        "confidence": "high",
        "summary": (
            "Completion cannot be accepted: the completed verdict's "
            f"completion_evidence record is invalid ({problem})."
        ),
        "missing_evidence_requests": [
            "Return completed only after independently deriving the decisive claim via compare_initial_path, overlay_run_command, rerun_check, a live probe, or your own perceive_artifact reading.",
        ],
        "findings": [
            {
                "finding_id": "vf-completion-evidence-independence",
                "verdict": "uncertain_missing_evidence",
                "priority": "blocking",
                "summary": "Completed verdict did not cite an independent-derivation inspection for a machine-re-derivable claim.",
                "evidence": [problem],
                "repair_instruction": (
                    "Independently re-derive the decisive claim (overlay execution, a live probe, "
                    "or your own perception) rather than only reading solver-produced artifacts, "
                    "then resubmit a completed verdict citing that inspection."
                ),
                "applies_to": ["completion_evidence"],
            },
        ],
    })
