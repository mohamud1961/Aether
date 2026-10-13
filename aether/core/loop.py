"""The Aether Core agent loop: model turn -> tools -> results, until finish or time.

Everything the model does is recorded in full (reasoning, calls, results,
timings, token usage, every failed provider attempt) to ``core_trace.jsonl``.
What the model sees is either the ``project`` view of that history (C1) or a
context the model manages itself under a token budget (``clm``; see ``clm``).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Awaitable, Callable

from . import compaction, images
from .clm import ClmContext, ClmSettings
from .context import SAVE_OVER, SAVED_NOTE, project, saved_path, size_chars
from .env import CONTROL_DIR, Environment, get_bytes, put_bytes
from .files import Files
from .oversight import Oversight, ReviewPlan, final_feedback, progress_feedback
from .provider import ChatProvider, ProviderError, parse_arguments
from .repl import Repl, sub_llm
from .review import Transport
from .terminal import Terminals
from .tools import system_prompt, tools
from . import contract as acceptance, contract_loop
from .clone import Clone

MAX_OUTPUT_TOKENS = 32_768
# A turn the output limit cuts off before any tool call is almost never followed by action at the same effort:
# in the archived rows 30 of 32 such turns produced nothing, and V2 seq-assembly lost 550-900 s of each row to
# two or three in a row. The next turn runs at low effort, to act on the reasoning it already has.
AFTER_CUT = {"reasoning_effort": "low"}
# V3: 3 of 4 low-effort turns acted within 25 s (under 2k output tokens); one still reasoned to 32k (265 s).
# Its output cap bounds that case to a quarter of the time.
AFTER_CUT_MAX_TOKENS = 8_192
STOP_MARGIN_S = 15.0
CONTEXT_MODES = ("project", "clm")


@dataclass(frozen=True)
class CoreConfig:
    context: str = "project"
    repl: bool = False
    images: bool = False
    reviews: ReviewPlan = ReviewPlan()
    clm: ClmSettings = field(default_factory=ClmSettings)
    control_dir: str = CONTROL_DIR  # where terminals and the REPL keep their files in the sandbox
    make_clone: Callable[[Environment], Awaitable[Any]] | None = None  # tests inject a clone; default docker
    contract: bool = False  # acceptance checks written before the work, offered as information (see contract)

    def __post_init__(self) -> None:
        if self.context not in CONTEXT_MODES:
            raise ValueError(f"context must be one of {CONTEXT_MODES}")


@dataclass
class RunResult:
    status: str  # finished | timeout | provider_error | context_error | no_tool_loop
    steps: int = 0
    usage: dict[str, int] = field(default_factory=lambda: {"input": 0, "cached": 0, "output": 0, "reasoning": 0})
    sub_usage: dict[str, int] = field(default_factory=dict)  # llm() and checkpoint calls
    calls: int = 0
    failed_attempts: int = 0
    request_chars: list[int] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
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
    elif name == "python":
        head = f"[python] {str(args.get('code', ''))[:400]}"
    elif name == "write_file":
        head = f"[write_file] {args.get('path')} ({len(str(args.get('content', '')))} chars)"
    elif name == "edit_file":
        head = f"[edit_file] {args.get('path')}"
    else:
        head = f"[{name}] {json.dumps(args)[:300]}"
    return f"{head}\n-> {result}"


def _touches_mirror(calls: list[dict[str, Any]]) -> bool:
    return any("LIVE_CTX" in str((c.get("function") or {}).get("arguments", "")) for c in calls)


def _attach(messages: list[dict[str, Any]], note: str) -> None:
    """Add a harness note to the newest tool result (or as a user message when there is none)."""
    if messages and messages[-1].get("role") == "tool":
        messages[-1]["content"] = f"{messages[-1]['content']}\n\n{note}"
    else:
        messages.append({"role": "user", "content": note})


class _Session:
    """Per-run state shared by the loop's helpers."""

    def __init__(self, env, task, workdir, provider, timeout_s, trace, config, transport, call):
        self.env, self.task, self.workdir, self.provider = env, task, workdir, provider
        self.timeout_s, self.trace, self.config = timeout_s, trace, config
        self.started = time.monotonic()
        self.deadline = self.started + timeout_s - STOP_MARGIN_S
        self.result = RunResult("timeout")
        self.terminals = Terminals(env, workdir, self.remaining, control_dir=config.control_dir)
        self.files = Files(env, workdir)
        self.repl = Repl(env, workdir, self.remaining, sub_llm(provider, self.remaining, self.result.sub_usage),
                         base=f"{config.control_dir}/repl")
        self.oversight = Oversight(config.reviews, transport, call, timeout_s, control_dir=config.control_dir)
        self.actions: list[str] = []
        self.clm: ClmContext | None = None
        self.messages: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self.pending_images: list[dict[str, Any]] = []  # shown after the current turn's tool results
        self.images_viewed = 0
        self.contract: acceptance.Contract | None = None
        self.contract_task: asyncio.Task | None = None
        self.contract_shown = False

    def clone(self, env: Environment) -> Awaitable[Any]:
        return (self.config.make_clone or Clone.create)(env)

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def clock(self) -> str:
        return f"[t={self.elapsed():.0f}s of {self.timeout_s:.0f}s]"

    @property
    def history(self) -> list[dict[str, Any]]:
        return self.clm.editable if self.clm else self.messages


