"""Canonical current-state inspection registry.

Verifier evidence is accepted only through immutable inspection records.  Model
text may cite an ``inspection_id``; route, target, generation, tool identity,
result hash, and evidence ceiling are always derived from the executed result.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .ledger import TASK_STATE_SNAPSHOT_BINDING_VERSION, ExecutionLedger, Receipt
from .proof_contract import EVIDENCE_STRENGTH, ROUTE_EVIDENCE_CEILINGS


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True)


def _request_view(request: Any) -> dict[str, Any]:
    if request is None:
        return {}
    if is_dataclass(request):
        view = dict(asdict(request))
        if not view.get("proof_ids"):
            view.pop("proof_ids", None)
        return view
    if isinstance(request, Mapping):
        view = dict(request)
        if not view.get("proof_ids"):
            view.pop("proof_ids", None)
        return view
    view = {
        key: getattr(request, key)
        for key in (
            "request_id", "kind", "path", "handle", "check_id", "receipt_kind",
            "limit", "command", "content", "target", "offset", "span",
            "proof_ids",
        )
        if hasattr(request, key)
    }
    if not view.get("proof_ids"):
        view.pop("proof_ids", None)
    return view


def _target_identity(request: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    """Return only a kernel-issued/capability-bound target identity.

    Free-form ``target`` and ``command`` text remain model-authored metadata
    and cannot establish evidence continuity.  Typed probes are different:
    their trusted probe implementation parses and echoes the concrete
    interface it actually observed.  Bind continuity to those normalized
    result fields, never to the model's unvalidated target string.
    """
    kind = str(result.get("kind", "") or request.get("kind", "")).strip()
    if kind == "read_cited_receipt":
        source_receipt_id = str(result.get("source_receipt_id", "")).strip()
        if source_receipt_id:
            return f"receipt:{source_receipt_id}"
    if kind == "probe_port":
        host = str(result.get("host", "")).strip()
        try:
            port = int(result.get("port"))
        except (TypeError, ValueError):
            port = 0
        if host and 1 <= port <= 65535:
            return f"socket:{host}:{port}"
    if kind == "probe_http":
        url = str(result.get("url", "")).strip()
        if url.startswith(("http://", "https://")):
            return f"url:{url}"
    if kind == "probe_job":
        job_id = str(result.get("job_id", "") or result.get("process_id", "")).strip()
        generation = str(result.get("process_generation", "")).strip()
        if job_id and generation:
            return f"job:{job_id}:generation:{generation}"
        if job_id:
            return f"job:{job_id}"
    if kind == "probe_process":
        pattern = str(result.get("pattern", "")).strip()
        if pattern:
            return f"process_pattern:{pattern}"
    if kind == "inspect_action_receipts":
        return "ledger:action_history"
    observed_path = str(result.get("path", "") or "").strip()
    if observed_path:
        return f"path:{observed_path}"
    for key in ("path", "handle", "check_id", "process_id", "service_name"):
        value = str(request.get(key, "") or result.get(key, "")).strip()
        if value:
            return f"{key}:{value}"
    return "target:opaque"


def _observation_type(kind: str) -> str:
    if kind in {"read_file", "read_output"}:
        return "content_observation"
    if kind == "compare_initial_path":
        return "relational_comparison"
    if kind == "read_cited_receipt":
        return "historical_content_observation"
    if kind == "probe_job":
        return "job_lifecycle"
    if kind in {"probe_port", "probe_http", "probe_process", "rerun_check"}:
        return "interface_response"
    if kind == "perceive_artifact":
        return "semantic_perception"
    if kind == "inspect_action_receipts":
        return "execution_history"
    if kind in {"inspect_artifact", "inspect_artifact_history", "inspect_recent_receipts"}:
        return "metadata"
    # Overlay command stdout is deliberately not source evidence.  A future
    # provenance-export capability may create separate direct subreceipts.
    return "execution_result"


def _target_generation(result: Mapping[str, Any]) -> str:
    for key in (
        "content_hash", "sha256", "relation_digest", "generation", "process_generation",
        "artifact_generation", "source_receipt_id",
    ):
        value = str(result.get(key, "")).strip()
        if value:
            return f"{key}:{value}"
    # Request IDs identify calls, not target state. Excluding them keeps two
    # identical read-only observations on the same target at the same material
    # generation equivalent, while any changed observed payload still changes
    # the fallback generation identity.
    generation_view = {
        str(key): value for key, value in result.items()
        if str(key) != "request_id"
    }
    return "result:" + hashlib.sha256(_stable_json(generation_view).encode("utf-8")).hexdigest()


def _tool_identity(result: Mapping[str, Any], *, executor: Any, overlay: Any | None) -> str:
    executed_in = str(result.get("executed_in", "")).strip()
    owner = overlay if executed_in == "verifier_overlay" and overlay is not None else executor
    cls = type(owner)
    return f"{cls.__module__}.{cls.__qualname__}:{executed_in or 'task_executor'}"


def _observation_valid(result: Mapping[str, Any], error: str) -> bool:
    """Return whether the inspection produced a valid bounded observation.

    For execution routes, exit polarity is observed content rather than
    inspection validity.  An exit-1 assertion failure can be decisive
    falsifying evidence just as exit-0 can be supporting evidence.  Only a
    tooling/protocol error or malformed process-result shape makes the
    observation invalid here; semantic polarity remains Verifier-owned.
    """
    if error:
        return False
    # A timed-out execution may contain partial stdout/stderr and even an exit
    # code supplied by a wrapper, but it did not complete the requested
    # observation. Never admit that partial execution as proof or as a
    # semantic negative/falsification result.
    if bool(result.get("timed_out", False)):
        return False
    for key in ("exit_code", "returncode"):
        if key in result:
            try:
                int(result.get(key))
            except (TypeError, ValueError):
                return False
            return True
    # Native ``success`` is observed outcome polarity, not whether the route
    # produced an observation. Direct negative states such as an empty action
    # history remain valid observations. Structural/tooling failure is carried
    # by ``error`` or the route-specific typed-shape checks.
    return True


def _observed_outcome_success(result: Mapping[str, Any]) -> bool | None:
    """Project native outcome polarity without granting proof authority."""
    for key in ("exit_code", "returncode"):
        if key in result:
            try:
                return int(result.get(key)) == 0
            except (TypeError, ValueError):
                return None
    raw = result.get("success")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "ok", "success"}
    return None


_OVERLAY_NETWORK_METHOD_RE = re.compile(
    r"(?i)\b(?:curl|wget|nc|netcat|telnet|grpcurl|ssh|scp|sftp|ping)\b"
    r"|https?://|(?:127\.0\.0\.1|localhost|\[?::1\]?):\d{1,5}\b"
)
_OVERLAY_PROCESS_METHOD_RE = re.compile(
    r"(?i)(?:^|[\s;|&()])(?:pgrep|pidof|ps|ss|netstat|lsof|systemctl|service)\b"
    r"|/proc/(?:self|[0-9]+)(?:/|$)"
)


def _overlay_method_domain_assessment(
    request: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    observed_outcome_success: bool | None,
) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    """Classify operational dependencies of an isolated overlay method only.

    This never interprets task prose. It asks whether a negative command
    outcome attempted to observe a parent-world runtime dimension that the
    executor explicitly attests is absent from the disposable substrate. Such
    a result remains a real observation, but cannot falsify the live parent
    world. Pure filesystem/computation failures retain existing authority.
    """
    contract = result.get("world_domain_contract")
    if not isinstance(contract, Mapping):
        return "unattested", (), (), "overlay substrate did not publish a world-domain contract"
    command = str(request.get("command", "") or result.get("command", ""))
    dependencies: list[str] = []
    if _OVERLAY_NETWORK_METHOD_RE.search(command):
        dependencies.append("live_network_or_service")
    if _OVERLAY_PROCESS_METHOD_RE.search(command):
        dependencies.append("parent_process_lifecycle")
    if observed_outcome_success is not False or not dependencies:
        return "compatible", tuple(dependencies), (), ""
    missing: list[str] = []
    if "live_network_or_service" in dependencies and (
        contract.get("parent_network_namespace_preserved") is False
        or contract.get("outbound_network_enabled") is False
    ):
        missing.append("parent_network_or_service")
    if (
        "parent_process_lifecycle" in dependencies
        and contract.get("parent_processes_preserved") is False
    ):
        missing.append("parent_process_lifecycle")
    if missing:
        return (
            "substrate_limited",
            tuple(dependencies),
            tuple(missing),
            "negative overlay outcome depends on parent-world runtime state absent from the isolated substrate",
        )
    return "compatible", tuple(dependencies), (), ""


def _evidence_strength(value: str) -> int:
    return EVIDENCE_STRENGTH.get(str(value or "").strip(), -1)


def _actual_observation_strength(
    kind: str,
    request: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    ledger: ExecutionLedger,
    task_generation: int,
    observation_valid: bool,
    admissibility: str,
    lifecycle_launch: Receipt | None,
) -> tuple[str, str]:
    """Derive actual evidential authority from typed observation facts only.

    This classifier never interprets task prose or decides whether an observation
    semantically supports a clause. It only bounds what the concrete observation
    is mechanically capable of establishing, then caps that class by the route's
    declared maximum.
    """
    ceiling = str(ROUTE_EVIDENCE_CEILINGS.get(kind, "") or "").strip()

    def capped(candidate: str, reason: str) -> tuple[str, str]:
        if not ceiling:
            return "model_claim", "route_has_no_evidence_ceiling"
        if _evidence_strength(candidate) > _evidence_strength(ceiling):
            return ceiling, reason + "_capped_by_route"
        return candidate, reason

    if not observation_valid:
        return capped("model_claim", "invalid_observation")

    origin = str(result.get("observation_origin", "") or "").strip()
    if kind == "read_file":
        if origin != "executor_read" or "matches" in result:
            return capped("metadata_proxy", "file_not_single_executor_snapshot")
        if result.get("text_decode_lossless") is False:
            return capped("metadata_proxy", "binary_or_non_utf8_snapshot")
        try:
            content_chars = int(result.get("content_chars", result.get("bytes")))
            offset = int(result.get("offset", 0) or 0)
        except (TypeError, ValueError):
            content_chars = -1; offset = -1
        excerpt = result.get("excerpt")
        complete = (
            content_chars >= 0 and offset == 0 and isinstance(excerpt, str)
            and len(excerpt) == content_chars
            and bool(str(result.get("content_hash") or "").strip())
            and bool(str(result.get("path") or request.get("path") or "").strip())
        )
        return capped("exact_contract" if complete else "metadata_proxy", "full_file_snapshot" if complete else "partial_file_snapshot")

    if kind == "read_cited_receipt":
        complete = (
            origin == "ledger_cited_receipt"
            and result.get("snapshot_verified") is True
            and result.get("snapshot_complete") is True
            and bool(str(result.get("content_hash") or "").strip())
            and bool(str(result.get("source_receipt_id") or "").strip())
        )
        return capped("exact_contract" if complete else "metadata_proxy", "verified_historical_snapshot" if complete else "partial_historical_snapshot")

    if kind == "compare_initial_path":
        exact = (
            origin == "initial_current_comparator"
            and result.get("current_stable") is True
            and str(result.get("relation", "")).strip() in {
                "equal", "different", "created", "removed", "kind_changed", "absent_both"
            }
            and bool(str(result.get("initial_snapshot_digest") or "").strip())
            and bool(str(result.get("relation_digest") or "").strip())
            and isinstance(result.get("initial"), Mapping)
            and isinstance(result.get("current"), Mapping)
        )
        return capped("exact_contract" if exact else "model_claim", "stable_generation0_current_relation" if exact else "relational_identity_or_stability_missing")

    if kind == "read_output":
        try:
            total = int(result.get("bytes"))
            offset = int(result.get("offset", 0) or 0)
        except (TypeError, ValueError):
            total = -1; offset = -1
        excerpt = result.get("excerpt")
        complete = (
            origin == "ledger_output" and total >= 0 and offset == 0
            and isinstance(excerpt, str) and len(excerpt) == total
            and bool(str(result.get("source_receipt_id") or "").strip())
            and bool(str(result.get("content_hash") or "").strip())
        )
        return capped("behavioral" if complete else "metadata_proxy", "full_ledger_output" if complete else "partial_ledger_output")

    if kind == "inspect_artifact":
        exists = result.get("exists")
        digest = str(result.get("sha256") or "").strip().lower()
        hash_exact = len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest)
        exact = origin == "executor_probe" and exists is True and hash_exact
        return capped("exact_contract" if exact else "metadata_proxy", "hashed_artifact_state" if exact else "artifact_metadata_only")

    if kind == "rerun_check":
        exact = (
            origin == "verifier_overlay" and str(result.get("check_id") or request.get("check_id") or "").strip()
            and any(key in result for key in ("exit_code", "returncode"))
        )
        return capped("exact_contract" if exact else "behavioral", "bound_authoritative_check" if exact else "unbound_check_execution")

    if kind == "overlay_run_command":
        if admissibility != "verdict_eligible" or origin != "verifier_overlay":
            return capped("model_claim", "derived_execution_not_admitted")
        basis = tuple(str(item).strip() for item in request.get("basis_refs", ()) if str(item).strip())
        records = inspection_records_by_id(ledger)
        basis_exact = bool(basis)
        for ref in basis:
            receipt = records.get(ref)
            payload = receipt.payload if receipt is not None and isinstance(receipt.payload, Mapping) else {}
            try:
                fresh = int(payload.get("task_state_generation", -1)) == int(task_generation)
            except (TypeError, ValueError):
                fresh = False
            if (
                receipt is None or not fresh
                or str(payload.get("admissibility", "")) != "direct_admissible"
                or _evidence_strength(str(payload.get("actual_evidence_class", ""))) < _evidence_strength("exact_contract")
            ):
                basis_exact = False
                break
        return capped("exact_contract" if basis_exact else "behavioral", "derived_from_exact_inputs" if basis_exact else "derived_behavioral_execution")

    if kind == "probe_http":
        behavioral = origin == "executor_probe" and result.get("response_observed") is True and any(key in result for key in ("status", "status_code"))
        return capped("behavioral" if behavioral else "metadata_proxy", "observed_http_response" if behavioral else "http_metadata_only")

    if kind in {"probe_port", "probe_process", "inspect_recent_receipts", "inspect_artifact_history"}:
        return capped("metadata_proxy", "metadata_route")

    if kind == "probe_job":
        exact = (
            origin == "executor_probe" and lifecycle_launch is not None
            and result.get("process_generation_verified") is True
            and bool(str(result.get("process_generation") or "").strip())
            and str(result.get("status") or "").strip() in {"running", "completed", "failed", "exited", "unknown"}
        )
        return capped("exact_contract" if exact else "metadata_proxy", "registered_job_generation" if exact else "unbound_job_metadata")

    if kind == "perceive_artifact":
        semantic = (
            origin == "vision_executor"
            and bool(str(result.get("transcription") or "").strip())
            and bool(str(result.get("content_hash") or "").strip())
            # Production rows explicitly report whether the bounded model-facing
            # transcription is complete. Legacy rows predate the field, so only
            # an explicit False is downgraded for compatibility.
            and result.get("transcription_complete") is not False
        )
        return capped(
            "independent_semantic" if semantic else "metadata_proxy",
            "independent_vision_transcription" if semantic else "partial_or_unbound_perception",
        )

    if kind == "inspect_action_receipts":
        rows = result.get("rows")
        complete = (
            origin == "ledger_action_history" and isinstance(rows, list) and bool(rows)
            and bool(result.get("method_evidence_only"))
            and int(result.get("omitted_count", 0) or 0) == 0
            and int(result.get("older_available_count", 0) or 0) == 0
            and int(result.get("newer_skipped_count", 0) or 0) == 0
            and int(result.get("successful_count", 0) or 0) > 0
        )
        return capped("exact_contract" if complete else "metadata_proxy", "complete_action_history" if complete else "partial_action_history")

    return capped("model_claim", "unclassified_route")


def _typed_observation_valid(
    kind: str,
    result: Mapping[str, Any],
    *,
    proof_bound: bool,
) -> tuple[bool, str]:
    """Require executor-shaped observations for shadow proof-bound requests.

    V1 requests without proof IDs retain their existing compatibility
    behavior.  V2 proof admission is stricter: a model-provided path or text
    cannot impersonate a trusted observation without the route's executor
    marker and minimum result shape.
    """
    origin = str(result.get("observation_origin", "")).strip()
    # F90 exact cited snapshots always receive an exact-contract route ceiling,
    # so their typed provenance contract is mandatory even when no shadow
    # proof_id is attached. Legacy compatibility must never upgrade a malformed
    # synthetic row merely because the request was not proof-bound.
    if kind == "compare_initial_path":
        relation = str(result.get("relation", "")).strip()
        if (
            origin != "initial_current_comparator"
            or relation not in {"equal", "different", "created", "removed", "kind_changed", "absent_both"}
            or result.get("current_stable") is not True
            or not str(result.get("initial_snapshot_digest") or "").strip()
            or not str(result.get("relation_digest") or "").strip()
            or not isinstance(result.get("initial"), Mapping)
            or not isinstance(result.get("current"), Mapping)
        ):
            return False, "compare_initial_path lacks stable immutable baseline/current identities"
        return True, ""
    if kind == "read_cited_receipt":
        generation = result.get("source_task_state_generation")
        try:
            int(generation)
            total_chars = int(result.get("total_chars"))
            offset = int(result.get("offset"))
            returned_chars = int(result.get("returned_chars"))
            next_offset = int(result.get("next_offset"))
            generation_valid = True
        except (TypeError, ValueError):
            total_chars = offset = returned_chars = next_offset = -1
            generation_valid = False
        excerpt = result.get("excerpt")
        more_available = result.get("more_available")
        snapshot_complete = result.get("snapshot_complete")
        paging_valid = (
            generation_valid
            and total_chars >= 0
            and 0 <= offset <= total_chars
            and returned_chars >= 0
            and isinstance(excerpt, str)
            and len(excerpt) == returned_chars
            and next_offset == min(total_chars, offset + returned_chars)
            and isinstance(more_available, bool)
            and more_available == (next_offset < total_chars)
            and isinstance(snapshot_complete, bool)
            and snapshot_complete == (offset == 0 and returned_chars == total_chars)
        )
        if (
            origin != "ledger_cited_receipt"
            or result.get("snapshot_verified") is not True
            or not str(result.get("source_receipt_id") or "").strip()
            or str(result.get("source_receipt_kind") or "").strip() != "read_file"
            or str(result.get("evidence_role") or "").strip() != "historical_support"
            or not generation_valid
            or not str(result.get("content_hash") or "").strip()
            or not paging_valid
        ):
            return False, "read_cited_receipt lacks exact cited snapshot provenance, hash, or paging truth"
        return True, ""
    if not proof_bound:
        return True, ""
    if kind == "read_file":
        if origin != "executor_read" or not any(result.get(key) for key in ("content_hash", "content_handle", "excerpt")):
            return False, "read_file lacks executor observation content or handle"
    elif kind == "read_output":
        if origin != "ledger_output" or not result.get("source_receipt_id") or not result.get("content_hash"):
            return False, "read_output lacks a bound ledger receipt and output hash"
    elif kind == "inspect_artifact":
        if origin != "executor_probe" or not result.get("path") or "exists" not in result:
            return False, "inspect_artifact lacks a registered executor observation"
    elif kind in {"rerun_check", "overlay_run_command"}:
        if origin != "verifier_overlay" or "exit_code" not in result:
            return False, "execution route lacks verifier-overlay exit status"
    elif kind == "probe_job":
        status = str(result.get("status", "")).strip()
        valid_status = status in {"running", "completed", "failed", "exited", "unknown"}
        lifecycle_authority = str(result.get("lifecycle_authority", "")).strip()
        terminal_shape = (
            status not in {"completed", "failed", "exited"}
            or isinstance(result.get("job_exit_code"), int)
            or (status == "exited" and lifecycle_authority == "registered_process_generation")
        )
        if (
            origin != "executor_probe"
            or not result.get("job_id")
            or not result.get("process_generation")
            or not bool(result.get("process_generation_verified"))
            or not valid_status
            or "completed" not in result
            or not terminal_shape
        ):
            return False, "probe_job lacks an exact registered generation, lifecycle status, or terminal exit code"
    elif kind == "probe_http":
        if origin != "executor_probe" or not result.get("response_observed") or not any(
            key in result for key in ("status", "status_code")
        ):
            return False, "probe_http lacks an executor-observed response"
    elif kind == "perceive_artifact":
        if origin != "vision_executor" or not result.get("transcription"):
            return False, "perceive_artifact lacks an executor-backed perceptual result"
    elif kind == "inspect_action_receipts":
        rows = result.get("rows", ())
        complete = (
            isinstance(rows, list)
            and bool(rows)
            and origin == "ledger_action_history"
            and bool(result.get("method_evidence_only"))
            and int(result.get("omitted_count", 0) or 0) == 0
            and int(result.get("older_available_count", 0) or 0) == 0
            and int(result.get("newer_skipped_count", 0) or 0) == 0
        )
        if not complete:
            return False, "inspect_action_receipts lacks a complete immutable action-history view"
    else:
        return False, f"route {kind} has no typed proof-observation contract"
    return True, ""


def _route(request: Mapping[str, Any], result: Mapping[str, Any]) -> tuple[str, str]:
    kind = str(result.get("kind", "") or request.get("kind", "")).strip()
    if kind == "overlay_run_command":
        command = str(request.get("command", "") or result.get("command", "")).strip()
        if command:
            digest = hashlib.sha256(command.encode("utf-8", "replace")).hexdigest()[:16]
            return kind, f"{kind}:command_sha256:{digest}"
    target = ""
    for key in ("path", "handle", "check_id", "target", "command"):
        target = str(result.get(key, "") or request.get(key, "")).strip()
        if target:
            break
    return kind, f"{kind}:{target}" if target else kind



def _matching_job_launch_receipt(
    ledger: ExecutionLedger,
    request: Mapping[str, Any],
    result: Mapping[str, Any],
) -> Receipt | None:
    job_id = str(result.get("job_id", "") or result.get("process_id", "")).strip()
    generation = str(result.get("process_generation", "")).strip()
    request_target = str(request.get("target", "")).strip()
    if not job_id or not generation or not request_target:
        return None
    for receipt in reversed(ledger.all_receipts()):
        if receipt.kind != "process_launch" or not receipt.success:
            continue
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        launch_id = str(payload.get("job_id", "") or payload.get("process_id", "")).strip()
        launch_generation = str(payload.get("process_generation", "")).strip()
        launch_name = str(payload.get("service_name", "")).strip()
        if (
            launch_id == job_id
            and launch_generation == generation
            and request_target in {launch_id, launch_name}
            and str(payload.get("launch_tool", "")).strip() == "start_job"
        ):
            return receipt
    return None


def _target_binding_valid(request: Mapping[str, Any], result: Mapping[str, Any]) -> bool:
    """Bind proof-capable direct observations to the target actually requested.

    The executor result is the observation authority; the model-authored request
    only selects what to inspect. If both sides expose a concrete selector and
    they disagree, the observation stays useful telemetry but cannot become
    proof for the requested target. Missing result selectors retain legacy
    compatibility rather than manufacturing a mismatch from absent metadata.
    """
    kind = str(request.get("kind", "") or result.get("kind", "")).strip()

    def same(request_key: str, result_key: str) -> bool:
        requested = str(request.get(request_key, "") or "").strip()
        observed = str(result.get(result_key, "") or "").strip()
        if not observed:
            return True
        return bool(requested) and requested == observed

    if kind == "read_file":
        requested = str(request.get("path", "") or result.get("requested_path", "")).strip()
        observed = str(result.get("path", "") or "").strip()
        if not observed:
            return True
        if not requested:
            return False
        def clean(value: str) -> str:
            while value.startswith("./"):
                value = value[2:]
            return value.rstrip("/")
        return clean(requested) == clean(observed)
    if kind == "probe_http":
        return same("target", "url")
    if kind == "probe_process":
        return same("target", "pattern")
    if kind == "probe_job":
        return same("target", "target")
    if kind == "read_output":
        return same("handle", "handle")
    if kind == "rerun_check":
        return same("check_id", "check_id")
    if kind == "probe_port":
        requested = str(request.get("target", "") or "").strip()
        host = str(result.get("host", "") or "").strip()
        try:
            port = int(result.get("port"))
        except (TypeError, ValueError):
            return True if not host and result.get("port") in (None, "") else False
        if not host:
            return True
        if not requested:
            return False
        if ":" in requested:
            requested_host, _, requested_port = requested.rpartition(":")
            requested_host = requested_host.strip() or "127.0.0.1"
        else:
            requested_host, requested_port = "127.0.0.1", requested
        def canonical_host(value: str) -> str:
            lowered = value.strip().lower()
            return "127.0.0.1" if lowered == "localhost" else lowered
        try:
            return canonical_host(requested_host) == canonical_host(host) and int(requested_port) == port
        except ValueError:
            return False
    return True

def register_inspection_results(
    requests: Sequence[Any],
    results: Sequence[Mapping[str, Any]],
    *,
    ledger: ExecutionLedger,
    step: int,
    requester: str,
    executor: Any,
    overlay: Any | None,
    packet_signature: str,
    proof_contract_identity: str = "",
    require_independent_isolation: bool = False,
    strict_snapshot_binding: bool = False,
) -> list[dict[str, Any]]:
    """Register every executed inspection and return rows enriched with IDs.

    Registration happens before rows return to the Verifier, so the model can
    cite only identities that already exist in the append-only ledger.
    """
    request_by_id: dict[str, dict[str, Any]] = {}
    positional: list[dict[str, Any]] = []
    for request in requests:
        view = _request_view(request)
        positional.append(view)
        request_id = str(view.get("request_id", "")).strip()
        if request_id and request_id not in request_by_id:
            request_by_id[request_id] = view

    existing = sum(1 for receipt in ledger.all_receipts() if receipt.kind == "inspection_record")
    enriched: list[dict[str, Any]] = []
    for index, raw_result in enumerate(results):
        result = dict(raw_result)
        request_id = str(result.get("request_id", "")).strip()
        request = request_by_id.get(request_id, positional[index] if index < len(positional) else {})
        kind, route = _route(request, result)
        ceiling = ROUTE_EVIDENCE_CEILINGS.get(kind, "")
        target_identity = _target_identity(request, result)
        observation_type = _observation_type(kind)
        target_generation = _target_generation(result)
        execution_scope = str(
            result.get("executed_in", "") or request.get("executed_in", "")
        ).strip()
        proof_ids_raw = request.get("proof_ids", ())
        if isinstance(proof_ids_raw, str):
            proof_ids_raw = (proof_ids_raw,)
        proof_ids = tuple(
            str(item).strip() for item in proof_ids_raw
            if str(item).strip()
        ) if isinstance(proof_ids_raw, (list, tuple)) else ()
        result_hash = hashlib.sha256(_stable_json(result).encode("utf-8")).hexdigest()
        inspection_id = f"inspection:{step}:{existing + index}:{request_id or kind or 'unknown'}"
        error = str(result.get("error", "")).strip()
        # Observation validity and observed task/test polarity are distinct.
        # A non-zero independent check may be decisive falsifying evidence;
        # tooling/protocol failure is what makes the observation invalid.
        observation_valid = _observation_valid(result, error)
        observed_outcome_success = _observed_outcome_success(result)
        # Keep the legacy Receipt.success polarity for compatibility with
        # positive-proof consumers. Evidence admissibility uses the separate
        # observation_valid field below.
        receipt_success = (
            observed_outcome_success
            if observed_outcome_success is not None
            else observation_valid
        )
        typed_valid, typed_failure = _typed_observation_valid(
            kind, result, proof_bound=bool(proof_ids),
        )
        isolation_required = bool(
            require_independent_isolation
            and kind in {"rerun_check", "overlay_run_command"}
        )
        isolation_verified = bool(
            result.get("independent_isolation_verified") is True
            and result.get("isolation_cleanup_verified") is True
        )
        if isolation_required and not isolation_verified:
            typed_valid = False
            typed_failure = "PCR executable Verifier observation lacks verified independent isolation and teardown"
        lifecycle_launch = None
        if kind == "probe_job" and proof_ids:
            lifecycle_launch = _matching_job_launch_receipt(ledger, request, result)
            if lifecycle_launch is None:
                typed_valid = False
                typed_failure = "probe_job is not bound to its original start_job receipt and generation"
        task_generation = ledger.task_state_generation()
        task_snapshot_digest = ""
        task_snapshot_known = True
        if strict_snapshot_binding:
            task_snapshot_digest = str(ledger.task_state_snapshot_digest())
            task_snapshot_known = bool(ledger.task_state_snapshot_known())
        target_binding_valid = _target_binding_valid(request, result)
        # ``admissibility`` is the sole proof-authority classification.  In
        # particular, an opaque overlay command can be useful exploratory
        # telemetry but it cannot become proof merely because it succeeded.
        # A derived execution is upgraded only when its inputs were already
        # registered direct observations with canonical targets.
        if not typed_valid:
            observation_valid = False
        admissibility = "direct_admissible"
        if not observation_valid or not target_binding_valid:
            admissibility = "exploratory"
        if observation_type == "relational_comparison" and observation_valid and typed_valid:
            admissibility = "verdict_eligible"
        method_domain_status = "not_applicable"
        method_domain_dependencies: tuple[str, ...] = ()
        method_domain_missing: tuple[str, ...] = ()
        method_domain_reason = ""
        # A direct live probe can truthfully observe that its own executor
        # namespace cannot resolve a requested hostname without establishing
        # that the service itself is absent. Keep such addressability failures
        # visible, but never admit them as a semantic negative about Primary's
        # configured world.
        if (
            kind in {"probe_http", "probe_port"}
            and str(result.get("failure_class", "")).strip() == "dns_resolution"
        ):
            method_domain_status = "substrate_limited"
            method_domain_dependencies = ("endpoint_addressability",)
            method_domain_missing = ("requested_hostname_resolution_in_probe_namespace",)
            method_domain_reason = (
                "requested hostname did not resolve in the executor probe namespace; "
                "this observation cannot falsify service state in another/client namespace"
            )
            admissibility = "exploratory"
        if observation_type == "execution_result":
            admissibility = "exploratory"
            if (
                observation_valid
                and typed_valid
                and
                str(request.get("evidence_mode", "")) == "derived"
                and _bound_to_prior_direct_inputs(
                    ledger, request, task_generation=task_generation,
                )
            ):
                admissibility = "verdict_eligible"
            if kind == "overlay_run_command":
                (
                    method_domain_status,
                    method_domain_dependencies,
                    method_domain_missing,
                    method_domain_reason,
                ) = _overlay_method_domain_assessment(
                    request, result,
                    observed_outcome_success=observed_outcome_success,
                )
                if method_domain_status == "substrate_limited":
                    # Keep the command result visible as a truthful observation,
                    # but do not let a missing parent-world runtime dimension
                    # become evidence that Primary's live world is wrong.
                    admissibility = "exploratory"
        action_contract_guarantees: list[str] = []
        if kind == "inspect_action_receipts":
            for history_row in result.get("rows", ()) if isinstance(result.get("rows", ()), list) else ():
                history_payload = history_row.get("payload", {}) if isinstance(history_row, Mapping) else {}
                guarantees = history_payload.get("contract_guarantees", ()) if isinstance(history_payload, Mapping) else ()
                if isinstance(guarantees, str):
                    guarantees = (guarantees,)
                if isinstance(guarantees, (list, tuple)):
                    action_contract_guarantees.extend(
                        str(item).strip() for item in guarantees if str(item).strip()
                    )
        actual_evidence_class, actual_evidence_reason = _actual_observation_strength(
            kind, request, result, ledger=ledger, task_generation=task_generation,
            observation_valid=observation_valid, admissibility=admissibility,
            lifecycle_launch=lifecycle_launch,
        )
        eligible_for_proof = bool(
            observation_valid
            and receipt_success
            and ceiling
            and target_binding_valid
            and admissibility in {"direct_admissible", "verdict_eligible"}
            and kind != "read_cited_receipt"
        )
        eligible_for_basis = bool(
            eligible_for_proof
            or (
                kind == "read_cited_receipt"
                and observation_valid
                and ceiling
                and admissibility == "direct_admissible"
                and target_identity != "target:opaque"
            )
        )
        payload = {
            "inspection_id": inspection_id,
            "request_id": request_id,
            "requester": requester,
            "route_kind": kind,
            "route": route,
            "route_parameters": request,
            "target_identity": target_identity,
            "canonical_targets": [] if target_identity == "target:opaque" else [target_identity],
            "target_binding_valid": target_binding_valid,
            "observation_type": observation_type,
            "admissibility": admissibility,
            "target_generation": target_generation,
            "task_state_generation": task_generation,
            "packet_signature": packet_signature,
            "tool_identity": _tool_identity(result, executor=executor, overlay=overlay),
            "result_hash": result_hash,
            "result_summary": error or str(result.get("summary", "") or result.get("excerpt", ""))[:1000],
            "evidence_ceiling": ceiling,
            "actual_evidence_class": actual_evidence_class,
            "actual_evidence_reason": actual_evidence_reason,
            "action_contract_guarantees": sorted(set(action_contract_guarantees)),
            "lifecycle_binding_verified": bool(lifecycle_launch),
            "lifecycle_launch_receipt_id": lifecycle_launch.receipt_id if lifecycle_launch is not None else "",
            # Retained as a compatibility projection only.  Consumers must
            # derive authority from ``admissibility``; this value can never
            # elevate exploratory evidence.
            "eligible_for_proof": eligible_for_proof,
            "eligible_for_basis": eligible_for_basis,
            "observation_valid": observation_valid,
            "observed_outcome_success": observed_outcome_success,
            "observed_exit_code": (
                result.get("exit_code") if "exit_code" in result else result.get("returncode")
            ),
            "observed_http_status": (
                result.get("status_code") if "status_code" in result else result.get("status")
            ),
            "observed_timed_out": bool(result.get("timed_out", False)),
            "observed_stdout_bytes": result.get("stdout_bytes"),
            "observed_stderr_bytes": result.get("stderr_bytes"),
            "observed_stdout_sha256": (
                hashlib.sha256(str(result.get("stdout", "")).encode("utf-8", "replace")).hexdigest()
                if "stdout" in result else ""
            ),
            "observed_stderr_sha256": (
                hashlib.sha256(str(result.get("stderr", "")).encode("utf-8", "replace")).hexdigest()
                if "stderr" in result else ""
            ),
            "independent_isolation_required": isolation_required,
            "independent_isolation_verified": isolation_verified,
            "execution_isolation": str(result.get("execution_isolation", "") or ""),
            "isolation_backend": str(result.get("isolation_backend", "") or ""),
            "isolation_cleanup_verified": bool(result.get("isolation_cleanup_verified", False)),
            "world_domain_contract": dict(result.get("world_domain_contract") or {})
            if isinstance(result.get("world_domain_contract"), Mapping) else {},
            "method_domain_status": method_domain_status,
            "method_domain_dependencies": list(method_domain_dependencies),
            "method_domain_missing": list(method_domain_missing),
            "method_domain_reason": method_domain_reason,
            # Legacy outcome polarity retained for positive-proof consumers.
            # Do not use this field to decide whether an observation exists;
            # evidence selectors use observation_valid.
            "success": receipt_success,
            "error": error,
        }
        if strict_snapshot_binding:
            payload.update({
                "task_state_snapshot_digest": task_snapshot_digest,
                "task_state_snapshot_known": task_snapshot_known,
                "snapshot_binding_version": TASK_STATE_SNAPSHOT_BINDING_VERSION,
            })
        if kind == "read_cited_receipt":
            payload.update({
                "source_receipt_id": str(result.get("source_receipt_id") or ""),
                "source_receipt_kind": str(result.get("source_receipt_kind") or ""),
                "evidence_role": str(result.get("evidence_role") or ""),
                "source_task_state_generation": result.get("source_task_state_generation"),
                "submission_task_state_generation": result.get("submission_task_state_generation"),
                "snapshot_verified": bool(result.get("snapshot_verified")),
                "source_content_hash": str(result.get("source_content_hash") or ""),
            })
        if proof_contract_identity:
            payload["proof_contract_identity"] = proof_contract_identity
        if not observation_valid:
            payload["observation_failure"] = error or typed_failure or "inspection did not produce a valid observation"
        if proof_ids:
            payload["proof_ids"] = list(proof_ids)
        if execution_scope:
            payload["execution_scope"] = execution_scope
        ledger.record(Receipt(
            receipt_id=inspection_id,
            step=step,
            kind="inspection_record",
            success=receipt_success,
            summary=(
                f"registered {kind or 'unknown'} inspection of {target_identity}"
                if observation_valid else f"inspection failed for {target_identity}: {error or typed_failure}"
            ),
            # A negative tested outcome is not a tooling failure. Preserve the
            # legacy success bit without manufacturing a failure class.
            failure_class="" if observation_valid else "verifier_inspection_failed",
            payload=payload,
        ))
        result.update({
            "inspection_id": inspection_id,
            "registered_route": route,
            "target_identity": target_identity,
            "canonical_targets": payload["canonical_targets"],
            "target_binding_valid": payload["target_binding_valid"],
            "observation_type": observation_type,
            "admissibility": payload["admissibility"],
            "target_generation": target_generation,
            "observed_task_state_generation": task_generation,
            "tool_identity": payload["tool_identity"],
            "result_hash": result_hash,
            "evidence_ceiling": ceiling,
            "actual_evidence_class": actual_evidence_class,
            "actual_evidence_reason": actual_evidence_reason,
            "eligible_for_proof": payload["eligible_for_proof"],
            "eligible_for_basis": payload["eligible_for_basis"],
            "observation_valid": observation_valid,
            "observed_outcome_success": observed_outcome_success,
            "observed_exit_code": payload["observed_exit_code"],
            "observed_http_status": payload["observed_http_status"],
            "observed_timed_out": payload["observed_timed_out"],
            "independent_isolation_required": payload["independent_isolation_required"],
            "independent_isolation_verified": payload["independent_isolation_verified"],
            "execution_isolation": payload["execution_isolation"],
            "isolation_backend": payload["isolation_backend"],
            "isolation_cleanup_verified": payload["isolation_cleanup_verified"],
            "world_domain_contract": payload["world_domain_contract"],
            "method_domain_status": payload["method_domain_status"],
            "method_domain_dependencies": payload["method_domain_dependencies"],
            "method_domain_missing": payload["method_domain_missing"],
            "method_domain_reason": payload["method_domain_reason"],
            "error": error,
            "lifecycle_binding_verified": payload["lifecycle_binding_verified"],
            "lifecycle_launch_receipt_id": payload["lifecycle_launch_receipt_id"],
        })
        if strict_snapshot_binding:
            result.update({
                "task_state_snapshot_digest": task_snapshot_digest,
                "task_state_snapshot_known": task_snapshot_known,
                "snapshot_binding_version": TASK_STATE_SNAPSHOT_BINDING_VERSION,
            })
        if proof_contract_identity:
            result["proof_contract_identity"] = proof_contract_identity
        if not observation_valid:
            result["observation_failure"] = error or typed_failure or "inspection did not produce a valid observation"
        enriched.append(result)
    return enriched


def inspection_superseded_by_later_observation(
    ledger: ExecutionLedger,
    receipt: Receipt,
) -> bool:
    """Whether a later valid same-route observation saw different target state.

    Task mutation generation catches harness-observed writes, but services,
    external processes, and even files changed outside a governed mutation can
    vary between two read-only inspections. A proof may not cherry-pick an
    older favorable observation once the Verifier has a newer contradictory
    observation of the same canonical target through the same route.
    """
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    route_kind = str(payload.get("route_kind", "")).strip()
    target_identity = str(payload.get("target_identity", "")).strip()
    target_generation = str(payload.get("target_generation", "")).strip()
    if not route_kind or not target_identity or target_identity == "target:opaque" or not target_generation:
        return False
    try:
        task_generation = int(payload.get("task_state_generation", -1))
    except (TypeError, ValueError):
        return False
    seen = False
    for later in ledger.all_receipts():
        if later.receipt_id == receipt.receipt_id:
            seen = True
            continue
        if not seen or later.kind != "inspection_record":
            continue
        later_payload = later.payload if isinstance(later.payload, Mapping) else {}
        if not bool(later_payload.get("observation_valid", later.success)):
            continue
        if str(later_payload.get("route_kind", "")).strip() != route_kind:
            continue
        if str(later_payload.get("target_identity", "")).strip() != target_identity:
            continue
        try:
            later_task_generation = int(later_payload.get("task_state_generation", -1))
        except (TypeError, ValueError):
            continue
        if later_task_generation != task_generation:
            continue
        later_target_generation = str(later_payload.get("target_generation", "")).strip()
        if later_target_generation and later_target_generation != target_generation:
            return True
    return False


def inspection_records_by_id(ledger: ExecutionLedger) -> dict[str, Receipt]:
    return {
        str(receipt.payload.get("inspection_id", receipt.receipt_id)): receipt
        for receipt in ledger.all_receipts()
        if receipt.kind == "inspection_record"
    }


def _bound_to_prior_direct_inputs(
    ledger: ExecutionLedger,
    request: Mapping[str, Any],
    *,
    task_generation: int,
) -> bool:
    """Whether a derived command has direct authority plus bound causal inputs.

    ``basis_refs`` must all be current direct-admissible observations.
    ``bound_input_refs`` may additionally contain a prior verifier-created
    overlay fixture. The fixture binds the exact test stimulus but remains
    exploratory: it cannot enter the authoritative basis or final proof refs.
    """
    basis = {str(item).strip() for item in request.get("basis_refs", ()) if str(item).strip()}
    bound = {str(item).strip() for item in request.get("bound_input_refs", ()) if str(item).strip()}
    if not basis or not bound:
        return False
    records = inspection_records_by_id(ledger)

    def current(receipt: Receipt) -> bool:
        try:
            return int(receipt.payload.get("task_state_generation", -1)) == task_generation
        except (TypeError, ValueError):
            return False

    for ref in basis:
        receipt = records.get(ref)
        if (
            receipt is None
            or not bool(receipt.payload.get("observation_valid", receipt.success))
            or not current(receipt)
            or inspection_superseded_by_later_observation(ledger, receipt)
            or str(receipt.payload.get("admissibility", "")) != "direct_admissible"
            or not receipt.payload.get("canonical_targets")
        ):
            return False

    for ref in bound:
        receipt = records.get(ref)
        if (
            receipt is None
            or not bool(receipt.payload.get("observation_valid", receipt.success))
            or not current(receipt)
            or inspection_superseded_by_later_observation(ledger, receipt)
        ):
            return False
        payload = receipt.payload
        if not payload.get("canonical_targets"):
            return False
        if str(payload.get("admissibility", "")) == "direct_admissible":
            # Preserve the original provenance law: every authoritative direct
            # input consumed by the command must also be declared in basis.
            if ref not in basis:
                return False
            continue
        fixture_input = (
            str(payload.get("route_kind", "")) == "overlay_write_fixture"
            and str(payload.get("admissibility", "")) == "exploratory"
            and str(payload.get("execution_scope", "")) == "verifier_overlay"
            and str(payload.get("requester", "")) == "model_verifier"
        )
        if not fixture_input:
            return False
    return True


def inspection_route_kinds_from_results(
    results: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    routes: dict[str, str] = {}
    for row in results:
        inspection_id = str(row.get("inspection_id", "")).strip()
        route_kind = str(row.get("kind", "")).strip()
        if inspection_id:
            routes[inspection_id] = route_kind
    return routes


def inspection_ceilings_from_results(results: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    ceilings: dict[str, str] = {}
    for row in results:
        inspection_id = str(row.get("inspection_id", "")).strip()
        ceiling = str(row.get("evidence_ceiling", "")).strip()
        if inspection_id:
            ceilings[inspection_id] = ceiling
    return ceilings


def inspection_actual_classes_from_results(
    results: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    """Return kernel-derived actual evidence classes by registered inspection ID."""
    classes: dict[str, str] = {}
    for row in results:
        inspection_id = str(row.get("inspection_id", "")).strip()
        actual = str(row.get("actual_evidence_class", "")).strip()
        if inspection_id and actual:
            classes[inspection_id] = actual
    return classes


def admissible_verdict_refs(
    ledger: ExecutionLedger,
    *,
    task_facts: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[set[str], set[str]]:
    """Return current direct and derived verdict-supporting inspection IDs.

    The check is provenance-only: receipt identity, ordering, freshness, and
    canonical-input continuity.  It never judges a parser or conclusion.
    """
    current_generation = int(ledger.task_state_generation())
    # Kept as an accepted argument for callers that retain packet facts in
    # their interface. V3 derived execution must bind kernel-issued direct
    # observations, never a prose task fact alone.
    del task_facts
    direct: set[str] = set()
    derived: set[str] = set()
    by_id: dict[str, Receipt] = {}
    for receipt in ledger.all_receipts():
        if receipt.kind != "inspection_record":
            continue
        payload = receipt.payload
        if not bool(payload.get("observation_valid", receipt.success)):
            continue
        if inspection_superseded_by_later_observation(ledger, receipt):
            continue
        inspection_id = str(payload.get("inspection_id", receipt.receipt_id)).strip()
        if not inspection_id:
            continue
        try:
            fresh = int(payload.get("task_state_generation")) == current_generation
        except (TypeError, ValueError):
            fresh = False
        admissibility = str(payload.get("admissibility", "")).strip()
        if not fresh or admissibility not in {"direct_admissible", "verdict_eligible"}:
            continue
        by_id[inspection_id] = receipt
        if admissibility == "direct_admissible":
            if bool(payload.get("eligible_for_proof", False)):
                direct.add(inspection_id)
            continue
        if admissibility == "verdict_eligible":
            derived.add(inspection_id)
    return direct, derived
