"""Trace-aware execution wrapper for bounded failure-learning pressure.

Interface: ExecutionBlock.run_loop(model, tools, context, max_steps) -> result
"""

from __future__ import annotations

from typing import Any

from runner.packet04_route_manifest import baseline_execution_run_loop


def run_loop(
    model: Any,
    tools: dict[str, Any],
    context: dict[str, Any],
    max_steps: int,
    tool_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the baseline loop while marking trace-learning state explicitly."""
    enriched = dict(context)
    history = list(enriched.get("history", []))
    history.append(
        {
            "role": "system",
            "content": (
                "Before repeating a failed action, state the failure source and "
                "choose the next smallest evidence-producing action."
            ),
        }
    )
    enriched["history"] = history
    result = baseline_execution_run_loop(
        model=model,
        tools=tools,
        context=enriched,
        max_steps=max_steps,
        tool_definitions=tool_definitions,
    )
    result["trace_learning_state"] = {
        "failure_source_prompted": True,
        "bounded_action_granularity_prompted": True,
    }
    return result
