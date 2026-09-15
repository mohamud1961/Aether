"""Provider-hosted tool-search custody for PERSISTENT Solver experiments.

The feature in this module is deliberately transport-only.  Aether declares the
same trusted PERSISTENT function schemas it already owns, but may mark action functions
``defer_loading`` and let the Responses provider search those declarations.
Provider search metadata is never an executable Aether action.

Safety/custody invariants:
- completion controls stay pinned (never deferred);
- every server-loaded function schema must byte-semantically match one exact
  Aether-declared deferred schema;
- at most the existing PERSISTENT function/computer call can authorise a task action;
- loaded schemas are staged with a provider response and only become committed
  when that Solver response is admitted;
- rejection rolls staged discovery back;
- parent loss / continuity clear drops the committed loaded set.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import threading
from typing import Any, Iterable, Mapping


SCHEMA = "aether.persistent_hosted_tool_search.v1"
CONTROL = "control"
HOSTED_V1 = "hosted_v1"
SUPPORTED_MODES = frozenset({CONTROL, HOSTED_V1})
PINNED_COMPLETION_TOOLS = frozenset({"finish_intent", "finish"})


class HostedToolSearchError(ValueError):
    """Provider-hosted search output violates Aether's frozen tool catalogue."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(self.code if not self.detail else f"{self.code}: {self.detail}")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(child) for child in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    )


