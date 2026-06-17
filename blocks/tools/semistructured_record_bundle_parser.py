"""Parse matched semi-structured records into compact provenance-backed bundles."""
from __future__ import annotations

import json
import re
from typing import Any

from .app_evidence_projection_normalizer import execute_tool_call as execute_baseline_tool_call
from .app_evidence_projection_normalizer import get_tools as baseline_get_tools
from . import semistructured_header_record_parser as header_parser

_HEADER_RE = re.compile(r"^#{2,6}\s*(?P<label>[^()\n][^()\n]*?)(?:\s*\((?P<meta>[^)]*)\))?\s*$")
_KV_RE = re.compile(r"^(?P<key>[A-Za-z0-9_.-]{1,64})\s*:\s*(?P<value>.+?)\s*$")
_LINE_KV_RE = re.compile(r"^(?P<line>\d+):(?P<key>[A-Za-z0-9_.-]{1,64})\s*:\s*(?P<value>.+?)\s*$")
_MAX_FACTS = 12


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    result = execute_baseline_tool_call(tool_call, sandbox)
    if result.get("result_class") != "success":
        return result
    payload = dict(result.get("normalized_tool_call_payload") or {})
    facts = _extract_facts(str(result.get("command", "")), str(result.get("stdout", "")), header_parser.base._sandbox_cwd(sandbox), payload)
    if not facts:
        return result
    markers = [header_parser.base._receipt_line(fact) for fact in facts]
    stdout = str(result.get("stdout", "")).rstrip()
    missing = [marker for marker in markers if marker not in stdout]
    if missing:
        result["stdout"] = stdout + (("\n" if stdout else "") + "\n".join(missing) + "\n")
    payload["semistructured_evidence_facts"] = facts
    payload["semistructured_evidence_fact_count"] = len(facts)
    result["normalized_tool_call_payload"] = payload
    return result


def _extract_facts(command: str, stdout: str, cwd: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    sources = header_parser.base._command_sources(command, cwd)
    default_source = sources[0] if len(sources) == 1 else f"tool_stdout://{payload.get('tool_name', 'raw_bash')}"
    for block_index, raw_block in enumerate((chunk for chunk in stdout.split("\n\n") if chunk.strip()), start=1):
        lines = [line.rstrip() for line in raw_block.splitlines() if line.strip()]
        if not lines:
            continue
        source = header_parser.base._line_source(lines[0], default_source, cwd)
        bundle = _bundle_from_block(lines)
        if bundle:
            facts.append(
                {
                    "fact_type": "record_bundle",
                    "key": "record_bundle",
                    "value": bundle,
                    "source_path": source,
                    "source_span": f"block:{block_index}",
                    "raw_text": raw_block[:240],
                    "confidence": 0.93,
                    "parser_mode": "record_bundle",
                }
            )
            if len(facts) >= _MAX_FACTS:
                return facts[:_MAX_FACTS]
            continue
        for offset, line in enumerate(lines, start=1):
            match = _LINE_KV_RE.match(line.strip())
            if not match:
                continue
            facts.append(
                {
                    "fact_type": "field",
                    "key": match.group("key"),
                    "value": match.group("value").strip(),
                    "source_path": source,
                    "source_span": f"line:{match.group('line')}",
                    "raw_text": line[:240],
                    "confidence": 0.87,
                    "parser_mode": "line_number_kv",
                }
            )
            if len(facts) >= _MAX_FACTS:
                return facts[:_MAX_FACTS]
    if facts:
        return facts[:_MAX_FACTS]
    return header_parser._extract_facts(command, stdout, cwd, payload)[:_MAX_FACTS]


def _bundle_from_block(lines: list[str]) -> dict[str, Any]:
    match = _HEADER_RE.match(lines[0].strip())
    if not match:
        return {}
    bundle: dict[str, Any] = {"header_label": match.group("label").strip()}
    for chunk in re.split(r"\s*[;,]\s*", match.group("meta") or ""):
        kv = _KV_RE.match(chunk)
        if kv:
            bundle[kv.group("key")] = kv.group("value").strip()
    for line in lines[1:]:
        kv = _KV_RE.match(line.strip())
        if kv:
            bundle[kv.group("key")] = kv.group("value").strip()
    return bundle if len(bundle) >= 3 else {}
