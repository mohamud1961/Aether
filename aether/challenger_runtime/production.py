"""Production wiring: same-model card turns and the direct JUDGE route.

JUDGE credentials are never read here. The launcher fetches the key transiently
through the managed-identity helper (``--judge-keyvault-direct``) and places it
only in the child environment, where ``HttpJudgeTransport`` reads it.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Mapping

from ..providers.judge import HttpJudgeTransport
from .config import (
    ARTIFACT_JUDGE_CAP_GBP, ARTIFACT_JUDGE_TIMEOUT_S, ARTIFACT_MAX_REQUEST_BYTES, CARD_MAX_OUTPUT_TOKENS, CHALLENGER_V1,
    CHALLENGER_V4, CHALLENGER_V5, JUDGE_CAP_GBP, JUDGE_INPUT_PRICE_GBP_PER_MILLION, JUDGE_JOURNAL_NAME,
    JUDGE_MAX_CALLS, JUDGE_MODEL,
)
from .controller import ChallengerController
from .judge_client import JudgeClient
from ..progress_checkpoints import CALL_CAP_GBP, MAX_CALLS as PROGRESS_MAX_CALLS


def build_card_model(profile: Any, make_chat_callable: Callable[..., Any]) -> Any:
    """Plain-text, tool-free callable on the solver's own route, effort, and limiter."""
    return make_chat_callable(
        profile, role="solver", effort=profile.solver_reasoning_effort, tools=(),
        native_persistent_tools=False, capture_rate_headers=True, disable_output_cap_escalation=True,
        charge_shared_pacer_wait_to_run_deadline=True, session_affinity_suffix="challenger",
    )


class BoundCardModel:
    """Adapts the chat callable to ``CardModel`` and forwards run cancellation."""

    def __init__(self, model: Any) -> None:
        self._model = model
        self._last_token_usage: dict[str, Any] | None = None

    def bind_run_cancellation(self, event: Any) -> None:
        bind = getattr(self._model, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    @property
    def last_token_usage(self) -> dict[str, Any] | None:
        """Expose only token telemetry produced by the most recent wrapped call."""
        return None if self._last_token_usage is None else dict(self._last_token_usage)

    def __call__(self, messages: Any) -> str:
        self._last_token_usage = None
        try:
            response = self._model(messages, max_output_tokens=CARD_MAX_OUTPUT_TOKENS)
        except BaseException:
            # A failed call without a returned provider response must not inherit
            # token counts from the previous Solver turn.
            self._last_token_usage = None
            raise
        telemetry = getattr(self._model, "last_call_telemetry", None)
        if isinstance(telemetry, Mapping):
            self._last_token_usage = {
                "usage_status": telemetry.get("usage_status"),
                **{key: telemetry.get(key) for key in (
                    "input_tokens", "output_tokens", "total_tokens", "cached_input_tokens",
                    "cache_write_tokens", "reasoning_tokens")},
            }
        return str(response)


def build_challenger_controller(
    profile: Any, *, make_chat_callable: Callable[..., Any], instruction: str, run_id: str,
    evidence_root: str | Path, transport_factory: Callable[..., Any] = HttpJudgeTransport,
    mode: str = CHALLENGER_V1, progress_fractions: tuple[int, ...] = (),
    progress_mode: str = "control", state_snapshot_mode: str = "control",
    success_contract_mode: str = "control", finish_review_mode: str = "control",
) -> tuple[ChallengerController, tuple[Any, ...]]:
    """Return the controller plus the cancellable components the caller must bind."""
    evidence_dir = Path(evidence_root) / re.sub(r"[^A-Za-z0-9_.:-]", "_", run_id)
    # challenger_v5 sends request bodies up to the artifact byte cap, so its transport bound, budget and timeout are larger.
    larger = ({"max_request_bytes": ARTIFACT_MAX_REQUEST_BYTES, "timeout_s": ARTIFACT_JUDGE_TIMEOUT_S}
              if mode == CHALLENGER_V5 else {})
    transport = transport_factory(
        model=JUDGE_MODEL, journal=evidence_dir / JUDGE_JOURNAL_NAME, max_calls=JUDGE_MAX_CALLS,
        cap_gbp=ARTIFACT_JUDGE_CAP_GBP if mode == CHALLENGER_V5 else JUDGE_CAP_GBP,
        input_gbp_per_million=JUDGE_INPUT_PRICE_GBP_PER_MILLION, **larger,
    )
    progress_transport = None
    if progress_fractions:
        if mode not in (CHALLENGER_V4, CHALLENGER_V5):
            raise ValueError("progress checkpoints require challenger_v4 or challenger_v5")
        progress_transport = transport_factory(
            model=JUDGE_MODEL, journal=evidence_dir / "challenger_progress_judge_provider.jsonl",
            max_calls=PROGRESS_MAX_CALLS, cap_gbp=CALL_CAP_GBP,
            input_gbp_per_million=JUDGE_INPUT_PRICE_GBP_PER_MILLION,
            max_request_bytes=ARTIFACT_MAX_REQUEST_BYTES, timeout_s=ARTIFACT_JUDGE_TIMEOUT_S,
        )
    card_model = BoundCardModel(build_card_model(profile, make_chat_callable))
    controller = ChallengerController(
        card_model=card_model,
        evaluator=JudgeClient(transport, model=JUDGE_MODEL, raw_task=instruction,
                               progress_transport=progress_transport),
        evidence_dir=evidence_dir, run_id=run_id, task_text=instruction, mode=mode,
        progress_fractions=progress_fractions,
        progress_mode=progress_mode,
        state_snapshot_mode=state_snapshot_mode,
        success_contract_mode=success_contract_mode,
        finish_review_mode=finish_review_mode,
    )
    return controller, (card_model, transport, *((progress_transport,) if progress_transport is not None else ()))
