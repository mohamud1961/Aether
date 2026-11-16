"""Per-run state shared by the loop's helpers, and how messages enter the context (split from loop.py)."""

from __future__ import annotations

import json
import os
import shlex
import time
import uuid
from typing import Any, Awaitable, Callable

from . import box_python, diffcheck, facts_probe, facts_projection, facts_pull, finish_report, runstate
from .clm import ClmContext
from .clone import Clone
from .env import DeadlineEnvironment, Environment, run
from .files import Files
from .loop_records import RunResult, Trace  # re-exported for existing callers
from .oversight import Oversight
from .record import Record
from .repl import Repl, sub_llm
from .terminal import Terminals
from . import browser
from .loop_config import VERIFIER_ROLE


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


def _attach(messages: list[dict[str, Any]], note: str) -> None:
    """Add a harness note to the newest tool result (or as a user message when there is none)."""
    if messages and messages[-1].get("role") == "tool":
        messages[-1]["content"] = f"{messages[-1]['content']}\n\n{note}"
    else:
        messages.append({"role": "user", "content": note})


class _Session:
    """Per-run state shared by the loop's helpers."""

    def __init__(
        self, env, task, workdir, provider, timeout_s, trace, config, transport, call, stop_margin_s
    ):
        self.env, self.task, self.workdir, self.provider = env, task, workdir, provider
        self.timeout_s, self.trace, self.config = timeout_s, trace, config
        self.witness = None  # outside_witness: first-write capture for the file tools (A21)
        self.rehydrate_due = False  # a provider compaction item arrived: rehydrate before the next request
        self.session_log = None  # H10: set by the loop when config.session_log is on
        self.started = time.monotonic()
        self.deadline = self.started + timeout_s - stop_margin_s
        self.result = RunResult("timeout")
        self.env = DeadlineEnvironment(env, self.remaining)
        self.browser = browser.BrowserSession(config.browser, self.env, persistent=config.browser_session,
                                              page_facts=config.browser_page_facts,
                                              effects=config.browser_effects) if config.browser else None
        self.terminals = Terminals(
            self.env, workdir, self.remaining, control_dir=config.control_dir,
            command_names=facts_probe.COMMANDS if config.managed_facts and config.role == "worker" else (),
            capture_state=config.facts_pull, preserve_existing=config.terminal_events,
            deliver_results=config.terminal_result_delivery,
            fast_process_scan=config.fast_process_scan,
        )
        self.facts = (facts_pull.make(self.env, workdir, self.remaining, trace, terminal_state=self.terminals.observed_session,
                                     python_state=lambda: self.repl.observed_state(), pull=config.facts_pull, v2=config.facts_v2,
                                     control_dir=config.control_dir, versions=config.check_versions) if config.managed_facts and config.role == "worker" else None)
        self.facts_pinned_index = None
        source = "state-v2" if config.facts_v2 else "managed-facts"
        self.facts_timeline = (facts_projection.FactsTimeline(source)
                               if self.facts and config.stable_facts and not config.facts_pull else None)
        self.files = Files(self.env, workdir)
        self.repl = Repl(
            self.env,
            workdir,
            self.remaining,
            sub_llm(provider, self.remaining, self.result.sub_usage),
            base=f"{config.control_dir}/repl",
            track_operations=config.terminal_events,
            library=config.toolset == "python",
            bundled_python=os.environ.get(box_python.REPL_PYTHON_ENV, ""),
        )
        self.oversight = Oversight(
            config.reviews, transport, call, timeout_s, control_dir=config.control_dir
        )
        self.actions: list[str] = []
        self.output_cut = False
        self.finish_wait_returned = False
        self.task_reshown = False  # task_at_first_observation fires once
        self.clm: ClmContext | None = None
        self.append_ctx = None  # context "append" (context_append.AppendContext)
        # Optional and ephemeral: index the first decision after a new CLM
        # edit/checkpoint/rollback, not every later turn (prompt-cost guard).
        self.evidence_index_last_generation: tuple[int, int, int] | None = None
        self.messages: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self.pending_images: list[
            dict[str, Any]
        ] = []  # shown after the current turn's tool results
        self.images_viewed = 0
        self.new_image = False  # the next request is the first to carry a newly attached image (image_effort)
        self.call_id = ""  # the call being dispatched (the fork answers the finish call by its id)
        self.operation_delivery = ""
        self.report_steps: list[finish_report.StepRecord] = []  # the finish report's step log
        # clone operations that outlived their check, owned by run-end cleanup (see verify)
        self.pending_cleanup: list[tuple[str, Any]] = []
        self.state = runstate.RunState(task, workdir) if config.state and config.role != VERIFIER_ROLE else None
        self.record = (
            Record(self.env, workdir, config.control_dir, self.remaining, trace, measure=config.record_measure, task=task,
                   paths_only=config.record_paths, commands=config.record_commands)
            if config.record and config.role != VERIFIER_ROLE else None
        )
        self.held = False  # the neutral finish hold was used
        self.diffcheck = (
            diffcheck.DiffCheck(self.env, task, f"{config.control_dir}/diffcheck", self.remaining, trace, _diffcheck_author(self),
                        self.elapsed, box=(lambda t: self.clone(self.env, timeout_s=t, egress=True)) if config.make_clone else None)
            if config.diffcheck and config.role == "worker" else None
        )

    def clone(
        self, env: Environment, timeout_s: float | None = None, read_only: bool = False, **egress: bool
    ) -> Awaitable[Any]:
        """A clone factory takes the time it may use (None: the run's remaining time), whether its filesystem is
        read-only outside clone.SCRATCH and, only for the diffcheck box, egress=True (the task's own network reach)."""
        return (self.config.make_clone or Clone.create)(
            env, timeout_s=timeout_s, read_only=read_only, **egress
        )

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def clock(self) -> str:
        return f"[t={self.elapsed():.0f}s of {self.timeout_s:.0f}s]"

    def delivery_tag(self) -> str:
        if not self.operation_delivery:
            self.operation_delivery = uuid.uuid4().hex
        return self.operation_delivery

    @property
    def history(self) -> list[dict[str, Any]]:
        return self.clm.editable if self.clm else self.messages


