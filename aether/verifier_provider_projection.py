"""Provider-only projections for the PCR Verifier.

The execution ledger, Verifier packet, validation schema and raw model transcript
remain canonical and complete.  This module only builds smaller *views* for a
provider request.  Every reduction is mechanical and fail-closed: semantic
judgment remains with the Verifier model, while authority/evidence stays in the
kernel-owned records.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


class ProviderProjectionError(ValueError):
    pass


_REF_LIKE_KEYS = ("$dynamicRef", "$recursiveRef")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def projection_digest(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _decode_pointer_token(token: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(token):
        ch = token[i]
        if ch != "~":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(token) or token[i + 1] not in "01":
            raise ProviderProjectionError(f"invalid JSON Pointer escape: {token!r}")
        out.append("~" if token[i + 1] == "0" else "/")
        i += 2
    return "".join(out)


def _local_def_name(ref: Any) -> str | None:
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return None
    rest = ref[len("#/$defs/") :]
    if not rest:
        raise ProviderProjectionError("empty local $defs target")
    return _decode_pointer_token(rest.split("/", 1)[0])


def _collect_local_def_refs(node: Any, *, skip_defs_key: bool = False) -> set[str]:
    refs: set[str] = set()
    if isinstance(node, Mapping):
        for key in _REF_LIKE_KEYS:
            value = node.get(key)
            if isinstance(value, str) and value.startswith("#/$defs/"):
                raise ProviderProjectionError(f"unsupported local {key}: {value!r}")
        local = _local_def_name(node.get("$ref"))
        if local is not None:
            refs.add(local)
        for key, value in node.items():
            if key == "$defs" and skip_defs_key:
                continue
            refs.update(_collect_local_def_refs(value))
    elif isinstance(node, list):
        for value in node:
            refs.update(_collect_local_def_refs(value))
    return refs


def prune_unreachable_local_defs_for_provider(
    schema: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Deep-copy and remove only provably unreachable ordinary local ``$defs``."""
    original = deepcopy(dict(schema))
    candidate = deepcopy(dict(schema))
    before_bytes = len(canonical_json_bytes(original))
    before_digest = projection_digest(original)
    defs = candidate.get("$defs")
    if not isinstance(defs, dict):
        return candidate, {
            "status": "no_defs", "reachable": [], "removed": [],
            "before_bytes": before_bytes, "after_bytes": before_bytes,
            "bytes_saved": 0, "before_digest": before_digest,
            "after_digest": before_digest,
        }
    try:
        roots = _collect_local_def_refs(candidate, skip_defs_key=True)
        reachable: set[str] = set()
        stack = list(sorted(roots, reverse=True))
        while stack:
            name = stack.pop()
            if name in reachable:
                continue
            if name not in defs:
                raise ProviderProjectionError(f"missing local $defs target: {name!r}")
            reachable.add(name)
            for child in sorted(_collect_local_def_refs(defs[name]), reverse=True):
                if child not in reachable:
                    stack.append(child)
        removed = [name for name in defs if name not in reachable]
        candidate["$defs"] = {name: value for name, value in defs.items() if name in reachable}
        after_bytes = len(canonical_json_bytes(candidate))
        return candidate, {
            "status": "pruned", "reachable": sorted(reachable), "removed": removed,
            "before_bytes": before_bytes, "after_bytes": after_bytes,
            "bytes_saved": before_bytes - after_bytes,
            "before_digest": before_digest, "after_digest": projection_digest(candidate),
        }
    except ProviderProjectionError as exc:
        return original, {
            "status": "fail_closed_unpruned", "error": str(exc), "reachable": [],
            "removed": [], "before_bytes": before_bytes, "after_bytes": before_bytes,
            "bytes_saved": 0, "before_digest": before_digest,
            "after_digest": before_digest,
        }


