"""Prompt text for the vNext Runtime Workbench Architect."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from .architect_review import (
    ARCHITECT_FINALIZER_APPENDIX,
    ARCHITECT_REVIEWER_SYSTEM_PROMPT,
    build_architect_finalizer_packet,
    build_architect_review_packet,
    parse_architect_review_report,
)
from .model_hooks import ModelCallable
from .workbench_config import HarnessConfigIR, parse_workbench_architect_output


from .workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT



class WorkbenchArchitect:
    """Ask a model for HarnessConfigIR without synthesizing fallback config."""

    def __init__(
        self,
        model: ModelCallable,
        *,
        review_model: ModelCallable | None = None,
        max_output_tokens: int = 24000,
        review_max_output_tokens: int = 24000,
        finalizer_max_output_tokens: int = 64000,
    ) -> None:
        self._model = model
        self._review_model = review_model
        self._max_output_tokens = max(1000, int(max_output_tokens))
        self._review_max_output_tokens = max(1000, int(review_max_output_tokens))
        self._finalizer_max_output_tokens = max(1000, int(finalizer_max_output_tokens))
        self.last_raw_output = ""
        self.last_errors: list[str] = []
        self.last_warning_codes: list[str] = []
        self.last_warnings: list[str] = []
        self.last_rejected_config_items: list[dict[str, Any]] = []
        self.last_repaired_output: str | None = None
        self.last_correction_findings: list[str] = []
        self.last_review_output: str = ""
        self.last_review_report: dict[str, Any] | None = None
        self.last_finalizer_output: str = ""
        self.review_calls: int = 0
        self.finalizer_calls: int = 0
        self.correction_calls: int = 0
        self.replacement_calls: int = 0

    @staticmethod
    def _is_output_budget_error(exc: Exception) -> bool:
        text = str(exc)
        return bool(re.search(r"max_output_tokens", text, re.IGNORECASE))

    def _call_model(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int,
        allow_budget_retry: bool = True,
    ) -> str:
        try:
            return self._model(messages, max_output_tokens=max_output_tokens)
        except Exception as exc:
            if allow_budget_retry and self._is_output_budget_error(exc):
                expanded = min(max(max_output_tokens + 12000, int(max_output_tokens * 1.5)), 48000)
                return self._model(messages, max_output_tokens=expanded)
            raise

    @staticmethod
    def _candidate_payload(raw: str) -> dict[str, Any]:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Architect candidate must be one JSON object")
        return value

    def _review_and_finalize(
        self,
        request: Mapping[str, Any],
        *,
        candidate_raw: str,
        candidate_config: HarnessConfigIR,
        candidate_errors: list[str] | tuple[str, ...] = (),
    ) -> tuple[HarnessConfigIR | None, list[str]]:
        """Run the optional independent model review and one bounded replacement.

        The reviewer receives only the original request and complete candidate.
        No evaluator findings or deterministic task-semantic repair are supplied.
        A finalizer is invoked only for a valid ``needs_revision`` report. The
        finalizer and compiler correction share one replacement-call budget.
        """
        if self._review_model is None:
            return candidate_config, list(candidate_errors)
        try:
            candidate_payload = self._candidate_payload(candidate_raw)
            review_messages = [
                {"role": "system", "content": ARCHITECT_REVIEWER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        build_architect_review_packet(request, candidate_payload),
                        default=str,
                    ),
                },
            ]
            self.review_calls += 1
            review_raw = self._review_model(
                review_messages,
                max_output_tokens=self._review_max_output_tokens,
            )
            self.last_review_output = str(review_raw)
            review = parse_architect_review_report(str(review_raw))
            self.last_review_report = review
            if review["review_status"] == "pass":
                return candidate_config, list(candidate_errors)
            if self.replacement_calls >= 1:
                error = "workbench architect replacement limit exhausted"
                self.last_errors = [error]
                return None, [error]
            self.replacement_calls += 1
            self.finalizer_calls += 1
            system_prompt = (
                WORKBENCH_ARCHITECT_SYSTEM_PROMPT
                + "\n\n## Independent-review finalization pass\n"
                + ARCHITECT_FINALIZER_APPENDIX
            )
            finalizer_messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        build_architect_finalizer_packet(
                            request,
                            candidate_payload,
                            review,
                        ),
                        default=str,
                    ),
                },
            ]
            final_raw = self._call_model(
                finalizer_messages,
                max_output_tokens=self._finalizer_max_output_tokens,
                allow_budget_retry=False,
            )
            self.last_finalizer_output = final_raw
            self.last_raw_output = final_raw
            parsed = parse_workbench_architect_output(
                final_raw,
                require_semantic_contract=(
                    str(request.get("schema_version", "")).strip()
                    == "architect_request.v2"
                ),
            )
            self.last_errors = list(parsed.errors)
            self.last_warning_codes = list(parsed.warning_codes)
            self.last_warnings = list(parsed.warnings)
            self.last_rejected_config_items = [
                dict(item) for item in parsed.rejected_config_items
            ]
            self.last_repaired_output = parsed.repaired_json
            return parsed.config, list(parsed.errors)
        except Exception as exc:
            self.last_errors = [f"architect review/finalization failed: {exc}"]
            self.last_warning_codes = []
            self.last_warnings = []
            self.last_rejected_config_items = []
            self.last_repaired_output = None
            return None, list(self.last_errors)

    def correct(
        self,
        request: Mapping[str, Any],
        *,
        previous_output: str,
        findings: list[str] | tuple[str, ...],
    ) -> tuple[HarnessConfigIR | None, list[str]]:
        """Perform at most one model-led correction of a parseable but invalid config.

        The correction receives the original request, the complete prior model
        output, and concrete validation/compiler findings. It must return a
        complete replacement config. No deterministic semantic repair is
        synthesized here, and callers remain responsible for a fresh full
        validation/compile pass before Solver start.
        """
        if self.correction_calls >= 1 or self.replacement_calls >= 1:
            error = "workbench architect replacement limit exhausted"
            self.last_errors = [error]
            return None, [error]
        self.correction_calls += 1
        self.replacement_calls += 1
        self.last_correction_findings = [str(item) for item in findings if str(item)]
        try:
            try:
                previous_payload: Any = json.loads(previous_output)
            except Exception:
                previous_payload = previous_output
            packet = {
                "mode": "architect_generic_correction.v1",
                "original_architect_request": request,
                "previous_draft": previous_payload,
                "compiler_findings": list(self.last_correction_findings),
                "review_contract": [
                    "Return one complete replacement HarnessConfigIR object, not a patch or commentary.",
                    "Re-read the visible task independently of the previous draft and re-inventory every material final-state requirement.",
                    "Preserve correct exact identities and constraints, but do not preserve an incomplete clause set or insufficient evidence route.",
                    "For every generated artifact requirement, ensure the selected route and evidence class are compatible and independently compare the current generated public interface or descriptors with current authoritative source.",
                    "For every required live service or behavior, include a distinct material clause and require a fresh public-interface operation with observed response; process or port liveness alone is insufficient.",
                    "Operationalize every material clause in both Solver and Verifier guidance, then perform a final completeness and evidence-strength audit.",
                ],
            }
            messages = [
                {"role": "system", "content": WORKBENCH_ARCHITECT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(packet, default=str)},
            ]
            raw = self._call_model(
                messages,
                max_output_tokens=self._max_output_tokens,
                allow_budget_retry=False,
            )
            prior = self.last_raw_output
            self.last_raw_output = prior + "\n\n---CORRECTION---\n\n" + raw if prior else raw
            parsed = parse_workbench_architect_output(
                raw,
                require_semantic_contract=(
                    str(request.get("schema_version", "")).strip() == "architect_request.v2"
                ),
            )
            self.last_errors = list(parsed.errors)
            self.last_warning_codes = list(parsed.warning_codes)
            self.last_warnings = list(parsed.warnings)
            self.last_rejected_config_items = [dict(item) for item in parsed.rejected_config_items]
            self.last_repaired_output = parsed.repaired_json
            return parsed.config, list(parsed.errors)
        except Exception as exc:
            self.last_errors = [str(exc)]
            self.last_warning_codes = []
            self.last_warnings = []
            self.last_rejected_config_items = []
            self.last_repaired_output = None
            return None, [str(exc)]

    def configure(self, request: Mapping[str, Any]) -> tuple[HarnessConfigIR | None, list[str]]:
        require_semantic_contract = (
            str(request.get("schema_version", "")).strip() == "architect_request.v2"
        )
        messages = [
            {"role": "system", "content": WORKBENCH_ARCHITECT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request, default=str)},
        ]
        try:
            raw = self._call_model(messages, max_output_tokens=self._max_output_tokens)
            self.last_raw_output = raw
            repaired = parse_workbench_architect_output(
                raw, require_semantic_contract=require_semantic_contract
            )
            self.last_errors = list(repaired.errors)
            self.last_warning_codes = list(repaired.warning_codes)
            self.last_warnings = list(repaired.warnings)
            self.last_rejected_config_items = [dict(item) for item in repaired.rejected_config_items]
            self.last_repaired_output = repaired.repaired_json
            if repaired.config is not None:
                return self._review_and_finalize(
                    request,
                    candidate_raw=raw,
                    candidate_config=repaired.config,
                    candidate_errors=list(repaired.errors),
                )
            repair_messages = [
                {"role": "system", "content": WORKBENCH_ARCHITECT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({
                        "request": request,
                        "previous_output": raw[:12000],
                        "parse_errors": list(repaired.errors),
                        "repair_instruction": (
                            "Repair the previous output. Return one complete, balanced, strict JSON object only. "
                            "Keep array items concise but preserve solver/verifier/config quality. "
                            "Do not include markdown, comments, trailing commas, or extra prose."
                        ),
                        "strict_json_rules": [
                            "Return exactly one JSON object.",
                            "Use double-quoted keys and strings.",
                            "Do not emit markdown, code fences, or comments.",
                            "Do not emit trailing commas or ellipses.",
                            "Do not invent keys outside the required schema.",
                        ],
                    }, default=str),
                },
            ]
            raw_retry = self._call_model(repair_messages, max_output_tokens=self._max_output_tokens)
            self.last_raw_output = raw + "\n\n---RETRY---\n\n" + raw_retry
            retry = parse_workbench_architect_output(
                raw_retry, require_semantic_contract=require_semantic_contract
            )
            self.last_errors = list(retry.errors)
            self.last_warning_codes = list(retry.warning_codes)
            self.last_warnings = list(retry.warnings)
            self.last_rejected_config_items = [dict(item) for item in retry.rejected_config_items]
            self.last_repaired_output = retry.repaired_json
            if retry.config is not None:
                return self._review_and_finalize(
                    request,
                    candidate_raw=raw_retry,
                    candidate_config=retry.config,
                    candidate_errors=list(retry.errors),
                )
            return retry.config, list(retry.errors)
        except Exception as exc:
            self.last_errors = [str(exc)]
            self.last_warning_codes = []
            self.last_warnings = []
            self.last_rejected_config_items = []
            self.last_repaired_output = None
            return None, [str(exc)]
