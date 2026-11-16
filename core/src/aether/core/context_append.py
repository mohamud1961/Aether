"""Append-only context (opt-in, ``context="append"``): the model never edits its history and is never nudged.

The request is the system prompt and task, then (after the first cut) one summary message, then every message since
the cut, unchanged and in order. Between cuts each request only grows at its end, so the provider's prompt cache keeps
the whole prefix. When the estimated request passes the policy's threshold, the older part is summarised once and
the newest ``keep_recent_tokens`` stay verbatim. This is how Pi, Unreal and Prime manage context near the window; the
$0 render (CONTEXT_APPEND_ONLY_20261115) found it cost-neutral or cheaper than CLM up to ~128K on Core's own runs.

A policy is data: when to cut, how much to keep, how the older part is summarised, and how the summary is put back.
Exact copies of other agents are policies in ``context_append_policies``; nothing in the loop branches on a name.
The full history is never discarded: ``s.messages`` keeps every message, so nothing is lost to the run record.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .context import size_chars

CHARS_PER_TOKEN = 4.0
Summarise = Callable[..., Awaitable[tuple[str, dict[str, Any]]]]


@dataclass(frozen=True)
class AppendPolicy:
    name: str
    threshold: Callable[[int], int]  # window tokens -> request tokens above which the older part is summarised
    keep_recent_tokens: int  # newest turns kept verbatim after a cut (at least the newest whole turn)
    summarise: Summarise  # (provider, task, older messages, previous summary, remaining_s=...) -> (text, usage)
    insert: Callable[[str], dict[str, Any]]  # summary text -> the message put back after the task
    source: str  # where the rule comes from (pinned commit for an exact copy)
    index: bool = False  # at each cut, save every cut-away tool result as a file and list them after the summary


def transcript(messages: list[dict[str, Any]]) -> str:
    """Plain rendering of messages for a summary call: role, text, tool calls and tool results, in order."""
    out = []
    for m in messages:
        role, content = m.get("role", "?"), m.get("content")
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False) if content else ""
        calls = [f"{(c.get('function') or {}).get('name')}({(c.get('function') or {}).get('arguments')})"
                 for c in m.get("tool_calls") or ()]
        out.append(f"[{role}]" + (f" {text}" if text else "") + ("\n" + "\n".join(calls) if calls else ""))
    return "\n\n".join(out)


class AppendContext:
    def __init__(self, policy: AppendPolicy, window_tokens: int, pinned: int = 2):
        self.policy, self.window, self.pinned = policy, window_tokens, pinned
        self.limit = policy.threshold(window_tokens)
        if not 0 < policy.keep_recent_tokens < self.limit <= window_tokens:
            raise ValueError(f"append policy {policy.name}: need 0 < keep {policy.keep_recent_tokens} < "
                             f"threshold {self.limit} <= window {window_tokens}")
        self.kept = pinned  # index of the first message after the cut
        self.summary: str | None = None
        self.chars_per_token = CHARS_PER_TOKEN
        self.cuts = 0
        self.summary_usage: dict[str, int] = {}
        self.index_lines: list[str] = []  # policy.index: one exact line per saved tool result, across all cuts

    def request(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        head = list(messages[: self.pinned])
        if self.summary is not None:
            index = ("\n\nEarlier tool results, saved in full:\n" + "\n".join(self.index_lines)
                     if self.index_lines else "")
            head.append(self.policy.insert(self.summary + index))
        return head + list(messages[self.kept :])

    def tokens(self, messages: list[dict[str, Any]]) -> int:
        return int(size_chars(self.request(messages)) / self.chars_per_token)

    def calibrate(self, request_chars: int, input_tokens: int) -> None:
        if request_chars > 0 and input_tokens > 0:  # same guard as CLM: only a plausible ratio is adopted
            ratio = request_chars / input_tokens
            if 1.5 <= ratio <= 12:
                self.chars_per_token = ratio

    def _boundary(self, messages: list[dict[str, Any]]) -> int | None:
        """Latest assistant-turn start that leaves at least ``keep_recent_tokens`` after it; None if no older turn."""
        starts = [i for i in range(self.kept, len(messages)) if messages[i].get("role") == "assistant"]
        if len(starts) < 2:
            return None
        for i in reversed(starts[1:]):
            if size_chars(messages[i:]) / self.chars_per_token >= self.policy.keep_recent_tokens:
                return i
        return starts[1]  # the recent part alone is under the keep size: cut everything but the newest turns

    async def _save_index(self, older: list[dict[str, Any]], first: int, save: Callable[..., Awaitable[None]],
                          save_dir: str) -> None:
        """Write each cut-away tool result to ``save_dir`` and add one line per result: what call made it, where it
        is, how big. Facts only; the files are the exact text the model was shown."""
        calls = {c.get("id"): c.get("function") or {} for m in older if m.get("role") == "assistant"
                 for c in m.get("tool_calls") or ()}
        for offset, m in enumerate(older):
            if m.get("role") != "tool":
                continue
            body = m.get("content")
            data = (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode()
            path = f"{save_dir}/obs_{first + offset}.txt"
            await save(path, data)
            fn = calls.get(m.get("tool_call_id"), {})
            args = str(fn.get("arguments", ""))
            args = args if len(args) <= 160 else args[:157] + "..."
            self.index_lines.append(f"- {fn.get('name', 'tool')}({args}) -> {path} ({len(data):,} bytes)")

    async def fit(self, provider: Any, task: str, messages: list[dict[str, Any]], *,
                  remaining_s: Callable[[], float], trace: Callable[..., None],
                  save: Callable[..., Awaitable[None]] | None = None, save_dir: str = "") -> dict[str, Any]:
        """Summarise once if the next request is over the threshold; returns the summary call's usage. Raises on a failed summary (the caller ends
        the run honestly); a cut that cannot bring the request under the limit is traced, not hidden."""
        before = self.tokens(messages)
        if before <= self.limit:
            return {}
        cut = self._boundary(messages)
        if cut is None:
            trace("context_append_cut", ok=False, tokens=before, limit=self.limit, reason="no older turn to cut")
            return {}
        text, usage = await self.policy.summarise(provider, task, messages[self.kept : cut], self.summary,
                                                  remaining_s=remaining_s)
        for key, value in usage.items():
            self.summary_usage[key] = self.summary_usage.get(key, 0) + value
        if self.policy.index:
            if save is None:
                raise ValueError(f"append policy {self.policy.name} saves an index but no writer was given")
            await self._save_index(messages[self.kept : cut], self.kept, save, save_dir)
        self.summary, self.kept, self.cuts = text, cut, self.cuts + 1
        trace("context_append_cut", ok=True, policy=self.policy.name, tokens_before=before,
              tokens=self.tokens(messages), limit=self.limit, kept_from=cut, summary_chars=len(text))
        return usage
