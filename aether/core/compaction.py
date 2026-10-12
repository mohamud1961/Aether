"""Structured context checkpoint, written when the model has not condensed its own context.

The prompts are Prime Agent's compaction prompts (MIT licence, Copyright (c) 2025-2026
Prime Intellect Ltd.), taken verbatim from
PrimeIntellect-ai/prime-agent@3e0893260eefdab3c8391dab9b7386d6cc864a62,
``crates/pa-core/src/session_engine/compaction{,_utils}.rs``.

Used only after the CLM rollback-and-retry budget is spent; every use is traced
and counted in the run record.
"""
from __future__ import annotations

from typing import Any, Callable

from .provider import ChatProvider

SUMMARIZATION_SYSTEM_PROMPT = (
    "You are a context summarization assistant. Your task is to read a conversation between a user and an AI "
    "coding assistant, then produce a structured summary following the exact format specified.\n\nDo NOT "
    "continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured "
    "summary.")

SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context \
checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the principal trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages."""

KERNEL_PERSIST_SUMMARY_NOTE = (
    "Note: the Python kernel keeps running after this summary — every Python variable, import, and helper you "
    "defined stays available. The cells that defined them won't appear above, so record in the summary any names "
    "worth remembering so you reuse them instead of redefining them.")

CHECKPOINT_NOTE = ("[context checkpoint] Your earlier turns were replaced by this summary because the context "
                   "reached its limit; your most recent turns follow it unchanged. Terminal logs and files on disk "
                   "are unchanged.")
# The output cap includes reasoning: at 4096 GLM's reasoning used it all and two D1 rows ended with
# "checkpoint call returned no text" (render-scene at 288 s of 1800 s).
MAX_SUMMARY_TOKENS = 16_384
# Summarizing is extraction, not problem solving: at the run's high effort four checkpoints took 284 s of a
# 1774 s row (D1 render-reverse). Low effort first; the run's own settings if that returns no text.
FIRST_OVERRIDES = {"reasoning_effort": "low"}


async def checkpoint(provider: ChatProvider, task: str, transcript: str, *, repl: bool,
                     remaining_s: Callable[[], float]) -> tuple[str, dict[str, Any]]:
    """Return (summary, usage). Raises on failure with the reason; the caller records it.

    Runs at low reasoning effort; a call that returns no summary text is retried once at the run's own."""
    prompt = SUMMARIZATION_PROMPT + ("\n\n" + KERNEL_PERSIST_SUMMARY_NOTE if repl else "")
    messages = [
        {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"<task>\n{task}\n</task>\n\n<conversation>\n{transcript}\n</conversation>"},
        {"role": "user", "content": prompt},
    ]
    usage: dict[str, Any] = {}
    empties = []
    for overrides in (FIRST_OVERRIDES, None):
        turn = await provider.complete(messages, None, max_tokens=MAX_SUMMARY_TOKENS, remaining_s=remaining_s,
                                       overrides=overrides)
        for key, value in turn.usage.items():
            usage[key] = usage.get(key, 0) + value
        summary = turn.content.strip()
        if summary:
            return summary, usage
        empties.append(f"finish_reason={turn.finish_reason} output={turn.usage.get('output')} "
                       f"reasoning={turn.usage.get('reasoning')}")
    raise ValueError("checkpoint call returned no text (" + "; ".join(empties) + ")")
