"""Append-context policies (data, selected by name; see context_append).

``core64`` / ``core128``: append-only history with Core's own checkpoint summary (compaction.checkpoint, itself
derived from Prime Agent's prompt) at a fixed request size. These are the B64/B128 arms of budget test B1.
Exact copies of other agents' rules are added here with their source commit; their prompts are verbatim.
"""

from __future__ import annotations

from typing import Any, Callable

from . import compaction
from .context_append import AppendPolicy, transcript


async def _core_summary(provider: Any, task: str, older: list[dict[str, Any]], previous: str | None, *,
                        remaining_s: Callable[[], float]) -> tuple[str, dict[str, Any]]:
    text = transcript(older)
    if previous is not None:  # the older part already began with a summary: carry it into the new one
        text = f"[earlier summary]\n{previous}\n\n{text}"
    return await compaction.checkpoint(provider, task, text, repl=False, remaining_s=remaining_s)


def _core_insert(summary: str) -> dict[str, Any]:
    return {"role": "user", "content": f"{compaction.CHECKPOINT_NOTE}\n\n{summary}"}


def _fixed(tokens: int) -> Callable[[int], int]:
    return lambda window: min(tokens, window)


POLICIES: dict[str, AppendPolicy] = {
    "core64": AppendPolicy("core64", _fixed(64_000), 20_000, _core_summary, _core_insert, "Core B1 arm"),
    "core128": AppendPolicy("core128", _fixed(128_000), 20_000, _core_summary, _core_insert, "Core B1 arm"),
    # Evidence-aware hybrid (E19): a smaller window, and every cut-away tool result saved as a file and indexed.
    "core32idx": AppendPolicy("core32idx", _fixed(32_000), 12_000, _core_summary, _core_insert,
                              "E19 hybrid", index=True),
    # Lossless memory hierarchy (16 Nov): append only; one rare large cut near the provider's window; every cut-away
    # tool result saved as a file and listed; read_history and the files stay the source of truth.
    "lossless": AppendPolicy("lossless", lambda window: int(window * 0.85), 40_000, _core_summary, _core_insert,
                             "16 Nov lossless hierarchy", index=True),
}
