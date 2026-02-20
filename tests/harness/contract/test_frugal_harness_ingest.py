import json
import tempfile
import unittest
from pathlib import Path

from aether.evals.utils.events import NULL_EVENT_HASH, load_events, validate_hash_chain
from aether.evals.utils.hashes import stable_hash
from aether.evals.frugal_evals.cli import main as frugal_cli_main
from aether.evals.frugal_evals.ingest import open_harness_run_view, summarize_harness_run


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


class TestFrugalHarnessIngest(unittest.TestCase):
    def test_dual_view_load_preserves_raw_payload_for_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "artifacts" / "objects").mkdir(parents=True, exist_ok=True)

            event1 = _with_hash(
                NULL_EVENT_HASH,
                {
                    "run_id": "run_001",
                    "event_type": "contextslice_binding",
                    "step_id": 1,
                    "timestamp": "2026-02-13T00:00:00Z",
                    "cwd": "/tmp",
                },
            )
            event2 = _with_hash(
                event1["event_id"],
                {
                    "run_id": "run_001",
                    "event_type": "run_end",
                    "step_id": 2,
                    "timestamp": "2026-02-13T00:00:01Z",
                    "cwd": "/tmp",
                },
            )
            log_path = run_dir / "event_log.jsonl"
            log_path.write_text(
                "\n".join(json.dumps(event) for event in (event1, event2)) + "\n",
                encoding="utf-8",
            )

            events = load_events(run_dir)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].payload["event_type"], "contextslice_binding")
            self.assertEqual(events[0].event_type, "CONTEXT_SLICE_BOUND")

            ok, first_bad_event_id = validate_hash_chain(events)
            self.assertTrue(ok)
            self.assertIsNone(first_bad_event_id)

    def test_harness_run_view_and_cli_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "artifacts" / "objects").mkdir(parents=True, exist_ok=True)

            event = _with_hash(
                NULL_EVENT_HASH,
                {
                    "run_id": "run_002",
                    "event_type": "run_START",
                    "step_id": 7,
                    "timestamp": "2026-02-13T00:00:00Z",
                    "cwd": "/tmp",
                },
            )
            (run_dir / "event_log.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

            view = open_harness_run_view(run_dir)
            self.assertEqual(view.events_path.name, "event_log.jsonl")
            self.assertTrue(any(path.name == "objects" for path in view.cas_roots))

            summary = summarize_harness_run(run_dir)
            self.assertEqual(summary["run_id"], "run_002")
            self.assertEqual(summary["event_count"], 1)
            self.assertEqual(summary["first_step_id"], 7)
            self.assertEqual(summary["last_step_id"], 7)
            self.assertTrue(summary["hash_chain_ok"])

            exit_code = frugal_cli_main(["summarize-run", "--run-dir", run_dir.as_posix()])
            self.assertEqual(exit_code, 0)

    def test_state_transition_uses_strict_alias_without_compat_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "artifacts" / "objects").mkdir(parents=True, exist_ok=True)

            event = _with_hash(
                NULL_EVENT_HASH,
                {
                    "run_id": "run_compat",
                    "event_type": "state_transition",
                    "step_id": 3,
                    "timestamp": "2026-02-13T00:00:00Z",
                    "cwd": "/tmp",
                },
            )
            (run_dir / "event_log.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

            view = open_harness_run_view(run_dir)
            loaded = view.load_events()
            self.assertEqual(loaded[0].event_type, "PHASE_TRANSITION")

            summary = summarize_harness_run(run_dir)
            self.assertTrue(summary["hash_chain_ok"])
            self.assertEqual(len(summary["compat_issues"]), 0)


if __name__ == "__main__":
    unittest.main()
