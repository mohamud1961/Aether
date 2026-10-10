"""Bounded Chat Completions provider for model-hook and PERSISTENT execution.

The adapter deliberately speaks the ordinary Chat Completions protocol.  It
does not carry Responses response IDs between turns: every continuation is an
explicit ``system``/``developer``/``user``/``assistant``/``tool`` transcript
supplied by :class:`aether.model_hooks.ModelHooks`.

The provider boundary is strict.  One choice is required, truncation is an
error, and a PERSISTENT call must contain exactly one canonical native function call.
The transport is injectable so protocol qualification can use a deterministic
mock without reading credentials or contacting a provider.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import urlparse

from ..model_profile import ModelProfile, PRODUCTION_PROFILE, require_provider_authorization
from .. import managed_context_checkpoint as _managed_context
from . import capacity_checkpoint as _capckpt
from ..persistent_provider_protocol import (
    PERSISTENT_CHAT_PROVIDER_TOOLS,
    PERSISTENT_CHAT_PROVIDER_TOOLS_COMMITMENT_V1,
    PERSISTENT_CHAT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1,
    PERSISTENT_CHAT_PROVIDER_TOOLS_COMMITMENT_AND_DISPOSITION_V1,
    PERSISTENT_CHAT_STATIC_TOOL_KERNEL_V1_NAMES,
    PERSISTENT_CHAT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES,
    PERSISTENT_STATIC_TOOL_KERNEL_V1_NAMES,
    PERSISTENT_TOOL_SURFACE_CONTROL,
    PERSISTENT_TOOL_SURFACE_MODES,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_JOBS_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1,
    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1,
    PERSISTENT_CHAT_STATIC_TOOL_KERNEL_EDIT_V1_NAMES,
    persistent_chat_edit_file_tool,
    persistent_flat_tool_parameters,
    persistent_chat_background_job_tools,
    PERSISTENT_SHELL_SENTENCE,
    PCRProviderProtocolError,
    canonicalize_persistent_direct_tool_call,
    with_finish_completion_card,
)
from ..tolerant_arguments import recover_argument_object
from ..history_lean import (
    LEAN_V1 as HISTORY_LEAN_V1, project_history_lean, resolve_history_mode, stable_packet_content,
)
from ..long_command_mode import LONG_COMMAND_BACKGROUND_V1, selected_long_command_mode
from ..session_affinity import (
    SESSION_AFFINITY_KEY_ENV, key_sha256_12, merge_affinity_headers, session_affinity_key_from_env,
)
from ..provider_budget import ProviderBudgetError, ProviderBudgetGuard, provider_budget_guard_from_env
from ..provider_pacing import ProviderThroughputError, SerialTokenPacer, SharedDeploymentTokenPacer
from ..run_cancellation import RunCancellationRequested, raise_if_run_cancelled
from ..run_deadline import (KernelRunTimeout, raise_if_run_deadline_exceeded, remaining_run_s, run_deadline_excluded_wait)
from .chat_stream import (
    DEFAULT_STREAM_IDLE_TIMEOUT_S,
    STREAM_OPTIONS,
    ChatStreamDeadline,
    collect_chat_stream,
)

_COMPLETION_RECORD_ACTION = "update_completion_record"
_FINISH_INTENT = "finish_intent"
_FINISH = "finish"

_CHAT_TELEMETRY_JOURNAL_ENV = "AETHER_CHAT_TELEMETRY_JOURNAL"
_CHAT_TELEMETRY_JOURNAL_LOCK = threading.Lock()


def _append_chat_telemetry_journal(event: Mapping[str, Any]) -> None:
    """Durably persist exact Chat attempt telemetry when explicit custody enables it.

    The event already contains the provider request/response payloads, usage and
    action receipt metadata used by normal in-memory telemetry. This durable
    projection removes header maps and exception-message strings; scalar
    request IDs and safe error types/status codes remain. A configured journal
    is strict: losing an attempt after a paid provider call is an evidence
    failure, not something to ignore silently.
    """
    raw_path = str(os.environ.get(_CHAT_TELEMETRY_JOURNAL_ENV, "") or "").strip()
    if not raw_path:
        return
    attempt = deepcopy(dict(event))
    def sanitize(value: Any) -> Any:
        if isinstance(value, Mapping):
            safe: dict[str, Any] = {}
            for raw_key, item in value.items():
                key = str(raw_key)
                lowered = key.lower()
                if (
                    lowered in {"error", "error_message", "error_description"}
                    or lowered.endswith("_error")
                    or ("headers" in lowered and not lowered.endswith("_headers_recorded"))
                ):
                    continue
                safe[key] = sanitize(item)
            return safe
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [sanitize(item) for item in value]
        return value

    attempt = sanitize(attempt)
    payload = {
        "schema_version": "aether.chat_provider_attempt_journal.v1",
        "event_kind": "chat_provider_attempt_journal",
        "persisted_at_unix_s": time.time(),
        "attempt": attempt,
    }
    line = (
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            default=str,
        )
        + "\n"
    ).encode("utf-8")
    parent = os.path.dirname(os.path.abspath(raw_path))
    try:
        os.makedirs(parent, exist_ok=True)
        with _CHAT_TELEMETRY_JOURNAL_LOCK:
            fd = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
    except Exception as exc:
        raise ChatModelError(
            f"chat telemetry journal write failed: {type(exc).__name__}: {exc}"
        ) from exc

_CAPACITY_REANCHOR_RECOVERY_OFF = "off"
_CAPACITY_REANCHOR_RECENT_OBSERVATIONS_V1 = "recent_observations_v1"
_CAPACITY_REANCHOR_RECENT_EXCHANGES_V1 = "recent_exchanges_v1"
_CAPACITY_REANCHOR_CHECKPOINT_AT_CAPACITY_V1 = _capckpt.CHECKPOINT_AT_CAPACITY_V1
_CAPACITY_REANCHOR_RECOVERY_MODES = frozenset({
    _CAPACITY_REANCHOR_RECOVERY_OFF,
    _CAPACITY_REANCHOR_RECENT_OBSERVATIONS_V1,
    _CAPACITY_REANCHOR_RECENT_EXCHANGES_V1,
    _CAPACITY_REANCHOR_CHECKPOINT_AT_CAPACITY_V1,
})
from ..context_file.tools import CONTEXT_FILE_MODES as _CONTEXT_FILE_SCOPE_MODES
from ..context_file.tools import surface_tools as _context_file_surface

_CAPACITY_OVERFLOW_REANCHOR = "reanchor"
_CAPACITY_OVERFLOW_M_TREE_EPOCH = "m_tree_epoch_overflow"
_CAPACITY_OVERFLOW_CONTEXT_FILE = "managed_context_context_overflow"
_CAPACITY_OVERFLOW_ACTIONS = frozenset({
    _CAPACITY_OVERFLOW_REANCHOR,
    _CAPACITY_OVERFLOW_M_TREE_EPOCH,
    _CAPACITY_OVERFLOW_CONTEXT_FILE,
})
# Modes that seed the post-reanchor history with the last exact exchanges.
_CAPACITY_REANCHOR_EXCHANGE_SEED_MODES = frozenset({
    _CAPACITY_REANCHOR_RECENT_EXCHANGES_V1,
    _CAPACITY_REANCHOR_CHECKPOINT_AT_CAPACITY_V1,
})
_CAPACITY_RECOVERY_PREFIX = "[continuity_reanchor_observations]\n"
_CONTEXT_PACKET_PREFIX = "[context_packet]\n"
_CAPACITY_RECOVERY_MAX_ITEMS = 5
# Ceiling for the one-shot doubled output cap after a length truncation.
_MAX_ESCALATED_OUTPUT_TOKENS = 65536
_CAPACITY_RECOVERY_MAX_ITEM_BYTES = 4096
_CAPACITY_RECOVERY_MAX_CONTENT_BYTES = 8192
_CAPACITY_RECENT_EXCHANGE_COUNT = 4
_TRANSPORT_FULL_SNAPSHOT = "full_snapshot_control"
_TRANSPORT_OBSERVATION_HISTORY_V1 = "observation_history_v1"
_TRANSPORT_LATEST_EXCHANGE_V1 = "latest_exchange_v1"
_TRANSPORT_REASONING_ACTIONS_NO_RESULTS_V1 = "reasoning_actions_no_results_v1"
_TRANSPORT_REASONING_LATEST_ACTION_NO_RESULTS_V1 = "reasoning_latest_action_no_results_v1"
_TRANSPORT_ACTIONS_RESULTS_NO_REASONING_V1 = "actions_results_no_reasoning_v1"
_HISTORICAL_RESULT_OMITTED_PREFIX = "[historical_result_omitted]\n"
_SOLVER_WORKING_CONTEXT_OFF = "off"
_SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1 = "assistant_content_v1"
_SOLVER_WORKING_CONTEXT_READ_INDEX_V1 = "read_index_v1"
_SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1 = "tool_notes_v1"
_SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1 = "tool_notes_grounded_v1"
_SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1 = "read_index_tool_notes_v1"
_SOLVER_WORKING_CONTEXT_TOOL_NOTES_MODES = frozenset({
    _SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1,
    _SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1,
    _SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1,
})
_SOLVER_WORKING_CONTEXT_MODES = frozenset({
    _SOLVER_WORKING_CONTEXT_OFF,
    _SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1,
    _SOLVER_WORKING_CONTEXT_READ_INDEX_V1,
    _SOLVER_WORKING_CONTEXT_TOOL_NOTES_V1,
    _SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1,
    _SOLVER_WORKING_CONTEXT_READ_INDEX_TOOL_NOTES_V1,
})
_CHAT_TRANSPORT_MODES = frozenset({
    _TRANSPORT_FULL_SNAPSHOT,
    _TRANSPORT_OBSERVATION_HISTORY_V1,
    _TRANSPORT_LATEST_EXCHANGE_V1,
    _TRANSPORT_REASONING_ACTIONS_NO_RESULTS_V1,
    _TRANSPORT_REASONING_LATEST_ACTION_NO_RESULTS_V1,
    _TRANSPORT_ACTIONS_RESULTS_NO_REASONING_V1,
})
_HISTORY_PROJECTION_MARKER = "observation_only_v1"


class ChatModelError(RuntimeError):
    """A Chat Completions transport or request failure."""


class ChatModelOutputError(ChatModelError):
    """A provider response cannot authorize one unambiguous model turn."""

    is_provider_output_error = True

    def __init__(
        self,
        code: str,
        detail: str = "",
        *,
        rejected_tool_name: str = "",
        rejected_tool_arguments: str = "",
        reasoning_content: str = "",
        output_tokens: int | None = None,
    ) -> None:
        self.code = str(code)
        self.detail = str(detail)
        # Inert evidence from a cap-truncated turn (never executable).
        self.reasoning_content = str(reasoning_content or "")
        self.output_tokens = output_tokens
        # Inert provider evidence for one bounded same-step format repair.
        # This context is never executable and never authorizes an action.
        self.rejected_tool_name = str(rejected_tool_name or "")
        self.rejected_tool_arguments = str(rejected_tool_arguments or "")
        super().__init__(self.code if not detail else f"{self.code}: {detail}")


class ChatContextCapacityError(ChatModelError):
    """The harness-built request cannot fit the declared route capacity.

    This is a harness/context failure, never a provider or model failure.
    """


class ChatRouteIdentityError(ChatModelError):
    """A response violated the sealed route; Solver correction cannot repair it."""

    code = "provider_route_identity_mismatch"


class ChatCompletionsTransport(Protocol):
    def create(self, **request: Any) -> Any: ...


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _jsonable(value: Any) -> Any:
    """Serialize SDK and test objects without losing the captured shape."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    for method in ("model_dump", "to_dict"):
        convert = getattr(value, method, None)
        if callable(convert):
            try:
                return _jsonable(convert())
            except Exception:
                pass
    if hasattr(value, "__dict__"):
        return {
            str(k): _jsonable(v)
            for k, v in vars(value).items()
            if not str(k).startswith("_")
        }
    return str(value)


def _canonical_json(value: Any) -> tuple[Any, bytes]:
    payload = _jsonable(value)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return payload, encoded


def _usage_telemetry(response: Any) -> dict[str, Any]:
    """Normalize Chat Completions usage while preserving missing as unmeasured."""
    usage = _field(response, "usage")
    if usage is None:
        return {
            "usage_status": "omitted",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "cache_write_tokens": None,
            "reasoning_tokens": None,
        }
    input_details = _field(usage, "prompt_tokens_details", None)
    if input_details is None:
        input_details = _field(usage, "input_tokens_details", {})
    output_details = _field(usage, "completion_tokens_details", None)
    if output_details is None:
        output_details = _field(usage, "output_tokens_details", {})
    missing = object()
    cached = _field(input_details or {}, "cached_tokens", missing)
    cache_write = _field(input_details or {}, "cache_write_tokens", missing)
    reasoning = _field(output_details or {}, "reasoning_tokens", None)
    return {
        "usage_status": "reported",
        "cache_metrics_status": (
            "reported" if cached is not missing or cache_write is not missing else "unmeasured"
        ),
        "input_tokens": _field(usage, "prompt_tokens", _field(usage, "input_tokens")),
        "output_tokens": _field(usage, "completion_tokens", _field(usage, "output_tokens")),
        "total_tokens": _field(usage, "total_tokens"),
        "cached_input_tokens": None if cached is missing else cached,
        "cache_write_tokens": None if cache_write is missing else cache_write,
        "reasoning_tokens": reasoning,
    }


def _chat_tool(tool: Mapping[str, Any]) -> dict[str, Any]:
    """Translate canonical PERSISTENT tool shape to Chat's nested function shape."""
    if str(tool.get("type") or "") != "function":
        raise ValueError("Chat Completions tools must have type=function")
    if isinstance(tool.get("function"), Mapping):
        function = deepcopy(dict(tool["function"]))
    else:
        function = {
            key: deepcopy(tool[key])
            for key in ("name", "description", "parameters", "strict")
            if key in tool
        }
    if not function.get("name") or not isinstance(function.get("parameters"), Mapping):
        raise ValueError("Chat Completions function tool requires name and parameters")
    return {"type": "function", "function": function}


def _with_persistent_shell_sentence(tool: Mapping[str, Any]) -> Mapping[str, Any]:
    function = tool["function"]
    if function.get("name") != "run_command":
        return tool
    row = deepcopy(dict(tool))
    row["function"]["description"] = f"{function['description']} {PERSISTENT_SHELL_SENTENCE}"
    return row


def _working_context_uses_tool_notes(mode: str) -> bool:
    return str(mode or "").strip().lower() in _SOLVER_WORKING_CONTEXT_TOOL_NOTES_MODES


def _chat_tool_with_required_working_notes(
    tool: Mapping[str, Any],
    *,
    grounded: bool = False,
) -> dict[str, Any]:
    row = deepcopy(dict(tool))
    function = deepcopy(dict(row.get("function") or {}))
    parameters = deepcopy(dict(function.get("parameters") or {}))
    if parameters.get("type") != "object":
        raise ValueError("working-notes tool schema requires an object root")
    properties = deepcopy(dict(parameters.get("properties") or {}))
    required = [str(item) for item in (parameters.get("required") or ())]
    properties["working_notes"] = {
        "type": "string",
        "pattern": r"\S",
    }
    if grounded:
        properties["working_notes"]["description"] = (
            "Carry forward the decision-relevant working state for the next turn. "
            "Preserve exact public task requirements and verified facts you rely on; "
            "include the receipt/file/output handle that supports a verified fact when available. "
            "Keep hypotheses explicitly separate from verified facts. Record failed approaches "
            "that should not be repeated and the concrete next step. Update or retract a belief "
            "when new evidence contradicts it. A self-authored test can verify your implementation "
            "against that test, but it is not evidence of the public task contract unless grounded "
            "in public task files or observed task evidence."
        )
    if "working_notes" not in required:
        required.append("working_notes")
    parameters["properties"] = properties
    parameters["required"] = required
    function["parameters"] = parameters
    row["function"] = function
    return row