def schema_sha256(tool: Mapping[str, Any]) -> str:
    return hashlib.sha256(stable_json(tool).encode("utf-8")).hexdigest()


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def hosted_provider_tools(
    tools: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return hosted-search request tools plus exact deferred-schema catalogue.

    Individual function deferral is intentional for V1: it preserves Aether's
    existing direct function names/canonicalizer and tests only schema loading,
    not a simultaneous namespace-routing treatment.
    """
    rendered: list[dict[str, Any]] = []
    catalogue: dict[str, dict[str, Any]] = {}
    saw_search = False
    for raw in tools:
        tool = deepcopy(dict(raw))
        tool_type = str(tool.get("type") or "")
        if tool_type == "tool_search":
            if saw_search:
                raise HostedToolSearchError("provider_persistent_tool_search_duplicate_declaration")
            saw_search = True
            rendered.append(tool)
            continue
        name = str(tool.get("name") or "")
        if tool_type == "function" and name not in PINNED_COMPLETION_TOOLS:
            if not name:
                raise HostedToolSearchError("provider_persistent_tool_search_deferred_name_missing")
            if name in catalogue:
                raise HostedToolSearchError(
                    "provider_persistent_tool_search_duplicate_deferred_name", name,
                )
            tool["defer_loading"] = True
            catalogue[name] = deepcopy(tool)
        rendered.append(tool)
    if not saw_search:
        rendered.append({"type": "tool_search"})
    return rendered, catalogue


def catalogue_identity(catalogue: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = [
        {"name": name, "sha256": schema_sha256(tool), "bytes": len(stable_json(tool).encode("utf-8"))}
        for name, tool in sorted(catalogue.items())
    ]
    return {
        "schema": SCHEMA,
        "tools": rows,
        "tool_count": len(rows),
        "sha256": hashlib.sha256(stable_json(rows).encode("utf-8")).hexdigest(),
    }


def _loaded_function_tools(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise HostedToolSearchError(
            "provider_persistent_tool_search_output_tools_invalid", "tools must be a list",
        )
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise HostedToolSearchError(
                "provider_persistent_tool_search_loaded_schema_invalid", "loaded tool must be an object",
            )
        tool = deepcopy(dict(item))
        if str(tool.get("type") or "") != "function":
            raise HostedToolSearchError(
                "provider_persistent_tool_search_loaded_schema_invalid",
                f"V1 accepts only direct deferred functions, got {tool.get('type')!r}",
            )
        rows.append(tool)
    return rows


@dataclass(frozen=True)
class HostedToolSearchObservation:
    search_call_count: int
    search_output_count: int
    newly_loaded_names: tuple[str, ...]
    newly_loaded_schema_sha256: tuple[str, ...]
    executable_function_names: tuple[str, ...]
    executable_deferred_names: tuple[str, ...]
    committed_loaded_names_before: tuple[str, ...]
    callable_deferred_names_after_response: tuple[str, ...]
    catalogue_sha256: str

    def as_telemetry(self) -> dict[str, Any]:
        return {
            "persistent_hosted_tool_search_mode": HOSTED_V1,
            "persistent_hosted_tool_search_call_count": self.search_call_count,
            "persistent_hosted_tool_search_output_count": self.search_output_count,
            "persistent_hosted_tool_search_newly_loaded_names": list(self.newly_loaded_names),
            "persistent_hosted_tool_search_newly_loaded_schema_sha256": list(self.newly_loaded_schema_sha256),
            "persistent_hosted_tool_search_executable_function_names": list(self.executable_function_names),
            "persistent_hosted_tool_search_executable_deferred_names": list(self.executable_deferred_names),
            "persistent_hosted_tool_search_committed_loaded_names_before": list(self.committed_loaded_names_before),
            "persistent_hosted_tool_search_callable_deferred_names_after_response": list(
                self.callable_deferred_names_after_response
            ),
            "persistent_hosted_tool_search_catalogue_sha256": self.catalogue_sha256,
        }


def validate_hosted_response(
    response: Any,
    *,
    catalogue: Mapping[str, Mapping[str, Any]],
    committed_loaded_names: Iterable[str] = (),
) -> HostedToolSearchObservation:
    """Validate hosted search metadata and prove any deferred call was loaded.

    Hosted server search is an in-provider schema-selection event.  The only
    task-authorising items remain ordinary ``function_call``/``computer_call``
    items, which the existing PERSISTENT canonicalizer independently constrains.
    """
    committed = {str(name) for name in committed_loaded_names}
    if not committed.issubset(set(catalogue)):
        raise HostedToolSearchError(
            "provider_persistent_tool_search_committed_catalogue_drift",
            stable_json(sorted(committed - set(catalogue))),
        )
    expected_digests = {
        str(name): schema_sha256(tool) for name, tool in catalogue.items()
    }
    search_calls: list[Any] = []
    search_outputs: list[Any] = []
    function_names: list[str] = []
    for item in _field(response, "output", ()) or ():
        item_type = str(_field(item, "type", "") or "")
        if item_type == "tool_search_call":
            search_calls.append(item)
        elif item_type == "tool_search_output":
            search_outputs.append(item)
        elif item_type == "function_call":
            function_names.append(str(_field(item, "name", "") or ""))

    if len(search_calls) != len(search_outputs):
        raise HostedToolSearchError(
            "provider_persistent_tool_search_pair_count_invalid",
            f"calls={len(search_calls)} outputs={len(search_outputs)}",
        )
    for index, item in enumerate(search_calls):
        if str(_field(item, "execution", "") or "") != "server":
            raise HostedToolSearchError(
                "provider_persistent_tool_search_execution_invalid",
                f"call[{index}] execution={_field(item, 'execution', None)!r}",
            )
        if str(_field(item, "status", "") or "") != "completed":
            raise HostedToolSearchError(
                "provider_persistent_tool_search_status_invalid",
                f"call[{index}] status={_field(item, 'status', None)!r}",
            )
        if _field(item, "call_id", None) not in (None, ""):
            raise HostedToolSearchError(
                "provider_persistent_tool_search_server_call_id_invalid",
                f"call[{index}] has client call_id",
            )
    newly_loaded: dict[str, str] = {}
    for output_index, item in enumerate(search_outputs):
        if str(_field(item, "execution", "") or "") != "server":
            raise HostedToolSearchError(
                "provider_persistent_tool_search_execution_invalid",
                f"output[{output_index}] execution={_field(item, 'execution', None)!r}",
            )
        if str(_field(item, "status", "") or "") != "completed":
            raise HostedToolSearchError(
                "provider_persistent_tool_search_status_invalid",
                f"output[{output_index}] status={_field(item, 'status', None)!r}",
            )
        if _field(item, "call_id", None) not in (None, ""):
            raise HostedToolSearchError(
                "provider_persistent_tool_search_server_call_id_invalid",
                f"output[{output_index}] has client call_id",
            )
        for tool in _loaded_function_tools(_field(item, "tools", None)):
            name = str(tool.get("name") or "")
            if name not in catalogue:
                raise HostedToolSearchError(
                    "provider_persistent_tool_search_loaded_tool_not_declared", name or "missing",
                )
            observed_digest = schema_sha256(tool)
            expected_digest = expected_digests[name]
            if observed_digest != expected_digest:
                raise HostedToolSearchError(
                    "provider_persistent_tool_search_loaded_schema_digest_mismatch",
                    stable_json({
                        "name": name,
                        "expected": expected_digest,
                        "observed": observed_digest,
                    }),
                )
            previous = newly_loaded.get(name)
            if previous is not None and previous != observed_digest:
                raise HostedToolSearchError(
                    "provider_persistent_tool_search_loaded_schema_conflict", name,
                )
            newly_loaded[name] = observed_digest

    callable_after = committed | set(newly_loaded)
    deferred_function_names = tuple(
        name for name in function_names if name in catalogue
    )
    unavailable = sorted(set(deferred_function_names) - callable_after)
    if unavailable:
        raise HostedToolSearchError(
            "provider_persistent_tool_search_deferred_call_not_loaded",
            stable_json(unavailable),
        )
    identity = catalogue_identity(catalogue)
    return HostedToolSearchObservation(
        search_call_count=len(search_calls),
        search_output_count=len(search_outputs),
        newly_loaded_names=tuple(sorted(newly_loaded)),
        newly_loaded_schema_sha256=tuple(newly_loaded[name] for name in sorted(newly_loaded)),
        executable_function_names=tuple(function_names),
        executable_deferred_names=deferred_function_names,
        committed_loaded_names_before=tuple(sorted(committed)),
        callable_deferred_names_after_response=tuple(sorted(callable_after)),
        catalogue_sha256=str(identity["sha256"]),
    )


class HostedToolSearchState:
    """Admission-coupled loaded-schema state for one provider callable."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._committed: dict[tuple[str, str], frozenset[str]] = {}
        self._pending: dict[tuple[str, str], dict[str, Any]] = {}

    @staticmethod
    def key(*, run_id: str, task_id: str) -> tuple[str, str]:
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            raise ValueError("hosted tool search requires run_id and task_id")
        return key

    def committed_loaded_names(self, *, run_id: str, task_id: str) -> tuple[str, ...]:
        key = self.key(run_id=run_id, task_id=task_id)
        with self._lock:
            return tuple(sorted(self._committed.get(key, frozenset())))

    def stage_candidate(
        self,
        *,
        run_id: str,
        task_id: str,
        response_id: str,
        observation: HostedToolSearchObservation,
    ) -> None:
        key = self.key(run_id=run_id, task_id=task_id)
        response = str(response_id).strip()
        if not response:
            raise ValueError("hosted tool search candidate requires response_id")
        candidate = frozenset(observation.callable_deferred_names_after_response)
        with self._lock:
            if key in self._pending:
                raise ValueError("hosted tool search pending candidate already exists")
            baseline = self._committed.get(key, frozenset())
            if not baseline.issubset(candidate):
                raise ValueError("hosted tool search candidate regressed committed loaded set")
            self._pending[key] = {
                "response_id": response,
                "loaded_names": candidate,
            }

    def commit_candidate(self, *, run_id: str, task_id: str, response_id: str) -> tuple[str, ...]:
        key = self.key(run_id=run_id, task_id=task_id)
        response = str(response_id).strip()
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                raise ValueError("hosted tool search pending candidate missing at commit")
            if str(pending["response_id"]) != response:
                raise ValueError("hosted tool search commit response_id mismatch")
            self._pending.pop(key)
            loaded = frozenset(pending["loaded_names"])
            self._committed[key] = loaded
            return tuple(sorted(loaded))

    def reject_candidate(self, *, run_id: str, task_id: str, response_id: str) -> bool:
        key = self.key(run_id=run_id, task_id=task_id)
        response = str(response_id).strip()
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                return False
            if str(pending["response_id"]) != response:
                raise ValueError("hosted tool search reject response_id mismatch")
            self._pending.pop(key)
            return True

    def clear_scope(self, *, run_id: str, task_id: str) -> None:
        key = self.key(run_id=run_id, task_id=task_id)
        with self._lock:
            self._pending.pop(key, None)
            self._committed.pop(key, None)


__all__ = [
    "SCHEMA", "CONTROL", "HOSTED_V1", "SUPPORTED_MODES", "PINNED_COMPLETION_TOOLS",
    "HostedToolSearchError", "HostedToolSearchObservation", "HostedToolSearchState",
    "hosted_provider_tools", "catalogue_identity", "schema_sha256", "validate_hosted_response",
]
