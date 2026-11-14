"""The Aether Core agent loop: model turn -> tools -> results, until finish or time.

Everything the model does is recorded in full (reasoning, calls, results,
timings, token usage, every failed provider attempt) to ``core_trace.jsonl``.
What the model sees is either the ``project`` view of that history (C1) or a
context the model manages itself under a token budget (``clm``; see ``clm``).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import shlex
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from . import compaction, diffcheck, facts, facts_probe, facts_projection, facts_pull, finish_report, image_region, images, intent, runstate
from . import receipt as finish_receipt
from .clm import ClmContext, ClmSettings
from .clone import Clone
from .context import SAVE_OVER, SAVED_NOTE, project, saved_path, size_chars
from .env import (
    CONTROL_DIR,
    DeadlineEnvironment,
    Environment,
    get_bytes,
    put_bytes,
    run,
)
from .files import Files
from .facts_workspace import WorkspaceBriefText
from .loop_records import RunResult, Trace  # re-exported for existing callers
from .oversight import Oversight, ReviewPlan, final_feedback, progress_feedback
from .provider import ChatProvider, ProviderError, parse_arguments
from .record import NEUTRAL_HOLD, Record
from .repl import Repl, sub_llm
from .review import Transport
from .terminal import Terminals
from . import agenda, browser, completion_notice, finish_settle, open_issues, stated_use, step0, workspace_brief
from .tools import system_prompt, tools, validate_call

MAX_OUTPUT_TOKENS = 16_384  # was 32_768; see CoreConfig.max_output_tokens
# A turn the output limit cuts off before any tool call is almost never followed by action at the same effort:
# in the archived rows 30 of 32 such turns produced nothing, and V2 dna-assembly lost 550-900 s of each row to
# two or three in a row. The next turn runs at low effort, to act on the reasoning it already has.
AFTER_CUT = {"reasoning_effort": "low"}
# V3: 3 of 4 low-effort turns acted within 25 s (under 2k output tokens); one still reasoned to 32k (265 s).
# Its output cap bounds that case to a quarter of the time.
AFTER_CUT_MAX_TOKENS = 8_192
STOP_MARGIN_S = 15.0
CONTEXT_MODES = ("project", "clm")
VERIFIER_ROLE = "verifier"  # the call-log role of the one independent finish check (see verify)


@dataclass(frozen=True)
class CoreConfig:
    context: str = "project"
    repl: bool = False
    images: bool = False
    reviews: ReviewPlan = ReviewPlan()
    clm: ClmSettings = field(default_factory=ClmSettings)
    control_dir: str = CONTROL_DIR  # where terminals and the REPL keep their files in the sandbox
    make_clone: Callable[[Environment], Awaitable[Any]] | None = None  # tests inject a clone; default docker
    parallel_reads: bool = False  # opt-in: bounded contiguous read_file batches only
    verify: bool = False  # one independent check of the first finish, in a fresh context on a clone (see verify)
    self_check: bool = (
        False  # the self-check paragraph in the system prompt (tools.SELF_CHECK_DOC)
    )
    intent: bool = False  # every action tool takes the model's reason and expected result (see intent)
    fork: bool = False  # experiment instrument: at the first finish, matched continuations on clones (see fork)
    fork_arms: tuple[tuple[str, str], ...] = ()  # named fork arms (fork.load_arms); empty: B and C
    fork_keep: bool = False  # keep the first-finish checkpoint for a later resume (fork.keep; named arms only)
    # Run end: "keep" (the default) leaves the container as the agent left it, because a service the task needs
    # running is part of the delivered state (E0/E3: pypi-server and kv-store-grpc 0/2 under stop, 2/2 under keep),
    # and records what was still running in ``left_running``. The container is owned by the trial and removed after
    # grading, which is the cleanup. "stop" kills every process started in a terminal (the pre-E3 behaviour).
    end_processes: str = "keep"
    hygiene: str = "off"  # tools.HYGIENE_MODES: one delivery-hygiene line (on) or its placebo in the solver prompt
    state: bool = False  # run state: harness-run requirement checks, notes, finish re-check (see runstate)
    managed_facts: bool = False  # isolated state/environment treatment; not yet qualified as a default
    facts_pull: bool = False  # expose managed observations as files instead of pushed notes
    facts_v2: bool = False  # the verified state service instead: env block + one line per action (state_service)
    role: str = "worker"  # call-log role of this run's own turns; VERIFIER_ROLE for the verifier's run
    record: bool = False  # the harness's record of the model's own command results, its facts and finish re-run (record)
    record_measure: bool = False  # the record also compares each check's printed results across file versions (record)
    record_paths: bool = False  # the record states only task-named paths that do not exist yet (record)
    record_commands: bool = False  # ...and at the first finish the task-shown commands no command contained (record)
    finish_hold: str = "off"  # "neutral": the first finish is held once with time left and no facts (control arm)
    browser: Any = None  # browser.Factory: a real browser in a sidecar on the task's network (browser); None = off
    image_region: bool = False  # view_image may show part of an image at full resolution (image_region)
    image_compare: bool = False  # view two independently selected images in the same observation
    # Reasoning effort for the request that first sees a newly attached image ("" = the run's own). 28 Oct: an
    # image-reading task went 0/3 at high and 2/3 valid at xhigh run-wide; this spends the extra effort only there.
    image_effort: str = ""
    env_brief: bool = False  # what the container provides (tools, packages, files), measured once, in the task (env_brief)
    start_copy: bool = False  # a copy of the working directory before the first action, named in the task (start_copy)
    task_at_first_observation: bool = False  # the task text once more, beside the first tool result (FD2, 10 Nov)
    stated_use: bool = False  # the task's own literal commands, run once when the work first exists (stated_use)
    working: str = "on"  # "lean": solver prompt without the three thoroughness lines (study arm)
    task_appendix_file: str = ""  # study arm: a file whose text follows the task in the first message (XL step-0 list)
    step0_file: str = ""  # study arm: JSON {question, answer}; the step-0 list as the model's own first turn (step0.py)
    agenda: str = "off"  # study arm: "on" = one no-tools call first; the model's own list of open points follows the task (agenda.py)
    start_note: str = "start"  # "late": start-copy note and state line wait for a changed start file (study arm)
    state_view: bool = False  # with start_copy: a read-only command showing what changed since it (state_view)
    diffcheck: bool = False  # an executable check of the task's output, written from the task alone during the run (diffcheck)
    # Per-turn output ceiling. Azure admits a request against the token rate limit by prompt + this ceiling, so
    # an unused ceiling costs rate-limit headroom (mission 2026-10-28: 2910 Luna turns, p99.9 11k, max 17k).
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    rival: bool = False  # at the first finish, a fresh call writes the strongest rival answer, handed back once (rival)
    exec_check: bool = False  # ablation of rival: the first finish is handed back once asking to run the deliverable
    card: bool = False  # at the first finish, a fresh reading of the request alone is handed back once (card)
    card_probe: bool = False  # the card's reader also writes a script observing each item; Core runs it once (card)
    card_challenge: str = ""  # "challenge": read-only checks, raw output (card, CH1); "attack": clone checks (attack, CH2); "observe": recorded only; "forks": start observations (forks)
    open_issues: bool = False  # finish takes the model's open issues; listing any with time left returns it once
    evidence_presentation: str = "off"  # default-off CLM source history index; not a task correctness engine
    stable_facts: bool = False
    terminal_events: bool = False
    finish_settle: bool = False  # hold the first finish once if delivered files are still changing (finish_settle)
    mcp_servers: tuple = ()  # opt-in (AETHER_CORE_MCP): task-declared MCP servers exposed through the mcp tool
    skills_dir: str | None = None  # opt-in (AETHER_CORE_SKILLS): the task-declared skills directory to list at start
    env_map: bool = False  # opt-in: repositories and listening services, measured once at start (env_map)
    completion_notices: bool = False  # opt-in: one line when a background terminal command finishes (completion_notice)
    workspace_brief: bool = False

    def __post_init__(self) -> None:
        if self.facts_pull and not self.managed_facts:
            raise ValueError("facts_pull requires managed_facts")
        if self.managed_facts and self.env_brief:
            raise ValueError("managed_facts and env_brief are alternative information channels")
        if self.context not in CONTEXT_MODES:
            raise ValueError(f"context must be one of {CONTEXT_MODES}")
        from .evidence_context import CONTEXT_EVIDENCE_MODES

        if self.evidence_presentation not in CONTEXT_EVIDENCE_MODES:
            raise ValueError(f"evidence_presentation must be one of {CONTEXT_EVIDENCE_MODES}")
        if self.evidence_presentation != "off" and self.context != "clm":
            raise ValueError("evidence_presentation requires Core CLM history")
        if self.evidence_presentation == "history_index" and not self.clm.attest_original_history:
            raise ValueError("history_index requires append-time original-history attestation")
        self.clm.check_request_limit(self.max_output_tokens)


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
        self, env, task, workdir, provider, timeout_s, trace, config, transport, call
    ):
        self.env, self.task, self.workdir, self.provider = env, task, workdir, provider
        self.timeout_s, self.trace, self.config = timeout_s, trace, config
        self.started = time.monotonic()
        self.deadline = self.started + timeout_s - STOP_MARGIN_S
        self.result = RunResult("timeout")
        self.env = DeadlineEnvironment(env, self.remaining)
        self.browser = browser.BrowserSession(config.browser, self.env) if config.browser else None
        self.terminals = Terminals(
            self.env, workdir, self.remaining, control_dir=config.control_dir,
            command_names=facts_probe.COMMANDS if config.managed_facts and config.role == "worker" else (),
            capture_state=config.facts_pull, preserve_existing=config.terminal_events,
        )
        self.facts = (facts_pull.make(self.env, workdir, self.remaining, trace, terminal_state=self.terminals.observed_session,
                                     python_state=lambda: self.repl.observed_state(), pull=config.facts_pull, v2=config.facts_v2,
                                     control_dir=config.control_dir) if config.managed_facts and config.role == "worker" else None)
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
        )
        self.oversight = Oversight(
            config.reviews, transport, call, timeout_s, control_dir=config.control_dir
        )
        self.actions: list[str] = []
        self.output_cut = False
        self.finish_wait_returned = False
        self.task_reshown = False  # task_at_first_observation fires once
        self.clm: ClmContext | None = None
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

    @property
    def history(self) -> list[dict[str, Any]]:
        return self.clm.editable if self.clm else self.messages


async def run_agent(
    *,
    env: Environment,
    task: str,
    workdir: str,
    provider: ChatProvider,
    timeout_s: float,
    trace: Trace,
    review_transport: Transport | None = None,
    review_call: Callable[..., Awaitable[Any]] | None = None,
    config: CoreConfig | None = None,
    resume: list[dict[str, Any]] | ClmContext | None = None,
) -> RunResult:
    """``resume``: continue an existing history instead of starting one (the fork arms use it): a message list
    (system prompt and task included) for the project context, a ``ClmContext`` for clm."""
    config = config or CoreConfig(
        reviews=ReviewPlan(finish=review_transport is not None)
    )
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be finite and positive")
    if resume is not None and isinstance(resume, ClmContext) != (config.context == "clm"):
        raise ValueError("resume must match the context: a ClmContext for clm, a message list otherwise")
    s = _Session(
        env,
        task,
        workdir,
        provider,
        timeout_s,
        trace,
        config,
        review_transport,
        review_call,
    )
    if resume is not None and s.facts:
        s.facts.initial_workspace = facts.continuation_state(resume) or s.facts.initial_workspace
        s.facts.initial_workspace.prepare_resume()
    try:
        async with asyncio.timeout(max(0, s.remaining())):
            setup_result = await s.env.exec(
                command=f"mkdir -p {shlex.quote(config.control_dir)}",
                cwd=None,
                env=None,
                timeout_sec=30,
            )
            from .env import exit_code

            if exit_code(setup_result) != 0:
                raise OSError("control directory setup did not report success")
            start_note = ""
            if (config.rival or config.card) and config.role == "worker":
                from . import attack

                await attack.mark_start(s)  # the start marker; in attack mode also the reader call
            if config.start_copy and config.role == "worker":
                from . import start_copy

                start_note, row = await start_copy.take(s.env, workdir, config.control_dir, view=config.state_view)
                facts_pull.trace_start_copy(s.facts, row, workdir, trace)
                if getattr(config, "start_note", "start") == "late":  # study arm: shown at the first changed start file
                    s.late_note, start_note = start_note, ""
            if config.env_brief and config.role == "worker":
                from . import env_brief

                brief, row = await env_brief.take(s.env, workdir)
                trace("env_brief", **row)
                start_note = "\n".join(x for x in (brief, start_note) if x)
            if config.env_map and config.role == "worker":
                from . import env_map

                mapped, row = await env_map.take(s.env, workdir)
                trace("env_map", **row)
                start_note = "\n".join(x for x in (start_note, mapped) if x)
            if getattr(config, "skills_dir", None) and config.role == "worker":
                from . import skills

                listed, row = await skills.take(s.env, config.skills_dir)
                trace("skills", **row)
                start_note = "\n".join(x for x in (start_note, listed) if x)
            # the start marker: files newer than it are what the run changed (the verifier and the finish report
            # use it). Only the verifier needs it to work; for the report a missing marker is a reported fact, not a
            # run failure.
            try:
                await finish_receipt.mark(s.env, config.control_dir)
            except OSError:
                if config.verify:
                    raise
            if s.diffcheck:
                await s.diffcheck.start()
            python = await s.repl.start() if config.repl else ""
            see = config.images and images.available()
            s.tools = tools(
                python=bool(python),
                images=see,
                history=config.context == "clm",
                verdict=config.role == VERIFIER_ROLE,
                terminal_events=config.terminal_events and config.role == "worker",
            )
            if getattr(config, "mcp_servers", ()) and config.role == "worker":
                from . import mcp

                s.mcp = mcp.Mcp(s.env, config.control_dir, list(config.mcp_servers))
                s.tools = [*s.tools, mcp.tool(list(config.mcp_servers))]
            if config.image_region and see:
                s.tools = image_region.with_region(s.tools)
            if config.image_compare and see:
                s.tools = image_region.with_compare(s.tools)
            if config.intent:
                s.tools = intent.with_intent(s.tools)
            if config.open_issues:
                s.tools = open_issues.with_field(s.tools)
            s.tools = browser.with_tool(s.tools) if config.browser else s.tools
            if s.state:
                s.tools = runstate.with_state(s.tools)
            if s.facts and config.facts_pull:
                start_note = "\n".join(filter(None, (start_note, await s.facts.start())))
            agenda_text = ""
            if getattr(config, "agenda", "off") in ("on", "consensus") and config.role == "worker" and resume is None:
                agenda_text = await agenda.ask(s.provider, task, s.remaining, trace, config.agenda)
            pinned = [
                {
                    "role": "system",
                    "content": system_prompt(
                        python_version=python,
                        clm=config.context == "clm",
                        images=see,
                        mirror_path=config.clm.mirror_path,
                        history_path=config.clm.history_path,
                        self_check=config.self_check,
                        verifier=config.role == VERIFIER_ROLE,
                        hygiene=config.hygiene,
                        working=getattr(config, "working", "on"),
                        notes=config.clm.notes_voice,
                    )
                    + (runstate.STATE_DOC if s.state else "")
                    + (facts_projection.POLICY if s.facts_timeline else ""),
                },
                *step0.task_messages(
                    getattr(config, "step0_file", ""),
                    task,
                    _appendix(config) + agenda_text,
                    f"(Working directory: {workdir}. Time limit: {timeout_s:.0f}s.)"
                    + "".join(f"\n{x}" for x in (start_note, getattr(s, "forks_note", "")) if x),
                ),
            ]
            if config.context == "clm":
                s.clm = resume or ClmContext(pinned=pinned, settings=config.clm)
            else:
                s.messages = list(resume) if resume is not None else list(pinned)
            if config.workspace_brief and config.role == "worker" and resume is None:
                brief = await workspace_brief.observe(s.env, workdir, trace)
                if brief:
                    _append(s, {"role": "assistant", "content": WorkspaceBriefText(brief)})
            if s.facts and config.facts_pull:
                s.facts_pinned_index = facts_pull.attach(s.clm, s.messages, resume is not None, s.facts)
            elif s.facts_timeline:
                _publish_facts(s, await s.facts.start(), 0)
            elif s.facts:
                text = await s.facts.start()
                note = {"role": "user", "content": facts.ManagedFactsText(text, s.facts.initial_workspace)}
                if s.clm:
                    s.facts_pinned_index = facts.install_clm_note(s.clm, note)
                else:
                    s.facts_pinned_index = facts.install_project_note(s.messages, note["content"])
            trace(
                "start",
                workdir=workdir,
                timeout_s=timeout_s,
                model=provider.model,
                params=provider.params,
                review=bool(review_transport),
                context=config.context,
                repl=config.repl,
                python=python,
                images=see,
                intent=config.intent,
                reviews=config.reviews.__dict__,
                clm=config.clm.__dict__ if s.clm else None,
            )
            await _loop(s)
    except TimeoutError:
        s.result.status, s.result.error = "timeout", "run work deadline exceeded"
    except asyncio.CancelledError:
        s.result.status, s.result.error = "cancelled", "run cancelled by caller"
        raise
    except Exception as exc:
        s.result.status, s.result.error = (
            "environment_error",
            f"{type(exc).__name__}: {exc}",
        )
    finally:
        cleanup_errors = []
        if s.facts:
            s.result.extras["core_facts"] = s.facts.safe_record()
        if s.diffcheck:
            await s.diffcheck.close()
        s.env.cleanup_until(time.monotonic() + max(1.0, STOP_MARGIN_S))
        for name, task in s.pending_cleanup:
            try:
                async with asyncio.timeout(max(1.0, s.env.remaining_s())):
                    outcome = (await asyncio.gather(task, return_exceptions=True))[0]
                if isinstance(outcome, Exception):
                    cleanup_errors.append(
                        f"{name}: {type(outcome).__name__}: {outcome}"
                    )
            except TimeoutError:
                cleanup_errors.append(f"{name}: still running when the run ended")
        keep = s.config.end_processes == "keep"
        closers = [("terminals", lambda: s.terminals.close(keep=keep)), ("repl", lambda: s.repl.close(keep=keep))]
        if s.browser:
            closers.append(("browser", s.browser.close))
        if getattr(s, "mcp", None):
            s.result.extras["mcp_calls"] = s.mcp.calls
            closers.append(("mcp", s.mcp.close))
        for name, closer in closers:
            try:
                await closer()
            except Exception as exc:
                cleanup_errors.append(f"{name}: {type(exc).__name__}: {exc}")
        if s.terminals.cleanup_uncertainties:
            cleanup_errors.append("earlier terminal cleanup unverified: " + "; ".join(s.terminals.cleanup_uncertainties))
        s.result.extras["cleanup_errors"] = cleanup_errors
        s.result.extras["process_cleanup"] = {
            "terminals": s.terminals.cleanup_receipt,
            "repl": s.repl.cleanup_receipt,
            "scope": "observed process identities; detached ownership before observation is not established",
        }
        s.result.extras["end_processes"] = s.config.end_processes
        s.result.extras["left_running"] = s.terminals.left_running
        try:
            async with asyncio.timeout(60):
                s.result.extras["finish_report"] = await finish_report.build(
                    s.env,
                    s.workdir,
                    s.config.control_dir,
                    s.report_steps,
                    status=s.result.status,
                    finish_summary=(s.result.extras.get("finish_args") or {}).get("summary"),
                    left_running=s.terminals.left_running,
                    task=s.task,
                )
                s.result.final_account = finish_report.render(s.result.extras["finish_report"])
            if s.state:
                s.result.extras["run_state"] = s.state.record()
                s.result.final_account += "\n\n" + s.state.account()
        except Exception as exc:
            cleanup_errors.append(f"finish report: {type(exc).__name__}: {exc}")
        if cleanup_errors:
            s.result.final_account += "\n\n[cleanup incomplete or unverified]\n" + "\n".join(cleanup_errors)
        _close(s)
    return s.result


async def _loop(s: _Session) -> None:
    result, idle_turns, tight, cut = s.result, 0, False, False
    while s.remaining() > 0:
        due = s.oversight.due(s.elapsed(), s.remaining())
        if due:
            await _scheduled_review(s, due)
        if s.clm and not await _fit_context(s):
            return
        request = s.clm.request() if s.clm else project(s.messages, tight=tight)
        if s.config.evidence_presentation != "off":
            from .evidence_context import select_context

            generation = (
                s.clm.stats.edits_accepted,
                s.clm.stats.checkpoints,
                s.clm.stats.rollbacks,
            )
            if s.evidence_index_last_generation == generation:
                presentation = {
                    "policy": s.config.evidence_presentation,
                    "changed": False,
                    "reason": "already_presented_for_context_generation",
                }
            else:
                request, presentation = select_context(
                    s.clm, request, s.tools, policy=s.config.evidence_presentation
                )
                if presentation.get("changed") is True:
                    s.evidence_index_last_generation = generation
            s.trace("context_evidence_presentation", **presentation)
        result.request_chars.append(size_chars(request))
        sizes = {"held": s.clm.held(), "request": s.clm.tokens()} if s.clm else None
        look = s.new_image and bool(s.config.image_effort) and s.provider.takes_effort and not cut
        s.new_image = False
        try:
            turn = await s.provider.complete(
                request,
                s.tools,
                max_tokens=min(AFTER_CUT_MAX_TOKENS, s.config.max_output_tokens) if cut else s.config.max_output_tokens,
                remaining_s=s.remaining,
                overrides=AFTER_CUT if cut else ({"reasoning_effort": s.config.image_effort} if look else None),
                role=s.config.role,
            )
        except ProviderError as exc:
            s.trace(
                "provider_error",
                status=exc.status,
                error=str(exc),
                deadline=exc.deadline,
                overflow=exc.context_overflow,
            )
            if exc.context_overflow and not tight and not s.clm:
                tight = True
                continue
            if exc.deadline:  # the reason is kept: a retry wait that outran the deadline is not the model's timeout
                result.status, result.error = "timeout", str(exc)
            else:
                result.status, result.error = "provider_error", str(exc)
            return
        result.calls += 1
        for key, value in turn.usage.items():
            result.usage[key] = result.usage.get(key, 0) + value
        if s.clm:
            s.clm.calibrate(result.request_chars[-1], turn.usage.get("input", 0))
        s.trace(
            "model",
            latency_s=round(turn.latency_s, 3),
            attempts=turn.attempts,
            failures=turn.failures,
            usage=turn.usage,
            request_chars=result.request_chars[-1],
            context_tokens=sizes,  # held (budgeted) and the whole request, estimated before sending
            finish_reason=turn.finish_reason,
            reasoning=turn.reasoning,
            content=turn.content,
            tool_calls=turn.tool_calls,
            effort=AFTER_CUT["reasoning_effort"] if cut and s.provider.takes_effort else (
                s.config.image_effort if look else None),
        )
        cut = turn.finish_reason == "length" and not turn.tool_calls
        assistant = turn.assistant_message()
        _append(s, assistant)
        if s.clm:
            s.clm.note_reasoning(assistant, turn.usage.get("reasoning"))
        if not turn.tool_calls:
            # A turn the output limit cut off is work in progress, not idleness; the time limit bounds it (D1
            # regex-chess: three 32k-token thoughts in a row ended the run with 30 minutes left).
            idle_turns += turn.finish_reason != "length"
            if idle_turns >= 3:
                result.status = "no_tool_loop"
                return
            if (
                turn.finish_reason == "length"
            ):  # say what happened: the output limit cut the turn off
                note = (
                    "Your last turn reached the output limit before any tool call; "
                    "its reasoning is above. Act on it now with a tool call (for example write down or test "
                    "your partial result) instead of reasoning further in one turn; "
                    + (  # only what really changes: a model without effort levels gets the smaller limit alone
                        "your next turn runs at low reasoning effort. "
                        if s.provider.takes_effort
                        else f"your next turn's output limit is {AFTER_CUT_MAX_TOKENS:,} tokens. "
                    )
                )
            else:
                note = "Continue by using a tool, or call finish if done. "
            _append(s, {"role": "user", "content": note + s.clock()})
            continue
        idle_turns = 0
        s.output_cut = turn.finish_reason == "length"  # a call cut off by the output limit has broken arguments
        if await _run_calls(s, turn.tool_calls):
            result.status = "finished"
            return


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


async def _run_calls(s: _Session, calls: list[dict[str, Any]]) -> bool:
    """Execute one turn's tool calls. Returns True when the run finished."""
    mirror = None
    mirror_error = ""
    if s.clm:
        upto = len(s.clm.editable) - 1  # the mirror holds history before this turn's assistant message
        text = s.clm.render(upto)
        try:
            await put_bytes(s.env, text.encode(), s.clm.settings.mirror_path)
            mirror = (upto, hashlib.sha256(text.encode()).hexdigest())
        except Exception as exc:
            mirror_error = f"[context mirror unavailable: {type(exc).__name__}: {exc}; context unchanged]"
            s.trace("context_mirror_error", error=mirror_error)
    failed = bool(mirror_error)
    finished = False
    fact_update = False
    buffered: dict[int, tuple[dict, str, bool, float, bool]] = {}
    for index, call in enumerate(calls):
        name = call["function"]["name"]
        if name == "finish" and failed:
            # The ordinary end-of-turn probe below is skipped when finish ends
            # this response. Check here so a same-response finish cannot hide
            # an earlier tool or context-mirror failure. A live sandbox still
            # permits the model to finish after an ordinary tool error.
            await _require_environment(s)
        if s.config.parallel_reads and name == "read_file" and index not in buffered:
            end = index
            while end < len(calls) and calls[end]["function"]["name"] == "read_file":
                end += 1
            gate = asyncio.Semaphore(4)

            async def read_one(item):
                async with gate:
                    return await _invoke(s, item)

            results = await asyncio.gather(
                *(read_one(item) for item in calls[index:end])
            )
            buffered.update(zip(range(index, end), results))
        args, out, finished, duration, held_finish = (
            buffered.pop(index) if index in buffered else await _invoke(s, call)
        )
        failed = failed or out.startswith("error:")
        if mirror_error:
            out += "\n" + mirror_error
            mirror_error = ""
        s.result.steps += 1
        if s.facts:
            update = await s.facts.after_action(s.result.steps, name, args, out, call_id=call["id"])
            if update and getattr(s, "late_note", ""):
                from . import start_copy

                update, s.late_note = start_copy.late(update, s.late_note)
                if not s.late_note:
                    s.trace("start_note_shown", step=s.result.steps)
            if update:
                out = f"{out}\n{update}"
            fact_update |= bool(s.facts.context_changed)
            if (update or s.facts.context_changed) and s.facts_pinned_index is not None:
                pinned = s.clm.pinned if s.clm else s.messages
                text = facts.ManagedFactsText(str(pinned[s.facts_pinned_index]["content"]) if s.config.facts_pull else s.facts.context_summary(), s.facts.initial_workspace)
                pinned[s.facts_pinned_index] = {"role": "user", "content": text}
        s.report_steps.append(
            finish_report.record(s.result.steps, name, args, out, s.workdir)
        )
        s.trace("tool", name=name, args=args, result=out, duration_s=duration)
        if s.record and name == "terminal":
            fact = await s.record.after_terminal(args, out, s.elapsed())
            if fact:
                out = f"{out}\n{fact}"
        if s.diffcheck and name != "finish":
            found = await s.diffcheck.after_action()
            if found:
                out = f"{out}\n{found}"
        if getattr(s.config, "completion_notices", False) and name != "finish":
            out += await completion_notice.after_tool(s)
        out = await _save(s, out)
        if s.state and not finished:
            if name in ("write_file", "edit_file") and not out.startswith("error"):
                s.state.wrote()
            out = _with_state(s, out)
        if name != "finish":
            s.actions.append(_action_view(name, args, out))
        reshow = ""  # task_at_first_observation: the task text once, beside the first tool result (method choice)
        if getattr(s.config, "task_at_first_observation", False) and not getattr(s, "task_reshown", True) and name != "finish":
            s.task_reshown, reshow = True, f"\n\n[The task, as given]\n{s.task}"
        if getattr(s.config, "stated_use", False) and name != "finish":
            reshow += await stated_use.after(s, name, args)
        _append(
            s,
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": f"{out}\n{s.clock()}{reshow}",
            },
        )
        if finished:
            return True
        if held_finish:
            # The hold requires a new model decision. Close the tool packet
            # without executing actions queued before the model saw the hold.
            for queued in calls[index + 1:]:
                cid = queued["id"]
                s.trace("action_skipped", call_id=cid, reason="finish_held")
                _append(s, {
                    "role": "tool", "tool_call_id": cid,
                    "content": "[not dispatched: finish was held for a new decision]",
                })
            break
    if failed:
        await _require_environment(s)
    if fact_update and s.facts_timeline:
        _publish_facts(s, s.facts.context_summary(), s.result.steps)
    if s.pending_images:  # images follow all of the turn's tool results (tool messages must stay contiguous)
        _append(s, *s.pending_images)
        s.pending_images = []
        s.new_image = True
    if mirror is not None:
        await _read_back(s, *mirror)
    return False


