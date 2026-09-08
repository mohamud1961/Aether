"""Hot/cold model projection for PCR Verifier packets.

The full immutable verifier packet remains the kernel/gate/evidence authority.
PCR models receive a smaller decision view containing task truth, current
state, the Primary claim, compact Did/Saw evidence indexes, unresolved
findings, and the handles needed to inspect current or cited evidence.
"""
from __future__ import annotations

from typing import Any, Mapping


def _plain(value: Any) -> Any:
    """Copy model-facing data without invoking frozen packet deepcopy hooks."""
    if isinstance(value, Mapping):
        return {str(key): _plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(child) for child in value]
    if isinstance(value, (set, frozenset)):
        return [_plain(child) for child in sorted(value, key=str)]
    return value


def _nonempty(value: Any) -> bool:
    return value not in (None, "", [], {}, ())


def _select(row: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: _plain(row[key]) for key in keys if key in row and _nonempty(row[key])}


def _project_finding(row: Mapping[str, Any]) -> dict[str, Any]:
    # Keep unresolved claim/evidence continuity, not the previous model's
    # prescriptive repair route. The new Verifier owns its falsification method.
    return _select(
        row,
        (
            "finding_id", "verdict", "priority", "status", "summary",
            "applies_to", "evidence", "supporting_inspection_ids",
        ),
    )


def _project_cited_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    projected = _select(
        row,
        (
            "receipt_id", "exact_receipt_handle", "kind", "success",
            "failure_class", "state_change", "evidence_role",
            "receipt_task_state_generation", "submission_task_state_generation",
        ),
    )
    payload = row.get("current_payload_projection", {})
    if isinstance(payload, Mapping):
        compact_payload = _select(
            payload,
            (
                "path", "file_handle", "bytes", "content_hash", "after_content_hash",
                "artifact_paths", "modified_paths", "removed_paths", "exit_code",
                "timed_out", "stdout_handle", "stderr_handle", "stdout_bytes",
                "stderr_bytes",
            ),
        )
        # F90: a path-based file handle names the live file, not the immutable
        # historical generation represented by a cited receipt.  Never present
        # that live navigation handle inside a historical-support row as though
        # it were snapshot identity; exact historical access uses the receipt
        # handle above.
        if str(row.get("evidence_role", "")).strip() == "historical_support":
            compact_payload.pop("file_handle", None)
        if compact_payload:
            projected["current_payload_projection"] = compact_payload
    return projected


def _project_primary_submission(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected = _select(value, ("claim", "task_state_generation", "evidence_bindings"))
    cited = value.get("cited_evidence", ())
    if isinstance(cited, (list, tuple)):
        rows = [_project_cited_evidence(row) for row in cited if isinstance(row, Mapping)]
        if rows:
            projected["cited_evidence_index"] = rows
    return projected


def _project_task_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    # authoritative_task_prompt already carries the raw prompt separately.
    # Keep exact clause IDs/text/atoms and any method constraints without
    # duplicating raw_task_prompt or custody hashes into model context.
    return _select(value, ("schema_version", "clauses", "method_constraints", "facts"))


def _project_open_obligations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    projected: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping):
            continue
        projected.append(
            _select(row, ("obligation_id", "kind", "status", "target", "evidence_ids"))
        )
    return projected


def _project_envmap(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    facts = value.get("facts", {})
    if not isinstance(facts, Mapping):
        return {}
    projected_facts = _select(
        facts,
        (
            "workspace_root", "network_scope", "resource_limits", "services",
            "permissions", "file_tree", "visible_files", "visible_dirs",
        ),
    )
    result: dict[str, Any] = {}
    if _nonempty(value.get("schema_version")):
        result["schema_version"] = _plain(value.get("schema_version"))
    if projected_facts:
        result["facts"] = projected_facts
    return result


def _cited_output_handles(primary_submission: Any) -> set[str]:
    handles: set[str] = set()
    if not isinstance(primary_submission, Mapping):
        return handles
    cited = primary_submission.get("cited_evidence", ())
    if not isinstance(cited, (list, tuple)):
        return handles
    for row in cited:
        if not isinstance(row, Mapping):
            continue
        payload = row.get("current_payload_projection", {})
        if not isinstance(payload, Mapping):
            continue
        for key in ("stdout_handle", "stderr_handle"):
            handle = str(payload.get(key, "") or "").strip()
            if handle:
                handles.add(handle)
    return handles


def _project_handles(value: Any, dynamic_state: Any, primary_submission: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    latest = dynamic_state.get("latest_result", {}) if isinstance(dynamic_state, Mapping) else {}
    hot_outputs = _cited_output_handles(primary_submission)
    for key in ("stdout_handle", "stderr_handle"):
        handle = str(latest.get(key, "") or "").strip() if isinstance(latest, Mapping) else ""
        if handle:
            hot_outputs.add(handle)

    projected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in value:
        if not isinstance(row, Mapping):
            continue
        kind = str(row.get("kind", "") or "").strip()
        handle = str(row.get("handle", "") or "").strip()
        path = str(row.get("path", "") or "").strip()
        if kind != "file" and handle not in hot_outputs:
            continue
        key = (kind, handle, path)
        if key in seen:
            continue
        seen.add(key)
        # A file:{path} handle is live navigation. Its byte/hash fields may
        # have originated from an older receipt for the same path and therefore
        # must not be presented as snapshot identity in PCR. Output handles are
        # immutable receipt-bound streams and retain their size/hash metadata.
        compact = _select(
            row,
            ("kind", "handle", "path")
            if kind == "file"
            else ("kind", "handle", "path", "stream", "bytes", "content_hash"),
        )
        if compact:
            projected.append(compact)
    return projected


def pcr_verifier_model_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact PCR model view without mutating full packet authority."""
    full = dict(packet)
    dynamic_state = full.get("dynamic_state", {})
    primary_submission = full.get("primary_submission", {})
    result: dict[str, Any] = {
        "schema_version": "pcr_verifier_model_view.v1",
        "step": _plain(full.get("step")),
        "reason": _plain(full.get("reason")),
        "task_contract": _project_task_contract(full.get("task_contract", {})),
        "open_obligations": _project_open_obligations(full.get("open_obligations", [])),
        "primary_submission": _project_primary_submission(primary_submission),
        "dynamic_state": _plain(dynamic_state),
        "stable_envmap": _project_envmap(full.get("stable_envmap", {})),
        "state_inspection_handles": _project_handles(
            full.get("state_inspection_handles", []), dynamic_state, primary_submission,
        ),
        # Mechanical namespace for the PCR-native rerun_check tool. Preserve
        # the field even when empty so the provider can distinguish "no
        # authoritative checks" from a malformed/missing projection.
        "authoritative_check_ids": _plain(full.get("authoritative_check_ids", [])),
        "active_findings": [
            _project_finding(row)
            for row in full.get("active_findings", ())
            if isinstance(row, Mapping)
        ],
        "evidence_requirements": _plain(full.get("evidence_requirements", {})),
    }
    # Preserve semantic/proof navigation if a future PCR profile activates it.
    for key in (
        "compiled_evidence_requirements", "compiled_proof_requirements",
        "proof_contract", "verification_task_facts", "raw_state_candidates",
    ):
        value = full.get(key)
        if _nonempty(value):
            result[key] = _plain(value)
    return result


def verifier_packet_for_model(compiled: Any, packet: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the single PCR Verifier model projection."""
    del compiled
    return pcr_verifier_model_packet(packet)
