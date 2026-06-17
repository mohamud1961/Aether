"""Receipt helpers for the active evidence kernel."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def summarize_text(value: Any, *, limit: int = 220) -> str:
    if not isinstance(value, str):
        return ""
    text = value.replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    head = text[: max(0, limit - 24)].rstrip()
    tail = text[-8:].lstrip() if len(text) > 8 else ""
    suffix = f" … [truncated {len(text) - len(head) - len(tail)} chars]"
    return f"{head}{suffix}{tail}"


@dataclass(frozen=True)
class KernelReceipt:
    receipt_id: str
    action_id: str
    action_type: str
    tool_name: str
    command: str
    cwd: str
    exit_code: int
    reason_code: str
    stdout_sha256: str
    stderr_sha256: str
    stdout_excerpt: str
    stderr_excerpt: str
    provenance_refs: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    deleted_files: tuple[str, ...] = ()
    mutation_observed: bool = False
    service_name: str | None = None
    service_status: str | None = None
    native_tool_status: str | None = None
    verifier_status: str | None = None
    tool_contract_status: dict[str, Any] | None = None
    pid: int | None = None
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "tool_name": self.tool_name,
            "command": self.command,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "reason_code": self.reason_code,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "stdout_excerpt": self.stdout_excerpt,
            "stderr_excerpt": self.stderr_excerpt,
            "provenance_refs": list(self.provenance_refs),
            "changed_files": list(self.changed_files),
            "deleted_files": list(self.deleted_files),
            "mutation_observed": self.mutation_observed,
            "service_name": self.service_name,
            "service_status": self.service_status,
            "native_tool_status": self.native_tool_status,
            "verifier_status": self.verifier_status,
            "tool_contract_status": dict(self.tool_contract_status or {}),
            "pid": self.pid,
            "timed_out": self.timed_out,
        }


def build_receipt(
    *,
    receipt_id: str,
    action_id: str,
    action_type: str,
    tool_name: str,
    command: str,
    cwd: str,
    exit_code: int,
    reason_code: str,
    stdout: str = "",
    stderr: str = "",
    changed_files: list[str] | tuple[str, ...] | None = None,
    deleted_files: list[str] | tuple[str, ...] | None = None,
    mutation_observed: bool = False,
    service_name: str | None = None,
    service_status: str | None = None,
    native_tool_status: str | None = None,
    verifier_status: str | None = None,
    tool_contract_status: dict[str, Any] | None = None,
    pid: int | None = None,
    timed_out: bool = False,
) -> dict[str, Any]:
    changed_files_tuple = tuple(str(path) for path in (changed_files or []) if isinstance(path, str) and path)
    deleted_files_tuple = tuple(str(path) for path in (deleted_files or []) if isinstance(path, str) and path)
    provenance_refs: list[str] = []
    provenance_refs.extend(f"changed_file:{path}" for path in changed_files_tuple)
    provenance_refs.extend(f"deleted_file:{path}" for path in deleted_files_tuple)
    if stdout:
        provenance_refs.append(f"stdout_sha256:{_hash_text(stdout)}")
    if stderr:
        provenance_refs.append(f"stderr_sha256:{_hash_text(stderr)}")
    if service_name:
        provenance_refs.append(f"service_name:{service_name}")
    if service_status:
        provenance_refs.append(f"service_status:{service_status}")
    if native_tool_status:
        provenance_refs.append(f"native_tool_status:{native_tool_status}")
    if verifier_status:
        provenance_refs.append(f"verifier_status:{verifier_status}")
    if isinstance(tool_contract_status, dict):
        status = tool_contract_status.get("status")
        if isinstance(status, str) and status:
            provenance_refs.append(f"tool_contract_status:{status}")
    if pid is not None:
        provenance_refs.append(f"pid:{pid}")
    receipt = KernelReceipt(
        receipt_id=receipt_id,
        action_id=action_id,
        action_type=action_type,
        tool_name=tool_name,
        command=command,
        cwd=cwd,
        exit_code=exit_code,
        reason_code=reason_code,
        stdout_sha256=_hash_text(stdout),
        stderr_sha256=_hash_text(stderr),
        stdout_excerpt=summarize_text(stdout),
        stderr_excerpt=summarize_text(stderr),
        provenance_refs=tuple(_dedupe_strings(provenance_refs)),
        changed_files=changed_files_tuple,
        deleted_files=deleted_files_tuple,
        mutation_observed=mutation_observed,
        service_name=service_name,
        service_status=service_status,
        native_tool_status=native_tool_status,
        verifier_status=verifier_status,
        tool_contract_status=dict(tool_contract_status or {}),
        pid=pid,
        timed_out=timed_out,
    )
    return receipt.to_dict()


def summarize_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        return {}
    summary = {
        "receipt_id": receipt.get("receipt_id"),
        "action_id": receipt.get("action_id"),
        "action_type": receipt.get("action_type"),
        "tool_name": receipt.get("tool_name"),
        "command": summarize_text(receipt.get("command")),
        "exit_code": receipt.get("exit_code"),
        "reason_code": receipt.get("reason_code"),
        "stdout_sha256": receipt.get("stdout_sha256"),
        "stderr_sha256": receipt.get("stderr_sha256"),
        "provenance_refs": list(receipt.get("provenance_refs", []))[:5],
        "changed_files": list(receipt.get("changed_files", []))[:5],
        "deleted_files": list(receipt.get("deleted_files", []))[:5],
        "mutation_observed": bool(receipt.get("mutation_observed")),
        "service_name": receipt.get("service_name"),
        "service_status": receipt.get("service_status"),
        "native_tool_status": receipt.get("native_tool_status"),
        "verifier_status": receipt.get("verifier_status"),
    }
    tool_contract = receipt.get("tool_contract_status")
    if isinstance(tool_contract, dict) and tool_contract:
        summary["tool_contract_status"] = {
            key: value
            for key, value in tool_contract.items()
            if isinstance(value, (str, int, float, bool)) and not isinstance(value, bool)
        }
    return summary


def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def compact_receipt_digest(receipts: list[dict[str, Any]]) -> str:
    payload = json.dumps(receipts, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
