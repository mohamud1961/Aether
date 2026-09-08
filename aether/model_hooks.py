"""Model-reasoning layer: provider-agnostic LLM hooks for Aether-Next.

The completion-evidence protocol (record validity, independence-kind gating,
and the verify_with_inspector bounded-rounds loop) lives in
verify_completion_protocol.py; inspection-request construction and ref
bookkeeping live in verify_inspection_requests.py. Both were extracted from
this module to hold it under the 500-LOC cap. Names tests/other modules
import from ``aether.model_hooks`` are re-exported here unchanged.
"""
from __future__ import annotations

from hashlib import sha256
import json
import uuid
from typing import Any, Mapping, Protocol, runtime_checkable

from .ledger import ExecutionLedger, Receipt
from .model_interface import build_model_interface_capture
from .verifier_provider_projection import compact_verifier_messages_for_provider
from .runtime_ir import CompiledRuntime, SolverTurn
from .run_cancellation import RunCancellationRequested
from .model_parse import (
    _extract_json_object,
    parse_solver_turn,
)
from .model_prompts import (
    DEFAULT_VERIFIER_IDENTITY_PROMPT,
    VERIFIER_RUNTIME_CONTRACT,
)
from .verify_completion_protocol import (
    _completion_independence_problem,
    _completion_record_problem,
    verify_with_inspector as _verify_with_inspector_impl,
)
from .verify_inspection_requests import (
    _independent_derivation_refs,
    _refs_from_inspections,
    _verifier_identity_prompt_for,
)