def _normalize_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Copy a complete Chat transcript, including assistant tool calls."""
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        raise TypeError("messages must be a sequence of message objects")
    result: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise TypeError(f"message {index} must be an object")
        role = str(message.get("role") or "")
        if role not in {"system", "developer", "user", "assistant", "tool"}:
            raise ValueError(f"unsupported Chat message role: {role!r}")
        row = deepcopy(dict(message))
        row["role"] = role
        if "content" not in row and role != "assistant":
            raise ValueError(f"message {index} has no content")
        # Do not flatten or discard tool_call_id/tool_calls/reasoning_content.
        result.append(row)
    if not result:
        raise ValueError("Chat Completions requires at least one message")
    return result


def _prefixed_json_object(message: Mapping[str, Any], prefix: str) -> dict[str, Any] | None:
    content = message.get("content")
    if not isinstance(content, str) or not content.startswith(prefix):
        return None
    try:
        value = json.loads(content[len(prefix):])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return dict(value) if isinstance(value, Mapping) else None




def _historical_observation_message(message: Mapping[str, Any]) -> dict[str, Any]:
    """Drop superseded state from a prior tool packet, keeping its observation."""
    packet = _prefixed_json_object(message, _CONTEXT_PACKET_PREFIX)
    if packet is None or message.get("role") != "tool":
        return dict(message)
    kept = {
        "latest_primary_result": packet.get("latest_primary_result", {}),
        "packet_history_projection": _HISTORY_PROJECTION_MARKER,
    }
    return {
        "role": "tool",
        "tool_call_id": message.get("tool_call_id"),
        "content": _CONTEXT_PACKET_PREFIX + json.dumps(
            kept, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ),
    }


def _historical_result_stub(message: Mapping[str, Any]) -> dict[str, Any]:
    """Replace one old tool result with exact retrieval handles only."""
    packet = _prefixed_json_object(message, _CONTEXT_PACKET_PREFIX)
    handles: list[str] = []
    if packet is not None:
        latest = packet.get("latest_primary_result")
        if isinstance(latest, Mapping):
            receipts = latest.get("outcome_receipts")
            if isinstance(receipts, list):
                for row in receipts:
                    if not isinstance(row, Mapping):
                        continue
                    receipt_id = str(row.get("receipt_id") or "").strip()
                    if receipt_id:
                        handles.append("receipt:" + receipt_id)
                    exact = row.get("exact_access")
                    if isinstance(exact, Mapping):
                        handle = str(exact.get("handle") or "").strip()
                        if handle:
                            handles.append(handle)
                        related = exact.get("related_handles")
                        if isinstance(related, list):
                            handles.extend(str(item).strip() for item in related if str(item).strip())
    deduped = list(dict.fromkeys(handles))
    payload = {
        "schema": "aether.historical_result_omitted.v1",
        "historical_results_are_current_state": False,
        "retrieval_actions": ["query_history", "read_output"],
        "retrieval_handles": deduped,
    }
    return {
        "role": "tool",
        "tool_call_id": message.get("tool_call_id"),
        "content": _HISTORICAL_RESULT_OMITTED_PREFIX + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ),
    }


def _reasoning_only_assistant(message: Mapping[str, Any]) -> dict[str, Any]:
    """Keep a historical assistant's own reasoning/content but drop its old action."""
    if message.get("role") != "assistant":
        return dict(message)
    row: dict[str, Any] = {"role": "assistant"}
    if "content" in message:
        row["content"] = deepcopy(message.get("content"))
    if "reasoning_content" in message:
        row["reasoning_content"] = deepcopy(message.get("reasoning_content"))
    return row


def _without_reasoning(message: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a historical assistant turn minus its reasoning; actions are untouched."""
    row = dict(message)
    if row.get("role") == "assistant":
        row.pop("reasoning_content", None)
    return row


def _compact_recovery_exact_access(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result = {
        key: deepcopy(value[key])
        for key in ("state", "handle", "sha256", "bytes")
        if value.get(key) not in (None, "")
    }
    related = value.get("related_handles")
    if isinstance(related, list) and related:
        result["related_handles"] = deepcopy(related)
    return result


def _compact_recovery_bounded_view(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    # Outer recovery item already carries receipt identity, step, evidence type,
    # and currentness-at-reanchor. Preserve the literal observation payload while
    # removing only duplicate envelope fields.
    return {
        str(key): deepcopy(item)
        for key, item in value.items()
        if str(key) not in {"receipt_id", "step", "kind", "success", "summary"}
    }


def _recovery_observation_origin(row: Mapping[str, Any]) -> str:
    """Return one deterministic dedupe locator without semantic interpretation."""
    bounded = row.get("bounded_view")
    if not isinstance(bounded, Mapping):
        bounded = {}
    path = str(bounded.get("path") or "").strip()
    if path:
        # A later observation/write of the same path supersedes an older copy
        # for recovery-memory purposes without asserting semantic relevance.
        return "path:" + path
    for key in ("handle", "file_handle", "stdout_handle", "stderr_handle", "target", "check_id"):
        value = str(bounded.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    command = str(bounded.get("command") or "").strip()
    if command:
        return "command_sha256:" + sha256(command.encode("utf-8")).hexdigest()
    return "receipt:" + str(row.get("receipt_id") or "").strip()


def _capacity_reanchor_recovery_message(
    history: Sequence[Mapping[str, Any]],
    fresh_messages: Sequence[Mapping[str, Any]],
    *,
    max_items: int = _CAPACITY_RECOVERY_MAX_ITEMS,
    max_item_bytes: int = _CAPACITY_RECOVERY_MAX_ITEM_BYTES,
    max_content_bytes: int = _CAPACITY_RECOVERY_MAX_CONTENT_BYTES,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Recover a tiny exact-observation workset when explicit Chat history is dropped.

    Selection is recency + exact locator deduplication only.  No assistant
    reasoning, semantic ranking, inferred importance, or new summary is added.
    An observation is eligible only while its receipt remains represented in
    the fresh PERSISTENT evidence index; the fresh packet supplies the currentness
    label and task-state generation.
    """
    fresh_packet: dict[str, Any] | None = None
    for message in reversed(list(fresh_messages)):
        packet = _prefixed_json_object(message, _CONTEXT_PACKET_PREFIX)
        if packet is not None:
            fresh_packet = packet
            break
    if fresh_packet is None:
        return None, {"status": "no_fresh_context_packet", "selected_count": 0}

    current_rows = fresh_packet.get("evidence_index")
    if not isinstance(current_rows, list):
        return None, {"status": "no_fresh_evidence_index", "selected_count": 0}
    current_by_id = {
        str(row.get("receipt_id") or ""): row
        for row in current_rows
        if isinstance(row, Mapping) and str(row.get("receipt_id") or "").strip()
    }

    candidates: list[dict[str, Any]] = []
    for message in history:
        recovery = _prefixed_json_object(message, _CAPACITY_RECOVERY_PREFIX)
        if recovery is not None:
            items = recovery.get("items")
            if isinstance(items, list):
                candidates.extend(dict(row) for row in items if isinstance(row, Mapping))
            continue
        packet = _prefixed_json_object(message, _CONTEXT_PACKET_PREFIX)
        if packet is None:
            continue
        latest = packet.get("latest_primary_result")
        if not isinstance(latest, Mapping):
            continue
        rows = latest.get("outcome_receipts")
        if not isinstance(rows, list):
            continue
        candidates.extend(dict(row) for row in rows if isinstance(row, Mapping))

    selected: list[dict[str, Any]] = []
    seen_origins: set[str] = set()
    skipped_missing_current = 0
    skipped_oversize = 0
    skipped_content_cap = 0
    for candidate in reversed(candidates):
        if len(selected) >= max(0, int(max_items)):
            break
        receipt_id = str(candidate.get("receipt_id") or "").strip()
        current = current_by_id.get(receipt_id)
        if current is None:
            skipped_missing_current += 1
            continue
        bounded = candidate.get("bounded_view")
        if not isinstance(bounded, Mapping) or not bounded:
            continue
        if candidate.get("success") is False:
            continue
        origin = _recovery_observation_origin(candidate)
        if not origin or origin in seen_origins:
            continue
        item: dict[str, Any] = {}
        for key in (
            "receipt_id", "evidence_ref", "evidence_type", "step",
            "completion_evidence_eligible",
        ):
            if candidate.get(key) not in (None, "", [], {}):
                item[key] = deepcopy(candidate[key])
        exact_access = _compact_recovery_exact_access(candidate.get("exact_access"))
        if exact_access:
            item["exact_access"] = exact_access
        item["currentness_at_reanchor"] = deepcopy(current.get("currentness"))
        item["bounded_view"] = _compact_recovery_bounded_view(bounded)
        item_bytes = len(json.dumps(
            item, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
        ).encode("utf-8"))
        if item_bytes > max(1, int(max_item_bytes)):
            skipped_oversize += 1
            seen_origins.add(origin)
            continue

        tentative = [*selected, item]
        payload = {
            "schema": "aether.chat_continuity_reanchor_observations.v1",
            "authority": "previously_model_visible_execution_observation",
            "semantic_ranking": False,
            "historical_results_are_current_state": False,
            "task_state_generation_at_reanchor": fresh_packet.get("task_state_generation"),
            "items": tentative,
        }
        content = _CAPACITY_RECOVERY_PREFIX + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
        )
        if len(content.encode("utf-8")) > max(1, int(max_content_bytes)):
            skipped_content_cap += 1
            seen_origins.add(origin)
            continue
        selected.append(item)
        seen_origins.add(origin)

    meta = {
        "status": "selected" if selected else "empty",
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "selected_receipt_ids": [str(row.get("receipt_id") or "") for row in selected],
        "skipped_missing_current_count": skipped_missing_current,
        "skipped_oversize_count": skipped_oversize,
        "skipped_content_cap_count": skipped_content_cap,
        "max_items": int(max_items),
        "max_item_bytes": int(max_item_bytes),
        "max_content_bytes": int(max_content_bytes),
    }
    if not selected:
        return None, meta
    payload = {
        "schema": "aether.chat_continuity_reanchor_observations.v1",
        "authority": "previously_model_visible_execution_observation",
        "semantic_ranking": False,
        "historical_results_are_current_state": False,
        "task_state_generation_at_reanchor": fresh_packet.get("task_state_generation"),
        "items": selected,
    }
    content = _CAPACITY_RECOVERY_PREFIX + json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    )
    meta["content_bytes"] = len(content.encode("utf-8"))
    return {"role": "system", "content": content}, meta


def _recent_complete_tool_exchanges(
    messages: Sequence[Mapping[str, Any]],
    *,
    count: int = _CAPACITY_RECENT_EXCHANGE_COUNT,
) -> list[dict[str, Any]]:
    """Return the trailing exact assistant/tool exchanges, newest window only.

    An exchange is complete only when one assistant native tool call is followed
    immediately by its matching tool result.  Messages are copied verbatim,
    including provider-visible reasoning fields.  No summarization or semantic
    selection occurs.
    """
    required = max(0, int(count))
    if required == 0:
        return []
    rows = _normalize_messages(messages)
    pairs: list[tuple[int, int]] = []
    for index in range(len(rows) - 1):
        assistant = rows[index]
        tool = rows[index + 1]
        if assistant.get("role") != "assistant" or tool.get("role") != "tool":
            continue
        calls = assistant.get("tool_calls")
        if not isinstance(calls, list) or len(calls) != 1:
            continue
        call_id = str(_field(calls[0], "id", "") or "").strip()
        if call_id and str(tool.get("tool_call_id") or "").strip() == call_id:
            pairs.append((index, index + 1))
    if len(pairs) < required:
        return []
    selected_pairs = pairs[-required:]
    first_start, _ = selected_pairs[0]
    _, last_end = selected_pairs[-1]
    # Between complete native exchanges, and after the newest exchange, only
    # inert USER feedback is admissible. A correction is not a tool result and
    # must travel with the selected window without breaking pair accounting.
    selected_span = rows[first_start:last_end + 1]
    cursor = first_start
    observed_pairs = 0
    while cursor <= last_end:
        if any(pair[0] == cursor for pair in selected_pairs):
            observed_pairs += 1
            cursor += 2
            continue
        if rows[cursor].get("role") != "user":
            return []
        cursor += 1
    if observed_pairs != required:
        return []
    trailing = rows[last_end + 1:]
    if any(row.get("role") != "user" for row in trailing):
        return []
    return [deepcopy(row) for row in [*selected_span, *trailing]]


def _request_context_anatomy(request: Mapping[str, Any]) -> dict[str, int]:
    """Byte composition of one dispatched Chat request (telemetry only)."""
    def _size(value: Any) -> int:
        return len(json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
        ).encode("utf-8"))

    messages = list(request.get("messages") or ())
    out = {
        "tool_schema_bytes": _size(request.get("tools") or []),
        "system_bytes": 0,
        "history_assistant_content_bytes": 0,
        "history_assistant_reasoning_bytes": 0,
        "history_tool_call_bytes": 0,
        "history_tool_result_bytes": 0,
        "current_context_bytes": 0,
        "history_exchange_count": 0,
    }
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            continue
        content = message.get("content")
        text = content if isinstance(content, str) else ("" if content is None else json.dumps(content, default=str))
        length = len(text.encode("utf-8"))
        role = message.get("role")
        if index == len(messages) - 1:
            out["current_context_bytes"] += length
        elif role == "system":
            out["system_bytes"] += length
        elif role == "assistant":
            out["history_assistant_content_bytes"] += length
            out["history_assistant_reasoning_bytes"] += len(
                str(message.get("reasoning_content") or "").encode("utf-8")
            )
            out["history_tool_call_bytes"] += _size(message.get("tool_calls") or [])
            out["history_exchange_count"] += 1
        else:
            out["history_tool_result_bytes"] += length
    return out


def _extract_content(message: Any) -> str:
    content = _field(message, "content")
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        parts: list[str] = []
        for chunk in content:
            text = _field(chunk, "text")
            if text is not None:
                parts.append(str(text))
        return "".join(parts)
    return ""


def _extract_tool_call(call: Any) -> tuple[str, str]:
    function = _field(call, "function")
    name = str(_field(function, "name", "") or "")
    arguments = _field(function, "arguments")
    if not name or not isinstance(arguments, str):
        raise ChatModelOutputError("native_tool_call_shape_invalid")
    return name, arguments


