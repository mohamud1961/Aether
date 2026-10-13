"""Model-managed context, following the published CLM method.

Source: Meta's context-language-models ``clm_harness`` README ("How a turn
works"). Implemented clean-room from that description; no CLM code is copied
(its licence is CC BY-NC 4.0).

- The system prompt and the task are pinned. Everything after them is the
  model's *editable* context, mirrored to a file in the sandbox as one
  ``[[CTX_TURN i role=...]]`` block per message.
- The model condenses its own context by editing that file with its ordinary
  tools. An edited file is parsed back into messages (assistant text stays
  assistant; every other role becomes user text) and accepted by a *fit* edit
  gate: the result must fit the limit.
- Token budget with one-shot nudges at 25/50/75% (re-armed after the context
  shrinks) and an adaptive urgent nudge near the limit.
- Above the limit (budget minus reserve) CLM rolls the newest turn back. Here
  ``max_rollbacks`` defaults to 0: tool outputs are capped at ~11 KB (~3.5k
  tokens), so one turn cannot overflow by itself, and a rollback would only
  discard real output. Over the limit, the caller writes Prime Agent's
  structured checkpoint of the older turns and keeps the newest
  ``keep_recent_tokens`` verbatim (see ``compaction``).

Settings and their evidence (C1, 12 Oct): interpreter-build requests averaged
~21k tokens and peaked near 60k; the route allows 300K tokens/minute at ~12
turns/minute, so a 32k budget (the CLM default) keeps a row under the limit.
Nudges start at 50%: at 25% the pinned prompt alone nearly triggers them.
"""

from __future__ import annotations

from copy import deepcopy

from dataclasses import dataclass, field
import json
import re
from typing import Any

from . import images

MIRROR_PATH = "/tmp/.aether/ctx/LIVE_CTX.txt"
HISTORY_PATH = "/tmp/.aether/ctx/HISTORY.txt"
TURN_RE = re.compile(r"^\[\[CTX_TURN (\d+) role=([a-z_]+)\]\]$", re.M)
CHARS_PER_TOKEN = 3.0  # initial estimate; recalibrated from the provider's own counts
TOOLS_OVERHEAD_TOKENS = 1_500
URGENT_EVERY_TURNS = 3  # C2 row 1: the urgent nudge fired on 10 consecutive turns; the checkpoint backs it up


@dataclass
class ClmSettings:
    budget_tokens: int = 32_000
    reserve_tokens: int = 2_048
    nudge_ratios: tuple[float, ...] = (0.5, 0.75)
    max_rollbacks: int = 0
    keep_recent_tokens: int = 8_000
    mirror_path: str = MIRROR_PATH
    history_path: str = HISTORY_PATH
    # Two different numbers (O1, B1 dna ep 2). ``budget_tokens`` governs the editable context the model manages
    # (``held``); the newest turn's replayed reasoning is outside it by design, so a whole request can exceed it.
    # ``request_limit_tokens`` is the provider's limit for one request's input plus its reply. None means unknown:
    # recorded as unknown, never assumed.
    request_limit_tokens: int | None = None

    @property
    def limit(self) -> int:
        return self.budget_tokens - self.reserve_tokens

    def check_request_limit(self, max_output_tokens: int) -> None:
        """Fail at configuration, not mid-run: the largest request the budget allows (the editable budget, plus
        one replayed reasoning of at most a full reply, plus the next reply) must fit the provider's limit."""
        if self.request_limit_tokens is None:
            return
        worst = self.budget_tokens + 2 * max_output_tokens
        if worst > self.request_limit_tokens:
            raise ValueError(
                f"CLM budget {self.budget_tokens} + 2 x {max_output_tokens} output tokens = {worst} exceeds the "
                f"provider request limit {self.request_limit_tokens}"
            )


@dataclass
class ClmStats:
    nudges: int = 0
    urgent_nudges: int = 0
    edits_accepted: int = 0
    edits_rejected: int = 0
    rollbacks: int = 0
    checkpoints: int = 0
    max_tokens_seen: int = 0


