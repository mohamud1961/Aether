from __future__ import annotations

import argparse

from aether.criteria_mode import (
    COMPLETE_V1, CONTROL, CRITERIA_MODE_ENV, build_criteria_mode_launch_binding,
    resolve_criteria_mode,
)
from aether.challenger_runtime.progress_question import split_criteria


def test_default_mode_retains_existing_line_wrapped_fragment() -> None:
    text = "The compiler must\nproduce a runnable output after validating its inputs."
    assert resolve_criteria_mode(environ={}) == CONTROL
    assert split_criteria(text, fallback=False) == [
        {"criterion_id": "C1", "text": "The compiler must"},
        {"criterion_id": "C2", "text": "produce a runnable output after validating its inputs."},
    ]


def test_complete_v1_joins_wrapped_clause_and_keeps_predicate() -> None:
    text = "The compiler must\nproduce a runnable output after validating its inputs."
    criteria = split_criteria(text, fallback=False, mode=COMPLETE_V1)
    assert criteria == [{
        "criterion_id": "C1",
        "text": "The compiler must produce a runnable output after validating its inputs.",
    }]
    assert "must produce" in criteria[0]["text"]
    assert len(criteria[0]["text"].split()) >= 6


def test_complete_v1_joins_wrapped_bullet_clause() -> None:
    text = "- The compiler must\n  produce a portable binary from the validated inputs."
    assert split_criteria(text, fallback=False, mode=COMPLETE_V1) == [{
        "criterion_id": "C1",
        "text": "- The compiler must produce a portable binary from the validated inputs.",
    }]


def test_complete_v1_splits_complete_sentences_and_rejects_modal_fragment() -> None:
    text = (
        "The compiler must produce a portable binary.\n"
        "The command must.\n"
        "The verifier must report each result with a clear status."
    )
    assert [row["text"] for row in split_criteria(text, fallback=False, mode=COMPLETE_V1)] == [
        "The compiler must produce a portable binary.",
        "The verifier must report each result with a clear status.",
    ]


def test_complete_v1_rejects_dangling_predicates_and_fallback_fragments() -> None:
    fragments = (
        "The generated file must contain",
        "The runner must ensure",
        "The final result needs to be",
    )
    for text in fragments:
        assert split_criteria(text, fallback=False, mode=COMPLETE_V1) == []
        assert split_criteria(text, mode=COMPLETE_V1) == []


def test_complete_v1_splits_lowercase_sentences_without_splitting_abbreviations() -> None:
    text = "Dr. smith must preserve every source comment. the tool should report parse errors."
    assert [row["text"] for row in split_criteria(text, fallback=False, mode=COMPLETE_V1)] == [
        "Dr. smith must preserve every source comment.",
        "the tool should report parse errors.",
    ]


def test_complete_v1_keeps_complete_prohibition_clause() -> None:
    text = "Do not remove the error reporting field from the generated output."
    assert split_criteria(text, fallback=False, mode=COMPLETE_V1) == [{
        "criterion_id": "C1", "text": text,
    }]


def test_selector_is_opt_in_and_launch_binding_records_treatment() -> None:
    parser = argparse.ArgumentParser()
    from aether.criteria_mode import add_criteria_mode_argument

    add_criteria_mode_argument(parser)
    assert parser.parse_args([]).criteria_mode == CONTROL
    assert build_criteria_mode_launch_binding(CONTROL) == {
        "criteria_mode": CONTROL, "env": {}, "manifest": {},
    }
    treatment = build_criteria_mode_launch_binding(COMPLETE_V1)
    assert treatment["env"] == {CRITERIA_MODE_ENV: COMPLETE_V1}
    assert treatment["manifest"] == {"criteria_mode": COMPLETE_V1}


def test_complete_v1_mode_can_be_selected_from_runtime_environment(monkeypatch) -> None:
    text = "The compiler must\nproduce a runnable output after validating its inputs."
    monkeypatch.setenv(CRITERIA_MODE_ENV, COMPLETE_V1)
    assert resolve_criteria_mode(environ={CRITERIA_MODE_ENV: COMPLETE_V1}) == COMPLETE_V1
    assert split_criteria(text, fallback=False, mode=None) == split_criteria(
        text, fallback=False, mode=COMPLETE_V1,
    )