class EnvironmentUnverified(RuntimeError):
    """A failed probe could not confirm the sandbox is live; the run ends as ``environment_error``."""


async def _require_environment(s: _Session) -> None:
    """After a turn with a failed tool or context write, confirm the sandbox still answers. P2 (10-22): Daytona
    deleted two sandboxes mid-run and Core called the model for 13 and 25 more minutes, every tool failing."""
    error = ""
    for attempt in range(2):
        try:
            probe = await run(s.env, "true", timeout_s=20)
            if probe.code == 0:
                return
            error = f"'true' probe did not report exit 0 (reported {probe.code})"
            if probe.stderr or probe.stdout:
                error += f": {(probe.stderr or probe.stdout).strip()[:200]}"
        except TimeoutError:
            if s.remaining() <= 0:
                raise
            error = "no answer within 20 s"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        if attempt == 0:
            await asyncio.sleep(2)
    s.trace("environment_unverified", error=error)
    raise EnvironmentUnverified(f"the sandbox could not be confirmed live: {error}")


async def _invoke(s: _Session, call: dict) -> tuple[dict, str, bool, float, bool]:
    """Execute one validated call, preserving errors and result ownership for ordered publication."""
    started = time.monotonic()
    name = call["function"]["name"]
    args: dict[str, Any] = {}
    finished, held_finish = False, False
    try:
        args = parse_arguments(call["function"]["arguments"])
        validate_call(name, args, s.tools)
        s.call_id = call["id"]
        out, finished = await _dispatch(s, name, args)
        held_finish = name == "finish" and not finished
    except Exception as exc:
        out = f"error: {type(exc).__name__}: {str(exc)[:1000]}"
        if isinstance(exc, json.JSONDecodeError) and s.output_cut:  # y13/y14: 4 of 4 bad-JSON calls were cut off here
            out += (" (your turn reached the output limit while writing this call, so its arguments were cut off and "
                    "nothing ran; write long content in smaller parts, e.g. write_file a first part, then append the rest from the terminal)")
        elif isinstance(exc, json.JSONDecodeError):
            out += " (the call's arguments were not valid JSON; it is shown with {} in your history)"
    return args, out, finished, round(time.monotonic() - started, 3), held_finish


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
    if name == "read_history" and s.clm:
        return s.clm.read_history(
            args["message_id"], args.get("offset", 0), args.get("limit", 12000)
        ), False
    if name == "finish":
        return await _finish(s, args)
    if name == "state" and s.state:
        return await s.state.act(s.env, args, s.remaining()), False
    if name == "terminal":
        return await s.terminals.use(
            name=str(args.get("name") or "main"),
            input=str(args.get("input", "")),
            mode=str(args.get("mode") or "command"),
            wait_s=float(args.get("wait_s", 30)),
            interrupt=bool(args.get("interrupt")),
        ), False
    if name == "terminal_wait":
        outcome = await s.terminals.wait_events(
            args["names"], mode=args.get("mode", "any"), wait_s=args.get("wait_s", 300),
        )
        s.trace("terminal_completion_frontier", **outcome)
        return json.dumps(outcome, ensure_ascii=False), False
    if name == "python":
        return await s.repl.run(str(args.get("code", "")), wait_s=float(args.get("wait_s", 60)), interrupt=bool(args.get("interrupt"))), False
    if name == "browser" and s.browser:
        if args.get("screenshot") and not s.config.images:
            return "error: browser screenshot requires image support", False
        output = await s.browser.use(args, s.remaining())
        if s.browser.image:
            desc, url = s.browser.image
            s.pending_images.append(images.message(desc, url))
            s.images_viewed += 1
            output += f"\n[{desc}; shown below]"
        return output, False
    if name == "mcp" and getattr(s, "mcp", None):
        return await s.mcp.use(args, s.remaining()), False
    if name == "view_image":
        path = s.files.resolve(args["path"])
        other = args.get("compare")
        if other is not None:
            other_path = s.files.resolve(other["path"])
            desc, url, other_desc, other_url = await images.compare(
                s.env, path, args.get("region"), other_path, other.get("region")
            )
            s.pending_images.append(images.comparison_message(desc, url, other_desc, other_url))
            s.images_viewed += 2
            return f"[images {desc} and {other_desc}; shown below]", False
        desc, url = await images.load(s.env, path, region=args.get("region"))
        s.pending_images.append(images.message(desc, url))
        s.images_viewed += 1
        return f"[image {desc}; shown below]", False
    if name == "read_file":
        return await s.files.read(
            args["path"],
            int(args.get("start_line") or 1),
            int(args.get("num_lines") or 400),
            offset=args.get("offset", 0),
        ), False
    if name == "write_file":
        return await s.files.write(args["path"], str(args["content"])), False
    if name == "edit_file":
        return await s.files.edit(args["path"], str(args["old_str"]), str(args["new_str"]), bool(args.get("replace_all"))), False
    return f"error: unknown tool {name!r}", False


