"""Register structured tool observations and project compact grounding markers."""
from __future__ import annotations
import ast, csv, io, json, re
from typing import Any

_FENCED_JSON_RE = re.compile(r"```(?:json|yaml|yml)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)
_QUOTED_TOKEN_RE = re.compile(r"""['"]([^'"]{2,})['"]""")
_WORD_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_.-]{3,}\b")
_PATH_RE = re.compile(r"(?:/[A-Za-z0-9_./-]+|[A-Za-z0-9_.-]+\.(?:csv|json|txt|md|yaml|yml|log))")
_STDOUT_RE = re.compile(r"stdout:\n(?P<stdout>.*?)(?:\nstderr:\n|\Z)", re.DOTALL)
_NOISE_TOKENS = {"cat", "sed", "awk", "python", "python3", "rg", "grep", "jq", "cut", "head", "tail", "print"}
_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
def apply_structured_observation_register(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> dict[str, Any]:
    observation, source = dict(new_observation), _source_context(history)
    created = _created_observations(history, observation, source)
    selected = sorted(created, key=lambda i: (1 if i.get("matched_token") else 0, _CONFIDENCE_RANK.get(str(i.get("confidence")), 0)), reverse=True)[:3]
    if created or selected:
        observation["structured_observation_register"] = {"created_observations": created, "selected_observation_ids": [i["id"] for i in selected], "source": source, "status": "active"}
    grounded = _grounding_status(history, observation)
    if created or grounded != "n/a":
        selected_ids = ",".join(i["id"] for i in selected) if selected else "none"
        marker = f"observation_created={len(created)} | observation_selected={selected_ids} | observation_projected={len(selected)} | answer_grounded_in_observation={grounded} | selection_bias=answer_from_selected_observations"
        marker_text, projected = f"[structured_observation_register] {marker}", _project_selected_observations(selected)
        content, register_text = observation.get("content"), f"{marker_text}\n{projected}" if projected else marker_text
        observation["content"] = f"{content}\n\n{register_text}" if isinstance(content, str) and content else register_text
    return observation
def _created_observations(history: list[dict[str, Any]], observation: dict[str, Any], source: dict[str, str]) -> list[dict[str, Any]]:
    if observation.get("role") != "tool":
        return []
    records = _structured_records(observation.get("content"), source.get("command", ""))
    if not records:
        return []
    tokens, base_index, created = _command_tokens(source.get("command", "")), len(history) + 1, []
    for idx, (obs_type, record, confidence) in enumerate(records, start=1):
        serialized = json.dumps(record, sort_keys=True, ensure_ascii=True)
        created.append({"id": f"sor-{base_index:04d}-{idx:02d}", "type": obs_type, "source_path": source.get("path", ""), "source_command": source.get("command", ""), "record": record, "matched_token": next((t for t in tokens if t in serialized), ""), "confidence": confidence, "status": "created"})
    return created
def _structured_records(content: Any, command: str) -> list[tuple[str, Any, str]]:
    if isinstance(content, dict):
        return [("json_record", dict(content), "high")]
    if isinstance(content, list):
        return [("json_array_record", row, "high") for row in content[:5] if isinstance(row, (dict, list))]
    if not isinstance(content, str) or not content.strip():
        return []
    match = _STDOUT_RE.search(content)
    text, records = (match.group("stdout") if match else content).strip(), []
    for candidate in [text, *[block.strip() for block in _FENCED_JSON_RE.findall(text)]]:
        parsed = _try_json(candidate)
        if isinstance(parsed, dict):
            records.append(("json_record", parsed, "high"))
        elif isinstance(parsed, list):
            records.extend(("json_array_record", row, "high") for row in parsed[:5] if isinstance(row, (dict, list)))
    for line in (row.strip() for row in text.splitlines()):
        if line.startswith("{") and line.endswith("}"):
            parsed = _try_json(line)
            if isinstance(parsed, dict):
                records.append(("json_record", parsed, "medium"))
                continue
            parsed = _try_python_literal(line)
            if isinstance(parsed, dict):
                records.append(("python_record", parsed, "medium"))
    records.extend(("kv_record", row, "low") for row in _kv_records(text))
    if records:
        return _dedupe_records(records)[:6]
    rows, delimiter = [row.strip() for row in text.splitlines() if row.strip()], _pick_delimiter(text, command)
    if rows and delimiter is not None:
        table = [row for row in csv.reader(io.StringIO("\n".join(rows[:5])), delimiter=delimiter) if row]
        if len(table) >= 2 and len(table[0]) >= 2:
            headers = table[0]
            for row in table[1:4]:
                if len(row) == len(headers):
                    records.append(("csv_row", {headers[i]: row[i] for i in range(len(headers))}, "medium"))
        elif table and any(token in command.lower() for token in ("csv", "dictreader", "delimiter", "split(", "cut -d", "awk -f")):
            records.append(("csv_row", {"columns": table[0], "row_text": rows[0]}, "low"))
    return _dedupe_records(records)[:6]
def _kv_records(text: str) -> list[dict[str, Any]]:
    def _scalar(raw: str) -> Any:
        value, low = raw.strip().strip("'").strip('"'), raw.strip().strip("'").strip('"').lower()
        if low in {"true", "false"}:
            return low == "true"
        if low in {"none", "null"}:
            return None
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        return float(value) if re.fullmatch(r"-?\d+\.\d+", value) else value

    records, yaml_buffer = [], {}
    for line in (row.strip() for row in text.splitlines()[:20]):
        if not line or line.startswith(("#", "{", "}", "[", "]")):
            continue
        if ":" in line and "=" not in line:
            key, value = [part.strip() for part in line.split(":", 1)]
            key = key.lstrip("-").strip()
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", key) and value:
                yaml_buffer[key] = _scalar(value)
            continue
        kv_line: dict[str, Any] = {}
        for token in line.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            value = value.strip().strip(",;")
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", key) and value:
                kv_line[key] = _scalar(value)
        if len(kv_line) >= 2:
            records.append(kv_line)
    if len(yaml_buffer) >= 2:
        records.append(yaml_buffer)
    return records[:2]
def _project_selected_observations(selected: list[dict[str, Any]]) -> str:
    if not selected:
        return ""
    lines = ["[structured_observation_register_projection]"]
    for idx, item in enumerate(selected, start=1):
        source = str(item.get("source_path") or item.get("source_command") or "unknown")
        source = f"{source[:69]}..." if len(source) > 72 else source
        record = json.dumps(item.get("record"), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        lines.append(f"obs[{idx}] id={item.get('id','')} type={item.get('type','')} confidence={item.get('confidence','')} provenance=source={source} token={item.get('matched_token') or '-'}")
        lines.append(f"obs[{idx}].record={record}")
    return "\n".join(lines)
def _source_context(history: list[dict[str, Any]]) -> dict[str, str]:
    for row in reversed(history):
        tool_calls = row.get("tool_calls")
        if not isinstance(tool_calls, list) or not tool_calls:
            continue
        raw = tool_calls[-1].get("arguments")
        parsed = _try_json(raw) if isinstance(raw, str) and raw else None
        command = parsed.get("command") if isinstance(parsed, dict) and isinstance(parsed.get("command"), str) else (raw or "")
        path = next((token for token in _PATH_RE.findall(command) if "/" in token or "." in token), "")
        return {"tool": str(tool_calls[-1].get("name") or ""), "command": command, "path": path}
    return {"tool": "", "command": "", "path": ""}
def _command_tokens(command: str) -> list[str]:
    seen, tokens = set(), []
    for token in [*_QUOTED_TOKEN_RE.findall(command), *_WORD_TOKEN_RE.findall(command)]:
        token = token.strip()
        if len(token) < 3 or token.lower() in _NOISE_TOKENS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens[:12]
def _pick_delimiter(text: str, command: str) -> str | None:
    if "," in text:
        return ","
    if "\t" in text:
        return "\t"
    if "|" in text:
        return "|"
    return "," if any(token in command.lower() for token in ("csv", "dictreader", "delimiter", "split(", "cut -d", "awk -f")) else None
def _grounding_status(history: list[dict[str, Any]], observation: dict[str, Any]) -> str:
    if observation.get("role") != "assistant":
        return "pending"
    content = observation.get("content")
    if not isinstance(content, str) or not content:
        return "n/a"
    for row in reversed(history):
        created = row.get("structured_observation_register", {}).get("created_observations")
        if not isinstance(created, list):
            continue
        for item in created:
            token = item.get("matched_token") if isinstance(item, dict) else ""
            if isinstance(token, str) and token and token in content:
                return "yes"
        return "no"
    return "no"
def _try_json(text: str) -> Any:
    try:
        return json.loads(text) if isinstance(text, str) and text else None
    except json.JSONDecodeError:
        return None
def _try_python_literal(text: str) -> Any:
    try:
        return ast.literal_eval(text) if isinstance(text, str) and text else None
    except (SyntaxError, ValueError):
        return None
def _dedupe_records(records: list[tuple[str, Any, str]]) -> list[tuple[str, Any, str]]:
    seen, unique = set(), []
    for obs_type, record, confidence in records:
        sig = json.dumps({"t": obs_type, "r": record}, sort_keys=True, ensure_ascii=True, default=str)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append((obs_type, record, confidence))
    return unique
