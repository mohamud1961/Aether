"""Model-reasoning layer: provider-agnostic LLM hooks for Aether-Next.

The completion-evidence protocol (record validity, independence-kind gating,
and the verify_with_inspector bounded-rounds loop) lives in
verify_completion_protocol.py; inspection-request construction and ref
bookkeeping live in verify_inspection_requests.py. Both were extracted from
this module to hold it under the 500-LOC cap. Names tests/other modules
import from ``aether.model_hooks`` are re-exported here unchanged.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import uuid
from typing import Any, Mapping, Protocol, runtime_checkable

from .ledger import ExecutionLedger, Receipt
from .model_interface import build_model_interface_capture
from .model_profile import ModelProfile, PRODUCTION_PROFILE
from .verifier_provider_projection import compact_verifier_messages_for_provider
from .verifier_activation_continuity import (
    FRESH_CONTROL as VERIFIER_ACTIVATION_FRESH_CONTROL,
    SUPPORTED_MODES as VERIFIER_ACTIVATION_CONTINUITY_MODES,
)
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
        current: BaseException | None = cause
        self.pre_dispatch_budget_admission_refused = False
        self.provider_terminal_event_type: str | None = None
        self.provider_terminal_retry_safe: bool | None = None
        self.provider_request_accepted: bool | None = None
        self.provider_partial_output_observed: bool | None = None
        self.provider_native_tool_call_observed: bool | None = None
        self.provider_native_tool_call_observed_known = False
        self.provider_incomplete_reason: str | None = None
        self.provider_replay_safety_reason: str | None = None
        self.provider_remaining_run_s_at_frontier_stop: float | None = None
        self.provider_protected_reserve_s: float | None = None
        for _ in range(8):
            if current is None:
                break
            if current.__class__.__name__ == "ProviderBudgetError":
                self.pre_dispatch_budget_admission_refused = True
            if self.provider_terminal_event_type is None and hasattr(current, "event_type"):
                value = getattr(current, "event_type", None)
                if value is not None:
                    self.provider_terminal_event_type = str(value)
            if self.provider_terminal_retry_safe is None and hasattr(current, "retry_safe"):
                self.provider_terminal_retry_safe = bool(getattr(current, "retry_safe"))
            if self.provider_request_accepted is None and hasattr(current, "request_accepted"):
                self.provider_request_accepted = bool(getattr(current, "request_accepted"))
            if self.provider_partial_output_observed is None and hasattr(current, "partial_output_observed"):
                self.provider_partial_output_observed = bool(
                    getattr(current, "partial_output_observed")
                )
            if (
                not self.provider_native_tool_call_observed_known
                and hasattr(current, "native_tool_call_observed")
            ):
                self.provider_native_tool_call_observed = bool(
                    getattr(current, "native_tool_call_observed")
                )
                self.provider_native_tool_call_observed_known = True
            if self.provider_incomplete_reason is None and hasattr(current, "incomplete_reason"):
                value = getattr(current, "incomplete_reason", None)
                if value is not None:
                    self.provider_incomplete_reason = str(value)
            if self.provider_replay_safety_reason is None and hasattr(current, "replay_safety_reason"):
                value = getattr(current, "replay_safety_reason", None)
                if value is not None:
                    self.provider_replay_safety_reason = str(value)
            if (
                self.provider_remaining_run_s_at_frontier_stop is None
                and hasattr(current, "remaining_run_s")
            ):
                self.provider_remaining_run_s_at_frontier_stop = float(
                    getattr(current, "remaining_run_s")
                )
            if (
                self.provider_protected_reserve_s is None
                and hasattr(current, "protected_reserve_s")
            ):
                self.provider_protected_reserve_s = float(
                    getattr(current, "protected_reserve_s")
                )
            current = current.__cause__
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
        model_profile: ModelProfile = PRODUCTION_PROFILE,
    ) -> None:
        self._solver = solver_model
        self._verifier = verifier_model
        self._model_profile = model_profile
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
        self._active_verifier_activation_id: str | None = None
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
            model_profile=self._model_profile,
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

    def configure_provider_frontier_recovery(
        self, mode: str, *, protected_reserve_s: float | None
    ) -> None:
        """Configure optional mechanical Solver provider reserve controls."""
        setter = getattr(self._solver, "configure_provider_frontier_recovery", None)
        if callable(setter):
            setter(str(mode), protected_reserve_s=protected_reserve_s)

    def configure_primary_completion_mode(self, mode: str) -> None:
        """Bind runtime-owned completion protocol state for the next Solver call."""
        setter = getattr(self._solver, "set_primary_completion_mode", None)
        if callable(setter):
            setter(
                str(mode), run_id=self._run_id, task_id=str(self._task_id or ""),
            )

    def solver_reasoning_effort(self) -> str | None:
        """The solver's configured reasoning effort, or ``None`` when it has none."""
        return getattr(self._solver, "configured_reasoning_effort", None)

    def configure_solver_reasoning_effort(self, effort: str | None) -> None:
        """Set (or clear with ``None``) the per-turn reasoning-effort override on the Solver callable."""
        setter = getattr(self._solver, "set_reasoning_effort_override", None)
        if not callable(setter):
            raise RuntimeError("solver callable does not support a per-turn reasoning-effort override")
        setter(effort)

    def solver_temperature(self) -> float:
        """The solver's configured base temperature."""
        value = getattr(self._solver, "configured_temperature", None)
        if value is None:
            raise RuntimeError("solver callable does not expose a configured temperature")
        return float(value)

    def configure_solver_temperature(self, temperature: float | None) -> None:
        """Set (or clear with ``None``) the per-request temperature override on the Solver callable."""
        setter = getattr(self._solver, "set_temperature_override", None)
        if not callable(setter):
            raise RuntimeError("solver callable does not support a per-request temperature override")
        setter(temperature)

    def configure_solver_step(self, step: int) -> None:
        """Tell the Solver callable which runtime step the next call belongs to."""
        setter = getattr(self._solver, "set_solver_step", None)
        if callable(setter):
            setter(int(step), run_id=self._run_id, task_id=str(self._task_id or ""))

    def drain_solver_context_events(self) -> tuple[dict[str, Any], ...]:
        """Context-policy outcomes (e.g. GLM-written checkpoints) awaiting a ledger receipt."""
        drain = getattr(self._solver, "drain_context_checkpoint_events", None)
        if not callable(drain):
            return ()
        return tuple(drain(run_id=self._run_id, task_id=str(self._task_id or "")))

    def configure_completion_disposition_mode(self, mode: str) -> None:
        """Bind the default-off final finding-disposition protocol for one Solver scope."""
        setter = getattr(self._solver, "set_completion_disposition_mode", None)
        if callable(setter):
            setter(
                str(mode), run_id=self._run_id, task_id=str(self._task_id or ""),
            )

    def configure_context_file_mode(self, mode: str) -> None:
        """Expose (or restrict to edit/finish) the context-file edit tool for one Solver scope."""
        setter = getattr(self._solver, "set_context_file_mode", None)
        if not callable(setter):
            raise RuntimeError("Solver provider cannot expose the context-file edit tool")
        setter(str(mode), run_id=self._run_id, task_id=str(self._task_id or ""))

    def configure_completion_record_mode(self, mode: str) -> None:
        """Hide or expose the structured completion-record control for one Solver scope."""
        setter = getattr(self._solver, "set_completion_record_mode", None)
        if callable(setter):
            setter(
                str(mode), run_id=self._run_id, task_id=str(self._task_id or ""),
            )

    def _configure_solver_commitment_mode(self, compiled: CompiledRuntime) -> None:
        setter = getattr(self._solver, "set_solver_commitment_mode", None)
        if not callable(setter):
            return
        raw_realization = getattr(compiled, "config_realization", {})
        realization = raw_realization if isinstance(raw_realization, Mapping) else {}
        reasoning_mode = str(realization.get("solver_reasoning_mode", "control") or "control").strip().lower()
        commitment_mode = "commitment_v1" if reasoning_mode == "commitment_v1" else "control"
        setter(
            commitment_mode,
            run_id=self._run_id,
            task_id=str(self._task_id or ""),
        )

    def _configure_solver_reality_transport_mode(self, compiled: CompiledRuntime) -> None:
        """Bind the experiment-only provider transport without changing PERSISTENT projection."""
        setter = getattr(self._solver, "set_reality_transport_mode", None)
        if not callable(setter):
            return
        raw_realization = getattr(compiled, "config_realization", {})
        realization = raw_realization if isinstance(raw_realization, Mapping) else {}
        mode = str(
            realization.get("solver_reality_transport_mode", "full_snapshot_control")
            or "full_snapshot_control"
        ).strip().lower()
        setter(mode, run_id=self._run_id, task_id=str(self._task_id or ""))

    def _configure_solver_working_context_mode(self, compiled: CompiledRuntime) -> None:
        """Bind the opt-in assistant-content admission mode for one Solver scope."""
        setter = getattr(self._solver, "set_solver_working_context_mode", None)
        if not callable(setter):
            return
        raw_realization = getattr(compiled, "config_realization", {})
        realization = raw_realization if isinstance(raw_realization, Mapping) else {}
        mode = str(realization.get("solver_working_context_mode", "off") or "off").strip().lower()
        setter(mode, run_id=self._run_id, task_id=str(self._task_id or ""))

    def _configure_solver_hosted_tool_search_mode(self, compiled: CompiledRuntime) -> None:
        """Bind the default-off hosted tool-search transport for one Solver scope."""
        setter = getattr(self._solver, "set_hosted_tool_search_mode", None)
        if not callable(setter):
            return
        raw_realization = getattr(compiled, "config_realization", {})
        realization = raw_realization if isinstance(raw_realization, Mapping) else {}
        mode = str(
            realization.get("solver_hosted_tool_search_mode", "control") or "control"
        ).strip().lower()
        setter(mode, run_id=self._run_id, task_id=str(self._task_id or ""))

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

    def reset_solver_continuity_for_recovery(self) -> bool:
        """Drop provider-native Solver continuity before one explicit fresh re-anchor.

        This does not alter Aether ledger/task state. It only prevents an
        accepted-but-incomplete provider response from becoming an implicit
        continuation parent. Callers must separately bound recovery admission.
        """
        clear = getattr(self._solver, "clear_continuity_scope", None)
        if not callable(clear):
            return False
        clear(run_id=self._run_id, task_id=str(self._task_id or ""))
        return True

    def reset_solver_continuity_state_only(self) -> bool:
        """Drop the provider's chat transcript but keep every per-scope tool/protocol mode."""
        clear = getattr(self._solver, "clear_continuity_state", None)
        if not callable(clear):
            return False
        clear(run_id=self._run_id, task_id=str(self._task_id or ""))
        return True

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
            self._configure_solver_commitment_mode(compiled)
            self._configure_solver_reality_transport_mode(compiled)
            self._configure_solver_working_context_mode(compiled)
            self._configure_solver_hosted_tool_search_mode(compiled)
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
                wrapped = ModelOutputError(
                    f"solver output could not be parsed: {exc}"
                )
                for field in ("rejected_tool_name", "rejected_tool_arguments"):
                    value = str(getattr(exc, field, "") or "")
                    if value:
                        setattr(wrapped, field, value)
                raise wrapped from exc
            setattr(self, "last_raw_solver_output", raw)
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            raise ModelProviderError(exc, role="solver") from exc

        try:
            setattr(self, "last_raw_solver_output", raw)
            selected_capability_ids = getattr(
                compiled, "selected_capability_ids", None,
            )
            capability_ids = (
                selected_capability_ids()
                if callable(selected_capability_ids)
                else ()
            )
            turn = parse_solver_turn(
                raw,
                action_schema=compiled.action_schema,
                capability_ids=capability_ids,
            )
            errors = turn.validate(compiled.action_schema)
            if errors:
                message = f"parsed turn failed validation: {errors}"
                self.last_parse_errors.append(message)
                raise ModelOutputError(message)
            take_salvage = getattr(self._solver, "take_protocol_salvage", None)
            salvage = take_salvage() if callable(take_salvage) else None
            if isinstance(salvage, Mapping):
                turn = replace(turn, protocol_salvage=dict(salvage))
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

        if turn.kind == "finish_outcome":
            take = getattr(self._solver, "take_completion_card", None)
            card = take(run_id=self._run_id, task_id=str(self._task_id or "")) if callable(take) else None
            if card is not None:
                turn = replace(turn, completion_card=card)
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
        from .persistent_verifier_context import verifier_packet_for_model
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

    def _verifier_activation_continuity_mode(
        self, compiled: CompiledRuntime,
    ) -> str | None:
        raw = getattr(compiled, "config_realization", {})
        realization = raw if isinstance(raw, Mapping) else {}
        if "verifier_activation_continuity_mode" not in realization:
            return None
        mode = str(
            realization.get("verifier_activation_continuity_mode")
            or VERIFIER_ACTIVATION_FRESH_CONTROL
        ).strip().lower()
        if mode not in VERIFIER_ACTIVATION_CONTINUITY_MODES:
            raise ValueError(f"unsupported Verifier activation continuity mode: {mode!r}")
        return mode

    def commit_verifier_provider_candidate(self) -> bool:
        activation_id = self._active_verifier_activation_id
        commit = getattr(self._verifier, "commit_verifier_activation_candidate", None)
        if not activation_id or not callable(commit):
            return False
        return bool(commit(
            run_id=self._run_id,
            task_id=str(self._task_id or ""),
            activation_id=activation_id,
        ))

    def reject_verifier_provider_candidate(self) -> bool:
        activation_id = self._active_verifier_activation_id
        reject = getattr(self._verifier, "reject_verifier_activation_candidate", None)
        if not activation_id or not callable(reject):
            return False
        return bool(reject(
            run_id=self._run_id,
            task_id=str(self._task_id or ""),
            activation_id=activation_id,
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
        activation_id = f"verifier-activation-{activation_ordinal}"
        mode = self._verifier_activation_continuity_mode(compiled)
        begin = getattr(self._verifier, "begin_verifier_activation", None)
        end = getattr(self._verifier, "end_verifier_activation", None)
        activated = mode is not None and callable(begin)
        if activated:
            begin(
                mode, run_id=self._run_id, task_id=str(self._task_id or ""),
                activation_id=activation_id,
            )
            self._active_verifier_activation_id = activation_id
        try:
            return _verify_with_inspector_impl(self, packet, compiled, ledger, inspector)
        finally:
            if activated:
                # A terminal verdict does not need a successor parent. Reject
                # any still-pending candidate explicitly before scope release so
                # provider evidence records its disposition rather than silently
                # discarding it.
                self.reject_verifier_provider_candidate()
            self._record_verifier_parse_errors(
                ledger, activation_ordinal=activation_ordinal,
            )
            if activated and callable(end):
                end(
                    run_id=self._run_id, task_id=str(self._task_id or ""),
                    activation_id=activation_id,
                )
            if self._active_verifier_activation_id == activation_id:
                self._active_verifier_activation_id = None

    def call_verifier(self, messages: list[dict[str, str]], *, max_output_tokens: int | None) -> str:
        """Shared verifier entrypoint with a lossless provider-only history projection."""
        if bool(getattr(self._verifier, "is_h1_mechanical_review_control", False)):
            # H1 Arm A is explicitly defined as a deterministic re-observation
            # of evidence nominated by the Primary. The production provider
            # projection intentionally strips current Primary citations to keep
            # the semantic reviewer independent, so this research-only callable
            # receives the canonical Verifier transcript instead. It has no
            # model/provider authority and its implementation is mechanically
            # constrained to cited targets. Semantic-review production remains
            # on the normal compacted evidence-isolated path below.
            provider_messages = [dict(message) for message in messages]
            projection_audit = {
                "status": "h1_mechanical_control_uncompacted",
                "semantic_reviewer_affected": False,
                "reason": "preregistered_primary_cited_evidence_reobservation_control",
            }
        else:
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
