"""Mechanical phase budgets for the model-backed verifier.

The budget deliberately distinguishes direct investigation from a later
derived execution.  It does not judge whether observations or a method are
semantically useful; the model retains that responsibility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Iterable, Mapping


DIRECT_OBSERVATION_KINDS = frozenset({
    "read_file", "read_output", "compare_initial_path", "inspect_artifact_history",
    "inspect_recent_receipts", "inspect_action_receipts", "probe_port", "probe_http", "probe_process", "probe_job",
    "inspect_artifact", "perceive_artifact",
})

# Executable verification operations run only in the disposable verifier
# overlay. They are a separate causal phase from direct observation: a model
# may compose fixture setup and executable checks in one derived batch because
# those operations depend only on model-authored fixture content and already
# observed inputs, never on a direct observation requested in the same turn.
DERIVED_EXECUTION_KINDS = frozenset({
    "rerun_check", "overlay_write_fixture", "overlay_run_command",
})


class VerifierBudgetError(ValueError):
    """A structural budget rejection, never a semantic verdict."""


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class VerifierPhaseBudget:
    max_direct_requests_per_batch: int = 12
    # One initial observation batch plus two bounded investigation revisions.
    # This is an operation-class ceiling, not a required cognitive sequence.
    max_investigation_batches: int = 3
    max_derived_execution_batches: int = 2
    max_protocol_corrections: int = 1
    max_provider_corrections: int = 1
    max_budget_corrections: int = 2
    # Initial investigation + two revisions, up to two derived executions,
    # a verdict, and one bounded protocol correction.
    max_model_calls: int = 7
    # Content requested from one direct observation. This is the model-visible
    # payload budget (for example read_file.excerpt), not the serialized
    # provenance envelope that carries that payload.
    max_result_bytes_per_request: int = 8_192
    # Provenance and registration metadata add deterministic bytes around the
    # requested content. Keep a separate fail-closed envelope ceiling so a
    # legal max-span observation cannot become illegal merely by being
    # provenance-bound.
    max_result_envelope_bytes_per_request: int = 16_384
    # Aggregate ceiling applies to the complete serialized result envelopes.
    max_result_bytes_per_batch: int = 65_536
    # Actual verifier-authored command execution budget. Overlay copy/setup and
    # teardown are lifecycle overhead and are bounded separately below.
    max_tool_execution_s_per_batch: int = 30
    max_tool_lifecycle_s_per_batch: int = 120

    @classmethod
    def from_environment(cls) -> "VerifierPhaseBudget":
        return cls(
            max_direct_requests_per_batch=_positive_int("AETHER_VERIFIER_MAX_DIRECT_REQUESTS", 12),
            max_investigation_batches=_positive_int("AETHER_VERIFIER_MAX_INVESTIGATION_BATCHES", 3),
            max_derived_execution_batches=_positive_int("AETHER_VERIFIER_MAX_DERIVED_EXECUTIONS", 2),
            max_protocol_corrections=_positive_int("AETHER_VERIFIER_MAX_PROTOCOL_CORRECTIONS", 1),
            max_provider_corrections=_positive_int("AETHER_VERIFIER_MAX_PROVIDER_CORRECTIONS", 1),
            max_budget_corrections=_positive_int("AETHER_VERIFIER_MAX_BUDGET_CORRECTIONS", 2),
            max_model_calls=_positive_int("AETHER_VERIFIER_MAX_MODEL_CALLS", 7),
            max_result_bytes_per_request=_positive_int("AETHER_VERIFIER_MAX_RESULT_BYTES", 8_192),
            max_result_envelope_bytes_per_request=_positive_int(
                "AETHER_VERIFIER_MAX_RESULT_ENVELOPE_BYTES", 16_384
            ),
            max_result_bytes_per_batch=_positive_int("AETHER_VERIFIER_MAX_BATCH_BYTES", 65_536),
            max_tool_execution_s_per_batch=_positive_int("AETHER_VERIFIER_TOOL_BUDGET_S", 30),
            max_tool_lifecycle_s_per_batch=_positive_int(
                "AETHER_VERIFIER_TOOL_LIFECYCLE_BUDGET_S", 120
            ),
        )


@dataclass
class VerifierPhaseState:
    budget: VerifierPhaseBudget
    model_calls: int = 0
    investigation_batches: int = 0
    derived_execution_batches: int = 0
    protocol_corrections: int = 0
    provider_corrections: int = 0
    budget_corrections: int = 0
    _request_fingerprints: set[str] = field(default_factory=set)

    @property
    def has_model_call_capacity(self) -> bool:
        return self.model_calls < self.budget.max_model_calls

    def reserve_model_call(self) -> None:
        if self.model_calls >= self.budget.max_model_calls:
            raise VerifierBudgetError("verifier model-call budget exhausted")
        self.model_calls += 1

    def reserve_protocol_correction(self) -> None:
        if self.protocol_corrections >= self.budget.max_protocol_corrections:
            raise VerifierBudgetError("verifier protocol-correction budget exhausted")
        self.protocol_corrections += 1

    def reserve_provider_correction(self) -> None:
        if self.provider_corrections >= self.budget.max_provider_corrections:
            raise VerifierBudgetError("verifier provider-correction budget exhausted")
        self.provider_corrections += 1

    def reserve_budget_correction(self) -> None:
        if self.budget_corrections >= self.budget.max_budget_corrections:
            raise VerifierBudgetError("verifier budget-correction budget exhausted")
        self.budget_corrections += 1

    def classify_and_reserve(self, requests: Iterable[Any]) -> str:
        rows = tuple(requests)
        kinds = {str(getattr(row, "kind", "")).strip() for row in rows}
        direct = bool(kinds) and kinds <= DIRECT_OBSERVATION_KINDS
        derived = bool(kinds) and kinds <= DERIVED_EXECUTION_KINDS
        if not direct and not derived:
            raise VerifierBudgetError(
                "inspection batch must contain either independent direct observations or derived executions, not both"
            )
        fingerprint = json.dumps([asdict(row) for row in rows], sort_keys=True, default=str)
        if fingerprint in self._request_fingerprints:
            raise VerifierBudgetError("equivalent verifier inspection batch already executed")
        if direct:
            if len(rows) > self.budget.max_direct_requests_per_batch:
                raise VerifierBudgetError(
                    f"direct observation batch exceeds maximum of {self.budget.max_direct_requests_per_batch} requests"
                )
            if self.investigation_batches >= self.budget.max_investigation_batches:
                raise VerifierBudgetError("verifier investigation-batch budget exhausted")
            for row in rows:
                if int(getattr(row, "span", 0) or 0) > self.budget.max_result_bytes_per_request:
                    raise VerifierBudgetError("direct observation span exceeds per-result byte budget")
            self.investigation_batches += 1
            phase = "INVESTIGATE"
        else:
            if self.derived_execution_batches >= self.budget.max_derived_execution_batches:
                raise VerifierBudgetError("verifier derived-execution budget exhausted")
            self.derived_execution_batches += 1
            phase = "VERIFY"
        self._request_fingerprints.add(fingerprint)
        return phase

    @staticmethod
    def _content_bytes(value: Any) -> int:
        """Count model-facing payload bytes without charging provenance metadata.

        Direct observations advertise ``max_result_bytes_per_request`` as the
        maximum content span. Historically ``validate_results`` compared the
        entire serialized result envelope against that same number, so an
        exactly-legal 8192-byte read was rejected once path/hash/provenance
        metadata was attached. Keep content and envelope accounting distinct.
        """
        content_fields = {"excerpt", "content", "transcription", "stdout", "stderr"}
        if isinstance(value, Mapping):
            total = 0
            for key, item in value.items():
                if str(key) in content_fields and isinstance(item, str):
                    total += len(item.encode("utf-8", "replace"))
                elif isinstance(item, (Mapping, list, tuple)):
                    total += VerifierPhaseState._content_bytes(item)
            return total
        if isinstance(value, (list, tuple)):
            return sum(VerifierPhaseState._content_bytes(item) for item in value)
        return 0

    def validate_results(self, results: Iterable[Mapping[str, Any]], *, elapsed_s: float) -> None:
        rows = tuple(results)
        reported_execution = [
            float(row.get("tool_execution_elapsed_s", 0.0) or 0.0)
            for row in rows
            if isinstance(row, Mapping) and "tool_execution_elapsed_s" in row
        ]
        # Before C7CD the 30-second command budget was applied to the entire
        # inspector wall time, including overlay copy/setup and teardown. A
        # cheap command could therefore invalidate a row because custody work
        # was slow. New overlay results report command-only execution time;
        # legacy/direct results retain the historical wall-time fallback.
        execution_elapsed_s = sum(reported_execution) if reported_execution else float(elapsed_s)
        if execution_elapsed_s > self.budget.max_tool_execution_s_per_batch:
            raise VerifierBudgetError("verifier inspection batch exceeded tool-execution budget")
        if elapsed_s > self.budget.max_tool_lifecycle_s_per_batch:
            raise VerifierBudgetError("verifier inspection batch exceeded tool-lifecycle budget")
        total = 0
        for row in rows:
            content_size = self._content_bytes(row)
            if content_size > self.budget.max_result_bytes_per_request:
                raise VerifierBudgetError(
                    "verifier inspection content exceeded per-result byte budget (content byte budget)"
                )
            envelope_size = len(
                json.dumps(dict(row), sort_keys=True, default=str).encode("utf-8")
            )
            if envelope_size > self.budget.max_result_envelope_bytes_per_request:
                raise VerifierBudgetError(
                    "verifier inspection result envelope exceeded per-result envelope byte budget"
                )
            total += envelope_size
        if total > self.budget.max_result_bytes_per_batch:
            raise VerifierBudgetError("verifier inspection batch exceeded aggregate byte budget")