async def run_agent(*, env: Environment, task: str, workdir: str, provider: ChatProvider, timeout_s: float,
                    trace: Trace, review_transport: Transport | None = None,
                    review_call: Callable[..., Awaitable[Any]] | None = None,
                    config: CoreConfig | None = None) -> RunResult:
    config = config or CoreConfig(reviews=ReviewPlan(finish=review_transport is not None))
    s = _Session(env, task, workdir, provider, timeout_s, trace, config, review_transport, review_call)
    await env.exec(command=f"mkdir -p {config.control_dir}",
                   cwd=None, env=None, timeout_sec=30)
    python = await s.repl.start() if config.repl else ""
    see = config.images and images.available()
    s.tools = tools(python=bool(python), images=see, contract=config.contract)
    pinned = [{"role": "system", "content": system_prompt(python_version=python, clm=config.context == "clm",
                                                          images=see)},
              {"role": "user", "content": f"{task}\n\n(Working directory: {workdir}. Time limit: {timeout_s:.0f}s.)"}]
    if config.context == "clm":
        s.clm = ClmContext(pinned=pinned, settings=config.clm)
    else:
        s.messages = list(pinned)
    trace("start", workdir=workdir, timeout_s=timeout_s, model=provider.model, params=provider.params,
          review=bool(review_transport), context=config.context, repl=config.repl, python=python,
          images=see,
          reviews=config.reviews.__dict__, clm=config.clm.__dict__ if s.clm else None)
    if config.contract:
        await contract_loop.start(s)
    try:
        await _loop(s)
    finally:
        if s.contract_task and not s.contract_task.done():
            s.contract_task.cancel()
            await asyncio.gather(s.contract_task, return_exceptions=True)
        _close(s)
        try:  # terminals die with the container anyway; outside one (tests, clones) they would linger
            await s.terminals.close()
            await s.repl.close()
        except Exception as exc:
            s.trace("terminals_close_error", error=f"{type(exc).__name__}: {exc}")
    return s.result


async def _loop(s: _Session) -> None:
    result, idle_turns, tight, cut = s.result, 0, False, False
    while s.remaining() > 0:
        contract_loop.show(s, _attach)
        due = s.oversight.due(s.elapsed(), s.remaining())
        if due:
            await _scheduled_review(s, due)
        if s.clm and not await _fit_context(s):
            return
        request = s.clm.request() if s.clm else project(s.messages, tight=tight)
        result.request_chars.append(size_chars(request))
        try:
            turn = await s.provider.complete(request, s.tools,
                                             max_tokens=AFTER_CUT_MAX_TOKENS if cut else MAX_OUTPUT_TOKENS,
                                             remaining_s=s.remaining, overrides=AFTER_CUT if cut else None)
        except ProviderError as exc:
            s.trace("provider_error", status=exc.status, error=str(exc), deadline=exc.deadline,
                    overflow=exc.context_overflow)
            if exc.context_overflow and not tight and not s.clm:
                tight = True
                continue
            if exc.deadline:
                result.status = "timeout"
            else:
                result.status, result.error = "provider_error", str(exc)
            return
        result.calls += 1
        for key, value in turn.usage.items():
            result.usage[key] = result.usage.get(key, 0) + value
        if s.clm:
            s.clm.calibrate(result.request_chars[-1], turn.usage.get("input", 0))
        s.trace("model", latency_s=round(turn.latency_s, 3), attempts=turn.attempts, failures=turn.failures,
                usage=turn.usage, request_chars=result.request_chars[-1], finish_reason=turn.finish_reason,
                reasoning=turn.reasoning, content=turn.content, tool_calls=turn.tool_calls,
                effort=AFTER_CUT["reasoning_effort"] if cut else None)
        cut = turn.finish_reason == "length" and not turn.tool_calls
        assistant = turn.assistant_message()
        _append(s, assistant)
        if s.clm:
            s.clm.note_reasoning(assistant, turn.usage.get("reasoning", 0))
        if not turn.tool_calls:
            # A turn the output limit cut off is work in progress, not idleness; the time limit bounds it (D1
            # regex-game: three 32k-token thoughts in a row ended the run with 30 minutes left).
            idle_turns += turn.finish_reason != "length"
            if idle_turns >= 3:
                result.status = "no_tool_loop"
                return
            if turn.finish_reason == "length":  # say what happened: the output limit cut the turn off
                note = ("Your last turn reached the output limit before any tool call; "
                        "its reasoning is above. Act on it now with a tool call (for example write down or test "
                        "your partial result) instead of reasoning further in one turn; your next turn runs at "
                        "low reasoning effort. ")
            else:
                note = "Continue by using a tool, or call finish if done. "
            _append(s, {"role": "user", "content": note + s.clock()})
            continue
        idle_turns = 0
        if await _run_calls(s, turn.tool_calls):
            result.status = "finished"
            return


