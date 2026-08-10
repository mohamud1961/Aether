"""Completion-evidence protocol enforcement and the verify_with_inspector loop.

Extracted from model_hooks.py for the 500-LOC cap. The record/independence
gate helpers (problem detection, retry instructions, and refusal builders)
were further extracted to verify_completion_gates.py for the same cap;
imported back below unchanged.

Design of record: audit addendum (FABLE5_ADVERSARIAL_AUDIT_20260708T165639Z.md)
Concern 1 -- the harness checks presence, non-emptiness, and that
inspection_refs resolve to inspections actually performed in the round. It
never evaluates reasoning content. Phase 1.5 (FABLE5_BATCH_AUDIT_20260709T101515Z.md
secs 4/6) adds a content-blind independence-kind requirement: when the
architect flags a task's decisive claims as machine-re-derivable
(``verifier_packet.evidence_requirements.re_derivable_claims``), a completed verdict must also cite
an inspection of an independent-derivation kind, not only a read of a
solver-produced artifact.
"""
from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any, Mapping

from .ledger import ExecutionLedger
from .method_independence import (
    executed_observed_implementations,
    overlapping_accumulator_problem,
    same_method_overlap,
)
from .inspection_registry import (
    admissible_verdict_refs,
    inspection_actual_classes_from_results,
    inspection_ceilings_from_results,
    inspection_route_kinds_from_results,
)
from .model_prompts import VERIFIER_RUNTIME_CONTRACT
from .persistent_verifier_prompt import verifier_runtime_contract_for
from .persistent_verifier_context import verifier_packet_for_model
from .runtime_ir import CompiledRuntime
from .verifier import (
    CompletionEvidenceShapeError,
    METHOD_VALIDITY_SHAPE,
    MethodValidityShapeError,
    parse_model_verifier_result,
)
from .verifier_inspector import (
    TASK_PROMPT_REF,
    V3_DERIVED_INSPECTION_EXAMPLE,
    VerifierInspectionProtocolError,
    invalid_authoritative_source_refs,
    parse_verifier_inspection_requests,
)
from .verifier_budget import VerifierBudgetError, VerifierPhaseBudget, VerifierPhaseState
from .verify_completion_gates import (
    _completion_independence_problem,
    _completion_record_problem,
    _completion_record_retry_instruction,
    _independent_derivation_retry_instruction,
    _refuse_completion_independence,
    _refuse_completion_record,
)
from .verify_inspection_requests import (
    _basis_refs_from_inspections,
    _bound_input_refs_from_inspections,
    _completed_inspection_is_semantically_grounded,
    _default_completion_inspection_requests,
    _independent_derivation_refs,
    _inspections_from_missing_evidence,
    _model_output_error,
    _refs_from_inspections,
    _structured_missing_evidence_requests,
    _verifier_identity_prompt_for,
    _verifier_max_output_tokens,
)

if TYPE_CHECKING:
    from .model_hooks import ModelHooks


def _inspection_protocol_correction(exc: Exception) -> dict[str, Any]:
    """Render a schema-derived correction without task-specific repair hints."""
    if isinstance(exc, VerifierInspectionProtocolError):
        return {
            "instruction": (
                "Your overlay command was not executed because its V3 verification_plan has the listed "
                "schema defects. Return the same inspect object with every missing field supplied and every "
                "invalid field removed or corrected; do not add prose outside JSON."
            ),
            "missing": list(exc.missing),
            "invalid": list(exc.invalid),
            "v3_overlay_request_example": V3_DERIVED_INSPECTION_EXAMPLE,
        }
    return {}


def _provider_envelope_protocol_error(exc: Exception) -> str:
    """Return a narrowly retryable structured-output error code, if any.

    The rejected response remains non-authoritative and executes nothing.  One
    bounded correction is allowed only for serialization/cardinality defects
    where the model may restate the same decision.  Refusals, truncation,
    transport failures, and choice-count failures remain terminal.
    """
    if type(exc).__name__ != "AzureProviderOutputError":
        return ""
    code = str(getattr(exc, "code", "") or "").strip()
    if (
        code.startswith("provider_envelope_")
        or code.startswith("provider_direct_turn_")
        or code == "multiple_distinct_assistant_outputs"
    ):
        return code
    return ""


def _provider_protocol_correction(code: str) -> dict[str, str]:
    """Render the exact bounded restatement contract for the active transport."""
    if code.startswith("provider_direct_turn_"):
        instruction = (
            "Your previous provider response was rejected and none of its candidate turns was executed. "
            "Return the same semantic decision again as exactly one strict outer JSON object with the "
            "sole key turn. turn must contain exactly one complete Verifier protocol state: either one "
            "inspect request object or one verifier verdict object. Do not emit prose, duplicate objects, "
            "concatenated alternatives, or multiple candidate turns."
        )
    else:
        instruction = (
            "Your previous provider response was not accepted as one valid Verifier envelope. "
            "Return the same semantic decision again as exactly one strict outer JSON object with only "
            "the key payload_json. payload_json must be one complete JSON object for either an inspect "
            "request or a verifier verdict. Do not emit prose, duplicate objects, truncated JSON, or "
            "multiple candidate responses."
        )
    return {
        "instruction": instruction,
        "provider_protocol_error": code,
        "rejected_response_executed": "false",
    }


def _budget_correction_payload(
    exc: VerifierBudgetError,
    budget: VerifierPhaseBudget,
) -> dict[str, Any]:
    """Return precise, task-agnostic guidance for one bounded budget repair."""
    problem = str(exc)
    instruction = (
        "Your inspection batch was not executed because it exceeded the structural phase budget. "
        "Return a non-equivalent bounded batch; do not add prose outside JSON."
    )
    limits: dict[str, int] = {}
    if "either independent direct observations or derived executions" in problem:
        instruction = (
            "The previous inspection turn mixed causal phases and nothing in that batch was executed. "
            "Return one homogeneous inspect turn: either only independent direct observations, or only "
            "disposable-overlay/derived operations (rerun_check, overlay_write_fixture, overlay_run_command). "
            "If a derived method needs a direct observation, request the observation first and use its returned "
            "inspection ID in a later derived turn. Do not add prose outside JSON."
        )
    elif "direct observation span exceeds" in problem or "content byte budget" in problem:
        limits["max_result_bytes_per_request"] = budget.max_result_bytes_per_request
        limits["max_result_bytes_per_batch"] = budget.max_result_bytes_per_batch
        instruction = (
            f"The previous direct observation exceeded the {budget.max_result_bytes_per_request}-byte "
            "content limit and was not admitted. Return a non-equivalent bounded request with span at "
            f"most {budget.max_result_bytes_per_request} bytes and keep the whole batch within "
            f"{budget.max_result_bytes_per_batch} serialized bytes. Prefer the smallest observation that "
            "resolves the gap. Do not add prose outside JSON."
        )
    elif "envelope byte budget" in problem:
        limits["max_result_bytes_per_request"] = budget.max_result_bytes_per_request
        limits["max_result_envelope_bytes_per_request"] = budget.max_result_envelope_bytes_per_request
        limits["max_result_bytes_per_batch"] = budget.max_result_bytes_per_batch
        instruction = (
            f"The previous inspection result exceeded the {budget.max_result_envelope_bytes_per_request}-byte "
            "serialized per-result envelope limit after provenance metadata was attached. Request a smaller "
            "non-equivalent observation while keeping direct content at or below "
            f"{budget.max_result_bytes_per_request} bytes and the batch at or below "
            f"{budget.max_result_bytes_per_batch} serialized bytes. Do not add prose outside JSON."
        )
    elif "tool-lifecycle budget" in problem:
        limits["max_tool_lifecycle_s_per_batch"] = budget.max_tool_lifecycle_s_per_batch
        instruction = (
            f"The previous inspection lifecycle exceeded the {budget.max_tool_lifecycle_s_per_batch}-second "
            "wall-time safety bound including overlay setup and teardown. Its result was not admitted. "
            "Return a smaller non-equivalent inspection or a fail-closed verdict; do not add prose outside JSON."
        )
    elif "tool-execution budget" in problem:
        limits["max_tool_execution_s_per_batch"] = budget.max_tool_execution_s_per_batch
        instruction = (
            f"The previous verifier-authored command execution exceeded the {budget.max_tool_execution_s_per_batch}-second "
            "tool budget and its result was not admitted. Return a materially cheaper non-equivalent "
            "inspection method. Reduce computational complexity, resolution, data volume, or output work; "
            "cosmetic shortening of the same algorithm is not a correction. Do not add prose outside JSON."
        )
    return {
        "instruction": instruction,
        "protocol_errors": [problem],
        "budget_limits": limits,
        "rejected_result_admitted": False,
    }


