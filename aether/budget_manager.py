from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .event_log import EventLog
from .policy_config import PolicyConfig


@dataclass
class BudgetState:
    model_calls_used: int = 0
    tool_calls_used: int = 0
    wall_clock_seconds: float = 0.0
    input_tokens_total: int = 0
    output_tokens_total: int = 0
    cost_units: float = 0.0


@dataclass(frozen=True)
class BudgetCheckResult:
    ok: bool
    exceeded_field: Optional[str] = None


class BudgetManager:
    def __init__(self, policy: PolicyConfig, event_log: EventLog) -> None:
        self.policy = policy
        self.event_log = event_log
        self.state = BudgetState()

    def record_model_call(self, *, input_tokens: int, output_tokens: int, cost_units: float = 0.0) -> None:
        self.state.model_calls_used += 1
        self.state.input_tokens_total += max(0, int(input_tokens))
        self.state.output_tokens_total += max(0, int(output_tokens))
        self.state.cost_units += max(0.0, float(cost_units))

    def record_tool_call(self) -> None:
        self.state.tool_calls_used += 1

    def update_wall_clock(self, seconds: float) -> None:
        self.state.wall_clock_seconds = max(self.state.wall_clock_seconds, float(seconds))

    def check_and_emit(self, *, timestamp: str, cwd: str) -> BudgetCheckResult:
        limits = {
            "model_calls_used": self.policy.max_model_calls,
            "tool_calls_used": self.policy.max_tool_calls,
            "wall_clock_seconds": float(self.policy.max_wall_clock_seconds),
            "input_tokens_total": self.policy.max_input_tokens_total,
            "output_tokens_total": self.policy.max_output_tokens_total,
            "cost_units": float(self.policy.max_cost_units),
        }
        current = {
            "model_calls_used": self.state.model_calls_used,
            "tool_calls_used": self.state.tool_calls_used,
            "wall_clock_seconds": self.state.wall_clock_seconds,
            "input_tokens_total": self.state.input_tokens_total,
            "output_tokens_total": self.state.output_tokens_total,
            "cost_units": self.state.cost_units,
        }

        exceeded_field: Optional[str] = None
        for field_name in (
            "model_calls_used",
            "tool_calls_used",
            "wall_clock_seconds",
            "input_tokens_total",
            "output_tokens_total",
            "cost_units",
        ):
            if current[field_name] > limits[field_name]:
                exceeded_field = field_name
                break

        self.event_log.append_event(
            {
                "event_type": "BUDGET_CHECK",
                "timestamp": timestamp,
                "cwd": cwd,
                "model_calls_used": current["model_calls_used"],
                "model_calls_max": limits["model_calls_used"],
                "tool_calls_used": current["tool_calls_used"],
                "tool_calls_max": limits["tool_calls_used"],
                "exceeded": exceeded_field is not None,
                "budget_current": current,
                "budget_max": limits,
                "pass": exceeded_field is None,
                "exceeded_field": exceeded_field,
            }
        )

        return BudgetCheckResult(ok=exceeded_field is None, exceeded_field=exceeded_field)

    def apply_extension(
        self,
        *,
        approval_granted: bool,
        extension: Dict[str, Any],
    ) -> bool:
        if not approval_granted:
            return False

        updates = {
            "max_model_calls": int,
            "max_tool_calls": int,
            "max_wall_clock_seconds": int,
            "max_input_tokens_total": int,
            "max_output_tokens_total": int,
            "max_cost_units": int,
        }
        payload: Dict[str, Any] = {
            "feature_flags": self.policy.feature_flags,
            "loop_breaker": self.policy.loop_breaker,
            "policy_profile": self.policy.policy_profile,
            "model_profile_id": self.policy.model_profile_id,
            "network_enabled": self.policy.network_enabled,
            "enforce_script_allowlist": self.policy.enforce_script_allowlist,
            "script_allowlist_hashes": self.policy.script_allowlist_hashes,
        }
        for key, value in updates.items():
            current = getattr(self.policy, key)
            requested = extension.get(key, current)
            payload[key] = value(requested)

        self.policy = PolicyConfig(**payload)
        return True