async def _read_back(s: _Session, upto: int, digest: str) -> None:
    path = s.clm.settings.mirror_path
    try:
        text = (await get_bytes(s.env, path)).decode("utf-8", "replace")
    except (
        Exception
    ) as exc:  # the model deleted or broke the file: say so, keep the context as it was
        _attach(
            s.clm.editable,
            f"[context] could not read {path} back ({type(exc).__name__}); "
            "your context is unchanged.",
        )
        s.trace("context_edit", accepted=False, reason=f"read failed: {exc}")
        return
    if hashlib.sha256(text.encode()).hexdigest() == digest:
        return
    kept = await _keep_history(s)
    accepted, receipt = s.clm.apply_edit(text, upto)
    _attach(s.clm.editable, receipt + (kept if accepted else ""))
    _restore_facts(s)
    s.trace(
        "context_edit",
        accepted=accepted,
        receipt=receipt,
        tokens=s.clm.tokens(),
        edited_text=text,
    )
    s.files.written.pop(path, None)


async def _keep_history(s: _Session) -> str:
    """Write the run's full history to the sandbox before an edit, rollback or checkpoint removes part of it.
    Returns the sentence that tells the model where it is, or a visible failure warning when it could not be written (also traced)."""
    path = s.clm.settings.history_path
    try:
        await put_bytes(s.env, s.clm.render_history().encode(), path)
    except Exception as exc:
        s.trace("history_save_error", path=path, error=f"{type(exc).__name__}: {exc}")
        return " [history save failed; a current disk copy is unavailable; use read_history to retrieve original messages]"
    return f" (original appended messages, removed ones included, are kept unchanged in {path})"


