"""Run a CLI agent command in the sandbox, without giving it hidden task paths.

The prompt is a quoted environment value. CLI usage/cost cannot be inferred from
stdout; traces explicitly mark these unavailable. A process exit isn't task success.
"""

import os

from .base import AgentResult


class CommandAgent:
    name = "command"

    def __init__(self, command=None):
        self.command = command or os.environ.get("HARNESS_EVALS_COMMAND")
        if not self.command:
            raise ValueError("set HARNESS_EVALS_COMMAND to the CLI agent command")

    def run(self, task, sandbox, budget_s):
        result = sandbox.exec(self.command, budget_s, env={"TASK_PROMPT": task.prompt})
        error = (
            "CLI agent timed out"
            if result.timed_out
            else (f"CLI agent exited {result.code}" if result.code else None)
        )
        return AgentResult(
            error is None,
            result.stdout,
            0,
            0,
            0.0,
            1,
            [self.command],
            error,
            [
                {
                    "command": self.command,
                    "exit_code": result.code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "wall_s": result.wall_s,
                    "usage_known": False,
                    "cost_known": False,
                }
            ],
        )


def make(**opts):
    return CommandAgent(**opts)
