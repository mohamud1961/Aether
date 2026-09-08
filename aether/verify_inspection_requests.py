"""Verifier inspection-request construction and ref bookkeeping.

Extracted from model_hooks.py for the 500-LOC cap. Production PCR accepts
explicitly typed Verifier inspection requests and classifies which inspections
actually happened (and which of those are independent-derivation kinds) so
the completion-evidence protocol in verify_completion_protocol.py can gate on
them without re-deriving that bookkeeping itself.

The completion_evidence refusal builders (``_refuse_completion_record`` /
``_refuse_completion_independence``) were further extracted to
verify_completion_gates.py, alongside the record/independence problem
detectors they pair with, for the same 500-LOC cap.
"""
from __future__ import annotations

from typing import Any, Mapping

from .model_prompts import VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE
from .pcr_verifier_prompt import pcr_verifier_identity_prompt
from .verifier import METHOD_VALIDITY_SHAPE
from .verifier_budget import DIRECT_OBSERVATION_KINDS
from .verifier_inspector import (
    V3_DERIVED_INSPECTION_EXAMPLE,
    VerifierInspectionRequest,
    parse_verifier_inspection_requests,
)


def _model_output_error(message: str) -> Exception:
    # Deferred import: model_hooks.py imports this module at module load
    # time, so importing ModelOutputError back at module level would cycle.
    # Mirrors the same pattern already used in model_parse.py.
    from .model_hooks import ModelOutputError

    return ModelOutputError(message)


def _verifier_identity_prompt_for(compiled: Any) -> str:
    prompt = str(getattr(compiled, "verifier_identity_prompt", "") or "").strip()
    if not prompt:
        raise _model_output_error("verifier identity prompt is required")
    return pcr_verifier_identity_prompt(prompt)

def _typed_inspections_from_missing_evidence(result: Any) -> tuple[VerifierInspectionRequest, ...]:
    """Return only explicitly typed direct inspections from a Verifier verdict.

    PCR production uses this instead of inferring executable routes from prose.  The
    provider canonicalizer has already mapped PCR's compact kind+locator shape
    onto the runtime request fields.  This helper performs no semantic routing.
    """
    raw = getattr(result, "missing_inspection_requests", ()) or ()
    if not raw:
        return ()
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [dict(item) for item in raw],
    })
    invalid = tuple(request.kind for request in requests if request.kind not in DIRECT_OBSERVATION_KINDS)
    if invalid:
        raise _model_output_error(
            "typed missing-evidence requests must be direct observations: " + ",".join(invalid)
        )
    return requests

def _inspection_result_errored(row: Mapping[str, Any]) -> bool:
    """True when an inspection RESULT row reports failure, never content.

    Every failure path in verifier_inspector.py (``_error_result`` and each
    probe's own failure dict) funnels through a non-empty top-level
    ``error`` field. A negative-but-successful observation -- a closed
    port, an unreachable URL, a non-existent artifact, a non-zero rerun
    exit code -- is NOT an error by this check: it is a real, content-
    bearing inspection outcome, and judging whether that content supports a
    claim stays the model's job. This is a structural/provenance check
    only.
    """
    return bool(str(row.get("error", "")).strip())


def _paired_non_errored_inspections(
    requests: Any, results: Any,
) -> list[tuple[Any, Mapping[str, Any]]]:
    """Pair each inspection request with its result row, keeping non-errored pairs.

    Pairing prefers a same-request_id result row (the real inspector always
    echoes request_id back); positional pairing is a defensive fallback for
    a results list that omits it. This is the shared basis for every
    content-blind provenance check on completion_evidence: a ref may only
    resolve to an inspection that both HAPPENED and DID NOT ERROR this
    round -- citing a failed read/probe must never satisfy a gate.
    """
    results_list = [row for row in (results or ()) if isinstance(row, Mapping)]
    by_request_id: dict[str, Mapping[str, Any]] = {}
    for row in results_list:
        rid = str(row.get("request_id", "")).strip()
        if rid and rid not in by_request_id:
            by_request_id[rid] = row
    pairs: list[tuple[Any, Mapping[str, Any]]] = []
    for idx, request in enumerate(requests or ()):
        request_id = str(getattr(request, "request_id", "")).strip()
        row = by_request_id.get(request_id)
        if row is None and idx < len(results_list):
            row = results_list[idx]
        if row is None or _inspection_result_errored(row):
            continue
        pairs.append((request, row))
    return pairs


