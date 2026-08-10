from __future__ import annotations

from aether.model_prompts import VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE
from aether.verify_inspection_requests import _verifier_identity_prompt_for
from tests.harness.test_completion_evidence_protocol import _compiled


def test_falsification_doctrine_decomposes_change_and_preservation_obligations() -> None:
    doctrine = VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE.lower()
    assert "separate obligations" in doctrine
    assert "distinct all-safe/no-target fixture" in doctrine
    assert "complete before/after bytes" in doctrine
    assert "mixed fixture" in doctrine
    assert "does not establish the untouched-input identity obligation" in doctrine


def test_falsification_doctrine_requires_representation_boundary_without_prescribing_case() -> None:
    doctrine = VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE.lower()
    assert "representation-sensitive" in doctrine
    assert "semantic-equivalence boundary" in doctrine
    assert "decoding" in doctrine
    assert "normalization" in doctrine
    assert "choose the concrete safe fixture and representation transform yourself" in doctrine


def test_falsification_doctrine_requires_outcome_binding_not_diagnostics() -> None:
    doctrine = VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE.lower()
    assert "outcome-binding" in doctrine
    assert "must fail or return nonzero" in doctrine
    assert "merely printing a false boolean" in doctrine
    assert "cannot establish completion" in doctrine


def test_falsification_doctrine_is_task_generic_and_not_benchmark_specific() -> None:
    doctrine = VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE.lower()
    for forbidden in (
        "html", "javascript", "xss", "iframe", "script tag", "entity encoding",
        "filter.py", "terminal-bench", "benchmark", "hidden test", "test_outputs.py",
    ):
        assert forbidden not in doctrine
    assert "only from the raw task" in doctrine
    assert "current observations" in doctrine
    assert "observed implementation" in doctrine
    assert "do not assume unobserved cases" in doctrine


def test_falsification_doctrine_is_in_stable_verifier_system_prefix() -> None:
    rendered = _verifier_identity_prompt_for(_compiled())
    assert VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE in rendered
    assert rendered.index(VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE) < rendered.index("Task-specific verifier prompt.")


def test_falsification_doctrine_does_not_prescribe_execution_command() -> None:
    doctrine = VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE.lower()
    for forbidden in ("python3", "bash", "pytest", "curl ", "grep ", "sed ", "awk "):
        assert forbidden not in doctrine
