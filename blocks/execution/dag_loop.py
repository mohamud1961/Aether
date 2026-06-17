"""DAG-based execution — model generates a DAG of subtasks, executes nodes in order.

Interface: ExecutionBlock.run_loop(model, tools, context, max_steps) -> result
"""
