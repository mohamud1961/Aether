"""Read-only verifier inspection requests and execution helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from .memory_events import artifact_history
from .runtime_ir import CompiledRuntime, EnvMap, normalize_relpath
from .verifier_probes import (
    inspect_artifact_probe,
    probe_http,
    probe_port,
    probe_process,
)


@dataclass(frozen=True)
class VerifierInspectionRequest:
    request_id: str
    kind: str
    path: str = ""
    check_id: str = ""
    receipt_kind: str = ""
    limit: int = 5
    command: str = ""
    content: str = ""
    target: str = ""
    offset: int = 0


def parse_verifier_inspection_requests(value: Any) -> tuple[VerifierInspectionRequest, ...]:
    data = _load_mapping(value)
    if str(data.get("kind", "")).strip() != "inspect":
        raise ValueError("verifier output is not an inspection request")
    raw = data.get("requests", ())
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not raw:
        raise ValueError("inspection request requires a non-empty requests list")
    parsed: list[VerifierInspectionRequest] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "")).strip()
        if not kind:
            continue
        parsed.append(
            VerifierInspectionRequest(
                request_id=str(item.get("request_id", f"inspect-{idx}")).strip() or f"inspect-{idx}",
                kind=kind,
                path=str(item.get("path", "")).strip(),
                check_id=str(item.get("check_id", "")).strip(),
                receipt_kind=str(item.get("receipt_kind", "")).strip(),
                limit=max(1, int(item.get("limit", 5) or 5)),
                command=str(item.get("command", "")),
                content=str(item.get("content", "")),
                target=str(item.get("target", "")).strip(),
                offset=max(0, int(item.get("offset", 0) or 0)),
            )
        )
    if not parsed:
        raise ValueError("inspection request contained no valid entries")
    return tuple(parsed)


def execute_verifier_inspection_requests(
    requests: tuple[VerifierInspectionRequest, ...],
    *,
    compiled: CompiledRuntime,
    ledger: Any,
    executor: Any,
    envmap: EnvMap,
    overlay: Any | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    checks_by_id = {check.check_id: check for check in compiled.planned_checks()}
    all_receipts = tuple(ledger.all_receipts())
    for request in requests:
        if request.kind == "read_file":
            results.append(_read_file_result(request, executor, envmap))
            continue
        if request.kind == "rerun_check":
            check = checks_by_id.get(request.check_id)
            if check is None:
                results.append(_error_result(request, f"unknown check_id: {request.check_id}"))
                continue
            if overlay is None:
                results.append(_error_result(
                    request,
                    "rerun_check requires the verifier overlay; no overlay available",
                ))
                continue
            # Checks execute in the copy-on-demand overlay so verification can
            # never mutate the solver workspace.
            outcome = overlay.run_command(check.command)
            row = {
                "request_id": request.request_id,
                "kind": request.kind,
                "check_id": check.check_id,
                "label": check.label,
                "executed_in": "verifier_overlay",
            }
            row.update(outcome)
            results.append(row)
            continue
        if request.kind == "overlay_run_command":
            if overlay is None:
                results.append(_error_result(request, "no overlay available"))
                continue
            if not getattr(request, "command", "").strip():
                results.append(_error_result(request, "overlay_run_command requires command"))
                continue
            row = {"request_id": request.request_id, "kind": request.kind, "executed_in": "verifier_overlay"}
            row.update(overlay.run_command(getattr(request, "command", "")))
            results.append(row)
            continue
        if request.kind == "overlay_write_fixture":
            if overlay is None:
                results.append(_error_result(request, "no overlay available"))
                continue
            if not request.path.strip():
                results.append(_error_result(request, "overlay_write_fixture requires path"))
                continue
            row = {"request_id": request.request_id, "kind": request.kind, "executed_in": "verifier_overlay"}
            row.update(overlay.write_fixture(request.path, getattr(request, "content", "")))
            results.append(row)
            continue
        if request.kind in {"probe_port", "probe_http", "probe_process", "inspect_artifact"}:
            target = getattr(request, "target", "") or request.path
            if request.kind == "probe_port":
                probe = probe_port(executor, target)
            elif request.kind == "probe_http":
                probe = probe_http(executor, target)
            elif request.kind == "probe_process":
                probe = probe_process(executor, target)
            else:
                probe = inspect_artifact_probe(
                    executor, normalize_relpath(request.path, envmap.workspace_root),
                )
            row = {"request_id": request.request_id, "kind": request.kind, "read_only": True}
            row.update(probe)
            results.append(row)
            continue
        if request.kind == "inspect_artifact_history":
            rows = [
                row
                for row in artifact_history(all_receipts, limit=max(12, request.limit))
                if not request.path or request.path in row.get("matched_paths", []) or request.path == row.get("path", "")
            ]
            results.append({
                "request_id": request.request_id,
                "kind": request.kind,
                "path": request.path,
                "rows": rows[-request.limit :],
            })
            continue
        if request.kind == "inspect_recent_receipts":
            rows = []
            for receipt in all_receipts:
                if request.receipt_kind and receipt.kind != request.receipt_kind:
                    continue
                rows.append({
                    "receipt_id": receipt.receipt_id,
                    "step": receipt.step,
                    "kind": receipt.kind,
                    "success": receipt.success,
                    "summary": receipt.summary,
                    "failure_class": receipt.failure_class,
                })
            results.append({
                "request_id": request.request_id,
                "kind": request.kind,
                "receipt_kind": request.receipt_kind,
                "rows": rows[-request.limit :],
            })
            continue
        results.append(_error_result(request, f"unsupported inspection kind: {request.kind}"))
    return results


def _read_file_result(request: VerifierInspectionRequest, executor: Any, envmap: EnvMap) -> dict[str, Any]:
    path = normalize_relpath(request.path, envmap.workspace_root)
    try:
        content = executor.read_file(path)
    except FileNotFoundError:
        return _error_result(request, f"file not found: {path}")
    offset = max(0, int(getattr(request, "offset", 0) or 0))
    excerpt = content[offset: offset + 4000]
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "path": path,
        "bytes": len(content),
        "offset": offset,
        "content_hash": sha256(content.encode("utf-8", "replace")).hexdigest()[:16],
        "excerpt": excerpt,
    }


def _error_result(request: VerifierInspectionRequest, message: str) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "error": message,
    }


def _load_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise TypeError("inspection request must be a JSON object or JSON object string")