def _packet_re_derivable_claims(packet: Mapping[str, Any]) -> tuple[str, ...]:
    """Read the canonical nested contract, retaining legacy replay support."""
    evidence_requirements = packet.get("evidence_requirements", {})
    if isinstance(evidence_requirements, Mapping):
        nested = evidence_requirements.get("re_derivable_claims", ())
        if isinstance(nested, str):
            nested = [nested]
        if isinstance(nested, (list, tuple)):
            claims = tuple(str(item).strip() for item in nested if str(item).strip())
            if claims:
                return claims
    legacy = packet.get("re_derivable_claims", ())
    if isinstance(legacy, str):
        legacy = [legacy]
    if isinstance(legacy, (list, tuple)):
        return tuple(str(item).strip() for item in legacy if str(item).strip())
    return ()


_CIRCULAR_PROXY_RISK_RE = re.compile(
    # Activate circular source-value extraction checks only when the Architect
    # explicitly names a descriptive-source proxy.  Regex parsing and
    # same-method risks have separate, more precise guards and must not make
    # every independent aggregation that uses a regex look circular.
    r"\b(metadata|comment|label|annotation|descriptive|source[- ]declared)\b",
    re.IGNORECASE,
)

_CIRCULAR_EXTRACTION_TARGET_RE = re.compile(
    r"\b(label|comment|annotation|metadata|declared|descriptive|object[-_ ]?name)\b",
    re.IGNORECASE,
)


_SAME_METHOD_RISK_RE = re.compile(
    r"\b(same[- ]method|same[- ]algorithm|same[- ]heuristic|validated only by the same|reuses? the solver(?:'s)? method)\b",
    re.IGNORECASE,
)


def _packet_declares_same_method_risk(packet: Mapping[str, Any]) -> bool:
    requirements = packet.get("evidence_requirements", {})
    if not isinstance(requirements, Mapping):
        return False
    risks = requirements.get("false_positive_risks", ())
    if isinstance(risks, str):
        risks = (risks,)
    return isinstance(risks, (list, tuple)) and any(
        _SAME_METHOD_RISK_RE.search(str(risk)) for risk in risks
    )


def _packet_declares_circular_proxy_risk(packet: Mapping[str, Any]) -> bool:
    """Whether the packet explicitly warns against descriptive/self-check proof.

    This is contract-driven rather than format- or task-driven: only an
    Architect-declared false-positive risk activates the stricter receipt
    check below.
    """
    requirements = packet.get("evidence_requirements", {})
    if not isinstance(requirements, Mapping):
        return False
    risks = requirements.get("false_positive_risks", ())
    if isinstance(risks, str):
        risks = (risks,)
    return isinstance(risks, (list, tuple)) and any(
        _CIRCULAR_PROXY_RISK_RE.search(str(risk)) for risk in risks
    )



def _compiled_outcome_clause_ids(compiled: Any) -> set[str]:
    """Return exact compiler-owned outcome clause IDs usable by Verifier derivations.

    Architect-backed runtimes use the certified proof contract. PERSISTENT intentionally
    has no Architect proof contract, so its exact raw-task TaskClause IDs are the
    only compiler-owned outcome identifiers. Never accept model-invented IDs.
    """
    proof_ids = {
        str(row.get("clause_id", "")).strip()
        for row in getattr(compiled, "proof_contract", ())
        if str(row.get("clause_id", "")).strip()
    }
    if proof_ids:
        return proof_ids
    task_contract = getattr(compiled, "task_contract", None)
    return {
        str(item).strip()
        for item in getattr(task_contract, "clause_ids", ())
        if str(item).strip()
    }

