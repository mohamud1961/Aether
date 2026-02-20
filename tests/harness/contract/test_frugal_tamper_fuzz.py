import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, sha256_bytes, stable_hash
from aether.evals.frugal_evals.cli import main as frugal_cli_main
from aether.evals.frugal_evals.tamper_fuzz import (
    EXPECTED_FAIL_BINDING,
    EXPECTED_FAIL_CAS,
    EXPECTED_FAIL_HASH,
    run_tamper_fuzz_suite,
)


def _write_cas_bytes(run_dir: Path, data: bytes) -> str:
    artifact_id = sha256_bytes(data)
    objects = run_dir / "artifacts" / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    (objects / artifact_id).write_bytes(data)
    return artifact_id


def _write_cas_json(run_dir: Path, payload: Dict[str, Any]) -> str:
    return _write_cas_bytes(run_dir, canonical_json_dumps(payload).encode("utf-8"))


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


def _build_run(run_dir: Path) -> None:
    context_pack_ref = _write_cas_json(
        run_dir,
        {
            "POLICY": [],
            "SYSTEM": [{"content": "system"}],
            "CONTRACTS": [{"source_ref": "completion_contract_digest"}],
            "TASK": [{"content": "task"}],
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
            "messages": [{"role": "user", "content": "hello"}],
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
            "workspace_fingerprint_hash": "wf-run_tamper",
            "policy_profile_id": "eval",
            "plan_version_id": "1",
            "completion_contract_id": "completion-run_tamper",
        },
    )
    stdout_ref = _write_cas_bytes(run_dir, b"stdout")
    stderr_ref = _write_cas_bytes(run_dir, b"stderr")

    events: List[Dict[str, Any]] = []
    _append_event(
        events,
        {
            "run_id": "run_tamper",
            "event_type": "run_START",
            "step_id": 1,
            "timestamp": "2026-02-13T00:00:01Z",
            "cwd": "/tmp/run_tamper",
        },
    )
    _append_event(
        events,
        {
            "run_id": "run_tamper",
            "event_type": "TOOL_CALL",
            "step_id": 2,
            "timestamp": "2026-02-13T00:00:02Z",
            "cwd": "/tmp/run_tamper",
            "tool_name": "run",
            "tool_args": {"command": ["ls"]},
            "artifact_refs": [stdout_ref, stderr_ref],
            "stdout_ref": stdout_ref,
            "stderr_ref": stderr_ref,
        },
    )
    _append_event(
        events,
        {
            "run_id": "run_tamper",
            "event_type": "context_slice_bound",
            "step_id": 3,
            "timestamp": "2026-02-13T00:00:03Z",
            "cwd": "/tmp/run_tamper",
            "context_slice_ref": context_slice_ref,
            "context_slice_hash": context_slice_ref,
            "context_pack_ref": context_pack_ref,
            "context_pack_hash": context_pack_ref,
            "manifest_ref": manifest_ref,
            "manifest_hash": manifest_ref,
            "model_request_ref": model_request_ref,
            "model_request_hash": model_request_ref,
            "workspace_fingerprint_hash": "wf-run_tamper",
            "policy_profile_id": "eval",
            "plan_version_id": "1",
            "completion_contract_id": "completion-run_tamper",
            "intent_contract_id": "intent-run_tamper",
        },
    )
    _append_event(
        events,
        {
            "run_id": "run_tamper",
            "event_type": "TOOL_CALL",
            "step_id": 4,
            "timestamp": "2026-02-13T00:00:04Z",
            "cwd": "/tmp/run_tamper",
            "tool_name": "run",
            "tool_args": {"command": ["pwd"]},
        },
    )
    _append_event(
        events,
        {
            "run_id": "run_tamper",
            "event_type": "run_END",
            "step_id": 5,
            "timestamp": "2026-02-13T00:00:05Z",
            "cwd": "/tmp/run_tamper",
            "termination_reason": "SUCCESS",
        },
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "event_log.jsonl").write_text(
        "\n".join(canonical_json_dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


class TestFrugalTamperFuzz(unittest.TestCase):
    def test_tamper_fuzz_detects_all_v0_1_categories_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "runs" / "run_tamper"
            out_dir = root / "out"
            out_dir_two = root / "out_second"
            _build_run(run_dir)

            first = run_tamper_fuzz_suite(run_dir=run_dir, out_dir=out_dir, truncation_events=1)
            second = run_tamper_fuzz_suite(run_dir=run_dir, out_dir=out_dir_two, truncation_events=1)

            self.assertEqual(first["report_hash"], second["report_hash"])

            report = json.loads(Path(first["report_path"]).read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["case_count"], 5)
            self.assertEqual(report["summary"]["failed_cases"], 0)

            expected = {
                "FIELD_MUTATION": EXPECTED_FAIL_HASH,
                "EVENT_SWAP": EXPECTED_FAIL_HASH,
                "EVENT_TRUNCATION": EXPECTED_FAIL_BINDING,
                "CAS_CORRUPTION": EXPECTED_FAIL_CAS,
                "CAS_DELETION": EXPECTED_FAIL_CAS,
            }
            seen: Dict[str, str] = {}
            for case in report["cases"]:
                self.assertTrue(case["pass"])
                seen[case["case_id"]] = case["actual_outcome"]

            self.assertEqual(seen, expected)

    def test_cli_run_tamper_fuzz(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "runs" / "run_tamper"
            out_dir = root / "out"
            _build_run(run_dir)

            exit_code = frugal_cli_main(
                [
                    "run-tamper-fuzz",
                    "--run-dir",
                    run_dir.as_posix(),
                    "--out-dir",
                    out_dir.as_posix(),
                    "--truncate-events",
                    "1",
                ]
            )
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
