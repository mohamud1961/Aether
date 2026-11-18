"""Keeping the request inside the context budget: checkpoints, history, rehydration (split from loop.py)."""

from __future__ import annotations


from . import compaction, facts
from .env import put_bytes
from .facts_workspace import WorkspaceBriefText
from .provider import ProviderError
from .loop_session import _Session, _attach, _restore_facts


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


async def _rehydrate(s: _Session, cause: str) -> None:
    """E18 K2: after the context is shortened, the files this run changed are shown again as they are now."""
    clm = s.clm
    if not s.config.rehydrate or clm is None:
        return
    from . import rehydrate

    if s.files.written and clm.held() >= clm.settings.limit:
        s.trace("rehydrate", cause=cause, shown=0, omitted="context_budget")
        return
    note, row = await rehydrate.note(s.env, list(s.files.written))
    if note:
        tail = clm.editable[-1] if clm.editable and clm.editable[-1].get("role") == "tool" else None
        original = tail["content"] if tail is not None else None
        _attach(clm.editable, note)
        if clm.over_limit():
            if tail is not None:
                tail["content"] = original
            else:
                clm.editable.pop()
            row.update(shown=0, omitted="context_budget")
    s.trace("rehydrate", cause=cause, **row)


async def _cut_window(s: _Session) -> bool:
    """Remove whole oldest turns without inventing a summary; original messages remain retrievable."""
    clm = s.clm
    before = clm.tokens()
    history = await _keep_history(s)
    removed = 0
    if getattr(clm.settings, "image_age_at_cut", False):
        s.trace("context_images_aged", cause="window_cut", hidden=clm.age_images())

    def discard_oldest() -> bool:
        nonlocal removed
        starts = [i for i, message in enumerate(clm.editable)
                  if message.get("role") == "assistant"
                  and not isinstance(message.get("content"), (facts.ManagedFactsText, WorkspaceBriefText))]
        if len(starts) < 2:
            return False
        del clm.editable[:starts[1]]
        removed += 1
        return True

    target = clm.settings.limit - clm.settings.window_cut_margin_tokens
    while clm.held() > target:
        if discard_oldest():
            continue
        if clm.over_limit():
            s.result.status, s.result.error = "context_error", "newest complete turn exceeds the context limit"
            s.trace("context_window_cut", ok=False, removed_turns=removed, error=s.result.error)
            return False
        break  # the margin is a target: nothing older is left, and the context is within its limit
    _attach(clm.editable, "[context window] Older turns were removed without a summary." + history)
    while clm.over_limit():
        if not discard_oldest():
            s.result.status, s.result.error = "context_error", "newest complete turn and history notice exceed the context limit"
            s.trace("context_window_cut", ok=False, removed_turns=removed, error=s.result.error)
            return False
    clm.stats.checkpoints += 1
    clm._rearm()
    if s.state:
        s.state.dirty = True
    if s.record:
        note = await s.record.after_checkpoint()
        if note:
            _attach(clm.editable, note)
    _restore_facts(s)
    await _rehydrate(s, "window_cut")
    if clm.over_limit():
        s.result.status, s.result.error = "context_error", "context exceeds the limit after restoring state"
        s.trace("context_window_cut", ok=False, removed_turns=removed, error=s.result.error)
        return False
    s.trace("context_window_cut", ok=True, tokens_before=before, tokens=clm.tokens(), removed_turns=removed)
    return True


def _final_turn(s: _Session) -> bool:
    """checkpoint_policy "stop" (meta profile): over the limit with no rollback left, the model gets one final turn to
    condense; still over at the next request, the run stops as a context error. No summary is ever written."""
    clm = s.clm
    if "context_final_turn" in s.result.extras:
        s.trace("context_final_turn", phase="stop", tokens=clm.held(), limit=clm.settings.limit)
        s.result.status, s.result.error = "context_error", "context is over its limit after its final turn"
        return False
    s.result.extras["context_final_turn"] = s.result.steps
    s.trace("context_final_turn", phase="given", tokens=clm.held(), limit=clm.settings.limit)
    _attach(clm.editable, f"[context limit] {clm.held()} of {clm.settings.limit} tokens used and no turn is left to "
            f"roll back. Condense {clm.settings.mirror_path} in this turn: if the context is still over its limit at "
            "the next turn, the run stops.")
    return True


async def _fit_context(s: _Session) -> bool:
    """CLM budget step before a request: roll back, or checkpoint, until it fits; then nudge."""
    clm = s.clm
    if s.rehydrate_due:
        s.rehydrate_due = False
        await _rehydrate(s, "native_compaction")
    if not clm.over_limit():
        s.result.extras.pop("context_final_turn", None)  # the model fitted its context again
    while clm.over_limit():
        if clm.can_roll_back():
            note = clm.roll_back(await _keep_history(s))
            margin = clm.settings.rollback_margin_tokens  # meta: roll back until this many tokens are free
            while margin and clm.held() > clm.settings.limit - margin and clm.can_roll_back():
                note = clm.roll_back(await _keep_history(s))
            s.trace("context_rollback", tokens=clm.tokens(), note=note)
            _restore_facts(s)
            continue
        if clm.settings.checkpoint_policy == "stop":
            if not _final_turn(s):
                return False
            break
        if clm.settings.checkpoint_policy == "window":
            if not await _cut_window(s):
                return False
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
        if getattr(clm.settings, "image_age_at_cut", False):
            s.trace("context_images_aged", cause="checkpoint", hidden=clm.age_images())
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
        await _rehydrate(s, "checkpoint")
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


async def _fit_append(s: _Session) -> bool:
    """Append-only context: summarise the older part once if the next request is over the policy's threshold.
    A failed summary ends the run as a context error with its reason (no silent unsummarised drop)."""
    try:
        usage = await s.append_ctx.fit(
            s.provider, s.task, s.messages, remaining_s=s.remaining, trace=s.trace,
            save=lambda path, data: put_bytes(s.env, data, path), save_dir=f"{s.config.control_dir}/evidence")
    except Exception as exc:
        s.trace("context_append_cut", ok=False, error=f"{type(exc).__name__}: {exc}")
        if isinstance(exc, ProviderError) and exc.deadline:
            s.result.status = "timeout"
        else:
            stage = "index save" if type(exc).__name__ == "IndexSaveError" else "summary"
            s.result.status, s.result.error = "context_error", f"append {stage} failed: {type(exc).__name__}: {exc}"
        return False
    for key, value in usage.items():
        s.result.sub_usage[key] = s.result.sub_usage.get(key, 0) + value
    return True


def calibrate(ctx, request_chars: int, turn) -> None:
    """Correct the chars-per-token estimate from the provider's prompt count. A turn that ran hosted searches bills
    their results as input although they are never replayed, so its count says nothing about the request: G10c fin
    (17 Nov) recalibrated on 81 such turns and checkpointed 43 times, each right after a search turn."""
    if ctx is not None and not turn.web_searches:
        ctx.calibrate(request_chars, turn.usage.get("input", 0))
