"""Oracle agent: applies the task's reference solution.

It measures the grader, not a model. A passing reference run is the first half of grader validity.
"""

from __future__ import annotations

from harness_evals.agents.base import AgentResult
from harness_evals.sandbox import Sandbox
from harness_evals.task import Task

REFERENCE_CLAIM = "reference solution applied"
REFERENCE_COMMAND = 'bash "$TASK_ROOT/reference/solve.sh"'


class ReferenceAgent:
    name = "reference"

    def run(self, task: Task, sandbox: Sandbox, budget_s: float) -> AgentResult:
        result = sandbox.exec(REFERENCE_COMMAND, timeout_s=budget_s)
        if result.timed_out:
            error: str | None = f"reference script timed out after {budget_s} s"
        elif result.code != 0:
            error = f"reference script exited with code {result.code}"
        else:
            error = None
        return AgentResult(
            finished=error is None,
            claim=REFERENCE_CLAIM if error is None else "",
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            tool_calls=1,
            actions=[REFERENCE_COMMAND],
            error=error,
            trace=[
                {
                    "command": REFERENCE_COMMAND,
                    "exit_code": result.code,
                    "timed_out": result.timed_out,
                    "wall_s": result.wall_s,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            ],
        )


def make(**opts: object) -> ReferenceAgent:
    if opts:
        raise TypeError(f"reference agent takes no options, got {sorted(opts)}")
    return ReferenceAgent()
