"""The narrow model boundary for the matched Thin Frontier comparator.

Thin is a projection of the existing PERSISTENT runtime, not a second runtime.  The
canonical compiler still owns the raw task, action schema, environment facts,
budgets, evidence custody, and provider-facing continuity.  This module only
removes incumbent completion-treatment state that cannot exist in a verifier-
free arm; it does not add planning, critique, recovery advice, or task hints.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Mapping

from .kernel_messages import build_solver_messages
from .glm_model_view import MODEL_VIEW_CONTROL, project_context_packet, project_prefix_messages
from .persistent_context import build_persistent_context
from .runtime_ir import CompiledRuntime, stable_json


THIN_CONTEXT_SCHEMA = "aether.thin_context.v1"
SOLVER_WORKING_CONTEXT_OFF = "off"
SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1 = "assistant_content_v1"
SOLVER_WORKING_CONTEXT_READ_INDEX_V1 = "read_index_v1"
SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1 = "tool_notes_v1"
SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1 = "tool_notes_grounded_v1"
SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1 = "read_index_tool_notes_v1"
SOLVER_WORKING_CONTEXT_READ_INDEX_MODES = frozenset({
    SOLVER_WORKING_CONTEXT_READ_INDEX_V1,
    SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1,
})
SOLVER_WORKING_CONTEXT_TOOL_NOTES_MODES = frozenset({
    SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1,
    SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1,
    SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1,
})
SOLVER_WORKING_CONTEXT_MODES = frozenset({
    SOLVER_WORKING_CONTEXT_OFF,
    SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1,
    *SOLVER_WORKING_CONTEXT_READ_INDEX_MODES,
    *SOLVER_WORKING_CONTEXT_TOOL_NOTES_MODES,
})
ASSISTANT_CONTENT_V1_GUIDANCE = (
    "[working_context]\n"
    "After a native tool call is admitted, only that latest assistant message (including its content, "
    "reasoning, and exact native tool call when present) and its matching latest tool result are carried "
    "into the next call. Text you put in your assistant message content alongside the tool call is kept "
    "verbatim for the next call and can hold anything you want to keep (goals, beliefs, failed approaches, "
    "evidence handles). Older results stay retrievable with query_history and read_output. This working "
    "note is fallible and non-authoritative: it must not override the raw task, tool contracts, current "
    "action results, or fresh reality; re-check its claims against current observations and retrieval."
)


_READ_INDEX_OBSERVATION_KINDS = frozenset({
    "read_file",
    "read_file_page",
    "read_output",
    "grep_output",
    "run_command",
    "terminal_read",
    "terminal_wait",
    "probe_job",
    "probe_service",
    "query_history",
    "query_artifact_history",
    "inspect_diff",
    "inspect_artifact",
})
_READ_INDEX_TARGET_FIELDS = (
    "path",
    "command",
    "handle",
    "source_receipt_id",
    "stream",
    "offset",
    "span",
    "query",
    "pattern",
    "mode",
    "timeout_s",
)
_READ_INDEX_RESULT_FIELDS = (
    "resolved_path",
    "file_handle",
    "stdout_handle",
    "stderr_handle",
    "exit_code",
    "timed_out",
    "more_available",
)
_READ_INDEX_SIZE_FIELDS = (
    "bytes",
    "stdout_bytes",
    "stderr_bytes",
    "returned_chars",
    "total_chars",
)
_READ_INDEX_HASH_FIELDS = (
    "content_sha256",
    "sha256",
    "file_sha256",
    "stdout_sha256",
    "stderr_sha256",
    "output_sha256",
    "artifact_hash",
    "command_sha256",
)


def working_context_uses_read_index(mode: str) -> bool:
    return str(mode or "").strip().lower() in SOLVER_WORKING_CONTEXT_READ_INDEX_MODES


def working_context_uses_tool_notes(mode: str) -> bool:
    return str(mode or "").strip().lower() in SOLVER_WORKING_CONTEXT_TOOL_NOTES_MODES


def build_factual_read_index(ledger: Any) -> dict[str, Any]:
    """Return a deduplicated factual observation index with no summaries or advice.

    Exact repeats update one mechanically keyed row rather than growing the
    prompt.  The key is derived only from the observation action target (for
    example path, command, or output handle), while result hashes/handles track
    the latest observed outcome.
    """
    entries: list[dict[str, Any]] = []
    index_by_key: dict[str, int] = {}
    for receipt in ledger.all_receipts():
        kind = str(getattr(receipt, "kind", "") or "")
        if kind not in _READ_INDEX_OBSERVATION_KINDS:
            continue
        raw_payload = getattr(receipt, "payload", {})
        payload = raw_payload if isinstance(raw_payload, Mapping) else {}
        target = {
            key: deepcopy(payload[key])
            for key in _READ_INDEX_TARGET_FIELDS
            if key in payload
            and isinstance(payload.get(key), (str, int, float, bool))
            and payload.get(key) != ""
        }
        index_key = kind + ":" + sha256(
            stable_json(target).encode("utf-8")
        ).hexdigest()
        step = int(getattr(receipt, "step", 0) or 0)
        row: dict[str, Any] = {
            "tool": kind,
            **target,
            "first_step": step,
            "last_step": step,
            "observation_count": 1,
            "success": bool(getattr(receipt, "success", False)),
            "receipt_handle": "receipt:" + str(getattr(receipt, "receipt_id", "") or ""),
            "observation_sha256": sha256(
                stable_json(dict(payload)).encode("utf-8")
            ).hexdigest(),
        }
        for key in _READ_INDEX_RESULT_FIELDS:
            value = payload.get(key)
            if isinstance(value, (str, int, float, bool)) and value != "":
                row[key] = deepcopy(value)
        for key in _READ_INDEX_SIZE_FIELDS:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                row[key] = value
        for key in _READ_INDEX_HASH_FIELDS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                row[key] = value
        existing = index_by_key.get(index_key)
        if existing is None:
            index_by_key[index_key] = len(entries)
            entries.append(row)
        else:
            previous = entries[existing]
            row["first_step"] = int(previous["first_step"])
            row["observation_count"] = int(previous["observation_count"]) + 1
            entries[existing] = row
    return {"schema": "aether.factual_read_index.v1", "entries": entries}

# These fields are produced for the incumbent's semantic/completion treatment
# path.  Thin never creates them and must not replay an injected value from a
# caller or a stale ledger.  All factual observations, aliases, handles,
# capability facts, history access, and hard budgets remain in the projection.
THIN_EXCLUDED_PACKET_KEYS = frozenset({
    "open_completion_findings",
    "submission_coherence",
    "submit_reentry_gate",
})

# The compiled prefix is shared byte-for-byte except for this incumbent-only
# instruction block.  The action schemas are not changed here.
THIN_EXCLUDED_PREFIX_SECTIONS = frozenset({"completion_controls"})


def _section_name(message: Mapping[str, Any]) -> str:
    content = str(message.get("content", ""))
    first_line, _separator, _body = content.partition("\n")
    if first_line.startswith("[") and first_line.endswith("]"):
        return first_line[1:-1]
    return ""


def thin_prefix_messages(compiled: CompiledRuntime) -> list[dict[str, str]]:
    """Return the incumbent prefix with only verifier/completion treatment removed.

    Raw task authority and its binding are generated by ``CompiledRuntime`` and
    are deliberately not reconstructed here.  Every remaining message is an
    unchanged compiler message, which makes this function a small, auditable
    adapter at the request boundary.
    """
    return [
        dict(message)
        for message in compiled.prefix_messages()
        if _section_name(message) not in THIN_EXCLUDED_PREFIX_SECTIONS
    ]


def _thin_linked_history(value: Any) -> Any:
    """Keep the factual linked-history projection without inventing a new view."""
    if not isinstance(value, Mapping):
        return deepcopy(value)
    # ``build_persistent_context`` already applies the factual projection.  The
    # allow-list is defense in depth for a caller that supplies a custom ledger
    # or an older packet shape.
    excluded = {
        "active_completion_findings",
        "open_completion_findings",
        "submission_recovery_directive",
        "verifier",
        "repair_instruction",
        "finding",
    }
    return {
        str(key): deepcopy(item)
        for key, item in value.items()
        if str(key) not in excluded
    }


def project_thin_context(
    packet: Mapping[str, Any], *, retain_completion_findings: bool = False,
) -> dict[str, Any]:
    """Project one canonical PERSISTENT packet onto Thin's factual/native surface.

    No content is summarized or ranked.  Missing fields remain missing, which
    preserves the runtime's fail-closed behavior instead of manufacturing a
    completion signal for the comparator.
    """
    excluded = set(THIN_EXCLUDED_PACKET_KEYS)
    if retain_completion_findings:
        excluded.discard("open_completion_findings")
    result = {
        str(key): deepcopy(value)
        for key, value in packet.items()
        if str(key) not in excluded
    }
    if "linked_history" in result:
        result["linked_history"] = _thin_linked_history(result["linked_history"])
    return result


def build_thin_context(
    compiled: CompiledRuntime,
    ledger: Any,
    alerts: list[Any],
    *,
    solver_working_context_mode: str = SOLVER_WORKING_CONTEXT_OFF,
    retain_completion_findings: bool = False,
) -> dict[str, Any]:
    """Build the Thin packet from the same canonical PERSISTENT authorities."""
    packet = project_thin_context(
        build_persistent_context(compiled, ledger, alerts),
        retain_completion_findings=retain_completion_findings,
    )
    if working_context_uses_read_index(solver_working_context_mode):
        packet = dict(packet)
        packet["read_index"] = build_factual_read_index(ledger)
    return packet


def build_thin_solver_messages(
    compiled: CompiledRuntime,
    context_packet: Mapping[str, Any],
    *,
    model_view_mode: str = MODEL_VIEW_CONTROL,
    solver_working_context_mode: str = SOLVER_WORKING_CONTEXT_OFF,
) -> list[dict[str, str]]:
    """Build the model-facing request from canonical Thin state.

    The selected projection applies only to serialization; callers retain and
    use ``context_packet`` for submission binding and execution validation.
    """
    messages = project_prefix_messages(thin_prefix_messages(compiled), model_view_mode)
    working_context_mode = str(
        solver_working_context_mode or SOLVER_WORKING_CONTEXT_OFF
    ).strip().lower()
    if working_context_mode not in SOLVER_WORKING_CONTEXT_MODES:
        raise ValueError(
            f"unsupported Solver working-context mode: {solver_working_context_mode}"
        )
    if working_context_mode == SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1:
        messages.append({"role": "system", "content": ASSISTANT_CONTENT_V1_GUIDANCE})
    visible_packet = project_context_packet(context_packet, model_view_mode)
    messages.append({
        "role": "system",
        "content": "[context_packet]\n" + json.dumps(
            visible_packet,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ),
    })
    return messages


def thin_action_schema(compiled: CompiledRuntime) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Expose the exact compiled action schema for equivalence assertions."""
    return tuple(
        (str(kind), tuple(str(argument) for argument in arguments))
        for kind, arguments in compiled.action_schema
    )


def thin_request_fingerprint(
    compiled: CompiledRuntime,
    context_packet: Mapping[str, Any],
) -> str:
    """Hash the exact model request for custody/equivalence artifacts."""
    payload = {
        "messages": build_thin_solver_messages(compiled, context_packet),
        "action_schema": thin_action_schema(compiled),
    }
    import hashlib

    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


__all__ = [
    "THIN_CONTEXT_SCHEMA",
    "THIN_EXCLUDED_PACKET_KEYS",
    "THIN_EXCLUDED_PREFIX_SECTIONS",
    "SOLVER_WORKING_CONTEXT_READ_INDEX_V1",
    "SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1",
    "SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1",
    "SOLVER_WORKING_CONTEXT_READ_INDEX_MODES",
    "SOLVER_WORKING_CONTEXT_TOOL_NOTES_MODES",
    "build_factual_read_index",
    "working_context_uses_read_index",
    "working_context_uses_tool_notes",
    "build_thin_context",
    "build_thin_solver_messages",
    "project_thin_context",
    "thin_action_schema",
    "thin_prefix_messages",
    "thin_request_fingerprint",
]