def _refs_from_inspections(requests: Any, results: Any) -> set[str]:
    """Canonical proof-authority IDs from successful registered inspections."""
    refs: set[str] = set()
    for _request, row in _paired_non_errored_inspections(requests, results):
        inspection_id = str(row.get("inspection_id", "")).strip()
        if inspection_id and bool(row.get("eligible_for_proof", False)):
            refs.add(inspection_id)
    return refs


def _basis_refs_from_inspections(requests: Any, results: Any) -> set[str]:
    """Canonical registered IDs allowed as authoritative derived-check inputs.

    Most routes are both proof- and basis-eligible. A generation-bound cited
    historical snapshot is the deliberate exception: exact evidence of past
    bytes may ground a fresh comparison but cannot directly prove current state.
    """
    refs: set[str] = set()
    for _request, row in _paired_non_errored_inspections(requests, results):
        inspection_id = str(row.get("inspection_id", "")).strip()
        if inspection_id and bool(row.get("eligible_for_basis", row.get("eligible_for_proof", False))):
            refs.add(inspection_id)
    return refs


def _bound_input_refs_from_inspections(requests: Any, results: Any) -> set[str]:
    """Canonical IDs that may bind a later derived execution's exact inputs.

    Proof-eligible observations remain valid inputs. A successful prior
    ``overlay_write_fixture`` is also accepted strictly as a causal input when
    it is registered in the verifier overlay with a canonical target. Fixture
    content remains exploratory and can never become verdict evidence through
    this helper.
    """
    refs = _basis_refs_from_inspections(requests, results)
    for request, row in _paired_non_errored_inspections(requests, results):
        if str(getattr(request, "kind", "")).strip() != "overlay_write_fixture":
            continue
        inspection_id = str(row.get("inspection_id", "")).strip()
        if not inspection_id:
            continue
        if (
            str(row.get("admissibility", "")).strip() == "exploratory"
            and str(row.get("executed_in", "")).strip() == "verifier_overlay"
            and bool(row.get("canonical_targets"))
            and bool(row.get("success", False))
        ):
            refs.add(inspection_id)
    return refs


# Inspection kinds that constitute independent derivation: the verifier
# itself executes/observes something (overlay execution, a live probe, or
# its own perception) rather than reading a solver-produced artifact's
# content and trusting it. read_file, read_output, inspect_recent_receipts,
# and inspect_artifact_history are deliberately excluded -- they only ever
# surface what the solver already produced, which is exactly the self-
# confirmation the false-clean failure mode exploits (see
# FABLE5_BATCH_AUDIT_20260709T101515Z.md secs 4/6). rerun_check groups with
# overlay_run_command: both execute independently in the disposable verifier
# overlay via VerifierOverlay.run_command, differing only in whether the
# command comes from an runtime-declared check or an ad hoc request.
_INDEPENDENT_DERIVATION_KINDS = frozenset({
    "overlay_run_command",
    "compare_initial_path",
    "rerun_check",
    "probe_port",
    "probe_http",
    "probe_process",
    "probe_job",
    "perceive_artifact",
})


def _independent_derivation_refs(requests: Any, results: Any) -> set[str]:
    """Canonical registered IDs for independent-derivation inspections."""
    refs: set[str] = set()
    for request, row in _paired_non_errored_inspections(requests, results):
        if str(getattr(request, "kind", "")).strip() not in _INDEPENDENT_DERIVATION_KINDS:
            continue
        inspection_id = str(row.get("inspection_id", "")).strip()
        if inspection_id and bool(row.get("eligible_for_proof", False)):
            refs.add(inspection_id)
    return refs