def verify_with_inspector(
    hooks: "ModelHooks",
    packet: Mapping[str, Any],
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    inspector,
) -> str:
    """Bounded-rounds verifier loop with read-only inspection and the completion-evidence gate.

    ``hooks`` is the owning ``ModelHooks`` instance: this is a pure move of
    the former ``ModelHooks.verify_with_inspector`` method body into a
    module-level function (``self`` -> ``hooks``) so the gate machinery can
    live outside model_hooks.py while ``ModelHooks`` keeps the same bound
    method other callers (e.g. kernel_verifier.py) already depend on.
    """
    hooks.last_parse_errors = []
    phase_state = VerifierPhaseState(VerifierPhaseBudget.from_environment())
    user_payload = {
        "verifier_runtime_contract": verifier_runtime_contract_for(
            compiled, VERIFIER_RUNTIME_CONTRACT,
        ),
        "verifier_phase_budget": {
            "max_direct_requests_per_batch": phase_state.budget.max_direct_requests_per_batch,
            "max_investigation_batches": phase_state.budget.max_investigation_batches,
            "max_derived_execution_batches": phase_state.budget.max_derived_execution_batches,
            "max_model_calls": phase_state.budget.max_model_calls,
            "max_result_bytes_per_request": phase_state.budget.max_result_bytes_per_request,
            "max_result_envelope_bytes_per_request": phase_state.budget.max_result_envelope_bytes_per_request,
            "max_result_bytes_per_batch": phase_state.budget.max_result_bytes_per_batch,
            "max_tool_execution_s_per_batch": phase_state.budget.max_tool_execution_s_per_batch,
            "max_tool_lifecycle_s_per_batch": phase_state.budget.max_tool_lifecycle_s_per_batch,
        },
        "verifier_packet": verifier_packet_for_model(compiled, packet),
        "authoritative_task_prompt": compiled.task_prompt,
        "ledger_receipt_count": len(ledger.all_receipts()),
    }
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": _verifier_identity_prompt_for(compiled),
        },
        {"role": "user", "content": json.dumps(user_payload, default=str, sort_keys=True)},
    ]
    require_v3_admissibility = packet.get("verifier_evidence_admissibility_version") == "v3"
    # F94: PERSISTENT asks the Verifier to classify each completion requirement in a
    # structured field. The kernel checks only verdict/status coherence; it
    # never derives status from prose, task content, or inspection bytes.
    require_structured_completion_status = (
        str(getattr(compiled, "solver_turn_protocol", "") or "") == "persistent_v0"
    )
    inspected = False
    missing_evidence_realized = False
    record_retry_used = False
    independence_retry_used = False
    # Architect-flagged trigger (Phase 1.5): when the task names claims
    # that are machine-re-derivable, a completed verdict must cite an
    # independent-derivation inspection. Absent/empty means unflagged --
    # unchanged legacy behavior, no independence requirement applied.
    require_independent_derivation = bool(_packet_re_derivable_claims(packet))
    performed_refs: set[str] = set()
    performed_independent_refs: set[str] = set()
    performed_ceilings: dict[str, str] = {}
    performed_routes: dict[str, str] = {}
    performed_actual_classes: dict[str, str] = {}
    available_authoritative_refs: set[str] = {TASK_PROMPT_REF}
    available_bound_input_refs: set[str] = {TASK_PROMPT_REF}
    executed_overlay_refs: set[str] = set()
    method_validity_retry_used = False
    method_revision_retry_used = False
    admissibility_retry_used = False
    last_inspection_results: list[dict[str, Any]] = []
    observed_source_texts: list[str] = []

    def invalid_clause_bindings(requests) -> tuple[str, ...]:
        """Validate exact compiler-owned clause IDs before any inspection runs.

        Derived overlay commands bind to certified outcome-proof clauses.
        Action-history inspections bind only to Architect-authored required
        method constraints. The kernel checks identity and duplicates, never
        whether receipt content semantically satisfies the method prose.
        """
        proof_clause_ids = _compiled_outcome_clause_ids(compiled)
        task_contract = getattr(compiled, "task_contract", None)
        method_clause_ids = {
            str(item.constraint_id).strip()
            for item in getattr(task_contract, "method_constraints", ())
            if str(item.constraint_id).strip()
        }
        errors: list[str] = []
        for request in requests:
            declared_rows = tuple(
                str(item).strip() for item in request.clause_ids if str(item).strip()
            )
            if len(set(declared_rows)) != len(declared_rows):
                errors.append(f"{request.request_id}: duplicate clause_ids")
                continue
            declared = set(declared_rows)
            if request.kind == "overlay_run_command" and request.evidence_mode == "derived":
                if proof_clause_ids and not declared:
                    errors.append(
                        f"{request.request_id}: missing verification_plan.clause_ids"
                    )
                unknown = sorted(declared - proof_clause_ids)
                if unknown:
                    errors.append(
                        f"{request.request_id}: unknown verification_plan.clause_ids={','.join(unknown)}"
                    )
                continue
            if request.kind == "inspect_action_receipts":
                if method_clause_ids and not declared:
                    errors.append(f"{request.request_id}: missing method clause_ids")
                unknown = sorted(declared - method_clause_ids)
                if unknown:
                    errors.append(
                        f"{request.request_id}: unknown method clause_ids={','.join(unknown)}"
                    )
        return tuple(errors)

    def invalid_proof_bindings(requests) -> tuple[str, ...]:
        errors = list(_invalid_shadow_proof_bindings(requests, compiled))
        requirements_by_id = {
            str(item.proof_id): item for item in compiled.proof_requirements
        }
        for request in requests:
            if request.kind == "inspect_action_receipts" and request.proof_ids:
                invalid = sorted(
                    proof_id for proof_id in request.proof_ids
                    if proof_id in requirements_by_id
                    and str(requirements_by_id[proof_id].target_type) == "outcome"
                    and not str(requirements_by_id[proof_id].target_id).strip()
                )
                if invalid:
                    errors.append(
                        f"{request.request_id}: inspect_action_receipts cannot bind "
                        + "outcome proof_ids=" + ",".join(invalid)
                    )
        return tuple(errors)

    def execute_budgeted(requests):
        phase_state.classify_and_reserve(requests)
        started = time.monotonic()
        results = inspector(requests)
        phase_state.validate_results(results, elapsed_s=time.monotonic() - started)
        for request, row in zip(requests, results):
            if request.kind != "read_file" or row.get("error"):
                continue
            excerpt = str(row.get("excerpt", "") or "")
            if excerpt:
                observed_source_texts.append(excerpt)
        return results

    while phase_state.has_model_call_capacity:
        try:
            phase_state.reserve_model_call()
            raw = hooks.call_verifier(
                messages,
                max_output_tokens=_verifier_max_output_tokens(),
            )
            setattr(hooks, "last_raw_verifier_output", raw)
        except Exception as exc:
            hooks.last_parse_errors.append(str(exc))
            provider_error = _provider_envelope_protocol_error(exc)
            if provider_error and phase_state.has_model_call_capacity:
                try:
                    phase_state.reserve_provider_correction()
                except VerifierBudgetError:
                    raise _model_output_error("verifier provider-correction budget exhausted") from exc
                # Do not echo the malformed provider text back into the next
                # prompt.  The valid prior transcript remains available, and
                # the model receives only the generic contract defect plus a
                # bounded instruction to restate its own decision.
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        _provider_protocol_correction(provider_error),
                        sort_keys=True,
                    ),
                })
                continue
            raise
        try:
            result = parse_model_verifier_result(raw)
        except CompletionEvidenceShapeError as shape_exc:
            # The verdict JSON itself parsed and named completion_evidence;
            # only that field's shape is wrong (e.g. a list of strings,
            # the pre-Phase-1 stub shape). Route to the SAME record-
            # problem retry the structural gate below uses, sharing its
            # one-retry budget -- never the generic "not valid protocol
            # JSON" path, which would misdirect the model to resend a
            # bare verdict/confidence/summary and could burn every
            # remaining round chasing the wrong fix.
            hooks.last_parse_errors.append(str(shape_exc))
            if phase_state.has_model_call_capacity and not record_retry_used:
                record_retry_used = True
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        _completion_record_retry_instruction(str(shape_exc)),
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
            return _refuse_completion_record(str(shape_exc))
        except MethodValidityShapeError as shape_exc:
            hooks.last_parse_errors.append(str(shape_exc))
            if phase_state.has_model_call_capacity and not method_validity_retry_used:
                method_validity_retry_used = True
                messages.append({"role": "assistant", "content": raw})
                conditional_missing = list(shape_exc.missing)
                if executed_overlay_refs and "execution_ref" not in conditional_missing:
                    conditional_missing.append("execution_ref")
                messages.append({
                    "role": "user",
                    "content": json.dumps({
                        "instruction": (
                            "Your verdict JSON parsed, but method_validity is incomplete. "
                            "Return the same semantic verdict with every missing field supplied. "
                            "execution_ref is required only when this verification round executed a "
                            "derived overlay; otherwise method_validity may be null. Do not switch to "
                            "an inspection request and do not add prose outside JSON."
                        ),
                        "missing": conditional_missing,
                        "invalid": list(shape_exc.invalid),
                        "method_validity_shape": METHOD_VALIDITY_SHAPE,
                    }, default=str, sort_keys=True),
                })
                continue
            raise _model_output_error(
                "verifier method-validity correction exhausted: " + str(shape_exc)
            ) from shape_exc
        except Exception as verdict_exc:
            try:
                requests = parse_verifier_inspection_requests(
                    raw, require_derived_contract=require_v3_admissibility,
                )
            except Exception as inspection_exc:
                hooks.last_parse_errors.append(f"{verdict_exc}; {inspection_exc}")
                if phase_state.has_model_call_capacity:
                    try:
                        phase_state.reserve_protocol_correction()
                    except VerifierBudgetError:
                        raise _model_output_error("verifier protocol-correction budget exhausted") from inspection_exc
                    protocol_error = str(inspection_exc)
                    correction = _inspection_protocol_correction(inspection_exc)
                    if correction:
                        instruction = correction["instruction"]
                    elif "top-level kind='overlay_run_command'" in protocol_error:
                        instruction = (
                            "Your overlay command was not executed because its request is missing the top-level "
                            "kind. Return the same inspect object with the request field "
                            "kind='overlay_run_command', plus verification_plan and execution; do not add prose outside JSON."
                        )
                    elif "exceeds maximum" in protocol_error:
                        instruction = (
                            "Your inspection request exceeded the per-round limit. Return exactly one inspect object "
                            "within the advertised direct-observation batch limit; prioritize the smallest observations needed before any derived command."
                        )
                    elif "execution.command" in protocol_error:
                        instruction = (
                            "Your overlay command was not executed because execution.command is required. "
                            "Put executable text in execution.command, not in verification_plan.method_summary. "
                            "Return the same inspect object with verification_plan as prose and execution "
                            "as {kind:'overlay_run_command', command:'...'}; do not add prose outside JSON."
                        )
                    else:
                        instruction = (
                            "Your previous verifier message was not valid protocol JSON. "
                            "Return exactly one JSON object and no prose. The object must "
                            "be either a final verifier verdict with fields verdict, "
                            "confidence, and summary, or an inspection request with "
                            "kind='inspect' and a non-empty requests list."
                        )
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": json.dumps(
                            correction or {"instruction": instruction},
                            default=str,
                            sort_keys=True,
                        ),
                    })
                    continue
                raise
            invalid_refs = invalid_authoritative_source_refs(
                requests,
                available_refs=available_authoritative_refs,
                available_input_refs=available_bound_input_refs,
            )
            invalid_bindings = invalid_clause_bindings(requests)
            invalid_proof_ids = invalid_proof_bindings(requests)
            if invalid_bindings:
                hooks.last_parse_errors.extend(invalid_bindings)
                if phase_state.has_model_call_capacity:
                    try:
                        phase_state.reserve_protocol_correction()
                    except VerifierBudgetError:
                        raise _model_output_error("verifier protocol-correction budget exhausted")
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": json.dumps({
                        "instruction": (
                            "Correct only the structural clause binding. Derived overlay commands use "
                            "exact outcome clause IDs from the compiled proof contract. "
                            "inspect_action_receipts uses exact required-method constraint IDs from "
                            "verifier_packet.task_contract.method_constraints. Do not add prose outside JSON."
                        ),
                        "available_outcome_clause_ids": sorted(_compiled_outcome_clause_ids(compiled)),
                        "available_method_clause_ids": sorted({
                            str(item.constraint_id).strip()
                            for item in getattr(
                                getattr(compiled, "task_contract", None),
                                "method_constraints", (),
                            )
                            if str(item.constraint_id).strip()
                        }),
                        "protocol_errors": list(invalid_bindings),
                    }, default=str, sort_keys=True)})
                    continue
                raise _model_output_error("verifier inspection request omitted a valid proof-clause binding")
            if invalid_proof_ids:
                hooks.last_parse_errors.extend(invalid_proof_ids)
                if phase_state.has_model_call_capacity:
                    try:
                        phase_state.reserve_protocol_correction()
                    except VerifierBudgetError:
                        raise _model_output_error("verifier proof-id correction budget exhausted")
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": json.dumps({
                        "instruction": (
                            "Proof IDs are kernel-owned current-contract identifiers. Do not execute this "
                            "inspection request with unknown or duplicate proof_ids. Return the same inspect "
                            "object with unique IDs from verifier_packet.compiled_proof_requirements, or omit "
                            "proof_ids for exploratory evidence."
                        ),
                        "available_proof_ids": sorted({
                            str(requirement.proof_id).strip()
                            for requirement in compiled.proof_requirements
                        }),
                        "protocol_errors": list(invalid_proof_ids),
                    }, default=str, sort_keys=True)})
                    continue
                raise _model_output_error("verifier inspection request cited invalid proof IDs")
            if invalid_refs:
                hooks.last_parse_errors.extend(invalid_refs)
                if phase_state.has_model_call_capacity:
                    try:
                        phase_state.reserve_protocol_correction()
                    except VerifierBudgetError:
                        raise _model_output_error("verifier protocol-correction budget exhausted")
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": json.dumps({
                        "instruction": (
                            "Do not execute a command from an unavailable input or from evidence requested in the same round. "
                            "verification_plan.basis contains "
                            "only earlier current direct-admissible observations that provide proof authority. "
                            "verification_plan.bound_input_refs binds the command's causal inputs and may additionally "
                            "include an earlier successful verifier-authored overlay_write_fixture inspection ID. "
                            "A fixture is an exploratory test stimulus only: never put its ID in basis, completion_evidence, "
                            "or method_validity.authoritative_source_refs. If a fixture is needed, create it in one VERIFY "
                            "turn, then use its returned inspection ID as a bound input in a later VERIFY turn."
                        ),
                        "available_authoritative_source_refs": sorted(available_authoritative_refs),
                        "available_bound_input_refs": sorted(available_bound_input_refs),
                        "protocol_errors": list(invalid_refs),
                    }, default=str, sort_keys=True)})
                    continue
                raise _model_output_error("verifier inspection request cited unavailable authoritative source refs")
            if not phase_state.has_model_call_capacity:
                raise _model_output_error(
                    "verifier requested inspection with no remaining verdict model-call capacity"
                )
            try:
                results = execute_budgeted(requests)
            except VerifierBudgetError as exc:
                hooks.last_parse_errors.append(str(exc))
                if phase_state.has_model_call_capacity:
                    try:
                        phase_state.reserve_budget_correction()
                    except VerifierBudgetError:
                        raise _model_output_error("verifier budget-correction budget exhausted") from exc
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": json.dumps(
                            _budget_correction_payload(exc, phase_state.budget),
                            default=str,
                            sort_keys=True,
                        ),
                    })
                    continue
                raise _model_output_error(str(exc)) from exc
            inspected = True
            performed_refs |= _refs_from_inspections(requests, results)
            available_authoritative_refs |= _basis_refs_from_inspections(requests, results)
            available_bound_input_refs |= _bound_input_refs_from_inspections(requests, results)
            executed_overlay_refs |= {
                str(row.get("inspection_id", "")).strip()
                for request, row in zip(requests, results)
                if request.kind == "overlay_run_command" and not row.get("error")
            }
            performed_independent_refs |= _independent_derivation_refs(requests, results)
            performed_ceilings.update(inspection_ceilings_from_results(results))
            performed_actual_classes.update(inspection_actual_classes_from_results(results))
            performed_routes.update(inspection_route_kinds_from_results(results))
            last_inspection_results = list(results)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": json.dumps(
                    {
                        "verifier_inspection_results": results,
                        "available_authoritative_source_refs": sorted(available_authoritative_refs),
                        "available_bound_input_refs": sorted(available_bound_input_refs),
                        "instruction": (
                            "Use these observations together with the original verifier_packet and "
                            + ("return a final verdict now; no further inspection is available." if not phase_state.has_model_call_capacity else "return either a final verdict or another bounded inspection request.")
                        ),
                    },
                    default=str,
                    sort_keys=True,
                ),
            })
            continue
        direct_refs: set[str] = set()
        derived_refs: set[str] = set()
        if require_v3_admissibility:
            direct_refs, derived_refs = admissible_verdict_refs(
                ledger, task_facts=_task_facts_by_id(packet),
            )
        direct_verdict_refs = (
            direct_refs
            if require_v3_admissibility
            else (performed_refs - executed_overlay_refs)
        )
        direct_needs_repair = _needs_repair_is_fully_directly_grounded(
            result, direct_verdict_refs,
        )
        if executed_overlay_refs and not direct_needs_repair:
            validity = result.method_validity
            invalid_validity = (
                validity is None
                or validity.execution_ref not in (
                    derived_refs if require_v3_admissibility else executed_overlay_refs
                )
                or not set(validity.authoritative_source_refs) <= available_authoritative_refs
            )
            if invalid_validity and phase_state.has_model_call_capacity and not method_validity_retry_used:
                method_validity_retry_used = True
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": json.dumps({
                    "instruction": (
                        "Before a final verdict after overlay execution, include method_validity with "
                        + ", ".join(METHOD_VALIDITY_SHAPE)
                        + ". "
                        "execution_ref must name a verdict-eligible derived execution (exploratory command "
                        "results cannot support a verdict); source refs must be "
                        "task:prompt or earlier successful inspection IDs. State only your audit record, "
                        "not hidden reasoning. method_alignment must explain why the executed rule measures "
                        "the semantic determinant instead of a descriptive proxy. If the executed rule only "
                        "extracts a declared name or label and performs string equality with a generated or "
                        "transformed output, treat it as metadata-only proxy evidence; a source-declared label, "
                        "comment, header, filename, or summary is not behavioral evidence. Without an independent "
                        "executable/effect check, return "
                        "uncertain_missing_evidence."
                    ),
                    "available_authoritative_source_refs": sorted(available_authoritative_refs),
                    "verdict_eligible_execution_refs": sorted(
                        derived_refs if require_v3_admissibility else executed_overlay_refs
                    ),
                }, default=str, sort_keys=True)})
                continue
            if invalid_validity:
                # method_validity is Verifier-owned protocol state.  After the
                # one bounded Verifier-side correction, keep the failure in the
                # Verifier lane rather than manufacturing a Solver-facing
                # missing-evidence request for a record only the Verifier emits.
                raise _model_output_error(
                    "verifier method_validity correction exhausted: " + invalid_validity
                )
            # Audit only the execution explicitly cited by method_validity.
            # Earlier exploratory or rejected commands must not poison a later
            # corrected method, while an uncited command cannot support the verdict.
            method_problem = _method_authority_problem(
                ledger,
                {validity.execution_ref},
                method_validity=validity,
                reject_circular_extraction_comparison=_packet_declares_circular_proxy_risk(packet),
                reject_same_method_overlap=_packet_declares_same_method_risk(packet),
                observed_source_texts=tuple(observed_source_texts),
            )
            if method_problem and phase_state.has_model_call_capacity and not method_revision_retry_used:
                method_revision_retry_used = True
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": json.dumps({
                    "instruction": (
                        "The cited derived method cannot support this semantic verdict because it is not "
                        "independent or internally self-consistent. Do not merely restate method_validity. "
                        "Request one new non-equivalent derived execution that measures the authoritative raw "
                        "structure without directly rerunning an inspected implementation as its proof method, "
                        "and ensure each input contributes exactly once to every intended accumulator bucket. "
                        "If no such method is available, return uncertain_missing_evidence."
                    ),
                    "problem": method_problem,
                }, default=str, sort_keys=True)})
                continue
            if method_problem:
                return json.dumps({
                    "verdict": "uncertain_missing_evidence",
                    "confidence": "high",
                    "summary": "Final verifier verdict cannot be accepted from a non-independent or internally inconsistent method.",
                    "missing_evidence_requests": [
                        "Perform a new independent, internally self-consistent derivation from authoritative raw observations.",
                    ],
                })
        # Preserve the existing automatic first observation for an uninspected
        # completion.  Admissibility is a final-evidence gate, not a reason to
        # skip that recovery path.
        if require_v3_admissibility and (
            result.verdict == "needs_repair" or (result.verdict == "completed" and inspected)
        ):
            problem = _verdict_admissibility_problem(result, direct_refs, derived_refs)
            if problem and phase_state.has_model_call_capacity and not admissibility_retry_used:
                admissibility_retry_used = True
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": json.dumps({
                    "instruction": (
                        "A final completed verdict and every blocking needs_repair finding must cite current "
                        "admissible evidence. Direct claims may cite a kernel-mediated observation. Derived "
                        "claims must cite a prior-grounded overlay execution with evidence_mode='derived', basis "
                        "refs, and bound input refs. Command stdout is exploratory, not source observation. "
                        f"Current problem: {problem}. If the verdict relies only on direct admissible "
                        "observations and no verdict-eligible derived execution exists, set method_validity "
                        "to null rather than inventing execution_ref. Return a corrected final verdict or "
                        "uncertain_missing_evidence."
                    ),
                    "direct_admissible_refs": sorted(direct_refs),
                    "verdict_eligible_execution_refs": sorted(
                        derived_refs if require_v3_admissibility else executed_overlay_refs
                    ),
                }, default=str, sort_keys=True)})
                continue
            if problem:
                return _refuse_admissibility(problem)
        if result.verdict == "blocked_by_tooling" and not inspected and phase_state.has_model_call_capacity:
            auto_requests = _default_completion_inspection_requests(packet)
            if auto_requests:
                results = execute_budgeted(auto_requests)
                inspected = True
                performed_refs |= _refs_from_inspections(auto_requests, results)
                available_authoritative_refs |= _basis_refs_from_inspections(auto_requests, results)
                available_bound_input_refs |= _bound_input_refs_from_inspections(auto_requests, results)
                performed_independent_refs |= _independent_derivation_refs(auto_requests, results)
                performed_ceilings.update(inspection_ceilings_from_results(results))
                performed_actual_classes.update(inspection_actual_classes_from_results(results))
                performed_routes.update(inspection_route_kinds_from_results(results))
                last_inspection_results = list(results)
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        {
                            "verifier_inspection_results": results,
                            "available_authoritative_source_refs": sorted(available_authoritative_refs),
                            "available_bound_input_refs": sorted(available_bound_input_refs),
                            "instruction": (
                                "blocked_by_tooling is only valid after at least one read-only "
                                "inspection attempt fails. The runtime supplied available inspection "
                                "results. Use them with the original verifier_packet and return a "
                                "final verdict; request another bounded inspection only if these "
                                "observations are genuinely insufficient."
                            ),
                        },
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": json.dumps(
                    {
                        "instruction": (
                            "Do not return blocked_by_tooling before attempting inspection. "
                            "Emit kind='inspect' with read_file, read_output, rerun_check, "
                            "overlay_run_command, probe_port/probe_http/probe_process, "
                            "inspect_artifact, or perceive_artifact as appropriate."
                        ),
                    },
                    default=str,
                    sort_keys=True,
                ),
            })
            continue

        if (
            result.verdict == "uncertain_missing_evidence"
            and phase_state.has_model_call_capacity
            and not missing_evidence_realized
        ):
            # Realize once per verification round: inspect, re-judge, and
            # if the verdict is still uncertain let durable findings and
            # unchanged-state memoization take over instead of looping.
            missing_evidence_realized = True
            auto_requests = _inspections_from_missing_evidence(result, packet=packet)
            if auto_requests:
                try:
                    results = execute_budgeted(auto_requests)
                except VerifierBudgetError:
                    # The model already returned a valid fail-closed verdict.
                    # Optional evidence realization cannot turn that safe
                    # non-completion into an invalid measurement when the
                    # declared inspection phase is exhausted.
                    return raw
                inspected = True
                performed_refs |= _refs_from_inspections(auto_requests, results)
                available_authoritative_refs |= _basis_refs_from_inspections(auto_requests, results)
                available_bound_input_refs |= _bound_input_refs_from_inspections(auto_requests, results)
                performed_independent_refs |= _independent_derivation_refs(auto_requests, results)
                performed_ceilings.update(inspection_ceilings_from_results(results))
                performed_actual_classes.update(inspection_actual_classes_from_results(results))
                performed_routes.update(inspection_route_kinds_from_results(results))
                last_inspection_results = list(results)
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        {
                            "verifier_inspection_results": results,
                            "available_authoritative_source_refs": sorted(available_authoritative_refs),
                            "available_bound_input_refs": sorted(available_bound_input_refs),
                            "instruction": (
                                "The runtime executed read-only inspections for the files "
                                "your missing-evidence requests named: the solver cannot "
                                "supply packet evidence, only your own inspection can. "
                                "Judge the current state now and return a final verdict; "
                                "request further bounded inspections only if these "
                                "observations are genuinely insufficient."
                            ),
                        },
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
        # Runtime-enforced, not prompt-only: a completed verdict must be
        # backed by at least one real independent inspection when the
        # inspector is available -- a model that judges "completed"
        # straight from the packet's narrative is exactly the false-clean
        # failure mode this mechanism exists to close. Force one more
        # round requiring inspection rather than trusting the prompt alone.
        if result.verdict == "completed" and not inspected and phase_state.has_model_call_capacity:
            auto_requests = _default_completion_inspection_requests(packet)
            if auto_requests:
                results = execute_budgeted(auto_requests)
                inspected = True
                performed_refs |= _refs_from_inspections(auto_requests, results)
                available_authoritative_refs |= _basis_refs_from_inspections(auto_requests, results)
                available_bound_input_refs |= _bound_input_refs_from_inspections(auto_requests, results)
                performed_independent_refs |= _independent_derivation_refs(auto_requests, results)
                performed_ceilings.update(inspection_ceilings_from_results(results))
                performed_actual_classes.update(inspection_actual_classes_from_results(results))
                performed_routes.update(inspection_route_kinds_from_results(results))
                last_inspection_results = list(results)
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        {
                            "verifier_inspection_results": results,
                            "available_authoritative_source_refs": sorted(available_authoritative_refs),
                            "available_bound_input_refs": sorted(available_bound_input_refs),
                            "instruction": (
                            "The runtime supplied a minimal read-only current-state "
                            "inspection because completed cannot be accepted from "
                            "packet evidence alone. Use these observations together "
                            "with the original verifier_packet and return your final "
                            "verdict. Treat solver-authored validation commands and "
                            "recomputation receipts as claims to audit, not as proof; "
                            "inspect whether their method matches the task semantics "
                            "before returning completed."
                        ),
                    },
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": json.dumps(
                    {
                        "instruction": (
                            "Protocol requires at least one read-only inspection before a "
                            "completed verdict can be accepted. Submit a bounded inspection "
                            "request (kind: inspect) that independently confirms the claim "
                            "your verdict depends on, then return your verdict."
                        ),
                    },
                    default=str,
                    sort_keys=True,
                ),
            })
            continue
        if (
            result.verdict == "completed"
            and inspected
            and not _completed_inspection_is_semantically_grounded(packet, last_inspection_results)
            and phase_state.has_model_call_capacity
        ):
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": json.dumps(
                    {
                        "instruction": (
                            "Do not return completed yet. The inspections so far only prove shape or artifact presence, "
                            "not semantically grounded current-state support for the produced result. Inspect concrete "
                            "result-bearing evidence next, such as the latest command output, produced output artifact, "
                            "or an independent overlay check against the deliverable, then judge again."
                        ),
                    },
                    default=str,
                    sort_keys=True,
                ),
            })
            continue
        if result.verdict == "completed" and inspected and phase_state.has_model_call_capacity:
            record_problem = _completion_record_problem(
                result, performed_refs, packet=packet,
                inspection_ceilings=performed_ceilings,
                inspection_routes=performed_routes,
                inspection_actual_classes=performed_actual_classes,
                require_risk_coverage=require_independent_derivation,
                require_requirement_status=require_structured_completion_status,
            )
            if record_problem and not record_retry_used:
                # Content-blind protocol enforcement, mirroring the
                # inspection-required gate: the record must exist and its
                # inspection_refs must resolve to inspections that actually
                # happened this round. Whether the evidence is GOOD stays
                # the model's judgment.
                record_retry_used = True
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        _completion_record_retry_instruction(record_problem),
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
            if (
                not record_problem
                and require_independent_derivation
                and not independence_retry_used
            ):
                # Phase 1.5: the record is structurally valid, but this
                # task flags its decisive claim(s) as machine-re-derivable
                # -- require at least one cited inspection to be an
                # independent-derivation kind, not only a read of a
                # solver-produced artifact. Same one-retry-then-refuse
                # shape as the structural gate above, its own budget.
                independence_problem = _completion_independence_problem(
                    result, performed_independent_refs,
                )
                if independence_problem:
                    independence_retry_used = True
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": json.dumps(
                            _independent_derivation_retry_instruction(independence_problem),
                            default=str,
                            sort_keys=True,
                        ),
                    })
                    continue
        if result.verdict == "uncertain_missing_evidence" and phase_state.has_model_call_capacity:
            try:
                missing_requests = _structured_missing_evidence_requests(raw)
            except Exception as exc:
                hooks.last_parse_errors.append(str(exc))
                missing_requests = ()
            if missing_requests:
                try:
                    results = execute_budgeted(missing_requests)
                except VerifierBudgetError:
                    # Preserve the valid uncertain verdict when no further
                    # optional inspection fits inside the phase budget.
                    return raw
                inspected = True
                performed_refs |= _refs_from_inspections(missing_requests, results)
                available_authoritative_refs |= _basis_refs_from_inspections(missing_requests, results)
                available_bound_input_refs |= _bound_input_refs_from_inspections(missing_requests, results)
                performed_independent_refs |= _independent_derivation_refs(missing_requests, results)
                performed_ceilings.update(inspection_ceilings_from_results(results))
                performed_actual_classes.update(inspection_actual_classes_from_results(results))
                performed_routes.update(inspection_route_kinds_from_results(results))
                last_inspection_results = list(results)
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        {
                            "verifier_inspection_results": results,
                            "available_authoritative_source_refs": sorted(available_authoritative_refs),
                            "available_bound_input_refs": sorted(available_bound_input_refs),
                            "instruction": (
                                "The runtime executed the structured read-only evidence "
                                "requests from your uncertain_missing_evidence verdict. "
                                "Use these observations with the original verifier_packet "
                                "and return a final verdict or another bounded inspection request."
                            ),
                        },
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
        if result.verdict == "completed" and not inspected:
            # Out of rounds and still uninspected: do not accept the
            # completion. Return an explicit non-completion verdict so the
            # solver sees a durable evidence gap instead of an opaque
            # verifier protocol error. This is protocol enforcement, not a
            # harness-side judgment that the task is wrong.
            return json.dumps({
                "verdict": "uncertain_missing_evidence",
                "confidence": "high",
                "summary": (
                    "Completion cannot be accepted because the verifier "
                    "did not perform a read-only current-state inspection."
                ),
                "missing_evidence_requests": [
                    "Provide independent current-state evidence, such as a relevant file read, recent receipt, or rerun check, before accepting completed.",
                ],
                "findings": [
                    {
                        "finding_id": "vf-uninspected-completion",
                        "verdict": "uncertain_missing_evidence",
                        "priority": "blocking",
                        "summary": "The verifier attempted to mark the task completed without read-only inspection.",
                        "evidence": [
                            "A completed verifier verdict requires read-only inspection when inspector tools are available.",
                        ],
                        "repair_instruction": (
                            "Surface concrete current-state evidence and resubmit only after the evidence gap is closed."
                        ),
                        "applies_to": ["completion_evidence"],
                    },
                ],
            })
        if result.verdict == "completed":
            record_problem = _completion_record_problem(
                result, performed_refs, packet=packet,
                inspection_ceilings=performed_ceilings,
                inspection_routes=performed_routes,
                inspection_actual_classes=performed_actual_classes,
                require_risk_coverage=require_independent_derivation,
                require_requirement_status=require_structured_completion_status,
            )
            if record_problem:
                # Out of retries and the record is still structurally
                # invalid: refuse the completion as a protocol event.
                # This is not a harness judgment that the task is wrong.
                return _refuse_completion_record(record_problem)
            if require_independent_derivation:
                independence_problem = _completion_independence_problem(
                    result, performed_independent_refs,
                )
                if independence_problem:
                    # Out of retries and no cited inspection resolves to
                    # an independent-derivation kind: refuse. This is the
                    # Phase 1.5 closure for the false-clean failure mode
                    # -- a model that only ever read solver-produced
                    # artifacts cannot self-certify a machine-re-derivable
                    # claim. Not a harness judgment that the task is wrong.
                    return _refuse_completion_independence(independence_problem)
        return raw
    raise _model_output_error("verifier exceeded bounded inspection rounds without returning a verdict")


