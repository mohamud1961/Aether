from __future__ import annotations

import json
from typing import Any

import pytest

from aether.architect_review import (
    build_architect_finalizer_packet,
    build_architect_review_packet,
    parse_architect_review_report,
)
from aether.workbench_hooks import WorkbenchArchitect
from tests.harness.test_architect_structured_output import _canonical_config


def _pass_review() -> dict[str, Any]:
    return {
        "review_status": "pass",
        "inventory": [],
        "findings": [],
        "strengths": ["Candidate matches the visible task."],
        "finalizer_directives": [],
    }


def _revision_review() -> dict[str, Any]:
    return {
        "review_status": "needs_revision",
        "inventory": [{
            "fact": "/app/output",
            "owner": None,
            "requirement": None,
            "task_basis": "The visible task names /app/output.",
            "candidate_status": "missing",
            "candidate_observation": "No visible_contract row names /app/output.",
        }],
        "findings": [{
            "finding_id": "missing-output",
            "category": "contract_omission",
            "severity": "major",
            "task_basis": "The visible task names /app/output.",
            "candidate_observation": "The candidate omits it.",
            "risk": "Completion may pass while the required destination is absent.",
            "required_correction": "Represent the named destination exactly once.",
        }],
        "strengths": ["Existing bindings are exact."],
        "finalizer_directives": ["Preserve exact existing bindings."],
    }


def test_review_parser_accepts_closed_pass_and_revision_reports() -> None:
    assert parse_architect_review_report(json.dumps(_pass_review())) == _pass_review()
    assert parse_architect_review_report(json.dumps(_revision_review())) == _revision_review()


@pytest.mark.parametrize("mutate, match", [
    (lambda x: x.update({"extra": True}), "fields mismatch"),
    (lambda x: x.update({"review_status": "pass", "findings": _revision_review()["findings"]}), "pass review cannot contain findings"),
    (lambda x: x.update({"review_status": "needs_revision", "findings": []}), "must contain at least one finding"),
    (lambda x: x.update({"findings": [*_revision_review()["findings"], *_revision_review()["findings"]]}), "finding_id values must be unique"),
])
def test_review_parser_fails_closed(mutate, match: str) -> None:
    report = _revision_review()
    mutate(report)
    with pytest.raises(ValueError, match=match):
        parse_architect_review_report(json.dumps(report))


def test_review_and_finalizer_packets_preserve_exact_inputs() -> None:
    request = {"schema_version": "architect_request.v2", "task": {"prompt": "visible task"}}
    candidate = _canonical_config()
    review = _revision_review()
    review_packet = build_architect_review_packet(request, candidate)
    finalizer_packet = build_architect_finalizer_packet(request, candidate, review)
    assert review_packet["architect_request"] == request
    assert review_packet["candidate_config"] == candidate
    assert "evaluator" not in json.dumps(review_packet).lower()
    assert finalizer_packet["architect_request"] == request
    assert finalizer_packet["candidate_config"] == candidate
    assert finalizer_packet["independent_review"] == review


def test_reviewer_pass_returns_original_candidate_without_replacement() -> None:
    candidate = _canonical_config()
    architect_calls: list[list[dict[str, str]]] = []
    reviewer_calls: list[list[dict[str, str]]] = []

    def architect_model(messages, *, max_output_tokens):
        architect_calls.append(messages)
        return json.dumps(candidate)

    def reviewer_model(messages, *, max_output_tokens):
        reviewer_calls.append(messages)
        return json.dumps(_pass_review())

    architect = WorkbenchArchitect(architect_model, review_model=reviewer_model)
    config, errors = architect.configure({"schema_version": "architect_request.v2", "task": {"prompt": "visible task"}})
    assert config is not None and errors == []
    assert config.expected_steps == candidate["expected_steps"]
    assert architect.last_review_report == _pass_review()
    assert len(architect_calls) == 1
    assert len(reviewer_calls) == 1
    assert architect.review_calls == 1
    assert architect.finalizer_calls == 0
    assert architect.replacement_calls == 0
    packet = json.loads(reviewer_calls[0][1]["content"])
    assert packet["candidate_config"] == candidate


def test_needs_revision_runs_one_finalizer_and_consumes_shared_replacement_budget() -> None:
    candidate = _canonical_config()
    replacement = _canonical_config()
    replacement["expected_steps"] = 9
    architect_outputs = [json.dumps(candidate), json.dumps(replacement)]
    reviewer_outputs = [json.dumps(_revision_review())]

    architect_budgets: list[int] = []

    def architect_model(messages, *, max_output_tokens):
        architect_budgets.append(max_output_tokens)
        return architect_outputs.pop(0)

    def reviewer_model(messages, *, max_output_tokens):
        return reviewer_outputs.pop(0)

    architect = WorkbenchArchitect(architect_model, review_model=reviewer_model)
    config, errors = architect.configure({"schema_version": "architect_request.v2", "task": {"prompt": "visible task"}})
    assert config is not None and errors == []
    assert config.expected_steps == 9
    assert architect.review_calls == 1
    assert architect.finalizer_calls == 1
    assert architect.replacement_calls == 1
    assert architect_budgets == [24000, 64000]
    assert architect.last_review_report == _revision_review()
    second, second_errors = architect.correct(
        {"schema_version": "architect_request.v2"},
        previous_output=json.dumps(candidate),
        findings=["compile:ValueError:still invalid"],
    )
    assert second is None
    assert second_errors == ["workbench architect replacement limit exhausted"]


def test_malformed_review_and_malformed_finalizer_fail_closed() -> None:
    candidate = _canonical_config()

    def candidate_model(messages, *, max_output_tokens):
        return json.dumps(candidate)

    bad_review = WorkbenchArchitect(
        candidate_model,
        review_model=lambda messages, max_output_tokens: json.dumps({"review_status": "pass"}),
    )
    config, errors = bad_review.configure({"schema_version": "architect_request.v2"})
    assert config is None
    assert any("architect review/finalization failed" in item for item in errors)

    outputs = [json.dumps(candidate), "not-json"]
    bad_finalizer = WorkbenchArchitect(
        lambda messages, max_output_tokens: outputs.pop(0),
        review_model=lambda messages, max_output_tokens: json.dumps(_revision_review()),
    )
    config, errors = bad_finalizer.configure({"schema_version": "architect_request.v2"})
    assert config is None
    assert bad_finalizer.review_calls == 1
    assert bad_finalizer.finalizer_calls == 1
    assert bad_finalizer.replacement_calls == 1
    assert errors


def test_reviewer_pass_preserves_candidate_parse_warnings() -> None:
    candidate = _canonical_config()
    candidate["verification_policy"]["visible_smoke_tests"] = [{"type": "grader_clone"}]

    architect = WorkbenchArchitect(
        lambda messages, max_output_tokens: json.dumps(candidate),
        review_model=lambda messages, max_output_tokens: json.dumps(_pass_review()),
    )
    config, errors = architect.configure({"task_prompt": "Write out.txt"})
    assert config is not None
    assert errors
    assert architect.last_warning_codes
    assert architect.review_calls == 1
    assert architect.finalizer_calls == 0
