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
    handle: str = ""
    check_id: str = ""
    receipt_kind: str = ""
    limit: int = 5
    command: str = ""
    content: str = ""
    target: str = ""
    offset: int = 0
    span: int = 4000


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
        if kind == "run_check":
            kind = "rerun_check"
        if not kind:
            continue
        parsed.append(
            VerifierInspectionRequest(
                request_id=str(item.get("request_id", f"inspect-{idx}")).strip() or f"inspect-{idx}",
                kind=kind,
                path=str(item.get("path", "")).strip(),
                handle=str(item.get("handle", "")).strip(),
                check_id=str(item.get("check_id", "")).strip(),
                receipt_kind=str(item.get("receipt_kind", "")).strip(),
                limit=max(1, int(item.get("limit", 5) or 5)),
                command=str(item.get("command", "")),
                content=str(item.get("content", "")),
                target=str(item.get("target", "")).strip(),
                offset=max(0, int(item.get("offset", 0) or 0)),
                span=max(1, int(item.get("span", item.get("limit", 4000)) or 4000)),
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
    hooks: Any | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    checks_by_id = {check.check_id: check for check in compiled.planned_checks()}
    all_receipts = tuple(ledger.all_receipts())
    for request in requests:
        if request.kind == "read_file":
            results.append(_read_file_result(request, executor, envmap))
            continue
        if request.kind == "read_output":
            results.append(_read_output_result(request, all_receipts))
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
        if request.kind == "perceive_artifact":
            results.append(_perceive_artifact_result(request, executor, envmap, hooks))
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


def _perceive_artifact_result(
    request: VerifierInspectionRequest, executor: Any, envmap: EnvMap, hooks: Any,
) -> dict[str, Any]:
    """Independent verifier perception: transcribe an image artifact through
    the run's vision model.  The result is the verifier's OWN reading -- it
    never depends on solver-produced transcriptions -- and is still labeled
    model-derived, not ground truth."""
    from .perception_vision import media_type_for
    import base64 as _b64

    perceive = getattr(hooks, "perceive_image", None)
    if not callable(perceive):
        return _error_result(request, "no vision model available for perceive_artifact")
    path = normalize_relpath(request.path, envmap.workspace_root)
    media_type = media_type_for(path)
    if not media_type:
        return _error_result(request, f"unsupported media type for perceive_artifact: {path}")
    read_bytes = getattr(executor, "read_file_bytes", None)
    if not callable(read_bytes):
        return _error_result(request, "executor lacks binary reads for perceive_artifact")
    try:
        raw = read_bytes(path)
    except (OSError, FileNotFoundError) as exc:
        return _error_result(request, f"perceive_artifact read failed: {exc}")
    prompt = (
        "Transcribe/describe the semantic content of this image exactly and "
        "completely. Code and text verbatim; labeled elements and values precisely. "
        "Output only the transcription/description."
    )
    try:
        transcription = str(perceive(prompt, _b64.b64encode(raw).decode("ascii"), media_type))
    except Exception as exc:
        return _error_result(request, f"perceive_artifact vision call failed: {exc}")
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "path": path,
        "media_type": media_type,
        "bytes": len(raw),
        "transcription": transcription[:8000],
        "extraction_authority": "model_transcription_not_ground_truth",
        "read_only": True,
    }


def _read_file_result(request: VerifierInspectionRequest, executor: Any, envmap: EnvMap) -> dict[str, Any]:
    path = normalize_relpath(request.path, envmap.workspace_root)
    if any(token in path for token in ("*", "?", "[")):
        matches = tuple(executor.glob(path))[: max(1, request.limit)]
        rows = []
        for matched in matches:
            try:
                content = executor.read_file(matched)
            except FileNotFoundError:
                rows.append({"path": matched, "error": "file_not_found"})
                continue
            rows.append({
                "path": matched,
                "bytes": len(content),
                "content_hash": sha256(content.encode("utf-8", "replace")).hexdigest()[:16],
                "excerpt": content[: min(1000, len(content))],
            })
        return {
            "request_id": request.request_id,
            "kind": request.kind,
            "path": path,
            "matched_paths": list(matches),
            "matches": rows,
        }
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


def _read_output_result(request: VerifierInspectionRequest, receipts: tuple[Any, ...]) -> dict[str, Any]:
    handle = request.handle or request.path or request.target
    if not handle:
        return _error_result(request, "read_output requires handle")

    full = ""
    source_receipt = ""
    stream = ""
    overflow = ""
    for receipt in receipts:
        payload = receipt.payload or {}
        if payload.get("stdout_handle") == handle:
            full = str(payload.get("stdout_full", ""))
            source_receipt = receipt.receipt_id
            stream = "stdout"
            overflow = str(payload.get("stdout_overflow_path", ""))
            break
        if payload.get("stderr_handle") == handle:
            full = str(payload.get("stderr_full", ""))
            source_receipt = receipt.receipt_id
            stream = "stderr"
            overflow = str(payload.get("stderr_overflow_path", ""))
            break
    if not source_receipt:
        return _error_result(request, f"output handle not found: {handle}")
    if overflow:
        try:
            with open(overflow, encoding="utf-8", errors="replace") as fh:
                full = fh.read()
        except OSError as exc:
            return _error_result(request, f"output spool unreadable for handle {handle}: {exc}")

    offset = max(0, int(getattr(request, "offset", 0) or 0))
    span = max(1, min(20000, int(getattr(request, "span", 4000) or 4000)))
    excerpt = full[offset: offset + span]
    return {
        "request_id": request.request_id,
        "kind": request.kind,
        "handle": handle,
        "source_receipt_id": source_receipt,
        "stream": stream,
        "bytes": len(full),
        "offset": offset,
        "span": span,
        "excerpt": excerpt,
        "content_hash": sha256(full.encode("utf-8", "replace")).hexdigest()[:16],
        "read_only": True,
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
        text = value.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        decoder = json.JSONDecoder()
        for idx, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(text[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise TypeError("inspection request must be a JSON object or JSON object string")
