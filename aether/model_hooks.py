"""Model-reasoning layer: provider-agnostic LLM hooks for Aether-Next.

The completion-evidence protocol (record validity, independence-kind gating,
and the verify_with_inspector bounded-rounds loop) lives in
verify_completion_protocol.py; inspection-request construction and ref
bookkeeping live in verify_inspection_requests.py. Both were extracted from
this module to hold it under the 500-LOC cap. Names tests/other modules
import from ``aether.model_hooks`` are re-exported here unchanged.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Mapping, Protocol, runtime_checkable

from .ledger import ExecutionLedger, Receipt
from .model_interface import build_model_interface_capture
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


class ModelProviderError(Exception):
    """Raised when a provider invocation fails before producing model output."""

    def __init__(self, cause: BaseException, *, role: str) -> None:
        self.role = str(role)
        self.cause_type = type(cause).__name__
        self.cause_message = str(cause)
        super().__init__(
            f"{self.role} provider invocation failed: "
            f"{self.cause_type}: {self.cause_message}"
        )


def _is_provider_output_error(exc: BaseException) -> bool:
    """Recognize provider-side output rejection without importing a provider."""
    return bool(getattr(exc, "is_provider_output_error", False))


class ModelHooks:
    """``KernelHooks`` backed by ``ModelCallable`` functions."""

    def __init__(
        self,
        architect_model: ModelCallable,
        solver_model: ModelCallable,
        verifier_model: ModelCallable | None = None,
        architect_reviewer_model: ModelCallable | None = None,
        vision_model: Any | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        self._architect = architect_model
        self._architect_reviewer = architect_reviewer_model
        self._solver = solver_model
        self._verifier = verifier_model or architect_model
        self._run_id = run_id or uuid.uuid4().hex
        self._task_id = task_id
        self._quarantined_model_telemetry: list[dict[str, Any]] = []
        self._model_interface_captures: list[dict[str, Any]] = []
        self._model_role_call_ordinals: dict[str, int] = {}
        self.last_parse_errors: list[str] = []
        self._verifier_activation_ordinal = 0
        if vision_model is not None:
            # Exposed only when a vision route exists so the perception lane
            # can detect availability with a plain getattr -- absence stays an
            # honest capability gap, never a fake success.
            self._vision = vision_model

            def perceive_image(prompt: str, image_b64: str, media_type: str) -> str:
                scoped = getattr(self._vision, "call_with_telemetry_scope", None)
                if callable(scoped):
                    return str(scoped(
                        prompt,
                        image_b64,
                        media_type,
                        run_id=self._run_id,
                        task_id=self._task_id,
                    ))
                return str(self._vision(prompt, image_b64, media_type))

            self.perceive_image = perceive_image

    def drain_model_telemetry(self) -> tuple[dict[str, Any], ...]:
        """Collect provider-call telemetry without making providers mandatory.

        Model callables remain protocol-compatible plain callables.  Only
        callables that implement ``drain_telemetry`` contribute rows; the
        Azure text and vision Responses callables both implement it. Offline
        test callables remain untouched.
        """
        rows: list[dict[str, Any]] = []
        self._quarantined_model_telemetry = []
        seen: set[int] = set()
        for model in (
            self._architect,
            self._architect_reviewer,
            self._solver,
            self._verifier,
            getattr(self, "_vision", None),
        ):
            if model is None or id(model) in seen:
                continue
            seen.add(id(model))
            for drain_name in ("drain_telemetry", "drain_continuity_admission_telemetry"):
                drain = getattr(model, drain_name, None)
                if not callable(drain):
                    continue
                for row in drain() or ():
                    if isinstance(row, dict):
                        snapshot = dict(row)
                        if snapshot.get("run_id") == self._run_id:
                            rows.append(snapshot)
                        else:
                            snapshot["telemetry_quarantine_reason"] = (
                                "late_or_unscoped_event_not_owned_by_current_run"
                            )
                            snapshot["drained_by_run_id"] = self._run_id
                            snapshot["drained_by_task_id"] = self._task_id
                            self._quarantined_model_telemetry.append(snapshot)
        return tuple(rows)

    def drain_quarantined_model_telemetry(self) -> tuple[dict[str, Any], ...]:
        """Return late/unscoped provider events excluded from this run row."""
        rows = tuple(self._quarantined_model_telemetry)
        self._quarantined_model_telemetry = []
        return rows

    def release_model_scope(self) -> None:
        """Release optional provider state owned by this immutable task/run scope."""
        seen: set[int] = set()
        for model in (
            self._architect,
            self._architect_reviewer,
            self._solver,
            self._verifier,
            getattr(self, "_vision", None),
        ):
            if model is None or id(model) in seen:
                continue
            seen.add(id(model))
            release = getattr(model, "clear_continuity_scope", None)
            if callable(release):
                release(run_id=self._run_id, task_id=str(self._task_id or ""))

    def drain_model_interface_captures(self) -> tuple[dict[str, Any], ...]:
        """Return exact model-facing transcripts and compact composition manifests."""
        rows = tuple(self._model_interface_captures)
        self._model_interface_captures = []
        return rows

    def _capture_model_interface(
        self,
        messages: list[dict[str, str]],
        *,
        model_role: str,
        max_output_tokens: int,
        stable_prefix_count: int,
    ) -> None:
        role = str(model_role or "model")
        ordinal = self._model_role_call_ordinals.get(role, 0) + 1
        self._model_role_call_ordinals[role] = ordinal
        self._model_interface_captures.append(build_model_interface_capture(
            messages,
            model_role=role,
            role_call_ordinal=ordinal,
            max_output_tokens=max_output_tokens,
            stable_prefix_count=stable_prefix_count,
        ))

    def _call_text_model(
        self,
        model: ModelCallable,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int,
        model_role: str = "model",
        stable_prefix_count: int = 0,
    ) -> str:
        """Capture the exact interface, then invoke the provider unchanged."""
        self._capture_model_interface(
            messages,
            model_role=model_role,
            max_output_tokens=max_output_tokens,
            stable_prefix_count=stable_prefix_count,
        )
        scoped = getattr(model, "call_with_telemetry_scope", None)
        if callable(scoped):
            return str(scoped(
                messages,
                max_output_tokens=max_output_tokens,
                run_id=self._run_id,
                task_id=self._task_id,
            ))
        return str(model(messages, max_output_tokens=max_output_tokens))

    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        self.last_parse_errors = []
        messages = [
            {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request, default=str)},
        ]
        try:
            raw = self._call_text_model(
                self._architect,
                messages,
                max_output_tokens=8000,
                model_role="architect_legacy",
                stable_prefix_count=1,
            )
            cap_index = request.get("capability_index", [])
            return parse_runtime_config_ir(raw, capability_index=cap_index)
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            raise ModelOutputError(f"architect output could not be parsed: {exc}") from exc

    def _commit_solver_continuity_candidate(self) -> None:
        commit = getattr(self._solver, "commit_pending_response", None)
        if callable(commit):
            commit(run_id=self._run_id, task_id=str(self._task_id or ""))

    def _reject_solver_continuity_candidate(self) -> None:
        reject = getattr(self._solver, "reject_pending_response", None)
        if callable(reject):
            reject(run_id=self._run_id, task_id=str(self._task_id or ""))

    def solve(
        self,
        messages: list[dict[str, str]],
        compiled: CompiledRuntime,
    ) -> SolverTurn:
        """Return one locally admitted Solver turn, or fail loudly.

        Native continuity candidates are staged by the provider callable. Only
        a turn that passes both parsing and runtime validation is committed as
        a future parent. Local rejection is discarded before the kernel can
        issue its bounded same-step protocol correction.
        """
        self.last_parse_errors = []
        raw = ""
        try:
            solver_messages = list(messages)
            raw = self._call_text_model(
                self._solver,
                solver_messages,
                max_output_tokens=16000,
                model_role="solver",
                stable_prefix_count=max(0, len(solver_messages) - 1),
            )
        except ModelProviderError:
            raise
        except ModelOutputError as exc:
            self._reject_solver_continuity_candidate()
            self.last_parse_errors.append(str(exc))
            setattr(self, "last_raw_solver_output", raw)
            raise ModelOutputError(f"solver output could not be parsed: {exc}") from exc
        except Exception as exc:
            if _is_provider_output_error(exc):
                self._reject_solver_continuity_candidate()
                self.last_parse_errors.append(str(exc))
                setattr(self, "last_raw_solver_output", raw)
                raise ModelOutputError(
                    f"solver output could not be parsed: {exc}"
                ) from exc
            setattr(self, "last_raw_solver_output", raw)
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            raise ModelProviderError(exc, role="solver") from exc

        try:
            setattr(self, "last_raw_solver_output", raw)
            solver_turn_protocol = getattr(
                compiled, "solver_turn_protocol", "solver_v1"
            )
            turn = parse_solver_turn(raw, protocol=solver_turn_protocol)
            errors = turn.validate(
                compiled.action_schema,
                solver_turn_protocol=solver_turn_protocol,
            )
            if errors:
                message = f"parsed turn failed validation: {errors}"
                self.last_parse_errors.append(message)
                raise ModelOutputError(message)
        except ModelOutputError as exc:
            self._reject_solver_continuity_candidate()
            self.last_parse_errors.append(str(exc))
            setattr(self, "last_raw_solver_output", raw)
            raise ModelOutputError(f"solver output could not be parsed: {exc}") from exc
        except Exception as exc:
            self._reject_solver_continuity_candidate()
            self.last_parse_errors.append(str(exc))
            setattr(self, "last_raw_solver_output", raw)
            raise ModelOutputError(f"solver call failed: {exc}") from exc

        self._commit_solver_continuity_candidate()
        return turn

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
            "authoritative_task_prompt": compiled.task_prompt,
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
            return self._call_text_model(
                self._verifier,
                messages,
                max_output_tokens=_verifier_max_output_tokens(),
                model_role="verifier",
                stable_prefix_count=2,
            )
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            raise

    def _record_verifier_parse_errors(
        self, ledger: ExecutionLedger, *, activation_ordinal: int,
    ) -> None:
        """Persist activation-local Verifier rejections before hook state resets.

        ``last_parse_errors`` is intentionally reset for each new Verifier
        activation.  Admission evidence cannot be: every provider/protocol/
        budget rejection observed by the bounded Verifier loop is copied into
        the immutable execution ledger before a later activation can clear the
        transient buffer.  The generic summary avoids injecting the error text
        into normal recent-receipt context; the exact bounded error remains in
        payload for result/admission metrics.
        """
        if not self.last_parse_errors:
            return
        record = getattr(ledger, "record", None)
        if not callable(record):
            # Some protocol unit tests intentionally supply a read-only ledger
            # facade. Production Aether always supplies ExecutionLedger, whose
            # append authority is the custody boundary proven separately.
            return
        receipts = ledger.all_receipts()
        step = max((int(receipt.step) for receipt in receipts), default=0)
        for error_ordinal, error in enumerate(tuple(self.last_parse_errors), start=1):
            text = str(error).strip()
            if not text:
                continue
            record(Receipt(
                receipt_id=(
                    f"verifier-activation-{activation_ordinal}:"
                    f"parse-error-{error_ordinal}"
                ),
                step=step,
                kind="verifier_parse_error",
                success=False,
                summary="verifier provider/protocol attempt rejected",
                failure_class="verifier_protocol_error",
                payload={
                    "error": text[:2000],
                    "activation_ordinal": activation_ordinal,
                    "error_ordinal": error_ordinal,
                },
            ))

    def verify_with_inspector(
        self,
        packet: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
        inspector,
    ) -> str:
        """Bounded-rounds verification with durable rejection custody."""
        self._verifier_activation_ordinal += 1
        activation_ordinal = self._verifier_activation_ordinal
        try:
            return _verify_with_inspector_impl(self, packet, compiled, ledger, inspector)
        finally:
            self._record_verifier_parse_errors(
                ledger, activation_ordinal=activation_ordinal,
            )

    def call_verifier(self, messages: list[dict[str, str]], *, max_output_tokens: int) -> str:
        """Shared verifier entrypoint used by bounded inspector rounds."""
        return self._call_text_model(
            self._verifier,
            messages,
            max_output_tokens=max_output_tokens,
            model_role="verifier",
            stable_prefix_count=min(2, len(messages)),
        )

    def call_architect_reviewer_model(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int,
    ) -> str:
        """Scoped independent Architect reviewer callable."""
        if self._architect_reviewer is None:
            raise ModelOutputError("architect reviewer model is not configured")
        return self._call_text_model(
            self._architect_reviewer,
            messages,
            max_output_tokens=max_output_tokens,
            model_role="architect_reviewer",
            stable_prefix_count=min(1, len(messages)),
        )

    def call_architect_model(self, messages: list[dict[str, str]], *, max_output_tokens: int) -> str:
        """Scoped callable for the certified one-call Architect V3 role."""
        return self._call_text_model(
            self._architect,
            messages,
            max_output_tokens=max_output_tokens,
            model_role="architect",
            stable_prefix_count=min(1, len(messages)),
        )

    def call_workbench_architect_model(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int,
    ) -> str:
        """Quarantined Workbench callable retained for replay/reference tests."""
        return self._call_text_model(
            self._architect,
            messages,
            max_output_tokens=max_output_tokens,
            model_role="architect_workbench",
            stable_prefix_count=min(1, len(messages)),
        )

    @staticmethod
    def _safe_fallback_turn() -> SolverTurn:
        raise ModelOutputError("safe fallback turns are forbidden in certified solver runtime")
