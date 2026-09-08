"""Mechanical phase budgets for the model-backed verifier.

The budget deliberately distinguishes direct investigation from a later
derived execution.  It does not judge whether observations or a method are
semantically useful; the model retains that responsibility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
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


@dataclass(frozen=True)
class VerifierPhaseBudget:
    max_direct_requests_per_batch: int = 12
    # One initial observation batch plus two bounded investigation revisions.
    # This is an operation-class ceiling, not a required cognitive sequence.
    max_investigation_batches: int | None = 3
    max_derived_execution_batches: int | None = 2
    max_protocol_corrections: int | None = 1
    max_provider_corrections: int | None = 1
    max_budget_corrections: int | None = 2
    # Initial investigation + two revisions, up to two derived executions,
    # a verdict, and one bounded protocol correction.
    max_model_calls: int | None = 7
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
    max_tool_execution_s_per_batch: int | None = 30
    max_tool_lifecycle_s_per_batch: int | None = 120




PRODUCTION_VERIFIER_PHASE_BUDGET = VerifierPhaseBudget(
    max_investigation_batches=None,
    max_derived_execution_batches=None,
    max_protocol_corrections=None,
    max_provider_corrections=None,
    max_budget_corrections=None,
    # D2 reviewer qualification and every retained D4 CURRENT_BC policy row
    # completed within four Verifier provider turns.  Keep one advisory review
    # activation bounded to that empirically qualified ceiling instead of
    # allowing inspection/correction churn to grow without limit.
    max_model_calls=4,
    max_tool_execution_s_per_batch=None,
    max_tool_lifecycle_s_per_batch=None,
)
PRODUCTION_VERIFIER_CALL_TIMEOUT_S = 180.0
PRODUCTION_VERIFIER_TIMEOUT_RESERVE_S = 10.0
PRODUCTION_VERIFIER_WALL_CLOCK_BUDGET_S: float | None = None



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
        ceiling = self.budget.max_model_calls
        return ceiling is None or self.model_calls < ceiling

    def reserve_model_call(self) -> None:
        ceiling = self.budget.max_model_calls
        if ceiling is not None and self.model_calls >= ceiling:
            raise VerifierBudgetError("verifier model-call budget exhausted")
        self.model_calls += 1

    def reserve_protocol_correction(self) -> None:
        ceiling = self.budget.max_protocol_corrections
        if ceiling is not None and self.protocol_corrections >= ceiling:
            raise VerifierBudgetError("verifier protocol-correction budget exhausted")
        self.protocol_corrections += 1

    def reserve_provider_correction(self) -> None:
        ceiling = self.budget.max_provider_corrections
        if ceiling is not None and self.provider_corrections >= ceiling:
            raise VerifierBudgetError("verifier provider-correction budget exhausted")
        self.provider_corrections += 1

    def reserve_budget_correction(self) -> None:
        ceiling = self.budget.max_budget_corrections
        if ceiling is not None and self.budget_corrections >= ceiling:
            raise VerifierBudgetError("verifier budget-correction budget exhausted")
        self.budget_corrections += 1

    @staticmethod
    def _direct_observation_fingerprint(rows: tuple[Any, ...]) -> str:
        """Identify information-equivalent direct reads, not model labels.

        The direct executor is driven by the request's locator and bounded
        read/probe parameters.  Request IDs, proof/clause labels, and the
        Verifier's explanation of a claim do not alter that observation.  Keep
        only execution-bearing fields and sort the per-request keys so that a
        renamed or reordered restatement cannot consume another investigation
        batch while a genuinely different locator or bound remains distinct.
        """
        execution_fields = (
            "kind", "path", "handle", "check_id", "receipt_kind", "limit",
            "target", "offset", "span",
        )
        views: list[dict[str, Any]] = []
        for row in rows:
            view = asdict(row)
            views.append({field: view.get(field) for field in execution_fields})
        views.sort(
            key=lambda view: json.dumps(
                view, sort_keys=True, separators=(",", ":"), default=str,
            )
        )
        return json.dumps(views, sort_keys=True, separators=(",", ":"), default=str)

    def classify_and_reserve(self, requests: Iterable[Any]) -> str:
        rows = tuple(requests)
        kinds = {str(getattr(row, "kind", "")).strip() for row in rows}
        direct = bool(kinds) and kinds <= DIRECT_OBSERVATION_KINDS
        derived = bool(kinds) and kinds <= DERIVED_EXECUTION_KINDS
        if not direct and not derived:
            raise VerifierBudgetError(
                "inspection batch must contain either independent direct observations or derived executions, not both"
            )
        fingerprint = (
            self._direct_observation_fingerprint(rows)
            if direct else json.dumps([asdict(row) for row in rows], sort_keys=True, default=str)
        )
        if fingerprint in self._request_fingerprints:
            if direct:
                raise VerifierBudgetError("duplicate_inspection_no_new_information")
            raise VerifierBudgetError("equivalent verifier inspection batch already executed")
        if direct:
            if len(rows) > self.budget.max_direct_requests_per_batch:
                raise VerifierBudgetError(
                    f"direct observation batch exceeds maximum of {self.budget.max_direct_requests_per_batch} requests"
                )
            ceiling = self.budget.max_investigation_batches
            if ceiling is not None and self.investigation_batches >= ceiling:
                raise VerifierBudgetError("verifier investigation-batch budget exhausted")
            for row in rows:
                if int(getattr(row, "span", 0) or 0) > self.budget.max_result_bytes_per_request:
                    raise VerifierBudgetError("direct observation span exceeds per-result byte budget")
            self.investigation_batches += 1
            phase = "INVESTIGATE"
        else:
            ceiling = self.budget.max_derived_execution_batches
            if ceiling is not None and self.derived_execution_batches >= ceiling:
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
        execution_ceiling = self.budget.max_tool_execution_s_per_batch
        if execution_ceiling is not None and execution_elapsed_s > execution_ceiling:
            raise VerifierBudgetError("verifier inspection batch exceeded tool-execution budget")
        lifecycle_ceiling = self.budget.max_tool_lifecycle_s_per_batch
        if lifecycle_ceiling is not None and elapsed_s > lifecycle_ceiling:
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
