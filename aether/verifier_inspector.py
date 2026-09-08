"""Read-only verifier inspection requests and execution helpers."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from .memory_events import artifact_history
from .runtime_ir import CompiledRuntime, EnvMap, normalize_relpath
from .verifier_probes import (
    inspect_artifact_probe,
    probe_http,
    probe_port,
    probe_process,
    probe_job,
)


# Phase-aware policy separately restricts direct and derived batches.  The
# parser's ceiling is only an early anti-amplification guard.
MAX_VERIFIER_INSPECTION_REQUESTS = 12

# Recent-receipt inspection is a model-facing metadata view, not a second copy
# of the immutable ledger. Keep enough headroom below the verifier's default
# 8 KiB per-result ceiling for registration metadata added later.
RECENT_RECEIPT_SUMMARY_EXCERPT_CHARS = 256
RECENT_RECEIPTS_PACKET_TARGET_BYTES = 7_000
ACTION_RECEIPTS_PACKET_TARGET_BYTES = 7_000
# Exact receipt kinds emitted by the current kernel action dispatcher.  Keep
# this list aligned with receipt authority, not legacy tool names: the model
# may describe a task method, but only immutable executed-action receipts can
# attest what actually happened.
ACTION_RECEIPT_KINDS = frozenset({
    "read_file", "read_file_page", "read_output", "grep_output",
    "write_file", "run_command", "bootstrap", "process_launch",
    "service_probe", "job_probe", "process_stop",
    "terminal_start", "terminal_send", "terminal_read", "terminal_wait",
    "terminal_interrupt", "terminal_close", "artifact_inspection",
})
ACTION_RECEIPT_PAYLOAD_FIELDS = (
    "path", "offset", "span", "bytes", "content_hash",
    "before_content_hash", "after_content_hash", "before_bytes",
    "command", "command_sha256", "timeout_s", "exit_code", "timed_out",
    "modified_paths", "artifact_paths", "removed_paths", "manager",
    "service_name", "process_id", "job_id", "process_generation", "pid",
    "launch_tool", "launch_mode", "detached", "contract_guarantees",
    "start_time_ticks", "target", "live", "job_status", "completed", "job_succeeded", "job_exit_code", "exit_code", "status_log", "process_generation_verified",
    "endpoint_owner_pids", "mode", "handle", "source_receipt_id", "stream",
    "session_id", "session_name", "name", "cursor", "total_bytes", "bytes_read",
    "bytes_sent", "more_available", "signal", "process_group_id", "session_leader_id",
)


# This is the one model-facing V3 derived-execution shape.  Prompt rendering,
# correction guidance, and parity tests consume this data, while the parser
# below remains the authority that rejects malformed requests.
V3_DERIVED_INSPECTION_EXAMPLE: dict[str, Any] = {
    "kind": "inspect",
    "requests": [{
        "request_id": "derived-check",
        "kind": "overlay_run_command",
        "verification_plan": {
            "claim": "the independently recomputed result matches the claimed artifact",
            "evidence_mode": "derived",
            "clause_ids": ["declared-proof-clause"],
            "basis": [{
                "ref": "inspection:earlier-source",
                "supported_fact": "the earlier direct observation exposes the required source structure",
            }],
            "bound_input_refs": ["inspection:earlier-source"],
            "authoritative_structure": "the authoritative field or grammar that determines the claimed value",
            "method_summary": "derive the claim from the earlier observed source structure",
            "proxy_risk": "a broader proxy could agree while the authoritative structure differs",
        },
        "execution": {
            "kind": "overlay_run_command",
            "command": "python3 verify.py",
        },
    }],
}


class VerifierInspectionProtocolError(ValueError):
    """A machine-readable inspection-schema rejection.

    The model-facing correction path uses the complete defect set rather than
    guessing which single missing field to mention.  This keeps V3's parser,
    rendered contract, and retry message aligned without making semantic
    judgments about a proposed command.
    """

    def __init__(self, *, missing: tuple[str, ...] = (), invalid: tuple[str, ...] = ()) -> None:
        self.missing = missing
        self.invalid = invalid
        parts: list[str] = []
        if missing:
            parts.append("missing: " + ", ".join(missing))
        if invalid:
            parts.append("invalid: " + ", ".join(invalid))
        super().__init__("overlay_run_command V3 verification_plan defects; " + "; ".join(parts))


@dataclass(frozen=True)
class VerifierInspectionRequest:
    request_id: str
    kind: str
    path: str = ""
    handle: str = ""
    check_id: str = ""
    receipt_kind: str = ""
    limit: int = 5
    command: str = ""
    content: str = ""
    target: str = ""
    offset: int = 0
    span: int = 4000
    claim: str = ""
    authoritative_source_refs: tuple[str, ...] = ()
    authoritative_structure: str = ""
    method_summary: str = ""
    proxy_risk: str = ""
    evidence_mode: str = ""
    basis_refs: tuple[str, ...] = ()
    bound_input_refs: tuple[str, ...] = ()
    clause_ids: tuple[str, ...] = ()
    proof_ids: tuple[str, ...] = ()


def parse_verifier_inspection_requests(
    value: Any, *, require_derived_contract: bool = False,
) -> tuple[VerifierInspectionRequest, ...]:
    data = _load_mapping(value)
    if str(data.get("kind", "")).strip() != "inspect":
        raise ValueError("verifier output is not an inspection request")
    raw = data.get("requests", ())
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not raw:
        raise ValueError("inspection request requires a non-empty requests list")
    if len(raw) > MAX_VERIFIER_INSPECTION_REQUESTS:
        raise ValueError(
            f"inspection request exceeds maximum of {MAX_VERIFIER_INSPECTION_REQUESTS} entries"
        )
    parsed: list[VerifierInspectionRequest] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "")).strip()
        if not kind:
            execution = item.get("execution")
            if isinstance(execution, Mapping) and str(execution.get("kind", "")).strip() == "overlay_run_command":
                raise ValueError("overlay_run_command requires top-level kind='overlay_run_command'")
            continue
        if kind == "overlay_run_command":
            plan = item.get("verification_plan")
            execution = item.get("execution")
            if not isinstance(plan, Mapping):
                raise ValueError("overlay_run_command requires verification_plan object")
            if not isinstance(execution, Mapping):
                raise ValueError("overlay_run_command requires execution object")
            refs_raw = plan.get("authoritative_source_refs", ())
            if isinstance(refs_raw, str):
                refs_raw = [refs_raw]
            refs = tuple(str(ref or "").strip() for ref in refs_raw or () if str(ref or "").strip())
            grounding = {
                "claim": str(plan.get("claim") or "").strip(),
                "method_summary": str(plan.get("method_summary") or "").strip(),
                "proxy_risk": str(plan.get("proxy_risk") or "").strip(),
            }
            missing = [field for field, value in grounding.items() if not value]
            authoritative_structure = str(plan.get("authoritative_structure") or "").strip()
            if require_derived_contract and not authoritative_structure:
                missing.append("verification_plan.authoritative_structure")
            if not require_derived_contract and not refs:
                missing.append("authoritative_source_refs")
            if missing and not require_derived_contract:
                raise ValueError(
                    "overlay_run_command requires verification_plan fields: "
                    + ", ".join(missing)
                )
            if str(execution.get("kind") or "").strip() != "overlay_run_command":
                raise ValueError("overlay_run_command execution.kind must be overlay_run_command")
            command = str(execution.get("command") or "").strip()
            if not command:
                raise ValueError("overlay_run_command requires execution.command")
            evidence_mode = str(plan.get("evidence_mode") or "").strip()
            if evidence_mode and evidence_mode not in {"direct", "derived"}:
                raise ValueError("verification_plan.evidence_mode must be direct or derived")
            basis_raw = plan.get("basis", ())
            if isinstance(basis_raw, Mapping):
                basis_raw = [basis_raw]
            if not isinstance(basis_raw, (list, tuple)):
                raise ValueError("verification_plan.basis must be a list when provided")
            basis_refs = tuple(
                str(item.get("ref", "")).strip()
                for item in basis_raw
                if isinstance(item, Mapping) and str(item.get("ref", "")).strip()
            )
            bound_raw = plan.get("bound_input_refs", ())
            if isinstance(bound_raw, str):
                bound_raw = [bound_raw]
            if not isinstance(bound_raw, (list, tuple)):
                raise ValueError("verification_plan.bound_input_refs must be a list when provided")
            bound_input_refs = tuple(str(item).strip() for item in bound_raw if str(item).strip())
            clause_raw = plan.get("clause_ids", ())
            if isinstance(clause_raw, str):
                clause_raw = [clause_raw]
            if not isinstance(clause_raw, (list, tuple)):
                raise ValueError("verification_plan.clause_ids must be a list when provided")
            clause_ids = tuple(str(item).strip() for item in clause_raw if str(item).strip())
            proof_raw = plan.get("proof_ids", item.get("proof_ids", ()))
            if isinstance(proof_raw, str):
                proof_raw = [proof_raw]
            if not isinstance(proof_raw, (list, tuple)):
                raise ValueError("verification_plan.proof_ids must be a list when provided")
            proof_ids = tuple(str(item).strip() for item in proof_raw if str(item).strip())
            if require_derived_contract:
                v3_missing = list(missing)
                v3_invalid: list[str] = []
                legacy_command = str(item.get("command") or "").strip()
                if legacy_command:
                    v3_invalid.append(
                        "top-level command is legacy-only in V3; use execution.command only"
                    )
                if evidence_mode != "derived":
                    if evidence_mode:
                        v3_invalid.append("verification_plan.evidence_mode must equal 'derived'")
                    else:
                        v3_missing.append("verification_plan.evidence_mode")
                if not basis_refs:
                    v3_missing.append("verification_plan.basis")
                if not bound_input_refs:
                    v3_missing.append("verification_plan.bound_input_refs")
                if refs:
                    v3_invalid.append(
                        "verification_plan.authoritative_source_refs is legacy-only in V3"
                    )
                if v3_missing or v3_invalid:
                    raise VerifierInspectionProtocolError(
                        missing=tuple(v3_missing), invalid=tuple(v3_invalid),
                    )
            elif evidence_mode == "derived":
                if not basis_refs:
                    raise ValueError("derived verification_plan requires basis refs")
                if not bound_input_refs:
                    raise ValueError("derived verification_plan requires bound_input_refs")
        else:
            refs = ()
            grounding = {"claim": "", "method_summary": "", "proxy_risk": ""}
            authoritative_structure = ""
            command = str(item.get("command", ""))
            evidence_mode = ""
            basis_refs = ()
            bound_input_refs = ()
            clause_raw = item.get("clause_ids", ())
            if isinstance(clause_raw, str):
                clause_raw = [clause_raw]
            if not isinstance(clause_raw, (list, tuple)):
                raise ValueError("inspection clause_ids must be a list when provided")
            clause_ids = tuple(str(item).strip() for item in clause_raw if str(item).strip())
            # The provider's strict shared inspection schema exposes nullable
            # clause_ids on every direct request. Retain any supplied values as
            # descriptive tags so a schema-valid direct observation is never
            # rejected by a stricter hidden parser rule. Kernel authority is
            # unchanged: invalid_clause_bindings enforces these IDs only for
            # inspect_action_receipts, while derived commands remain bound via
            # verification_plan.clause_ids.
            proof_raw = item.get("proof_ids", ())
            if isinstance(proof_raw, str):
                proof_raw = [proof_raw]
            proof_ids = tuple(str(item).strip() for item in proof_raw if str(item).strip()) if isinstance(proof_raw, (list, tuple)) else ()
        parsed.append(
            VerifierInspectionRequest(
                request_id=str(item.get("request_id", f"inspect-{idx}")).strip() or f"inspect-{idx}",
                kind=kind,
                path=str(item.get("path", "")).strip(),
                handle=str(item.get("handle", "")).strip(),
                check_id=str(item.get("check_id", "")).strip(),
                receipt_kind=str(item.get("receipt_kind", "")).strip(),
                limit=max(1, int(item.get("limit", 5) or 5)),
                command=command,
                content=str(item.get("content", "")),
                target=str(item.get("target", "")).strip(),
                offset=max(0, int(item.get("offset", 0) or 0)),
                span=max(1, int(item.get("span", item.get("limit", 4000)) or 4000)),
                authoritative_source_refs=refs,
                authoritative_structure=authoritative_structure,
                evidence_mode=evidence_mode,
                basis_refs=basis_refs,
                bound_input_refs=bound_input_refs,
                clause_ids=clause_ids,
                proof_ids=proof_ids,
                **grounding,
            )
        )
    if not parsed:
        raise ValueError("inspection request contained no valid entries")
    return tuple(parsed)


TASK_PROMPT_REF = "task:prompt"


def invalid_authoritative_source_refs(
    requests: tuple[VerifierInspectionRequest, ...], *, available_refs: set[str],
    available_input_refs: set[str] | None = None,
) -> tuple[str, ...]:
    """Content-blind causal check for overlay-command provenance.

    ``basis`` is proof authority and therefore may cite only prior admissible
    observations. ``bound_input_refs`` is the causal execution-input binding:
    it may additionally cite a prior verifier-authored overlay fixture that is
    registered as an exploratory input. This distinction preserves exact test
    stimulus custody without upgrading verifier-created fixture content into
    completion evidence.
    """
    input_refs = available_refs if available_input_refs is None else available_input_refs
    invalid: list[str] = []
    for request in requests:
        if request.kind != "overlay_run_command":
            continue
        if request.evidence_mode == "derived":
            unknown_basis = sorted(set(request.basis_refs) - available_refs)
            unknown_inputs = sorted(set(request.bound_input_refs) - input_refs)
            if unknown_basis:
                invalid.append(
                    f"{request.request_id}: unavailable authoritative basis refs {', '.join(unknown_basis)}"
                )
            if unknown_inputs:
                invalid.append(
                    f"{request.request_id}: unknown or not-yet-observed bound input refs {', '.join(unknown_inputs)}"
                )
            continue
        unknown = sorted(set(request.authoritative_source_refs) - available_refs)
        if unknown:
            invalid.append(
                f"{request.request_id}: unknown or not-yet-observed refs {', '.join(unknown)}"
            )
    return tuple(invalid)


def _bound_overlay_fixture_paths(
    ledger: Any,
    bound_input_refs: tuple[str, ...],
) -> tuple[tuple[str, ...], str]:
    """Resolve only explicitly bound current verifier fixtures to materialize.

    Direct observation refs are causal inputs but do not materialize files.
    A fixture ref resolves only from an immutable current inspection_record
    produced by the model Verifier in the verifier overlay.  This is a
    mechanical provenance lookup; command semantics are never inspected.
    """
    wanted = {str(ref).strip() for ref in bound_input_refs if str(ref).strip()}
    if not wanted:
        return (), ""
    try:
        current_generation = int(ledger.task_state_generation())
    except Exception:
        current_generation = -1
    paths: list[str] = []
    seen_paths: set[str] = set()
    for receipt in ledger.all_receipts():
        if receipt.kind != "inspection_record":
            continue
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        inspection_id = str(payload.get("inspection_id", receipt.receipt_id)).strip()
        if inspection_id not in wanted:
            continue
        if str(payload.get("route_kind", "")).strip() != "overlay_write_fixture":
            continue
        try:
            fresh = int(payload.get("task_state_generation", -1)) == current_generation
        except (TypeError, ValueError):
            fresh = False
        route_parameters = payload.get("route_parameters", {})
        path = str(route_parameters.get("path", "")).strip() if isinstance(route_parameters, Mapping) else ""
        valid = (
            bool(payload.get("observation_valid", receipt.success))
            and bool(payload.get("success", receipt.success))
            and fresh
            and str(payload.get("admissibility", "")).strip() == "exploratory"
            and str(payload.get("execution_scope", "")).strip() == "verifier_overlay"
            and str(payload.get("requester", "")).strip() == "model_verifier"
            and bool(payload.get("canonical_targets"))
            and bool(path)
        )
        if not valid:
            return (), f"bound verifier fixture is not a current valid registered input: {inspection_id}"
        if path not in seen_paths:
            seen_paths.add(path)
            paths.append(path)
    # Any bound ref that is not a fixture is a direct authoritative input and
    # requires no filesystem materialization.  Only refs recognized as fixture
    # records above are mapped to paths.
    return tuple(paths), ""


def execute_verifier_inspection_requests(
    requests: tuple[VerifierInspectionRequest, ...],
    *,
    compiled: CompiledRuntime,
    ledger: Any,
    executor: Any,
    envmap: EnvMap,
    overlay: Any | None = None,
    hooks: Any | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    checks_by_id = {check.check_id: check for check in compiled.planned_checks()}
    all_receipts = tuple(ledger.all_receipts())
    for request in requests:
        if request.kind == "read_file":
            results.append(_read_file_result(request, executor, envmap))
            continue
        if request.kind == "read_output":
            if str(request.handle or "").startswith("receipt:"):
                results.append(_read_cited_receipt_result(request, all_receipts, ledger=ledger))
            else:
                results.append(_read_output_result(request, all_receipts))
            continue
        if request.kind == "compare_initial_path":
            compare = getattr(executor, "compare_initial_path", None)
            if not callable(compare):
                results.append(_error_result(
                    request, "executor lacks immutable initial/current comparison capability",
                ))
                continue
            try:
                comparison = compare(request.path)
            except (OSError, RuntimeError, ValueError) as exc:
                results.append(_error_result(
                    request, f"initial/current comparison failed: {type(exc).__name__}: {exc}",
                ))
                continue
            row = {
                "request_id": request.request_id,
                "kind": request.kind,
                "read_only": True,
                "observation_origin": "initial_current_comparator",
            }
            row.update(comparison)
            results.append(row)
            continue
        if request.kind == "rerun_check":
            check = checks_by_id.get(request.check_id)
            if check is None:
                results.append(_error_result(request, f"unknown check_id: {request.check_id}"))
                continue
            if overlay is None:
                results.append(_error_result(
                    request,
                    "rerun_check requires the verifier overlay; no overlay available",
                ))
                continue
            # Checks execute in the copy-on-demand overlay so verification can
            # never mutate the solver workspace.
            outcome = overlay.run_command(check.command)
            row = {
                "request_id": request.request_id,
                "kind": request.kind,
                "check_id": check.check_id,
                "label": check.label,
                "executed_in": "verifier_overlay",
                "observation_origin": "verifier_overlay",
            }
            row.update(outcome)
            results.append(row)
            continue
        if request.kind == "overlay_run_command":
            if overlay is None:
                results.append(_error_result(request, "no overlay available"))
                continue
            if not getattr(request, "command", "").strip():
                results.append(_error_result(request, "overlay_run_command requires command"))
                continue
            fixture_paths, fixture_error = _bound_overlay_fixture_paths(
                ledger, tuple(getattr(request, "bound_input_refs", ()) or ()),
            )
            if fixture_error:
                results.append(_error_result(request, fixture_error))
                continue
            row = {
                "request_id": request.request_id,
                "kind": request.kind,
                "executed_in": "verifier_overlay",
                "observation_origin": "verifier_overlay",
            }
            row.update(overlay.run_command(
                getattr(request, "command", ""), fixture_paths=fixture_paths,
            ))
            results.append(row)
            continue
        if request.kind == "overlay_write_fixture":
            if overlay is None:
                results.append(_error_result(request, "no overlay available"))
                continue
            if not request.path.strip():
                results.append(_error_result(request, "overlay_write_fixture requires path"))
                continue
            row = {"request_id": request.request_id, "kind": request.kind, "executed_in": "verifier_overlay"}
            row.update(overlay.write_fixture(request.path, getattr(request, "content", "")))
            results.append(row)
            continue
        if request.kind == "perceive_artifact":
            results.append(_perceive_artifact_result(request, executor, envmap, hooks))
            continue
        if request.kind in {"probe_port", "probe_http", "probe_process", "probe_job", "inspect_artifact"}:
            target = getattr(request, "target", "") or request.path
            if request.kind == "probe_port":
                probe = probe_port(executor, target)
            elif request.kind == "probe_http":
                probe = probe_http(executor, target)
            elif request.kind == "probe_process":
                probe = probe_process(executor, target)
            elif request.kind == "probe_job":
                probe = probe_job(executor, target)
            else:
                requested_artifact_path = str(request.path or "").strip()
                try:
                    artifact_path = _resolve_artifact_probe_path(
                        requested_artifact_path, executor, envmap,
                    )
                except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
                    results.append(
                        _error_result(
                            request, f"artifact inspection path error: {exc}",
                        ) | {
                            "path": requested_artifact_path,
                            "requested_path": requested_artifact_path,
                            "read_only": True,
                        }
                    )
                    continue
                probe = inspect_artifact_probe(executor, artifact_path)
                probe["requested_path"] = requested_artifact_path
            row = {
                "request_id": request.request_id,
                "kind": request.kind,
                "read_only": True,
                "observation_origin": "executor_probe",
            }
            row.update(probe)
            results.append(row)
            continue
        if request.kind == "inspect_artifact_history":
            # Filter by the requested artifact BEFORE applying the history
            # limit. Limiting the whole receipt stream first can evict an
            # early pre-mutation read behind unrelated bookkeeping/model
            # receipts, leaving the Verifier with empty history despite an
            # immutable kernel observation still existing in the ledger.
            normalized_path = (
                normalize_relpath(request.path, envmap.workspace_root)
                if request.path else ""
            )
            rows = artifact_history(
                all_receipts,
                path=normalized_path or None,
                limit=request.limit,
            )
            results.append({
                "request_id": request.request_id,
                "kind": request.kind,
                "path": request.path,
                "normalized_path": normalized_path,
                "rows": rows,
                "observation_origin": "ledger_artifact_history",
                "read_only": True,
            })
            continue
        if request.kind == "inspect_action_receipts":
            matching = [
                receipt for receipt in all_receipts
                if receipt.kind in ACTION_RECEIPT_KINDS
                and (not request.receipt_kind or receipt.kind == request.receipt_kind)
            ]
            # Page backward from the newest matching receipt. offset=0 is
            # the newest page; a positive offset skips that many newer rows.
            page_end = max(0, len(matching) - request.offset)
            page_start = max(0, page_end - request.limit)
            selected = matching[page_start:page_end]
            rows = _bounded_action_receipt_rows(selected, request=request)
            successful_count = sum(bool(row.get("success")) for row in rows)
            results.append({
                "request_id": request.request_id,
                "kind": request.kind,
                "clause_ids": list(request.clause_ids),
                "receipt_kind": request.receipt_kind,
                "requested_limit": request.limit,
                "offset": request.offset,
                "matching_count": len(matching),
                "returned_count": len(rows),
                "older_available_count": page_start,
                "newer_skipped_count": len(matching) - page_end,
                "successful_count": successful_count,
                "failed_count": len(rows) - successful_count,
                "omitted_count": max(0, len(selected) - len(rows)),
                "rows": rows,
                "structured_view": "immutable_action_receipts",
                "method_evidence_only": True,
                "observation_origin": "ledger_action_history",
                "read_only": True,
                # Empty or failed-only history is inspectable telemetry, not
                # affirmative method compliance evidence.
                "success": successful_count > 0,
                # Empty/failed matching history is a valid negative observation,
                # not an inspection/tooling failure. Preserve the native outcome
                # separately while reserving error for inability to inspect.
                "outcome_detail": (
                    "" if successful_count > 0 else "no successful matching action receipt"
                ),
                "error": "",
            })
            continue
        if request.kind == "inspect_recent_receipts":
            matching = [
                receipt
                for receipt in all_receipts
                if not request.receipt_kind or receipt.kind == request.receipt_kind
            ]
            selected = matching[-request.limit :]
            rows = _bounded_recent_receipt_rows(
                selected,
                request_id=request.request_id,
                receipt_kind=request.receipt_kind,
                matching_count=len(matching),
                requested_limit=request.limit,
            )
            results.append({
                "request_id": request.request_id,
                "kind": request.kind,
                "receipt_kind": request.receipt_kind,
                "requested_limit": request.limit,
                "matching_count": len(matching),
                "returned_count": len(rows),
                "omitted_count": max(0, len(selected) - len(rows)),
                "rows": rows,
                "metadata_view": "bounded_summary_excerpts",
                "observation_origin": "ledger_metadata",
            })
            continue
        results.append(_error_result(request, f"unsupported inspection kind: {request.kind}"))
    return results


def _bounded_action_receipt_rows(
    receipts: list[Any],
    *,
    request: VerifierInspectionRequest,
) -> list[dict[str, Any]]:
    """Expose exact immutable action facts without outputs or model narrative."""
    compact: list[dict[str, Any]] = []
    for receipt in receipts:
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        safe_payload = {
            key: payload[key]
            for key in ACTION_RECEIPT_PAYLOAD_FIELDS
            if key in payload and payload[key] not in (None, "", (), [], {})
        }
        compact.append({
            "receipt_id": receipt.receipt_id,
            "step": receipt.step,
            "kind": receipt.kind,
            "success": receipt.success,
            "failure_class": receipt.failure_class,
            "state_change": bool(getattr(receipt, "state_change", False)),
            "payload": safe_payload,
        })
    kept_newest_first: list[dict[str, Any]] = []
    for row in reversed(compact):
        candidate = list(reversed(kept_newest_first + [row]))
        envelope = {
            "request_id": request.request_id,
            "kind": "inspect_action_receipts",
            "clause_ids": list(request.clause_ids),
            "receipt_kind": request.receipt_kind,
            "rows": candidate,
        }
        size = len(json.dumps(envelope, sort_keys=True, default=str).encode("utf-8"))
        if size > ACTION_RECEIPTS_PACKET_TARGET_BYTES:
            break
        kept_newest_first.append(row)
    return list(reversed(kept_newest_first))


def _bounded_recent_receipt_rows(
    receipts: list[Any],
    *,
    request_id: str,
    receipt_kind: str,
    matching_count: int,
    requested_limit: int,
) -> list[dict[str, Any]]:
    """Return newest receipt metadata that fits one model-facing result.

    Full summaries remain in the immutable ledger. The verifier receives a
    compact excerpt plus byte count and hash, preventing historical commands
    from being duplicated into context or causing an otherwise successful
    mixed observation batch to fail atomically.
    """
    compact: list[dict[str, Any]] = []
    for receipt in receipts:
        summary = str(receipt.summary or "")
        encoded = summary.encode("utf-8", "replace")
        excerpt = summary[:RECENT_RECEIPT_SUMMARY_EXCERPT_CHARS]
        compact.append({
            "receipt_id": receipt.receipt_id,
            "step": receipt.step,
            "kind": receipt.kind,
            "success": receipt.success,
            "summary": excerpt,
            "summary_bytes": len(encoded),
            "summary_sha256": sha256(encoded).hexdigest(),
            "summary_truncated": excerpt != summary,
            "failure_class": receipt.failure_class,
        })

    # Keep the newest rows, adding older rows only while the complete result
    # remains below the target. Reverse at the end to preserve ledger order.
    kept_newest_first: list[dict[str, Any]] = []
    for row in reversed(compact):
        candidate = list(reversed(kept_newest_first + [row]))
        envelope = {
            "request_id": request_id,
            "kind": "inspect_recent_receipts",
            "receipt_kind": receipt_kind,
            "requested_limit": requested_limit,
            "matching_count": matching_count,
            "returned_count": len(candidate),
            "omitted_count": max(0, len(compact) - len(candidate)),
            "rows": candidate,
            "metadata_view": "bounded_summary_excerpts",
        }
        size = len(json.dumps(envelope, sort_keys=True, default=str).encode("utf-8"))
        if size > RECENT_RECEIPTS_PACKET_TARGET_BYTES:
            break
        kept_newest_first.append(row)
    return list(reversed(kept_newest_first))


def _verifier_read_text(executor: Any, path: str) -> str:
    world_reader = getattr(executor, "read_verifier_file", None)
    if str(path).startswith("/") and callable(world_reader):
        return str(world_reader(path))
    return str(executor.read_file(path))


def _verifier_read_bytes(executor: Any, path: str) -> bytes:
    world_reader = getattr(executor, "read_verifier_file_bytes", None)
    if str(path).startswith("/") and callable(world_reader):
        return bytes(world_reader(path))
    read_bytes = getattr(executor, "read_file_bytes", None)
    if not callable(read_bytes):
        raise RuntimeError("executor lacks binary reads for perceive_artifact")
    return bytes(read_bytes(path))


def _verifier_read_snapshot(executor: Any, path: str) -> tuple[str, int, str, bool, str]:
    """Read one verifier file while preserving byte identity when available.

    Production executors expose an exact byte route.  Decode those bytes only
    for model presentation and explicitly record whether UTF-8 decoding was
    lossless; replacement-decoded binary data must never be promoted as an
    exact semantic text contract.  Simpler test executors that expose only a
    textual reader retain a text-reader contract and are treated as lossless
    text by that narrower interface.
    """
    world_reader = getattr(executor, "read_verifier_file_bytes", None)
    local_reader = getattr(executor, "read_file_bytes", None)
    has_binary_reader = (
        callable(world_reader) if str(path).startswith("/") else callable(local_reader)
    )
    if has_binary_reader:
        raw = _verifier_read_bytes(executor, path)
        try:
            content = raw.decode("utf-8", "strict")
            lossless = True
        except UnicodeDecodeError:
            content = raw.decode("utf-8", "replace")
            lossless = False
        return (
            content, len(raw), sha256(raw).hexdigest()[:16], lossless,
            "captured_bytes",
        )
    content = _verifier_read_text(executor, path)
    raw = content.encode("utf-8")
    return (
        content, len(raw), sha256(raw).hexdigest()[:16], True,
        "text_reader_contract",
    )


def _perceive_artifact_result(
    request: VerifierInspectionRequest, executor: Any, envmap: EnvMap, hooks: Any,
) -> dict[str, Any]:
    """Independent verifier perception: transcribe an image artifact through
    the run's vision model.  The result is the verifier's OWN reading -- it
    never depends on solver-produced transcriptions -- and is still labeled
    model-derived, not ground truth."""
    from .perception_vision import media_type_for
    import base64 as _b64

    perceive = getattr(hooks, "perceive_image", None)
    if not callable(perceive):
        return _error_result(request, "no vision model available for perceive_artifact")
    requested_path = str(request.path or "").strip()
    path = requested_path if requested_path.startswith("/") else normalize_relpath(requested_path, envmap.workspace_root)
    media_type = media_type_for(path)
    if not media_type:
        return _error_result(request, f"unsupported media type for perceive_artifact: {path}")
    try:
        raw = _verifier_read_bytes(executor, path)
    except (OSError, FileNotFoundError, RuntimeError, ValueError) as exc:
        return _error_result(request, f"perceive_artifact read failed: {exc}")
    prompt = (
        "Transcribe/describe the semantic content of this image exactly and "
        "completely. Code and text verbatim; labeled elements and values precisely. "
        "Output only the transcription/description."
    )
    try:
        full_transcription = str(perceive(prompt, _b64.b64encode(raw).decode("ascii"), media_type))
    except Exception as exc:
        return _error_result(request, f"perceive_artifact vision call failed: {exc}")
    transcription_limit = 8000
    transcription = full_transcription[:transcription_limit]
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "path": path,
        "media_type": media_type,
        "bytes": len(raw),
        "content_hash": sha256(raw).hexdigest(),
        "transcription": transcription,
        "transcription_chars_total": len(full_transcription),
        "transcription_complete": len(full_transcription) <= transcription_limit,
        "extraction_authority": "model_transcription_not_ground_truth",
        "observation_origin": "vision_executor",
        "read_only": True,
    }


def _read_file_result(request: VerifierInspectionRequest, executor: Any, envmap: EnvMap) -> dict[str, Any]:
    requested_path = str(request.path or "").strip()
    path = normalize_relpath(requested_path, envmap.workspace_root) if any(token in requested_path for token in ("*", "?", "[")) else _resolve_read_path(requested_path, executor, envmap)
    if any(token in path for token in ("*", "?", "[")):
        matches = tuple(executor.glob(path))[: max(1, request.limit)]
        rows = []
        for matched in matches:
            try:
                content, byte_count, content_hash, lossless, identity_basis = _verifier_read_snapshot(executor, matched)
            except FileNotFoundError:
                rows.append({"path": matched, "error": "file_not_found"})
                continue
            except OSError as exc:
                rows.append({"path": matched, "error": f"read error: {exc}"})
                continue
            rows.append({
                "path": matched,
                "bytes": byte_count,
                "content_chars": len(content),
                "content_hash": content_hash,
                "content_identity_basis": identity_basis,
                "text_decode_lossless": lossless,
                "excerpt": content[: min(1000, len(content))],
                "observation_origin": "executor_read",
                "read_only": True,
            })
        return {
            "request_id": request.request_id,
            "kind": request.kind,
            "path": path,
            "requested_path": requested_path,
            "matched_paths": list(matches),
            "matches": rows,
            "observation_origin": "executor_read",
            "read_only": True,
        }
    try:
        content, byte_count, content_hash, lossless, identity_basis = _verifier_read_snapshot(executor, path)
    except FileNotFoundError:
        candidates = _candidate_paths(requested_path or path, executor, envmap, limit=max(1, request.limit))
        if candidates:
            return _error_result(
                request,
                f"file not found at {path}; candidate path(s) elsewhere: {', '.join(candidates)}",
            ) | {"path": path, "requested_path": requested_path, "candidate_paths": candidates, "read_only": True}
        return _error_result(request, f"file not found at {path}; no candidate paths found") | {
            "path": path, "requested_path": requested_path, "read_only": True,
        }
    except (OSError, RuntimeError, ValueError) as exc:
        return _error_result(request, f"read error: {exc}") | {
            "path": path, "requested_path": requested_path, "read_only": True,
        }
    span = max(1, min(20000, int(getattr(request, "span", 4000) or 4000)))
    offset = max(0, int(getattr(request, "offset", 0) or 0))
    anchor = "offset"
    # Append-only service logs should default to current-state evidence.  A
    # request may still force head/offset by supplying a positive offset.
    if requested_path.lower().endswith((".log", ".out", ".err")) and offset == 0 and len(content) > span:
        offset = max(0, len(content) - span)
        anchor = "tail"
    excerpt = content[offset: offset + span]
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "path": path,
        "requested_path": requested_path,
        "bytes": byte_count,
        "content_chars": len(content),
        "offset": offset,
        "span": span,
        "anchor": anchor,
        "content_hash": content_hash,
        "content_identity_basis": identity_basis,
        "text_decode_lossless": lossless,
        "excerpt": excerpt,
        "observation_origin": "executor_read",
        "read_only": True,
    }


def _resolve_artifact_probe_path(requested_path: str, executor: Any, envmap: EnvMap) -> str:
    """Resolve an artifact target without laundering absolute task-world paths.

    Relative targets remain workspace-relative. Absolute targets are preserved
    and, when the executor exposes a guarded verifier-world resolver, must pass
    that resolver before any shell-backed metadata probe runs. This mirrors the
    read_file privacy boundary without requiring the target to be a text file.
    """
    raw = str(requested_path or "").strip().replace("\\", "/")
    if not raw:
        return ""
    if raw.startswith("/"):
        resolver = getattr(executor, "resolve_verifier_read_path", None)
        if callable(resolver):
            return str(resolver(raw))
        return raw
    return normalize_relpath(raw, envmap.workspace_root)



def _resolve_read_path(requested_path: str, executor: Any, envmap: EnvMap) -> str:
    if not requested_path:
        return ""
    # Absolute paths such as /var/log/... and /etc/nginx/... are legitimate
    # verifier targets.  Do not silently remap them under /app.
    if requested_path.startswith("/"):
        resolver = getattr(executor, "resolve_verifier_read_path", None)
        if callable(resolver):
            try:
                return str(resolver(requested_path))
            except FileNotFoundError:
                pass
            except (OSError, RuntimeError, ValueError):
                # Preserve the requested absolute path so the actual read emits
                # the precise guarded-world error instead of silently remapping
                # it under the workspace root.
                return requested_path
        else:
            try:
                executor.read_file(requested_path)
                return requested_path
            except FileNotFoundError:
                pass
            except (OSError, RuntimeError, ValueError):
                return requested_path
    normalized = normalize_relpath(requested_path, envmap.workspace_root)
    try:
        executor.read_file(normalized)
        return normalized
    except FileNotFoundError:
        pass
    except OSError:
        return normalized
    candidates = _candidate_paths(requested_path, executor, envmap, limit=1)
    if candidates:
        return candidates[0]
    return normalized


def _candidate_paths(requested_path: str, executor: Any, envmap: EnvMap, *, limit: int = 5) -> list[str]:
    clean_req = str(requested_path).strip().strip("/")
    if clean_req.startswith("./"):
        clean_req = clean_req[2:]
    if not clean_req:
        return []
    
    # We want to match paths that end with the requested path.
    # Since fnmatch in real_executor doesn't support sophisticated suffix matching natively,
    # we can just use **/basename and then filter the results to ensure they end with the requested suffix.
    basename = os.path.basename(clean_req)
    if not basename:
        return []
        
    patterns = []
    workspace_root = str(getattr(envmap, "workspace_root", "") or "").rstrip("/")
    if workspace_root:
        patterns.append(f"{workspace_root}/**/{basename}")
    patterns.append(f"**/{basename}")
    
    seen: set[str] = set()
    matches: list[str] = []
    for pattern in patterns:
        try:
            found = tuple(executor.glob(pattern))
        except Exception:
            found = ()
        for path in found:
            text = str(path)
            # Filter matches to ensure they actually end with the requested path snippet
            if text.endswith(clean_req) or text.endswith(f"/{clean_req}"):
                if text not in seen:
                    seen.add(text)
                    matches.append(text)
                if len(matches) >= limit:
                    return matches
    return matches


def _read_cited_receipt_result(
    request: VerifierInspectionRequest,
    receipts: tuple[Any, ...],
    *,
    ledger: Any,
) -> dict[str, Any]:
    """Read one immutable exact receipt snapshot cited by the current PCR claim.

    Provider schema binding is only a convenience boundary. This function is
    the runtime authority: it independently checks the latest Primary claim,
    exact receipt identity, evidence binding/generation, receipt kind/success,
    and snapshot hash before exposing content.
    """
    handle = str(request.handle or "").strip()
    def error(message: str) -> dict[str, Any]:
        return {
            "request_id": request.request_id,
            "kind": "read_cited_receipt",
            "handle": handle,
            "error": message,
        }
    if not handle.startswith("receipt:") or len(handle) <= len("receipt:"):
        return error("read_cited_receipt requires an exact receipt handle")
    claim = next((r for r in reversed(receipts) if r.kind == "primary_submission_claim"), None)
    if claim is None:
        return error("no bound Primary submission claim is available")
    claim_payload = claim.payload if isinstance(claim.payload, Mapping) else {}
    exact_handles = {
        str(item).strip() for item in (claim_payload.get("evidence_exact_handles", ()) or ())
        if str(item).strip()
    }
    receipt_ids = {
        str(item).strip() for item in (claim_payload.get("evidence_receipt_ids", ()) or ())
        if str(item).strip()
    }
    source_receipt_id = handle[len("receipt:"):]
    if handle not in exact_handles or source_receipt_id not in receipt_ids:
        return error("receipt handle is not cited by the current bound Primary submission")
    source = next((r for r in receipts if r.receipt_id == source_receipt_id), None)
    if source is None:
        return error("cited source receipt is missing from the immutable ledger")
    if source.kind != "read_file" or not source.success:
        return error("cited source receipt is not a successful read_file observation")
    bindings = claim_payload.get("evidence_bindings", ()) or ()
    binding = next((
        row for row in bindings
        if isinstance(row, Mapping) and str(row.get("receipt_id") or "").strip() == source_receipt_id
    ), None)
    if not isinstance(binding, Mapping):
        return error("cited source receipt lacks its exact evidence binding")
    evidence_role = str(binding.get("role") or "").strip()
    if evidence_role != "historical_support":
        return error("read_cited_receipt requires a historical-support evidence binding")
    try:
        source_generation = int(binding.get("task_state_generation"))
        submission_generation = int(claim_payload.get("task_state_generation"))
    except (TypeError, ValueError):
        return error("cited source receipt lacks a valid task-state generation binding")
    derived_source_generation = ledger.receipt_task_state_generation(source_receipt_id)
    current_generation = int(ledger.task_state_generation())
    if derived_source_generation is None or int(derived_source_generation) != source_generation:
        return error("cited source generation binding does not match immutable ledger history")
    if submission_generation != current_generation:
        return error("bound Primary submission is stale for the current task-state generation")
    if source_generation >= submission_generation:
        return error("historical-support cited receipt is not older than the submission generation")
    payload = source.payload if isinstance(source.payload, Mapping) else {}
    recorded_hash = str(payload.get("content_hash") or "").strip().lower()
    if not recorded_hash or any(ch not in "0123456789abcdef" for ch in recorded_hash):
        return error("cited read_file receipt lacks a cryptographic content hash")
    candidates: list[tuple[str, str]] = []
    if isinstance(payload.get("content"), str):
        candidates.append(("content", str(payload.get("content"))))
    if isinstance(payload.get("excerpt"), str):
        candidates.append(("excerpt", str(payload.get("excerpt"))))
    exact_content = ""
    content_source = ""
    full_digest = ""
    for source_name, candidate in candidates:
        digest = sha256(candidate.encode("utf-8", "replace")).hexdigest()
        if digest.startswith(recorded_hash):
            exact_content = candidate
            content_source = source_name
            full_digest = digest
            break
    if not content_source:
        return error("cited read_file payload is not a hash-verifiable complete snapshot")
    offset = max(0, int(getattr(request, "offset", 0) or 0))
    span = max(1, min(20_000, int(getattr(request, "span", 4000) or 4000)))
    excerpt = exact_content[offset: offset + span]
    total_chars = len(exact_content)
    returned_chars = len(excerpt)
    next_offset = min(total_chars, offset + returned_chars)
    more_available = next_offset < total_chars
    # F92: consume an immutable cited snapshot capability only after one
    # runtime-authored observation has actually exposed the complete snapshot
    # from its beginning. A final partial page is not enough to prove that the
    # model observed all preceding bytes.
    snapshot_complete = offset == 0 and returned_chars == total_chars
    path = str(payload.get("path") or "").strip()
    return {
        "request_id": request.request_id,
        "kind": "read_cited_receipt",
        "handle": handle,
        "source_receipt_id": source_receipt_id,
        "source_receipt_kind": source.kind,
        "evidence_role": evidence_role,
        "source_task_state_generation": source_generation,
        "submission_task_state_generation": submission_generation,
        "path": path,
        "bytes": len(exact_content.encode("utf-8", "replace")),
        "total_chars": total_chars,
        "offset": offset,
        "span": span,
        "returned_chars": returned_chars,
        "next_offset": next_offset,
        "more_available": more_available,
        "snapshot_complete": snapshot_complete,
        "excerpt": excerpt,
        "content_hash": full_digest,
        "source_content_hash": recorded_hash,
        "snapshot_content_source": content_source,
        "snapshot_verified": True,
        "observation_origin": "ledger_cited_receipt",
        "read_only": True,
    }


def _read_output_result(request: VerifierInspectionRequest, receipts: tuple[Any, ...]) -> dict[str, Any]:
    handle = request.handle or request.path or request.target
    if not handle:
        return _error_result(request, "read_output requires handle")

    full = ""
    source_receipt = ""
    stream = ""
    overflow = ""
    for receipt in receipts:
        payload = receipt.payload or {}
        if payload.get("stdout_handle") == handle:
            full = str(payload.get("stdout_full", ""))
            source_receipt = receipt.receipt_id
            stream = "stdout"
            overflow = str(payload.get("stdout_overflow_path", ""))
            break
        if payload.get("stderr_handle") == handle:
            full = str(payload.get("stderr_full", ""))
            source_receipt = receipt.receipt_id
            stream = "stderr"
            overflow = str(payload.get("stderr_overflow_path", ""))
            break
    if not source_receipt:
        return _error_result(request, f"output handle not found: {handle}")
    if overflow:
        try:
            with open(overflow, encoding="utf-8", errors="replace") as fh:
                full = fh.read()
        except OSError as exc:
            return _error_result(request, f"output spool unreadable for handle {handle}: {exc}")

    offset = max(0, int(getattr(request, "offset", 0) or 0))
    span = max(1, min(20000, int(getattr(request, "span", 4000) or 4000)))
    excerpt = full[offset: offset + span]
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "handle": handle,
        "source_receipt_id": source_receipt,
        "stream": stream,
        "bytes": len(full),
        "offset": offset,
        "span": span,
        "excerpt": excerpt,
        "content_hash": sha256(full.encode("utf-8", "replace")).hexdigest()[:16],
        "observation_origin": "ledger_output",
        "read_only": True,
    }


def _error_result(request: VerifierInspectionRequest, message: str) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "error": message,
    }


def _load_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        decoder = json.JSONDecoder()
        for idx, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(text[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise TypeError("inspection request must be a JSON object or JSON object string")