def _append(s: _Session, *messages: dict[str, Any]) -> None:
    if s.clm:
        s.clm.append(*messages)
    else:
        s.messages.extend(messages)


async def _run_calls(s: _Session, calls: list[dict[str, Any]]) -> bool:
    """Execute one turn's tool calls. Returns True when the run finished."""
    mirror = None
    if s.clm and _touches_mirror(calls):
        upto = len(s.clm.editable) - 1  # the mirror holds history before this turn's assistant message
        text = s.clm.render(upto)
        await put_bytes(s.env, text.encode(), s.clm.settings.mirror_path)
        mirror = (upto, hashlib.sha256(text.encode()).hexdigest())
    finished = False
    for call in calls:
        name = call["function"]["name"]
        t0 = time.monotonic()
        args: dict[str, Any] = {}
        try:
            args = parse_arguments(call["function"]["arguments"])
            out, finished = await _dispatch(s, name, args)
        except Exception as exc:  # tool errors are the model's to handle; reported verbatim
            out = f"error: {type(exc).__name__}: {str(exc)[:1000]}"
            if isinstance(exc, json.JSONDecodeError):
                out += " (the call's arguments were not valid JSON; it is shown with {} in your history)"
        s.result.steps += 1
        s.trace("tool", name=name, args=args, result=out, duration_s=round(time.monotonic() - t0, 3))
        out = await _save(s, out)
        if name != "finish":
            s.actions.append(_action_view(name, args, out))
        _append(s, {"role": "tool", "tool_call_id": call["id"], "content": f"{out}\n{s.clock()}"})
        if finished:
            return True
    if s.pending_images:  # images follow all of the turn's tool results (tool messages must stay contiguous)
        _append(s, *s.pending_images)
        s.pending_images = []
    if mirror is not None:
        await _read_back(s, *mirror)
    return False


async def _save(s: _Session, out: str) -> str:
    """Keep an exact copy of a long result in the sandbox, so trims, edits and checkpoints never lose it."""
    if len(out) <= SAVE_OVER:
        return out
    path = saved_path(s.config.control_dir, s.result.steps)
    try:
        await put_bytes(s.env, out.encode(), path)
    except Exception as exc:  # substrate failure: the result is still shown; the trace says it was not saved
        s.trace("result_save_error", path=path, error=f"{type(exc).__name__}: {exc}")
        return out
    return f"{out}\n{SAVED_NOTE.format(path=path)}"


async def _dispatch(s: _Session, name: str, args: dict[str, Any]) -> tuple[str, bool]:
    if name == "finish":
        return await _finish(s, args)
    if name == "run_checks" and s.config.contract:
        return await contract_loop.run_checks(s), False
    if name == "terminal":
        return await s.terminals.use(name=str(args.get("name") or "main"), input=str(args.get("input", "")),
                                     mode=str(args.get("mode") or "command"), wait_s=float(args.get("wait_s") or 30),
                                     interrupt=bool(args.get("interrupt"))), False
    if name == "python":
        return await s.repl.run(str(args.get("code", "")), wait_s=float(args.get("wait_s") or 60),
                                interrupt=bool(args.get("interrupt"))), False
    if name == "view_image":
        path = s.files.resolve(args["path"])
        desc, url = await images.load(s.env, path)
        s.pending_images.append(images.message(desc, url))
        s.images_viewed += 1
        return f"[image {desc}; shown below]", False
    if name == "read_file":
        return await s.files.read(args["path"], int(args.get("start_line") or 1), int(args.get("num_lines") or 400)), False
    if name == "write_file":
        return await s.files.write(args["path"], str(args["content"])), False
    if name == "edit_file":
        return await s.files.edit(args["path"], str(args["old_str"]), str(args["new_str"]),
                                  bool(args.get("replace_all"))), False
    return f"error: unknown tool {name!r}", False


