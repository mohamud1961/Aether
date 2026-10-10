from __future__ import annotations

import pytest

from aether import harbor_runtime as hr


def test_prefix_renderer_defaults_to_incumbent_for_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(hr.SOLVER_PREFIX_RENDERER_ENV, raising=False)
    assert hr.selected_solver_prefix_renderer(hr.build_selected_frontier_models) == hr.SOLVER_PREFIX_RENDERER_CONTROL


def test_explicit_minimal_prefix_is_available_only_on_production_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(hr.SOLVER_PREFIX_RENDERER_ENV, hr.SOLVER_PREFIX_RENDERER_MINIMAL)
    assert hr.selected_solver_prefix_renderer(hr.build_selected_frontier_models) == hr.SOLVER_PREFIX_RENDERER_MINIMAL

    def offline_factory():
        raise AssertionError("factory should not be invoked")

    assert hr.selected_solver_prefix_renderer(offline_factory) == hr.SOLVER_PREFIX_RENDERER_CONTROL


def test_invalid_production_prefix_renderer_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(hr.SOLVER_PREFIX_RENDERER_ENV, "not-a-renderer")
    with pytest.raises(RuntimeError, match=hr.SOLVER_PREFIX_RENDERER_ENV):
        hr.selected_solver_prefix_renderer(hr.build_selected_frontier_models)


def test_runtime_identity_records_explicit_prefix_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    class Env:
        task_metadata = {}

        def digest(self) -> str:
            return "env-digest"

    class Context:
        metadata = {}
        context_id = "ctx"

    monkeypatch.setenv(hr.SOLVER_PREFIX_RENDERER_ENV, hr.SOLVER_PREFIX_RENDERER_MINIMAL)
    identity = hr._runtime_identity(Context(), Env(), model_factory=hr.build_selected_frontier_models)
    assert identity["research_solver_prefix_renderer"] == hr.SOLVER_PREFIX_RENDERER_MINIMAL
    assert identity["research_solver_prefix_renderer_authority"] == hr.SOLVER_PREFIX_RENDERER_ENV
