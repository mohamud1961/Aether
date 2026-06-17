"""Cached prefix transcript management."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping


def _normalize_message(message: Mapping[str, Any]) -> dict[str, Any]:
    role = str(message.get("role", "system"))
    content = message.get("content", "")
    if not isinstance(content, str):
        content = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    normalized = {"role": role, "content": content}
    for key in ("tool_call_id", "name"):
        if key in message and message[key] is not None:
            normalized[key] = str(message[key])
    if "tool_calls" in message and message["tool_calls"] is not None:
        tool_calls = message["tool_calls"]
        if isinstance(tool_calls, list):
            normalized["tool_calls"] = [
                dict(item) if isinstance(item, Mapping) else {"value": str(item)}
                for item in tool_calls
            ]
    return normalized


def _render_json_block(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Prefix:
    messages: tuple[dict[str, Any], ...]
    frozen_bytes: bytes
    token_estimate: int


class ContextManager:
    def __init__(self, *, delta_state: Any | None = None, compaction_generation: int = 0) -> None:
        self.delta_state = delta_state
        self.compaction_generation = int(compaction_generation)
        self.prefix: Prefix | None = None
        self.system_prompt = ""
        self.task_instruction = ""
        self.top_contract: dict[str, Any] = {}
        self.orientation: dict[str, Any] = {}
        self.tool_schemas: list[dict[str, Any]] = []
        self.extra_prefix_messages: list[dict[str, Any]] = []
        self.transcript: list[dict[str, Any]] = []
        self._tail_state = ""
        self._tail_render = ""
        self._tail_payload: dict[str, Any] = {}
        self._completion_contract: dict[str, Any] = {}
        self._prefix_digest: str | None = None
        self._task_instruction_digest: str | None = None
        self._orientation_digest: str | None = None
        self._tool_schema_digest: str | None = None

    def build_prefix(
        self,
        *,
        system_prompt: str,
        task_instruction: str,
        orientation: Mapping[str, Any],
        tool_schemas: list[dict[str, Any]],
        extra_prefix_messages: list[Mapping[str, Any]] | None = None,
    ) -> Prefix:
        self.system_prompt = system_prompt
        self.task_instruction = task_instruction
        self.top_contract = {"task_instruction": task_instruction}
        self.orientation = dict(orientation)
        self.tool_schemas = [dict(schema) for schema in tool_schemas]
        self.extra_prefix_messages = [
            _normalize_message(message) for message in (extra_prefix_messages or [])
        ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_instruction},
            {
                "role": "system",
                "content": "[orientation_snapshot]\n" + _render_json_block(self.orientation),
            },
            {
                "role": "system",
                "content": "[tool_schemas]\n" + _render_json_block(self.tool_schemas),
            },
            *self.extra_prefix_messages,
        ]
        frozen_bytes = _render_json_block(messages).encode("utf-8")
        self.prefix = Prefix(
            messages=tuple(_normalize_message(message) for message in messages),
            frozen_bytes=frozen_bytes,
            token_estimate=math.ceil(len(frozen_bytes.decode("utf-8")) / 4),
        )
        self._prefix_digest = _digest_bytes(frozen_bytes)
        self._task_instruction_digest = _digest_value(task_instruction)
        self._orientation_digest = _digest_value(self.orientation)
        self._tool_schema_digest = _digest_value(self.tool_schemas)
        return self.prefix

    def append_turn(self, *messages: Mapping[str, Any]) -> None:
        self.transcript.extend(_normalize_message(message) for message in messages)

    def set_completion_contract(self, completion_contract: Mapping[str, Any] | None) -> None:
        self._completion_contract = _normalize_tail_mapping(completion_contract)

    def render_tail(
        self,
        tail_state: Mapping[str, Any] | None = None,
        *,
        completion_contract: Mapping[str, Any] | None = None,
    ) -> str:
        if completion_contract is not None:
            self.set_completion_contract(completion_contract)
        payload = _normalize_tail_mapping(tail_state)
        if self._completion_contract:
            payload["completion_contract"] = dict(self._completion_contract)
        rendered_state = _render_json_block(payload)
        if rendered_state != self._tail_state:
            self._tail_state = rendered_state
            self._tail_render = "[tail_telemetry]\n" + rendered_state
            self._tail_payload = payload
        return self._tail_render

    def assert_prefix_unchanged(self) -> None:
        if self.prefix is None:
            raise AssertionError("prefix has not been built")
        rebuilt = ContextManager(delta_state=self.delta_state)
        rebuilt_prefix = rebuilt.build_prefix(
            system_prompt=self.system_prompt,
            task_instruction=self.task_instruction,
            orientation=self.orientation,
            tool_schemas=self.tool_schemas,
            extra_prefix_messages=self.extra_prefix_messages,
        )
        if rebuilt_prefix.frozen_bytes != self.prefix.frozen_bytes:
            raise AssertionError("immutable prefix changed")

    def message_history(self) -> list[dict[str, Any]]:
        if self.prefix is None:
            raise AssertionError("prefix has not been built")
        return [*self.prefix.messages, *self.transcript]

    def immutable_top_contract(self) -> dict[str, Any]:
        return dict(self.top_contract)

    def current_completion_contract(self) -> dict[str, Any]:
        return dict(self._completion_contract)

    def current_tail_payload(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._tail_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True))

    def digest_snapshot(self) -> dict[str, Any]:
        if self.prefix is None:
            raise AssertionError("prefix has not been built")
        return {
            "immutable_prefix_digest": self._prefix_digest,
            "task_instruction_digest": self._task_instruction_digest,
            "orientation_digest": self._orientation_digest,
            "tool_schema_digest": self._tool_schema_digest,
            "tail_digest": _digest_value(self._tail_payload),
            "completion_contract_digest": _digest_value(self._completion_contract),
            "compaction_generation": self.compaction_generation,
        }


def _normalize_tail_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    return json.loads(_render_json_block(dict(payload)))


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_value(value: Any) -> str:
    return _digest_bytes(_render_json_block(value).encode("utf-8"))