async def _read_back(s: _Session, upto: int, digest: str) -> None:
    path = s.clm.settings.mirror_path
    try:
        text = (await get_bytes(s.env, path)).decode("utf-8", "replace")
    except Exception as exc:  # the model deleted or broke the file: say so, keep the context as it was
        _attach(s.clm.editable, f"[context] could not read {path} back ({type(exc).__name__}); "
                                "your context is unchanged.")
        s.trace("context_edit", accepted=False, reason=f"read failed: {exc}")
        return
    if hashlib.sha256(text.encode()).hexdigest() == digest:
        return
    accepted, receipt = s.clm.apply_edit(text, upto)
    _attach(s.clm.editable, receipt)
    s.trace("context_edit", accepted=accepted, receipt=receipt, tokens=s.clm.tokens())
    s.files.written.pop(path, None)


async def _fit_context(s: _Session) -> bool:
    """CLM budget step before a request: roll back, or checkpoint, until it fits; then nudge."""
    clm = s.clm
    while clm.over_limit():
        if clm.can_roll_back():
            note = clm.roll_back()
            s.trace("context_rollback", tokens=clm.tokens(), note=note)
            continue
        keep = clm.checkpoint_split()
        try:
            summary, usage = await compaction.checkpoint(s.provider, s.task, clm.render(keep), repl=bool(s.repl.pid),
                                                         remaining_s=s.remaining)
        except Exception as exc:  # surfaced: the run stops with the reason, never silently trimmed
            s.trace("context_checkpoint", ok=False, error=f"{type(exc).__name__}: {exc}")
            if isinstance(exc, ProviderError) and exc.deadline:  # the time limit ran out mid-checkpoint
                s.result.status = "timeout"
            else:
                s.result.status, s.result.error = "context_error", f"checkpoint failed: {exc}"
            return False
        for key, value in usage.items():
            s.result.sub_usage[key] = s.result.sub_usage.get(key, 0) + value
        before = clm.tokens()
        clm.replace_with_checkpoint(summary, compaction.CHECKPOINT_NOTE, keep)
        s.trace("context_checkpoint", ok=True, tokens_before=before, tokens=clm.tokens(), kept_messages=
                len(clm.editable) - 1, summary=summary)
        if clm.over_limit():
            s.result.status, s.result.error = "context_error", "context is over its limit even after a checkpoint"
            return False
    note = clm.nudge()
    if note:
        _attach(clm.editable, note)
        s.trace("context_nudge", tokens=clm.tokens(), note=note)
    return True


async def _scheduled_review(s: _Session, kind: str) -> None:
    verdict, row = await s.oversight.run(kind, s.env, task=s.task, workdir=s.workdir, actions=s.actions,
                                         written=list(s.files.written))
    s.result.reviews.append(row)
    s.trace("review", answers=verdict.answers, **row)
    if verdict.status == "error":
        return
    text = (final_feedback(verdict, s.remaining()) if kind == "final"
            else progress_feedback(verdict, s.elapsed(), s.timeout_s))
    _attach(s.history, text)


async def _finish(s: _Session, args: dict[str, Any]) -> tuple[str, bool]:
    skip = s.oversight.finish_gate(s.remaining())
    if skip:
        s.trace("finish", summary=args.get("summary", ""), review="skipped", reason=skip)
        return "finished", True
    verdict, row = await s.oversight.run("finish", s.env, task=s.task, workdir=s.workdir, actions=s.actions,
                                         written=list(s.files.written))
    s.result.reviews.append(row)
    s.trace("review", summary=args.get("summary", ""), answers=verdict.answers, **row)
    if verdict.status == "hold":
        return verdict.feedback(), False
    return "finished", True


def _close(s: _Session) -> None:
    r = s.result
    r.failed_attempts = s.provider.failed_attempts
    statuses: dict[str, int] = {}
    for row in s.provider.failure_log:
        key = str(row.get("status") or row.get("error"))
        statuses[key] = statuses.get(key, 0) + 1
    r.extras = {
        "provider_failures_by_status": statuses,
        "provider_retry_wait_s": round(sum(float(x.get("wait_s") or 0) for x in s.provider.failure_log), 1),
        "images_viewed": s.images_viewed,
        "python": s.repl.python, "python_cells": s.repl.seq, "llm_calls": s.repl.llm_calls,
        "llm_errors": s.repl.llm_errors,
        "clm": s.clm.stats.__dict__ if s.clm else None,
    }
    s.trace("end", status=r.status, error=r.error, steps=r.steps, usage=r.usage, sub_usage=r.sub_usage,
            elapsed_s=round(s.elapsed(), 1), **r.extras)


def default_review_call(transport: Transport, request: dict) -> Awaitable[Any]:
    return asyncio.to_thread(transport, request)