def _append(s: _Session, *messages: dict[str, Any]) -> None:
    if s.clm:
        s.clm.append(*messages)
    else:
        s.messages.extend(messages)


def _publish_facts(s: _Session, body: str, step: int) -> None:
    timeline = s.facts_timeline
    note = timeline.observe(body, step, s.facts.initial_workspace)
    if note is not None:
        _append(s, note)
        s.trace("facts_projection", generation=timeline.generation, revision=timeline.revision,
                source=timeline.source, step=step)


def _restore_facts(s: _Session) -> None:
    if s.facts_timeline and s.clm:
        latest = s.facts_timeline.latest
        if latest is not None and latest not in s.clm.editable:
            _append(s, latest)


def _diffcheck_author(s: _Session) -> Callable[[str, float], Awaitable[Any]]:
    """The differential check's author: a fresh Core run in the check's own container (isolated mode) or, in
    component tests only, the given environment, working in the check directory (see diffcheck)."""

    async def author(brief: str, timeout_s: float, env: Environment | None = None) -> RunResult:
        from .loop import run_agent  # the author is a fresh Core run
        from .verify import _Labelled

        env = env if env is not None else s.env
        await run(env, f"mkdir -p {shlex.quote(s.diffcheck.dir)}")
        return await run_agent(env=env, task=brief, workdir=s.diffcheck.dir,
                               provider=_Labelled(s.provider, diffcheck.AUTHOR_ROLE), timeout_s=timeout_s,
                               trace=Trace(s.trace.path.with_name(diffcheck.TRACE_FILE)),
                               config=diffcheck.author_config(s.config))

    return author
