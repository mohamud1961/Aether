"""Parse semi-structured stdout into provenance-backed facts with header record support."""
from __future__ import annotations

import re
from typing import Any

from .app_evidence_projection_normalizer import execute_tool_call as execute_baseline_tool_call
from .app_evidence_projection_normalizer import get_tools as baseline_get_tools
from . import semistructured_evidence_parser as base

_LINE_HIT_RE = re.compile(r"^(?P<line>\d+):(?P<text>.+)$")
_HEADER_RE = re.compile(r"^#{2,6}\s*(?P<label>[^()\n][^()\n]*?)(?:\s*\((?P<meta>[^)]*)\))?\s*$")


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    result = execute_baseline_tool_call(tool_call, sandbox)
    if result.get("result_class") != "success":
        return result
    payload = dict(result.get("normalized_tool_call_payload") or {})
    facts = _extract_facts(str(result.get("command", "")), str(result.get("stdout", "")), base._sandbox_cwd(sandbox), payload)
    if not facts:
        return result
    stdout = str(result.get("stdout", "")).rstrip()
    markers = [base._receipt_line(fact) for fact in facts]
    missing = [marker for marker in markers if marker not in stdout]
    if missing:
        result["stdout"] = stdout + (("\n" if stdout else "") + "\n".join(missing) + "\n")
    payload["semistructured_evidence_facts"] = facts
    payload["semistructured_evidence_fact_count"] = len(facts)
    result["normalized_tool_call_payload"] = payload
    return result


def _extract_facts(command: str, stdout: str, cwd: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources = base._command_sources(command, cwd)
    default_source = sources[0] if len(sources) == 1 else f"tool_stdout://{payload.get('tool_name', 'raw_bash')}"
    parsed = base._parse_json(stdout)
    if isinstance(parsed, (dict, list)):
        base._flatten_json(parsed, default_source, cwd, facts, seen)
    lines = [(idx + 1, line.rstrip()) for idx, line in enumerate(stdout.splitlines()) if line.strip()]
    for fallback_no, raw_line in lines:
        line, source, span = _provenanced_line(raw_line, fallback_no, default_source, cwd)
        line_json = base._parse_json(line)
        if isinstance(line_json, dict):
            base._flatten_json(line_json, source, cwd, facts, seen, span=span, mode="json_line")
            continue
        _header_facts(line, source, span, facts, seen)
        base._fact_from_line(line, source, span, facts, seen)
    base._table_facts(lines, default_source, cwd, facts, seen)
    return facts[: base._MAX_FACTS]


def _provenanced_line(raw_line: str, fallback_no: int, default_source: str, cwd: Any) -> tuple[str, str, str]:
    line = raw_line.strip()
    rg_match = base._RG_RE.match(line)
    if rg_match:
        source = base._normalize_path(rg_match.group("path"), cwd) or default_source
        return rg_match.group("text").strip(), source, f"line:{rg_match.group('line')}"
    line_hit = _LINE_HIT_RE.match(line)
    if line_hit:
        body = line_hit.group("text").strip()
        if _looks_like_fact_line(body):
            return body, base._line_source(body, default_source, cwd), f"line:{line_hit.group('line')}"
    return line, base._line_source(line, default_source, cwd), f"line:{fallback_no}"


def _header_facts(line: str, source: str, span: str, facts: list[dict[str, Any]], seen: set[str]) -> None:
    match = _HEADER_RE.fullmatch(line)
    if not match:
        return
    label = match.group("label").strip()
    if label:
        base._push_fact(facts, seen, base._fact("record_header", "header_label", label, source, span, line, 0.92, "header_record"))
    for chunk in re.split(r"\s*[;,]\s*", match.group("meta") or ""):
        kv_match = base._KV_RE.fullmatch(chunk)
        if not kv_match:
            continue
        value = base._coerce_scalar(kv_match.group("value"))
        if base._scalar_ok(value):
            base._push_fact(facts, seen, base._fact("header_metadata", kv_match.group("key"), value, source, span, line, 0.9, "header_record"))


def _looks_like_fact_line(text: str) -> bool:
    return bool(
        _HEADER_RE.fullmatch(text)
        or base._KV_RE.fullmatch(text)
        or isinstance(base._parse_json(text), dict)
        or sum(1 for _ in base._INLINE_KV_RE.finditer(text)) >= 2
    )
