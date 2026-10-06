"""Revision-9.2 trace-aware one-shot JUDGE stuck-state reviewer.

This research-only assistant reads only solver-visible/public state:
- the public task/contract,
- Aether's execution ledger, and
- the exact Chat telemetry journal produced by the same GLM solver.

It never reads a grader, hidden fixtures, solutions, or future observations.  JUDGE
is advisory-only; GLM retains task action and finish authority.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

from .ledger import ExecutionLedger
from .persistent_evidence import is_persistent_admitted_completion_evidence, is_persistent_primary_action_result
from .run_cancellation import RunCancellationRequested
from .run_deadline import KernelRunTimeout

SCHEMA = "aether.semantic_advice.v1"
MODE_HARD_STUCK_TRACE_V1 = "hard_stuck_trace_v1"

_PROGRESS_CHOICES = (
    "productive_progress",
    "local_loop",
    "hypothesis_churn",
    "waiting_on_operation",
    "evidence_gap",
    "uncertain",
)
_STRATEGY_CHOICES = (
    "current_strategy_supported",
    "current_strategy_contradicted",
    "current_strategy_underdetermined",
    "uncertain",
)
_NEXT_MOVE_CHOICES = (
    "run_discriminating_experiment",
    "inspect_authoritative_evidence",
    "wait_for_current_operation",
    "preserve_last_good_candidate",
    "change_strategy",
    "run_public_or_task_authorized_verification",
    "finish_if_authoritatively_verified",
    "uncertain",
)

_INTERNAL_KINDS = frozenset({
    "provider_accounting",
    "thin_deadline_exceeded",
    "thin_parse_error",
    "solver_turn_budget_exhausted",
})
_VERIFICATION_WORDS = (
    "verify", "verification", "test", "pytest", "check", "probe", "smoke",
    "rehearsal", "benchmark",
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        default=str,
    )


def _bounded_text(value: Any, limit: int) -> str:
    text = str(value or "")
    if len(text.encode("utf-8")) <= limit:
        return text
    raw = text.encode("utf-8")
    # Prefer the most recent reasoning/action detail while making truncation explicit.
    tail = raw[-max(0, limit - 64):].decode("utf-8", errors="ignore")
    return "[bounded_prefix_omitted]\n" + tail


def _empty(*, status: str, calls: int, features: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema": SCHEMA,
        "authority": "advisory_only",
        "mode": MODE_HARD_STUCK_TRACE_V1,
        "projection": "hard_stuck_trace_v1",
        "context_pruned": False,
        "status": status,
        "calls_total": int(calls),
        "items": [],
    }
    if features:
        row["trigger_features"] = dict(features)
    return row


def _typed_answer(
    answers: Mapping[str, Any], question_id: str, choices: tuple[str, ...],
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
        if not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError(f"invalid JUDGE probability for {question_id}:{key}")
        clean[key] = number
    if abs(sum(clean.values()) - 1.0) > 0.02:
        raise ValueError(f"invalid JUDGE probability total for {question_id}")
    return {"choice": choice, "probabilities": clean}


def _read_completed_attempts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                outer = json.loads(line)
            except json.JSONDecodeError:
                continue
            attempt: Mapping[str, Any] | None = None
            if isinstance(outer, Mapping) and isinstance(outer.get("attempt"), Mapping):
                attempt = outer["attempt"]
            elif isinstance(outer, Mapping) and outer.get("event_kind") == "provider_attempt":
                attempt = outer
            if not isinstance(attempt, Mapping):
                continue
            if attempt.get("event_kind") != "provider_attempt" or attempt.get("status") != "completed":
                continue
            out.append(dict(attempt))
    return out


def _attempt_projection(attempt: Mapping[str, Any]) -> dict[str, Any]:
    raw = attempt.get("raw_provider_output")
    message: Mapping[str, Any] = {}
    if isinstance(raw, Mapping):
        choices = raw.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
            candidate = choices[0].get("message")
            if isinstance(candidate, Mapping):
                message = candidate
    tool_name = ""
    tool_args = ""
    calls = message.get("tool_calls") if isinstance(message, Mapping) else None
    if isinstance(calls, list) and calls and isinstance(calls[0], Mapping):
        fn = calls[0].get("function")
        if isinstance(fn, Mapping):
            tool_name = str(fn.get("name") or "")
            tool_args = _bounded_text(fn.get("arguments"), 320)
    return {
        "logical_call_id": attempt.get("logical_call_id"),
        "reasoning_content_excerpt": _bounded_text(message.get("reasoning_content"), 900),
        "tool_name": tool_name,
        "tool_arguments_excerpt": tool_args,
        "finish_reason": attempt.get("finish_reason") or attempt.get("provider_finish_reason"),
    }


def _receipt_signature(receipt: Any) -> str:
    payload = getattr(receipt, "payload", {}) or {}
    # Exact mechanically observable signature; no semantic clustering.
    material = {
        "kind": str(getattr(receipt, "kind", "")),
        "payload": payload,
    }
    return sha256(_canonical(material).encode("utf-8")).hexdigest()


def _receipt_projection(receipt: Any, generation: int | None) -> dict[str, Any]:
    payload = getattr(receipt, "payload", {}) or {}
    return {
        "receipt_id": str(getattr(receipt, "receipt_id", "")),
        "step": int(getattr(receipt, "step", 0) or 0),
        "kind": str(getattr(receipt, "kind", "")),
        "success": bool(getattr(receipt, "success", False)),
        "state_change": bool(getattr(receipt, "state_change", False)),
        "task_state_generation": generation,
        "summary": _bounded_text(getattr(receipt, "summary", ""), 320),
        "payload_excerpt": _bounded_text(_canonical(payload), 420),
    }


def _stuckness_features(
    ledger: ExecutionLedger,
    *,
    completed_provider_attempts: int,
    min_provider_attempts: int,
) -> dict[str, Any]:
    receipts = list(ledger.all_receipts())
    current_generation = ledger.task_state_generation()
    recent = [r for r in receipts if str(getattr(r, "kind", "")) not in _INTERNAL_KINDS][-18:]
    current = [
        r for r in recent
        if ledger.receipt_task_state_generation(str(getattr(r, "receipt_id", ""))) == current_generation
    ]

    actionish = [r for r in current if is_persistent_primary_action_result(r)]
    signatures = [_receipt_signature(r) for r in actionish]
    counts = Counter(signatures)
    repeated_signature_count = max(counts.values(), default=0)

    observations = [
        r for r in actionish
        if bool(getattr(r, "success", False)) and not bool(getattr(r, "state_change", False))
    ]
    obs_counts = Counter(_receipt_signature(r) for r in observations)
    repeated_unchanged_probe_count = max(obs_counts.values(), default=0)

    verification_cycles = 0
    for receipt in actionish:
        text = (
            str(getattr(receipt, "summary", "")) + " " +
            _canonical(getattr(receipt, "payload", {}) or {})
        ).lower()
        if any(word in text for word in _VERIFICATION_WORDS):
            verification_cycles += 1

    generation_age_actions = len(actionish)
    pressure_ok = completed_provider_attempts >= min_provider_attempts
    conditions = {
        "repeated_unchanged_probe": repeated_unchanged_probe_count >= 3,
        "state_generation_stall": generation_age_actions >= 6,
        "repeated_action_signature": repeated_signature_count >= 3,
        "repeated_verification_cycles": verification_cycles >= 3,
    }
    return {
        "completed_provider_attempts": completed_provider_attempts,
        "min_provider_attempts": min_provider_attempts,
        "pressure_ok": pressure_ok,
        "task_state_generation": current_generation,
        "state_generation_age_actions": generation_age_actions,
        "repeated_action_signature_count": repeated_signature_count,
        "repeated_unchanged_probe_count": repeated_unchanged_probe_count,
        "verification_debug_cycle_count": verification_cycles,
        "conditions": conditions,
        "triggered": pressure_ok and any(conditions.values()),
    }


class TraceAwareJudgeAdvice:
    """One sparse JUDGE review after deterministic hard-run stuckness."""

    def __init__(
        self,
        evaluate: Callable[[dict[str, Any]], Mapping[str, Any]],
        *,
        model: str,
        telemetry_journal: Path,
        public_contract: Mapping[str, str] | None = None,
        max_request_bytes: int = 16000,
        min_provider_attempts: int = 24,
    ) -> None:
        if not model:
            raise ValueError("exact JUDGE model identity is required")
        if max_request_bytes <= 0 or min_provider_attempts <= 0:
            raise ValueError("positive J-S bounds required")
        self.evaluate = evaluate
        self.model = str(model)
        self.telemetry_journal = Path(telemetry_journal)
        self.public_contract = {
            str(k): str(v)
            for k, v in dict(public_contract or {}).items()
            if str(v).strip()
        }
        self.max_request_bytes = int(max_request_bytes)
        self.min_provider_attempts = int(min_provider_attempts)
        self.calls = 0
        self.events: list[dict[str, Any]] = []
        self._attempted = False
        self._scope: tuple[str, str] | None = None

    def bind_run_cancellation(self, event: Any) -> None:
        bind = getattr(self.evaluate, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    def __call__(
        self,
        *,
        task_text: str,
        ledger: ExecutionLedger,
        step: int,
        runtime_identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        run_id = str(runtime_identity.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("trace-aware JUDGE advice requires run identity")
        task_hash = sha256(str(task_text).encode("utf-8")).hexdigest()
        scope = (run_id, task_hash)
        if self._scope is not None and self._scope != scope:
            raise ValueError("trace-aware JUDGE advice instance cannot cross runs")
        self._scope = scope
        if self._attempted:
            return _empty(status="already_attempted", calls=self.calls)

        completed = _read_completed_attempts(self.telemetry_journal)
        features = _stuckness_features(
            ledger,
            completed_provider_attempts=len(completed),
            min_provider_attempts=self.min_provider_attempts,
        )
        if not features["pressure_ok"]:
            return _empty(status="waiting_for_hard_pressure", calls=self.calls, features=features)
        if not features["triggered"]:
            return _empty(status="no_stuckness_trigger", calls=self.calls, features=features)

        recent_attempts = [_attempt_projection(a) for a in completed[-6:]]
        receipts = [
            r for r in ledger.all_receipts()
            if str(getattr(r, "kind", "")) not in _INTERNAL_KINDS
        ][-10:]
        recent_receipts = [
            _receipt_projection(
                r,
                ledger.receipt_task_state_generation(str(getattr(r, "receipt_id", ""))),
            )
            for r in receipts
        ]
        admitted_completion_ids = [
            str(getattr(r, "receipt_id", ""))
            for r in receipts
            if is_persistent_admitted_completion_evidence(r)
            and ledger.receipt_snapshot_binding_is_current(r)
        ][-5:]

        state = {
            "run_id": run_id,
            "task_hash": task_hash,
            "step": int(step),
            "policy_version": MODE_HARD_STUCK_TRACE_V1,
            "task_instruction": str(task_text),
            "public_contract": dict(self.public_contract),
            "current_state": {
                "task_state_generation": ledger.task_state_generation(),
                "completion_requirements_source": "public_task_and_contract_only",
                "current_authoritative_observation_present": ledger.has_current_authoritative_observation(),
                "latest_admitted_completion_evidence_ids": admitted_completion_ids,
            },
            "recent_solver_attempts": recent_attempts,
            "recent_action_observation_receipts": recent_receipts,
            "progress_features": features,
            "private_truth_available": False,
            "grader_or_solution_visible": False,
        }
        questions = {
            "progress_state": {
                "type": "choice",
                "instructions": (
                    "Classify solver progress using only the supplied public task, recent GLM "
                    "reasoning/actions, receipts, and mechanical progress features."
                ),
                "criteria": {choice: choice.replace("_", " ") for choice in _PROGRESS_CHOICES},
            },
            "strategy_support": {
                "type": "choice",
                "instructions": (
                    "Judge whether the current strategy is supported, contradicted, or "
                    "underdetermined by the supplied public/current evidence."
                ),
                "criteria": {choice: choice.replace("_", " ") for choice in _STRATEGY_CHOICES},
            },
            "best_next_move": {
                "type": "choice",
                "instructions": (
                    "Choose the smallest next move most likely to break an unproductive loop or "
                    "close an evidence gap. Do not assume hidden grader truth."
                ),
                "criteria": {choice: choice.replace("_", " ") for choice in _NEXT_MOVE_CHOICES},
            },
        }
        request = {"model": self.model, "state": state, "questions": questions}
        encoded = _canonical(request).encode("utf-8")
        if len(encoded) > self.max_request_bytes:
            self._attempted = True
            self.events.append({
                "step": int(step),
                "status": "abstained",
                "reason": "core_packet_exceeds_bound",
                "request_bytes": len(encoded),
                "features": features,
            })
            return _empty(status="request_too_large", calls=self.calls, features=features)

        self._attempted = True
        self.calls += 1
        event: dict[str, Any] = {
            "step": int(step),
            "status": "pending",
            "request_sha256": sha256(encoded).hexdigest(),
            "request_bytes": len(encoded),
            "features": features,
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
                "progress_state": _typed_answer(answers, "progress_state", _PROGRESS_CHOICES),
                "strategy_support": _typed_answer(answers, "strategy_support", _STRATEGY_CHOICES),
                "best_next_move": _typed_answer(answers, "best_next_move", _NEXT_MOVE_CHOICES),
            }
            event["status"] = "ok"
            event["choices"] = {key: value["choice"] for key, value in validated.items()}
            self.events.append(event)
            return {
                "schema": SCHEMA,
                "authority": "advisory_only",
                "mode": MODE_HARD_STUCK_TRACE_V1,
                "projection": "hard_stuck_trace_v1",
                "context_pruned": False,
                "status": "advice",
                "calls_total": self.calls,
                "trigger_features": features,
                "items": [{
                    "head": "trace_aware_judge",
                    "topic": MODE_HARD_STUCK_TRACE_V1,
                    "answers": validated,
                    "instruction": (
                        "Advisory only. GLM retains task strategy, action, and finish authority. "
                        "Use only public/current evidence; JUDGE has no grader or solution truth."
                    ),
                }],
            }
        except (RunCancellationRequested, KernelRunTimeout):
            raise
        except Exception as exc:
            event["status"] = "abstained"
            event["error_type"] = type(exc).__name__
            self.events.append(event)
            return _empty(status="judge_abstained", calls=self.calls, features=features)