async def _fit_context(s: _Session) -> bool:
    """CLM budget step before a request: roll back, or checkpoint, until it fits; then nudge."""
    clm = s.clm
    while clm.over_limit():
        if clm.can_roll_back():
            note = clm.roll_back(await _keep_history(s))
            s.trace("context_rollback", tokens=clm.tokens(), note=note)
            _restore_facts(s)
            continue
        keep = clm.checkpoint_split()
        try:
            summary, usage = await compaction.checkpoint(
                s.provider,
                s.task,
                clm.render(keep),
                repl=bool(s.repl.pid),
                remaining_s=s.remaining,
                voice=clm.settings.notes_voice,
            )
        except Exception as exc:
            s.trace("context_checkpoint", ok=False, error=f"{type(exc).__name__}: {exc}")
            if isinstance(exc, ProviderError) and exc.deadline:  # the time limit ran out mid-checkpoint
                s.result.status = "timeout"
                return False
            # The summary is an auxiliary call: its failure must not end a working run (Mercury segment path-tracing
            # ended on one HTTP 500 at step 93). Drop the older turns unsummarised and say so; they stay in the history.
            summary, usage = compaction.unsummarised(exc, clm.settings.history_path), {}
        for key, value in usage.items():
            s.result.sub_usage[key] = s.result.sub_usage.get(key, 0) + value
        before = clm.tokens()
        clm.replace_with_checkpoint(
            summary, compaction.note(clm.settings.notes_voice) + await _keep_history(s), keep
        )
        if s.state:  # the checkpoint summary is the model's; the run state is shown again whole
            s.state.dirty = True
        # Still over: drop the oldest kept turn (with its tool results) until it fits or only the newest turn is left.
        trimmed = 0
        while clm.over_limit():
            starts = [i for i, m in enumerate(clm.editable) if i > 0 and m.get("role") == "assistant"
                      and not isinstance(m.get("content"), (facts.ManagedFactsText, WorkspaceBriefText))]
            if len(starts) < 2:
                break
            del clm.editable[1 : starts[1]]
            trimmed += 1
        if clm.over_limit():  # only the newest turn is left: the summary itself must give way, not the run
            head = clm.editable[0]["content"]
            cut = int((clm.held() - clm.settings.limit) * clm.chars_per_token * 1.2) + 200
            if cut < len(head) // 2:
                clm.editable[0]["content"] = head[: len(head) - cut] + "\n[summary cut here to fit the context]"
        s.trace(
            "context_checkpoint",
            ok=True,
            tokens_before=before,
            tokens=clm.tokens(),
            kept_messages=len(clm.editable) - 1,
            trimmed_turns=trimmed,
            summary=summary,
        )
        if s.record:  # the summary is the model's; the exact check results are restated by the harness
            note = await s.record.after_checkpoint()
            if note:
                _attach(clm.editable, note)
        _restore_facts(s)
        if clm.over_limit():
            s.result.status, s.result.error = (
                "context_error",
                "context is over its limit even after a checkpoint",
            )
            return False
    note = clm.nudge()
    if note:
        _attach(clm.editable, note)
        s.trace("context_nudge", tokens=clm.tokens(), note=note)
    return True


