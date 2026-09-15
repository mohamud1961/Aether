"""Lossless provider-transport delta for one Verifier activation.

The canonical Verifier transcript and ``compact_verifier_messages_for_provider``
remain the authority. This module changes only how the already-projected
provider input is transported after a successful prior Verifier turn.

The patch format is deliberately generic JSON structure, not evidence-aware
logic. It therefore cannot choose what matters or replace Verifier judgment.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import threading
from typing import Any, Mapping, Sequence


FRESH_CONTROL = "fresh_compact_control"
PREVIOUS_RESPONSE_V1 = "activation_previous_response_v1"
SUPPORTED_MODES = frozenset({FRESH_CONTROL, PREVIOUS_RESPONSE_V1})
SCHEMA = "aether.verifier_activation_continuity_delta.v1"
PREFIX = "[verifier_activation_delta]\n"
REPRESENTATION_CONTRACT = (
    "Apply operations in order to the previous verifier provider input JSON. "
    "Each operation is add, remove, or replace at an RFC6901 JSON Pointer path. "
    "For add at a list path ending /-, append the supplied value. The result_sha256 "
    "must equal the canonical JSON SHA-256 after reconstruction. This is serialization only, "
    "not evidence interpretation or strategy guidance."
)


def stable_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str,
    )


def snapshot_sha256(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _escape_pointer(value: str) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _unescape_pointer(value: str) -> str:
    return str(value).replace("~1", "/").replace("~0", "~")


def _join(path: str, token: str) -> str:
    encoded = _escape_pointer(token)
    return f"{path}/{encoded}" if path else f"/{encoded}"


def _diff(previous: Any, current: Any, *, path: str, out: list[dict[str, Any]]) -> None:
    if type(previous) is not type(current):
        out.append({"op": "replace", "path": path or "", "value": deepcopy(current)})
        return
    if isinstance(previous, Mapping):
        previous_keys = set(previous)
        current_keys = set(current)
        for key in sorted(previous_keys - current_keys, key=str):
            out.append({"op": "remove", "path": _join(path, str(key))})
        for key in sorted(current_keys - previous_keys, key=str):
            out.append({"op": "add", "path": _join(path, str(key)), "value": deepcopy(current[key])})
        for key in sorted(previous_keys & current_keys, key=str):
            _diff(previous[key], current[key], path=_join(path, str(key)), out=out)
        return
    if isinstance(previous, list):
        if previous == current:
            return
        # Equal-cardinality structured lists are safe to recurse positionally.
        # Provider message order and compact inspection ordering are canonical,
        # so this exposes nested append-only evidence growth without inventing
        # an identity matcher.
        if len(previous) == len(current):
            for index, (old_value, new_value) in enumerate(zip(previous, current, strict=True)):
                _diff(old_value, new_value, path=_join(path, str(index)), out=out)
            return
        # Monotonic list growth is common for exact inspection-result and
        # available-ref namespaces. Encode only appended values when the old
        # list is an exact prefix; otherwise replace the list without guessing.
        if len(current) >= len(previous) and current[: len(previous)] == previous:
            for value in current[len(previous):]:
                out.append({"op": "add", "path": _join(path, "-"), "value": deepcopy(value)})
            return
        out.append({"op": "replace", "path": path or "", "value": deepcopy(current)})
        return
    if previous != current:
        out.append({"op": "replace", "path": path or "", "value": deepcopy(current)})


def delta_envelope(previous: Any, current: Any) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    _diff(previous, current, path="", out=operations)
    return {
        "schema": SCHEMA,
        "representation_contract": REPRESENTATION_CONTRACT,
        "base_snapshot_sha256": snapshot_sha256(previous),
        "result_snapshot_sha256": snapshot_sha256(current),
        "operations": operations,
        "operation_count": len(operations),
    }


def _tokens(path: str) -> list[str]:
    if path == "":
        return []
    if not path.startswith("/"):
        raise ValueError("JSON Pointer path must be empty or start with /")
    return [_unescape_pointer(token) for token in path[1:].split("/")]


def _parent(root: Any, path: str) -> tuple[Any, str]:
    tokens = _tokens(path)
    if not tokens:
        raise ValueError("root path has no parent")
    current = root
    for token in tokens[:-1]:
        if isinstance(current, list):
            if token == "-":
                raise ValueError("/- is legal only for final add token")
            index = int(token)
            current = current[index]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise ValueError("JSON Pointer traverses scalar")
    return current, tokens[-1]


def apply_delta(previous: Any, envelope: Mapping[str, Any]) -> Any:
    if envelope.get("schema") != SCHEMA:
        raise ValueError("unexpected verifier activation delta schema")
    if envelope.get("representation_contract") != REPRESENTATION_CONTRACT:
        raise ValueError("verifier activation delta representation contract drift")
    if envelope.get("base_snapshot_sha256") != snapshot_sha256(previous):
        raise ValueError("verifier activation delta base snapshot mismatch")
    operations = envelope.get("operations")
    if not isinstance(operations, list) or int(envelope.get("operation_count", -1)) != len(operations):
        raise ValueError("verifier activation delta operations malformed")
    result = deepcopy(previous)
    for row in operations:
        if not isinstance(row, Mapping):
            raise ValueError("verifier activation delta operation must be object")
        op = str(row.get("op") or "")
        path = str(row.get("path") if "path" in row else "")
        if op not in {"add", "remove", "replace"}:
            raise ValueError("unsupported verifier activation delta operation")
        if path == "":
            if op == "remove":
                raise ValueError("cannot remove verifier activation root")
            if "value" not in row:
                raise ValueError("root add/replace requires value")
            result = deepcopy(row["value"])
            continue
        parent, token = _parent(result, path)
        if isinstance(parent, list):
            if op == "add" and token == "-":
                if "value" not in row:
                    raise ValueError("list append requires value")
                parent.append(deepcopy(row["value"]))
                continue
            index = int(token)
            if op == "remove":
                del parent[index]
            elif op == "replace":
                if "value" not in row:
                    raise ValueError("list replace requires value")
                parent[index] = deepcopy(row["value"])
            else:
                if "value" not in row:
                    raise ValueError("list add requires value")
                parent.insert(index, deepcopy(row["value"]))
            continue
        if not isinstance(parent, dict):
            raise ValueError("verifier activation delta parent must be list or object")
        if op == "remove":
            if token not in parent:
                raise ValueError("verifier activation delta remove target missing")
            del parent[token]
        elif op in {"add", "replace"}:
            if op == "replace" and token not in parent:
                raise ValueError("verifier activation delta replace target missing")
            if "value" not in row:
                raise ValueError("verifier activation delta add/replace requires value")
            parent[token] = deepcopy(row["value"])
    if envelope.get("result_snapshot_sha256") != snapshot_sha256(result):
        raise ValueError("verifier activation delta result snapshot mismatch")
    return result


def render_delta(previous: Any, current: Any) -> tuple[str, dict[str, Any]]:
    envelope = delta_envelope(previous, current)
    # Self-verify before any provider can see the representation.
    if apply_delta(previous, envelope) != current:
        raise ValueError("verifier activation delta failed lossless self-check")
    return PREFIX + stable_json(envelope), envelope


@dataclass(frozen=True)
class PreparedVerifierActivationTransport:
    """One provider-free activation transport candidate.

    ``snapshot`` is always the exact current compact provider view. ``rendered``
    is either that full view (first/control call) or one lossless delta string.
    Nothing here interprets evidence or chooses a Verifier action.
    """

    key: tuple[str, str, str]
    configured_mode: str
    transport_kind: str
    snapshot: Any
    rendered: Any
    previous_response_id: str | None = None
    previous_call_id: str | None = None
    envelope: Mapping[str, Any] | None = None


class VerifierActivationContinuityState:
    """Two-phase provider continuity state scoped to one Verifier activation.

    State is keyed by ``(run_id, task_id, activation_id)``. Provider-native
    response/call identifiers are globally one-use for the lifetime of this
    object, so clearing an activation can never make a historical identifier
    eligible for reuse by a later activation.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._committed: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._pending: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._seen_response_ids: dict[str, tuple[str, str, str]] = {}
        self._seen_call_ids: dict[str, tuple[str, str, str]] = {}

    @staticmethod
    def key(*, run_id: str, task_id: str, activation_id: str) -> tuple[str, str, str]:
        key = (str(run_id).strip(), str(task_id).strip(), str(activation_id).strip())
        if not all(key):
            raise ValueError("Verifier activation continuity requires run_id, task_id, and activation_id")
        return key

    def prepare(
        self,
        snapshot: Any,
        *,
        mode: str,
        run_id: str,
        task_id: str,
        activation_id: str,
    ) -> PreparedVerifierActivationTransport:
        normalized = str(mode or FRESH_CONTROL).strip().lower()
        if normalized not in SUPPORTED_MODES:
            raise ValueError(f"unsupported Verifier activation continuity mode: {normalized!r}")
        key = self.key(run_id=run_id, task_id=task_id, activation_id=activation_id)
        current = deepcopy(snapshot)
        with self._lock:
            if key in self._pending:
                raise ValueError("Verifier activation continuity pending candidate requires admission")
            previous = self._committed.get(key)
            if normalized == FRESH_CONTROL or previous is None:
                return PreparedVerifierActivationTransport(
                    key=key,
                    configured_mode=normalized,
                    transport_kind="full_snapshot",
                    snapshot=current,
                    rendered=deepcopy(current),
                )
            rendered, envelope = render_delta(previous["snapshot"], current)
            return PreparedVerifierActivationTransport(
                key=key,
                configured_mode=normalized,
                transport_kind="delta",
                snapshot=current,
                rendered=rendered,
                previous_response_id=str(previous["response_id"]),
                previous_call_id=str(previous["call_id"]),
                envelope=deepcopy(envelope),
            )

    @staticmethod
    def _nonempty_identifier(value: str, *, label: str) -> str:
        result = str(value or "").strip()
        if not result:
            raise ValueError(f"Verifier activation continuity {label} is required")
        return result

    def stage_candidate(
        self,
        prepared: PreparedVerifierActivationTransport,
        *,
        response_id: str,
        call_id: str,
    ) -> None:
        response = self._nonempty_identifier(response_id, label="response_id")
        call = self._nonempty_identifier(call_id, label="call_id")
        key = prepared.key
        with self._lock:
            if key in self._pending:
                raise ValueError("Verifier activation continuity pending candidate already staged")
            response_owner = self._seen_response_ids.get(response)
            if response_owner is not None:
                raise ValueError(
                    "Verifier activation continuity response_id reuse forbidden: "
                    f"owner={response_owner!r} current={key!r}"
                )
            call_owner = self._seen_call_ids.get(call)
            if call_owner is not None:
                raise ValueError(
                    "Verifier activation continuity call_id reuse forbidden: "
                    f"owner={call_owner!r} current={key!r}"
                )
            # Burn identifiers at stage, not commit. A rejected candidate was
            # still a real provider event and can never become fresh later.
            self._seen_response_ids[response] = key
            self._seen_call_ids[call] = key
            self._pending[key] = {
                "prepared": prepared,
                "snapshot": deepcopy(prepared.snapshot),
                "response_id": response,
                "call_id": call,
            }

    def commit_candidate(
        self,
        *,
        run_id: str,
        task_id: str,
        activation_id: str,
        response_id: str,
    ) -> dict[str, Any]:
        key = self.key(run_id=run_id, task_id=task_id, activation_id=activation_id)
        expected = self._nonempty_identifier(response_id, label="response_id")
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                raise ValueError("Verifier activation continuity pending candidate missing at commit")
            if pending["response_id"] != expected:
                raise ValueError("Verifier activation continuity commit response_id mismatch")
            self._pending.pop(key)
            self._committed[key] = {
                "snapshot": deepcopy(pending["snapshot"]),
                "response_id": pending["response_id"],
                "call_id": pending["call_id"],
            }
            return deepcopy(self._committed[key])

    def reject_candidate(
        self,
        *,
        run_id: str,
        task_id: str,
        activation_id: str,
        response_id: str,
    ) -> bool:
        key = self.key(run_id=run_id, task_id=task_id, activation_id=activation_id)
        expected = self._nonempty_identifier(response_id, label="response_id")
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                return False
            if pending["response_id"] != expected:
                raise ValueError("Verifier activation continuity reject response_id mismatch")
            self._pending.pop(key)
            return True

    def clear_activation(self, *, run_id: str, task_id: str, activation_id: str) -> None:
        key = self.key(run_id=run_id, task_id=task_id, activation_id=activation_id)
        with self._lock:
            self._pending.pop(key, None)
            self._committed.pop(key, None)

    def pending_identity(
        self, *, run_id: str, task_id: str, activation_id: str,
    ) -> dict[str, Any] | None:
        key = self.key(run_id=run_id, task_id=task_id, activation_id=activation_id)
        with self._lock:
            row = self._pending.get(key)
            if row is None:
                return None
            return {
                "response_id": str(row["response_id"]),
                "call_id": str(row["call_id"]),
                "transport_kind": str(row["prepared"].transport_kind),
            }

    def committed_identity(
        self, *, run_id: str, task_id: str, activation_id: str,
    ) -> dict[str, Any] | None:
        key = self.key(run_id=run_id, task_id=task_id, activation_id=activation_id)
        with self._lock:
            row = self._committed.get(key)
            return None if row is None else deepcopy(row)

    def observed_identifier_counts(self) -> dict[str, int]:
        with self._lock:
            return {
                "response_ids": len(self._seen_response_ids),
                "call_ids": len(self._seen_call_ids),
            }


__all__ = [
    "FRESH_CONTROL", "PREVIOUS_RESPONSE_V1", "PREFIX", "REPRESENTATION_CONTRACT",
    "SCHEMA", "SUPPORTED_MODES", "PreparedVerifierActivationTransport", "VerifierActivationContinuityState",
    "apply_delta", "delta_envelope", "render_delta",
    "snapshot_sha256", "stable_json",
]
