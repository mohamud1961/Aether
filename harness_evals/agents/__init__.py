"""Agents: anything that works on a task inside a sandbox.

An agent module exposes make(**opts) returning an object with `name` and run(task, sandbox,
budget_s). Agents are looked up by module name through base.get_agent.
"""