async def _scheduled_review(s: _Session, kind: str) -> None:
    verdict, row = await s.oversight.run(
        kind,
        s.env,
        task=s.task,
        workdir=s.workdir,
        actions=s.actions,
        written=list(s.files.written),
    )
    s.result.reviews.append(row)
    s.trace("review", answers=verdict.answers, **row)
    if verdict.status == "error":
        return
    text = (
        final_feedback(verdict, s.remaining())
        if kind == "final"
        else progress_feedback(verdict, s.elapsed(), s.timeout_s)
    )
    _attach(s.history, text)


def _appendix(config: CoreConfig) -> str:
    """Study arm (XL, 11 Nov): text placed after the task, read from a file named by the launcher. Used to carry the
    solver's own step-0 list of the points the task leaves open, written from the task text before the run starts."""
    path = getattr(config, "task_appendix_file", "")
    if not path:
        return ""
    with open(path, encoding="utf-8") as handle:
        return "\n\n" + handle.read().strip()


def _with_state(s: _Session, out: str) -> str:
    """The run state view after a change or checkpoint; otherwise one line while a check is failing."""
    if s.state.dirty:
        s.state.dirty = False
        return f"{out}\n\n{s.state.view()}"
    line = s.state.reminder()
    return f"{out}\n{line}" if line else out


