"""Revision-9.2 one-shot selective JUDGE advice.

This module is deliberately narrower than the generic SemanticAssistance relation
helper.  It is an experiment treatment for a small set of preregistered public
uncertainty patterns.  The transport is injected and owns authentication, budget,
timeouts, and provider journaling.

JUDGE never gets hidden graders, private fixtures, future observations, or private
model reasoning.  Its result is advisory-only; GLM keeps action/finish authority.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import math
from typing import Any, Callable, Mapping

from .ledger import ExecutionLedger
from .run_cancellation import RunCancellationRequested
from .run_deadline import KernelRunTimeout


SCHEMA = "aether.semantic_advice.v1"
MODE_OFF = "off"
MODE_S1_FINISH_V1 = "s1_finish_v1"
MODE_S2_OVERLAP_V1 = "s2_overlap_v1"
MODE_L3_PROBE_V1 = "l3_probe_v1"
MODES = frozenset({MODE_OFF, MODE_S1_FINISH_V1, MODE_S2_OVERLAP_V1, MODE_L3_PROBE_V1})

_OBSERVATION_KINDS = frozenset({
    "read_file", "read_file_page", "read_output", "grep_output",
    "run_command", "command_result", "artifact_inspection",
})

_POLICIES: dict[str, dict[str, Any]] = {
    MODE_S1_FINISH_V1: {
        "projection": "s1_finish_v1",
        "min_step": 6,
        "markers": (
            "irregular damped-signal samples",
            "residual",
        ),
        "questions": {
            "verification_status": {
                "choices": (
                    "sufficient_public_evidence",
                    "concrete_unmet_requirement",
                    "uncertain",
                ),
                "instructions": (
                    "Using only the supplied public task contract and recent solver-visible "
                    "observations, decide whether there is a concrete public requirement that "
                    "still lacks evidence. A self-authored extra test or possible polish is not "
                    "itself an unmet task requirement. Prefer uncertain when the observations "
                    "do not establish sufficiency."
                ),
                "criteria": {
                    "sufficient_public_evidence": (
                        "Recent public verification and outputs cover the named public "
                        "requirements strongly enough that further model changes need a "
                        "specific new reason."
                    ),
                    "concrete_unmet_requirement": (
                        "A named public requirement has direct evidence of failure or lacks a "
                        "necessary verification."
                    ),
                    "uncertain": (
                        "The supplied public evidence is insufficient to decide whether a "
                        "named requirement remains unmet."
                    ),
                },
            },
            "best_next_move": {
                "choices": (
                    "finish_preserve_last_good",
                    "run_public_verification",
                    "inspect_residual_evidence",
                    "change_model_for_named_gap",
                    "uncertain",
                ),
                "instructions": (
                    "Choose the smallest next move justified by the public task and current "
                    "observations. Avoid open-ended polishing. Preserve a verified last-good "
                    "candidate unless a concrete public requirement motivates a change."
                ),
                "criteria": {
                    "finish_preserve_last_good": (
                        "No concrete unmet public requirement is evidenced; preserve the "
                        "working candidate and finish."
                    ),
                    "run_public_verification": (
                        "A named public verification has not yet been run on the current "
                        "candidate."
                    ),
                    "inspect_residual_evidence": (
                        "The public residual requirement needs direct inspection before "
                        "changing the model."
                    ),
                    "change_model_for_named_gap": (
                        "A specific public requirement is failing and warrants a model change."
                    ),
                    "uncertain": "No next move is established by the supplied evidence.",
                },
            },
        },
    },
    MODE_S2_OVERLAP_V1: {
        "projection": "s2_overlap_v1",
        "min_step": 4,
        "markers": (
            "coupled mechanical system observed by asynchronous channels",
            "fit only timestamps covered by the required input channels",
        ),
        "questions": {
            "fit_domain": {
                "choices": (
                    "shared_observed_overlap_required",
                    "outside_overlap_supported",
                    "uncertain",
                ),
                "instructions": (
                    "Under the supplied public MODEL contract, determine whether fitting may "
                    "use response timestamps outside the observed coverage of either predictor. "
                    "Do not infer hidden grader behavior."
                ),
                "criteria": {
                    "shared_observed_overlap_required": (
                        "The public contract requires fitting only timestamps jointly covered "
                        "by position, response, and drive after interpolation."
                    ),
                    "outside_overlap_supported": (
                        "The public contract explicitly supports fitting response samples "
                        "outside a predictor's observed range."
                    ),
                    "uncertain": (
                        "The supplied public materials do not establish the fit domain."
                    ),
                },
            },
            "best_next_probe": {
                "choices": (
                    "inspect_channel_ranges",
                    "fit_shared_overlap_jointly",
                    "compare_joint_fit_residuals",
                    "no_probe_needed",
                    "uncertain",
                ),
                "instructions": (
                    "Choose the smallest public analysis that best resolves a coupled-fit "
                    "mistake. Prefer the declared two-feature model and observed overlap; never "
                    "request private fixtures or hidden expected parameters."
                ),
                "criteria": {
                    "inspect_channel_ranges": (
                        "First establish the actual observed ranges of all required channels."
                    ),
                    "fit_shared_overlap_jointly": (
                        "Fit coupling and damping jointly on the common observed range."
                    ),
                    "compare_joint_fit_residuals": (
                        "Use public/current data to compare residuals of plausible joint fits."
                    ),
                    "no_probe_needed": "The current public evidence is already decisive.",
                    "uncertain": "No next public probe is established.",
                },
            },
        },
    },
    MODE_L3_PROBE_V1: {
        "projection": "l3_probe_v1",
        "min_step": 4,
        "markers": (
            "scientific identification task",
            "observational prefix is intentionally plausible under a wrong interpretation",
        ),
        "questions": {
            "evidence_status": {
                "choices": (
                    "controlled_probe_evidence_decisive",
                    "observational_evidence_only",
                    "current_hypothesis_contradicted",
                    "uncertain",
                ),
                "instructions": (
                    "Using only the public model contract and recent solver-visible evidence, "
                    "assess whether the current interpretation is supported by controlled probe "
                    "rows rather than the intentionally misleading observational prefix."
                ),
                "criteria": {
                    "controlled_probe_evidence_decisive": (
                        "Controlled probe rows discriminate the relevant lag/sign hypothesis."
                    ),
                    "observational_evidence_only": (
                        "The apparent support comes only from the misleading observational "
                        "region and should not justify commitment."
                    ),
                    "current_hypothesis_contradicted": (
                        "Controlled probe evidence materially contradicts the current "
                        "interpretation."
                    ),
                    "uncertain": "The supplied evidence does not discriminate the hypothesis.",
                },
            },
            "best_next_probe": {
                "choices": (
                    "analyze_probe_rows",
                    "compare_lag_probe_rmse",
                    "fit_selected_lag_on_probes",
                    "no_probe_needed",
                    "uncertain",
                ),
                "instructions": (
                    "Choose the smallest next public calculation that would discriminate the "
                    "scientific hypothesis. Do not request hidden grader values."
                ),
                "criteria": {
                    "analyze_probe_rows": "Inspect the controlled-intervention rows directly.",
                    "compare_lag_probe_rmse": (
                        "Compare candidate integer lags by residual error on probe rows."
                    ),
                    "fit_selected_lag_on_probes": (
                        "Once lag is discriminated, estimate gain and bias from probe rows."
                    ),
                    "no_probe_needed": "Controlled probe evidence is already decisive.",
                    "uncertain": "No useful next public calculation is established.",
                },
            },
        },
    },
}


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _empty(*, mode: str, projection: str, status: str, calls: int) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "authority": "advisory_only",
        "mode": mode,
        "projection": projection,
        "context_pruned": False,
        "status": status,
        "calls_total": int(calls),
        "items": [],
    }


def _typed_answer(
    answers: Mapping[str, Any],
    question_id: str,
    choices: tuple[str, ...],
) -> dict[str, Any]:
    row = answers.get(question_id)
    if not isinstance(row, Mapping):
        raise ValueError(f"missing JUDGE answer: {question_id}")
    choice = str(row.get("choice") or "")
    if choice not in choices:
        raise ValueError(f"unexpected JUDGE choice for {question_id}: {choice!r}")
    probs = row.get("probabilities")
    if not isinstance(probs, Mapping) or set(map(str, probs)) != set(choices):
        raise ValueError(f"incomplete JUDGE probabilities for {question_id}")
    clean: dict[str, float] = {}
    for key in choices:
        value = probs.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"invalid JUDGE probability for {question_id}:{key}")
        number = float(value)
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            raise ValueError(f"invalid JUDGE probability for {question_id}:{key}")
        clean[key] = number
    if abs(sum(clean.values()) - 1.0) > 0.02:
        raise ValueError(f"invalid JUDGE probability total for {question_id}")
    return {"choice": choice, "probabilities": clean}


class SelectiveJudgeAdvice:
    """One-shot, public-evidence-only semantic advice for preregistered pressure."""

    def __init__(
        self,
        evaluate: Callable[[dict[str, Any]], Mapping[str, Any]],
        *,
        model: str,
        mode: str,
        public_contract: Mapping[str, str] | None = None,
        max_request_bytes: int = 16000,
        max_observations: int = 4,
    ) -> None:
        if mode not in MODES or mode == MODE_OFF:
            raise ValueError(f"unsupported active selective JUDGE mode: {mode!r}")
        if not model:
            raise ValueError("exact JUDGE model identity is required")
        if max_request_bytes <= 0 or max_observations <= 0:
            raise ValueError("positive selective JUDGE bounds required")
        self.evaluate = evaluate
        self.model = str(model)
        self.mode = mode
        self.policy = _POLICIES[mode]
        self.public_contract = {
            str(k): str(v)
            for k, v in dict(public_contract or {}).items()
            if str(v).strip()
        }
        self.max_request_bytes = int(max_request_bytes)
        self.max_observations = int(max_observations)
        self.calls = 0
        self.events: list[dict[str, Any]] = []
        self._attempted = False
        self._scope: tuple[str, str] | None = None

    def bind_run_cancellation(self, event: Any) -> None:
        bind = getattr(self.evaluate, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    def _target_matches(self, task_text: str) -> bool:
        # Public contracts are Markdown/text and may wrap a preregistered marker
        # across line boundaries. Match semantic whitespace, not byte layout.
        normalize = lambda value: " ".join(str(value).lower().split())
        haystack = normalize(
            str(task_text) + "\n" + "\n".join(self.public_contract.values())
        )
        return all(normalize(marker) in haystack for marker in self.policy["markers"])

    def __call__(
        self,
        *,
        task_text: str,
        ledger: ExecutionLedger,
        step: int,
        runtime_identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        projection = str(self.policy["projection"])
        if not self._target_matches(task_text):
            return _empty(
                mode=self.mode, projection=projection,
                status="not_target_task", calls=self.calls,
            )

        run_id = str(runtime_identity.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("selective JUDGE advice requires a run identity")
        task_hash = sha256(str(task_text).encode("utf-8")).hexdigest()
        scope = (run_id, task_hash)
        if self._scope is not None and self._scope != scope:
            raise ValueError("selective JUDGE advice instance cannot cross runs")
        self._scope = scope

        if self._attempted:
            return _empty(
                mode=self.mode, projection=projection,
                status="already_attempted", calls=self.calls,
            )
        if int(step) < int(self.policy["min_step"]):
            return _empty(
                mode=self.mode, projection=projection,
                status="waiting_for_public_evidence", calls=self.calls,
            )

        generation = ledger.task_state_generation()
        observations = []
        for receipt in ledger.all_receipts():
            if (
                receipt.kind in _OBSERVATION_KINDS
                and receipt.success
                and not receipt.state_change
                and ledger.receipt_payload_is_intact(receipt)
                and ledger.receipt_task_state_generation(receipt.receipt_id) == generation
            ):
                row = asdict(receipt)
                observations.append({
                    "receipt_id": receipt.receipt_id,
                    "step": receipt.step,
                    "kind": receipt.kind,
                    "summary": receipt.summary,
                    "payload": row.get("payload") or {},
                })
        observations = observations[-self.max_observations:]
        if not observations:
            return _empty(
                mode=self.mode, projection=projection,
                status="waiting_for_public_evidence", calls=self.calls,
            )

        state = {
            "run_id": run_id,
            "task_hash": task_hash,
            "step": int(step),
            "policy_version": self.mode,
            "task_instruction": str(task_text),
            "public_contract": dict(self.public_contract),
            "recent_public_observations": observations,
        }
        questions: dict[str, Any] = {}
        allowed_by_question: dict[str, tuple[str, ...]] = {}
        for qid, spec in self.policy["questions"].items():
            choices = tuple(spec["choices"])
            allowed_by_question[str(qid)] = choices
            questions[str(qid)] = {
                "type": "choice",
                "instructions": str(spec["instructions"]),
                "criteria": {key: str(spec["criteria"][key]) for key in choices},
            }
        request = {"model": self.model, "state": state, "questions": questions}
        encoded = _canonical(request).encode("utf-8")
        if len(encoded) > self.max_request_bytes:
            self._attempted = True
            self.events.append({
                "step": int(step),
                "status": "abstained",
                "reason": "request_too_large",
                "request_bytes": len(encoded),
            })
            return _empty(
                mode=self.mode, projection=projection,
                status="request_too_large", calls=self.calls,
            )

        self._attempted = True
        self.calls += 1
        event: dict[str, Any] = {
            "step": int(step),
            "status": "pending",
            "request_sha256": sha256(encoded).hexdigest(),
            "request_bytes": len(encoded),
        }
        try:
            raw = self.evaluate(request)
            if not isinstance(raw, Mapping):
                raise ValueError("JUDGE response is not a mapping")
            result = raw.get("result")
            answers: Mapping[str, Any] | None = None
            if isinstance(result, Mapping) and isinstance(result.get("answers"), Mapping):
                answers = result["answers"]
            elif isinstance(raw.get("answers"), Mapping):
                answers = raw["answers"]
            if answers is None:
                raise ValueError("JUDGE response missing typed answers")
            validated = {
                qid: _typed_answer(answers, qid, choices)
                for qid, choices in allowed_by_question.items()
            }
            event["status"] = "ok"
            event["choices"] = {qid: value["choice"] for qid, value in validated.items()}
            self.events.append(event)
            return {
                "schema": SCHEMA,
                "authority": "advisory_only",
                "mode": self.mode,
                "projection": projection,
                "context_pruned": False,
                "status": "advice",
                "calls_total": self.calls,
                "items": [{
                    "head": "selective_judge",
                    "topic": self.mode,
                    "answers": validated,
                    "instruction": (
                        "Advisory only. Use only public evidence. GLM retains full authority "
                        "over whether and how to follow this advice."
                    ),
                }],
            }
        except (RunCancellationRequested, KernelRunTimeout):
            raise
        except Exception as exc:
            event["status"] = "abstained"
            event["error_type"] = type(exc).__name__
            self.events.append(event)
            return _empty(
                mode=self.mode, projection=projection,
                status="judge_abstained", calls=self.calls,
            )