def _invalid_shadow_proof_bindings(requests: Any, compiled: Any) -> tuple[str, ...]:
    """Reject unknown/duplicate shadow-v2 proof IDs before execution."""
    known = {
        str(requirement.proof_id).strip()
        for requirement in getattr(compiled, "proof_requirements", ())
        if str(requirement.proof_id).strip()
    }
    if not known:
        return ()
    errors: list[str] = []
    for request in requests:
        proof_ids = tuple(str(item).strip() for item in request.proof_ids if str(item).strip())
        if len(set(proof_ids)) != len(proof_ids):
            errors.append(f"{request.request_id}: duplicate proof_ids")
        unknown = sorted(set(proof_ids) - known)
        if unknown:
            errors.append(f"{request.request_id}: unknown proof_ids={','.join(unknown)}")
    return tuple(errors)


def _task_facts_by_id(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = packet.get("verification_task_facts", ())
    if not isinstance(raw, (list, tuple)):
        return {}
    facts: dict[str, Mapping[str, Any]] = {}
    for item in raw:
        if not isinstance(item, Mapping) or not bool(item.get("grounds_method", False)):
            continue
        fact_id = str(item.get("id", "")).strip()
        if (
            fact_id.startswith("task-fact:")
            and str(item.get("excerpt", "")).strip()
            and str(item.get("excerpt_hash", "")).strip()
        ):
            facts[fact_id] = item
    return facts


def _needs_repair_is_fully_directly_grounded(
    result: Any,
    direct_refs: set[str],
) -> bool:
    """Whether every repair finding cites a current direct observation.

    An exploratory overlay may have run earlier in the round, but it does not
    become mandatory evidence for a blocking verdict that the model grounds in
    direct current-state observations. Completed verdicts and repair findings
    that rely on derived evidence retain the strict method-validity gates.
    """
    if str(getattr(result, "verdict", "")) != "needs_repair":
        return False
    findings = tuple(getattr(result, "findings", ()) or ())
    repair_findings = tuple(
        finding
        for finding in findings
        if str(getattr(finding, "verdict", "")) == "needs_repair"
    )
    if not repair_findings:
        return False
    return all(
        bool(set(getattr(finding, "supporting_inspection_ids", ()) or ()))
        and set(getattr(finding, "supporting_inspection_ids", ()) or ()) <= direct_refs
        for finding in repair_findings
    )


def _verdict_admissibility_problem(
    result: Any,
    direct_refs: set[str],
    derived_refs: set[str],
) -> str:
    admissible_refs = direct_refs | derived_refs
    if result.verdict == "completed":
        cited = {
            ref
            for entry in tuple(getattr(result, "completion_evidence", ()) or ())
            for ref in tuple(getattr(entry, "inspection_refs", ()) or ())
        }
        if not cited or not cited & admissible_refs:
            return "completed cites no current direct or verdict-eligible evidence"
    validity = getattr(result, "method_validity", None)
    execution_ref = str(getattr(validity, "execution_ref", "") or "") if validity is not None else ""
    if execution_ref and execution_ref not in derived_refs:
        return "method_validity.execution_ref is not a current verdict-eligible derived execution"
    if result.verdict == "needs_repair":
        for finding in tuple(getattr(result, "findings", ()) or ()):
            if str(getattr(finding, "priority", "")) != "blocking":
                continue
            refs = set(getattr(finding, "supporting_inspection_ids", ()) or ())
            if not refs:
                return f"blocking finding {getattr(finding, 'finding_id', 'unknown')} cites no current admissible evidence"
            non_admissible = sorted(refs - admissible_refs)
            if non_admissible:
                return (
                    f"blocking finding {getattr(finding, 'finding_id', 'unknown')} cites non-admissible evidence: "
                    + ", ".join(non_admissible)
                )
    return ""


_DESCRIPTIVE_AUTHORITY_RE = re.compile(
    # Match ordinary inflections as well as the bare nouns.  The model's V3
    # contract is free prose: "object-region labeling" has the same
    # descriptive-authority meaning as "object label" and must not evade the
    # structural guard merely by using a different grammatical form.
    r"\b(label(?:s|ed|ing)?|annotation(?:s)?|comment(?:s|ed|ing)?|header(?:s)?)\b"
    r"|\bsummary\b(?!\.\w)",
    re.IGNORECASE,
)


def _bound_direct_observation_paths(
    ledger: ExecutionLedger,
    request: Mapping[str, Any],
) -> tuple[str, ...]:
    refs = {
        str(item).strip()
        for field in ("basis_refs", "bound_input_refs")
        for item in tuple(request.get(field, ()) or ())
        if str(item).strip()
    }
    paths: list[str] = []
    for receipt in ledger.all_receipts():
        inspection_id = str(receipt.payload.get("inspection_id", receipt.receipt_id)).strip()
        if inspection_id not in refs or str(receipt.payload.get("route_kind", "")) != "read_file":
            continue
        route = receipt.payload.get("route_parameters", {})
        path = str(route.get("path", "") if isinstance(route, Mapping) else "").strip()
        if path:
            paths.append(path)
    return tuple(dict.fromkeys(paths))


def _method_authority_problem(
    ledger: ExecutionLedger,
    derived_refs: set[str],
    *,
    method_validity: Any | None = None,
    reject_circular_extraction_comparison: bool = False,
    reject_same_method_overlap: bool = False,
    observed_source_texts: tuple[str, ...] = (),
) -> str:
    """Reject proof plans that name descriptive metadata as the determinant.

    This is deliberately task-agnostic.  It does not identify formats or
    benchmark tasks; it checks the model-authored contract itself.  A plan may
    inspect metadata, but metadata alone cannot be the authoritative structure
    for a semantic verdict unless it also declares an independent effect or
    counterfactual check.
    """
    for receipt in ledger.all_receipts():
        inspection_id = str(receipt.payload.get("inspection_id", receipt.receipt_id)).strip()
        if inspection_id not in derived_refs:
            continue
        request = receipt.payload.get("route_parameters", {})
        if not isinstance(request, Mapping):
            continue
        # PERSISTENT F89 moves semantic method judgment to the final post-execution
        # MethodValidityRecord. Generic/direct unit callers that do not supply
        # one retain the historical request-field fallback, but production
        # verdict admission above always supplies the cited final record. This
        # ensures transport-only PERSISTENT placeholders can neither grant nor block
        # semantic authority.
        if method_validity is not None:
            descriptor = str(getattr(method_validity, "observed_structure", "") or "")
            executed_rule = str(getattr(method_validity, "executed_rule", "") or "")
            method_alignment = str(getattr(method_validity, "method_alignment", "") or "")
        else:
            descriptor = str(request.get("authoritative_structure", ""))
            executed_rule = str(request.get("method_summary", ""))
            method_alignment = ""
        command = str(request.get("command", ""))
        circular_text = " ".join((command, executed_rule, method_alignment)).lower()
        integrity_problem = overlapping_accumulator_problem(command)
        if integrity_problem:
            return f"derived execution {inspection_id} is internally inconsistent: {integrity_problem}"
        if reject_same_method_overlap:
            executed_paths = executed_observed_implementations(
                command,
                _bound_direct_observation_paths(ledger, request),
            )
            if executed_paths:
                return (
                    f"derived execution {inspection_id} directly executes an inspected implementation "
                    f"under an explicit same-method false-positive risk: {', '.join(executed_paths)}"
                )
        if reject_same_method_overlap and observed_source_texts:
            overlaps, details = same_method_overlap(command, observed_source_texts)
            if overlaps:
                return (
                    f"derived execution {inspection_id} substantially reuses an inspected implementation "
                    "under an explicit same-method false-positive risk "
                    f"(shared_shingles={details['shared_shingles']}, containment={details['containment']})"
                )
        if reject_circular_extraction_comparison and (
            re.search(r"\b(re\.search|regex|extract|group\()", circular_text)
            and re.search(r"(==|match\s*=|compare)", circular_text)
            and _CIRCULAR_EXTRACTION_TARGET_RE.search(circular_text)
        ):
            return (
                f"derived execution {inspection_id} circularly extracts a declared source value and "
                "compares it with an output under an explicit metadata/heuristic risk"
            )
        if not _DESCRIPTIVE_AUTHORITY_RE.search(descriptor):
            continue
        independent = (
            " ".join((executed_rule, method_alignment))
            if method_validity is not None
            else " ".join(
                str(request.get(field, ""))
                for field in ("behavioral_basis", "effect_check", "counterfactual_check")
            )
        )
        if not re.search(r"\b(effect|behavior|execute|counterfactual|mutat|perturb|rerun)\b", independent, re.IGNORECASE):
            return (
                f"derived execution {inspection_id} names descriptive metadata as its authoritative "
                "structure without an independent executable or counterfactual effect check"
            )
    return ""


def _refuse_admissibility(problem: str) -> str:
    return json.dumps({
        "verdict": "uncertain_missing_evidence",
        "confidence": "high",
        "summary": f"Final verifier verdict cannot be accepted: {problem}.",
        "missing_evidence_requests": [
            "Provide current admissible inspection evidence supporting each blocking finding or completion claim before resubmitting the verdict.",
        ],
        "findings": [{
            "finding_id": "vf-evidence-admissibility",
            "verdict": "uncertain_missing_evidence",
            "priority": "blocking",
            "summary": "Final verdict lacked current admissible evidence.",
            "evidence": [problem],
            "repair_instruction": "Obtain a current direct observation or a prior-grounded derived execution before returning a blocking or completed verdict.",
            "applies_to": ["verification_evidence"],
        }],
    })