async def _finish(s: _Session, args: dict[str, Any]) -> tuple[str, bool]:
    if s.config.terminal_events and s.config.role == "worker":
        pending = s.terminals.pending_names()
        s.result.extras["finish_terminal_frontier"] = pending
        if pending and s.remaining() > 15 and not s.finish_wait_returned:
            s.finish_wait_returned = True
            observed = await s.terminals.wait_events(pending[:8], mode="all", wait_s=min(300, s.remaining() - 10))
            s.trace("finish_pending_terminal_observation", **observed)
            return "Foreground terminal state at finish. Assess these results before finishing.\n" + json.dumps(observed), False
    s.result.extras["finish_args"] = args
    if s.config.role == "worker" and (settle := await finish_settle.at_finish(s)):
        return settle, False
    if s.config.open_issues and not s.result.extras.get("open_issues_held"):
        text = open_issues.hold(args, s.remaining(), s.timeout_s)
        s.trace("open_issues", issues=open_issues.issues(args), held=text is not None,
                remaining_s=round(s.remaining(), 1))
        if text:
            s.result.extras["open_issues_held"] = True
            return text, False
    if s.record:
        hold, text, _row = await s.record.at_finish()
        if hold:
            return text, False
    elif s.config.finish_hold == "neutral" and not s.held:
        s.held = True
        s.trace("finish_hold", kind="neutral", remaining_s=round(s.remaining(), 1))
        return NEUTRAL_HOLD.format(left=s.remaining()), False
    if s.state:
        held, text = await s.state.at_finish(s.env, s.remaining(), s.timeout_s)
        s.trace("state_finish", held=held, state=s.state.record())
        if held:
            return text, False
    if s.diffcheck:
        note = await s.diffcheck.at_finish()
        if note:
            return note, False
    if s.config.exec_check and not s.config.rival and "rival" not in s.result.extras:
        from . import rival

        text, row = rival.exec_at_finish(s.remaining, s.timeout_s)
        s.result.extras["rival"] = row
        s.trace("rival", handed_back=text is not None, **row)
        if text:
            return text, False
    if s.config.rival and "rival" not in s.result.extras:
        from . import rival

        text, row = await rival.at_finish(
            s.env, s.provider.complete, task=s.task, summary=str(args.get("summary", "")), workdir=s.workdir,
            control_dir=s.config.control_dir, remaining_s=s.remaining, timeout_s=s.timeout_s)
        s.result.extras["rival"] = row
        s.trace("rival", handed_back=text is not None, **row)
        if text:
            return text, False
    if s.config.card and ("rival" not in s.result.extras or s.result.extras["rival"].get("again")):
        from . import attack, card

        text, row = await (attack.at_finish(s) if s.config.card_challenge in ("attack", "observe", "forks") else card.at_finish(
            s.env, s.provider.complete, task=s.task, workdir=s.workdir, control_dir=s.config.control_dir,
            remaining_s=s.remaining, timeout_s=s.timeout_s, probe=s.config.card_probe, challenge=bool(s.config.card_challenge)))
        s.result.extras["rival"] = row
        s.trace("rival", handed_back=text is not None, **row)
        if text:
            return text, False
    if s.config.verify and "verification" not in s.result.extras:
        from . import verify

        return await verify.at_finish(s)
    if s.config.fork and "fork" not in s.result.extras:
        from . import fork

        return await fork.at_finish(s)
    skip = s.oversight.finish_gate(s.remaining())
    if skip:
        s.trace(
            "finish", summary=args.get("summary", ""), review="skipped", reason=skip
        )
        return "finished", True
    verdict, row = await s.oversight.run(
        "finish",
        s.env,
        task=s.task,
        workdir=s.workdir,
        actions=s.actions,
        written=list(s.files.written),
    )
    s.result.reviews.append(row)
    s.trace("review", summary=args.get("summary", ""), answers=verdict.answers, **row)
    return (
        f"finished\n[advisory review; does not block finish]\n{verdict.feedback()}",
        True,
    )


