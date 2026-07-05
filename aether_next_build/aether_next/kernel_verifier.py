"""Optional model-verifier gate integration for the kernel."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import threading
from typing import Any

from .ledger import ExecutionLedger, Receipt
from .runtime_ir import CompiledRuntime
from .verifier import ModelVerifierResult, parse_model_verifier_result
from .verifier_inspector import (
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
)
from .verifier_overlay import VerifierOverlay
from .verifier_packets import build_verifier_packet

_REASON_ALIASES = {
    "solver_submit_success_candidate": "solver_submit",
    "deterministic_success_candidate": "deterministic_success_candidate",
    "deterministic_failure": "deterministic_failure",
    "max_steps": "deterministic_failure",
    "no_progress": "deterministic_failure",
    "blocked_by_harness_config": "deterministic_failure",
    "uncertain_missing_evidence": "deterministic_failure",
}


def run_model_verifier_if_available(
    hooks: Any,
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    *,
    step: int,
    reason: str,
    executor: Any | None = None,
    envmap: Any | None = None,
) -> ModelVerifierResult | None:
    verify = getattr(hooks, "verify", None)
    if verify is None:
        return None
    allowed = _verifier_reason_allowed(compiled, reason)
    if not allowed:
        ledger.record(Receipt(
            receipt_id=f"step-{step}:model_verifier_skipped:{reason}",
            step=step,
            kind="model_verifier_skipped",
            success=True,
            summary=f"model verifier skipped by policy for {reason}",
            payload={
                "reason": reason,
                "policy": {
                    "enabled": compiled.model_verifier_policy.enabled,
                    "runs_on": list(compiled.model_verifier_policy.runs_on),
                },
            },
        ))
        return None
    packet = build_verifier_packet(compiled, ledger, step=step, reason=reason)
    ledger.record(Receipt(
        receipt_id=f"step-{step}:model_verifier_packet:{reason}",
        step=step,
        kind="model_verifier_packet",
        success=True,
        summary=f"model verifier packet built for {reason}",
        payload={"reason": reason, "packet": packet},
    ))
    try:
        raw = _call_verify_with_timeout(
            hooks,
            verify,
            packet,
            compiled,
            ledger,
            step=step,
            executor=executor,
            envmap=envmap,
        )
        result = parse_model_verifier_result(raw)
    except Exception as exc:
        ledger.record(Receipt(
            receipt_id=f"step-{step}:model_verifier_error:{reason}",
            step=step,
            kind="model_verifier_error",
            success=False,
            summary=f"model verifier failed for {reason}: {exc}",
            failure_class="model_verifier_error",
            payload={"reason": reason, "error": str(exc)},
        ))
        _persist_verifier_bundle(
            step=step,
            reason=reason,
            packet=packet,
            raw_output=None,
            parsed_result=None,
            active_findings_after=ledger.active_finding_context(step + 1),
            error=str(exc),
        )
        return None
    ledger.apply_verifier_result(result, step=step, compiled=compiled)
    active_after = ledger.active_finding_context(step + 1)
    result_receipt = ledger.latest_receipt("model_verifier_result")
    if result_receipt is not None:
        result_receipt.payload.update({
            "reason": reason,
            "verifier_packet": packet,
            "raw_verifier_output": raw,
            "parsed_verifier_result": result.as_dict(),
            "active_findings_after": active_after,
        })
    _persist_verifier_bundle(
        step=step,
        reason=reason,
        packet=packet,
        raw_output=raw,
        parsed_result=result.as_dict(),
        active_findings_after=active_after,
    )
    return result


def _call_verify_with_timeout(
    hooks: Any,
    verify: Any,
    packet: dict[str, Any],
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    *,
    step: int,
    executor: Any | None = None,
    envmap: Any | None = None,
) -> Any:
    timeout_s = float(os.environ.get("AETHER_MODEL_VERIFIER_TIMEOUT_S", "180"))
    if timeout_s <= 0:
        return _call_verify(
            hooks,
            verify,
            packet,
            compiled,
            ledger,
            step=step,
            executor=executor,
            envmap=envmap,
        )

    results: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def _target() -> None:
        try:
            results.put((
                True,
                _call_verify(
                    hooks,
                    verify,
                    packet,
                    compiled,
                    ledger,
                    step=step,
                    executor=executor,
                    envmap=envmap,
                ),
            ))
        except Exception as exc:  # pragma: no cover - exercised through caller
            results.put((False, exc))

    thread = threading.Thread(target=_target, name="aether-model-verifier", daemon=True)
    thread.start()
    try:
        ok, value = results.get(timeout=timeout_s)
    except queue.Empty as exc:
        raise TimeoutError(f"model verifier timed out after {timeout_s:.0f}s") from exc
    if ok:
        return value
    raise value


def _call_verify(
    hooks: Any,
    verify: Any,
    packet: dict[str, Any],
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    *,
    step: int,
    executor: Any | None = None,
    envmap: Any | None = None,
) -> Any:
    verify_with_inspector = getattr(hooks, "verify_with_inspector", None)
    if callable(verify_with_inspector) and executor is not None and envmap is not None:
        overlay = VerifierOverlay(executor, envmap.workspace_root)

        def _inspector(requests: tuple[VerifierInspectionRequest, ...]) -> list[dict[str, Any]]:
            results = execute_verifier_inspection_requests(
                requests,
                compiled=compiled,
                ledger=ledger,
                executor=executor,
                envmap=envmap,
                overlay=overlay,
            )
            ledger.record(Receipt(
                receipt_id=f"step-{step}:model_verifier_inspection:{len(ledger.all_receipts())}",
                step=step,
                kind="model_verifier_inspection",
                success=True,
                summary=f"model verifier inspection executed: {', '.join(request.kind for request in requests)}",
                payload={
                    "requests": [
                        {
                            "request_id": request.request_id,
                            "kind": request.kind,
                            "path": request.path,
                            "check_id": request.check_id,
                            "receipt_kind": request.receipt_kind,
                            "limit": request.limit,
                            "command": getattr(request, "command", ""),
                        }
                        for request in requests
                    ],
                    "results": results,
                },
            ))
            return results

        try:
            return verify_with_inspector(packet, compiled, ledger, _inspector)
        finally:
            # Rollback is unconditional: the overlay never outlives the
            # verification round, pass or fail.
            teardown = overlay.teardown()
            if teardown.get("overlay_root"):
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:model_verifier_overlay_teardown",
                    step=step,
                    kind="model_verifier_overlay_teardown",
                    success=bool(teardown.get("removed")),
                    summary=f"verifier overlay removed: {teardown.get('overlay_root')}",
                    payload=teardown,
                ))
    return verify(packet, compiled, ledger)


def _verifier_reason_allowed(compiled: CompiledRuntime, reason: str) -> bool:
    policy = compiled.model_verifier_policy
    if not policy.enabled:
        return False
    runs_on = set(policy.runs_on)
    alias = _REASON_ALIASES.get(reason, reason)
    return reason in runs_on or alias in runs_on


def _persist_verifier_bundle(
    *,
    step: int,
    reason: str,
    packet: dict[str, Any],
    raw_output: Any,
    parsed_result: dict[str, Any] | None,
    active_findings_after: list[dict[str, Any]],
    error: str = "",
) -> None:
    root = os.environ.get("AETHER_VERIFIER_EVIDENCE_DIR", "").strip()
    if not root:
        return
    safe_reason = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in reason)[:80]
    out_dir = Path(root) / f"step_{step:04d}_{safe_reason}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verifier_packet.json").write_text(json.dumps(packet, indent=2, sort_keys=True, default=str))
    (out_dir / "verifier_prompt.txt").write_text(str(packet.get("architect_verifier_prompt", {}).get("rendered", "")))
    if raw_output is not None:
        if isinstance(raw_output, str):
            (out_dir / "raw_verifier_output.txt").write_text(raw_output)
        else:
            (out_dir / "raw_verifier_output.txt").write_text(json.dumps(raw_output, indent=2, sort_keys=True, default=str))
    if parsed_result is not None:
        (out_dir / "parsed_verifier_result.json").write_text(json.dumps(parsed_result, indent=2, sort_keys=True, default=str))
    (out_dir / "active_findings_after.json").write_text(json.dumps(active_findings_after, indent=2, sort_keys=True, default=str))
    if error:
        (out_dir / "verifier_error.txt").write_text(error)
