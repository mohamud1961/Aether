"""The Aether Core agent loop: model turn -> tools -> results, until finish or time.

Everything the model does is recorded in full (reasoning, calls, results,
timings, token usage) to ``core_trace.jsonl``; the request the model sees is a
projection of that history (see ``context``).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Awaitable, Callable

from .context import project, size_chars
from .env import Environment
from .files import Files
from .provider import ChatProvider, ProviderError, parse_arguments
from .review import Transport, review
from .terminal import Terminals

MAX_OUTPUT_TOKENS = 32_768
MAX_REVIEW_HOLDS = 2
REVIEW_MIN_REMAINING_FRACTION = 0.15
REVIEW_MIN_REMAINING_S = 90.0
STOP_MARGIN_S = 15.0

SYSTEM_PROMPT = """You are an expert engineer working autonomously in a Linux container to complete the task \
you are given. No one will answer questions; keep working until the task is done.

Your tools:
- terminal: persistent bash shells. The working directory, environment variables, virtualenvs and running \
programs persist between calls. Open several named terminals to run things in parallel (for example a long \
build in one while you explore in another). For long commands use a short wait_s and check back later. Each \
terminal keeps its full output in a log file; large outputs are shown as head and tail with the log path, so \
grep or tail the log instead of re-running.
- read_file, write_file, edit_file: read with line numbers, create or replace files, and make exact edits.
- finish: end the task.

