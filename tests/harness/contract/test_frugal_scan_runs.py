import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, sha256_text, stable_hash
from aether.evals.frugal_evals.cli import main as frugal_cli_main
from aether.evals.frugal_evals.scan_runs import run_scan_suite


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


def _build_valid_run(*, run_dir: Path, run_id: str, file_relpath: str) -> None:
    workspace = run_dir / "workspace"
    file_path = workspace / file_relpath
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("print('ok')\n", encoding="utf-8")

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
            "event_type": "run_END",
            "step_id": 4,
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


def _build_alias_only_run(*, run_dir: Path, run_id: str) -> None:
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "objects").mkdir(parents=True, exist_ok=True)

    events: List[Dict[str, Any]] = []
    _append_event(
        events,
        {
            "run_id": run_id,
            "event_type": "state_transition",
            "step_id": 1,
            "timestamp": "2026-02-13T00:00:01Z",
            "cwd": workspace.as_posix(),
            "to_phase": "EXPLORE",
        },
    )
    _append_event(
        events,
        {
            "run_id": run_id,
            "event_type": "run_END",
            "step_id": 2,
            "timestamp": "2026-02-13T00:00:02Z",
            "cwd": workspace.as_posix(),
            "termination_reason": "FAILED",
        },
    )
    (run_dir / "event_log.jsonl").write_text(
        "\n".join(canonical_json_dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


class TestFrugalScanRuns(unittest.TestCase):
    def test_scan_runs_outputs_and_no_internal_exception_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            _build_valid_run(run_dir=runs_root / "valid_001", run_id="run_valid_001", file_relpath="src/a.py")
            _build_alias_only_run(run_dir=runs_root / "alias_001", run_id="run_alias_001")

            summary = run_scan_suite(runs_root=runs_root, out_dir=root / "scan_out")
            self.assertEqual(summary["run_count"], 2)

            strict = json.loads(Path(summary["strict_parse_scan_path"]).read_text(encoding="utf-8"))
            ingest = json.loads(Path(summary["ingest_compatibility_scan_path"]).read_text(encoding="utf-8"))
            episode = json.loads(Path(summary["episode_extraction_scan_path"]).read_text(encoding="utf-8"))
            self.assertEqual(strict["summary"]["internal_exception_count"], 0)
            self.assertEqual(ingest["summary"]["internal_exception_count"], 0)
            self.assertEqual(episode["summary"]["internal_exception_count"], 0)

            strict_errors = {item["error_code"] for item in strict["summary"]["top_error_buckets"]}
            self.assertIn("unknown_event_type", strict_errors)

            episode_error_codes = {
                entry["error_code"]
                for entry in episode["entries"]
                if entry.get("error_code")
            }
            self.assertNotIn("internal_attribute_error", episode_error_codes)

    def test_scan_runs_summary_stable_across_reruns_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            _build_valid_run(run_dir=runs_root / "valid_001", run_id="run_valid_001", file_relpath="src/a.py")
            _build_alias_only_run(run_dir=runs_root / "alias_001", run_id="run_alias_001")

            out_1 = root / "scan_out_1"
            out_2 = root / "scan_out_2"
            run_scan_suite(runs_root=runs_root, out_dir=out_1)
            run_scan_suite(runs_root=runs_root, out_dir=out_2)

            strict_1 = json.loads((out_1 / "strict_parse_scan.json").read_text(encoding="utf-8"))
            strict_2 = json.loads((out_2 / "strict_parse_scan.json").read_text(encoding="utf-8"))
            ingest_1 = json.loads((out_1 / "ingest_compatibility_scan.json").read_text(encoding="utf-8"))
            ingest_2 = json.loads((out_2 / "ingest_compatibility_scan.json").read_text(encoding="utf-8"))
            episode_1 = json.loads((out_1 / "episode_extraction_scan.json").read_text(encoding="utf-8"))
            episode_2 = json.loads((out_2 / "episode_extraction_scan.json").read_text(encoding="utf-8"))

            self.assertEqual(strict_1["summary"], strict_2["summary"])
            self.assertEqual(ingest_1["summary"], ingest_2["summary"])
            self.assertEqual(episode_1["summary"], episode_2["summary"])

            out_cli = root / "scan_out_cli"
            exit_code = frugal_cli_main(
                [
                    "scan-runs",
                    "--runs-root",
                    runs_root.as_posix(),
                    "--out-dir",
                    out_cli.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)
            strict_cli = json.loads((out_cli / "strict_parse_scan.json").read_text(encoding="utf-8"))
            self.assertEqual(strict_1["summary"], strict_cli["summary"])


if __name__ == "__main__":
    unittest.main()
