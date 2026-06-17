"""Project machine-readable grounded facts on top of the normalized raw_bash surface."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .open_workflow_answer_candidate_normalizer import execute_tool_call as execute_baseline_tool_call
from .open_workflow_answer_candidate_normalizer import get_tools as baseline_get_tools

_DIRECT_KEYS = {
    "answer",
    "final_answer",
    "answer_candidate",
    "name",
    "full_name",
    "person",
    "winner",
    "result",
    "value",
    "total",
    "count",
}
_PATH_KEYS = {
    "artifact_path": "artifact_path",
    "output_path": "artifact_path",
    "report_path": "artifact_path",
    "evidence_path": "evidence_path",
    "workspace_path": "evidence_path",
}
_LIST_PATH_KEYS = {
    "artifact_paths": "artifact_path",
    "evidence_paths": "evidence_path",
}
_LABELED_LINE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*[:=]\s*(?P<value>.+)$")
_PATH_RE = re.compile(r"(?:(?:/app|/Users)/[A-Za-z0-9_./-]+|(?:artifacts|case)/[A-Za-z0-9_./-]+)")


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    result = execute_baseline_tool_call(tool_call, sandbox)
    if result.get("result_class") != "success":
        return result
    facts = _extract_facts(result, sandbox)
    if not facts:
        return result
    stdout = str(result.get("stdout", ""))
    markers = [_marker_line(fact) for fact in facts]
    missing = [marker for marker in markers if marker not in stdout]
    if missing:
        result["stdout"] = f"{stdout.rstrip()}\n" + "\n".join(missing) + "\n"
    payload = dict(result.get("normalized_tool_call_payload") or {})
    payload["grounded_facts"] = facts
    result["normalized_tool_call_payload"] = payload
    return result


def _extract_facts(result: dict[str, Any], sandbox: Any) -> list[dict[str, Any]]:
    stdout = str(result.get("stdout", ""))
    payload = dict(result.get("normalized_tool_call_payload") or {})
    cwd = _sandbox_cwd(sandbox)
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    answer_candidate = payload.get("answer_candidate")
    if isinstance(answer_candidate, str) and answer_candidate:
        _push_fact(facts, seen, {"fact_type": "direct_answer", "key": "answer_candidate", "value": answer_candidate})
    parsed = _parse_json(stdout)
    if isinstance(parsed, dict):
        _facts_from_mapping(parsed, cwd, facts, seen)
    elif isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        _facts_from_mapping(parsed[0], cwd, facts, seen)
    for line in (line.strip() for line in stdout.splitlines() if line.strip()):
        match = _LABELED_LINE_RE.fullmatch(line)
        if not match:
            continue
        key = match.group("key").lower()
        value = match.group("value").strip()
        if key in _DIRECT_KEYS and _concise_value(value):
            _push_fact(facts, seen, {"fact_type": "direct_answer", "key": key, "value": value})
        elif key in _PATH_KEYS:
            normalized = _normalize_path(value, cwd)
            if normalized:
                _push_fact(facts, seen, {"fact_type": _PATH_KEYS[key], "path": normalized})
    for raw_path in _PATH_RE.findall(stdout):
        normalized = _normalize_path(raw_path, cwd)
        if normalized:
            _push_fact(facts, seen, {"fact_type": _path_fact_type(normalized), "path": normalized})
    return facts


def _facts_from_mapping(
    payload: dict[str, Any],
    cwd: Path | None,
    facts: list[dict[str, Any]],
    seen: set[str],
) -> None:
    for key in _DIRECT_KEYS:
        value = payload.get(key)
        if _scalar(value):
            _push_fact(facts, seen, {"fact_type": "direct_answer", "key": key, "value": value})
    for key, fact_type in _PATH_KEYS.items():
        normalized = _normalize_path(payload.get(key), cwd)
        if normalized:
            _push_fact(facts, seen, {"fact_type": fact_type, "path": normalized})
    for key, fact_type in _LIST_PATH_KEYS.items():
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            normalized = _normalize_path(value, cwd)
            if normalized:
                _push_fact(facts, seen, {"fact_type": fact_type, "path": normalized})


def _push_fact(facts: list[dict[str, Any]], seen: set[str], fact: dict[str, Any]) -> None:
    marker = _marker_line(fact)
    if marker not in seen:
        seen.add(marker)
        facts.append(fact)


def _marker_line(fact: dict[str, Any]) -> str:
    return f"GROUNDED_FACT: {json.dumps(fact, sort_keys=True)}"


def _parse_json(stdout: str) -> Any:
    text = stdout.strip()
    if not text.startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalize_path(value: Any, cwd: Path | None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = value.strip().rstrip(".,;:)]}")
    if path.startswith("/app/"):
        return path
    if path.startswith("artifacts/") or path.startswith("case/"):
        return f"/app/{path.lstrip('/')}"
    if cwd is None:
        return None
    prefix = cwd.as_posix().rstrip("/") + "/"
    return f"/app/{path[len(prefix):].lstrip('/')}" if path.startswith(prefix) else None


def _path_fact_type(path: str) -> str:
    return "artifact_path" if path.startswith("/app/artifacts/") else "evidence_path"


def _sandbox_cwd(sandbox: Any) -> Path | None:
    raw_cwd = getattr(sandbox, "cwd", None)
    return Path(str(raw_cwd)).resolve() if raw_cwd is not None else None


def _scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and _concise_value(value)


def _concise_value(value: Any) -> bool:
    text = str(value).strip()
    return bool(text) and len(text) <= 120 and "\n" not in text