@runtime_checkable
class ModelCallable(Protocol):
    def __call__(self, messages: list[dict[str, str]], *, max_output_tokens: int | None = None) -> str: ...


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
        solver_model: ModelCallable,
        verifier_model: ModelCallable,
        vision_model: Any | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        telemetry_identity: Mapping[str, Any] | None = None,
        solver_max_output_tokens: int | None = 16000,
        verifier_max_output_tokens: int | None = 12000,
    ) -> None:
        self._solver = solver_model
        self._verifier = verifier_model
        self._runtime_capability_ids: set[str] = set()
        self._runtime_capabilities_configured = False
        self._run_id = run_id or uuid.uuid4().hex
        self._task_id = task_id
        source_identity = dict(telemetry_identity or {})
        self._telemetry_identity: dict[str, Any] = {
            "run_id": self._run_id,
            "task_id": self._task_id,
        }
        for key in (
            "campaign_id", "source_commit", "runtime_manifest_sha256",
            "task_closure_sha256", "package_closure_sha256",
            "model_profile_sha256", "tool_schema_sha256", "raw_task_sha256",
        ):
            value = source_identity.get(key)
            if value not in (None, ""):
                self._telemetry_identity[key] = value
        self._solver_max_output_tokens = (
            int(solver_max_output_tokens) if solver_max_output_tokens is not None else None
        )
        self._verifier_max_output_tokens = (
            int(verifier_max_output_tokens) if verifier_max_output_tokens is not None else None
        )
        for value in (self._solver_max_output_tokens, self._verifier_max_output_tokens):
            if value is not None and value <= 0:
                raise ValueError("model output token budgets must be positive when configured")
        self._quarantined_model_telemetry: list[dict[str, Any]] = []
        self._model_interface_captures: list[dict[str, Any]] = []
        self._model_exchange_captures: list[dict[str, Any]] = []
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
                        owned = snapshot.get("run_id") == self._run_id
                        if owned and self._task_id not in (None, ""):
                            observed_task = snapshot.get("task_id")
                            owned = observed_task in (None, "", self._task_id)
                        conflicts = [
                            key for key, expected in self._telemetry_identity.items()
                            if snapshot.get(key) not in (None, "", expected)
                        ]
                        if owned and not conflicts:
                            for key, value in self._telemetry_identity.items():
                                if value not in (None, ""):
                                    snapshot.setdefault(key, value)
                            rows.append(snapshot)
                        else:
                            snapshot["telemetry_quarantine_reason"] = (
                                "telemetry_identity_conflict" if conflicts
                                else "late_or_unscoped_event_not_owned_by_current_run"
                            )
                            if conflicts:
                                snapshot["telemetry_identity_conflict_fields"] = sorted(conflicts)
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
            close_transport = getattr(model, "close_run_transport", None)
            if callable(close_transport):
                close_transport()

    def stage_primary_native_image_observation(
        self,
        *,
        image_bytes: bytes,
        media_type: str,
        artifact_sha256: str,
        artifact_path: str,
        source_receipt_id: str,
    ) -> bool:
        """Offer one exact image to the persistent Primary's next causal boundary.

        This is a provider capability probe/staging operation, not a model call.
        Plain/offline Solver callables simply return False and preserve the
        existing perception fallback.
        """
        stage = getattr(self._solver, "stage_native_image_observation", None)
        if not callable(stage):
            return False
        return bool(stage(
            image_bytes=bytes(image_bytes),
            media_type=str(media_type),
            artifact_sha256=str(artifact_sha256),
            artifact_path=str(artifact_path),
            source_receipt_id=str(source_receipt_id),
            run_id=self._run_id,
            task_id=str(self._task_id or ""),
        ))

    def drain_model_interface_captures(self) -> tuple[dict[str, Any], ...]:
        """Return exact model-facing transcripts and compact composition manifests."""
        rows = tuple(self._model_interface_captures)
        self._model_interface_captures = []
        return rows

    def drain_model_exchange_captures(self) -> tuple[dict[str, Any], ...]:
        """Return evidence-only visible provider exchanges in call order.

        These rows are not fed back into the model and are not a second action
        authority. They bind the already-captured exact provider input to the
        visible provider output (or provider error) for trajectory export.
        """
        rows = tuple(self._model_exchange_captures)
        self._model_exchange_captures = []
        return rows

    def _capture_model_interface(
        self,
        messages: list[dict[str, str]],
        *,
        model_role: str,
        max_output_tokens: int | None,
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
        max_output_tokens: int | None,
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
        role = str(model_role or "model")
        ordinal = int(self._model_role_call_ordinals.get(role, 0))
        latest_capture = self._model_interface_captures[-1] if self._model_interface_captures else {}
        manifest = latest_capture.get("manifest", {}) if isinstance(latest_capture, dict) else {}
        base_exchange = {
            "model_role": role,
            "role_call_ordinal": ordinal,
            "run_id": self._run_id,
            "task_id": self._task_id,
            "input_transcript_sha256": str(manifest.get("transcript_sha256", "")),
            "input_messages": [dict(item) for item in latest_capture.get("messages", ())] if isinstance(latest_capture, dict) else [],
            "max_output_tokens": (int(max_output_tokens) if max_output_tokens is not None else None),
        }
        scoped = getattr(model, "call_with_telemetry_scope", None)
        try:
            if callable(scoped):
                scoped_kwargs = {"run_id": self._run_id, "task_id": self._task_id}
                if max_output_tokens is not None:
                    scoped_kwargs["max_output_tokens"] = max_output_tokens
                output = str(scoped(messages, **scoped_kwargs))
            elif max_output_tokens is None:
                output = str(model(messages))
            else:
                output = str(model(messages, max_output_tokens=max_output_tokens))
        except Exception as exc:
            self._model_exchange_captures.append({
                **base_exchange,
                "provider_call_succeeded": False,
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
            })
            raise
        self._model_exchange_captures.append({
            **base_exchange,
            "provider_call_succeeded": True,
            "output": output,
            "output_sha256": sha256(output.encode("utf-8")).hexdigest(),
            "output_utf8_bytes": len(output.encode("utf-8")),
        })
        return output

    def configure_runtime_capabilities(self, capability_ids: set[str] | tuple[str, ...] | list[str]) -> None:
        """Bind current executor capability truth for the next Solver decision."""
        self._runtime_capability_ids = {
            str(capability_id).strip()
            for capability_id in capability_ids
            if str(capability_id).strip()
        }
        self._runtime_capabilities_configured = True

    def _configure_solver_runtime_capabilities(self, compiled: CompiledRuntime) -> None:
        setter = getattr(self._solver, "set_computer_use_available", None)
        if not callable(setter):
            return
        selected_ids = getattr(compiled, "selected_capability_ids", None)
        selected = set(selected_ids()) if callable(selected_ids) else set()
        if self._runtime_capabilities_configured:
            selected.discard("computer_control")
            selected.update(self._runtime_capability_ids)
        setter(
            "computer_control" in selected,
            run_id=self._run_id, task_id=str(self._task_id or ""),
        )

    def stage_primary_computer_observation(
        self, *, screenshot_bytes: bytes, media_type: str, screenshot_sha256: str,
        source_receipt_id: str, action: Mapping[str, Any],
    ) -> bool:
        stage = getattr(self._solver, "stage_computer_observation", None)
        if not callable(stage):
            return False
        return bool(stage(
            screenshot_bytes=bytes(screenshot_bytes), media_type=str(media_type),
            screenshot_sha256=str(screenshot_sha256), source_receipt_id=str(source_receipt_id),
            action=dict(action), run_id=self._run_id, task_id=str(self._task_id or ""),
        ))

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
            self._configure_solver_runtime_capabilities(compiled)
            solver_messages = list(messages)
            raw = self._call_text_model(
                self._solver,
                solver_messages,
                max_output_tokens=self._solver_max_output_tokens,
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
            if isinstance(exc, RunCancellationRequested):
                raise
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
            turn = parse_solver_turn(raw)
            errors = turn.validate(compiled.action_schema)
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

    @property
    def verifier_max_output_tokens(self) -> int | None:
        """Positive constructor-owned Verifier output ceiling."""
        return self._verifier_max_output_tokens

    def verify(
        self,
        packet: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
    ) -> str:
        self.last_parse_errors = []
        from .pcr_verifier_context import verifier_packet_for_model
        user_payload = {
            "verifier_runtime_contract": VERIFIER_RUNTIME_CONTRACT,
            "verifier_packet": dict(verifier_packet_for_model(compiled, packet)),
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
                max_output_tokens=self._verifier_max_output_tokens,
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

    def call_verifier(self, messages: list[dict[str, str]], *, max_output_tokens: int | None) -> str:
        """Shared verifier entrypoint with a lossless provider-only history projection."""
        provider_messages, projection_audit = compact_verifier_messages_for_provider(messages)
        try:
            return self._call_text_model(
                self._verifier,
                provider_messages,
                max_output_tokens=max_output_tokens,
                model_role="verifier",
                stable_prefix_count=min(2, len(provider_messages)),
            )
        finally:
            # The capture is evidence-only and is never fed back into the model.
            # Bind the representational audit to the exact provider-facing
            # transcript so live rows can prove when compaction did/did not run.
            if self._model_interface_captures:
                latest = self._model_interface_captures[-1]
                manifest = latest.get("manifest", {}) if isinstance(latest, dict) else {}
                captured_role = (
                    latest.get("model_role") if isinstance(latest, dict) else None
                ) or (manifest.get("model_role") if isinstance(manifest, dict) else None)
                if captured_role == "verifier":
                    latest["provider_projection_audit"] = dict(projection_audit)

    @staticmethod
    def _safe_fallback_turn() -> SolverTurn:
        raise ModelOutputError("safe fallback turns are forbidden in certified solver runtime")
