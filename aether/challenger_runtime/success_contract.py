"""Opt-in experimental solver success checks, captured once after three actions."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from ..ledger import Receipt

CONTRACT_PROMPT = """Create 2 to 6 concise observable checks for the task below. These are checks you will be judged against later. Return one JSON object only: {{\"checks\":[{{\"id\":\"K1\",\"description\":\"...\",\"observable\":\"...\"}}]}}. Each observable must name a file/path state, command output, or service that can be inspected. Do not include implementation advice.

Task and allowed environment facts:
{context}

First three actions:
{actions}"""


class SuccessContractError(ValueError):
    pass


MAX_CONTRACT_PROMPT_BYTES = 8_000
_ENV_FACTS = frozenset({"workspace_root", "cwd", "shell", "python", "node", "available_capabilities"})
_SECRET_NAME = re.compile(r"key|token|secret|password|credential|authorization", re.I)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Z0-9_.-]*(?:API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Z0-9_.-]*\s*=\s*)[^\s]+"
)
_PATH_OBSERVABLE = re.compile(
    r"(?<![\w])(?:/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*|[A-Za-z0-9_.-]+\.[A-Za-z0-9_-]{1,16})(?![\w])"
)
_COMMAND_OBSERVABLE = re.compile(
    r"`[^`\n]{1,120}`|\b(?:pytest|python(?:3(?:\.\d+)?)?|node|npm|cargo|go|make|curl|wget|grep|cat|ls|git|test)\s+[^\s,;]+",
    re.I,
)
_SERVICE_OBSERVABLE = re.compile(
    r"https?://[^\s]+|\b(?:service|server)\s+[A-Za-z][\w.-]*|\b[A-Za-z][\w.-]*\s+(?:service|server)\b.{0,40}\b(?:port\s+\d+|health|status|listening|responds)\b",
    re.I,
)


def _clip_utf8(text: str, byte_limit: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= byte_limit:
        return text
    return encoded[:max(0, byte_limit - 3)].decode("utf-8", "ignore") + "..."


def _observable_is_inspectable(text: str) -> bool:
    return bool(_PATH_OBSERVABLE.search(text) or _COMMAND_OBSERVABLE.search(text)
                or _SERVICE_OBSERVABLE.search(text))


def build_contract_prompt(task_text: str, envmap: Any, receipts: Sequence[Receipt]) -> str:
    raw_env = dict(envmap) if isinstance(envmap, Mapping) else {
        k: getattr(envmap, k) for k in ("workspace_root", "cwd", "shell", "python", "node")
        if envmap is not None and hasattr(envmap, k)
    }
    env = {}
    for key, value in raw_env.items():
        if str(key) not in _ENV_FACTS or _SECRET_NAME.search(str(key)):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            env[str(key)] = _clip_utf8(str(value), 256) if isinstance(value, str) else value
    context_data = {"task": _clip_utf8(str(task_text), 4_000), "env": env}
    actions = []
    for row in receipts:
        if row.kind not in {"read_file", "read_file_page", "list_files", "search_files", "write_file", "edit_file", "run_command", "job_output", "job_wait", "job_stop", "m_tree_zoom", "managed_context_edit_context"}:
            continue
        payload = row.payload if isinstance(row.payload, Mapping) else {}
        args = str(payload.get("command") or payload.get("path") or row.summary)[:240]
        args = _SECRET_ASSIGNMENT.sub(r"\1[redacted]", args)
        actions.append({"step": int(row.step), "tool": row.kind,
                        "args": args[:200],
                        "exit_code": payload.get("exit_code")})
        if len(actions) == 3:
            break
    action_text = json.dumps(actions, ensure_ascii=False, default=str)
    while True:
        context = json.dumps(context_data, sort_keys=True, ensure_ascii=False, default=str)
        prompt = CONTRACT_PROMPT.format(context=context, actions=action_text)
        if len(prompt.encode("utf-8")) <= MAX_CONTRACT_PROMPT_BYTES:
            return prompt
        task = str(context_data["task"])
        if not task:
            raise SuccessContractError("success contract prompt exceeds its fixed byte cap")
        context_data["task"] = _clip_utf8(task, max(0, len(task.encode("utf-8")) - 512))


def parse_success_contract(text: str) -> list[dict[str, str]]:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SuccessContractError("success contract must be one JSON object") from exc
    rows = value.get("checks") if isinstance(value, Mapping) else None
    if not isinstance(rows, list) or not 2 <= len(rows) <= 6:
        raise SuccessContractError("success contract needs 2 to 6 checks")
    result = []
    seen = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise SuccessContractError("each success check must be an object")
        check_id = str(row.get("id") or "").strip()
        description = str(row.get("description") or "").strip()
        observable = str(row.get("observable") or "").strip()
        if not check_id or check_id in seen or not description or not observable:
            raise SuccessContractError("each success check needs a unique id, description, and observable")
        if len(description) > 240 or len(observable) > 240:
            raise SuccessContractError("success check fields may not exceed 240 characters")
        if check_id != f"K{index}":
            raise SuccessContractError("success check ids must be K1, K2, ... in order")
        if not _observable_is_inspectable(observable):
            raise SuccessContractError(
                "each observable must identify an inspectable path, concrete command output, or service"
            )
        seen.add(check_id)
        result.append({"id": check_id, "description": description, "observable": observable})
    return result