class ChatCompletionsModelCallable:
    """Synchronous, one-create Chat Completions ModelCallable."""

    _RATE_HEADER_PREFIXES = (
        "x-ratelimit-",
        "x-ms-ratelimit-",
        "retry-after",
        "retry-after-ms",
    )

    def __init__(
        self,
        *,
        transport: ChatCompletionsTransport | Callable[..., Any] | None = None,
        client: Any | None = None,
        deployment: str,
        role: str = "solver",
        effort: str | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        native_persistent_tools: bool | None = None,
        tool_surface_mode: str = PERSISTENT_TOOL_SURFACE_CONTROL,
        budget_guard: ProviderBudgetGuard | None = None,
        temperature: float = 0.0,
        throughput_pacer: SerialTokenPacer | SharedDeploymentTokenPacer | None = None,
        max_retries: int = 0,
        capacity_reanchor_recovery_mode: str = _CAPACITY_REANCHOR_RECOVERY_OFF,
        capacity_overflow_action: str = _CAPACITY_OVERFLOW_REANCHOR,
        capture_rate_headers: bool = False,
        expected_returned_model: str | None = None,
        research_runtime_config_sha256: str | None = None,
        provider_timeout_s: float | None = None,
        context_policy: str = _managed_context.MANAGED_CONTEXT_POLICY_CONTROL,
        managed_context_trigger_tokens: int = _managed_context.MANAGED_CONTEXT_DEFAULT_TRIGGER_TOKENS,
        managed_context_keep_exchanges: int = _managed_context.MANAGED_CONTEXT_DEFAULT_KEEP_EXCHANGES,
        stream_idle_timeout_s: float | None = None,
        capture_provider_request_id: bool = False,
        disable_output_cap_escalation: bool = False,
        charge_shared_pacer_wait_to_run_deadline: bool = False,
        session_affinity_suffix: str = "",
        top_p: float | None = None,
        tolerant_argument_parsing: bool = False,
    ) -> None:
        # Opt-in arm (aether/history_lean.py): model-facing request projection of the committed history.
        self._history_mode = resolve_history_mode(environ=os.environ)
        # Opt-in infrastructure arm (aether/session_affinity.py): an SDK-only header, never model-facing.
        self._session_affinity_key = session_affinity_key_from_env(
            {SESSION_AFFINITY_KEY_ENV: os.environ.get(SESSION_AFFINITY_KEY_ENV, "")},
            suffix=str(session_affinity_suffix or ""),
        )
        if transport is None:
            if client is None:
                raise ValueError("a Chat Completions transport or client is required")
            transport = getattr(getattr(client, "chat", None), "completions", None)
        if transport is None:
            raise ValueError("client does not expose chat.completions")
        self._transport = transport
        self._deployment = str(deployment)
        self._expected_returned_model = (
            self._deployment if expected_returned_model is None
            else str(expected_returned_model).strip()
        )
        if not self._expected_returned_model:
            raise ValueError("expected_returned_model must be nonempty")
        self._require_returned_model = expected_returned_model is not None
        self._role = str(role)
        self._tolerant_argument_parsing = bool(tolerant_argument_parsing)
        self._last_protocol_salvage: dict[str, Any] | None = None
        self._effort = None if effort is None else str(effort)
        self._effort_override: str | None = None
        use_native = self._role == "solver" if native_persistent_tools is None else bool(native_persistent_tools)
        source_tools = PERSISTENT_CHAT_PROVIDER_TOOLS if (tools is None and use_native) else (tools or ())
        self._tools = tuple(_chat_tool(tool) for tool in source_tools)
        from ..context_tree.epoch import ZOOM_TOOL

        canonical_zoom_tool = _chat_tool(ZOOM_TOOL)
        configured_zoom_tools = tuple(
            tool for tool in self._tools
            if tool["function"].get("name") == "zoom"
        )
        if configured_zoom_tools and configured_zoom_tools != (canonical_zoom_tool,):
            raise ValueError("M-TREE zoom must use the exact context-tree tool contract")
        self._m_tree_zoom_tool = (
            deepcopy(canonical_zoom_tool) if configured_zoom_tools else None
        )
        self._native_persistent_tools = bool(self._tools) and use_native
        # challenger_v4: the configured finish tool carries a completion_card; the surface rebuilt per
        # scope below keeps it, and the parser lifts it out of the call (never into the turn).
        self._finish_completion_card = any(
            tool["function"].get("name") == "finish"
            and "completion_card" in tool["function"]["parameters"].get("properties", {})
            for tool in self._tools
        )
        selected_tool_surface_mode = str(tool_surface_mode or PERSISTENT_TOOL_SURFACE_CONTROL).strip()
        if selected_tool_surface_mode not in PERSISTENT_TOOL_SURFACE_MODES:
            raise ValueError(f"unsupported Chat tool surface mode: {selected_tool_surface_mode!r}")
        if selected_tool_surface_mode in {
            PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1, PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1,
            PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1,
        } and not self._native_persistent_tools:
            raise ValueError(f"{selected_tool_surface_mode} requires native PERSISTENT tools")
        self._tool_surface_mode = selected_tool_surface_mode
        self._context_policy = str(context_policy or _managed_context.MANAGED_CONTEXT_POLICY_CONTROL).strip()
        if self._context_policy not in _managed_context.MANAGED_CONTEXT_POLICIES:
            raise ValueError(f"unsupported Chat context policy: {self._context_policy!r}")
        self._managed_context_trigger_tokens = int(managed_context_trigger_tokens)
        self._managed_context_keep_exchanges = int(managed_context_keep_exchanges)
        self._managed_context_scopes: dict[tuple[str, str], _managed_context.ClmScope] = {}
        if self._context_policy in _managed_context.MANAGED_CONTEXT_CHECKPOINT_POLICIES:
            if not self._native_persistent_tools:
                raise ValueError("checkpoint context policy requires native PERSISTENT tools")
            if self._managed_context_trigger_tokens <= 0 or self._managed_context_keep_exchanges < 0:
                raise ValueError("managed_context trigger tokens must be positive; keep exchanges non-negative")
            exposed = {t["function"].get("name") for t in self._tools_for_scope(None)}
            missing = [n for n in _managed_context.MANAGED_CONTEXT_REQUIRED_TOOL_NAMES if n not in exposed]
            if missing:
                raise ValueError(
                    "checkpoint context policy requires retrieval tools to stay exposed: " + ", ".join(missing)
                )
        self._budget_guard = budget_guard
        self._temperature = float(temperature)
        # Opt-in sampling arm (aether/sampling.py): None omits the key, so control request bytes are unchanged.
        self._top_p: float | None = None if top_p is None else float(top_p)
        self._temperature_override: float | None = None
        self._throughput_pacer = throughput_pacer
        self._capture_provider_request_id = bool(capture_provider_request_id)
        self._disable_output_cap_escalation = bool(disable_output_cap_escalation)
        self._charge_shared_pacer_wait_to_run_deadline = bool(
            charge_shared_pacer_wait_to_run_deadline
        )
        self._max_retries = int(max_retries)
        self._capture_rate_headers = bool(capture_rate_headers)
        self._research_runtime_config_sha256 = str(research_runtime_config_sha256 or "").strip()
        self._provider_timeout_s = (
            None if provider_timeout_s is None else float(provider_timeout_s)
        )
        if self._provider_timeout_s is not None and self._provider_timeout_s <= 0:
            raise ValueError("provider_timeout_s must be positive")
        # When set, requests stream and this bounds the gap between chunks;
        # the task deadline (not a whole-request timeout) bounds total time.
        self._stream_idle_timeout_s = (
            None if stream_idle_timeout_s is None else float(stream_idle_timeout_s)
        )
        if self._stream_idle_timeout_s is not None and self._stream_idle_timeout_s <= 0:
            raise ValueError("stream_idle_timeout_s must be positive")
        self._last_rate_headers: dict[str, str] = {}
        self._capacity_reanchor_recovery_mode = str(
            capacity_reanchor_recovery_mode or _CAPACITY_REANCHOR_RECOVERY_OFF
        ).strip().lower()
        if self._capacity_reanchor_recovery_mode not in _CAPACITY_REANCHOR_RECOVERY_MODES:
            raise ValueError(
                "unsupported Chat capacity reanchor recovery mode: "
                + self._capacity_reanchor_recovery_mode
            )
        self._capacity_overflow_action = str(
            capacity_overflow_action or _CAPACITY_OVERFLOW_REANCHOR
        ).strip().lower()
        if self._capacity_overflow_action not in _CAPACITY_OVERFLOW_ACTIONS:
            raise ValueError(
                "unsupported Chat capacity overflow action: "
                + self._capacity_overflow_action
            )
        if self._temperature < 0:
            raise ValueError("temperature must be non-negative")
        if self._top_p is not None and not 0.0 < self._top_p <= 1.0:
            raise ValueError("top_p must be in (0, 1]")
        if self._max_retries not in {0, 1, 2}:
            raise ValueError("Chat Completions max_retries must be 0, 1, or 2")
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_lock = threading.Lock()
        self._next_logical_call_id = 0
        self.last_call_telemetry: dict[str, Any] = {}
        self._run_cancellation_event: Any | None = None
        self._scope_lock = threading.Lock()
        self._continuity_states: dict[tuple[str, str], dict[str, Any]] = {}
        self._pending_continuity_states: dict[tuple[str, str], dict[str, Any]] = {}
        self._scope_completion_modes: dict[tuple[str, str], str] = {}
        self._scope_commitment_modes: dict[tuple[str, str], str] = {}
        self._scope_disposition_modes: dict[tuple[str, str], str] = {}
        self._scope_record_modes: dict[tuple[str, str], str] = {}
        self._scope_transport_modes: dict[tuple[str, str], str] = {}
        self._scope_working_context_modes: dict[tuple[str, str], str] = {}
        self._scope_context_file_modes: dict[tuple[str, str], str] = {}
        self._completion_cards: dict[tuple[str, str], dict[str, Any]] = {}
        self._continuity_admission_events: list[dict[str, Any]] = []

    def _logical_call_id(self) -> int:
        with self._telemetry_lock:
            self._next_logical_call_id += 1
            return self._next_logical_call_id

    def _record(self, event: dict[str, Any]) -> None:
        snapshot = deepcopy(event)
        with self._telemetry_lock:
            self.last_call_telemetry = snapshot
            self._telemetry_events.append(snapshot)
        _append_chat_telemetry_journal(snapshot)

    def drain_telemetry(self) -> tuple[dict[str, Any], ...]:
        with self._telemetry_lock:
            rows = tuple(self._telemetry_events)
            self._telemetry_events.clear()
            return rows

    def drain_continuity_admission_telemetry(self) -> tuple[dict[str, Any], ...]:
        with self._scope_lock:
            rows = tuple(self._continuity_admission_events)
            self._continuity_admission_events.clear()
            return rows

    def bind_run_cancellation(self, event: Any | None) -> None:
        """Bind the current task cancellation signal without dispatching."""
        self._run_cancellation_event = event

    def _raise_if_run_cancelled(self) -> None:
        raise_if_run_cancelled(self._run_cancellation_event)
        raise_if_run_deadline_exceeded()

    def __call__(
        self, messages: Sequence[Mapping[str, Any]], *, max_output_tokens: int | None = None,
    ) -> str:
        return self._call(messages, max_output_tokens=max_output_tokens, telemetry_scope=None)

    def call_with_telemetry_scope(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        max_output_tokens: int | None = None,
        run_id: str,
        task_id: str | None,
        call_generation: int | None = None,
    ) -> str:
        return self._call(
            messages,
            max_output_tokens=max_output_tokens,
            telemetry_scope={"run_id": str(run_id), "task_id": task_id},
            call_generation=call_generation,
        )

    @staticmethod
    def _scope_key(scope: Mapping[str, Any] | None) -> tuple[str, str] | None:
        if not scope:
            return None
        run_id = str(scope.get("run_id") or "").strip()
        task_id = str(scope.get("task_id") or "").strip()
        return (run_id, task_id) if run_id and task_id else None

    def _tools_for_scope(self, scope_key: tuple[str, str] | None) -> tuple[dict[str, Any], ...]:
        """Apply runtime-owned PERSISTENT capability filters to canonical tools."""
        tools: Sequence[Mapping[str, Any]] = self._tools
        commitment = "control"
        disposition = "control"
        completion = "inspect_or_finish"
        record = "v1"
        working_context = _SOLVER_WORKING_CONTEXT_OFF
        if scope_key is not None:
            with self._scope_lock:
                commitment = self._scope_commitment_modes.get(scope_key, commitment)
                disposition = self._scope_disposition_modes.get(scope_key, disposition)
                completion = self._scope_completion_modes.get(scope_key, completion)
                record = self._scope_record_modes.get(scope_key, record)
                working_context = self._scope_working_context_modes.get(
                    scope_key, _SOLVER_WORKING_CONTEXT_OFF,
                )
        if self._native_persistent_tools:
            if commitment == "commitment_v1" and disposition == "completion_disposition_v1":
                tools = PERSISTENT_CHAT_PROVIDER_TOOLS_COMMITMENT_AND_DISPOSITION_V1
            elif commitment == "commitment_v1":
                tools = PERSISTENT_CHAT_PROVIDER_TOOLS_COMMITMENT_V1
            elif disposition == "completion_disposition_v1":
                tools = PERSISTENT_CHAT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1
            # The canonical variants above are already Chat-shaped by _chat_tool.
            tools = tuple(_chat_tool(tool) for tool in tools)
            if self._finish_completion_card:
                tools = with_finish_completion_card(tools)
            if completion == "finish_intent_only":
                tools = tuple(tool for tool in tools if tool["function"].get("name") != _FINISH)
            elif completion == "finish_only":
                tools = tuple(tool for tool in tools if tool["function"].get("name") != _FINISH_INTENT)
            if record == "off":
                tools = tuple(
                    tool for tool in tools
                    if tool["function"].get("name") != _COMPLETION_RECORD_ACTION
                )
        if self._tool_surface_mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1:
            selected_names = frozenset(PERSISTENT_CHAT_STATIC_TOOL_KERNEL_V1_NAMES)
            tools = tuple(
                tool for tool in tools
                if tool["function"].get("name") in selected_names
            )
        elif self._tool_surface_mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_JOBS_V1:
            selected_names = frozenset(PERSISTENT_CHAT_STATIC_TOOL_KERNEL_JOBS_V1_NAMES)
            tools = tuple(
                tool for tool in tools
                if tool["function"].get("name") in selected_names
            )
        elif self._tool_surface_mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1:
            selected_names = frozenset(PERSISTENT_CHAT_STATIC_TOOL_KERNEL_EDIT_V1_NAMES)
            kept = [
                tool for tool in tools
                if tool["function"].get("name") in selected_names
            ]
            # Opt-in partial-edit tool, listed right after its whole-file sibling.
            edit_tool = _chat_tool(persistent_chat_edit_file_tool(commitment_v1=commitment == "commitment_v1"))
            at = next(
                (i + 1 for i, tool in enumerate(kept) if tool["function"].get("name") == "write_file"),
                len(kept),
            )
            tools = (*kept[:at], edit_tool, *kept[at:])
            tools = tuple(_with_persistent_shell_sentence(tool) for tool in tools)
        elif self._tool_surface_mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1:
            selected_names = frozenset(PERSISTENT_CHAT_STATIC_TOOL_KERNEL_EDIT_V1_NAMES)
            kept = [
                tool for tool in tools
                if tool["function"].get("name") in selected_names
            ]
            edit_tool = _chat_tool(persistent_chat_edit_file_tool(commitment_v1=commitment == "commitment_v1"))
            at = next(
                (i + 1 for i, tool in enumerate(kept) if tool["function"].get("name") == "write_file"),
                len(kept),
            )
            tools = (*kept[:at], edit_tool, *kept[at:])
            tools = tuple(_with_persistent_shell_sentence(tool) for tool in tools)
        if selected_long_command_mode() == LONG_COMMAND_BACKGROUND_V1:
            if not self._native_persistent_tools:
                raise ValueError("background_v1 requires native PERSISTENT tools")
            background_tools = tuple(
                _chat_tool(tool)
                for tool in persistent_chat_background_job_tools(commitment_v1=commitment == "commitment_v1")
                if tool.get("name") not in {item["function"].get("name") for item in tools}
            )
            tools = (*tools, *background_tools)
        if self._tool_surface_mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1:
            # Flatten last so background-job tools on this surface are flat too.
            tools = tuple(
                {"type": "function", "function": {
                    **dict(tool["function"]),
                    "parameters": persistent_flat_tool_parameters(tool["function"]["parameters"]),
                    "strict": False,
                }}
                for tool in tools
            )
        if _working_context_uses_tool_notes(working_context):
            grounded_notes = (
                working_context == _SOLVER_WORKING_CONTEXT_TOOL_NOTES_GROUNDED_V1
            )
            tools = tuple(
                _chat_tool_with_required_working_notes(tool, grounded=grounded_notes)
                for tool in tools
            )
        if self._m_tree_zoom_tool is not None and not any(
            tool["function"].get("name") == "zoom" for tool in tools
        ):
            tools = (*tools, deepcopy(self._m_tree_zoom_tool))
        if scope_key is not None:
            with self._scope_lock:
                context_file_mode = self._scope_context_file_modes.get(scope_key, "off")
            tools = _context_file_surface(tuple(tools), context_file_mode)
        return tuple(deepcopy(dict(tool)) for tool in tools)

    def _prepare_messages(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        telemetry_scope: Mapping[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Re-anchor a fresh Thin context onto the committed Chat transcript.

        Thin deliberately rebuilds its system/context packet each turn.  When a
        committed native call exists, the latest packet becomes that call's
        exact tool result, while the immutable prefix stays at the front.  The
        prior assistant messages and reasoning fields remain in order.
        """
        prepared = _normalize_messages(messages)
        scope_key = self._scope_key(telemetry_scope)
        if scope_key is None or not self._native_persistent_tools:
            return prepared
        with self._scope_lock:
            state = self._continuity_states.get(scope_key)
            if state is not None and scope_key in self._pending_continuity_states:
                raise ChatModelError("chat_continuity_pending_candidate_requires_admission")
            history = [] if state is None else deepcopy(list(state.get("history") or ()))
            call_id = "" if state is None else str(state.get("call_id") or "")
        if state is None:
            return prepared
        if not call_id or not history:
            raise ChatModelError("chat_continuity_parent_identity_missing")
        # Thin can append inert USER protocol feedback after its real context
        # packet. That feedback did not execute a native tool and must never
        # become the result of the last admitted native call.
        packet_indices = [
            i for i, row in enumerate(prepared)
            if isinstance(row.get("content"), str)
            and row["content"].startswith(_CONTEXT_PACKET_PREFIX)
        ]
        current_index = packet_indices[-1] if packet_indices else len(prepared) - 1
        current = prepared[current_index]
        prefix = prepared[:current_index]
        feedback = prepared[current_index + 1:]
        if any(row.get("role") != "user" for row in feedback):
            raise ChatModelError("chat_continuity_feedback_role_invalid")
        boundary = current.get("content")
        if not isinstance(boundary, str):
            boundary = json.dumps(_jsonable(boundary), sort_keys=True, separators=(",", ":"))
        if self._history_mode == HISTORY_LEAN_V1:
            # Cache-stable boundary packet: the result first, volatile state last (aether/history_lean.py).
            boundary = stable_packet_content(boundary)
        segment = [*history, {
            "role": "tool",
            "tool_call_id": call_id,
            "content": boundary,
        }]
        if self._history_mode == HISTORY_LEAN_V1:
            # Request projection only: the stored history stays exact (see _stage_pending_response).
            segment = project_history_lean(segment)
        return [*prefix, *segment, *feedback]

    def _stage_pending_response(
        self,
        *,
        scope_key: tuple[str, str] | None,
        response: Any,
        receipt: Mapping[str, Any],
        request_messages: Sequence[Mapping[str, Any]],
    ) -> None:
        if scope_key is None or not self._native_persistent_tools:
            return
        call_id = str(receipt.get("native_tool_call_id") or "").strip()
        message = _field(_field(response, "choices", [])[0], "message")
        assistant = _jsonable(message)
        if not call_id or not isinstance(assistant, Mapping):
            raise ChatModelOutputError("native_tool_continuity_identity_missing")
        # SDK response-only metadata is not legal in Azure Chat input. Keep
        # native calls and reasoning verbatim; raw response remains in telemetry.
        assistant = {key: deepcopy(value) for key, value in assistant.items()
                     if key in {"role", "content", "tool_calls", "reasoning_content"}}
        request_transcript = _normalize_messages(request_messages)
        with self._scope_lock:
            if scope_key in self._pending_continuity_states:
                raise ChatModelError("chat_continuity_pending_candidate_already_staged")
            committed = self._continuity_states.get(scope_key)
            previous_history = [] if committed is None else list(committed.get("history") or ())
            if committed is None:
                # The initial request has no provider tool result to replay.
                # A capacity re-anchor can deliberately seed one bounded prior
                # window.  Preserve only the configured transport-owned seed;
                # ordinary fresh system/context messages are rebuilt by Thin.
                if (
                    self._capacity_reanchor_recovery_mode
                    in _CAPACITY_REANCHOR_EXCHANGE_SEED_MODES
                ):
                    exchange_messages = _recent_complete_tool_exchanges(
                        request_transcript,
                        count=_CAPACITY_RECENT_EXCHANGE_COUNT,
                    )
                    # A model-written capacity checkpoint travels with the seed.
                    checkpoint_rows = [
                        dict(row) for row in request_transcript
                        if _capckpt.is_checkpoint_message(row)
                    ]
                    history = [*checkpoint_rows, *exchange_messages, dict(assistant)]
                else:
                    recovery_messages = [
                        dict(row) for row in request_transcript
                        if isinstance(row, Mapping)
                        and _prefixed_json_object(row, _CAPACITY_RECOVERY_PREFIX) is not None
                    ]
                    history = [*recovery_messages, dict(assistant)]
            else:
                # _prepare_messages emits [fresh prefix, committed suffix,
                # current tool result, optional USER feedback]. Recover that exact suffix from the
                # request that was actually dispatched. This preserves the
                # required assistant/tool alternation over arbitrarily many
                # re-anchors and prevents adjacent assistant tool calls.
                boundary_indices = [
                    i for i, row in enumerate(request_transcript)
                    if row.get("role") == "tool"
                    and str(row.get("tool_call_id") or "") == str(committed.get("call_id") or "")
                ]
                if len(boundary_indices) != 1:
                    raise ChatModelError("chat_continuity_tool_result_identity_mismatch")
                boundary_index = boundary_indices[0]
                suffix_start = boundary_index - len(previous_history)
                if (
                    self._history_mode == HISTORY_LEAN_V1
                    and suffix_start >= 0
                    and request_transcript[suffix_start:boundary_index]
                    == project_history_lean([*previous_history, request_transcript[boundary_index]])[:-1]
                ):
                    # The dispatched history was the lean projection of the stored one: stage from the
                    # exact stored messages so projected text never becomes custody.
                    request_transcript = [
                        *request_transcript[:suffix_start], *previous_history,
                        *request_transcript[boundary_index:],
                    ]
                if suffix_start < 0 or request_transcript[suffix_start:boundary_index] != previous_history:
                    raise ChatModelError("chat_continuity_committed_transcript_mismatch")
                current_tool = request_transcript[boundary_index]
                feedback = request_transcript[boundary_index + 1:]
                if any(row.get("role") != "user" for row in feedback):
                    raise ChatModelError("chat_continuity_feedback_role_invalid")
                if (
                    current_tool.get("role") != "tool"
                    or str(current_tool.get("tool_call_id") or "") != str(committed.get("call_id") or "")
                ):
                    raise ChatModelError("chat_continuity_tool_result_identity_mismatch")
                transport_mode = self._scope_transport_modes.get(
                    scope_key, _TRANSPORT_FULL_SNAPSHOT,
                )
                if transport_mode == _TRANSPORT_LATEST_EXCHANGE_V1:
                    history = [dict(assistant)]
                elif transport_mode == _TRANSPORT_OBSERVATION_HISTORY_V1:
                    history = [
                        *request_transcript[suffix_start:boundary_index],
                        _historical_observation_message(current_tool),
                        *feedback,
                        dict(assistant),
                    ]
                elif transport_mode == _TRANSPORT_ACTIONS_RESULTS_NO_REASONING_V1:
                    history = [
                        *[_without_reasoning(row) for row in request_transcript[suffix_start:boundary_index]],
                        _historical_observation_message(current_tool),
                        *feedback,
                        dict(assistant),
                    ]
                elif transport_mode == _TRANSPORT_REASONING_ACTIONS_NO_RESULTS_V1:
                    history = [
                        *request_transcript[suffix_start:boundary_index],
                        _historical_result_stub(current_tool),
                        *feedback,
                        dict(assistant),
                    ]
                elif transport_mode == _TRANSPORT_REASONING_LATEST_ACTION_NO_RESULTS_V1:
                    prior = request_transcript[suffix_start:boundary_index]
                    history = [
                        *[
                            (
                                _reasoning_only_assistant(row)
                                if row.get("role") == "assistant"
                                else dict(row)
                            )
                            for row in prior
                            if row.get("role") in {"assistant", "user"}
                        ],
                        *feedback,
                        dict(assistant),
                    ]
                else:
                    history = [*request_transcript[suffix_start:], dict(assistant)]
            self._pending_continuity_states[scope_key] = {
                "call_id": call_id,
                "history": history,
                "request_transcript": request_transcript,
                "managed_context_read_key": _managed_context.read_action_key(
                    (assistant.get("tool_calls") or [{}])[0]
                ),
            }

    def commit_pending_response(self, *, run_id: str, task_id: str) -> None:
        if self._role != "solver":
            return
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            raise ChatModelError("chat_continuity_scope_missing")
        with self._scope_lock:
            pending = self._pending_continuity_states.pop(key, None)
            previous = self._continuity_states.get(key)
            if pending is None:
                raise ChatModelError("chat_continuity_pending_candidate_missing_at_commit")
            self._continuity_states[key] = {
                k: v for k, v in pending.items() if k != "managed_context_read_key"
            }
            managed_context_scope = self._managed_context_scopes.get(key)
            if managed_context_scope is not None:
                self._continuity_admission_events.extend(
                    self._managed_context_metric_events(key, managed_context_scope.note_committed_action(
                        pending.get("managed_context_read_key")
                    ))
                )
            event = {
                "event_kind": "chat_continuity_parent_admission",
                "provider": "chat_completions",
                "role": self._role,
                "run_id": key[0],
                "task_id": key[1],
                "persistent_continuity_mode": "explicit_chat_history",
                "persistent_continuity_parent_disposition": "committed",
                "persistent_continuity_call_id": pending["call_id"],
                "persistent_continuity_previous_call_id": None if previous is None else previous.get("call_id"),
            }
            self._continuity_admission_events.append(event)

    def reject_pending_response(self, *, run_id: str, task_id: str) -> None:
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            return
        with self._scope_lock:
            pending = self._pending_continuity_states.pop(key, None)
            if pending is not None:
                self._continuity_admission_events.append({
                    "event_kind": "chat_continuity_parent_admission",
                    "provider": "chat_completions",
                    "role": self._role,
                    "run_id": key[0],
                    "task_id": key[1],
                    "persistent_continuity_mode": "explicit_chat_history",
                    "persistent_continuity_parent_disposition": "rejected",
                    "persistent_continuity_call_id": pending.get("call_id"),
                })

    def export_continuity_scope(self, *, run_id: str, task_id: str) -> dict[str, Any] | None:
        """Export one committed explicit-Chat continuity scope for process restart.

        Only already-admitted history is exported. A staged/pending provider
        response is intentionally not serializable because its associated
        Solver action has not yet been admitted by the runtime.
        """
        if self._role != "solver":
            raise ChatModelError("chat_continuity_restart_export_solver_only")
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            raise ChatModelError("chat_continuity_scope_missing")
        with self._scope_lock:
            if key in self._pending_continuity_states:
                raise ChatModelError("chat_continuity_pending_candidate_requires_admission")
            state = self._continuity_states.get(key)
            if state is None:
                return None
            payload = {
                "schema_version": "aether.chat_continuity_snapshot.v1",
                "provider": "chat_completions",
                "role": self._role,
                "deployment": self._deployment,
                "run_id": key[0],
                "task_id": key[1],
                "call_id": str(state.get("call_id") or ""),
                "history": deepcopy(list(state.get("history") or ())),
                "request_transcript": deepcopy(list(state.get("request_transcript") or ())),
            }
        if not payload["call_id"] or not payload["history"]:
            raise ChatModelError("chat_continuity_parent_identity_missing")
        _, encoded = _canonical_json(payload)
        return {
            **payload,
            "state_sha256": sha256(encoded).hexdigest(),
        }

    def import_continuity_scope(
        self,
        snapshot: Mapping[str, Any],
        *,
        run_id: str,
        task_id: str,
    ) -> None:
        """Restore one integrity-checked committed Chat transcript after restart."""
        if self._role != "solver":
            raise ChatModelError("chat_continuity_restart_import_solver_only")
        if not isinstance(snapshot, Mapping):
            raise ChatModelError("chat_continuity_restart_snapshot_invalid")
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            raise ChatModelError("chat_continuity_scope_missing")
        raw = dict(snapshot)
        supplied_hash = str(raw.pop("state_sha256", "") or "").strip().lower()
        _, encoded = _canonical_json(raw)
        expected_hash = sha256(encoded).hexdigest()
        if not supplied_hash or supplied_hash != expected_hash:
            raise ChatModelError("chat_continuity_restart_snapshot_hash_mismatch")
        required = {
            "schema_version": "aether.chat_continuity_snapshot.v1",
            "provider": "chat_completions",
            "role": self._role,
            "deployment": self._deployment,
            "run_id": key[0],
            "task_id": key[1],
        }
        for field, expected in required.items():
            if str(raw.get(field) or "") != str(expected):
                raise ChatModelError(f"chat_continuity_restart_snapshot_{field}_mismatch")
        call_id = str(raw.get("call_id") or "").strip()
        history_raw = raw.get("history")
        request_raw = raw.get("request_transcript")
        if not call_id or not isinstance(history_raw, list) or not history_raw:
            raise ChatModelError("chat_continuity_restart_snapshot_state_missing")
        if not isinstance(request_raw, list) or not request_raw:
            raise ChatModelError("chat_continuity_restart_snapshot_request_missing")
        history = _normalize_messages(history_raw)
        request_transcript = _normalize_messages(request_raw)
        last = history[-1]
        tool_calls = last.get("tool_calls") if isinstance(last, Mapping) else None
        if (
            last.get("role") != "assistant"
            or not isinstance(tool_calls, list)
            or len(tool_calls) != 1
            or str(_field(tool_calls[0], "id", "") or "").strip() != call_id
        ):
            raise ChatModelError("chat_continuity_restart_snapshot_parent_mismatch")
        with self._scope_lock:
            if key in self._pending_continuity_states or key in self._continuity_states:
                raise ChatModelError("chat_continuity_restart_scope_already_present")
            self._continuity_states[key] = {
                "call_id": call_id,
                "history": deepcopy(history),
                "request_transcript": deepcopy(request_transcript),
            }
            self._continuity_admission_events.append({
                "event_kind": "chat_continuity_restart_restore",
                "provider": "chat_completions",
                "role": self._role,
                "run_id": key[0],
                "task_id": key[1],
                "deployment": self._deployment,
                "persistent_continuity_mode": "explicit_chat_history",
                "persistent_continuity_call_id": call_id,
                "state_sha256": supplied_hash,
            })

    def set_primary_completion_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        normalized = str(mode or "").strip()
        if normalized not in {"finish_intent_only", "finish_only"}:
            raise ChatModelError(f"unsupported primary completion mode: {normalized!r}")
        with self._scope_lock:
            self._scope_completion_modes[(str(run_id), str(task_id))] = normalized

    def set_solver_commitment_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        normalized = str(mode or "").strip().lower()
        if normalized not in {"control", "commitment_v1"}:
            raise ChatModelError(f"unsupported solver commitment mode: {normalized!r}")
        with self._scope_lock:
            self._scope_commitment_modes[(str(run_id), str(task_id))] = normalized

    def set_completion_disposition_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        normalized = str(mode or "").strip().lower()
        if normalized not in {"control", "completion_disposition_v1"}:
            raise ChatModelError(f"unsupported completion disposition mode: {normalized!r}")
        with self._scope_lock:
            self._scope_disposition_modes[(str(run_id), str(task_id))] = normalized

    def take_completion_card(self, *, run_id: str, task_id: str) -> dict[str, Any] | None:
        """The completion card of the last finish call in this scope, once (challenger_v4)."""
        with self._scope_lock:
            return self._completion_cards.pop((str(run_id).strip(), str(task_id).strip()), None)

    def set_completion_record_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        normalized = str(mode or "").strip().lower()
        if normalized not in {"off", "v1"}:
            raise ChatModelError(f"unsupported completion record mode: {normalized!r}")
        with self._scope_lock:
            self._scope_record_modes[(str(run_id), str(task_id))] = normalized

    def set_computer_use_available(self, available: bool, *, run_id: str, task_id: str) -> None:
        if available:
            raise ChatModelError("Chat Completions GLM route has no qualified computer tool")

    def set_reality_transport_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        normalized = str(mode or _TRANSPORT_FULL_SNAPSHOT).strip().lower()
        if normalized not in _CHAT_TRANSPORT_MODES:
            raise ChatModelError(
                "Chat Completions GLM route supports only qualified reality-transport modes; "
                f"got {normalized!r}"
            )
        with self._scope_lock:
            self._scope_transport_modes[(str(run_id), str(task_id))] = normalized

    def set_solver_working_context_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        normalized = str(mode or _SOLVER_WORKING_CONTEXT_OFF).strip().lower()
        if normalized not in _SOLVER_WORKING_CONTEXT_MODES:
            raise ChatModelError(f"unsupported Solver working-context mode: {normalized!r}")
        with self._scope_lock:
            self._scope_working_context_modes[(str(run_id), str(task_id))] = normalized

    def set_context_file_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        normalized = str(mode or "off").strip().lower()
        if normalized not in _CONTEXT_FILE_SCOPE_MODES:
            raise ChatModelError(f"unsupported context file mode: {normalized!r}")
        if normalized != "off" and not self._native_persistent_tools:
            raise ChatModelError("context file mode requires native PERSISTENT tools")
        with self._scope_lock:
            self._scope_context_file_modes[(str(run_id), str(task_id))] = normalized

    def clear_continuity_state(self, *, run_id: str, task_id: str) -> None:
        """Drop only the explicit chat transcript; every other scope mode survives."""
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            return
        with self._scope_lock:
            self._continuity_states.pop(key, None)
            self._pending_continuity_states.pop(key, None)

    def set_hosted_tool_search_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        if str(mode or "control").strip().lower() != "control":
            raise ChatModelError("Chat Completions GLM route has no qualified hosted tool search")

    def _request(
        self,
        messages: Sequence[Mapping[str, Any]],
        max_output_tokens: int | None,
        *,
        telemetry_scope: Mapping[str, Any] | None,
        checkpoint_request: bool = False,
        transcript_override: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if max_output_tokens is None or int(max_output_tokens) <= 0:
            raise ValueError("max_output_tokens must be a positive integer")
        prepared_messages = (
            [deepcopy(dict(row)) for row in transcript_override]
            if transcript_override is not None
            else self._prepare_messages(messages, telemetry_scope=telemetry_scope)
        )
        if checkpoint_request:
            prepared_messages = _managed_context.checkpoint_request_messages(prepared_messages)
        request: dict[str, Any] = {
            "model": self._deployment,
            "messages": prepared_messages,
            "max_tokens": int(max_output_tokens),
            "temperature": (
                self._temperature if self._temperature_override is None else self._temperature_override
            ),
            "n": 1,
        }
        if self._top_p is not None:
            request["top_p"] = self._top_p
        effective_effort = self._effort_override if self._effort_override is not None else self._effort
        if effective_effort is not None:
            request["reasoning_effort"] = effective_effort
        scope_key = self._scope_key(telemetry_scope)
        tools = self._tools_for_scope(scope_key)
        if tools:
            request.update({
                "tools": deepcopy(list(tools)),
                "tool_choice": "required" if self._native_persistent_tools else "auto",
                "parallel_tool_calls": False,
            })
        if checkpoint_request:
            request["tools"] = [*request["tools"], deepcopy(_managed_context.WRITE_CHECKPOINT_TOOL)]
            request["tool_choice"] = deepcopy(_managed_context.FORCED_TOOL_CHOICE)
        return request

    def _effective_provider_timeout_s(self) -> float | None:
        configured = self._provider_timeout_s
        if configured is None:
            return None
        remaining = remaining_run_s()
        if remaining is None:
            return configured
        if remaining <= 0.0:
            raise KernelRunTimeout("task run deadline exceeded before provider dispatch")
        # The task deadline is the wall-clock authority. A per-request SDK
        # timeout may be shorter than the profile ceiling only because less
        # task time remains.
        return min(configured, max(0.001, float(remaining)))

    @staticmethod
    def _is_timeout_exception(exc: BaseException) -> bool:
        return any("timeout" in klass.__name__.lower() for klass in type(exc).__mro__)

    def _create(self, request: dict[str, Any]) -> Any:
        if self._stream_idle_timeout_s is not None:
            return self._create_streamed(request)
        self._last_rate_headers = {}
        dispatch_request = request
        effective_timeout = self._effective_provider_timeout_s()
        if effective_timeout is not None:
            dispatch_request = dict(request)
            # OpenAI SDK request option; not part of the model-facing payload
            # or Aether token accounting.
            dispatch_request["timeout"] = effective_timeout
        dispatch_request = merge_affinity_headers(dispatch_request, self._session_affinity_key)
        if self._capture_rate_headers:
            raw_api = getattr(self._transport, "with_raw_response", None)
            raw_create = getattr(raw_api, "create", None)
            if callable(raw_create):
                try:
                    raw = raw_create(**dispatch_request)
                except Exception as exc:
                    response = getattr(exc, "response", None)
                    headers = getattr(response, "headers", None) or {}
                    self._last_rate_headers = {
                        str(key).lower(): str(value)
                        for key, value in dict(headers).items()
                        if str(key).lower().startswith(self._RATE_HEADER_PREFIXES)
                    }
                    raise
                headers = getattr(raw, "headers", None) or {}
                self._last_rate_headers = {
                    str(key).lower(): str(value)
                    for key, value in dict(headers).items()
                    if str(key).lower().startswith(self._RATE_HEADER_PREFIXES)
                }
                return raw.parse()
        create = getattr(self._transport, "create", None)
        if callable(create):
            return create(**dispatch_request)
        if callable(self._transport):
            return self._transport(**dispatch_request)
        raise ChatModelError("Chat Completions transport has no create method")

    def _create_streamed(self, request: dict[str, Any]) -> Any:
        """Stream one request and return a ChatCompletion-shaped dict.

        Infrastructure-only: ``stream``/``stream_options``/``timeout`` are SDK
        options and never enter the model-facing request snapshot.
        """
        self._last_rate_headers = {}
        remaining = remaining_run_s()
        if remaining is not None and remaining <= 0.0:
            raise KernelRunTimeout("task run deadline exceeded before provider dispatch")
        idle = float(self._stream_idle_timeout_s or 0.0)
        dispatch_request = dict(request)
        dispatch_request["stream"] = True
        dispatch_request["stream_options"] = dict(STREAM_OPTIONS)
        dispatch_request["timeout"] = idle if remaining is None else min(idle, max(0.001, remaining))
        dispatch_request = merge_affinity_headers(dispatch_request, self._session_affinity_key)
        stream: Any
        raw_api = getattr(self._transport, "with_raw_response", None) if self._capture_rate_headers else None
        raw_create = getattr(raw_api, "create", None)
        if callable(raw_create):
            try:
                raw = raw_create(**dispatch_request)
            except Exception as exc:
                headers = getattr(getattr(exc, "response", None), "headers", None) or {}
                self._last_rate_headers = {
                    str(key).lower(): str(value) for key, value in dict(headers).items()
                    if str(key).lower().startswith(self._RATE_HEADER_PREFIXES)
                }
                raise
            headers = getattr(raw, "headers", None) or {}
            self._last_rate_headers = {
                str(key).lower(): str(value) for key, value in dict(headers).items()
                if str(key).lower().startswith(self._RATE_HEADER_PREFIXES)
            }
            stream = raw.parse()
        else:
            create = getattr(self._transport, "create", None)
            if callable(create):
                stream = create(**dispatch_request)
            elif callable(self._transport):
                stream = self._transport(**dispatch_request)
            else:
                raise ChatModelError("Chat Completions transport has no create method")
        try:
            return collect_chat_stream(
                stream,
                capture_request_id=self._capture_provider_request_id,
                deadline_remaining_s=remaining_run_s,
            )
        except ChatStreamDeadline as exc:
            raise KernelRunTimeout("task run deadline expired during provider request") from exc

    def _retry_after_s(self) -> float | None:
        headers = self._last_rate_headers
        try:
            if "retry-after-ms" in headers:
                return float(headers["retry-after-ms"]) / 1000.0
            if "retry-after" in headers:
                return float(headers["retry-after"])
        except ValueError:
            return None
        return None

    def _admit_throughput(self, *, estimated_tokens: int) -> dict[str, Any]:
        """Admit one provider request without charging cross-row queue wait.

        Shared deployment admission is campaign infrastructure: it is recorded
        in wall/throughput telemetry but excluded from the scientific task
        deadline by default. Callers with an externally enforced finite replay
        deadline may charge the shared wait explicitly. Serial pacing remains
        task-owned and therefore charged.
        """
        pacer = self._throughput_pacer
        if pacer is None:
            return {}
        if isinstance(pacer, SharedDeploymentTokenPacer):
            if self._charge_shared_pacer_wait_to_run_deadline:
                return dict(pacer.admit(estimated_tokens=estimated_tokens))
            with run_deadline_excluded_wait():
                result = dict(pacer.admit(estimated_tokens=estimated_tokens))
            result["throughput_task_deadline_excluded_wait_s"] = round(
                float(result.get("throughput_wait_s") or 0.0), 6,
            )
            return result
        return dict(pacer.admit(estimated_tokens=estimated_tokens))

    def _note_pacer_rate_limit(self) -> None:
        pacer = self._throughput_pacer
        if isinstance(pacer, SharedDeploymentTokenPacer):
            pacer.note_rate_limit_response(retry_after_s=self._retry_after_s())
        elif pacer is not None:
            pacer.note_rate_limit()

    def _report_headers_to_pacer(self, event: dict[str, Any]) -> None:
        pacer = self._throughput_pacer
        if not isinstance(pacer, SharedDeploymentTokenPacer) or not self._last_rate_headers:
            return
        def number(name: str) -> float | None:
            try:
                return float(self._last_rate_headers[name])
            except (KeyError, ValueError):
                return None
        remaining_tokens = number("x-ratelimit-remaining-tokens")
        if remaining_tokens is None:
            return
        try:
            pacer.report_rate_limit_headers(
                remaining_tokens=remaining_tokens,
                remaining_requests=number("x-ratelimit-remaining-requests"),
                reservation_id=event.get("throughput_reservation_id"),
            )
        except ProviderThroughputError as exc:
            event["throughput_header_report_error"] = str(exc)[:500]

    def _record_rate_header_telemetry(self, event: dict[str, Any]) -> None:
        if self._last_rate_headers:
            event["provider_rate_limit_headers"] = dict(self._last_rate_headers)
        else:
            event.pop("provider_rate_limit_headers", None)

    @staticmethod
    def _is_pre_response_rate_limit(exc: BaseException) -> bool:
        lowered = str(exc).lower()
        return "429" in lowered or "rate limit" in lowered or "rate_limit" in lowered

    def _pre_response_retry_reason(self, exc: BaseException) -> str:
        """Classify a transient failure that happened before any model output."""
        if self._is_pre_response_rate_limit(exc):
            return "pre_response_rate_limit"
        status_int = self._exception_status_code(exc)
        if status_int is not None and 500 <= status_int <= 599:
            return "pre_response_server_error"
        lowered = str(exc).lower()
        if any(
            f"error code: {code}" in lowered or f"http {code}" in lowered
            for code in range(500, 600)
        ):
            return "pre_response_server_error"
        names = [klass.__name__.lower() for klass in type(exc).__mro__]
        # A client timeout is outcome-ambiguous (the provider may have accepted
        # and billed the request), so it is never a safe pre-response retry.
        # openai's APITimeoutError subclasses APIConnectionError, hence the
        # explicit exclusion before the connection check.
        # Exception: a streamed request that stalls between chunks. A chat
        # completion has no task side effect, so its only ambiguity is token
        # cost; Wave 1 showed stalls are otherwise fatal to the row.
        if any("timeout" in name for name in names):
            return "stream_idle_timeout" if (self._stream_idle_timeout_s is not None) else ""
        if any("remoteprotocol" in name or "incompleteread" in name for name in names):
            return "stream_connection_dropped" if (self._stream_idle_timeout_s is not None) else ""
        if any("connection" in name for name in names):
            return "pre_response_connection_error"
        return ""

    @staticmethod
    def _exception_status_code(exc: BaseException) -> int | None:
        try:
            status = getattr(exc, "status_code", None)
            return int(status) if status is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_journal_error_code(exc: BaseException) -> str | None:
        """Return an HTTP status label without copying provider error bodies."""
        current: BaseException | None = exc
        for _ in range(6):
            if current is None:
                break
            try:
                status = getattr(current, "status_code", None)
                status_int = int(status) if status is not None else None
            except (TypeError, ValueError):
                status_int = None
            if status_int is not None and 100 <= status_int <= 599:
                return f"http_{status_int}"
            current = current.__cause__
        return None

    @staticmethod
    def _safe_exception_request_id(exc: BaseException) -> str | None:
        """Extract one bounded request-ID scalar from an SDK exception."""
        current: BaseException | None = exc
        for _ in range(6):
            if current is None:
                break
            candidate: Any = None
            for name in ("_request_id", "request_id"):
                try:
                    candidate = getattr(current, name, None)
                except Exception:  # noqa: BLE001 - do not inspect exception bodies.
                    candidate = None
                if (
                    isinstance(candidate, str)
                    and candidate.strip()
                    and len(candidate) <= 512
                    and all(ord(char) >= 32 and ord(char) != 127 for char in candidate)
                ):
                    return candidate.strip()
            try:
                response = getattr(current, "response", None)
                headers = getattr(response, "headers", None)
                get_header = getattr(headers, "get", None)
                candidate = get_header("x-request-id") if callable(get_header) else None
            except Exception:  # noqa: BLE001 - read only the scalar correlation header.
                candidate = None
            if (
                isinstance(candidate, str)
                and candidate.strip()
                and len(candidate) <= 512
                and all(ord(char) >= 32 and ord(char) != 127 for char in candidate)
            ):
                return candidate.strip()
            current = current.__cause__
        return None

    def _create_with_bounded_pre_response_retry(
        self,
        request: dict[str, Any],
        *,
        event: dict[str, Any],
        first_started: float,
        first_reservation: Mapping[str, Any] | None,
    ) -> tuple[Any, Mapping[str, Any] | None, float | None]:
        """Retry transient pre-response failures, up to ``max_retries`` times.

        SDK retries remain disabled. Every failed create is recorded as its own
        attempt and its reservation remains conservative. Each retry re-enters
        the pacer and takes a separate budget reservation. Rate limits
        additionally apply the existing full-window blackout; 5xx and
        connection/timeout failures get the same retry envelope without
        pretending they were rate limits.

        Model output/parsing failures are outside this helper and are never
        retried.
        """
        reservation = first_reservation
        attempt_started = first_started
        retries_used = 0
        while True:
            request_started = time.monotonic()
            try:
                response = self._create(request)
            except KernelRunTimeout:
                raise
            except Exception as exc:
                event["provider_request_elapsed_s"] = max(
                    0.0, time.monotonic() - request_started,
                )
                if self._is_timeout_exception(exc):
                    remaining = remaining_run_s()
                    if remaining is not None and remaining <= 0.0:
                        raise KernelRunTimeout(
                            "task run deadline expired during provider request"
                        ) from exc
                self._record_rate_header_telemetry(event)
                retry_reason = self._pre_response_retry_reason(exc)
                if retries_used >= self._max_retries or not retry_reason:
                    raise
                failed = deepcopy(event)
                failed.update({
                    "status": "failed",
                    "attempt_phase": "terminal",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                    "provider_retry_scheduled": True,
                    "provider_retry_reason": retry_reason,
                    "provider_retry_status_code": self._exception_status_code(exc),
                    "provider_budget_settlement_status": (
                        "retained_failed_attempt" if reservation is not None else "not_reserved"
                    ),
                    "elapsed_s": round(time.monotonic() - attempt_started, 3),
                })
                if self._throughput_pacer is not None and retry_reason == "pre_response_rate_limit":
                    self._note_pacer_rate_limit()
                    failed["throughput_rate_limit_backoff_recorded"] = True
                if isinstance(self._throughput_pacer, SharedDeploymentTokenPacer):
                    self._throughput_pacer.mark_failed_reservation(
                        reservation_id=event.get("throughput_reservation_id"),
                    )
                self._record(failed)

                retries_used += 1
                event["provider_retry_from_attempt_ordinal"] = event["attempt_ordinal"]
                event["attempt_ordinal"] = int(event["attempt_ordinal"]) + 1
                event["status"] = "in_progress"
                event["attempt_phase"] = "create"
                event.pop("provider_rate_limit_headers", None)
                event["provider_retry_reason"] = retry_reason
                if self._throughput_pacer is not None:
                    estimate = int(event.get("throughput_estimated_tokens") or 0)
                    event.update(self._admit_throughput(estimated_tokens=estimate))
                if self._budget_guard is not None:
                    reservation = self._budget_guard.reserve(self._role, self._budget_view(request))
                    event["provider_budget_reservation"] = dict(reservation)
                attempt_started = time.monotonic()
                continue
            event["provider_request_elapsed_s"] = max(
                0.0, time.monotonic() - request_started,
            )
            return response, reservation, (attempt_started if retries_used else None)

    @staticmethod
    def _budget_view(request: Mapping[str, Any]) -> dict[str, Any]:
        """Accounting-only Responses-era alias; never part of the wire request."""
        view = dict(request)
        view["max_output_tokens"] = view["max_tokens"]
        return view

    def _settle_budget_success(
        self, reservation: Mapping[str, Any] | None, event: dict[str, Any],
    ) -> None:
        usage_in = event.get("input_tokens")
        usage_out = event.get("output_tokens")
        if (
            reservation is not None
            and getattr(getattr(self._budget_guard, "contract", None), "schema_version", None)
            == "aether.provider_budget.v2"
            and isinstance(usage_in, int)
            and isinstance(usage_out, int)
        ):
            settlement = self._budget_guard.settle_success(
                reservation, input_tokens=usage_in, output_tokens=usage_out,
            )
            event.update({
                "provider_budget_settlement_status": "settled_terminal_success_usage",
                "provider_budget_settlement": dict(settlement),
            })
        elif reservation is not None:
            event["provider_budget_settlement_status"] = "retained_missing_usage"

    @staticmethod
    def _is_cap_truncated_without_tool_call(response: Any) -> bool:
        choices = _field(response, "choices", None)
        if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or not choices:
            return False
        choice = choices[0]
        if str(_field(choice, "finish_reason", "") or "") not in {"length", "max_tokens"}:
            return False
        message = _field(choice, "message", None)
        return not (
            _field(message, "tool_calls", None) or _field(message, "function_call", None)
        )

    def _escalate_output_cap(
        self,
        request: dict[str, Any],
        response: Any,
        *,
        event: dict[str, Any],
        started: float,
        reservation: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], Any, Mapping[str, Any] | None, float] | None:
        """Re-issue one identical request with a doubled output cap.

        Only a ``length`` finish with no tool call qualifies. The capped
        response is recorded as its own attempt, settled with the pacer and
        budget guard, and never parsed or staged into continuity. Nothing
        model-visible changes: only ``max_tokens`` differs. Returns ``None``
        when the cap is already at the ceiling or the larger request would not
        fit the declared local throughput limit; the caller then surfaces the
        truncation as it would have without escalation.
        """
        original_cap = int(request["max_tokens"])
        escalated_cap = min(original_cap * 2, _MAX_ESCALATED_OUTPUT_TOKENS)
        if escalated_cap <= original_cap:
            event["provider_cap_escalation_skipped"] = "at_ceiling"
            return None
        escalated = deepcopy(request)
        escalated["max_tokens"] = escalated_cap
        escalated_payload, escalated_bytes = _canonical_json(escalated)
        estimate = 0
        if self._throughput_pacer is not None:
            estimate = self._throughput_pacer.approximate_request_tokens(
                len(escalated_bytes), escalated_cap,
            )
            if estimate > int(self._throughput_pacer.token_limit):
                event["provider_cap_escalation_skipped"] = "local_capacity"
                return None

        # Settle the capped attempt exactly like a received response.
        response_payload, response_bytes = _canonical_json(response)
        event["raw_provider_output"] = response_payload
        event["raw_provider_output_sha256"] = sha256(response_bytes).hexdigest()
        returned_model = str(_field(response, "model", "") or "").strip()
        event["returned_model"] = returned_model or None
        event["returned_model_known"] = bool(returned_model)
        event.update(_usage_telemetry(response))
        self._record_rate_header_telemetry(event)
        event["provider_finish_reason"] = "length"
        event["provider_output_cap_reached"] = True
        event["native_tool_call_observed_known"] = True
        event["native_tool_call_observed"] = False
        if isinstance(self._throughput_pacer, SharedDeploymentTokenPacer):
            event.update(self._throughput_pacer.reconcile_observed_usage(
                reservation_id=event.get("throughput_reservation_id"),
                input_tokens=event.get("input_tokens"),
                output_tokens=event.get("output_tokens"),
                requested_output_tokens=original_cap,
            ))
        elif self._throughput_pacer is not None:
            event.update(self._throughput_pacer.reconcile_success(
                input_tokens=event.get("input_tokens"),
                requested_output_tokens=original_cap,
                output_tokens=event.get("output_tokens"),
            ))
        self._settle_budget_success(reservation, event)
        capped = deepcopy(event)
        capped.update({
            "status": "failed",
            "attempt_phase": "terminal",
            "error_type": "ProviderOutputCapReached",
            "error": f"finish_reason=length at max_tokens={original_cap}; no tool call",
            "provider_cap_escalation": True,
            "provider_cap_escalation_scheduled": True,
            "provider_cap_original_max_tokens": original_cap,
            "provider_cap_escalated_max_tokens": escalated_cap,
            "elapsed_s": round(time.monotonic() - started, 3),
        })
        self._record(capped)

        # Admit the escalated request like any other request.
        event.update({
            "attempt_ordinal": int(event["attempt_ordinal"]) + 1,
            "attempt_phase": "create",
            "status": "in_progress",
            "provider_cap_escalation": True,
            "provider_cap_original_max_tokens": original_cap,
            "provider_cap_escalated_max_tokens": escalated_cap,
            "request": escalated_payload,
            "raw_provider_request": escalated_payload,
            "request_sha256": sha256(escalated_bytes).hexdigest(),
            "raw_provider_request_sha256": sha256(escalated_bytes).hexdigest(),
            "request_utf8_bytes": len(escalated_bytes),
            "max_output_tokens": escalated_cap,
            "raw_provider_output": None,
            "raw_provider_output_sha256": None,
            "output": None,
            "output_sha256": None,
            "native_tool_call_observed_known": False,
            "native_tool_call_observed": None,
            "provider_finish_reason": None,
            "provider_output_cap_reached": None,
            "provider_budget_settlement_status": None,
            "provider_budget_settlement": None,
            **_usage_telemetry(None),
        })
        event.pop("provider_retry_from_attempt_ordinal", None)
        event.pop("provider_retry_reason", None)
        event["provider_cap_escalation_from_attempt_ordinal"] = capped["attempt_ordinal"]
        if self._throughput_pacer is not None:
            event.update(self._admit_throughput(estimated_tokens=estimate))
        new_reservation: Mapping[str, Any] | None = None
        if self._budget_guard is not None:
            new_reservation = self._budget_guard.reserve(self._role, self._budget_view(escalated))
            event["provider_budget_reservation"] = dict(new_reservation)
        new_started = time.monotonic()
        response2, new_reservation, retry_started = self._create_with_bounded_pre_response_retry(
            escalated, event=event, first_started=new_started, first_reservation=new_reservation,
        )
        return (
            escalated,
            response2,
            new_reservation,
            retry_started if retry_started is not None else new_started,
        )

    def _managed_context_metric_events(
        self, key: tuple[str, str], snapshots: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        return [{
            "event_kind": "managed_context_checkpoint_metrics",
            "provider": "chat_completions",
            "role": self._role,
            "run_id": key[0],
            "task_id": key[1],
            **dict(snapshot),
        } for snapshot in snapshots]

    @property
    def configured_reasoning_effort(self) -> str | None:
        return self._effort

    @property
    def configured_temperature(self) -> float:
        return self._temperature

    def set_temperature_override(self, temperature: float | None) -> None:
        """Per-request temperature override (opt-in retry arm); ``None`` restores the configured temperature."""
        if temperature is not None and float(temperature) < 0:
            raise ValueError("temperature must be non-negative")
        self._temperature_override = None if temperature is None else float(temperature)

    def set_reasoning_effort_override(self, effort: str | None) -> None:
        """Per-turn effort override (opt-in arms only); ``None`` restores the configured effort."""
        if effort is not None and self._effort is None:
            raise ValueError("cannot override reasoning effort on a callable with no configured effort")
        self._effort_override = None if effort is None else str(effort)

    def set_solver_step(self, step: int, *, run_id: str, task_id: str) -> None:
        """Record the runtime step so a checkpoint can name where it was written."""
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key) or (
            self._context_policy not in _managed_context.MANAGED_CONTEXT_CHECKPOINT_POLICIES
            and self._capacity_reanchor_recovery_mode
            != _CAPACITY_REANCHOR_CHECKPOINT_AT_CAPACITY_V1
        ):
            return
        with self._scope_lock:
            self._managed_context_scopes.setdefault(key, _managed_context.ClmScope()).step = int(step)

    def drain_context_checkpoint_events(
        self, *, run_id: str, task_id: str,
    ) -> tuple[dict[str, Any], ...]:
        """Hand checkpoint outcomes to the runtime so it can record them as receipts."""
        key = (str(run_id).strip(), str(task_id).strip())
        with self._scope_lock:
            scope = self._managed_context_scopes.get(key)
            if scope is None:
                return ()
            rows = tuple(deepcopy(scope.events))
            scope.events.clear()
            return rows

    def _call(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        max_output_tokens: int | None,
        telemetry_scope: Mapping[str, Any] | None,
        call_generation: int | None = None,
    ) -> str:
        scope_key = self._scope_key(telemetry_scope)
        if (
            self._context_policy not in _managed_context.MANAGED_CONTEXT_CHECKPOINT_POLICIES
            or scope_key is None
            or not self._native_persistent_tools
        ):
            return self._call_request(
                messages, max_output_tokens=max_output_tokens,
                telemetry_scope=telemetry_scope, call_generation=call_generation,
            )
        with self._scope_lock:
            transport_mode = self._scope_transport_modes.get(scope_key, _TRANSPORT_FULL_SNAPSHOT)
        if transport_mode != _TRANSPORT_OBSERVATION_HISTORY_V1:
            raise ChatModelError("checkpoint context policy requires observation_history_v1 transport")
        self._managed_context_maybe_checkpoint(
            messages, scope_key=scope_key, max_output_tokens=max_output_tokens,
            telemetry_scope=telemetry_scope, call_generation=call_generation,
        )
        result = self._call_request(
            messages, max_output_tokens=max_output_tokens,
            telemetry_scope=telemetry_scope, call_generation=call_generation,
        )
        telemetry = self.last_call_telemetry
        request_messages = ((telemetry.get("request") or {}).get("messages")) or ()
        with self._scope_lock:
            self._managed_context_scopes.setdefault(scope_key, _managed_context.ClmScope()).note_response(
                input_tokens=telemetry.get("input_tokens"),
                cached_input_tokens=telemetry.get("cached_input_tokens"),
                message_count=len(request_messages),
            )
        return result

    def _managed_context_maybe_checkpoint(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        scope_key: tuple[str, str],
        max_output_tokens: int | None,
        telemetry_scope: Mapping[str, Any] | None,
        call_generation: int | None,
    ) -> None:
        with self._scope_lock:
            scope = self._managed_context_scopes.setdefault(scope_key, _managed_context.ClmScope())
            committed = self._continuity_states.get(scope_key)
            has_history = committed is not None and bool(committed.get("history"))
            pending = scope_key in self._pending_continuity_states
            step = scope.step
        if not has_history or pending:
            return
        prepared = self._prepare_messages(messages, telemetry_scope=telemetry_scope)
        uncached_policy = (
            self._context_policy == _managed_context.MANAGED_CONTEXT_POLICY_CHECKPOINT_UNCACHED_V1
        )
        estimate = (
            scope.eligible_uncached_estimate(prepared)
            if uncached_policy else scope.eligible_estimate(prepared)
        )
        if estimate is None or estimate < scope.trigger_threshold(
            self._managed_context_trigger_tokens, uncached=uncached_policy,
        ):
            return
        attempts: list[dict[str, Any]] = []
        for attempt in range(1, _managed_context.MANAGED_CONTEXT_MAX_CHECKPOINT_ATTEMPTS + 1):
            try:
                content = self._call_request(
                    messages, max_output_tokens=max_output_tokens,
                    telemetry_scope=telemetry_scope, call_generation=call_generation,
                    checkpoint_request=True,
                )
            except (RunCancellationRequested, KernelRunTimeout, ChatRouteIdentityError):
                raise
            except ChatModelError as exc:
                attempts.append({"attempt": attempt, "error": str(exc)[:500]})
                continue
            call_input = self.last_call_telemetry.get("input_tokens")
            call_cached_input = self.last_call_telemetry.get("cached_input_tokens")
            checkpoint = _managed_context.checkpoint_message(scope.ordinal + 1, step, content)
            with self._scope_lock:
                state = self._continuity_states.get(scope_key)
                if state is None or scope_key in self._pending_continuity_states:
                    raise ChatModelError("chat_continuity_state_changed_during_checkpoint")
                state["history"] = _managed_context.reshape_history(
                    state["history"], checkpoint, keep_exchanges=self._managed_context_keep_exchanges,
                )
                metric = scope.record_checkpoint(
                    step=step, content=content, trigger_estimate=estimate,
                    call_input_tokens=call_input,
                    call_cached_input_tokens=call_cached_input,
                    attempts=attempt,
                    trigger_basis=("uncached_input" if uncached_policy else "total_input"),
                )
                self._continuity_admission_events.extend(
                    self._managed_context_metric_events(scope_key, [_managed_context.public_metric(metric)])
                )
            return
        with self._scope_lock:
            scope.record_failure(step=step, attempts=attempts)

    def _capacity_checkpoint_recovery(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        pre_messages: Sequence[Mapping[str, Any]],
        max_output_tokens: int | None,
        telemetry_scope: Mapping[str, Any] | None,
        call_generation: int | None,
        scope_key: tuple[str, str],
        previous_call_id: str,
        pre_estimate: int,
        token_limit: int,
        committed: Mapping[str, Any] | None,
    ) -> _capckpt.CapacityCheckpointOutcome:
        """Ask the model for a checkpoint at the capacity boundary and rebuild around it.

        A failed or invalid checkpoint returns an outcome with a reason (the
        caller falls back) and records ``capacity_checkpoint_failed``.
        Cancellation, deadline and route-identity errors propagate after the
        committed continuity state is restored.
        """
        pacer = self._throughput_pacer

        def estimate(candidate: Mapping[str, Any]) -> int:
            _, candidate_bytes = _canonical_json(candidate)
            return int(pacer.approximate_request_tokens(
                len(candidate_bytes), int(max_output_tokens or 0),
            ))

        def estimate_view(view: list[dict[str, Any]]) -> int:
            return estimate(self._request(
                messages, max_output_tokens, telemetry_scope=telemetry_scope,
                checkpoint_request=True, transcript_override=view,
            ))

        def estimate_rebuilt(rebuilt: list[dict[str, Any]]) -> int:
            return estimate(self._request(
                rebuilt, max_output_tokens, telemetry_scope=telemetry_scope,
            ))

        def dispatch(view: list[dict[str, Any]]) -> str:
            try:
                return self._call_request(
                    messages, max_output_tokens=max_output_tokens,
                    telemetry_scope=telemetry_scope, call_generation=call_generation,
                    checkpoint_request=True, checkpoint_transcript=view,
                )
            except (RunCancellationRequested, KernelRunTimeout, ChatRouteIdentityError):
                raise
            except ChatModelError as exc:
                raise _capckpt.CapacityCheckpointUnavailable(
                    f"{type(exc).__name__}: {str(exc)[:300]}"
                ) from exc

        with self._scope_lock:
            managed_context_scope = self._managed_context_scopes.setdefault(scope_key, _managed_context.ClmScope())
            step, ordinal = managed_context_scope.step, managed_context_scope.ordinal + 1
        try:
            outcome = _capckpt.run_capacity_checkpoint(
                fresh_messages=_normalize_messages(messages),
                pre_messages=pre_messages,
                packet_prefix=_CONTEXT_PACKET_PREFIX,
                token_limit=token_limit,
                pre_estimated_tokens=pre_estimate,
                ordinal=ordinal,
                step=step,
                select_exchanges=lambda rows, count: _recent_complete_tool_exchanges(
                    rows, count=count,
                ),
                estimate_view=estimate_view,
                estimate_rebuilt=estimate_rebuilt,
                dispatch=dispatch,
            )
        except BaseException:
            if committed is not None:
                with self._scope_lock:
                    self._continuity_states.setdefault(scope_key, deepcopy(dict(committed)))
            raise
        event_args = {
            "role": self._role, "run_id": scope_key[0], "task_id": scope_key[1],
            "previous_call_id": previous_call_id, "outcome": outcome,
            "token_limit": token_limit,
        }
        with self._scope_lock:
            if outcome.ok:
                telemetry = self.last_call_telemetry
                metric = managed_context_scope.record_checkpoint(
                    step=step, content=outcome.content, trigger_estimate=pre_estimate,
                    call_input_tokens=telemetry.get("input_tokens"),
                    call_cached_input_tokens=telemetry.get("cached_input_tokens"),
                    attempts=1, trigger_basis="capacity_boundary",
                )
                self._continuity_admission_events.append(_capckpt.written_event(**event_args))
                self._continuity_admission_events.extend(
                    self._managed_context_metric_events(scope_key, [_managed_context.public_metric(metric)])
                )
            else:
                self._continuity_admission_events.append(_capckpt.failure_event(**event_args))
        return outcome

    def _call_request(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        max_output_tokens: int | None,
        telemetry_scope: Mapping[str, Any] | None,
        call_generation: int | None = None,
        checkpoint_request: bool = False,
        checkpoint_transcript: Sequence[Mapping[str, Any]] | None = None,
    ) -> str:
        logical_call_id = self._logical_call_id()
        request_build_started = time.monotonic()
        request = self._request(
            messages, max_output_tokens, telemetry_scope=telemetry_scope,
            checkpoint_request=checkpoint_request,
            transcript_override=checkpoint_transcript,
        )
        request_payload, request_bytes = _canonical_json(request)
        pacing: dict[str, Any] = {}
        request_build_elapsed_s: float | None = None
        capacity_reanchor: dict[str, Any] = {}
        capacity_overflow = False
        reanchor_scope_key: tuple[str, str] | None = None
        reanchor_committed: Mapping[str, Any] | None = None
        if self._throughput_pacer is not None:
            estimated_tokens = self._throughput_pacer.approximate_request_tokens(
                len(request_bytes), int(max_output_tokens or 0),
            )
            token_limit = int(self._throughput_pacer.token_limit)
            scope_key = self._scope_key(telemetry_scope)
            if (
                estimated_tokens > token_limit
                and scope_key is not None
                and self._native_persistent_tools
                and not checkpoint_request
                and self._capacity_overflow_action == _CAPACITY_OVERFLOW_REANCHOR
            ):
                pre_reanchor_request_messages = deepcopy(
                    list((request_payload or {}).get("messages") or ())
                )
                previous_call_id = ""
                committed_history: list[dict[str, Any]] = []
                with self._scope_lock:
                    if scope_key in self._pending_continuity_states:
                        raise ChatModelError(
                            "chat_continuity_pending_candidate_requires_admission"
                        )
                    committed = self._continuity_states.pop(scope_key, None)
                    if committed is not None:
                        reanchor_scope_key = scope_key
                        reanchor_committed = deepcopy(committed)
                        previous_call_id = str(committed.get("call_id") or "")
                        committed_history = deepcopy(list(committed.get("history") or ()))
                        self._continuity_admission_events.append({
                            "event_kind": "chat_continuity_capacity_reanchor",
                            "provider": "chat_completions",
                            "role": self._role,
                            "run_id": scope_key[0],
                            "task_id": scope_key[1],
                            "persistent_continuity_mode": "fresh_current_context_at_capacity_boundary",
                            "persistent_continuity_previous_call_id": previous_call_id,
                            "throughput_pre_reanchor_estimated_tokens": int(estimated_tokens),
                            "throughput_token_limit": token_limit,
                        })
                if previous_call_id:
                    pre_reanchor_estimate = int(estimated_tokens)
                    request = self._request(
                        messages, max_output_tokens, telemetry_scope=telemetry_scope,
                    )
                    request_payload, request_bytes = _canonical_json(request)
                    estimated_tokens = self._throughput_pacer.approximate_request_tokens(
                        len(request_bytes), int(max_output_tokens or 0),
                    )
                    recovery_meta: dict[str, Any] | None = None
                    effective_recovery_mode = self._capacity_reanchor_recovery_mode
                    checkpoint_fallback_reason = ""
                    checkpoint_outcome: _capckpt.CapacityCheckpointOutcome | None = None
                    if effective_recovery_mode == _CAPACITY_REANCHOR_CHECKPOINT_AT_CAPACITY_V1:
                        checkpoint_outcome = self._capacity_checkpoint_recovery(
                            messages=messages,
                            pre_messages=pre_reanchor_request_messages,
                            max_output_tokens=max_output_tokens,
                            telemetry_scope=telemetry_scope,
                            call_generation=call_generation,
                            scope_key=scope_key,
                            previous_call_id=previous_call_id,
                            pre_estimate=pre_reanchor_estimate,
                            token_limit=token_limit,
                            committed=reanchor_committed,
                        )
                        if checkpoint_outcome.ok:
                            request = self._request(
                                checkpoint_outcome.rebuilt_messages, max_output_tokens,
                                telemetry_scope=telemetry_scope,
                            )
                            request_payload, request_bytes = _canonical_json(request)
                            estimated_tokens = checkpoint_outcome.estimated_tokens
                            recovery_meta = dict(checkpoint_outcome.meta)
                        else:
                            effective_recovery_mode = _CAPACITY_REANCHOR_RECENT_EXCHANGES_V1
                            checkpoint_fallback_reason = checkpoint_outcome.reason
                    if (
                        effective_recovery_mode
                        == _CAPACITY_REANCHOR_RECENT_EXCHANGES_V1
                    ):
                        exchange_messages = _recent_complete_tool_exchanges(
                            pre_reanchor_request_messages,
                            count=_CAPACITY_RECENT_EXCHANGE_COUNT,
                        )
                        recovery_meta = {
                            "mode": effective_recovery_mode,
                            **(
                                {
                                    "requested_mode": self._capacity_reanchor_recovery_mode,
                                    "capacity_checkpoint_failed": checkpoint_fallback_reason,
                                }
                                if checkpoint_fallback_reason else {}
                            ),
                            "required_exchange_count": _CAPACITY_RECENT_EXCHANGE_COUNT,
                            "selected_exchange_count": sum(
                                1 for index, row in enumerate(exchange_messages[:-1])
                                if row.get("role") == "assistant"
                                and exchange_messages[index + 1].get("role") == "tool"
                            ),
                            "semantic_ranking": False,
                            "exact_messages": True,
                        }
                        exchange_pair_count = sum(
                            1 for index, row in enumerate(exchange_messages[:-1])
                            if row.get("role") == "assistant"
                            and exchange_messages[index + 1].get("role") == "tool"
                        )
                        if exchange_pair_count == _CAPACITY_RECENT_EXCHANGE_COUNT:
                            base_messages = list(messages)
                            packet_indices = [
                                i for i, row in enumerate(base_messages)
                                if isinstance(row.get("content"), str)
                                and row["content"].startswith(_CONTEXT_PACKET_PREFIX)
                            ]
                            base_prefix = (
                                base_messages[:packet_indices[-1]]
                                if packet_indices else base_messages[:-1]
                            )
                            augmented_messages = [
                                *base_prefix,
                                *exchange_messages,
                            ]
                            candidate_request = self._request(
                                augmented_messages,
                                max_output_tokens,
                                telemetry_scope=telemetry_scope,
                            )
                            candidate_payload, candidate_bytes = _canonical_json(candidate_request)
                            candidate_estimate = self._throughput_pacer.approximate_request_tokens(
                                len(candidate_bytes), int(max_output_tokens or 0),
                            )
                            recovery_meta.update({
                                "request_utf8_bytes_with_recovery": len(candidate_bytes),
                                "estimated_tokens_with_recovery": int(candidate_estimate),
                            })
                            if candidate_estimate <= token_limit:
                                request = candidate_request
                                request_payload = candidate_payload
                                request_bytes = candidate_bytes
                                estimated_tokens = candidate_estimate
                                recovery_meta["admission"] = "included_exact_four"
                            else:
                                # P1 contract: four complete exchanges are the
                                # minimum admitted window. Never silently shed
                                # one to make the request fit.
                                request = candidate_request
                                request_payload = candidate_payload
                                request_bytes = candidate_bytes
                                estimated_tokens = candidate_estimate
                                recovery_meta["admission"] = "rejected_exact_four_over_capacity"
                        else:
                            recovery_meta["admission"] = "unavailable_exact_four"
                            # Do not silently dispatch a fresh-only request. The
                            # declared recent-exchange mode requires the exact
                            # window; an unconstructable window is a truthful
                            # harness capacity failure.
                            estimated_tokens = max(int(estimated_tokens), token_limit + 1)
                    elif (
                        self._capacity_reanchor_recovery_mode
                        == _CAPACITY_REANCHOR_RECENT_OBSERVATIONS_V1
                    ):
                        base_messages = list(messages)
                        recovery_meta = {
                            "mode": self._capacity_reanchor_recovery_mode,
                            "admission": "empty",
                        }
                        # Prefer the full frozen bound, then shed the oldest
                        # recovered item until the augmented fresh request fits
                        # the same declared single-request throughput limit.
                        for recovery_items in range(_CAPACITY_RECOVERY_MAX_ITEMS, 0, -1):
                            recovery_message, candidate_meta = _capacity_reanchor_recovery_message(
                                committed_history,
                                base_messages,
                                max_items=recovery_items,
                            )
                            recovery_meta = {
                                "mode": self._capacity_reanchor_recovery_mode,
                                **candidate_meta,
                            }
                            if recovery_message is None:
                                break
                            augmented_messages = [
                                *base_messages[:-1],
                                recovery_message,
                                base_messages[-1],
                            ]
                            candidate_request = self._request(
                                augmented_messages,
                                max_output_tokens,
                                telemetry_scope=telemetry_scope,
                            )
                            candidate_payload, candidate_bytes = _canonical_json(candidate_request)
                            candidate_estimate = self._throughput_pacer.approximate_request_tokens(
                                len(candidate_bytes), int(max_output_tokens or 0),
                            )
                            if candidate_estimate <= token_limit:
                                request = candidate_request
                                request_payload = candidate_payload
                                request_bytes = candidate_bytes
                                estimated_tokens = candidate_estimate
                                recovery_meta.update({
                                    "admission": "included",
                                    "admitted_max_items": recovery_items,
                                    "request_utf8_bytes_with_recovery": len(candidate_bytes),
                                    "estimated_tokens_with_recovery": int(candidate_estimate),
                                })
                                break
                            recovery_meta.update({
                                "admission": "shed_for_capacity",
                                "last_rejected_estimated_tokens": int(candidate_estimate),
                            })
                    capacity_reanchor = {
                        "throughput_capacity_reanchor": True,
                        "throughput_pre_reanchor_estimated_tokens": pre_reanchor_estimate,
                        "throughput_post_reanchor_estimated_tokens": int(estimated_tokens),
                        "throughput_capacity_reanchor_previous_call_id": previous_call_id,
                    }
                    if recovery_meta is not None:
                        capacity_reanchor["throughput_capacity_reanchor_recovery"] = recovery_meta
            capacity_overflow = estimated_tokens > token_limit
            request_build_elapsed_s = max(0.0, time.monotonic() - request_build_started)
            if capacity_overflow:
                # A rejected re-anchor did not dispatch a candidate. Restore
                # the committed state so the next call cannot lose the last
                # admitted native history merely because local capacity was
                # exceeded or the exact recovery window was unavailable.
                if reanchor_scope_key is not None and reanchor_committed is not None:
                    with self._scope_lock:
                        self._continuity_states.setdefault(
                            reanchor_scope_key,
                            deepcopy(dict(reanchor_committed)),
                        )
                pacing = {
                    "throughput_token_limit": token_limit,
                    "throughput_window_s": self._throughput_pacer.window_s,
                    "throughput_estimated_tokens": int(estimated_tokens),
                    "throughput_single_request_admission": "rejected_local_capacity",
                }
            else:
                pacing = self._admit_throughput(
                    estimated_tokens=estimated_tokens,
                )
        if request_build_elapsed_s is None:
            request_build_elapsed_s = max(0.0, time.monotonic() - request_build_started)
        event: dict[str, Any] = {
            "event_kind": "provider_attempt",
            "provider": "chat_completions",
            "api_mode": "chat_completions",
            "deployment": self._deployment,
            "requested_model": self._deployment,
            "expected_returned_model": self._expected_returned_model,
            "research_runtime_config_sha256": self._research_runtime_config_sha256 or None,
            "returned_model": None,
            "returned_model_known": False,
            "role": self._role,
            "chat_reality_transport_mode": self._scope_transport_modes.get(
                self._scope_key(telemetry_scope), _TRANSPORT_FULL_SNAPSHOT,
            ) if self._scope_key(telemetry_scope) is not None else _TRANSPORT_FULL_SNAPSHOT,
            "logical_call_id": logical_call_id,
            "attempt_ordinal": 1,
            "attempt_phase": "create",
            "status": "in_progress",
            "request": request_payload,
            "raw_provider_request": request_payload,
            "request_sha256": sha256(request_bytes).hexdigest(),
            "raw_provider_request_sha256": sha256(request_bytes).hexdigest(),
            "request_utf8_bytes": len(request_bytes),
            "provider_request_build_elapsed_s": request_build_elapsed_s,
            "max_output_tokens": int(max_output_tokens or 0),
            "native_tool_call_observed_known": False,
            "native_tool_call_observed": None,
            "output": None,
            "output_sha256": None,
            "raw_provider_output": None,
            **_usage_telemetry(None),
            **pacing,
            **capacity_reanchor,
        }
        event["request_context_anatomy"] = _request_context_anatomy(request_payload or {})
        if self._session_affinity_key is not None:
            event["session_affinity_key_sha256_12"] = key_sha256_12(self._session_affinity_key)
        if checkpoint_request:
            event["context_checkpoint_call"] = True
        if telemetry_scope:
            event.update({"run_id": telemetry_scope.get("run_id"), "task_id": telemetry_scope.get("task_id")})
        if call_generation is not None:
            event["call_generation"] = int(call_generation)
        reservation: Mapping[str, Any] | None = None
        started = time.monotonic()
        provider_dispatch_started = False
        shared_reservation_settled = False
        try:
            self._raise_if_run_cancelled()
            if capacity_overflow:
                if self._capacity_overflow_action == _CAPACITY_OVERFLOW_M_TREE_EPOCH:
                    capacity_error = (
                        "m_tree_epoch_overflow: Solver request exceeds its declared "
                        "M-TREE epoch capacity"
                    )
                elif self._capacity_overflow_action == _CAPACITY_OVERFLOW_CONTEXT_FILE:
                    capacity_error = (
                        "managed_context_context_overflow: Solver request exceeds its declared "
                        "context capacity"
                    )
                else:
                    capacity_error = (
                        "harness_context_capacity: chat request exceeds declared provider "
                        "throughput limit"
                    )
                if capacity_reanchor.get("throughput_capacity_reanchor") is True:
                    capacity_error += " after fresh current-context re-anchor"
                raise ChatContextCapacityError(
                    capacity_error
                )
            if self._budget_guard is not None:
                # ProviderBudgetGuard uses the Responses-era field name as its
                # canonical reservation contract.  Keep that accounting-only
                # alias out of the Chat wire request.
                reservation = self._budget_guard.reserve(self._role, self._budget_view(request))
                event["provider_budget_reservation"] = dict(reservation)
            self._raise_if_run_cancelled()
            provider_dispatch_started = True
            response, retry_reservation, retry_started = self._create_with_bounded_pre_response_retry(
                request,
                event=event,
                first_started=started,
                first_reservation=reservation,
            )
            if retry_reservation is not None:
                reservation = retry_reservation
            if retry_started is not None:
                started = retry_started
            if self._is_cap_truncated_without_tool_call(response):
                if self._disable_output_cap_escalation:
                    event["provider_cap_escalation_disabled"] = True
                else:
                    escalation = self._escalate_output_cap(
                        request, response, event=event, started=started, reservation=reservation,
                    )
                    if escalation is not None:
                        request, response, reservation, started = escalation
                        max_output_tokens = int(request["max_tokens"])
                        shared_reservation_settled = False
            # A synchronous SDK call cannot be revoked by the surrounding
            # thread, but its client timeout bounds the wait. Do not admit a
            # response that arrived after task cancellation/deadline.
            self._raise_if_run_cancelled()
            response_payload, response_bytes = _canonical_json(response)
            event["raw_provider_output"] = response_payload
            event["raw_provider_output_sha256"] = sha256(response_bytes).hexdigest()
            # OpenAI SDK response models expose the response header's request
            # identifier as a scalar attribute. Preserve that identifier for
            # trace correlation without retaining the header mapping.
            if self._capture_provider_request_id:
                provider_request_id = _field(response, "provider_request_id")
                if not isinstance(provider_request_id, str) or not provider_request_id.strip():
                    provider_request_id = _field(response, "_request_id")
                if not isinstance(provider_request_id, str) or not provider_request_id.strip():
                    provider_request_id = _field(response, "request_id")
                if (
                    isinstance(provider_request_id, str)
                    and provider_request_id.strip()
                    and len(provider_request_id) <= 512
                    and all(ord(char) >= 32 and ord(char) != 127 for char in provider_request_id)
                ):
                    event["provider_request_id"] = provider_request_id.strip()
            returned_model = str(_field(response, "model", "") or "").strip()
            event["returned_model"] = returned_model or None
            event["returned_model_known"] = bool(returned_model)
            # Usage belongs to the received provider response even when its
            # action cannot be parsed or its identity is rejected. Keep failed
            # reservations conservative, but never erase observed usage.
            event.update(_usage_telemetry(response))
            self._record_rate_header_telemetry(event)
            choices = _field(response, "choices", None)
            choice = choices[0] if isinstance(choices, Sequence) and not isinstance(choices, (str, bytes)) and choices else None
            finish_reason = str(_field(choice, "finish_reason", "") or "") if choice is not None else ""
            event["provider_finish_reason"] = finish_reason or None
            event["provider_output_cap_reached"] = finish_reason in {"length", "max_tokens"}
            message = _field(choice, "message", None) if choice is not None else None
            if message is not None:
                event["native_tool_call_observed_known"] = True
                event["native_tool_call_observed"] = bool(
                    _field(message, "tool_calls", None) or _field(message, "function_call", None)
                )
            self._report_headers_to_pacer(event)
            if isinstance(self._throughput_pacer, SharedDeploymentTokenPacer):
                event.update(self._throughput_pacer.reconcile_observed_usage(
                    reservation_id=event.get("throughput_reservation_id"),
                    input_tokens=event.get("input_tokens"),
                    output_tokens=event.get("output_tokens"),
                    requested_output_tokens=int(max_output_tokens or 0),
                ))
                shared_reservation_settled = True
            elif self._throughput_pacer is not None:
                event.update(self._throughput_pacer.reconcile_success(
                    input_tokens=event.get("input_tokens"),
                    requested_output_tokens=int(max_output_tokens or 0),
                    output_tokens=event.get("output_tokens"),
                ))
            if (returned_model or self._require_returned_model) and returned_model != self._expected_returned_model:
                raise ChatRouteIdentityError(
                    "provider_route_identity_mismatch: "
                    f"deployment={self._deployment!r} "
                    f"expected={self._expected_returned_model!r} returned={returned_model!r}"
                )
            scope_key = self._scope_key(telemetry_scope)
            with self._scope_lock:
                working_context_mode = (
                    self._scope_working_context_modes.get(
                        scope_key, _SOLVER_WORKING_CONTEXT_OFF,
                    )
                    if scope_key is not None
                    else _SOLVER_WORKING_CONTEXT_OFF
                )
            if working_context_mode != _SOLVER_WORKING_CONTEXT_OFF:
                event["solver_working_context_mode"] = working_context_mode
            if checkpoint_request:
                try:
                    result, receipt = _managed_context.extract_checkpoint_content(response)
                except _managed_context.CheckpointRejected as exc:
                    raise ChatModelOutputError(str(exc)) from exc
            else:
                result, receipt = self._parse(
                    response,
                    solver_working_context_mode=working_context_mode,
                    available_tool_names=frozenset(
                        str(_field(_field(tool, "function", {}), "name", "") or "")
                        for tool in (request.get("tools") or ())
                    ),
                )
            completion_card = receipt.pop("challenger_completion_card", None)
            if scope_key is not None:
                with self._scope_lock:
                    if completion_card is None:
                        self._completion_cards.pop(scope_key, None)
                    else:
                        self._completion_cards[scope_key] = completion_card
            event.update(receipt)
            self._settle_budget_success(reservation, event)
            if not checkpoint_request:
                self._stage_pending_response(
                    scope_key=self._scope_key(telemetry_scope),
                    response=response,
                    receipt=receipt,
                    request_messages=request.get("messages") or (),
                )
            event.update({
                "status": "completed",
                "attempt_phase": "terminal",
                "output": result,
                "output_sha256": sha256(result.encode("utf-8")).hexdigest(),
            })
            return result
        except ProviderBudgetError as exc:
            event.update({
                "status": "budget_denied",
                "attempt_phase": "admission",
                "provider_budget_admission": "denied",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
            })
            raise
        except Exception as exc:
            if self._throughput_pacer is not None:
                lowered = str(exc).lower()
                if "429" in lowered or "rate limit" in lowered or "rate_limit" in lowered:
                    self._note_pacer_rate_limit()
                    event["throughput_rate_limit_backoff_recorded"] = True
            event.update({
                "status": "failed",
                "attempt_phase": "terminal",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
            })
            error_code = self._safe_journal_error_code(exc)
            if error_code is not None:
                event["error_code"] = error_code
            if self._capture_provider_request_id:
                provider_request_id = self._safe_exception_request_id(exc)
                if provider_request_id is not None:
                    event["provider_request_id"] = provider_request_id
            if isinstance(exc, (RunCancellationRequested, KernelRunTimeout, ChatModelError)):
                raise
            raise ChatModelError(f"chat.completions.create failed: {exc}") from exc
        finally:
            if isinstance(self._throughput_pacer, SharedDeploymentTokenPacer) and not shared_reservation_settled:
                reservation_id = event.get("throughput_reservation_id")
                try:
                    if provider_dispatch_started:
                        self._throughput_pacer.mark_failed_reservation(reservation_id=reservation_id)
                    else:
                        self._throughput_pacer.release_reservation(reservation_id=reservation_id)
                except Exception as limiter_exc:
                    event["throughput_limiter_settlement_error"] = str(limiter_exc)[:500]
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            self._record(event)

    def _parse(
        self,
        response: Any,
        *,
        solver_working_context_mode: str = _SOLVER_WORKING_CONTEXT_OFF,
        available_tool_names: frozenset[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        choices = _field(response, "choices", None)
        if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
            raise ChatModelOutputError("choice_collection_invalid")
        if len(choices) != 1:
            raise ChatModelOutputError("choice_count_invalid", f"expected=1 actual={len(choices)}")
        choice = choices[0]
        message = _field(choice, "message")
        if message is None:
            raise ChatModelOutputError("choice_message_missing")
        finish_reason = str(_field(choice, "finish_reason", "") or "")
        if finish_reason in {"length", "max_tokens", "content_filter"}:
            reasoning = _field(message, "reasoning_content", None)
            used = _usage_telemetry(response).get("output_tokens")
            raise ChatModelOutputError(
                "provider_output_truncated", finish_reason,
                reasoning_content=reasoning if isinstance(reasoning, str) else "",
                output_tokens=used if isinstance(used, int) and not isinstance(used, bool) else None,
            )
        tool_calls = _field(message, "tool_calls", None) or ()
        legacy_call = _field(message, "function_call", None)
        if legacy_call is not None:
            tool_calls = [legacy_call]
        if self._native_persistent_tools:
            if finish_reason != "tool_calls" or len(tool_calls) != 1:
                raise ChatModelOutputError(
                    "native_tool_call_count_invalid",
                    f"finish_reason={finish_reason!r} count={len(tool_calls)}",
                )
            working_context_mode = str(
                solver_working_context_mode or _SOLVER_WORKING_CONTEXT_OFF
            ).strip().lower()
            if working_context_mode not in _SOLVER_WORKING_CONTEXT_MODES:
                raise ChatModelOutputError("solver_working_context_mode_invalid")
            raw_content = _field(message, "content", None)
            if raw_content is not None and not isinstance(raw_content, str):
                raise ChatModelOutputError("native_tool_content_format_invalid")
            if (
                raw_content
                and working_context_mode != _SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1
            ):
                raise ChatModelOutputError("native_tool_mixed_output")
            name, arguments = _extract_tool_call(tool_calls[0])
            self._last_protocol_salvage = None
            working_notes: str | None = None
            canonical_arguments = arguments
            salvage_provenance: dict[str, Any] | None = None
            if self._tolerant_argument_parsing:
                canonical_arguments, salvage_provenance = recover_argument_object(arguments)
            if _working_context_uses_tool_notes(working_context_mode):
                try:
                    payload = json.loads(canonical_arguments)
                except (TypeError, ValueError) as exc:
                    raise ChatModelOutputError(
                        "solver_working_notes_arguments_invalid", str(exc),
                        rejected_tool_name=name,
                        rejected_tool_arguments=arguments,
                    ) from exc
                if not isinstance(payload, Mapping):
                    raise ChatModelOutputError(
                        "solver_working_notes_arguments_invalid", "tool arguments must be one JSON object",
                        rejected_tool_name=name,
                        rejected_tool_arguments=arguments,
                    )
                raw_note = payload.get("working_notes")
                if not isinstance(raw_note, str) or not raw_note.strip():
                    raise ChatModelOutputError(
                        "solver_working_notes_missing", name,
                        rejected_tool_name=name,
                        rejected_tool_arguments=arguments,
                    )
                working_notes = raw_note
                clean_payload = dict(payload)
                clean_payload.pop("working_notes", None)
                canonical_arguments = json.dumps(
                    clean_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
            if (
                self._tool_surface_mode in {
                    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_V1, PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_V1,
                    PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1,
                }
                and name not in (available_tool_names or frozenset())
            ):
                raise ChatModelOutputError(
                    "native_tool_call_not_in_surface",
                    name,
                    rejected_tool_name=name,
                    rejected_tool_arguments=arguments,
                )
            try:
                canonical, receipt = canonicalize_persistent_direct_tool_call(
                    name,
                    canonical_arguments,
                    allow_m_tree_zoom="zoom" in (available_tool_names or frozenset()),
                    allow_edit_context="edit_context" in (available_tool_names or frozenset()),
                    allow_completion_card=self._finish_completion_card,
                    allow_edit_file="edit_file" in (available_tool_names or frozenset()),
                    allow_flat_tool_surface=(
                        self._tool_surface_mode == PERSISTENT_TOOL_SURFACE_STATIC_KERNEL_EDIT_FLAT_V1
                    ),
                    allow_background_jobs=(selected_long_command_mode() == LONG_COMMAND_BACKGROUND_V1),
                )
            except PCRProviderProtocolError as exc:
                raise ChatModelOutputError(
                    exc.code,
                    exc.detail,
                    rejected_tool_name=name,
                    rejected_tool_arguments=arguments,
                ) from exc
            receipt = dict(receipt)
            if working_notes is not None:
                encoded_note = working_notes.encode("utf-8")
                receipt.update({
                    "solver_working_notes": working_notes,
                    "solver_working_notes_utf8_bytes": len(encoded_note),
                    "solver_working_notes_sha256": sha256(encoded_note).hexdigest(),
                })
            receipt.update({
                "structured_output_mode": "persistent_v0_direct_native_tools_chat_completions",
                "native_tool_name": name,
                "native_tool_call_count": 1,
                "native_tool_call_id": str(_field(tool_calls[0], "id", "") or ""),
                "native_tool_call_observed_known": True,
                "native_tool_call_observed": True,
                "finish_reason": finish_reason,
            })
            if salvage_provenance is not None:
                receipt["protocol_salvage"] = dict(salvage_provenance)
                self._last_protocol_salvage = dict(salvage_provenance)
            return canonical, receipt
        if tool_calls:
            raise ChatModelOutputError("unexpected_native_tool_call")
        if finish_reason != "stop":
            raise ChatModelOutputError("finish_reason_invalid", finish_reason)
        text = _extract_content(message)
        if not text:
            raise ChatModelOutputError("assistant_content_missing")
        return text, {
            "structured_output_mode": "chat_completions_text",
            "finish_reason": finish_reason,
            "native_tool_call_observed_known": False,
        }

    def take_protocol_salvage(self) -> dict[str, Any] | None:
        """Consume provenance for the most recently parsed recovered tool call."""
        provenance = self._last_protocol_salvage
        self._last_protocol_salvage = None
        return None if provenance is None else dict(provenance)

    def clear_continuity_scope(self, *, run_id: str, task_id: str) -> None:
        """Release only the explicit transcript owned by one task/run scope."""
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            return
        with self._scope_lock:
            self._continuity_states.pop(key, None)
            self._pending_continuity_states.pop(key, None)
            self._scope_completion_modes.pop(key, None)
            self._scope_commitment_modes.pop(key, None)
            self._scope_disposition_modes.pop(key, None)
            self._scope_record_modes.pop(key, None)
            self._scope_working_context_modes.pop(key, None)
            self._scope_context_file_modes.pop(key, None)
            self._completion_cards.pop(key, None)
            self._managed_context_scopes.pop(key, None)

    def close_run_transport(self) -> None:
        close = getattr(self._transport, "close", None)
        if callable(close):
            close()


def _normalize_endpoint(raw: str, *, azure: bool) -> str:
    value = str(raw).strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        if azure:
            value = f"{parsed.scheme}://{parsed.netloc}"
    if azure:
        return value + "/openai/v1/"
    return value + "/" if value else value


def make_chat_completions_callable(
    *,
    profile: ModelProfile | Any = PRODUCTION_PROFILE,
    role: str = "solver",
    effort: str | None = None,
    tools: Sequence[Mapping[str, Any]] | None = None,
    native_persistent_tools: bool | None = None,
    budget_guard: ProviderBudgetGuard | None = None,
    client_factory: Callable[..., Any] | None = None,
    base_url_env: str | None = None,
    azure: bool | None = None,
    timeout_s: float | None = None,
    capture_rate_headers: bool = False,
    tool_surface_mode: str = PERSISTENT_TOOL_SURFACE_CONTROL,
    context_policy: str = _managed_context.MANAGED_CONTEXT_POLICY_CONTROL,
    managed_context_trigger_tokens: int = _managed_context.MANAGED_CONTEXT_DEFAULT_TRIGGER_TOKENS,
    managed_context_keep_exchanges: int = _managed_context.MANAGED_CONTEXT_DEFAULT_KEEP_EXCHANGES,
    stream_idle_timeout_s: float | None = None,
    capture_provider_request_id: bool = False,
    disable_output_cap_escalation: bool = False,
    charge_shared_pacer_wait_to_run_deadline: bool = False,
    session_affinity_suffix: str = "",
    temperature: float = 0.0,
    top_p: float | None = None,
    tolerant_argument_parsing: bool = False,
) -> ChatCompletionsModelCallable:
    """Build a callable after, and only after, provider authorization.

    ``profile`` is injected by a launch boundary.  The production profile is
    used only as a compatibility default; this factory never mutates it.
    Credential and endpoint environment values are read after authorization.
    """
    require_provider_authorization(profile)
    endpoint_name = str(base_url_env or getattr(profile, "endpoint_env", ""))
    key_name = str(getattr(profile, "key_env", ""))
    deployment_name = str(getattr(profile, "deployment_env", ""))
    if not endpoint_name or not key_name or not deployment_name:
        raise ChatModelError("authorized profile lacks endpoint, key, or deployment environment names")
    endpoint = os.environ[endpoint_name]
    api_key = os.environ[key_name]
    deployment = str(os.environ[deployment_name]).strip()
    profile_model_id = str(getattr(profile, "model_id", "") or "").strip()
    declared_alias = str(getattr(profile, "deployment_alias", "") or "").strip()
    if not deployment:
        raise ChatModelError("deployment environment is empty")
    if profile_model_id and not declared_alias and deployment != profile_model_id:
        raise ChatModelError(
            "deployment does not match authorized profile model_id and no deployment alias is declared"
        )
    resolved_azure = (
        bool(getattr(profile, "api_mode", "") == "chat_completions")
        if azure is None else bool(azure)
    )
    base_url = _normalize_endpoint(endpoint, azure=resolved_azure)
    profile_timeout = getattr(profile, "provider_poll_timeout_s", None)
    resolved_timeout = float(timeout_s if timeout_s is not None else (profile_timeout or 450.0))
    if resolved_timeout <= 0:
        raise ChatModelError("timeout_s must be positive")
    # The authorized profile/launch boundary owns the timeout contract. Do not
    # silently clamp it here: Wave-0 allows 32k -> 65k completion escalation,
    # and long legal responses can exceed the historical 450s ceiling.
    guard = budget_guard if budget_guard is not None else provider_budget_guard_from_env(expected_model_id=profile_model_id)
    profile_max_retries = int(getattr(profile, "provider_max_retries", 0) or 0)
    if guard is not None:
        contract = getattr(guard, "contract", None)
        contract_model_id = str(getattr(contract, "model_id", "") or "").strip()
        if contract_model_id != profile_model_id:
            raise ChatModelError("provider budget model_id does not match authorized profile model_id")
        contract_max_retries = int(getattr(contract, "provider_max_retries", 0) or 0)
        if contract_max_retries != profile_max_retries:
            raise ChatModelError("provider budget retry policy does not match authorized profile")
    # Real SDK clients stream by default (Wave 1: non-streamed GLM calls past
    # ~250 s never returned). Injected test clients opt in explicitly.
    if stream_idle_timeout_s is None:
        raw_idle = str(os.environ.get("AETHER_PROVIDER_STREAM_IDLE_TIMEOUT_S", "") or "").strip()
        if raw_idle:
            stream_idle_timeout_s = float(raw_idle) if raw_idle.lower() not in {"0", "off", "none"} else None
        elif client_factory is None:
            stream_idle_timeout_s = DEFAULT_STREAM_IDLE_TIMEOUT_S
    if client_factory is None:
        try:
            import openai
        except ModuleNotFoundError as exc:  # pragma: no cover - construction requires SDK.
            raise ChatModelError("openai package is required for Chat Completions") from exc
        client_factory = openai.OpenAI
    client = client_factory(
        api_key=api_key, base_url=base_url, max_retries=0, timeout=resolved_timeout,
    )
    resolved_effort = effort if effort is not None else getattr(profile, f"{role}_reasoning_effort", None)
    capacity_overflow_action = (
        getattr(profile, "chat_capacity_overflow_action", _CAPACITY_OVERFLOW_REANCHOR)
        if role == "solver" else _CAPACITY_OVERFLOW_REANCHOR
    )
    throughput_pacer: SerialTokenPacer | SharedDeploymentTokenPacer | None = None
    raw_tpm = str(os.environ.get("AETHER_PROVIDER_TPM_LIMIT", "") or "").strip()
    raw_rpm = str(os.environ.get("AETHER_PROVIDER_RPM_LIMIT", "") or "").strip()
    shared_limiter_path = str(os.environ.get("AETHER_PROVIDER_SHARED_LIMITER_PATH", "") or "").strip()
    raw_window_anchor = str(
        os.environ.get("AETHER_PROVIDER_WINDOW_ANCHOR", "settlement") or "settlement"
    ).strip()
    raw_serial_settlement = str(
        os.environ.get("AETHER_PROVIDER_SERIAL_SETTLEMENT", "requested_output_cap")
        or "requested_output_cap"
    ).strip()
    if shared_limiter_path and (not raw_tpm or not raw_rpm):
        raise ChatModelError("shared provider limiter requires both AETHER_PROVIDER_TPM_LIMIT and AETHER_PROVIDER_RPM_LIMIT")
    if raw_rpm and not shared_limiter_path:
        raise ChatModelError("AETHER_PROVIDER_RPM_LIMIT requires the shared deployment limiter")
    if raw_tpm:
        try:
            tpm_limit = int(raw_tpm)
            window_s = float(str(os.environ.get("AETHER_PROVIDER_TPM_WINDOW_S", "60") or "60"))
            rpm_limit = int(raw_rpm) if raw_rpm else 0
        except ValueError as exc:
            raise ChatModelError("provider throughput launch contract is invalid") from exc
        if shared_limiter_path:
            if raw_window_anchor not in {"settlement", "dispatch"}:
                raise ChatModelError("AETHER_PROVIDER_WINDOW_ANCHOR must be settlement or dispatch")
            route_identity = f"{base_url.rstrip('/')}\n{deployment}"
            throughput_pacer = SharedDeploymentTokenPacer(
                state_path=Path(shared_limiter_path),
                deployment=route_identity,
                token_limit=tpm_limit,
                request_limit=rpm_limit,
                window_s=window_s,
                window_anchor=raw_window_anchor,
            )
        else:
            if raw_serial_settlement not in {"requested_output_cap", "observed_output"}:
                raise ChatModelError(
                    "AETHER_PROVIDER_SERIAL_SETTLEMENT must be requested_output_cap or observed_output"
                )
            throughput_pacer = SerialTokenPacer(
                token_limit=tpm_limit,
                window_s=window_s,
                settlement_mode=raw_serial_settlement,
            )
    return ChatCompletionsModelCallable(
        client=client,
        deployment=deployment,
        role=role,
        effort=resolved_effort,
        tools=tools,
        native_persistent_tools=native_persistent_tools,
        tool_surface_mode=tool_surface_mode,
        context_policy=context_policy,
        managed_context_trigger_tokens=managed_context_trigger_tokens,
        managed_context_keep_exchanges=managed_context_keep_exchanges,
        budget_guard=guard,
        throughput_pacer=throughput_pacer,
        max_retries=profile_max_retries,
        capture_rate_headers=capture_rate_headers,
        expected_returned_model=getattr(profile, "expected_returned_model", None),
        research_runtime_config_sha256=str(
            os.environ.get("AETHER_RESEARCH_RUNTIME_CONFIG_SHA256", "") or ""
        ).strip() or None,
        provider_timeout_s=resolved_timeout,
        stream_idle_timeout_s=stream_idle_timeout_s,
        capture_provider_request_id=capture_provider_request_id,
        disable_output_cap_escalation=disable_output_cap_escalation,
        charge_shared_pacer_wait_to_run_deadline=charge_shared_pacer_wait_to_run_deadline,
        session_affinity_suffix=session_affinity_suffix,
        temperature=temperature,
        top_p=top_p,
        tolerant_argument_parsing=tolerant_argument_parsing,
        capacity_reanchor_recovery_mode=str(
            getattr(profile, "chat_capacity_reanchor_recovery_mode", "off") or "off"
        ),
        capacity_overflow_action=str(
            capacity_overflow_action or _CAPACITY_OVERFLOW_REANCHOR
        ),
    )


# Small aliases keep route integration descriptive without duplicating behavior.
make_glm_callable = make_chat_completions_callable
ChatModelCallable = ChatCompletionsModelCallable


def make_chat_callable(
    profile: ModelProfile | Any = PRODUCTION_PROFILE,
    *,
    role: str = "solver",
    **kwargs: Any,
) -> ChatCompletionsModelCallable:
    """Route-friendly spelling used by bounded research runners."""
    return make_chat_completions_callable(profile=profile, role=role, **kwargs)