def _message_copy(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise ProviderProjectionError("Verifier transcript contains a non-text/unknown message")
        copied.append({"role": str(role), "content": content})
    return copied


def _select(source: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {key: deepcopy(source[key]) for key in keys if key in source and source[key] not in (None, "", [], {}, ())}


def _compact_cited_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Project only historical receipts that can actually be replayed exactly.

    Current anchors and ordinary Solver citations are claims for the independent
    Verifier to re-observe, not provider capabilities.  The only citation shape
    the PCR provider can expose is an immutable successful historical read_file
    with captured content identity and a strictly older task generation.
    """
    if str(row.get("evidence_role") or "").strip() != "historical_support":
        return None
    if str(row.get("kind") or "").strip() != "read_file" or row.get("success") is not True:
        return None
    receipt_id = str(row.get("receipt_id") or "").strip()
    handle = str(row.get("exact_receipt_handle") or "").strip()
    if not receipt_id or handle != f"receipt:{receipt_id}":
        return None
    payload = row.get("current_payload_projection")
    if not isinstance(payload, Mapping):
        return None
    content_hash = str(payload.get("content_hash") or "").strip().lower()
    if not content_hash or any(ch not in "0123456789abcdef" for ch in content_hash):
        return None
    try:
        receipt_generation = int(row.get("receipt_task_state_generation"))
        submission_generation = int(row.get("submission_task_state_generation"))
    except (TypeError, ValueError):
        return None
    if receipt_generation >= submission_generation:
        return None
    out = _select(row, (
        "receipt_id", "exact_receipt_handle", "kind", "success", "evidence_role",
        "receipt_task_state_generation", "submission_task_state_generation",
    ))
    out["current_payload_projection"] = _select(payload, ("content_hash", "bytes", "path"))
    return out


def _compact_initial_payload(initial: Mapping[str, Any]) -> dict[str, Any]:
    """Remove duplicated/cold machine state from the repeated provider authority view.

    Raw task text, task-clause identity/text, Primary claim identity, inspectable
    handles, historical receipt capability, unresolved findings and evidence
    requirements are retained.  Current dynamic state is *not* asserted from a
    Solver packet to an independent reviewer; the reviewer has typed live
    inspection routes for current reality.
    """
    out: dict[str, Any] = {}
    # Keep the exact raw task as semantic authority.
    if "authoritative_task_prompt" in initial:
        out["authoritative_task_prompt"] = deepcopy(initial["authoritative_task_prompt"])
    packet = initial.get("verifier_packet")
    if not isinstance(packet, Mapping):
        raise ProviderProjectionError("initial Verifier payload lacks verifier_packet")
    projected: dict[str, Any] = {}
    for key in (
        "task_contract", "open_obligations", "authoritative_check_ids",
        "active_findings", "evidence_requirements", "compiled_evidence_requirements",
        "compiled_proof_requirements", "proof_contract", "verification_task_facts",
        "raw_state_candidates",
    ):
        value = packet.get(key)
        if value not in (None, "", [], {}, ()) or key == "authoritative_check_ids":
            projected[key] = deepcopy(value)

    handles = packet.get("state_inspection_handles")
    if isinstance(handles, list):
        files: dict[str, dict[str, Any]] = {}
        outputs: dict[str, dict[str, Any]] = {}
        for row in handles:
            if not isinstance(row, Mapping):
                continue
            kind = str(row.get("kind") or "").strip()
            if kind == "file":
                path = str(row.get("path") or "").strip()
                if path:
                    files[path] = {"kind": "file", "path": path}
            elif kind == "output":
                handle = str(row.get("handle") or "").strip()
                if handle:
                    compact = {"kind": "output", "handle": handle}
                    stream = str(row.get("stream") or "").strip()
                    if stream:
                        compact["stream"] = stream
                    outputs[handle] = compact
        projected["state_inspection_handles"] = [*files.values(), *outputs.values()]
    primary = packet.get("primary_submission")
    if isinstance(primary, Mapping):
        # Candidate generation is review authority. Solver-authored completion
        # prose is not: the independent Verifier judges the raw task and current
        # state. Preserve only generation plus replayable immutable historical
        # reads as navigation.
        p = _select(primary, ("task_state_generation",))
        cited = primary.get("cited_evidence_index")
        if isinstance(cited, list):
            rows = [
                compact
                for row in cited
                if isinstance(row, Mapping)
                for compact in (_compact_cited_row(row),)
                if compact is not None
            ]
            if rows:
                p["cited_evidence_index"] = rows
        projected["primary_submission"] = p
    # Workspace root, overlay/network semantics, call limits and direct batch
    # cardinality are fixed by the PCR protocol/tool boundary and enforced by
    # the host. Repeating them here is machine narration, not task evidence.
    out["verifier_packet"] = projected
    return out


# Fields that remain model-relevant after an inspection. They are copied
# exactly, never summarized. Unknown non-empty fields do not become authority;
# the canonical receipt remains retrievable/custodied outside this view.
_EVIDENCE_FIELDS = (
    "inspection_id", "kind", "path", "handle", "target", "check_id",
    "receipt_kind", "error", "observation_valid", "excerpt",
    "stdout", "stderr", "exit_code", "timed_out", "success", "bytes",
    "content_hash", "stdout_bytes", "stderr_bytes", "total_chars", "offset",
    "returned_chars", "next_offset", "snapshot_verified", "snapshot_complete",
    "more_available", "eligible_for_basis", "eligible_for_proof", "admissibility",
    "actual_evidence_class", "evidence_ceiling", "actual_evidence_reason",
    "observation_origin", "target_generation", "observed_task_state_generation",
    "observed_http_status", "observed_outcome_success", "result_hash",
    "target_binding_valid", "method_domain_status", "method_domain_dependencies",
    "method_domain_missing", "method_domain_reason", "independent_isolation_verified",
    "isolation_cleanup_verified", "network_scope", "command_sha256",
)


def _compact_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the exact model-authored operation needed to interpret its observation."""
    return _select(request, (
        "kind", "path", "handle", "check_id", "receipt_kind", "limit", "target",
        "offset", "span", "content", "clause_ids", "proof_ids", "verification_plan",
        "execution",
    ))


def _compact_result(row: Mapping[str, Any], request: Mapping[str, Any] | None) -> dict[str, Any]:
    out = _select(row, _EVIDENCE_FIELDS)
    inspection_id = str(row.get("inspection_id") or "").strip()
    if not inspection_id:
        raise ProviderProjectionError("inspection result lacks inspection_id")
    out["inspection_id"] = inspection_id
    if request is not None:
        kind = str(request.get("kind") or row.get("kind") or "").strip()
        if kind in {"overlay_run_command", "rerun_check", "overlay_write_fixture"}:
            # Preserve the Verifier-authored derived method/command so the
            # observation and later method-validity judgment remain auditable.
            compact_request = _compact_request(request)
        else:
            # A direct result already carries its exact kind and locator. Only
            # clause/proof bindings add information not present in the result.
            compact_request = _select(request, ("clause_ids", "proof_ids"))
        if compact_request:
            out["requested"] = compact_request
    return out


def _parse_inspection_requests(assistant_content: str | None) -> list[dict[str, Any]]:
    if not assistant_content:
        return []
    try:
        payload = json.loads(assistant_content)
    except Exception:
        return []
    if not isinstance(payload, Mapping) or payload.get("kind") != "inspect":
        return []
    rows = payload.get("requests")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        return []
    return [dict(row) for row in rows]


def _projection_audit(before: list[dict[str, str]], after: list[dict[str, str]], *, status: str,
                      inspection_count: int = 0, error: str | None = None) -> dict[str, Any]:
    before_bytes = len(canonical_json_bytes(before)); after_bytes = len(canonical_json_bytes(after))
    row: dict[str, Any] = {
        "status": status, "before_message_count": len(before), "after_message_count": len(after),
        "registered_inspection_count": inspection_count, "before_bytes": before_bytes,
        "after_bytes": after_bytes, "bytes_saved": before_bytes - after_bytes,
        "before_digest": projection_digest(before), "after_digest": projection_digest(after),
    }
    if error: row["error"] = error
    return row


def compact_verifier_messages_for_provider(
    messages: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Build a fresh compact provider view from canonical Verifier dialogue."""
    try:
        original = _message_copy(messages)
    except ProviderProjectionError as exc:
        raw = [dict(m) for m in messages]
        return raw, {"status": "fail_closed_original", "error": str(exc),
                     "before_message_count": len(raw), "after_message_count": len(raw),
                     "registered_inspection_count": 0}
    if not original:
        return original, _projection_audit(original, original, status="empty")
    if len(original) < 2 or original[0]["role"] != "system" or original[1]["role"] != "user":
        return original, _projection_audit(original, original, status="fail_closed_original",
                                            error="Verifier authority prefix is not system,user")
    try:
        initial = json.loads(original[1]["content"])
        if not isinstance(initial, Mapping):
            raise ProviderProjectionError("initial Verifier user payload is not an object")
        initial_compact = _compact_initial_payload(initial)
        compact_prefix = [
            original[0],
            {"role": "user", "content": json.dumps(initial_compact, default=str, sort_keys=True)},
        ]
        if len(original) == 2:
            return compact_prefix, _projection_audit(original, compact_prefix, status="authority_compacted")

        by_id: dict[str, dict[str, Any]] = {}
        latest_authoritative: list[str] | None = None
        latest_bound: list[str] | None = None
        latest_instruction: Any = None
        latest_user_index: int | None = None
        latest_user_payload: dict[str, Any] | None = None
        prior_assistant_content: str | None = None
        latest_correction_assistant: dict[str, str] | None = None

        for index, message in enumerate(original[2:], start=2):
            if message["role"] == "assistant":
                prior_assistant_content = message["content"]
                continue
            if message["role"] != "user":
                continue
            latest_user_index = index
            try:
                payload = json.loads(message["content"])
            except Exception as exc:
                raise ProviderProjectionError(f"post-authority user message {index} is not JSON") from exc
            if not isinstance(payload, dict):
                raise ProviderProjectionError(f"post-authority user message {index} is not an object")
            latest_user_payload = payload
            requests = _parse_inspection_requests(prior_assistant_content)
            results = payload.get("verifier_inspection_results")
            if results is not None:
                if not isinstance(results, list):
                    raise ProviderProjectionError("verifier_inspection_results must be a list")
                if requests and len(requests) != len(results):
                    raise ProviderProjectionError("inspection request/result cardinality mismatch")
                for result_index, row in enumerate(results):
                    if not isinstance(row, Mapping):
                        raise ProviderProjectionError("inspection result must be an object")
                    request = requests[result_index] if requests else None
                    exact = _compact_result(row, request)
                    inspection_id = exact["inspection_id"]
                    prior = by_id.get(inspection_id)
                    if prior is not None and canonical_json_bytes(prior) != canonical_json_bytes(exact):
                        raise ProviderProjectionError(f"conflicting duplicate inspection_id: {inspection_id}")
                    by_id[inspection_id] = exact
                latest_instruction = payload.get("instruction")
            else:
                # This is a protocol/record correction. Keep the immediately
                # preceding model output so the correction has an exact referent.
                if prior_assistant_content is not None:
                    latest_correction_assistant = {"role": "assistant", "content": prior_assistant_content}
            for key, target in (("available_authoritative_source_refs", "a"),
                                ("available_bound_input_refs", "b")):
                if key not in payload: continue
                values = payload[key]
                if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                    raise ProviderProjectionError(f"{key} must be non-empty strings")
                normalized = [v.strip() for v in values]
                if len(normalized) != len(set(normalized)):
                    raise ProviderProjectionError(f"{key} contains duplicates")
                previous = latest_authoritative if target == "a" else latest_bound
                if previous is not None and not set(previous).issubset(normalized):
                    raise ProviderProjectionError(f"{key} regressed")
                if target == "a": latest_authoritative = normalized
                else: latest_bound = normalized
            prior_assistant_content = None
        if latest_authoritative is not None and latest_bound is not None and not set(latest_authoritative).issubset(latest_bound):
            raise ProviderProjectionError("authoritative refs are not contained in bound-input refs")
        if latest_user_index is None:
            return original, _projection_audit(original, original, status="no_host_state_to_compact")

        compact = list(compact_prefix)
        evidence: dict[str, Any] = {}
        if by_id:
            # Keep the established host-authored observation key so both the
            # Verifier prompt and provider namespace extraction consume one
            # exact evidence representation rather than duplicated aliases.
            evidence["verifier_inspection_results"] = [by_id[key] for key in sorted(by_id)]
        if latest_authoritative is not None: evidence["available_authoritative_source_refs"] = latest_authoritative
        if latest_bound is not None: evidence["available_bound_input_refs"] = latest_bound
        latest_is_inspection = bool(latest_user_payload and "verifier_inspection_results" in latest_user_payload)
        if latest_is_inspection:
            if latest_instruction is not None: evidence["instruction"] = deepcopy(latest_instruction)
            compact.append({"role": "user", "content": json.dumps(evidence, default=str, sort_keys=True)})
        else:
            if evidence:
                compact.append({"role": "user", "content": json.dumps(evidence, default=str, sort_keys=True)})
            if latest_correction_assistant is not None: compact.append(latest_correction_assistant)
            compact.append(original[latest_user_index])
        return compact, _projection_audit(original, compact, status="compacted",
                                            inspection_count=len(by_id))
    except (ProviderProjectionError, json.JSONDecodeError) as exc:
        return original, _projection_audit(original, original, status="fail_closed_original", error=str(exc))
