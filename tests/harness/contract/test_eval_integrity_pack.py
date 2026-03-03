import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from aether.evals.runner import main as eval_runner_main
from aether.evals.utils.hashes import stable_hash


NULL_EVENT_HASH = "0" * 64
DEFAULT_TrunCATION = {
    "stdout": {
        "truncated": False,
        "size_bytes": 0,
        "captured_bytes": 0,
        "unknown": False,
    },
    "stderr": {
        "truncated": False,
        "size_bytes": 0,
        "captured_bytes": 0,
        "unknown": False,
    },
}


def _build_event(
    *,
    step_id: int,
    event_type: str,
    prev_event_hash: str,
    run_id: str = "run_integrity_fixture",
    **overrides: Any,
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "run_id": run_id,
        "event_type": event_type,
        "step_id": step_id,
        "timestamp": f"2026-02-20T00:00:{step_id:02d}Z",
        "cwd": "/workspace",
        "tool_name": None,
        "tool_args": None,
        "exit_code": None,
        "files_read": [],
        "files_written": [],
        "artifact_refs": [],
        "truncation": DEFAULT_TrunCATION,
        "verifier_run": False,
        "verifier_result": None,
        "triggers_fired": [],
        "trigger_explanation": None,
        "workspace_fingerprint_hash": "ws_hash",
        "dirty_since_last_verify": None,
        "context_pack_hash": None,
        "manifest_hash": None,
        "completion_signals": [],
        "termination_reason": None,
        "checkpoint_ref": None,
        "retry_after_fix": None,
        "recovery_candidate": None,
    }
    event.update(overrides)
    event["prev_event_hash"] = prev_event_hash
    event["event_id"] = stable_hash(
        {key: value for key, value in event.items() if key not in {"event_id", "prev_event_hash"}}
    )
    return event


def _write_run_dir(
    run_dir: Path,
    *,
    include_integrity_report: bool,
    include_tool_surface_profile: bool,
) -> None:
    (run_dir / "artifacts" / "objects").mkdir(parents=True, exist_ok=True)
    prev = NULL_EVENT_HASH

    run_start_overrides: Dict[str, Any] = {}
    if include_tool_surface_profile:
        run_start_overrides["tool_surface_profile"] = {
            "tools": ["run", "request_phase_transition"],
            "interpreters": [],
            "policy_profile": "eval",
        }

    events: List[Dict[str, Any]] = []
    start = _build_event(
        step_id=1,
        event_type="run_START",
        prev_event_hash=prev,
        **run_start_overrides,
    )
    events.append(start)
    prev = start["event_id"]

    end = _build_event(
        step_id=2,
        event_type="run_END",
        prev_event_hash=prev,
        terminal_outcome="SUCCESS",
        summary_reason_code="commit_success",
    )
    events.append(end)

    (run_dir / "event_log.jsonl").write_text(
        "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n",
        encoding="utf-8",
    )

    if include_integrity_report:
        (run_dir / "integrity_report.json").write_text(
            json.dumps(
                {
                    "evaluation_mode": "EVAL",
                    "agent_container_checks": {
                        "tests_path_exists": False,
                        "verifier_artifacts_accessible": False,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )


def _run_integrity_pack(run_dir: Path, out_dir: Path) -> tuple[int, Dict[str, Any]]:
    exit_code = eval_runner_main(
        [
            "--pack",
            "integrity",
            "--run-dir",
            run_dir.as_posix(),
            "--out",
            out_dir.as_posix(),
        ]
    )
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    return exit_code, report


class TestEvalIntegrityPack(unittest.TestCase):
    def test_integrity_pack_passes_minimal_real_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "run_ok"
            out_dir = root / "out_ok"
            _write_run_dir(
                run_dir,
                include_integrity_report=True,
                include_tool_surface_profile=True,
            )

            exit_code, report = _run_integrity_pack(run_dir, out_dir)

            self.assertEqual(exit_code, 0)
            tests = report.get("tests", [])
            self.assertEqual(len(tests), 3)
            self.assertTrue(all(test.get("passed") is True for test in tests))

    def test_integrity_pack_fails_when_integrity_report_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "run_missing_report"
            out_dir = root / "out_missing_report"
            _write_run_dir(
                run_dir,
                include_integrity_report=False,
                include_tool_surface_profile=True,
            )

            exit_code, report = _run_integrity_pack(run_dir, out_dir)

            self.assertEqual(exit_code, 2)
            failures = [test.get("fail_signature") for test in report.get("tests", []) if not test.get("passed")]
            self.assertIn("integrity_report_missing", failures)

    def test_integrity_pack_fails_when_tool_surface_profile_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "run_missing_surface"
            out_dir = root / "out_missing_surface"
            _write_run_dir(
                run_dir,
                include_integrity_report=True,
                include_tool_surface_profile=False,
            )

            exit_code, report = _run_integrity_pack(run_dir, out_dir)

            self.assertEqual(exit_code, 2)
            failures = [test.get("fail_signature") for test in report.get("tests", []) if not test.get("passed")]
            self.assertIn("tool_surface_profile_missing", failures)

    def test_integrity_pack_is_not_applicable_for_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out_dir = root / "out_fixture"

            exit_code = eval_runner_main(
                [
                    "--pack",
                    "integrity",
                    "--fixture",
                    "fixture_contract_success",
                    "--out",
                    out_dir.as_posix(),
                ]
            )
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 0)
            tests = report.get("tests", [])
            self.assertEqual(len(tests), 3)
            self.assertTrue(all(test.get("passed") is True for test in tests))
            for test in tests:
                details = test.get("details", {})
                self.assertEqual(details.get("applicability"), "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
