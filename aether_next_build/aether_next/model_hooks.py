"""Model-reasoning layer: provider-agnostic LLM hooks for Aether-Next.

The completion-evidence protocol (record validity, independence-kind gating,
and the verify_with_inspector bounded-rounds loop) lives in
verify_completion_protocol.py; inspection-request construction and ref
bookkeeping live in verify_inspection_requests.py. Both were extracted from
this module to hold it under the 500-LOC cap. Names tests/other modules
import from ``aether_next.model_hooks`` are re-exported here unchanged.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Protocol, runtime_checkable

from .ledger import ExecutionLedger
from .runtime_ir import CompiledRuntime, RuntimeConfigIR, SolverTurn
from .model_parse import (
    _extract_json_object,
    parse_runtime_config_ir,
    parse_solver_turn,
)
from .model_prompts import (
    ARCHITECT_SYSTEM_PROMPT,
    DEFAULT_VERIFIER_IDENTITY_PROMPT,
    VERIFIER_RUNTIME_CONTRACT,
)
from .verify_completion_protocol import (
    _completion_independence_problem,
    _completion_record_problem,
    verify_with_inspector as _verify_with_inspector_impl,
)
from .verify_inspection_requests import (
    _completed_inspection_is_semantically_grounded,
    _default_completion_inspection_requests,
    _independent_derivation_refs,
    _inspections_from_missing_evidence,
    _refs_from_inspections,
    _verifier_identity_prompt_for,
    _verifier_max_output_tokens,
)


@runtime_checkable
class ModelCallable(Protocol):
    def __call__(self, messages: list[dict[str, str]], *, max_output_tokens: int = 8000) -> str: ...


class ModelOutputError(Exception):
    """Raised when model output cannot be parsed into the expected IR."""


class ModelHooks:
    """``KernelHooks`` backed by ``ModelCallable`` functions."""

    def __init__(
        self,
        architect_model: ModelCallable,
        solver_model: ModelCallable,
        verifier_model: ModelCallable | None = None,
        vision_model: Any | None = None,
    ) -> None:
        self._architect = architect_model
        self._solver = solver_model
        self._verifier = verifier_model or architect_model
        self.last_parse_errors: list[str] = []
        if vision_model is not None:
            # Exposed only when a vision route exists so the perception lane
            # can detect availability with a plain getattr -- absence stays an
            # honest capability gap, never a fake success.
            self._vision = vision_model

            def perceive_image(prompt: str, image_b64: str, media_type: str) -> str:
                return str(self._vision(prompt, image_b64, media_type))

            self.perceive_image = perceive_image

    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        self.last_parse_errors = []
        messages = [
            {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request, default=str)},
        ]
        try:
            raw = self._architect(messages, max_output_tokens=8000)
            cap_index = request.get("capability_index", [])
            return parse_runtime_config_ir(raw, capability_index=cap_index)
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            raise ModelOutputError(f"architect output could not be parsed: {exc}") from exc

    def solve(
        self,
        messages: list[dict[str, str]],
        compiled: CompiledRuntime,
    ) -> SolverTurn:
        """Return a parsed solver turn, or fail loudly.

        Solver parse/validation errors must never be converted into a
        fabricated turn.  The kernel owns parse-error receipts and same-step
        retry so the solver sees the exact failure and raw malformed output is
        preserved for audit.
        """
        self.last_parse_errors = []
        raw = ""
        try:
            raw = self._solver(list(messages), max_output_tokens=16000)
            turn = parse_solver_turn(raw)
            errors = turn.validate(compiled.action_schema)
            if not errors:
                return turn
            message = f"parsed turn failed validation: {errors}"
            self.last_parse_errors.append(message)
            raise ModelOutputError(message)
        except ModelOutputError as exc:
            self.last_parse_errors.append(str(exc))
            setattr(self, "last_raw_solver_output", raw)
            raise ModelOutputError(f"solver output could not be parsed: {exc}") from exc
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            setattr(self, "last_raw_solver_output", raw)
            raise ModelOutputError(f"solver call failed: {exc}") from exc

    def verify(
        self,
        packet: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
    ) -> str:
        self.last_parse_errors = []
        user_payload = {
            "verifier_runtime_contract": VERIFIER_RUNTIME_CONTRACT,
            "verifier_packet": dict(packet),
            "compiled_summary": compiled.task_prompt[:500],
            "ledger_receipt_count": len(ledger.all_receipts()),
        }
        messages = [
            {
                "role": "system",
                "content": _verifier_identity_prompt_for(compiled),
            },
            {"role": "user", "content": json.dumps(user_payload, default=str, sort_keys=True)},
        ]
        try:
            return self._verifier(messages, max_output_tokens=_verifier_max_output_tokens())
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            raise

    def verify_with_inspector(
        self,
        packet: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
        inspector,
    ) -> str:
        """Bounded-rounds verification with read-only inspection and the completion-evidence gate.

        The loop and gate machinery live in
        ``verify_completion_protocol.verify_with_inspector`` (500-LOC cap);
        this method stays a real bound method on ``ModelHooks`` so existing
        callers (e.g. ``kernel_verifier.py``'s
        ``getattr(hooks, "verify_with_inspector")``) keep working unchanged.
        """
        return _verify_with_inspector_impl(self, packet, compiled, ledger, inspector)

    @staticmethod
    def _safe_fallback_turn() -> SolverTurn:
        raise ModelOutputError("safe fallback turns are forbidden in certified solver runtime")
