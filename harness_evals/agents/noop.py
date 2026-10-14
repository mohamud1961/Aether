"""Floor agent: changes nothing and makes no claim. Its grade is the baseline for any task."""

from __future__ import annotations

from harness_evals.agents.base import AgentResult
from harness_evals.sandbox import Sandbox
from harness_evals.task import Task


class NoopAgent:
    name = "noop"

    def run(self, task: Task, sandbox: Sandbox, budget_s: float) -> AgentResult:
        return AgentResult(
            finished=False,
            claim="",
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            tool_calls=0,
            actions=[],
            error=None,
            trace=[],
        )


def make(**opts: object) -> NoopAgent:
    if opts:
        raise TypeError(f"noop agent takes no options, got {sorted(opts)}")
    return NoopAgent()
