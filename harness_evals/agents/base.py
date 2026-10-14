"""Agent protocol, result type and registry.

An agent receives a task and a sandbox whose root holds a fresh copy of the task workspace. It
returns an AgentResult. Grading is never the agent's job: the caller grades the sandbox root
after the agent returns.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from typing import Any, Protocol

from harness_evals.sandbox import Sandbox
from harness_evals.task import Task

_AGENT_NAME = re.compile(r"[a-z][a-z0-9_]*")


class UnknownAgent(ValueError):
    """No agent module matches the requested name."""


@dataclass
class AgentResult:
    finished: bool
    claim: str
    tokens_in: int
    tokens_out: int
    cost: float
    tool_calls: int
    actions: list[str]
    error: str | None
    trace: list[dict[str, Any]]


class Agent(Protocol):
    name: str

    def run(self, task: Task, sandbox: Sandbox, budget_s: float) -> AgentResult: ...


def get_agent(name: str, **opts: Any) -> Agent:
    if not _AGENT_NAME.fullmatch(name):
        raise UnknownAgent(f"invalid agent name {name!r}")
    module_name = f"harness_evals.agents.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise UnknownAgent(f"no agent named {name!r}") from exc
        raise
    make = getattr(module, "make", None)
    if not callable(make):
        raise UnknownAgent(f"agent module {module_name} does not define make()")
    agent: Agent = make(**opts)
    return agent
