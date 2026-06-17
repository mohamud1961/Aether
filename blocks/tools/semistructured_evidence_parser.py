"""Parse semi-structured stdout into provenance-backed facts."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from .app_evidence_projection_normalizer import execute_tool_call as execute_baseline_tool_call
from .app_evidence_projection_normalizer import get_tools as baseline_get_tools

_FACT_PREFIX = "SEMISTRUCTURED_FACT: "
_KV_RE = re.compile(r"^(?P<key>[A-Za-z0-9_.-]{1,64})\s*[:=]\s*(?P<value>.+?)\s*$")
_INLINE_KV_RE = re.compile(r"(?P<key>[A-Za-z0-9_.-]{1,64})=(?P<value>[^\s,;]+)")
_RG_RE = re.compile(r"^(?P<path>[^:\n]+):(?P<line>\d+):(?P<text>.+)$")
_PATH_RE = re.compile(r"(?:(?:/app|/Users)/[A-Za-z0-9_./-]+|(?:artifacts|case)/[A-Za-z0-9_./-]+)")
_TABLE_SEP_RE = re.compile(r"^\s*:?-{3,}:?\s*$")
_TEXT_SUFFIXES = (".txt", ".md", ".log", ".cfg", ".ini", ".json", ".yaml", ".yml", ".csv", ".tsv")
_MAX_FACTS = 24
def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()
def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    result = execute_baseline_tool_call(tool_call, sandbox)
    if result.get("result_class") != "success":
        return result
    payload = dict(result.get("normalized_tool_call_payload") or {})
    facts = _extract_facts(str(result.get("command", "")), str(result.get("stdout", "")), _sandbox_cwd(sandbox), payload)
    if not facts:
        return result
    markers = [_receipt_line(fact) for fact in facts]
    stdout = str(result.get("stdout", "")).rstrip()
    missing = [marker for marker in markers if marker not in stdout]
    if missing:
        result["stdout"] = stdout + (("\n" if stdout else "") + "\n".join(missing) + "\n")
    payload["semistructured_evidence_facts"] = facts
    payload["semistructured_evidence_fact_count"] = len(facts)
    result["normalized_tool_call_payload"] = payload
    return result
def _extract_facts(command: str, stdout: str, cwd: Path | None, payload: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources = _command_sources(command, cwd)
    default_source = sources[0] if len(sources) == 1 else f"tool_stdout://{payload.get('tool_name', 'raw_bash')}"
    parsed = _parse_json(stdout)
    if isinstance(parsed, (dict, list)):
        _flatten_json(parsed, default_source, cwd, facts, seen)
    lines = [(idx + 1, line.rstrip()) for idx, line in enumerate(stdout.splitlines()) if line.strip()]
    for line_no, raw_line in lines:
        line = raw_line.strip()
        rg_match = _RG_RE.match(line)
        if rg_match:
            source = _normalize_path(rg_match.group("path"), cwd) or default_source
            _fact_from_line(rg_match.group("text").strip(), source, f"line:{rg_match.group('line')}", facts, seen)
            continue
        line_json = _parse_json(line)
        if isinstance(line_json, dict):
            _flatten_json(line_json, default_source, cwd, facts, seen, span=f"line:{line_no}", mode="json_line")
            continue
        _fact_from_line(line, _line_source(line, default_source, cwd), f"line:{line_no}", facts, seen)
    _table_facts(lines, default_source, cwd, facts, seen)
    return facts[:_MAX_FACTS]
def _fact_from_line(line: str, source: str, span: str, facts: list[dict[str, Any]], seen: set[str]) -> None:
    match = _KV_RE.fullmatch(line)
    if match:
        value = _coerce_scalar(match.group("value"))
        if _scalar_ok(value):
            _push_fact(facts, seen, _fact("labeled_value", match.group("key"), value, source, span, line, 0.86, "line_kv"))
        return
    pairs = [(m.group("key"), _coerce_scalar(m.group("value"))) for m in _INLINE_KV_RE.finditer(line)]
    if len(pairs) < 2:
        return
    for key, value in pairs:
        if _scalar_ok(value):
            _push_fact(facts, seen, _fact("inline_pair", key, value, source, span, line, 0.78, "inline_kv"))
def _flatten_json(node: Any, source: str, cwd: Path | None, facts: list[dict[str, Any]], seen: set[str], prefix: str = "", span: str = "stdout", mode: str = "json") -> None:
    if len(facts) >= _MAX_FACTS:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            _flatten_json(value, source, cwd, facts, seen, f"{prefix}.{key}" if prefix else str(key), span, mode)
        return
    if isinstance(node, list):
        for idx, value in enumerate(node):
            _flatten_json(value, source, cwd, facts, seen, f"{prefix}[{idx}]", span, mode)
        return
    if _scalar_ok(node) and prefix:
        raw_text = f"{prefix}={json.dumps(node, ensure_ascii=True)}"
        _push_fact(facts, seen, _fact("json_scalar", prefix, node, _line_source(raw_text, source, cwd), f"{span}:{prefix}", raw_text, 0.95, mode))
def _table_facts(
    lines: list[tuple[int, str]], default_source: str, cwd: Path | None, facts: list[dict[str, Any]], seen: set[str]
) -> None:
    delimiter = next((item for item in ("|", "\t", ",") if sum(item in line for _, line in lines[:6]) >= 2), None)
    table_lines = [(no, line) for no, line in lines[:5] if delimiter and delimiter in line]
    if len(table_lines) < 2:
        return
    rows = [_split_row(line, delimiter) for _, line in table_lines]
    headers = rows[0]
    start = 2 if len(rows) > 2 and all(_TABLE_SEP_RE.fullmatch(cell.strip()) for cell in rows[1]) else 1
    data_rows = [row for row in rows[start:start + 3] if len(row) == len(headers)]
    if len(headers) < 2 or any(not header for header in headers) or not data_rows:
        return
    for row_idx, row in enumerate(data_rows, start=1):
        line_no, raw_line = table_lines[min(start + row_idx - 1, len(table_lines) - 1)]
        source = _line_source(raw_line, default_source, cwd)
        for col_idx, header in enumerate(headers):
            value = _coerce_scalar(row[col_idx])
            if _scalar_ok(value):
                key = header if len(data_rows) == 1 else f"row_{row_idx}.{header}"
                _push_fact(facts, seen, _fact("table_cell", key, value, source, f"line:{line_no}", raw_line, 0.74, "table"))
def _fact(
    fact_type: str, key: str, value: Any, source_path: str, source_span: str, raw_text: str, confidence: float, parser_mode: str
) -> dict[str, Any]:
    return {
        "fact_type": fact_type,
        "key": key,
        "value": value,
        "source_path": source_path,
        "source_span": source_span,
        "raw_text": raw_text[:240],
        "confidence": round(confidence, 2),
        "parser_mode": parser_mode,
    }
def _command_sources(command: str, cwd: Path | None) -> list[str]:
    if cwd is None:
        return []
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    seen: set[str] = set()
    sources: list[str] = []
    for token in tokens:
        if token.startswith("-") or token in {"cat", "sed", "awk", "python", "python3", "bash", "sh", "rg", "grep", "head", "tail", "cut", "jq"}:
            continue
        if "/" not in token and not token.endswith(_TEXT_SUFFIXES):
            continue
        normalized = _normalize_path(token, cwd)
        if normalized and normalized not in seen:
            seen.add(normalized)
            sources.append(normalized)
    return sources[:3]
def _receipt_line(fact: dict[str, Any]) -> str:
    compact = {key: fact[key] for key in ("fact_type", "key", "value", "source_path", "source_span", "confidence", "parser_mode")}
    return _FACT_PREFIX + json.dumps(compact, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
def _line_source(line: str, default_source: str, cwd: Path | None) -> str:
    match = _PATH_RE.search(line)
    return (_normalize_path(match.group(0), cwd) if match else "") or default_source
def _normalize_path(raw_path: str, cwd: Path | None) -> str:
    path = raw_path.strip().rstrip(".,;:)]}")
    if path.startswith("/app/"):
        return path
    if path.startswith(("case/", "artifacts/")):
        return f"/app/{path.lstrip('/')}"
    if cwd is None or not path:
        return ""
    if path.startswith("/"):
        prefix = cwd.as_posix().rstrip("/") + "/"
        return f"/app/{path[len(prefix):].lstrip('/')}" if path.startswith(prefix) else ""
    if not (cwd / path.removeprefix("./")).exists():
        return ""
    try:
        rel = (cwd / path.removeprefix("./")).resolve().relative_to(cwd)
    except ValueError:
        return ""
    return f"/app/{rel.as_posix()}"
def _split_row(line: str, delimiter: str | None) -> list[str]:
    text = line.strip().strip("|") if delimiter == "|" else line.strip()
    return [cell.strip().strip("`") for cell in text.split(delimiter or ",")]
def _parse_json(text: str) -> Any:
    raw = text.strip()
    if not raw.startswith(("{", "[")):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
def _push_fact(facts: list[dict[str, Any]], seen: set[str], fact: dict[str, Any]) -> None:
    marker = json.dumps(fact, sort_keys=True, ensure_ascii=True, default=str)
    if marker not in seen and len(facts) < _MAX_FACTS:
        seen.add(marker)
        facts.append(fact)
def _coerce_scalar(value: str) -> Any:
    text = value.strip().strip("`")
    low = text.lower()
    if low in {"true", "false"}:
        return low == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text
def _scalar_ok(value: Any) -> bool:
    text = str(value).strip()
    return isinstance(value, (str, int, float, bool)) and 0 < len(text) <= 160 and "\n" not in text
def _sandbox_cwd(sandbox: Any) -> Path | None:
    raw_cwd = getattr(sandbox, "cwd", None)
    return Path(str(raw_cwd)).resolve() if raw_cwd is not None else None
