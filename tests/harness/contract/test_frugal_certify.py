import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, sha256_text, stable_hash
from aether.evals.frugal_evals.certify import STAGE_NAMES, run_certification
from aether.evals.frugal_evals.cli import main as frugal_cli_main


def _write_cas_json(run_dir: Path, payload: Dict[str, Any]) -> str:
    serialized = canonical_json_dumps(payload)
    content_hash = sha256_text(serialized)
    objects = run_dir / "artifacts" / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    (objects / content_hash).write_text(serialized, encoding="utf-8")
    return content_hash


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


def _build_fixture_run(*, run_dir: Path, run_id: str, file_relpath: str) -> None:
    workspace = run_dir / "workspace"
    file_path = workspace / file_relpath
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("print('ok')\n", encoding="utf-8")
    (workspace / "README.md").write_text("# fixture\n", encoding="utf-8")

    context_pack_ref = _write_cas_json(
        run_dir,
        {
            "POLICY": [{"content": "policy"}],
            "SYSTEM": [{"content": "system"}],
            "CONTRACTS": [{"source_ref": "completion_contract_digest"}],
            "TASK": [{"content": "fix the fixture"}],
            "EVIDENCE": [],
            "STATE": [{"content": "state"}],
            "SCRATCH": [],
        },
    )
    manifest_ref = _write_cas_json(
        run_dir,
        {
            "context_window_tokens": 1024,
            "total_tokens_estimate": 256,
        },
    )
    model_request_ref = _write_cas_json(
        run_dir,
        {
            "model_identifier": "mock-zombie-v1",
            "messages": [{"role": "user", "content": f"fix {file_relpath}"}],
            "tools": [],
            "temperature": 0.0,
            "max_tokens": 64,
        },
    )
    context_slice_ref = _write_cas_json(
        run_dir,
        {
            "version": "context_slice.v1",
            "step_id": 3,
            "timestamp": "2026-02-13T00:00:03Z",
            "context_pack_ref": context_pack_ref,
            "context_pack_hash": context_pack_ref,
            "manifest_ref": manifest_ref,
            "manifest_hash": manifest_ref,
            "model_request_ref": model_request_ref,
            "model_request_hash": model_request_ref,
            "workspace_fingerprint_hash": f"wf-{run_id}",
            "policy_profile_id": "eval",
            "plan_version_id": "1",
            "completion_contract_id": f"completion-{run_id}",
        },
    )

    events: List[Dict[str, Any]] = []
    _append_event(
        events,
        {
            "run_id": run_id,
            "event_type": "run_START",
            "step_id": 1,
            "timestamp": "2026-02-13T00:00:01Z",
            "cwd": workspace.as_posix(),
            "task_spec": {
                "prompt": f"Fix {file_relpath}",
                "workspace_root": workspace.as_posix(),
            },
        },
    )
    _append_event(
        events,
        {
            "run_id": run_id,
            "event_type": "TOOL_CALL",
            "step_id": 2,
            "timestamp": "2026-02-13T00:00:02Z",
            "cwd": workspace.as_posix(),
            "tool_name": "run",
            "tool_args": {"command": ["pytest", "-q"]},
            "files_read": [file_path.as_posix()],
            "files_written": [file_path.as_posix()],
        },
    )
    _append_event(
        events,
        {
            "run_id": run_id,
            "event_type": "context_slice_bound",
            "step_id": 3,
            "timestamp": "2026-02-13T00:00:03Z",
            "cwd": workspace.as_posix(),
            "context_slice_ref": context_slice_ref,
            "context_slice_hash": context_slice_ref,
            "context_pack_ref": context_pack_ref,
            "context_pack_hash": context_pack_ref,
            "manifest_ref": manifest_ref,
            "manifest_hash": manifest_ref,
            "model_request_ref": model_request_ref,
            "model_request_hash": model_request_ref,
            "workspace_fingerprint_hash": f"wf-{run_id}",
            "policy_profile_id": "eval",
            "intent_contract_id": f"intent-{run_id}",
            "completion_contract_id": f"completion-{run_id}",
            "plan_version_id": "1",
        },
    )
    _append_event(
        events,
        {
            "run_id": run_id,
            "event_type": "MODEL_CALL",
            "step_id": 4,
            "timestamp": "2026-02-13T00:00:04Z",
            "cwd": workspace.as_posix(),
            "finish_reason": "tool_use",
        },
    )
    _append_event(
        events,
        {
            "run_id": run_id,
            "event_type": "run_END",
            "step_id": 5,
            "timestamp": "2026-02-13T00:00:05Z",
            "cwd": workspace.as_posix(),
            "termination_reason": "SUCCESS",
        },
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "event_log.jsonl").write_text(
        "\n".join(canonical_json_dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


class TestFrugalCertification(unittest.TestCase):
    def test_chop_shop_baseline_predictions_are_not_oracle_on_fixture_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            _build_fixture_run(run_dir=runs_root / "fixture_001", run_id="run_fixture_001", file_relpath="src/a.py")
            _build_fixture_run(run_dir=runs_root / "fixture_002", run_id="run_fixture_002", file_relpath="src/b.py")

            summary = run_certification(
                runs_root=runs_root,
                out_dir=root / "cert_out",
                selection_prefix="",
                zombie_limit=2,
            )
            report = json.loads(Path(summary["certification_report_path"]).read_text(encoding="utf-8"))
            self.assertEqual(
                report["modes"]["REPLAY"]["chop_shop"]["baseline_predictor"],
                "deterministic_path_overlap_v1",
            )
            self.assertTrue(report["modes"]["REPLAY"]["chop_shop"]["gold_blind"])

            tasks_by_id: Dict[str, Dict[str, Any]] = {}
            for line in (Path(summary["out_dir"]) / "chop_shop_tasks.jsonl").read_text(encoding="utf-8").splitlines():
                payload = json.loads(line)
                tasks_by_id[payload["task_id"]] = payload

            predictions = [
                json.loads(line)
                for line in (Path(summary["out_dir"]) / "chop_shop_predictions.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(predictions), 2)
            for prediction in predictions:
                task = tasks_by_id[prediction["task_id"]]
                self.assertNotEqual(prediction["ranked_files"], task["gold_files"])

    def test_certification_outputs_cost_ledger_fields_and_reconciles_zombie(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            _build_fixture_run(run_dir=runs_root / "fixture_001", run_id="run_fixture_001", file_relpath="src/a.py")
            _build_fixture_run(run_dir=runs_root / "fixture_002", run_id="run_fixture_002", file_relpath="src/b.py")

            summary = run_certification(
                runs_root=runs_root,
                out_dir=root / "cert_out",
                selection_prefix="",
                zombie_limit=2,
            )
            self.assertTrue(Path(summary["certification_report_path"]).exists())
            self.assertTrue(Path(summary["cost_ledger_path"]).exists())
            self.assertTrue(Path(summary["evidence_index_path"]).exists())

            ledger = json.loads(Path(summary["cost_ledger_path"]).read_text(encoding="utf-8"))
            self.assertIn("timestamp", ledger)
            self.assertTrue(str(ledger["timestamp"]).endswith("Z"))
            for stage_name in STAGE_NAMES:
                stage_payload = ledger["stages"][stage_name]
                self.assertGreater(stage_payload["wall_clock_s"], 0.0)

            report = json.loads(Path(summary["certification_report_path"]).read_text(encoding="utf-8"))
            zombie_summary = json.loads(Path(report["artifacts"]["zombie_batch_summary_path"]).read_text(encoding="utf-8"))
            self.assertEqual(report["report_hash"], report["evidence_bearing_hash"])
            self.assertEqual(
                ledger["stages"]["zombie"]["model_calls"],
                zombie_summary["episode_count"],
            )
            self.assertEqual(
                ledger["stages"]["zombie"]["input_tokens"],
                zombie_summary["cumulative_cost_line"]["total_input_tokens"],
            )
            self.assertEqual(
                ledger["stages"]["zombie"]["output_tokens"],
                zombie_summary["cumulative_cost_line"]["total_output_tokens"],
            )

    def test_evidence_bearing_hash_stable_across_out_dirs_and_cli_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_a = root / "runs" / "fixture_a"
            run_b = root / "runs" / "fixture_b"
            _build_fixture_run(run_dir=run_a, run_id="run_fixture_a", file_relpath="pkg/a.py")
            _build_fixture_run(run_dir=run_b, run_id="run_fixture_b", file_relpath="pkg/b.py")

            first = run_certification(
                run_dirs=[run_a, run_b],
                out_dir=root / "cert_out_1",
                zombie_limit=2,
            )
            second = run_certification(
                run_dirs=[run_a, run_b],
                out_dir=root / "cert_out_2",
                zombie_limit=2,
            )

            report_1 = json.loads(Path(first["certification_report_path"]).read_text(encoding="utf-8"))
            report_2 = json.loads(Path(second["certification_report_path"]).read_text(encoding="utf-8"))
            self.assertEqual(report_1["evidence_bearing_hash"], report_2["evidence_bearing_hash"])

            fuzz_1 = json.loads(Path(report_1["artifacts"]["tamper_fuzz_report_path"]).read_text(encoding="utf-8"))
            fuzz_2 = json.loads(Path(report_2["artifacts"]["tamper_fuzz_report_path"]).read_text(encoding="utf-8"))
            self.assertEqual(fuzz_1["report_hash"], fuzz_2["report_hash"])

            out_cli = root / "cert_out_cli"
            exit_code = frugal_cli_main(
                [
                    "run-certification",
                    "--run-dirs",
                    run_a.as_posix(),
                    run_b.as_posix(),
                    "--out-dir",
                    out_cli.as_posix(),
                    "--zombie-limit",
                    "2",
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((out_cli / "certification_report.json").exists())

    def test_selection_supports_phase3_tree_and_records_t1_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            results_root = root / "phase_3_runs" / "results"
            claude_run = results_root / "claude" / "runs" / "wal-restore_20260212_175404"
            gemini_run = results_root / "gemini" / "runs" / "wal-restore_20260212_163820"
            extra_run = results_root / "gemini" / "runs" / "tiny-model-golf_20260212_163908"

            _build_fixture_run(
                run_dir=claude_run,
                run_id="run_claude_db_wal",
                file_relpath="src/recover.py",
            )
            _build_fixture_run(
                run_dir=gemini_run,
                run_id="run_gemini_db_wal",
                file_relpath="src/recover.py",
            )
            _build_fixture_run(
                run_dir=extra_run,
                run_id="run_gemini_extra",
                file_relpath="src/extra.py",
            )

            summary = run_certification(
                runs_root=results_root,
                out_dir=root / "cert_out",
                selection_prefix="wal-restore_",
                max_runs=2,
                zombie_limit=2,
            )
            selection = json.loads((Path(summary["out_dir"]) / "run_selection.json").read_text(encoding="utf-8"))
            self.assertEqual(selection["n"], 2)
            self.assertEqual(selection["tier_labels"]["T1"], 2)
            self.assertEqual(selection["tier_labels"]["T2"], 0)
            self.assertEqual(selection["selected_run_dirs"], sorted(selection["selected_run_dirs"]))
            self.assertTrue(selection["selection_rule"].startswith("recursive_sorted_with_prefix_wal-restore_"))
            self.assertIn("limited_to_2", selection["selection_rule"])
            self.assertEqual(len(selection["selected_runs"]), 2)

            providers = {item["provider"] for item in selection["selected_runs"]}
            self.assertEqual(providers, {"claude", "gemini"})
            for item in selection["selected_runs"]:
                self.assertEqual(item["source_tier"], "T1")
                self.assertEqual(item["task_name"], "wal-restore")
                self.assertTrue(item["existing_cas_roots"])
                self.assertTrue(item["missing_cas_roots"])

            report = json.loads(Path(summary["certification_report_path"]).read_text(encoding="utf-8"))
            self.assertEqual(report["corpus"]["tier_labels"]["T1"], 2)
            self.assertGreater(report["corpus"]["missing_cas_roots_total"], 0)
            for run_summary in report["modes"]["REAL"]["runs"]:
                self.assertEqual(run_summary["source_tier"], "T1")
                self.assertIn("missing_cas_roots", run_summary)


if __name__ == "__main__":
    unittest.main()
