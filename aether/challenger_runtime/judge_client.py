"""Wire adapter from CHALLENGER typed questions to the direct JUDGE transport.

The adapter is the only place that knows the judge request shape. The
transport (``HttpJudgeTransport`` in production, a fake in tests) is injected.
JUDGE sees the public task text, the solver's card, and solver-produced evidence
views only; no Aether-owned mechanical fact is ever put to it as a question.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Mapping

MAX_TASK_CHARS = 3000
MAX_REQUEST_BYTES = 15_000
_VIEW_LIMITS = (500, 250, 120)

CHOICE_DESCRIPTIONS: Mapping[str, str] = {
    "direct_and_current": "The cited evidence directly shows the criterion holds in the current task state.",
    "indirect": "The cited evidence only bears on the criterion indirectly.",
    "self_written_check_only": "Only a check or script the solver wrote supports it; nothing independent does.",
    "none": "No cited evidence bears on the criterion.",
    "contradicted": "Cited evidence shows the criterion does not hold.",
}

Transport = Callable[[dict[str, Any]], Mapping[str, Any]]


class JudgeClient:
    """``QuestionEvaluator`` over an injected JUDGE transport."""

    def __init__(self, transport: Transport, *, model: str, raw_task: str,
                 progress_transport: Transport | None = None) -> None:
        if not model.strip():
            raise ValueError("JUDGE model must be non-empty")
        self._transport = transport
        self._progress_transport = progress_transport
        self._model = model
        self._raw_task = raw_task[:MAX_TASK_CHARS]
        self.last_request_bytes = 0  # size of the most recent request put on the wire

    @property
    def model(self) -> str:
        return self._model

    @property
    def raw_task(self) -> str:
        return self._raw_task

    def __call__(
        self, state: Mapping[str, Any], questions: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Mapping[str, Any]]:
        criteria_text = {
            str(row["criterion_id"]): str(row["text"]) for row in state.get("criteria", ())
        }
        wire_questions = {
            str(qid): _wire_question(spec, criteria_text) for qid, spec in questions.items()
        }
        cited = sorted({ref for spec in questions.values() for ref in spec.get("evidence_refs", ())})
        evidence = state.get("visible_evidence", {})
        request = self._fit({
            "model": self._model,
            "state": {
                "schema": state.get("schema"),
                "raw_task": self._raw_task,
                "criteria": list(state.get("criteria", ())),
                "claim_card": state.get("claim_card"),
                "visible_evidence": {},
            },
            "questions": wire_questions,
        }, {ref: str(evidence.get(ref, "")) for ref in cited})
        return self._answers(request)

    def send_prepared(self, request: dict[str, Any], *, max_bytes: int) -> Mapping[str, Mapping[str, Any]]:
        """Send an already-fitted request (artifact-evidence path); the caller owns its size bound."""
        if _request_bytes(request) > max_bytes:
            raise ValueError("CHALLENGER JUDGE request exceeds the declared byte bound")
        return self._answers(request)

    def send_progress_prepared(
        self, request: dict[str, Any], *, max_bytes: int,
    ) -> Mapping[str, Mapping[str, Any]]:
        """Use the checkpoint-only transport and its independent per-run call/cost cap."""
        if self._progress_transport is None:
            raise ValueError("progress-checkpoint transport is not configured")
        if _request_bytes(request) > max_bytes:
            raise ValueError("progress checkpoint request exceeds the declared byte bound")
        return self._answers_with(self._progress_transport, request)

    def _answers(self, request: dict[str, Any]) -> Mapping[str, Mapping[str, Any]]:
        self.last_request_bytes = _request_bytes(request)
        return self._extract_answers(self._transport(request))

    def _answers_with(self, transport: Transport, request: dict[str, Any]) -> Mapping[str, Mapping[str, Any]]:
        self.last_progress_request_bytes = _request_bytes(request)
        return self._extract_answers(transport(request))

    @staticmethod
    def _extract_answers(response: Any) -> Mapping[str, Mapping[str, Any]]:
        if not isinstance(response, Mapping):
            raise ValueError("JUDGE response is not a mapping")
        result = response.get("result")
        answers = result.get("answers") if isinstance(result, Mapping) else None
        if answers is None:
            answers = response.get("answers")
        if not isinstance(answers, Mapping):
            raise ValueError("JUDGE response does not contain answers")
        return answers

    @staticmethod
    def _fit(request: dict[str, Any], views: Mapping[str, str]) -> dict[str, Any]:
        for limit in _VIEW_LIMITS:
            request["state"]["visible_evidence"] = {ref: view[:limit] for ref, view in views.items()}
            if _request_bytes(request) <= MAX_REQUEST_BYTES:
                return request
        raise ValueError("CHALLENGER JUDGE request exceeds the declared byte bound")


def _request_bytes(request: Mapping[str, Any]) -> int:
    return len(json.dumps(request, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8"))


def _wire_question(spec: Mapping[str, Any], criteria_text: Mapping[str, str]) -> dict[str, Any]:
    details = dict(spec.get("choice_details") or {})
    parts = [str(spec["relation"])]
    criterion_id = str(spec.get("criterion_id") or "")
    if criterion_id:
        parts.append(f"Criterion {criterion_id}: {criteria_text.get(criterion_id, '')}")
    if spec.get("context_text"):
        parts.append(str(spec["context_text"]))
    refs = list(spec.get("evidence_refs", ()))
    if refs:
        parts.append("Cited evidence refs (see state.visible_evidence): " + ", ".join(refs))
    return {
        "type": "choice",
        "instructions": "\n".join(parts),
        "criteria": {
            str(choice): str(
                details.get(choice) or CHOICE_DESCRIPTIONS.get(choice)
                or (f"Rank {choice} (1 = best explains the stated symptom)" if str(choice).isdigit() else choice)
            )
            for choice in spec["choices"]
        },
    }
