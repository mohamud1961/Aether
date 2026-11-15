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
    if not s.config.rehydrate or s.clm is None:
        return
    from . import rehydrate

    note, row = await rehydrate.note(s.env, list(s.files.written))
    if note:
        _attach(s.clm.editable, note)
    s.trace("rehydrate", cause=cause, **row)


async def _fit_context(s: _Session) -> bool:
    """CLM budget step before a request: roll back, or checkpoint, until it fits; then nudge."""
    clm = s.clm
    if s.rehydrate_due:
        s.rehydrate_due = False
        await _rehydrate(s, "native_compaction")
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
        await _rehydrate(s, "checkpoint")
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
