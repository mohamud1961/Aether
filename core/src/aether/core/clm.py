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

Settings and their evidence (C1, 12 Oct): make-mips-interpreter requests averaged
~21k tokens and peaked near 60k; the route allows 300K tokens/minute at ~12
turns/minute, so a 32k budget (the CLM default) keeps a row under the limit.
Nudges start at 50%: at 25% the pinned prompt alone nearly triggers them.
"""

from __future__ import annotations

from copy import deepcopy

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from . import images
from .clm_settings import HISTORY_PATH, MIRROR_PATH, NOTES_VOICES, REPLAY_MODES, ClmSettings  # noqa: F401
from .facts_workspace import ManagedFactsText, WorkspaceBriefText

NOTES_HEADER = (
    "[your notes] You wrote this when you condensed your context. It is your own record, not the task: the task "
    "statement at the top is the only statement of the task, and where your notes differ from it, the task "
    "statement is right."
)
NOTES_TAG = "[your notes]"
TURN_RE = re.compile(r"^\[\[CTX_TURN (\d+) role=([a-z_]+)\]\]$", re.M)
CHARS_PER_TOKEN = 3.0  # initial estimate; recalibrated from the provider's own counts
TOOLS_OVERHEAD_TOKENS = 1_500
URGENT_EVERY_TURNS = 3  # C2 row 1: the urgent nudge fired on 10 consecutive turns; the checkpoint backs it up




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
    _append_message_sha256: list[str] = field(default_factory=list, init=False, repr=False)
    stats: ClmStats = field(default_factory=ClmStats)
    chars_per_token: float = CHARS_PER_TOKEN
    _armed: set[float] = field(default_factory=set)
    _rollbacks_in_episode: int = 0
    _recent_outputs: list[int] = field(default_factory=list)
    _turn: int = 0
    _last_urgent: int = -URGENT_EVERY_TURNS
    # Retained across a copied/resumed context; never inferred from user text.
    _managed_facts_pin_index: int | None = field(default=None, init=False, repr=False)
    # id(message) -> (message, provider reasoning tokens); None means provider usage was not reported
    _reasoning: dict[int, tuple[dict[str, Any], int | None]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.settings.replay_reasoning not in REPLAY_MODES:
            raise ValueError(f"replay_reasoning must be one of {REPLAY_MODES}")
        if self.settings.notes_voice not in NOTES_VOICES:
            raise ValueError(f"notes_voice must be one of {NOTES_VOICES}")
        self._armed = set(self.settings.nudge_ratios)
        if self.settings.attest_original_history and self.raw:
            # No post-hoc declaration that externally supplied history was
            # attested at append time. Use off or reconstruct from clean start.
            raise ValueError("cannot append-time attest a prepopulated raw history")

    def append_digest_candidate(self, message_id: int) -> str | None:
        """Append-time index key only; callers must reverify selected raw/pages.

        Avoid reserializing every historical payload merely to locate candidates.
        This method alone never attests the current mutable raw message.
        """
        if self.settings.attest_original_history and 0 <= message_id < len(self._append_message_sha256):
            return self._append_message_sha256[message_id]
        return None

    def original_message_digest(self, message_id: int) -> str | None:
        """Opt-in verified original JSON source hash, not a task-state verdict."""
        if not self.settings.attest_original_history:
            return None
        if not 0 <= message_id < len(self.raw):
            return None
        if message_id >= len(self._append_message_sha256):
            return None
        text = json.dumps(self.raw[message_id], ensure_ascii=False)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        recorded = self._append_message_sha256[message_id]
        return digest if digest == recorded else None

    # ----- the request ---------------------------------------------------------------------------
    def request(self) -> list[dict[str, Any]]:
        """Pinned + editable; reasoning is replayed per ``settings.replay_reasoning``."""
        keep = {id(m) for m in self._replayed()}
        out = list(self.pinned)
        for msg in self.editable:
            if id(msg) not in keep and "reasoning_content" in msg:
                msg = {k: v for k, v in msg.items() if k != "reasoning_content"}
            out.append(msg)
        return images.limit(out)

    def _last_model_turn(self) -> dict[str, Any] | None:
        # Core publishes versioned facts in an assistant carrier after tool results.
        return next(
            (
                message
                for message in reversed(self.editable)
                if message.get("role") == "assistant"
                and not isinstance(message.get("content"), (ManagedFactsText, WorkspaceBriefText))
            ),
            None,
        )

    def _replayed(self) -> list[dict[str, Any]]:
        """The assistant messages whose reasoning the next request sends back."""
        turns = [m for m in self.editable if m.get("role") == "assistant" and m.get("reasoning_content")]
        if self.settings.replay_reasoning in ("all", "segment"):
            return turns
        last = self._last_model_turn()
        return [last] if last is not None and last.get("reasoning_content") else []

    def tokens(self, messages: list[dict[str, Any]] | None = None) -> int:
        chars = images.size_chars(self.request() if messages is None else images.limit(messages))
        r_chars, r_tokens = self._replayed_reasoning() if messages is None else (0, 0)
        return int((chars - r_chars) / self.chars_per_token) + r_tokens + TOOLS_OVERHEAD_TOKENS

    def window_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Tokens these messages add to ``held()``, counted as ``held()`` counts them (raw characters let encrypted
        reasoning through at a fraction of its cost: Mercury segment checkpointed 31,043 to 30,918 tokens and ended)."""
        stripped = [{k: v for k, v in m.items() if k != "reasoning_content"} for m in messages]
        total = int(images.size_chars(images.limit(stripped)) / self.chars_per_token)
        if self.settings.replay_reasoning == "segment":
            ids = {id(m) for m in messages}
            replayed = self._replayed()
            newest = replayed[-1] if replayed else None
            for m in replayed:
                if id(m) in ids and m is not newest:
                    t = self._counted(m)
                    c = len(json.dumps(m["reasoning_content"], ensure_ascii=False))
                    total += int(c / self.chars_per_token) if t is None else t
        return total

    def held(self) -> int:
        """Tokens the budget governs: the request minus the newest turn's replayed reasoning. That reasoning is the
        model's live working memory, sent once and dropped after its next turn; the model cannot condense it and a
        checkpoint never sees it. Counting it let a single long thought trigger a checkpoint that discarded it (D1
        circuit-fibsqrt: three 32k-token thoughts each summarised away, about 1100 s of reasoning redone)."""
        if self.settings.replay_reasoning == "segment":
            return self.tokens() - self._newest_reasoning_tokens()
        return self.tokens() - self._replayed_reasoning()[1]

    def _newest_reasoning_tokens(self) -> int:
        """Tokens of the newest assistant turn's replayed reasoning (``segment`` leaves only this out of the budget)."""
        last = self._last_model_turn()
        if last is None or not last.get("reasoning_content"):
            return 0
        t = self._counted(last)
        return int(len(json.dumps(last["reasoning_content"], ensure_ascii=False)) / self.chars_per_token) if t is None else t

    def note_reasoning(
        self, message: dict[str, Any], reasoning_tokens: int | None
    ) -> None:
        """Record the provider's reasoning-token count for an assistant message just appended.

        The newest turn's reasoning is replayed in the next request and tokenizes far more densely than tool
        output: in D1 a 32k-token reasoning turn was estimated at 27.7k and counted at 38.2k (budget 32k)."""
        # A 0 next to reasoning text is a missing count (MiniMax on Dahl), not a measurement: estimate it instead.
        if not reasoning_tokens and message.get("reasoning_content"):
            reasoning_tokens = None
        self._reasoning[id(message)] = (message, None if reasoning_tokens is None else int(reasoning_tokens))

    def _counted(self, msg: dict[str, Any]) -> int | None:
        entry = self._reasoning.get(id(msg))
        return entry[1] if entry is not None and entry[0] is msg else None

    def _replayed_reasoning(self, known_only: bool = False) -> tuple[int, int]:
        """(JSON chars, tokens) of the reasoning the next request replays: the provider's count where it reported one,
        else an estimate from the characters. ``known_only``: only the turns whose count the provider reported."""
        chars = tokens = 0
        for msg in self._replayed():
            c = len(json.dumps(msg["reasoning_content"], ensure_ascii=False))
            t = self._counted(msg)
            if t is None and known_only:
                continue
            chars += c
            tokens += int(c / self.chars_per_token) if t is None else t
        return chars, tokens

    def calibrate(self, request_chars: int, input_tokens: int) -> None:
        """Use the provider's real prompt-token count to correct the chars-per-token estimate
        (replayed reasoning whose token count is known exactly is left out of the ratio; an estimate must not
        masquerade as reported usage)."""
        r_chars, r_tokens = self._replayed_reasoning(known_only=True)
        request_chars, input_tokens = request_chars - r_chars, input_tokens - r_tokens
        if input_tokens > TOOLS_OVERHEAD_TOKENS * 2 and request_chars > 0:
            self.chars_per_token = max(
                1.5, min(6.0, request_chars / (input_tokens - TOOLS_OVERHEAD_TOKENS))
            )

    def append(self, *messages: dict[str, Any]) -> None:
        self.editable.extend(messages)
        copied = deepcopy(messages)
        self.raw.extend(copied)
        if self.settings.attest_original_history:
            self._append_message_sha256.extend(
                hashlib.sha256(
                    json.dumps(message, ensure_ascii=False).encode("utf-8")
                ).hexdigest()
                for message in copied
            )
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
        outside = self._replayed_reasoning()[1]  # replayed reasoning: sent, but outside the editable budget
        whole = (
            f" The whole request is about {used + outside} tokens: {outside} of them are your earlier reasoning, "
            "sent back as well but outside this budget."
        ) if outside else ""
        if used > limit // 2 and room < max(0.10 * limit, 2 * largest):
            if self._turn - self._last_urgent < URGENT_EVERY_TURNS:
                return ""
            self._last_urgent = self._turn
            self.stats.urgent_nudges += 1
            # 10-27 board: the old "only about N left" read as the end of the run (path-tracing e1 finished citing
            # context limits; sqlite e2 skipped a check because "context is nearly exhausted"), and it left out the
            # replayed reasoning that made up most of the request.
            return (
                f"[context: urgent] {used} of {limit} tokens of your editable context used; about {room} left before "
                "older turns are replaced by a summary. The run continues after that: this is not a time or turn "
                f"limit.{whole} Condense {self.settings.mirror_path} now (keep facts, paths, decisions and open "
                "problems; drop the rest), and send large outputs to files instead of the conversation."
            )
        crossed = [r for r in self._armed if ratio >= r]
        if not crossed:
            return ""
        top = max(crossed)
        self._armed -= set(crossed)
        self.stats.nudges += 1
        # 10-30 audit: without the whole-request clause 153/617 nudges understated the request by >25 points
        head = f"[context] Your editable context is at {ratio:.0%} of its {self.settings.budget_tokens}-token budget."
        head += whole + " "
        return head + (
            f"It is mirrored at {self.settings.mirror_path}; condense it when convenient by editing that file (keep what "
            "you still need, drop the rest). This shrinks future context; the model/tool turn still uses time and tokens."
            if top < 0.75
            else f"Condense {self.settings.mirror_path} soon: above the limit older turns are replaced by a summary and the "
            "run continues."
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
    def parse(text: str, voice: str = "legacy") -> list[dict[str, Any]]:
        """The edited mirror as messages. Blocks the model marks as its turns stay assistant turns; everything else
        it wrote (its summaries, kept outputs, any block it labels user) is its own record, so with voice "own" it
        comes back labelled as its notes (still role=user), the first with the header that ranks it below the task."""
        marks = list(TURN_RE.finditer(text))
        blocks: list[tuple[str, str]] = []
        lead = (text[: marks[0].start()] if marks else text).strip()
        if lead:
            blocks.append(("user", lead))
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            body = text[m.end() : end].strip("\n")
            if body.strip():
                blocks.append(("assistant" if m.group(2) == "assistant" else "user", body))
        out, headed = [], False
        for role, body in blocks:
            if role == "user" and voice == "own":
                body = f"{NOTES_TAG if headed else NOTES_HEADER}\n{body}"
                headed = True
            out.append({"role": role, "content": body})
        return out

    def _unchanged(self, text: str, upto: int) -> list[dict[str, Any]]:
        """The edit as messages, keeping the original message for every block the model left exactly as rendered.

        Rebuilding every block from text turned untouched tool results into role=user (labelled as notes under
        "own") and tool calls into "[tool_call ...]" text (P1: R5.base.protein-assembly e1r2, 2 -> 52 user
        messages after a one-line edit). A call and its results stay native only together, unchanged and in order;
        anything else goes the text way, as ``parse`` builds it."""
        marks = list(TURN_RE.finditer(text))
        lead = (text[: marks[0].start()] if marks else text).strip()
        blocks: list[tuple[int | None, str, str]] = [(None, "user", lead)] if lead else []
        seen: set[int] = set()
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            body = text[m.end() : end].strip("\n")
            if not body.strip():
                continue
            i, role = int(m.group(1)), m.group(2)
            same = (
                i < upto
                and i not in seen
                and self.editable[i].get("role") == role
                and body == render_message(self.editable[i]).strip("\n")
            )
            seen.add(i)
            blocks.append((i if same else None, role, body))
        keep = [orig is not None and blocks[j][1] != "tool" for j, (orig, _, _) in enumerate(blocks)]
        for j, (orig, _, _) in enumerate(blocks):
            msg = self.editable[orig] if orig is not None else {}
            if keep[j] and msg.get("tool_calls"):
                ids = [c.get("id") for c in msg["tool_calls"]]
                results = blocks[j + 1 : j + 1 + len(ids)]
                keep[j] = len(results) == len(ids) and all(
                    o == orig + n + 1 and r == "tool" and self.editable[o].get("tool_call_id") == ids[n]
                    for n, (o, r, _) in enumerate(results)
                )
                for n in range(len(ids)) if keep[j] else ():  # a result is native only inside its own call's unit
                    keep[j + 1 + n] = True
        out, headed = [], False
        voice = self.settings.notes_voice
        for (orig, role, body), kept in zip(blocks, keep):
            if kept:
                out.append(self.editable[orig])
                continue
            role = "assistant" if role == "assistant" else "user"
            if role == "user" and voice == "own":
                body = f"{NOTES_TAG if headed else NOTES_HEADER}\n{body}"
                headed = True
            out.append({"role": role, "content": body})
        return out

    def apply_edit(self, text: str, upto: int) -> tuple[bool, str]:
        """Replace editable[:upto] (what the mirror held) with the edit, if it fits; untouched blocks keep their
        original message."""
        parsed = self._unchanged(text, upto)
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
            i for i, m in enumerate(self.editable)
            if m.get("role") == "assistant" and not isinstance(m.get("content"), (ManagedFactsText, WorkspaceBriefText))
        ]
        keep = len(self.editable)
        for i in reversed(starts):
            if self.window_tokens(self.editable[i:]) > self.settings.keep_recent_tokens:
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
        # The summary is written while the context is full and can say so (sqlite e2: "Context is nearly exhausted
        # (~29.8k/29.9k tokens)" carried past a checkpoint that cut the request from 83k to 10k); state it fresh.
        self.editable[0]["content"] += (
            f"\n\n[context] Now, after this summary: {self.held()} of {self.settings.budget_tokens} tokens used. "
            "Any statement above about the context being full predates the summary."
        )
