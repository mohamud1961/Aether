import json
import tempfile
import unittest
from pathlib import Path

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, sha256_text, stable_hash
from aether.evals.frugal_evals.cli import main as frugal_cli_main
from aether.evals.frugal_evals.context_dump import dump_context_diagnostics


def _write_cas_json(run_dir: Path, payload: dict) -> str:
    serialized = canonical_json_dumps(payload)
    content_hash = sha256_text(serialized)
    objects = run_dir / "artifacts" / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    (objects / content_hash).write_text(serialized, encoding="utf-8")
    return content_hash


def _with_hash(prev_event_hash: str, payload: dict) -> dict:
    event = dict(payload)
    event["prev_event_hash"] = prev_event_hash
    event["event_id"] = stable_hash(
        {
            key: value
            for key, value in event.items()
            if key not in {"event_id", "prev_event_hash"}
        }
    )
    return event


def _build_run_dir(base: Path) -> Path:
    run_dir = base / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    context_pack = {
        "POLICY": [{"source_ref": "policy_digest", "kind": "policy", "trust_level": "TRUSTED"}],
        "SYSTEM": [{"source_ref": "doctrine_digest", "kind": "doctrine"}],
        "CONTRACTS": [{"source_ref": "completion_contract_digest", "kind": "contract_digest"}],
        "TASK": [{"source_ref": "task_spec", "kind": "task"}],
        "EVIDENCE": [{"source_ref": "verifier_raw:stderr", "kind": "verifier_raw", "truncation_flags": "STDERR_TrunCATED"}],
        "STATE": [],
        "SCRATCH": [
            {
                "source_ref": "tool_stdout",
                "kind": "tool_output",
                "trust_level": "UNTRUSTED",
                "truncation": {
                    "stdout": {"truncated": True, "unknown": False},
                    "stderr": {"truncated": False, "unknown": False},
                },
            }
        ],
    }
    manifest = {"sweet_zone_pct": 0.42, "reasons": []}
    context_hash = _write_cas_json(run_dir, context_pack)
    manifest_hash = _write_cas_json(run_dir, manifest)

    step_1 = _with_hash(
        NULL_EVENT_HASH,
        {
            "run_id": "run_ctx_001",
            "event_type": "CONTEXTPACK_COMPILED",
            "step_id": 1,
            "timestamp": "2026-02-13T00:00:00Z",
            "cwd": "/tmp",
            "context_pack_hash": context_hash,
            "manifest_hash": manifest_hash,
            "context_pack_ref": context_hash,
            "manifest_ref": manifest_hash,
            "artifact_refs": [context_hash, manifest_hash],
            "sweet_zone_pct": 0.42,
        },
    )
    step_2 = _with_hash(
        step_1["event_id"],
        {
            "run_id": "run_ctx_001",
            "event_type": "run_END",
            "step_id": 2,
            "timestamp": "2026-02-13T00:00:01Z",
            "cwd": "/tmp",
        },
    )
    (run_dir / "event_log.jsonl").write_text(
        "\n".join(json.dumps(event) for event in (step_1, step_2)) + "\n",
        encoding="utf-8",
    )
    return run_dir


class TestFrugalContextDump(unittest.TestCase):
    def test_dump_context_outputs_expected_files_and_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _build_run_dir(Path(tmpdir))
            result = dump_context_diagnostics(run_dir, max_steps=2)

            debug_path = Path(result["debug_context_path"])
            json_path = Path(result["context_diagnostic_path"])
            self.assertTrue(debug_path.exists())
            self.assertTrue(json_path.exists())

            diagnostic = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(diagnostic["steps_requested"], 2)
            self.assertEqual(diagnostic["steps_analyzed"], 2)
            self.assertEqual(
                diagnostic["layer_order"],
                ["POLICY", "SYSTEM", "CONTRACTS", "TASK", "EVIDENCE", "STATE", "SCRATCH"],
            )

            first = diagnostic["steps"][0]
            self.assertTrue(first["has_compiled_context"])
            self.assertTrue(first["completion_contract_digest_present"])
            self.assertIn("STDOUT_TRUNCATED", first["truncation_flags"])
            self.assertIn("STDERR_TrunCATED", first["truncation_flags"])

            scratch = next(layer for layer in first["layers"] if layer["name"] == "SCRATCH")
            self.assertEqual(scratch["items"][0]["trust_tag"], "UNTRUSTED")

            second = diagnostic["steps"][1]
            self.assertFalse(second["has_compiled_context"])

            debug_text = debug_path.read_text(encoding="utf-8")
            self.assertIn("Context Compiler Diagnostic", debug_text)
            self.assertIn("completion_contract_digest_present: True", debug_text)

    def test_cli_dump_context_writes_to_out_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = _build_run_dir(root)
            out_dir = root / "diag"
            exit_code = frugal_cli_main(
                [
                    "summarize-run",
                    "--run-dir",
                    run_dir.as_posix(),
                    "--dump-context",
                    "--steps",
                    "1",
                    "--out-dir",
                    out_dir.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((out_dir / "debug_context.txt").exists())
            self.assertTrue((out_dir / "context_diagnostic.json").exists())


if __name__ == "__main__":
    unittest.main()
