from __future__ import annotations

import tempfile

from aether.runners.docker_runner import run_tbench_task


class HonestCallable:
    def preflight_request(self, *, max_output_tokens: int, logical_role: str):
        return {
            "provider": "test-provider",
            "model": "test-model",
            "provider_role": logical_role,
            "effort": "low",
            "max_output_tokens": max_output_tokens,
            "background": True,
        }

    def __call__(self, messages, *, max_output_tokens=8000):
        raise AssertionError("this test must stop before any model call")


class ClampingCallable(HonestCallable):
    def __init__(self) -> None:
        self.called = False

    def preflight_request(self, *, max_output_tokens: int, logical_role: str):
        row = super().preflight_request(
            max_output_tokens=max_output_tokens,
            logical_role=logical_role,
        )
        if logical_role == "solver":
            row["max_output_tokens"] = 1200
        return row

    def __call__(self, messages, *, max_output_tokens=8000):
        self.called = True
        raise AssertionError("model call must not happen")


def test_runner_rejects_solver_output_budget_mismatch_before_docker_or_model() -> None:
    architect = HonestCallable()
    solver = ClampingCallable()
    verifier = HonestCallable()
    with tempfile.TemporaryDirectory() as task_dir:
        record = run_tbench_task(
            task_dir=task_dir,
            image="image-that-must-not-be-used",
            architect_model=architect,
            solver_model=solver,
            verifier_model=verifier,
            architect_mode="architect_v3",
        )
    assert record["status"] == "error"
    assert record["error"] == "model_request_output_budget_mismatch"
    assert "16000" in record["error_detail"]
    assert "1200" in record["error_detail"]
    assert solver.called is False


class ForbiddenArchitectPreflight(HonestCallable):
    def __init__(self) -> None:
        self.preflight_called = False

    def preflight_request(self, *, max_output_tokens: int, logical_role: str):
        self.preflight_called = True
        raise AssertionError("PERSISTENT V0 must not preflight an Architect request")


def test_persistent_runner_omits_architect_from_model_preflight() -> None:
    architect = ForbiddenArchitectPreflight()
    solver = ClampingCallable()
    verifier = HonestCallable()
    with tempfile.TemporaryDirectory() as task_dir:
        record = run_tbench_task(
            task_dir=task_dir,
            image="image-that-must-not-be-used",
            architect_model=architect,
            solver_model=solver,
            verifier_model=verifier,
            architect_mode="persistent_v0",
        )
    assert record["status"] == "error"
    assert record["error"] == "model_request_output_budget_mismatch"
    assert architect.preflight_called is False
    assert solver.called is False