def _call_text(call: dict[str, Any]) -> str:
    fn = call.get("function") or {}
    return f"[tool_call {fn.get('name', '')}] {fn.get('arguments', '')}"


def render_message(msg: dict[str, Any]) -> str:
    parts = [images.text_of(msg.get("content"))]
    parts += [_call_text(c) for c in msg.get("tool_calls") or ()]
    return "\n".join(p for p in parts if p)


@dataclass
class ClmContext:
    pinned: list[dict[str, Any]]
    settings: ClmSettings = field(default_factory=ClmSettings)
    editable: list[dict[str, Any]] = field(default_factory=list)
    raw: list[dict[str, Any]] = field(
        default_factory=list
    )  # every appended message as shown; edits never touch it
    stats: ClmStats = field(default_factory=ClmStats)
    chars_per_token: float = CHARS_PER_TOKEN
    _armed: set[float] = field(default_factory=set)
    _rollbacks_in_episode: int = 0
    _recent_outputs: list[int] = field(default_factory=list)
    _turn: int = 0
    _last_urgent: int = -URGENT_EVERY_TURNS
    _reasoning: tuple[int, int | None] = (
        0,
        None,
    )  # None means provider usage was not reported

    def __post_init__(self) -> None:
        self._armed = set(self.settings.nudge_ratios)

    # ----- the request ---------------------------------------------------------------------------
    def request(self) -> list[dict[str, Any]]:
        """Pinned + editable; reasoning is replayed for the newest assistant turn only."""
        last = max(
            (i for i, m in enumerate(self.editable) if m.get("role") == "assistant"),
            default=-1,
        )
        out = list(self.pinned)
        for i, msg in enumerate(self.editable):
            if i != last and "reasoning_content" in msg:
                msg = {k: v for k, v in msg.items() if k != "reasoning_content"}
            out.append(msg)
        return images.limit(out)

    def tokens(self, messages: list[dict[str, Any]] | None = None) -> int:
        chars = images.size_chars(
            self.request() if messages is None else images.limit(messages)
        )
        r_chars, r_tokens = self._replayed_reasoning() if messages is None else (0, 0)
        return (
            int((chars - r_chars) / self.chars_per_token)
            + r_tokens
            + TOOLS_OVERHEAD_TOKENS
        )

    def held(self) -> int:
        """Tokens the budget governs: the request minus the newest turn's replayed reasoning. That reasoning is the
        model's live working memory, sent once and dropped after its next turn; the model cannot condense it and a
        checkpoint never sees it. Counting it let a single long thought trigger a checkpoint that discarded it (D1
        circuit-math: three 32k-token thoughts each summarised away, about 1100 s of reasoning redone)."""
        return self.tokens() - self._replayed_reasoning()[1]

    def note_reasoning(
        self, message: dict[str, Any], reasoning_tokens: int | None
    ) -> None:
        """Record the provider's reasoning-token count for an assistant message just appended.

        The newest turn's reasoning is replayed in the next request and tokenizes far more densely than tool
        output: in D1 a 32k-token reasoning turn was estimated at 27.7k and counted at 38.2k (budget 32k)."""
        self._reasoning = (
            id(message),
            None if reasoning_tokens is None else int(reasoning_tokens),
        )

    def _replayed_reasoning(self) -> tuple[int, int]:
        """(JSON chars, provider tokens) of the reasoning the next request replays, when the count is known."""
        last = next(
            (m for m in reversed(self.editable) if m.get("role") == "assistant"), None
        )
        if (
            last is None
            or id(last) != self._reasoning[0]
            or not last.get("reasoning_content")
        ):
            return 0, 0
        chars = len(json.dumps(last["reasoning_content"], ensure_ascii=False))
        tokens = self._reasoning[1]
        return chars, int(chars / self.chars_per_token) if tokens is None else tokens

    def calibrate(self, request_chars: int, input_tokens: int) -> None:
        """Use the provider's real prompt-token count to correct the chars-per-token estimate
        (the replayed reasoning, whose token count is known exactly, is left out of the ratio)."""
        r_chars, r_tokens = self._replayed_reasoning()
        if self._reasoning[1] is None:
            r_chars, r_tokens = (
                0,
                0,
            )  # an estimate must not masquerade as reported usage in calibration
        request_chars, input_tokens = request_chars - r_chars, input_tokens - r_tokens
        if input_tokens > TOOLS_OVERHEAD_TOKENS * 2 and request_chars > 0:
            self.chars_per_token = max(
                1.5, min(6.0, request_chars / (input_tokens - TOOLS_OVERHEAD_TOKENS))
            )

    def append(self, *messages: dict[str, Any]) -> None:
        self.editable.extend(messages)
        self.raw.extend(deepcopy(messages))
        for m in messages:
            if m.get("role") == "tool":
                self._recent_outputs = (
                    self._recent_outputs + [len(str(m.get("content") or ""))]
                )[-3:]

    # ----- budget: nudges and rollback -----------------------------------------------------------
    def nudge(self) -> str:
        """Nudge text to show the model now (may be empty). Call once per turn, before the request."""
        used = self.held()
        limit = self.settings.limit
        self.stats.max_tokens_seen = max(self.stats.max_tokens_seen, self.tokens())
        ratio = used / self.settings.budget_tokens
        self._rearm(ratio)
        room = limit - used
        largest = max(self._recent_outputs or [0]) / self.chars_per_token
        self._turn += 1
        if used > limit // 2 and room < max(0.10 * limit, 2 * largest):
            if self._turn - self._last_urgent < URGENT_EVERY_TURNS:
                return ""
            self._last_urgent = self._turn
            self.stats.urgent_nudges += 1
            return (
                f"[context: urgent] {used} of {limit} tokens used; only about {room} left. Condense "
                f"{self.settings.mirror_path} now (keep facts, paths, decisions and open problems; drop the rest), and "
                "send large outputs to files instead of the conversation."
            )
        crossed = [r for r in self._armed if ratio >= r]
        if not crossed:
            return ""
        top = max(crossed)
        self._armed -= set(crossed)
        self.stats.nudges += 1
        return (
            f"[context] Your context is at {ratio:.0%} of its {self.settings.budget_tokens}-token budget. "
            f"It is mirrored at {self.settings.mirror_path}; condense it when convenient by editing that file (keep what "
            "you still need, drop the rest). A turn that only edits that file and prints nothing is free."
            if top < 0.75
            else f"[context] Your context is at {ratio:.0%} of its {self.settings.budget_tokens}-token budget. "
            f"Condense {self.settings.mirror_path} soon: above the limit older turns are replaced by a summary."
        )

    def _rearm(self, ratio: float | None = None) -> None:
        """Re-arm the nudge thresholds the context is back under (after an edit, checkpoint or shrink)."""
        ratio = self.held() / self.settings.budget_tokens if ratio is None else ratio
        for r in self.settings.nudge_ratios:
            if ratio < r:
                self._armed.add(r)
        if ratio < 0.75:
            self._rollbacks_in_episode = 0

    def over_limit(self) -> bool:
        return self.held() > self.settings.limit

    def can_roll_back(self) -> bool:
        return self._rollbacks_in_episode < self.settings.max_rollbacks and any(
            m.get("role") == "assistant" for m in self.editable
        )

    def roll_back(self, kept: str = "") -> str:
        """Remove the newest assistant turn and its results; return the note to pin for the model."""
        idx = max(
            i for i, m in enumerate(self.editable) if m.get("role") == "assistant"
        )
        removed = self.editable[idx:]
        del self.editable[idx:]
        self._rollbacks_in_episode += 1
        self.stats.rollbacks += 1
        cmds = [_call_text(c)[:200] for c in removed[0].get("tool_calls") or ()]
        sizes = [
            len(str(m.get("content") or "")) for m in removed if m.get("role") == "tool"
        ]
        note = (
            f"[context limit] Your newest turn was rolled back: the context would exceed its "
            f"{self.settings.limit}-token limit. The command(s) did run and their effects remain, but their "
            f"output ({sum(sizes)} chars) was dropped from your context{kept}:\n"
            + "\n".join(f"- {c}" for c in cmds)
            + f"\nCondense {self.settings.mirror_path} now, then continue; re-run with smaller output or write it to a file."
        )
        self.editable.append({"role": "user", "content": note})
        return note

    # ----- the mirror file -----------------------------------------------------------------------
    def render(self, upto: int | None = None) -> str:
        msgs = self.editable if upto is None else self.editable[:upto]
        return "\n".join(
            f"[[CTX_TURN {i} role={m.get('role')}]]\n{render_message(m)}"
            for i, m in enumerate(msgs)
        )

    def render_history(self) -> str:
        """Original appended messages, including reasoning and structured content, with stable message IDs.

        Later harness annotations do not overwrite the original observation. JSON preserves the fields that
        the editable text mirror intentionally leaves out, including tool IDs and image data.
        """
        return "\n".join(
            f"[[MSG {i} role={m.get('role')}]]\n{json.dumps(m, ensure_ascii=False)}"
            for i, m in enumerate(self.raw)
        )

    def read_history(self, message_id: int, offset: int = 0, limit: int = 12000) -> str:
        """Page one original message without depending on the sandbox history file."""
        if not 0 <= message_id < len(self.raw):
            raise ValueError(
                f"history contains {len(self.raw)} messages; IDs are 0 through {len(self.raw) - 1}"
            )
        text = json.dumps(self.raw[message_id], ensure_ascii=False)
        if offset < 0 or offset > len(text) or limit < 1 or limit > 20000:
            raise ValueError(
                f"offset must be 0..{len(text)} and limit must be 1..20000 characters"
            )
        end = min(len(text), offset + limit)
        next_page = f"; next offset={end}" if end < len(text) else "; complete"
        return (
            f"[history MSG {message_id}; {len(self.raw)} messages; chars {offset}:{end} of {len(text)}"
            f"{next_page}]\n{text[offset:end]}"
        )

    @staticmethod
    def parse(text: str) -> list[dict[str, Any]]:
        marks = list(TURN_RE.finditer(text))
        if not marks:
            body = text.strip()
            return [{"role": "user", "content": body}] if body else []
        out = []
        lead = text[: marks[0].start()].strip()
        if lead:
            out.append({"role": "user", "content": lead})
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            body = text[m.end() : end].strip("\n")
            if not body.strip():
                continue
            out.append(
                {
                    "role": "assistant" if m.group(2) == "assistant" else "user",
                    "content": body,
                }
            )
        return out

    def apply_edit(self, text: str, upto: int) -> tuple[bool, str]:
        """Replace editable[:upto] (what the mirror held) with the parsed edit, if it fits."""
        parsed = self.parse(text)
        candidate = parsed + self.editable[upto:]
        used = self.tokens(list(self.pinned) + candidate)
        if used > self.settings.limit:
            self.stats.edits_rejected += 1
            return False, (
                f"[context edit rejected] the edited context would use about {used} tokens, over the "
                f"{self.settings.limit}-token limit; condense it further."
            )
        before = self.tokens()
        self.editable = candidate
        self.stats.edits_accepted += 1
        self._rearm()
        return (
            True,
            f"[context edit accepted] {before} -> {used} tokens ({len(parsed)} blocks).",
        )

    def checkpoint_split(self) -> int:
        """Index of the first message kept verbatim: the newest turns within ``keep_recent_tokens``,
        starting at an assistant turn (so tool results stay with their calls). At least one turn is
        always summarised; 0 means there is nothing older to summarise."""
        starts = [
            i for i, m in enumerate(self.editable) if m.get("role") == "assistant"
        ]
        keep = len(self.editable)
        for i in reversed(starts):
            if (
                self.tokens(self.editable[i:]) - TOOLS_OVERHEAD_TOKENS
                > self.settings.keep_recent_tokens
            ):
                break
            keep = i
        if keep <= 0:
            later = [i for i in starts if i > 0]
            keep = later[0] if later else len(self.editable)
        return keep

    def replace_with_checkpoint(self, summary: str, note: str, keep_from: int) -> None:
        self.editable = [
            {"role": "user", "content": f"{note}\n\n{summary}"}
        ] + self.editable[keep_from:]
        self.stats.checkpoints += 1
        self._rollbacks_in_episode = 0
        self._rearm()
