import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from typing import Any, Dict, List

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, stable_hash
from aether.evals.frugal_evals.chop_shop_search import (
    adapt_t2_external_run,
    build_t1_search_tasks,
    generate_baseline_search_predictions,
    score_search_predictions,
)
from aether.evals.frugal_evals.cli import main as frugal_cli_main


def _append_event(events: List[Dict[str, Any]], payload: Dict[str, Any]) -> None:
    prev_event_hash = events[-1]["event_id"] if events else NULL_EVENT_HASH
    event = dict(payload)
    event["prev_event_hash"] = prev_event_hash
    event["event_id"] = stable_hash(
        {
            key: value
            for key, value in event.items()
            if key not in {"event_id", "prev_event_hash"}
        }
    )
    events.append(event)


def _write_run(run_dir: Path, events: List[Dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "objects").mkdir(parents=True, exist_ok=True)
    (run_dir / "event_log.jsonl").write_text(
        "\n".join(canonical_json_dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


class TestFrugalChopShopSearch(unittest.TestCase):
    def test_baseline_predictor_is_gold_blind(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "tasks.jsonl"
            predictions_path = root / "predictions.jsonl"
            predictions_cli_path = root / "predictions_cli.jsonl"

            tasks = [
                {
                    "task_id": "task_1",
                    "source_run_id": "task_1",
                    "source_tier": "T1",
                    "prompt": "Find parser files",
                    "repo_map": {
                        "format": "file_list.v1",
                        "root": "/tmp/repo",
                        "files": ["src/parser.py", "README.md", "tests/test_parser.py"],
                        "truncation": {
                            "policy": "max_files",
                            "max_files": 2000,
                            "total_files": 3,
                            "truncated": False,
                        },
                    },
                    # Intentionally malformed; prediction generation must not read gold fields.
                    "gold_files": "DO_NOT_READ",
                    "gold_derivation": "trace_derived",
                    "scoring": {"k_values": [5, 10, 20], "metric": "recall_at_k"},
                }
            ]
            tasks_path.write_text(
                "\n".join(canonical_json_dumps(item) for item in tasks) + "\n",
                encoding="utf-8",
            )

            summary = generate_baseline_search_predictions(tasks_path=tasks_path, out_path=predictions_path)
            self.assertEqual(summary["tasks_scored"], 1)
            payload = json.loads(predictions_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["task_id"], "task_1")
            self.assertIn("ranked_files", payload)
            self.assertGreater(len(payload["ranked_files"]), 0)

            exit_code = frugal_cli_main(
                [
                    "predict-search-baseline",
                    "--tasks",
                    tasks_path.as_posix(),
                    "--out",
                    predictions_cli_path.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                predictions_path.read_text(encoding="utf-8"),
                predictions_cli_path.read_text(encoding="utf-8"),
            )

    def test_t1_dataset_builder_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            run_dir = runs_root / "run_alpha"
            workspace = run_dir / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "main.py").write_text("print('x')\n", encoding="utf-8")
            (workspace / "tests").mkdir(parents=True, exist_ok=True)
            (workspace / "tests" / "test_main.py").write_text("def test_main():\n    assert True\n", encoding="utf-8")

            events: List[Dict[str, Any]] = []
            _append_event(
                events,
                {
                    "run_id": "run_alpha",
                    "event_type": "plan_update",
                    "step_id": 1,
                    "timestamp": "2026-02-13T00:00:01Z",
                    "cwd": workspace.as_posix(),
                    "task_spec": {
                        "prompt": "Fix failing test in src/main.py",
                        "workspace_root": workspace.as_posix(),
                    },
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_alpha",
                    "event_type": "tool_call",
                    "step_id": 2,
                    "timestamp": "2026-02-13T00:00:02Z",
                    "cwd": workspace.as_posix(),
                    "tool_name": "run",
                    "tool_args": {"command": ["pytest", "-q"]},
                    "files_read": [
                        (workspace / "src" / "main.py").as_posix(),
                        (workspace / "tests" / "test_main.py").as_posix(),
                    ],
                    "files_written": [(workspace / "src" / "main.py").as_posix()],
                },
            )
            _write_run(run_dir, events)

            out1 = root / "search_tasks_1.jsonl"
            out2 = root / "search_tasks_2.jsonl"

            build_t1_search_tasks(runs_root=runs_root, out_path=out1)
            build_t1_search_tasks(runs_root=runs_root, out_path=out2)
            out_cli = root / "search_tasks_cli.jsonl"
            exit_code = frugal_cli_main(
                [
                    "build-search-tasks",
                    "--runs-root",
                    runs_root.as_posix(),
                    "--out",
                    out_cli.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)

            self.assertEqual(
                hashlib.sha256(out1.read_bytes()).hexdigest(),
                hashlib.sha256(out2.read_bytes()).hexdigest(),
            )

            lines = [line for line in out1.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["task_id"], "run_alpha")
            self.assertEqual(payload["source_tier"], "T1")
            self.assertEqual(payload["gold_derivation"], "trace_derived")
            self.assertEqual(payload["gold_files"], ["src/main.py", "tests/test_main.py"])
            self.assertEqual(payload["scoring"]["k_values"], [5, 10, 20])
            self.assertIn("repo_map", payload)
            self.assertEqual(lines[0], canonical_json_dumps(payload))
            self.assertEqual(out1.read_text(encoding="utf-8"), out_cli.read_text(encoding="utf-8"))

    def test_t1_builder_falls_back_to_baseline_diff_when_trace_gold_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fake_repo = root / "fake_repo"
            run_dir = root / "runs" / "wal-restore_20260212_175404"
            workspace = run_dir / "workspace"
            baseline = fake_repo / "official_tasks" / "wal-restore" / "environment"

            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (baseline / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "wal.py").write_text("print('after')\n", encoding="utf-8")
            (baseline / "src" / "wal.py").write_text("print('before')\n", encoding="utf-8")
            (workspace / "README.md").write_text("workspace\n", encoding="utf-8")
            (baseline / "README.md").write_text("baseline\n", encoding="utf-8")

            events: List[Dict[str, Any]] = []
            _append_event(
                events,
                {
                    "run_id": "run_db_wal",
                    "event_type": "run_START",
                    "step_id": 1,
                    "timestamp": "2026-02-13T00:00:01Z",
                    "cwd": workspace.as_posix(),
                    "task_spec": {
                        "prompt": "Repair db wal behavior in src/wal.py",
                        "workspace_root": workspace.as_posix(),
                    },
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_db_wal",
                    "event_type": "TOOL_CALL",
                    "step_id": 2,
                    "timestamp": "2026-02-13T00:00:02Z",
                    "cwd": workspace.as_posix(),
                    "tool_name": "run",
                    "tool_args": {"command": ["pytest", "-q"]},
                    "files_read": [],
                    "files_written": [],
                },
            )
            _write_run(run_dir, events)

            out_path = root / "search_tasks.jsonl"
            with patch("aether.evals.frugal_evals.chop_shop_search._repo_root", return_value=fake_repo):
                summary = build_t1_search_tasks(runs_root=root / "runs", out_path=out_path)
            self.assertEqual(summary["tasks_written"], 1)

            payload = json.loads(out_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["gold_derivation"], "patch_derived")
            self.assertIn("src/wal.py", payload["gold_files"])

    def test_tier_separated_scoring_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "tasks.jsonl"
            predictions_path = root / "predictions.jsonl"
            report_path = root / "report.json"

            tasks = [
                {
                    "task_id": "task_t1",
                    "source_run_id": "task_t1",
                    "source_tier": "T1",
                    "prompt": "Find relevant files",
                    "repo_map": {
                        "format": "file_list.v1",
                        "root": "/tmp/repo",
                        "files": ["a.py", "b.py"],
                        "truncation": {
                            "policy": "max_files",
                            "max_files": 2000,
                            "total_files": 2,
                            "truncated": False,
                        },
                    },
                    "gold_files": ["a.py"],
                    "gold_derivation": "trace_derived",
                    "scoring": {"k_values": [5, 10, 20], "metric": "recall_at_k"},
                },
                {
                    "task_id": "task_t2",
                    "source_run_id": "task_t2",
                    "source_tier": "T2",
                    "prompt": "Find relevant files",
                    "repo_map": {
                        "format": "file_list.v1",
                        "root": "/tmp/repo",
                        "files": ["x.py", "y.py"],
                        "truncation": {
                            "policy": "max_files",
                            "max_files": 2000,
                            "total_files": 2,
                            "truncated": False,
                        },
                    },
                    "gold_files": ["x.py"],
                    "gold_derivation": "patch_derived",
                    "scoring": {"k_values": [5, 10, 20], "metric": "recall_at_k"},
                },
            ]
            tasks_path.write_text(
                "\n".join(canonical_json_dumps(item) for item in tasks) + "\n",
                encoding="utf-8",
            )
            predictions = [
                {"task_id": "task_t1", "ranked_files": ["a.py", "b.py"]},
                {"task_id": "task_t2", "ranked_files": ["y.py", "x.py"]},
            ]
            predictions_path.write_text(
                "\n".join(canonical_json_dumps(item) for item in predictions) + "\n",
                encoding="utf-8",
            )

            summary = score_search_predictions(
                predictions_path=predictions_path,
                tasks_path=tasks_path,
                report_path=report_path,
            )
            self.assertEqual(summary["tasks_scored"], 2)
            report_cli = root / "report_cli.json"
            exit_code = frugal_cli_main(
                [
                    "score-search",
                    "--predictions",
                    predictions_path.as_posix(),
                    "--tasks",
                    tasks_path.as_posix(),
                    "--report",
                    report_cli.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            report_from_cli = json.loads(report_cli.read_text(encoding="utf-8"))
            self.assertIn("tier_reports", report)
            self.assertIn("T1", report["tier_reports"])
            self.assertIn("T2", report["tier_reports"])
            self.assertEqual(report["tier_reports"]["T1"]["task_count"], 1)
            self.assertEqual(report["tier_reports"]["T2"]["task_count"], 1)
            self.assertEqual(report["tier_reports"]["T1"]["mean_metrics"]["by_k"]["5"]["recall_at_k_mean"], 1.0)
            self.assertEqual(report["tier_reports"]["T2"]["mean_metrics"]["by_k"]["5"]["recall_at_k_mean"], 1.0)
            self.assertEqual(report["tier_reports"]["T2"]["mean_metrics"]["mrr"], 0.5)
            self.assertEqual(report["tier_reports"], report_from_cli["tier_reports"])

    def test_t2_adapter_cli_and_labeling(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            external_run = root / "external_case"
            workspace = external_run / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "pkg").mkdir(parents=True, exist_ok=True)
            (workspace / "pkg" / "module.py").write_text("print('ok')\n", encoding="utf-8")
            (workspace / "README.md").write_text("# title\n", encoding="utf-8")
            (external_run / "prompt.txt").write_text("Resolve bug in pkg/module.py", encoding="utf-8")
            (external_run / "patch.diff").write_text(
                "diff --git a/pkg/module.py b/pkg/module.py\n"
                "--- a/pkg/module.py\n"
                "+++ b/pkg/module.py\n"
                "@@ -1 +1 @@\n"
                "-print('bad')\n"
                "+print('ok')\n",
                encoding="utf-8",
            )

            out_path = root / "t2_tasks.jsonl"
            direct_summary = adapt_t2_external_run(external_run_dir=external_run, out_path=out_path)
            self.assertEqual(direct_summary["tasks_written"], 1)

            payload = json.loads(out_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["source_tier"], "T2")
            self.assertEqual(payload["gold_derivation"], "patch_derived")
            self.assertEqual(payload["gold_files"], ["pkg/module.py"])

            out_cli = root / "t2_tasks_cli.jsonl"
            exit_code = frugal_cli_main(
                [
                    "adapt-t2-search",
                    "--external-run-dir",
                    external_run.as_posix(),
                    "--out",
                    out_cli.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)
            cli_payload = json.loads(out_cli.read_text(encoding="utf-8").strip())
            self.assertEqual(cli_payload["source_tier"], "T2")


if __name__ == "__main__":
    unittest.main()
