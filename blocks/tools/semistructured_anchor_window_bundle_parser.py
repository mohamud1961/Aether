"""Promote enclosing header-led record bundles around grounded anchors."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import semistructured_evidence_parser as base
from . import semistructured_record_bundle_parser as bundle_parser

_LINE_HIT_RE = re.compile(r"^(?P<line>\d+):(?P<text>.+)$")
_HEADER_RE = re.compile(r"^#{2,6}\s*(?P<label>[^()\n][^()\n]*?)(?:\s*\((?P<meta>[^)]*)\))?\s*$")
_MAX_FACTS = 8
_ANCHOR_RADIUS = 6


def get_tools() -> list[dict[str, Any]]:
    return bundle_parser.get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    result = bundle_parser.execute_tool_call(tool_call, sandbox)
    if result.get("result_class") != "success":
        return result
    payload = dict(result.get("normalized_tool_call_payload") or {})
    facts = _extract_anchor_window_facts(str(result.get("command", "")), str(result.get("stdout", "")), base._sandbox_cwd(sandbox), payload)
    if not facts:
        return result
    merged = _merge_facts(list(payload.get("semistructured_evidence_facts") or []), facts)
    payload["semistructured_evidence_facts"] = merged
    payload["semistructured_evidence_fact_count"] = len(merged)
    stdout = str(result.get("stdout", "")).rstrip()
    markers = [base._receipt_line(fact) for fact in facts]
    missing = [marker for marker in markers if marker not in stdout]
    if missing:
        result["stdout"] = stdout + (("\n" if stdout else "") + "\n".join(missing) + "\n")
    result["normalized_tool_call_payload"] = payload
    return result


def _extract_anchor_window_facts(command: str, stdout: str, cwd: Path | None, payload: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_path, anchors in _collect_anchors(command, stdout, cwd, payload).items():
        records = _records_from_source(source_path, cwd)
        if not records:
            continue
        for record, anchor in _matched_records(records, anchors):
            bundle = bundle_parser._bundle_from_block(record["lines"])
            if not bundle:
                continue
            if anchor.get("text"):
                bundle["anchor_text"] = anchor["text"]
            if anchor.get("line") is not None:
                bundle["anchor_line"] = anchor["line"]
            base._push_fact(
                facts,
                seen,
                {
                    "fact_type": "record_bundle",
                    "key": "record_bundle",
                    "value": bundle,
                    "source_path": source_path,
                    "source_span": f"lines:{record['start']}-{record['end']}",
                    "raw_text": "\n".join(record["lines"])[:240],
                    "confidence": 0.95 if anchor.get("line") is not None else 0.88,
                    "parser_mode": "anchor_window_bundle",
                },
            )
            if len(facts) >= _MAX_FACTS:
                return facts
    return facts


def _collect_anchors(command: str, stdout: str, cwd: Path | None, payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    sources = base._command_sources(command, cwd)
    default_source = sources[0] if len(sources) == 1 else f"tool_stdout://{payload.get('tool_name', 'raw_bash')}"
    anchors: dict[str, list[dict[str, Any]]] = {}
    for raw_line in (line.rstrip() for line in stdout.splitlines() if line.strip()):
        source_path, line_no, text = _anchor_line(raw_line, default_source, cwd)
        if source_path and not source_path.startswith("tool_stdout://"):
            anchors.setdefault(source_path, []).append({"line": line_no, "text": text})
    return anchors


def _anchor_line(raw_line: str, default_source: str, cwd: Path | None) -> tuple[str, int | None, str]:
    line = raw_line.strip()
    match = base._RG_RE.match(line)
    if match:
        return _anchor(base._normalize_path(match.group("path"), cwd) or default_source, int(match.group("line")), match.group("text").strip())
    hit = _LINE_HIT_RE.match(line)
    if hit:
        return _anchor(default_source, int(hit.group("line")), hit.group("text").strip())
    if _looks_like_anchor_text(line):
        return _anchor(base._line_source(line, default_source, cwd), None, line)
    return "", None, ""


def _anchor(source_path: str, line_no: int | None, text: str) -> tuple[str, int | None, str]:
    return source_path, line_no, text[:160]


def _looks_like_anchor_text(text: str) -> bool:
    if len(text) < 3 or len(text) > 120:
        return False
    if _HEADER_RE.match(text) or base._KV_RE.match(text) or base._INLINE_KV_RE.search(text) or base._TABLE_SEP_RE.match(text):
        return False
    return bool(re.search(r"[A-Za-z0-9]", text)) and "\t" not in text and text.count(",") < 3


def _records_from_source(source_path: str, cwd: Path | None) -> list[dict[str, Any]]:
    path = _local_path(source_path, cwd)
    if path is None or not path.exists() or path.suffix.lower() not in base._TEXT_SUFFIXES:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    start: int | None = None
    current: list[str] = []
    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()
        if _HEADER_RE.match(line.strip()):
            if start is not None:
                records.append({"start": start, "end": line_no - 1, "lines": current[:]})
            start = line_no
            current = [line]
        elif start is not None:
            current.append(line)
    if start is not None and current:
        records.append({"start": start, "end": len(lines), "lines": current[:]})
    return records


def _local_path(source_path: str, cwd: Path | None) -> Path | None:
    return cwd / source_path.removeprefix("/app/") if cwd is not None and source_path.startswith("/app/") else None


def _matched_records(records: list[dict[str, Any]], anchors: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for anchor in anchors:
        for record in records:
            if _record_matches(record, anchor):
                marker = json.dumps([record["start"], record["end"], anchor.get("line"), anchor.get("text")], ensure_ascii=True)
                if marker not in seen:
                    seen.add(marker)
                    matches.append((record, anchor))
                break
    return matches


def _record_matches(record: dict[str, Any], anchor: dict[str, Any]) -> bool:
    line_no = anchor.get("line")
    if isinstance(line_no, int) and record["start"] - _ANCHOR_RADIUS <= line_no <= record["end"] + _ANCHOR_RADIUS:
        return True
    text = str(anchor.get("text") or "").strip().casefold()
    return bool(text) and any(line.strip().casefold() == text for line in record["lines"])


def _merge_facts(existing: list[dict[str, Any]], new_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fact in [*existing, *new_facts]:
        marker = json.dumps(fact, sort_keys=True, ensure_ascii=True, default=str)
        if marker not in seen:
            seen.add(marker)
            merged.append(fact)
    return merged
