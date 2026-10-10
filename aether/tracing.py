"""Opt-in per-step trace capture for Aether-Next kernel runs.

Produces a complete JSON-serializable audit trail: mechanical runtime config,
Solver context/turn/observations per step, and completion-gate decisions.
Activated only when a ``RunTrace`` instance is passed to ``kernel.run()``.
"""
from __future__ import annotations

import dataclasses
import json
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Recursive string truncator
# ---------------------------------------------------------------------------

def _truncate_strings(obj: Any, limit: int) -> Any:
    """Return a deep copy of *obj* with every string leaf truncated to *limit* chars."""
    if isinstance(obj, str):
        if len(obj) <= limit:
            return obj
        return obj[:limit] + f"…[truncated {len(obj) - limit} chars]"
    if isinstance(obj, dict):
        return {k: _truncate_strings(v, limit) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        converted = [_truncate_strings(item, limit) for item in obj]
        return type(obj)(converted) if isinstance(obj, tuple) else converted
    return obj


def _safe_json_len(obj: Any) -> int:
    """Return the JSON-serialized length of *obj*, or 0 on failure."""
    try:
        return len(json.dumps(obj, default=str))
    except (TypeError, ValueError, OverflowError):
        return 0


# ---------------------------------------------------------------------------
# RunTrace — accumulator for a single kernel run
# ---------------------------------------------------------------------------

class RunTrace:
    """Accumulates a full step-by-step trace of a kernel run.

    Does NOT import ``kernel`` — accepts already-built objects to avoid
    circular dependencies.
    """

    def __init__(self) -> None:
        self.runtime_config: dict[str, Any] = {}
        self.prefix_messages: list[dict[str, Any]] = []
        self.steps: list[dict[str, Any]] = []
        self.gate_decisions: list[dict[str, Any]] = []

    # -- runtime snapshot ----------------------------------------------------

    def set_runtime(
        self,
        runtime_ir: Any,
        prefix_messages: list[dict[str, Any]],
    ) -> None:
        """Snapshot the mechanically compiled runtime before the loop starts."""
        self.runtime_config = dataclasses.asdict(runtime_ir)
        self.prefix_messages = _truncate_strings(list(prefix_messages), 4000)

    # -- per-step capture ----------------------------------------------------

    def add_step(
        self,
        step: int,
        context_packet: Mapping[str, Any],
        turn: Any,
        step_receipts: Sequence[Any],
    ) -> None:
        """Record one iteration of the kernel loop."""
        # Context: truncate oversized string leaves if total > 8000 chars.
        ctx: Any = dict(context_packet)
        if _safe_json_len(ctx) > 8000:
            ctx = _truncate_strings(ctx, 2000)

        # Turn: extract structured summary.
        turn_dict = self._extract_turn(turn)

        # Observations: one entry per receipt.
        observations = [self._extract_observation(r) for r in step_receipts]

        self.steps.append({
            "step": step,
            "context_seen": ctx,
            "turn": turn_dict,
            "observations": observations,
        })

    # -- gate decision -------------------------------------------------------

    def add_gate(self, step: int, decision: Any) -> None:
        """Record a completion-gate evaluation."""
        self.gate_decisions.append({
            "step": step,
            "ready": bool(decision.ready),
            "used_check_ids": list(decision.used_check_ids),
            "blockers": [str(b) for b in decision.blockers],
        })

    # -- serialization -------------------------------------------------------

    def to_dict(
        self,
        *,
        task: str = "",
        image: str = "",
        reward: float | None = None,
        status: str = "",
    ) -> dict[str, Any]:
        return {
            "task": task,
            "image": image,
            "reward": reward,
            "status": status,
            "runtime_config": self.runtime_config,
            "prefix_messages": self.prefix_messages,
            "steps": self.steps,
            "gate_decisions": self.gate_decisions,
        }

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _extract_turn(turn: Any) -> dict[str, Any]:
        """Build a concise turn dict from a SolverTurn."""
        actions = []
        for action in getattr(turn, "actions", ()):
            args = dict(getattr(action, "arguments", {}) or {})
            args = _truncate_strings(args, 600)
            actions.append({
                "action_id": getattr(action, "action_id", ""),
                "kind": getattr(action, "kind", ""),
                "capability_id": getattr(action, "capability_id", ""),
                "intent": getattr(action, "intent", ""),
                "expected_observation": getattr(action, "expected_observation", ""),
                "if_fail_next": getattr(action, "if_fail_next", ""),
                "arguments": args,
            })
        return {
            "kind": getattr(turn, "kind", ""),
            "summary": getattr(turn, "summary", ""),
            "requested_check_ids": list(
                getattr(turn, "requested_check_ids", ()),
            ),
            "claimed_artifacts": list(
                getattr(turn, "claimed_artifacts", ()),
            ),
            "actions": actions,
        }

    @staticmethod
    def _extract_observation(receipt: Any) -> dict[str, Any]:
        """Build an observation dict from a Receipt."""
        payload = getattr(receipt, "payload", None) or {}
        stdout_raw = payload.get("stdout", "")
        stderr_raw = payload.get("stderr", "")
        return {
            "receipt_id": getattr(receipt, "receipt_id", ""),
            "kind": getattr(receipt, "kind", ""),
            "success": getattr(receipt, "success", False),
            "failure_class": getattr(receipt, "failure_class", ""),
            "summary": getattr(receipt, "summary", ""),
            "exit_code": payload.get("exit_code"),
            "stdout_tail": str(stdout_raw)[-1200:] if stdout_raw else "",
            "stderr_tail": str(stderr_raw)[-1200:] if stderr_raw else "",
            "path": payload.get("path", ""),
        }