Working well:
- Look at what exists before changing it, and keep to what the task asks; do not alter or delete unrelated \
files, history or system state.
- Check your work the way the task will be judged: run the real program and confirm the exact output, file \
location, name and format the task requires.
- Every tool result shows the elapsed time and the time limit. Get a complete working result early, then \
improve it.
- Call finish only when every requirement is met and checked, or when no time is left."""

TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "terminal",
        "description": "Send input to a persistent bash terminal and return its new output. mode=command (default) "
                       "runs the input as shell command(s) and waits up to wait_s for them to finish; mode=keys "
                       "sends raw keystrokes to whatever is running (e.g. an interactive program; \\x03 is Ctrl-C) "
                       "and returns once output settles. Empty input just waits for and shows new output.",
        "parameters": {"type": "object", "properties": {
            "input": {"type": "string", "description": "Command(s) or keystrokes. May be empty."},
            "name": {"type": "string", "description": "Terminal name (default 'main'); a new name opens a new terminal."},
            "mode": {"type": "string", "enum": ["command", "keys"]},
            "wait_s": {"type": "number", "description": "Max seconds to wait (default 30, max 900)."},
            "interrupt": {"type": "boolean", "description": "Send Ctrl-C to the running program first."},
        }, "required": ["input"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a text file with line numbers (default 400 lines from start_line).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "start_line": {"type": "integer"}, "num_lines": {"type": "integer"},
        }, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Create or overwrite a file with the given content (parents are created; permissions kept).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"},
        }, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "edit_file",
        "description": "Replace an exact, unique occurrence of old_str with new_str in a file "
                       "(or every occurrence with replace_all=true).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"},
            "replace_all": {"type": "boolean"},
        }, "required": ["path", "old_str", "new_str"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "End the task. Use when every requirement is met and checked, or no time is left.",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string", "description": "One or two sentences on the final state."},
        }, "required": ["summary"]}}},
]


@dataclass
class RunResult:
    status: str  # finished | timeout | provider_error | no_tool_loop
    steps: int = 0
    usage: dict[str, int] = field(default_factory=lambda: {"input": 0, "cached": 0, "output": 0, "reasoning": 0})
    calls: int = 0
    failed_attempts: int = 0
    request_chars: list[int] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


class Trace:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._t0 = time.monotonic()

    def __call__(self, event: str, **data: Any) -> None:
        row = {"t": round(time.monotonic() - self._t0, 3), "event": event, **data}
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _action_view(name: str, args: dict[str, Any], result: str) -> str:
    if name == "terminal":
        head = f"[terminal {args.get('name') or 'main'}] $ {str(args.get('input', ''))[:400]}"
    elif name == "write_file":
        head = f"[write_file] {args.get('path')} ({len(str(args.get('content', '')))} chars)"
    elif name == "edit_file":
        head = f"[edit_file] {args.get('path')}"
    else:
        head = f"[{name}] {json.dumps(args)[:300]}"
    return f"{head}\n-> {result}"


async def run_agent(*, env: Environment, task: str, workdir: str, provider: ChatProvider, timeout_s: float,
                    trace: Trace, review_transport: Transport | None = None,
                    review_call: Callable[..., Awaitable[Any]] | None = None) -> RunResult:
    started = time.monotonic()
    deadline = started + timeout_s - STOP_MARGIN_S
    remaining = lambda: deadline - time.monotonic()  # noqa: E731
    terminals, files = Terminals(env, workdir, remaining), Files(env, workdir)
    clock = lambda: f"[t={time.monotonic() - started:.0f}s of {timeout_s:.0f}s]"  # noqa: E731
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{task}\n\n(Working directory: {workdir}. Time limit: {timeout_s:.0f}s.)"},
    ]
    result, actions, tight, idle_turns = RunResult("timeout"), [], False, 0
    trace("start", workdir=workdir, timeout_s=timeout_s, model=provider.model, params=provider.params,
          review=bool(review_transport))
    while remaining() > 0:
        request = project(messages, tight=tight)
        result.request_chars.append(size_chars(request))
        try:
            turn = await provider.complete(request, TOOLS, max_tokens=MAX_OUTPUT_TOKENS, remaining_s=remaining)
        except ProviderError as exc:
            if exc.context_overflow and not tight:
                tight = True
                trace("context_overflow", chars=result.request_chars[-1])
                continue
            result.status, result.error = "provider_error", str(exc)
            break
        result.calls += 1
        for key, value in turn.usage.items():
            result.usage[key] = result.usage.get(key, 0) + value
        trace("model", latency_s=round(turn.latency_s, 3), attempts=turn.attempts, usage=turn.usage,
              request_chars=result.request_chars[-1], finish_reason=turn.finish_reason,
              reasoning=turn.reasoning, content=turn.content, tool_calls=turn.tool_calls)
        messages.append(turn.assistant_message())
        if not turn.tool_calls:
            idle_turns += 1
            if idle_turns >= 3:
                result.status = "no_tool_loop"
                break
            messages.append({"role": "user", "content": "Continue by using a tool, or call finish if done. " + clock()})
            continue
        idle_turns = 0
        finished = False
        for call in turn.tool_calls:
            name = call["function"]["name"]
            t0 = time.monotonic()
            args: dict[str, Any] = {}
            try:
                args = parse_arguments(call["function"]["arguments"])
                if name == "finish":
                    out, finished = await _finish(args, result, env=env, task=task, workdir=workdir,
                                                  actions=actions, files=files, remaining=remaining,
                                                  timeout_s=timeout_s, transport=review_transport,
                                                  call=review_call, trace=trace)
                elif name == "terminal":
                    out = await terminals.use(name=str(args.get("name") or "main"), input=str(args.get("input", "")),
                                              mode=str(args.get("mode") or "command"),
                                              wait_s=float(args.get("wait_s") or 30),
                                              interrupt=bool(args.get("interrupt")))
                elif name == "read_file":
                    out = await files.read(args["path"], int(args.get("start_line") or 1),
                                           int(args.get("num_lines") or 400))
                elif name == "write_file":
                    out = await files.write(args["path"], str(args["content"]))
                elif name == "edit_file":
                    out = await files.edit(args["path"], str(args["old_str"]), str(args["new_str"]),
                                           bool(args.get("replace_all")))
                else:
                    out = f"error: unknown tool {name!r}"
            except Exception as exc:  # tool errors are the model's to handle; reported verbatim
                out = f"error: {type(exc).__name__}: {str(exc)[:1000]}"
            result.steps += 1
            text = f"{out}\n{clock()}"
            trace("tool", name=name, args=args, result=out, duration_s=round(time.monotonic() - t0, 3))
            if name != "finish":
                actions.append(_action_view(name, args, out))
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": text})
            if finished:
                break
        if finished:
            result.status = "finished"
            break
    result.failed_attempts = provider.failed_attempts
    trace("end", status=result.status, error=result.error, steps=result.steps, usage=result.usage,
          elapsed_s=round(time.monotonic() - started, 1))
    return result


async def _finish(args, result: RunResult, *, env, task, workdir, actions, files: Files, remaining, timeout_s,
                  transport, call, trace) -> tuple[str, bool]:
    holds = sum(1 for r in result.reviews if r["status"] == "hold")
    enough_time = remaining() > max(REVIEW_MIN_REMAINING_S, REVIEW_MIN_REMAINING_FRACTION * timeout_s)
    if transport is None or call is None or holds >= MAX_REVIEW_HOLDS or not enough_time:
        reason = ("review_off" if transport is None else "hold_limit" if holds >= MAX_REVIEW_HOLDS
                  else "low_time")
        trace("finish", summary=args.get("summary", ""), review="skipped", reason=reason)
        return "finished", True
    t0 = time.monotonic()
    verdict = await review(transport, env, task=task, workdir=workdir, actions=actions,
                           written=list(files.written), call=call)
    row = {"status": verdict.status, "mode": verdict.mode, "confidence": verdict.confidence,
           "unmet": verdict.unmet, "reason": verdict.reason, "request_bytes": verdict.request_bytes,
           "latency_s": round(time.monotonic() - t0, 2)}
    result.reviews.append(row)
    trace("review", summary=args.get("summary", ""), answers=verdict.answers, **row)
    if verdict.status == "hold":
        return verdict.feedback(), False
    return "finished", True


def default_review_call(transport: Transport, request: dict) -> Awaitable[Any]:
    return asyncio.to_thread(transport, request)
