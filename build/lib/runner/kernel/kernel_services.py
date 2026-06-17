"""Generic service/process tracking helpers for the active kernel."""

from __future__ import annotations

import re
from typing import Any


_START_PATTERNS = (
    r"\blaunch_service\.py\b",
    r"\buvicorn\b",
    r"\bflask\b",
    r"\bpython(?:3)?\s+-m\s+http\.server\b",
    r"\bwebsockify\b",
    r"\bnginx\b",
    r"\bqemu-system-[^\s]+\b",
    r"\bnode\b",
)
_PROBE_PATTERNS = (r"\bcurl\b", r"\bwget\b", r"\bnc\b", r"\bnetcat\b")


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def classify_service_command(command: str) -> dict[str, Any]:
    normalized = command.strip().lower()
    port_match = re.search(r"(?:--port\s+|:)(\d{2,5})\b", normalized)
    port = int(port_match.group(1)) if port_match else None
    service_name = None
    script_match = re.search(r"([\w./-]+(?:launch_service\.py|probe_service\.py|server\.py|app\.py))", command)
    if script_match:
        service_name = script_match.group(1).rsplit("/", 1)[-1].replace(".py", "")
    if port is not None:
        service_name = f"service@{port}"
    elif not service_name:
        service_name = "service@unknown"
    if any(re.search(pattern, normalized) for pattern in _PROBE_PATTERNS):
        return {"kind": "probe_service", "service_name": service_name, "port": port, "command": command}
    if any(re.search(pattern, normalized) for pattern in _START_PATTERNS) or "nohup" in normalized:
        return {"kind": "start_service", "service_name": service_name, "port": port, "command": command}
    return {"kind": "command", "service_name": service_name, "port": port, "command": command}


def update_service_state(
    *,
    service_registry: dict[str, dict[str, Any]],
    process_registry: dict[str, dict[str, Any]],
    receipt: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    action_type = receipt.get("action_type")
    if action_type not in {"start_service", "probe_service"}:
        return None, None
    service_name = receipt.get("service_name")
    if not service_name:
        return None, None
    entry = dict(service_registry.get(service_name, {}))
    process_entry = dict(process_registry.get(service_name, {}))
    events = list(entry.get("events", []))
    event = {
        "receipt_id": receipt.get("receipt_id"),
        "action_type": receipt.get("action_type"),
        "reason_code": receipt.get("reason_code"),
        "exit_code": receipt.get("exit_code"),
        "timed_out": bool(receipt.get("timed_out")),
    }
    events.append(event)
    
    port = None
    if "@" in service_name:
        try:
            port = int(service_name.split("@")[-1])
        except ValueError:
            pass
            
    pid = receipt.get("pid")
    status = receipt.get("service_status") or "running"
    
    if action_type == "start_service":
        process_entry["pid"] = pid
        process_entry["start_receipt_id"] = receipt.get("receipt_id")
        process_entry["status"] = status
        if port is not None:
            process_entry["port"] = port
        probe = dict(entry.get("probe", {}))
    else:
        # probe_service
        probe = {
            "receipt_id": receipt.get("receipt_id"),
            "status": status,
            "reason_code": receipt.get("reason_code"),
            "command": receipt.get("command"),
        }
        process_entry.setdefault("start_receipt_id", None)
        process_entry["last_probe_receipt_id"] = receipt.get("receipt_id")
        process_entry["status"] = status
        if port is not None:
            process_entry["port"] = port
            
    entry.update(
        {
            "status": status,
            "pid": pid,
            "last_action_type": action_type,
            "probe": probe,
            "events": events,
        }
    )
    if port is not None:
        entry["port"] = port
        
    service_registry[service_name] = entry
    process_registry[service_name] = process_entry
    return service_name, entry


def project_service_summary(
    service_registry: dict[str, dict[str, Any]],
    process_registry: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    service_summary = {
        name: {
            "status": value.get("status"),
            "pid": value.get("pid"),
            "port": value.get("port"),
            "last_action_type": value.get("last_action_type"),
            "event_count": len(value.get("events", [])) if isinstance(value.get("events"), list) else 0,
        }
        for name, value in service_registry.items()
        if isinstance(value, dict)
    }
    process_summary = {
        name: {
            "status": value.get("status"),
            "pid": value.get("pid"),
            "port": value.get("port"),
            "start_receipt_id": value.get("start_receipt_id"),
            "last_probe_receipt_id": value.get("last_probe_receipt_id"),
        }
        for name, value in process_registry.items()
        if isinstance(value, dict)
    }
    not_ready = sorted(name for name, value in service_summary.items() if value.get("status") not in {"ready", "running", "starting"})
    not_running = sorted(name for name, value in process_summary.items() if value.get("status") not in {"running", "starting", "ready"})
    return {
        "service_summary": service_summary,
        "process_summary": process_summary,
        "service_not_ready": not_ready,
        "process_not_running": not_running,
    }


def _exit_code(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return 1
