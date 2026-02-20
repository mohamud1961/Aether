import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from aether.evals.frugal_evals.cli import main as frugal_cli_main
from aether.evals.frugal_evals.task_000_gate import (
    FAIL_CRASH,
    FAIL_NO_FILE,
    FAIL_NO_TOOL,
    FAIL_OVER_BUDGET,
    FAIL_WRONG_CONTENT,
    PASS,
    enforce_task_000_before_stage,
    run_task_000_gate,
)


class TestFrugalTask000Gate(unittest.TestCase):
    def test_mock_passes_consistently_five_times(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"FRUGAL_TASK_000_RUN_ROOT": tmpdir}
            with patch.dict(os.environ, env, clear=False):
                outcomes = []
                for _ in range(5):
                    result = run_task_000_gate(
                        model_id="mock-zombie-v1",
                        adapter_mode="mock",
                        max_steps=5,
                    )
                    outcomes.append((result.outcome, result.reason_code, result.steps_used, round(result.cost_usd_est, 3)))
                    self.assertEqual(result.outcome, PASS)
                    self.assertEqual(result.reason_code, "verifier_passed_within_budget")
                    self.assertTrue(Path(result.result_path).exists())

                self.assertEqual(len(set(outcomes)), 1, "task-000 pass outcome was not deterministic across runs")

    def test_fail_modes_return_actionable_reason_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"FRUGAL_TASK_000_RUN_ROOT": tmpdir}
            with patch.dict(os.environ, env, clear=False):
                cases = [
                    ("mock_no_tool", FAIL_NO_TOOL, "model_responded_text"),
                    ("mock_wrong_content", FAIL_WRONG_CONTENT, "status_content_mismatch"),
                    ("mock_no_file", FAIL_NO_FILE, "status_file_missing"),
                    ("mock_over_budget", FAIL_OVER_BUDGET, "max_steps_exceeded"),
                    ("mock_crash", FAIL_CRASH, "unexpected_error"),
                ]
                for adapter_mode, expected_outcome, expected_reason in cases:
                    with self.subTest(adapter_mode=adapter_mode):
                        result = run_task_000_gate(
                            model_id="mock-zombie-v1",
                            adapter_mode=adapter_mode,
                            max_steps=5,
                        )
                        self.assertEqual(result.outcome, expected_outcome)
                        self.assertEqual(result.reason_code, expected_reason)

    def test_gate_enforcement_blocks_downstream_stage_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"FRUGAL_TASK_000_RUN_ROOT": tmpdir}
            called = {"value": 0}

            def _downstream_stage() -> None:
                called["value"] += 1

            with patch.dict(os.environ, env, clear=False):
                blocked = enforce_task_000_before_stage(
                    model_id="mock-zombie-v1",
                    adapter_mode="mock_no_tool",
                    max_steps=5,
                    downstream_stage=_downstream_stage,
                )
                self.assertFalse(blocked.proceeded)
                self.assertEqual(blocked.gate_result.outcome, FAIL_NO_TOOL)
                self.assertEqual(called["value"], 0)

                passed = enforce_task_000_before_stage(
                    model_id="mock-zombie-v1",
                    adapter_mode="mock",
                    max_steps=5,
                    downstream_stage=_downstream_stage,
                )
                self.assertTrue(passed.proceeded)
                self.assertEqual(passed.gate_result.outcome, PASS)
                self.assertEqual(called["value"], 1)

    def test_cli_task_000_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"FRUGAL_TASK_000_RUN_ROOT": tmpdir}
            with patch.dict(os.environ, env, clear=False):
                with io.StringIO() as stdout:
                    with redirect_stdout(stdout):
                        exit_code = frugal_cli_main(
                            [
                                "task-000",
                                "--model-id",
                                "mock-zombie-v1",
                                "--adapter",
                                "mock",
                            ]
                        )
                    output = stdout.getvalue().strip()

                self.assertEqual(exit_code, 0)
                self.assertIn("PASS", output)

                with io.StringIO() as stdout:
                    with redirect_stdout(stdout):
                        exit_code = frugal_cli_main(
                            [
                                "task-000",
                                "--model-id",
                                "mock-zombie-v1",
                                "--adapter",
                                "mock_no_tool",
                            ]
                        )
                    output = stdout.getvalue().strip()

                self.assertEqual(exit_code, 2)
                self.assertIn("FAIL_NO_TOOL", output)
                self.assertIn("reason=model_responded_text", output)


if __name__ == "__main__":
    unittest.main()