def _diffcheck_author(s: _Session) -> Callable[[str, float], Awaitable[Any]]:
    """The differential check's author: a fresh Core run in the check's own container (isolated mode) or, in
    component tests only, the given environment, working in the check directory (see diffcheck)."""

    async def author(brief: str, timeout_s: float, env: Environment | None = None) -> RunResult:
        from .verify import _Labelled

        env = env if env is not None else s.env
        await run(env, f"mkdir -p {shlex.quote(s.diffcheck.dir)}")
        return await run_agent(env=env, task=brief, workdir=s.diffcheck.dir,
                               provider=_Labelled(s.provider, diffcheck.AUTHOR_ROLE), timeout_s=timeout_s,
                               trace=Trace(s.trace.path.with_name(diffcheck.TRACE_FILE)),
                               config=diffcheck.author_config(s.config))

    return author


def _close(s: _Session) -> None:
    r = s.result
    r.failed_attempts = s.provider.log.totals()["all"]["failed"]
    own, roles = s.config.role, list(s.provider.log.by_role)
    r.usage = s.provider.log.usage([own])
    r.sub_usage = s.provider.log.usage(  # this run's helper calls; the verifier's are reported by verify
        [x for x in roles if x.startswith(own + ".")]
        if own != "worker"
        else [x for x in roles if x != own and not x.startswith((VERIFIER_ROLE, diffcheck.AUTHOR_ROLE))]
    )
    statuses: dict[str, int] = {}
    for row in s.provider.failure_log:
        key = str(row.get("status") or row.get("error"))
        statuses[key] = statuses.get(key, 0) + 1
    r.extras = {
        **r.extras,
        "provider_failures_by_status": statuses,
        "provider_retry_wait_s": round(
            sum(float(x.get("wait_s") or 0) for x in s.provider.failure_log), 1
        ),
        "images_viewed": s.images_viewed,
        "python": s.repl.python,
        "python_cells": s.repl.seq,
        "llm_calls": s.repl.llm_calls,
        "llm_errors": s.repl.llm_errors,
        "clm": s.clm.stats.__dict__ if s.clm else None,
        "model_calls": s.provider.log.totals(),
        "record": s.record.summary() if s.record else None,
        "diffcheck": {**s.diffcheck.summary(), "usage": s.provider.log.usage(
            [x for x in roles if x.startswith(diffcheck.AUTHOR_ROLE)])} if s.diffcheck else None,
        "finish_hold": s.config.finish_hold,
        "switches": {"finish_settle": s.config.finish_settle, "completion_notices": s.config.completion_notices,
                     "env_map": s.config.env_map},
    }
    s.trace(
        "end",
        status=r.status,
        error=r.error,
        steps=r.steps,
        usage=r.usage,
        sub_usage=r.sub_usage,
        elapsed_s=round(s.elapsed(), 1),
        **r.extras,
    )


def default_review_call(transport: Transport, request: dict) -> Awaitable[Any]:
    return asyncio.to_thread(transport, request)
