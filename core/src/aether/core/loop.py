"""The Aether Core agent loop: model turn -> tools -> results, until finish or time.

Everything the model does is recorded in full (reasoning, calls, results,
timings, token usage, every failed provider attempt) to ``core_trace.jsonl``.
What the model sees is either the ``project`` view of that history (C1) or a
context the model manages itself under a token budget (``clm``; see ``clm``).
"""

from __future__ import annotations

import asyncio
import math
import shlex
import time
from typing import Any, Awaitable, Callable

from . import diffcheck, facts, facts_projection, facts_pull, finish_report, image_region, images, intent, runstate
from . import receipt as finish_receipt
from .clm import ClmContext
from .context import project, size_chars
from .env import Environment
from .facts_workspace import WorkspaceBriefText
from .loop_records import RunResult, Trace  # re-exported for existing callers
from .oversight import ReviewPlan
from .provider import ChatProvider, ProviderError
from .review import Transport
from . import agenda, browser, open_issues, operations, step0, workspace_brief
from .tools import system_prompt, tools
from .loop_config import AFTER_CUT, AFTER_CUT_MAX_TOKENS, CONTEXT_MODES, MAX_OUTPUT_TOKENS, VERIFIER_ROLE, CoreConfig  # noqa: F401
from .loop_session import _Session, _append, _publish_facts
from .loop_calls import _run_calls
from .loop_context import _fit_context
from .loop_finish import _appendix, _scheduled_review

STOP_MARGIN_S = 15.0


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
    if getattr(provider, "native_compaction", None) is not None and config.context != "clm":
        raise ValueError("native compaction requires the CLM context")
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
        STOP_MARGIN_S,
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
            if config.outside_witness and config.role == "worker":
                from . import outside_witness

                witnessed, row = await outside_witness.take(s.env, workdir, config.control_dir, config.outside_roots)
                s.witness = outside_witness.Witness(s.env, workdir, config.control_dir, config.outside_roots)
                trace("outside_witness", **row)
                start_note = "\n".join(x for x in (start_note, witnessed) if x)
            if config.env_brief and config.role == "worker":
                from . import env_brief

                brief, row = await env_brief.take(s.env, workdir)
                trace("env_brief", **row)
                start_note = "\n".join(x for x in (brief, start_note) if x)
            if config.env_map and config.role == "worker":
                from . import env_map

                mapped, row = await env_map.take(s.env, workdir, task)
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
            if config.terminal_events:
                # Only Core result tokens in the resumed history acknowledge a receipt.
                history = resume.raw if isinstance(resume, ClmContext) else (resume or [])
                deliveries = {m[operations.DELIVERY_FIELD] for m in history
                              if m.get("role") == "tool" and m.get(operations.DELIVERY_FIELD)}
                s.terminals.conversation, s.terminals.delivery_tag = deliveries, s.delivery_tag
                s.repl.conversation, s.repl.delivery_tag = deliveries, s.delivery_tag
                if s.browser:  # A11/A13: adopt the task's sidecar and track browser result delivery
                    s.browser.adopt, s.browser.conversation, s.browser.delivery_tag = True, deliveries, s.delivery_tag
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

                s.mcp = mcp.Mcp(s.env, config.control_dir, list(config.mcp_servers), adopt=config.terminal_events,
                                idempotency=config.mcp_idempotency)
                if config.terminal_events:
                    s.mcp.conversation, s.mcp.delivery_tag = s.terminals.conversation, s.delivery_tag
                s.tools = [*s.tools, mcp.tool(list(config.mcp_servers))]
            if config.workspace_search and config.role == "worker":
                from . import workspace_search

                s.tools.append(workspace_search.TOOL)
            if config.evidence_presentation == "path_lookup" and config.role == "worker":
                from .evidence_context import LOCATE_TOOL

                s.tools.append(LOCATE_TOOL)
            if see and config.context == "clm" and config.clm.attest_original_history:
                s.tools = images.with_history_recall(s.tools)
            if config.image_region and see:
                s.tools = image_region.with_region(s.tools)
            if config.image_compare and see:
                s.tools = image_region.with_compare(s.tools)
            if config.intent:
                s.tools = intent.with_intent(s.tools)
            if config.open_issues:
                s.tools = open_issues.with_field(s.tools)
            s.tools = browser.with_tool(s.tools, config.browser_session) if config.browser else s.tools
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
        if s.config.evidence_presentation == "history_index":
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
            response_id=turn.response_id or None,  # H1: joins this turn to its provider receipt and spend row
            effort=AFTER_CUT["reasoning_effort"] if cut and s.provider.takes_effort else (
                s.config.image_effort if look else None),
        )
        cut = turn.finish_reason == "length" and not turn.tool_calls
        assistant = turn.assistant_message()
        _append(s, assistant)
        if assistant.get("compaction"):
            s.trace("native_compaction", items=len(assistant["compaction"]), usage=turn.usage)
            s.rehydrate_due = True
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
                     "env_map": s.config.env_map, "terminal_result_delivery": s.config.terminal_result_delivery,
                     "finish_facts": s.config.finish_facts, "outside_witness": s.config.outside_witness,
                     "mcp_idempotency": s.config.mcp_idempotency, "browser_page_facts": s.config.browser_page_facts},
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
