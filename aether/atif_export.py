"""ATIF-v1.7 projection derived from Aether's existing evidence plane.

ATIF is an export/view, never an action or evidence authority. The immutable
ExecutionLedger receipts remain the exact task-reality source. This module emits
the model-visible observation projection plus receipt/handle provenance so
large exact payloads do not become a duplicate trajectory evidence database.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .model_parse import parse_solver_turn

ATIF_SCHEMA_VERSION = "ATIF-v1.7"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _visible_receipt_content(receipt: Mapping[str, Any]) -> str:
    payload = receipt.get("payload") if isinstance(receipt.get("payload"), Mapping) else {}
    kind = str(receipt.get("kind", ""))
    if kind == "run_command":
        return json.dumps({
            "exit_code": payload.get("exit_code"),
            "stdout": payload.get("stdout", ""),
            "stderr": payload.get("stderr", ""),
            "timed_out": payload.get("timed_out", False),
        }, ensure_ascii=False, sort_keys=True)
    for key in ("chunk", "output", "content", "detail"):
        if key in payload:
            return str(payload.get(key, ""))
    return str(receipt.get("summary", ""))


def _receipt_extra(receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload = receipt.get("payload") if isinstance(receipt.get("payload"), Mapping) else {}
    keep = (
        "stdout_handle", "stderr_handle", "stdout_bytes", "stderr_bytes",
        "file_handle", "source_receipt_id", "stream", "content_hash",
        "before_content_hash", "after_content_hash", "artifact_paths",
        "modified_paths", "removed_paths", "process_id", "process_generation",
        "session_id", "state_delta", "timed_out", "exit_code",
    )
    return {
        "aether_receipt_id": str(receipt.get("receipt_id", "")),
        "aether_step": int(receipt.get("step", 0) or 0),
        "aether_kind": str(receipt.get("kind", "")),
        "success": bool(receipt.get("success", False)),
        "state_change": bool(receipt.get("state_change", False)),
        "failure_class": str(receipt.get("failure_class", "")),
        **{key: _json_safe(payload[key]) for key in keep if key in payload and payload[key] not in (None, "", [], (), {})},
    }


def _action_receipt(receipts: Iterable[Mapping[str, Any]], action_id: str) -> Mapping[str, Any] | None:
    marker = f":{action_id}:"
    for receipt in receipts:
        if marker in str(receipt.get("receipt_id", "")):
            return receipt
    return None


def _aggregate_metrics(telemetry: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    prompt = completion = cached = 0
    cost = 0.0
    seen_prompt = seen_completion = seen_cached = seen_cost = False
    for row in telemetry:
        if row.get("input_tokens") is not None:
            prompt += int(row.get("input_tokens") or 0); seen_prompt = True
        if row.get("output_tokens") is not None:
            completion += int(row.get("output_tokens") or 0); seen_completion = True
        if row.get("cached_input_tokens") is not None:
            cached += int(row.get("cached_input_tokens") or 0); seen_cached = True
        if row.get("cost_usd") is not None:
            cost += float(row.get("cost_usd") or 0.0); seen_cost = True
    result: dict[str, Any] = {}
    if seen_prompt: result["total_prompt_tokens"] = prompt
    if seen_completion: result["total_completion_tokens"] = completion
    if seen_cached: result["total_cached_tokens"] = cached
    if seen_cost: result["total_cost_usd"] = round(cost, 8)
    return result


def build_atif_trajectory(
    *,
    instruction: str,
    run_record: Mapping[str, Any],
    agent_name: str = "aether-next",
    agent_version: str = "postmerge-v3",
    model_name: str | None = None,
) -> dict[str, Any]:
    """Build a schema-shaped ATIF-v1.7 trajectory from exact Aether records."""
    runtime_identity = run_record.get("runtime_identity") if isinstance(run_record.get("runtime_identity"), Mapping) else {}
    session_id = str(runtime_identity.get("run_id") or "aether-run")
    trajectory_id = "aether-primary-" + sha256(session_id.encode("utf-8")).hexdigest()[:16]
    receipts = [row for row in run_record.get("receipt_records", ()) if isinstance(row, Mapping)]
    exchanges = [row for row in run_record.get("model_exchange_records", ()) if isinstance(row, Mapping)]
    telemetry = [row for row in run_record.get("model_call_telemetry", ()) if isinstance(row, Mapping)]

    steps: list[dict[str, Any]] = [{
        "step_id": 1,
        "source": "user",
        "message": str(instruction),
        "extra": {"raw_task_sha256": runtime_identity.get("raw_task_sha256", "")},
    }]
    used_receipts: set[str] = set()
    verifier_exchanges: list[Mapping[str, Any]] = []

    for exchange in exchanges:
        role = str(exchange.get("model_role", ""))
        if role.startswith("verifier"):
            verifier_exchanges.append(exchange)
            continue
        if role != "solver":
            continue
        output = str(exchange.get("output", ""))
        step: dict[str, Any] = {
            "step_id": len(steps) + 1,
            "source": "agent",
            "message": output,
            "llm_call_count": 1,
            "extra": {
                "aether_model_role": role,
                "role_call_ordinal": exchange.get("role_call_ordinal"),
                "input_transcript_sha256": exchange.get("input_transcript_sha256", ""),
                "output_sha256": exchange.get("output_sha256", ""),
                "provider_call_succeeded": bool(exchange.get("provider_call_succeeded", False)),
            },
        }
        if not exchange.get("provider_call_succeeded", False):
            step["extra"].update({
                "provider_error_type": exchange.get("error_type", ""),
                "provider_error": exchange.get("error", ""),
            })
        else:
            try:
                turn = parse_solver_turn(output)
            except Exception as exc:  # malformed visible output is still trajectory evidence
                step["extra"]["aether_parse_status"] = "rejected"
                step["extra"]["aether_parse_error"] = str(exc)[:1000]
            else:
                step["extra"]["aether_parse_status"] = "accepted"
                if turn.kind == "act" and turn.actions:
                    action = turn.actions[0]
                    step["tool_calls"] = [{
                        "tool_call_id": action.action_id,
                        "function_name": action.kind,
                        "arguments": _json_safe(dict(action.arguments)),
                        "extra": {"capability_id": action.capability_id},
                    }]
                    receipt = _action_receipt(receipts, action.action_id)
                    if receipt is not None:
                        rid = str(receipt.get("receipt_id", "")); used_receipts.add(rid)
                        step["observation"] = {"results": [{
                            "source_call_id": action.action_id,
                            "content": _visible_receipt_content(receipt),
                            "extra": _receipt_extra(receipt),
                        }]}
        steps.append(step)

    # Runtime receipts not directly paired with a Solver tool call remain exact
    # Aether events. Export them as system observations, preserving their Aether
    # step and receipt identity rather than pretending a model call caused them.
    for receipt in receipts:
        rid = str(receipt.get("receipt_id", ""))
        if not rid or rid in used_receipts:
            continue
        steps.append({
            "step_id": len(steps) + 1,
            "source": "system",
            "message": "Aether provenance-bound runtime event",
            "observation": {"results": [{
                "content": _visible_receipt_content(receipt),
                "extra": _receipt_extra(receipt),
            }]},
            "extra": {"aether_export_kind": "unpaired_runtime_event"},
        })

    subagents: list[dict[str, Any]] = []
    if verifier_exchanges:
        verifier_steps: list[dict[str, Any]] = []
        for exchange in verifier_exchanges:
            inputs = exchange.get("input_messages") if isinstance(exchange.get("input_messages"), list) else []
            user_message = next((str(item.get("content", "")) for item in reversed(inputs) if isinstance(item, Mapping) and item.get("role") == "user"), "")
            verifier_steps.append({"step_id": len(verifier_steps) + 1, "source": "user", "message": user_message})
            verifier_steps.append({
                "step_id": len(verifier_steps) + 1,
                "source": "agent",
                "message": str(exchange.get("output", "")),
                "llm_call_count": 1,
                "extra": {
                    "aether_model_role": "verifier",
                    "role_call_ordinal": exchange.get("role_call_ordinal"),
                    "input_transcript_sha256": exchange.get("input_transcript_sha256", ""),
                    "output_sha256": exchange.get("output_sha256", ""),
                    "provider_call_succeeded": bool(exchange.get("provider_call_succeeded", False)),
                },
            })
        verifier_id = "aether-verifier-" + sha256(session_id.encode("utf-8")).hexdigest()[:16]
        subagents.append({
            "schema_version": ATIF_SCHEMA_VERSION,
            "session_id": session_id,
            "trajectory_id": verifier_id,
            "agent": {"name": "aether-next-verifier", "version": agent_version, **({"model_name": model_name} if model_name else {})},
            "steps": verifier_steps,
            "notes": "Independent Verifier trajectory. This trace is audit evidence and is never injected into Solver private cognition.",
        })
        steps.append({
            "step_id": len(steps) + 1,
            "source": "agent",
            "message": "",
            "llm_call_count": 0,
            "observation": {"results": [{
                "subagent_trajectory_ref": [{"trajectory_id": verifier_id, "session_id": session_id}],
                "extra": {"aether_relation": "independent_verifier_audit_trace"},
            }]},
            "extra": {"aether_export_kind": "verifier_trace_reference"},
        })

    final_metrics = _aggregate_metrics(telemetry)
    final_metrics["total_steps"] = len(steps)
    return {
        "schema_version": ATIF_SCHEMA_VERSION,
        "session_id": session_id,
        "trajectory_id": trajectory_id,
        "agent": {"name": agent_name, "version": agent_version, **({"model_name": model_name} if model_name else {})},
        "steps": steps,
        "final_metrics": final_metrics,
        "notes": "Derived ATIF view. Aether ExecutionLedger receipts remain exact reality authority; large outputs are exported as the exact model-visible projection plus lossless Aether handles/provenance.",
        "extra": {
            "aether_runtime_identity": _json_safe(runtime_identity),
            "aether_receipt_count": len(receipts),
            "aether_model_exchange_count": len(exchanges),
        },
        **({"subagent_trajectories": subagents} if subagents else {}),
    }


def write_atif_trajectory(path: str | Path, trajectory: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_json_safe(dict(trajectory)), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


__all__ = ["ATIF_SCHEMA_VERSION", "build_atif_trajectory", "write_atif_trajectory"]
