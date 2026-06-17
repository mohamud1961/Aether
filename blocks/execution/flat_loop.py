"""Simple while-not-done loop — basic agent loop with no phases or gates.

Interface: ExecutionBlock.run_loop(model, tools, context, max_steps) -> result
"""

from __future__ import annotations

from typing import Any, Callable

def run_loop(
    model: Any,
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    context: dict[str, Any],
    max_steps: int,
    tool_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run a bounded baseline loop with optional tool execution."""
    if max_steps <= 0:
        raise ValueError("max_steps must be >= 1")
    history = list(context.get("history", []))
    manage_history = context["manage_history"]
    steps: list[dict[str, Any]] = []
    status = "max_steps_exhausted"
    last_completion: dict[str, Any] = {}
    terminal_reason = "step_budget_exhausted"
    terminal_step = max_steps - 1
    lifecycle = _init_lifecycle_state()
    error_raised: Exception | None = None
    failure_tracker: dict[str, Any] = {"last_failure_signature": None, "streak": 0}
    autopsy_events: list[dict[str, Any]] = []

    _record_lifecycle_event(lifecycle, "loop_entered")

    try:
        for step in range(max_steps):
            terminal_step = step
            complete_kwargs: dict[str, Any] = {}
            if tool_definitions:
                complete_kwargs["tools"] = tool_definitions
            completion = model.complete(history, **complete_kwargs)
            last_completion = completion
            assistant_text = completion.get("text")
            if isinstance(assistant_text, str) and assistant_text:
                history = manage_history(history, {"role": "assistant", "content": assistant_text})

            tool_calls = completion.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                status = "completed"
                terminal_reason = "no_tool_calls"
                steps.append(
                    {
                        "step": step,
                        "tool_calls": 0,
                        "status": "no_tool_calls",
                        "completion": completion,
                    }
                )
                break

            step_result: dict[str, Any] = {
                "step": step,
                "tool_calls": len(tool_calls),
                "results": [],
                "completion": completion,
            }
            history = manage_history(
                history,
                {
                    "role": "assistant",
                    "content": assistant_text if isinstance(assistant_text, str) and assistant_text else None,
                    "tool_calls": tool_calls,
                },
            )
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    result = {"error": "malformed_tool_call"}
                    history = manage_history(
                        history,
                        {
                            "role": "tool",
                            "name": "unknown",
                            "tool_call_id": None,
                            "content": _tool_observation({"name": "unknown"}, result),
                        },
                    )
                    step_result["results"].append(result)
                    continue
                tool_name = tool_call.get("name")
                if not isinstance(tool_name, str) or tool_name not in tools:
                    result = {"error": f"unsupported_tool:{tool_name}"}
                else:
                    blocked = _build_blind_retry_blocked_result(tool_call, failure_tracker)
                    result = blocked if blocked is not None else tools[tool_name](tool_call)
                history = manage_history(
                    history,
                    {
                        "role": "tool",
                        "name": tool_name or "unknown",
                        "tool_call_id": tool_call.get("id") if isinstance(tool_call, dict) else None,
                        "content": _tool_observation(tool_call, result),
                    },
                )
                step_result["results"].append(result)
                failure_tracker = _update_failure_tracker(
                    tracker=failure_tracker,
                    tool_call=tool_call,
                    result=result,
                )
                if int(failure_tracker.get("streak", 0) or 0) >= 2:
                    autopsy_event = {
                        "step": step,
                        "failure_signature": failure_tracker.get("last_failure_signature"),
                        "reason_code": "bounded_autopsy_replan_required_after_repeated_failure",
                    }
                    autopsy_events.append(autopsy_event)
                    history = manage_history(
                        history,
                        {
                            "role": "system",
                            "content": (
                                "Harness autopsy: repeated failure signature detected. "
                                "Replan now and do not repeat the same failing command."
                            ),
                        },
                    )
                    step_result["status"] = "autopsy_replan_required"
            steps.append(step_result)
    except Exception as err:
        error_raised = err
        status = "error"
        terminal_reason = "loop_exception"
        _record_lifecycle_event(lifecycle, "execution_error")
        _write_terminal_outcome(
            lifecycle,
            terminal_status=status,
            reason_code=terminal_reason,
            step=terminal_step,
        )
        raise
    finally:
        if lifecycle["terminal_write_count"] == 0:
            _write_terminal_outcome(
                lifecycle,
                terminal_status=status,
                reason_code=terminal_reason,
                step=terminal_step,
            )
        _record_lifecycle_event(lifecycle, "cleanup_started")
        cleanup_reason_codes = ["loop_cleanup_completed"]
        if error_raised is not None:
            cleanup_reason_codes.append("loop_cleanup_after_error")
        _finalize_cleanup_state(lifecycle, reason_codes=cleanup_reason_codes)
        _record_lifecycle_event(lifecycle, "cleanup_completed")
        if error_raised is not None:
            _attach_lifecycle_to_error(error_raised, _export_lifecycle_summary(lifecycle))
    _record_lifecycle_event(lifecycle, "loop_exited")

    result = {
        "status": status,
        "history": history,
        "steps": steps,
        "step_count": len(steps),
        "last_completion": last_completion,
    }
    if autopsy_events:
        result["autopsy"] = {
            "triggered": True,
            "replan_required": True,
            "reason_codes": ["bounded_autopsy_replan_required_after_repeated_failure"],
            "events": autopsy_events,
        }
    result.update(_export_lifecycle_summary(lifecycle))
    return result


def _build_blind_retry_blocked_result(
    tool_call: dict[str, Any],
    failure_tracker: dict[str, Any],
) -> dict[str, Any] | None:
    command = _tool_call_command(tool_call)
    if not command:
        return None
    last_signature = failure_tracker.get("last_failure_signature")
    if not isinstance(last_signature, str) or not last_signature:
        return None
    if last_signature != command:
        return None
    return {
        "tool_name": tool_call.get("name") if isinstance(tool_call.get("name"), str) else "unknown",
        "command": command,
        "exit_code": 1,
        "stdout": "",
        "stderr": "blind_retry_blocked_same_failed_command",
        "timed_out": False,
        "result_class": "runtime_error",
        "reason_code": "blind_retry_blocked_same_failed_command",
    }


def _update_failure_tracker(
    *,
    tracker: dict[str, Any],
    tool_call: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    command = _tool_call_command(tool_call)
    if not command:
        return {"last_failure_signature": None, "streak": 0}
    failed = _result_failed(result)
    if not failed:
        return {"last_failure_signature": None, "streak": 0}
    signature = command
    prior_signature = tracker.get("last_failure_signature")
    if signature == prior_signature:
        streak = int(tracker.get("streak", 0) or 0) + 1
    else:
        streak = 1
    return {"last_failure_signature": signature, "streak": streak}


def _result_failed(result: dict[str, Any]) -> bool:
    if "error" in result:
        return True
    exit_code = result.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    if bool(result.get("timed_out", False)):
        return True
    return False


def _tool_call_command(tool_call: dict[str, Any]) -> str:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        if isinstance(command, str):
            return command.strip()
    if isinstance(arguments, str):
        return arguments.strip()
    return ""


def _tool_observation(tool_call: dict[str, Any], result: dict[str, Any]) -> str:
    name = tool_call.get("name") if isinstance(tool_call.get("name"), str) else "unknown"
    if "error" in result:
        return f"{name} error: {result['error']}"
    exit_code = result.get("exit_code")
    stdout = result.get("stdout") or ""
    stderr = result.get("stderr") or ""
    return f"{name} exit={exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}".strip()


def _init_lifecycle_state() -> dict[str, Any]:
    return {
        "events": [],
        "terminal_outcome": {},
        "terminal_write_count": 0,
        "terminal_write_attempt_count": 0,
        "cleanup_state": {"status": "pending", "reason_codes": [], "after_terminal": False},
    }


def _record_lifecycle_event(lifecycle: dict[str, Any], event: str) -> None:
    lifecycle["events"].append(event)


def _write_terminal_outcome(
    lifecycle: dict[str, Any],
    *,
    terminal_status: str,
    reason_code: str,
    step: int,
) -> None:
    lifecycle["terminal_write_attempt_count"] += 1
    if lifecycle["terminal_write_count"] >= 1:
        _record_lifecycle_event(lifecycle, "terminal_outcome_duplicate_blocked")
        return
    lifecycle["terminal_write_count"] = 1
    lifecycle["terminal_outcome"] = {
        "status": terminal_status,
        "reason_code": reason_code,
        "step": step,
    }
    _record_lifecycle_event(lifecycle, "terminal_outcome_written")


def _finalize_cleanup_state(lifecycle: dict[str, Any], *, reason_codes: list[str]) -> None:
    cleanup_state = lifecycle["cleanup_state"]
    cleanup_state["status"] = "completed"
    cleanup_state["reason_codes"] = list(reason_codes)
    cleanup_state["after_terminal"] = lifecycle["terminal_write_count"] == 1


def _export_lifecycle_summary(lifecycle: dict[str, Any]) -> dict[str, Any]:
    cleanup_state = lifecycle["cleanup_state"]
    unresolved_state_exit_count = 0
    if lifecycle["terminal_write_attempt_count"] != 1:
        unresolved_state_exit_count += 1
    if cleanup_state.get("status") != "completed":
        unresolved_state_exit_count += 1
    if not cleanup_state.get("after_terminal"):
        unresolved_state_exit_count += 1
    return {
        "terminal_outcome": dict(lifecycle["terminal_outcome"]),
        "terminal_write_count": lifecycle["terminal_write_count"],
        "cleanup_completion_reason_codes": list(cleanup_state.get("reason_codes", [])),
        "lifecycle_sequence_fingerprint": ">".join(lifecycle["events"]),
        "unresolved_state_exit_count": unresolved_state_exit_count,
    }


def _attach_lifecycle_to_error(error: Exception, lifecycle_summary: dict[str, Any]) -> None:
    details = getattr(error, "details", None)
    payload = {"execution_lifecycle": lifecycle_summary}
    if isinstance(details, dict):
        payload = dict(details)
        payload["execution_lifecycle"] = lifecycle_summary
    try:
        setattr(error, "details", payload)
    except Exception:
        return
