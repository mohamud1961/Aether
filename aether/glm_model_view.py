"""Serialization-only projection for the Thin Solver's model-visible request.

The canonical context remains the authority for execution, submission binding,
and custody.  This module only removes named harness bookkeeping from the
serialized Solver request; it does not summarize or rank task evidence.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

MODEL_VIEW_CONTROL = "control"
MODEL_VIEW_HYGIENE_V1 = "hygiene_v1"
MODEL_VIEW_HYGIENE_LEAN_V1 = "hygiene_lean_v1"
MODEL_VIEW_MODES = frozenset({
    MODEL_VIEW_CONTROL,
    MODEL_VIEW_HYGIENE_V1,
    MODEL_VIEW_HYGIENE_LEAN_V1,
})

_HARNESS_ONLY_PREFIX_SECTIONS = frozenset({"raw_task_binding"})
_EMPTY_REFUSAL_BOUNDARY = "No local-only external-grading allowance compiled."
_EMPTY_ENVIRONMENT_PROBE = "{}"

_HARNESS_ONLY_PACKET_KEYS = frozenset({
    "runtime_identity",
    "task_state_generation",
    "task_state_snapshot_digest",
    "task_state_snapshot_known",
    "snapshot_binding_version",
    "task_state_snapshot_authority",
    "context_projection",
    "context_budget",
})
_ROW_IDENTITY_KEYS = frozenset({"task_id", "run_id", "workspace_id"})
_HARNESS_ONLY_FACT_KINDS = frozenset({"source_custody_gap"})
_HARNESS_ONLY_LINKED_KEYS = frozenset({"persistent_context_boundary"})

# The section body is task-agnostic guidance.  Its former name carries the
# experiment designation, so hygiene mode gives it a neutral header only.
_NEUTRAL_SECTION_NAMES = {
    "solver_reasoning_treatment": "working_guidance",
    "solver_commitment_contract": "working_guidance",
    "solver_async_execution": "execution_guidance",
}


def normalize_model_view_mode(mode: str | None) -> str:
    normalized = str(mode or MODEL_VIEW_CONTROL).strip().lower()
    if normalized not in MODEL_VIEW_MODES:
        raise ValueError(f"unsupported solver model view mode: {mode!r}")
    return normalized


def _section(content: Any) -> tuple[str, str]:
    text = content if isinstance(content, str) else ""
    first, _separator, body = text.partition("\n")
    if first.startswith("[") and first.endswith("]"):
        return first[1:-1], body
    return "", text


def project_prefix_messages(
    messages: Sequence[Mapping[str, Any]], mode: str,
) -> list[dict[str, Any]]:
    """Project named harness-only sections without mutating compiler messages."""
    selected = normalize_model_view_mode(mode)
    if selected == MODEL_VIEW_CONTROL:
        return [dict(message) for message in messages]

    projected: list[dict[str, Any]] = []
    for source in messages:
        name, body = _section(source.get("content"))
        if name in _HARNESS_ONLY_PREFIX_SECTIONS:
            continue
        if name == "refusal_boundary" and body.strip() == _EMPTY_REFUSAL_BOUNDARY:
            continue
        if name == "environment_probe" and body.strip() == _EMPTY_ENVIRONMENT_PROBE:
            continue

        message = dict(source)
        neutral_name = _NEUTRAL_SECTION_NAMES.get(name)
        if neutral_name is not None:
            message["content"] = f"[{neutral_name}]\n{body}"
        projected.append(message)
    return projected


def _strip_row_identity(row: Any) -> Any:
    if not isinstance(row, Mapping):
        return deepcopy(row)
    return {
        str(key): deepcopy(value)
        for key, value in row.items()
        if str(key) not in _ROW_IDENTITY_KEYS
    }


def _strip_nested_row_identity(value: Any) -> Any:
    """Remove named harness identity keys at every level of a projected record."""
    if isinstance(value, Mapping):
        return {
            str(key): _strip_nested_row_identity(nested)
            for key, nested in value.items()
            if str(key) not in _ROW_IDENTITY_KEYS
        }
    if isinstance(value, list):
        return [_strip_nested_row_identity(item) for item in value]
    return deepcopy(value)


def _lean_exact_access(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    drop = {"sha256", "bytes", "retrieval", "handle", "related_handles"}
    out = {str(key): deepcopy(item) for key, item in value.items() if str(key) not in drop}
    handle = value.get("handle")
    if isinstance(handle, str) and handle:
        out["handle"] = handle
    related = value.get("related_handles")
    if isinstance(related, list) and related:
        out["related_handles"] = deepcopy(related)
    retrieval = value.get("retrieval")
    if isinstance(retrieval, Mapping):
        lean_retrieval: dict[str, Any] = {}
        for key, item in retrieval.items():
            if key == "action_kind" and item == "read_output":
                continue
            if key == "paging_supported" and isinstance(item, bool):
                continue
            if key == "arguments" and isinstance(item, Mapping):
                arguments = {str(arg_key): deepcopy(arg_value) for arg_key, arg_value in item.items()}
                if arguments.get("handle") == handle:
                    arguments.pop("handle", None)
                if arguments:
                    lean_retrieval[str(key)] = arguments
            else:
                lean_retrieval[str(key)] = deepcopy(item)
        if lean_retrieval:
            out["retrieval"] = lean_retrieval
    return out


_BOUNDED_VIEW_DUPLICATES = (
    ("receipt_id", "receipt_id"),
    ("step", "step"),
    ("success", "success"),
    ("kind", "evidence_type"),
)
_EVIDENCE_ALIAS_KEYS = (
    "evidence_ref", "receipt_id", "evidence_type", "currentness",
    "completion_evidence_eligible",
)


def _lean_row(row: Any) -> Any:
    """Remove only named row-envelope duplicates and preserve unknown fields."""
    if not isinstance(row, Mapping):
        return deepcopy(row)
    out = {str(key): deepcopy(value) for key, value in row.items()}
    bounded = out.get("bounded_view")
    if isinstance(bounded, Mapping):
        lean_bounded = dict(bounded)
        for inner, outer in _BOUNDED_VIEW_DUPLICATES:
            if inner in lean_bounded and outer in out and lean_bounded[inner] == out[outer]:
                lean_bounded.pop(inner)
        if out.get("mechanical_description") == lean_bounded.get("summary"):
            out.pop("mechanical_description", None)
        out["bounded_view"] = lean_bounded
    access = _lean_exact_access(out.get("exact_access"))
    if access:
        out["exact_access"] = access
    else:
        out.pop("exact_access", None)
    related = out.get("related_handles")
    if isinstance(related, list) and related == access.get("related_handles"):
        out.pop("related_handles", None)
    elif isinstance(related, list) and not related:
        out.pop("related_handles", None)
    return out


def _lean_packet(packet: dict[str, Any]) -> dict[str, Any]:
    latest = packet.get("latest_primary_result")
    latest_rows_by_id: dict[str, Any] = {}
    if isinstance(latest, Mapping):
        lean_latest = {str(key): deepcopy(value) for key, value in latest.items()}
        if not lean_latest.get("missing_outcome_receipt_ids"):
            lean_latest.pop("missing_outcome_receipt_ids", None)
        rows = lean_latest.get("outcome_receipts")
        if isinstance(rows, list):
            row_receipt_ids = {
                str(row.get("receipt_id") or "")
                for row in rows if isinstance(row, Mapping)
            }
            for row in rows:
                if isinstance(row, Mapping):
                    receipt_id = str(row.get("receipt_id") or "").strip()
                    if receipt_id:
                        latest_rows_by_id[receipt_id] = row
            lean_latest["outcome_receipts"] = [_lean_row(row) for row in rows]
            missing_ids = {
                str(item) for item in latest.get("missing_outcome_receipt_ids", ()) or ()
            }
            outcome_ids = latest.get("outcome_receipt_ids")
            if isinstance(outcome_ids, list) and set(map(str, outcome_ids)) <= (row_receipt_ids | missing_ids):
                # The complete rows or explicit missing-ID list already carry these IDs.
                lean_latest.pop("outcome_receipt_ids", None)
        packet["latest_primary_result"] = lean_latest
    evidence = packet.get("evidence_index")
    if isinstance(evidence, list):
        lean_rows: list[Any] = []
        for row in evidence:
            if isinstance(row, Mapping):
                receipt_id = str(row.get("receipt_id") or "").strip()
                latest_row = latest_rows_by_id.get(receipt_id)
                if latest_row is not None and _lean_row(row) == _lean_row(latest_row):
                    # The complete canonical row is already in latest_primary_result.
                    lean_rows.append({key: deepcopy(row[key]) for key in _EVIDENCE_ALIAS_KEYS if key in row})
                    continue
                lean_rows.append(_lean_row(row))
            else:
                lean_rows.append(_lean_row(row))
        packet["evidence_index"] = lean_rows
    return packet


def project_context_packet(
    packet: Mapping[str, Any], mode: str,
) -> Mapping[str, Any]:
    """Return a model-visible packet while preserving canonical input untouched.

    Only fields explicitly named as harness bookkeeping are removed. Unknown
    and task-world fields pass through unchanged so this projection cannot
    silently become a semantic summarizer.
    """
    selected = normalize_model_view_mode(mode)
    if selected == MODEL_VIEW_CONTROL:
        return packet

    out = {
        str(key): deepcopy(value)
        for key, value in packet.items()
        if str(key) not in _HARNESS_ONLY_PACKET_KEYS
    }

    facts = out.get("unresolved_runtime_facts")
    if isinstance(facts, list):
        kept_facts = [
            fact for fact in facts
            if not (
                isinstance(fact, Mapping)
                and fact.get("kind") in _HARNESS_ONLY_FACT_KINDS
            )
        ]
        if kept_facts:
            out["unresolved_runtime_facts"] = kept_facts
        else:
            out.pop("unresolved_runtime_facts")

    linked_history = out.get("linked_history")
    if isinstance(linked_history, Mapping):
        kept_linked = {
            key: value for key, value in linked_history.items()
            if key not in _HARNESS_ONLY_LINKED_KEYS
        }
        if kept_linked:
            out["linked_history"] = kept_linked
        else:
            out.pop("linked_history")

    evidence_index = out.get("evidence_index")
    if isinstance(evidence_index, list):
        out["evidence_index"] = [_strip_row_identity(row) for row in evidence_index]

    latest = out.get("latest_primary_result")
    if isinstance(latest, Mapping) and isinstance(latest.get("outcome_receipts"), list):
        latest_copy = dict(latest)
        latest_copy["outcome_receipts"] = [
            _strip_row_identity(row) for row in latest["outcome_receipts"]
        ]
        out["latest_primary_result"] = latest_copy

    completion_record = out.get("completion_record")
    if isinstance(completion_record, Mapping):
        projected_completion_record = _strip_nested_row_identity(completion_record)
        if "treatment_instruction" in projected_completion_record:
            projected_completion_record.pop("treatment_instruction", None)
        out["completion_record"] = projected_completion_record

    if selected == MODEL_VIEW_HYGIENE_LEAN_V1:
        out = _lean_packet(out)

    return out


def observation_payload(packet: Mapping[str, Any]) -> set[str]:
    """Collect exposed string facts except explicit access digests/boilerplate.

    Unknown string fields are included so this checker does not silently stop
    protecting newly added observation fields. Retrieval payloads are boilerplate
    only when their handles are represented elsewhere; nested handle fields still
    participate in the equivalence check.
    """
    found: set[str] = set()

    def walk(value: Any, path: tuple[Any, ...] = ()) -> None:
        if isinstance(value, Mapping):
            for nested_key, nested_value in value.items():
                key = str(nested_key)
                child_path = path + (key,)
                row_level_identity = (
                    (len(path) == 2 and path[0] == "evidence_index")
                    or (len(path) == 3 and path[0] == "latest_primary_result"
                        and path[1] == "outcome_receipts")
                )
                if row_level_identity and key in _ROW_IDENTITY_KEYS:
                    continue
                exact_access_path = (
                    (len(path) == 3 and path[0] == "evidence_index" and path[2] == "exact_access")
                    or (len(path) == 4 and path[0] == "latest_primary_result"
                        and path[1] == "outcome_receipts" and path[3] == "exact_access")
                )
                if exact_access_path and key in {"sha256", "bytes"}:
                    continue
                walk(nested_value, child_path)
        elif isinstance(value, list):
            for index, nested_value in enumerate(value):
                walk(nested_value, path + (index,))
        elif isinstance(value, str):
            parent = path[:-1]
            key = str(path[-1]) if path else ""
            exact_access_retrieval_path = (
                (len(parent) == 4 and parent[0] == "evidence_index"
                 and parent[2:] == ("exact_access", "retrieval"))
                or (len(parent) == 5 and parent[0] == "latest_primary_result"
                    and parent[1] == "outcome_receipts"
                    and parent[3:] == ("exact_access", "retrieval"))
            )
            if (
                exact_access_retrieval_path
                and key == "action_kind"
                and value == "read_output"
            ):
                return
            found.add(value)

    for key in ("latest_primary_result", "evidence_index"):
        walk(packet.get(key), (key,))
    return found


__all__ = [
    "MODEL_VIEW_CONTROL",
    "MODEL_VIEW_HYGIENE_V1",
    "MODEL_VIEW_HYGIENE_LEAN_V1",
    "MODEL_VIEW_MODES",
    "normalize_model_view_mode",
    "observation_payload",
    "project_context_packet",
    "project_prefix_messages",
]
