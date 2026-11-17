"""CLM settings: the context budget, nudges, replay and notes-voice choices, and the request-limit check.

Split from clm.py (module-size cap, 2026-10-26) with the code unchanged; clm.py re-exports every name.
"""

from __future__ import annotations

from dataclasses import dataclass

MIRROR_PATH = "/tmp/.aether/ctx/LIVE_CTX.txt"
HISTORY_PATH = "/tmp/.aether/ctx/HISTORY.txt"
NOTES_VOICES = ("own", "legacy")
CHECKPOINT_POLICIES = ("summary", "window", "stop")
# AETHER_CORE_CLM_PROFILE=meta: Meta's published clm_harness defaults (README, read 16 Nov; clean-room, its licence is
# CC BY-NC 4.0): nudges at 25/50/75%, the adaptive urgent nudge on every turn near the limit, roll back the newest turns
# until 2048 tokens are free (up to 50 times), no summary; still over after the rollbacks: one final turn, then stop.
CLM_PROFILES = ("core", "meta")
META_PROFILE = {"nudge_ratios": (0.25, 0.5, 0.75), "urgent_every_turns": 1, "max_rollbacks": 50,
                "rollback_margin_tokens": 2_048, "checkpoint_policy": "stop"}


@dataclass
class ClmSettings:
    budget_tokens: int = 32_000
    reserve_tokens: int = 2_048
    nudge_ratios: tuple[float, ...] = (0.5, 0.75)
    max_rollbacks: int = 0
    rollback_margin_tokens: int = 0  # after a rollback, keep rolling back until this many tokens are free (meta: 2048)
    # AETHER_CORE_CLM_NUDGES=late (the Harbor default since 17 Nov): the paper's runs (arXiv 2609.37725, App. E) give one editing reminder 2,048 tokens
    # before the budget instead of ratio and urgent nudges. 0 = Core's nudges. Re-armed once the room grows again.
    reminder_room_tokens: int = 0
    urgent_every_turns: int = 3  # C2 row 1: the urgent nudge fired on 10 consecutive turns (meta: 1, every turn)
    keep_recent_tokens: int = 8_000
    # Experimental: cut complete old turns without an auxiliary summary call.
    checkpoint_policy: str = "summary"
    mirror_path: str = MIRROR_PATH
    history_path: str = HISTORY_PATH
    # Two different numbers (O1, B1 dna ep 2). ``budget_tokens`` governs the editable context the model manages
    # (``held``); the newest turn's replayed reasoning is outside it by design, so a whole request can exceed it.
    # ``request_limit_tokens`` is the provider's limit for one request's input plus its reply. None means unknown:
    # recorded as unknown, never assumed.
    request_limit_tokens: int | None = None
    # Which assistant turns' reasoning goes back to the provider. "newest": only the latest turn's (it is the model's
    # live working memory; older turns' is dropped). "all": every turn's, so the request only ever grows at its end.
    # L2 audit: dropping the previous turn's reasoning edits the middle of the history every turn, and the provider's
    # prompt cache never extended past such an edit (0 of 270 requests) but did on 31 of 32 pure extensions.
    # Replayed reasoning is outside ``budget_tokens`` in "newest" and "all". "segment" replays like "all" but the
    # budget counts every replayed reasoning except the newest turn's, so a checkpoint bounds the whole request and
    # drops older reasoning with the turns it summarises (between checkpoints the request only grows at its end).
    # "none" (any context mode): no turn's reasoning is ever sent back, the newest included; the model reasons
    # afresh each turn from the visible history. The trace still records every turn's reasoning.
    replay_reasoning: str = "newest"
    # How the model's edited context is framed when it comes back. Both modes send it in role=user messages (the
    # role is not changed). "own" prefixes each such block with a "[your notes]" label, the first with a header
    # ranking it below the task statement, and changes the checkpoint prompt and a system-prompt sentence (a framing
    # package, under test in N3). "legacy" (default) is the original behaviour. Audit 2026-10-21: 84 of 122
    # accepted edits put a restated task and the model's own conclusions back as unlabelled user text.
    notes_voice: str = "legacy"
    # Opt-in only: record SHA-256 of each original raw message when appended.
    # This identifies later in-process mutation, not malicious edits to both
    # source and digest, and does not reconstruct an original task VM.
    attest_original_history: bool = False
    # Images leave the request in groups of this many (images.limit); 1 = one at a time, the original behaviour.
    image_batch: int = 1
    # Images kept in the request (images.limit); 2 = images.KEEP_IMAGES, images.FULL_KEEP under image fidelity "original".
    image_keep: int = 2
    # AETHER_CORE_IMAGE_EXEMPT=on: images kept in the request (at most image_keep) do not count toward the editable
    # limit. G9 freecad passes checkpointed mid-reading on images, lost them and re-viewed 7-9 (17 Nov).
    image_exempt: bool = False

    @property
    def limit(self) -> int:
        return self.budget_tokens - self.reserve_tokens

    def check_request_limit(self, max_output_tokens: int) -> None:
        """Fail at configuration, not mid-run: the largest request the budget allows (the editable budget, plus
        one replayed reasoning of at most a full reply, plus the next reply) must fit the provider's limit."""
        if self.request_limit_tokens is None:
            return
        if self.replay_reasoning == "all":
            raise ValueError(
                "replay_reasoning 'all' has no bounded worst-case request; it cannot be checked against a known "
                "provider request limit"
            )
        worst = self.budget_tokens + 2 * max_output_tokens
        if worst > self.request_limit_tokens:
            raise ValueError(
                f"CLM budget {self.budget_tokens} + 2 x {max_output_tokens} output tokens = {worst} exceeds the "
                f"provider request limit {self.request_limit_tokens}"
            )


REPLAY_MODES = ("newest", "all", "segment", "none")
