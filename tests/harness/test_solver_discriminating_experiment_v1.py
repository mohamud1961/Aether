from __future__ import annotations

from pathlib import Path

import pytest

from aether.envmap_builder import build_envmap_from_task
from aether.persistent_runtime import (
    DISCRIMINATING_EXPERIMENT_GUIDANCE,
    build_persistent_runtime,
)


def _env(tmp_path: Path):
    (tmp_path / "instruction.md").write_text("Create result.txt with the requested value.", encoding="utf-8")
    return build_envmap_from_task(
        str(tmp_path),
        "Create result.txt with the requested value.",
        workspace_root="/app",
        projection_mode="factual_only",
    )


def _sections(compiled) -> list[tuple[str, str]]:
    return list(compiled.stable_prefix_sections)


def test_control_mode_is_byte_identical_to_implicit_baseline(tmp_path: Path) -> None:
    env = _env(tmp_path)
    implicit = build_persistent_runtime(env)
    explicit = build_persistent_runtime(env, solver_reasoning_mode="control")
    assert implicit.compiled is not None
    assert explicit.compiled is not None
    assert implicit.compiled.stable_prefix_sections == explicit.compiled.stable_prefix_sections
    assert implicit.compiled.config_realization == explicit.compiled.config_realization
    assert "solver_reasoning_mode" not in implicit.compiled.config_realization
    assert not any(name == "solver_reasoning_treatment" for name, _ in _sections(implicit.compiled))


def test_treatment_adds_exactly_one_model_facing_section(tmp_path: Path) -> None:
    env = _env(tmp_path)
    baseline = build_persistent_runtime(env, solver_reasoning_mode="control")
    treated = build_persistent_runtime(env, solver_reasoning_mode="discriminating_experiment_v1")
    assert baseline.compiled is not None
    assert treated.compiled is not None

    baseline_sections = _sections(baseline.compiled)
    treated_sections = _sections(treated.compiled)
    added = [row for row in treated_sections if row not in baseline_sections]
    assert added == [("solver_reasoning_treatment", DISCRIMINATING_EXPERIMENT_GUIDANCE)]
    assert [row for row in treated_sections if row[0] != "solver_reasoning_treatment"] == baseline_sections
    assert treated.compiled.config_realization["solver_reasoning_mode"] == "discriminating_experiment_v1"
    assert treated.compiled.task_prompt == baseline.compiled.task_prompt
    assert treated.compiled.selected_capability_ids() == baseline.compiled.selected_capability_ids()
    assert treated.compiled.action_schema == baseline.compiled.action_schema
    assert treated.compiled.model_verifier_policy == baseline.compiled.model_verifier_policy


def test_treatment_keeps_frontier_as_semantic_authority(tmp_path: Path) -> None:
    env = _env(tmp_path)
    treated = build_persistent_runtime(env, solver_reasoning_mode="discriminating_experiment_v1")
    assert treated.compiled is not None
    text = dict(treated.compiled.stable_prefix_sections)["solver_reasoning_treatment"]
    assert "You own the hypothesis, experiment, interpretation, and decision" in text
    assert "raw task" in text
    assert "observed reality" in text
    assert "let the observed result influence your next decision" in text
    assert "review" not in text.lower()
    assert "verifier" not in text.lower()
    assert "requirements ledger" not in text.lower()


def test_unknown_reasoning_mode_fails_closed(tmp_path: Path) -> None:
    env = _env(tmp_path)
    with pytest.raises(ValueError, match="unsupported Solver reasoning mode"):
        build_persistent_runtime(env, solver_reasoning_mode="mystery")


def test_kernel_rejects_unknown_reasoning_mode() -> None:
    from aether.kernel import AetherNextKernel

    with pytest.raises(ValueError, match="unsupported Solver reasoning mode"):
        AetherNextKernel(solver_reasoning_mode="mystery")


def test_harbor_h3_selector_is_default_off_and_factory_bound(monkeypatch) -> None:
    import aether.harbor_runtime as harbor

    monkeypatch.delenv(harbor.H3_SOLVER_REASONING_ARM_ENV, raising=False)
    assert harbor.selected_h3_solver_reasoning_mode(harbor.build_selected_frontier_models) == "control"

    monkeypatch.setenv(
        harbor.H3_SOLVER_REASONING_ARM_ENV,
        harbor.H3_DISCRIMINATING_EXPERIMENT_ARM,
    )
    assert (
        harbor.selected_h3_solver_reasoning_mode(harbor.build_selected_frontier_models)
        == "discriminating_experiment_v1"
    )
    # Non-production/custom model factories do not silently inherit the Frontier research treatment.
    assert harbor.selected_h3_solver_reasoning_mode(lambda: None) == "control"


def test_harbor_h3_selector_rejects_unknown_arm(monkeypatch) -> None:
    import aether.harbor_runtime as harbor

    monkeypatch.setenv(harbor.H3_SOLVER_REASONING_ARM_ENV, "unknown")
    with pytest.raises(RuntimeError, match=harbor.H3_SOLVER_REASONING_ARM_ENV):
        harbor.selected_h3_solver_reasoning_mode(harbor.build_selected_frontier_models)
