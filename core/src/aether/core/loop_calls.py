"""One turn's tool calls: dispatch, environment checks, saving long results, read-back (split from loop.py)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from . import facts, finish_report, images
from .context import SAVE_OVER, SAVED_NOTE, saved_path
from .env import get_bytes, put_bytes, run
from .provider import parse_arguments
from . import completion_notice, operations, stated_use
from .tools import validate_call
from .loop_context import _keep_history
from .loop_finish import _finish, _with_state
from .loop_session import _Session, _action_view, _append, _attach, _publish_facts, _restore_facts


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
            started = time.monotonic()
            in_flight = peak = 0

            async def read_one(item):
                nonlocal in_flight, peak
                async with gate:
                    in_flight += 1
                    peak = max(peak, in_flight)
                    try:
                        return await _invoke(s, item)
                    finally:
                        in_flight -= 1

            results = await asyncio.gather(
                *(read_one(item) for item in calls[index:end])
            )
            if len(results) > 1:
                s.trace("parallel_read_group", calls=len(results), max_in_flight=peak,
                        duration_s=round(time.monotonic() - started, 3))
            buffered.update(zip(range(index, end), results))
        s.operation_delivery = ""
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
        if not finished and (held_finish or index + 1 == len(calls)):
            if getattr(s.config, "completion_notices", False) or getattr(s.config, "terminal_result_delivery", False):
                out += await completion_notice.before_model(s)
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
        message = {"role": "tool", "tool_call_id": call["id"], "content": f"{out}\n{s.clock()}{reshow}"}
        if s.operation_delivery:
            message[operations.DELIVERY_FIELD] = s.operation_delivery
        _append(s, message)
        if s.operation_delivery and s.terminals.conversation is not None:
            s.terminals.conversation.add(s.operation_delivery)
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
        if s.clm and s.clm.settings.attest_original_history:
            for i, message in enumerate(s.pending_images, len(s.clm.raw)):
                message.setdefault(images.HISTORY_FIELD, i)
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
        s.operation_delivery = ""
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
    if name == "find_history" and s.clm:
        from .evidence_context import locate_path

        return locate_path(s.clm, args["path"]), False
    if name == "search_workspace":
        from . import workspace_search

        return await workspace_search.search(s.env, s.workdir, s.config.control_dir, args), False
    if name == "read_history" and s.clm:
        if args.get("show_image"):
            if "offset" in args or "limit" in args:
                raise ValueError("image recall does not take a text offset or limit")
            message_id = args["message_id"]
            s.pending_images.append(s.clm.history_image(message_id))
            s.images_viewed += 1
            return f"[original image observation from history MSG {message_id}; shown below]", False
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
            quiet_s=args.get("quiet_s"),
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
    if name in ("write_file", "edit_file"):
        kept = await s.witness.before_write(str(args["path"])) if s.witness else ""
        if kept:
            s.trace("outside_witness", path=args["path"], state=s.witness.seen.get(args["path"]))
        if name == "write_file":
            out = await s.files.write(args["path"], str(args["content"]))
        else:
            out = await s.files.edit(args["path"], str(args["old_str"]), str(args["new_str"]), bool(args.get("replace_all")))
        return (f"{out}\n{kept}" if kept else out), False
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
