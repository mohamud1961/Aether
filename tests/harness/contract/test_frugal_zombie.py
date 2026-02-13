import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, sha256_text, stable_hash
from aether.evals.frugal_evals.episodes import extract_and_write_episodes
from aether.evals.frugal_evals.zombie import run_zombie_batch


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


def _write_run(run_dir: Path, events: List[Dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "event_log.jsonl").write_text(
        "\n".join(canonical_json_dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


def _build_binding_artifacts(run_dir: Path, *, step_id: int, timestamp: str, tag: str) -> Dict[str, str]:
    context_pack_ref = _write_cas_json(
        run_dir,
        {
            "POLICY": [{"content": "policy"}],
            "SYSTEM": [{"content": "system"}],
            "CONTRACTS": [{"source_ref": "completion_contract_digest", "content": f"contract-{tag}"}],
            "TASK": [{"content": f"task-{tag}"}],
            "EVIDENCE": [{"content": "evidence"}],
            "STATE": [{"content": "state"}],
            "SCRATCH": [],
        },
    )
    manifest_ref = _write_cas_json(
        run_dir,
        {
            "context_window_tokens": 1000,
            "total_tokens_estimate": 250,
        },
    )
    model_request_ref = _write_cas_json(
        run_dir,
        {
            "system_prompt": "system",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [],
            "model_identifier": "recorded-model",
            "max_tokens": 128,
            "temperature": 0.0,
        },
    )
    context_slice_ref = _write_cas_json(
        run_dir,
        {
            "version": "context_slice.v1",
            "step_id": step_id,
            "timestamp": timestamp,
            "context_pack_ref": context_pack_ref,
            "context_pack_hash": context_pack_ref,
            "manifest_ref": manifest_ref,
            "manifest_hash": manifest_ref,
            "model_request_ref": model_request_ref,
            "model_request_hash": model_request_ref,
            "workspace_fingerprint_hash": f"wf-{tag}",
            "policy_profile_id": "eval",
            "plan_version_id": "1",
            "completion_contract_id": f"completion-{tag}",
        },
    )
    return {
        "context_slice_ref": context_slice_ref,
        "context_slice_hash": context_slice_ref,
        "context_pack_ref": context_pack_ref,
        "context_pack_hash": context_pack_ref,
        "manifest_ref": manifest_ref,
        "manifest_hash": manifest_ref,
        "model_request_ref": model_request_ref,
        "model_request_hash": model_request_ref,
        "workspace_fingerprint_hash": f"wf-{tag}",
        "policy_profile_id": "eval",
        "plan_version_id": "1",
        "completion_contract_id": f"completion-{tag}",
    }


class TestFrugalZombie(unittest.TestCase):
    def test_mock_batch_has_metrics_cost_and_no_tool_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            runs_root.mkdir(parents=True, exist_ok=True)

            action_sequence = [
                "tool",
                "verify",
                "plan",
                "reanchor",
                "refuse",
                "tool",
                "verify",
                "plan",
                "reanchor",
                "refuse",
            ]
            phase_sequence = [
                "Orient",
                "Explore",
                "Implement",
                "Verify",
                "Orient",
                "Explore",
                "Implement",
                "Verify",
                "Orient",
                "Explore",
            ]

            for idx, (action_kind, phase_name) in enumerate(zip(action_sequence, phase_sequence), start=1):
                run_dir = runs_root / f"run_{idx:02d}"
                run_id = f"run_{idx:02d}"
                binding = _build_binding_artifacts(
                    run_dir,
                    step_id=10,
                    timestamp=f"2026-02-13T00:00:{idx:02d}Z",
                    tag=run_id,
                )

                events: List[Dict[str, Any]] = []
                _append_event(
                    events,
                    {
                        "run_id": run_id,
                        "event_type": "run_START",
                        "step_id": 1,
                        "timestamp": f"2026-02-13T00:00:{idx:02d}Z",
                        "cwd": "/tmp",
                    },
                )

                current_step = 2
                if phase_name in {"Explore", "Implement", "Verify"}:
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "PHASE_TRANSITION",
                            "step_id": current_step,
                            "timestamp": f"2026-02-13T00:01:{idx:02d}Z",
                            "cwd": "/tmp",
                            "from_phase": "Orient",
                            "to_phase": "Explore",
                        },
                    )
                    current_step += 1
                if phase_name in {"Implement", "Verify"}:
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "PHASE_TRANSITION",
                            "step_id": current_step,
                            "timestamp": f"2026-02-13T00:02:{idx:02d}Z",
                            "cwd": "/tmp",
                            "from_phase": "Explore",
                            "to_phase": "Implement",
                        },
                    )
                    current_step += 1
                if phase_name == "Verify":
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "PHASE_TRANSITION",
                            "step_id": current_step,
                            "timestamp": f"2026-02-13T00:03:{idx:02d}Z",
                            "cwd": "/tmp",
                            "from_phase": "Implement",
                            "to_phase": "Verify",
                        },
                    )
                    current_step += 1

                _append_event(
                    events,
                    {
                        "run_id": run_id,
                        "event_type": "context_slice_bound",
                        "step_id": 10,
                        "timestamp": f"2026-02-13T00:04:{idx:02d}Z",
                        "cwd": "/tmp",
                        **binding,
                        "intent_contract_id": f"intent-{run_id}",
                    },
                )

                if action_kind == "tool":
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "model_response",
                            "step_id": 11,
                            "timestamp": f"2026-02-13T00:05:{idx:02d}Z",
                            "cwd": "/tmp",
                            "finish_reason": "tool_use",
                        },
                    )
                elif action_kind == "verify":
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "model_response",
                            "step_id": 11,
                            "timestamp": f"2026-02-13T00:05:{idx:02d}Z",
                            "cwd": "/tmp",
                            "text_content": "Run tests to verify behavior.",
                        },
                    )
                elif action_kind == "plan":
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "PLAN_UPDATE",
                            "step_id": 11,
                            "timestamp": f"2026-02-13T00:05:{idx:02d}Z",
                            "cwd": "/tmp",
                            "update_reason_code": "adaptation",
                        },
                    )
                elif action_kind == "reanchor":
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "REANCHOR_START",
                            "step_id": 11,
                            "timestamp": f"2026-02-13T00:05:{idx:02d}Z",
                            "cwd": "/tmp",
                        },
                    )
                else:
                    _append_event(
                        events,
                        {
                            "run_id": run_id,
                            "event_type": "model_response",
                            "step_id": 11,
                            "timestamp": f"2026-02-13T00:05:{idx:02d}Z",
                            "cwd": "/tmp",
                            "text_content": "I cannot continue safely.",
                        },
                    )

                _append_event(
                    events,
                    {
                        "run_id": run_id,
                        "event_type": "run_END",
                        "step_id": 12,
                        "timestamp": f"2026-02-13T00:06:{idx:02d}Z",
                        "cwd": "/tmp",
                        "termination_reason": "done",
                    },
                )
                _write_run(run_dir, events)

            episodes_path = root / "episodes.jsonl"
            extract_and_write_episodes(
                runs_root=runs_root,
                out_path=episodes_path,
                index_out_path=root / "episode_index.json",
            )

            result = run_zombie_batch(
                episodes_path=episodes_path,
                out_root=root / "zombie",
                model_id="mock-zombie-v1",
                adapter_mode="mock",
                limit=10,
                offset=0,
                pricing_path=Path("aether/evals/frugal_evals/model_pricing.json"),
            )

            batch_summary = json.loads(Path(result["batch_summary_path"]).read_text(encoding="utf-8"))
            self.assertEqual(batch_summary["mode"], "REPLAY_DECISION")
            self.assertEqual(batch_summary["episode_count"], 10)
            self.assertIn("agreement_rate", batch_summary)
            self.assertIn("behavioral_distribution", batch_summary)
            self.assertIn("coherence_rate", batch_summary)
            self.assertIn("cumulative_cost_line", batch_summary)

            cumulative = batch_summary["cumulative_cost_line"]
            self.assertIn("total_input_tokens", cumulative)
            self.assertIn("total_output_tokens", cumulative)
            self.assertIn("total_cost_usd_est", cumulative)
            self.assertEqual(cumulative["model_id"], "mock-zombie-v1")

            for run_entry in batch_summary["episode_runs"]:
                run_dir = Path(run_entry["run_dir"])
                summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
                self.assertIsNotNone(summary["input_tokens"])
                self.assertIsNotNone(summary["output_tokens"])
                self.assertIsNotNone(summary["cost_usd_est"])
                self.assertEqual(summary["mode"], "REPLAY_DECISION")
                self.assertIn(summary["zombie_action_shape"], {"ACT_TOOL", "ACT_VERIFY", "ACT_PLAN_UPDATE", "ACT_REANCHOR", "ACT_REFUSE"})

                for artifact_key in ("request_artifact_ref", "response_artifact_ref", "parsed_action_artifact_ref"):
                    artifact_ref = summary[artifact_key]
                    self.assertTrue((run_dir / "artifacts" / "objects" / artifact_ref).exists())

                for line in (run_dir / "event_log.jsonl").read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    self.assertNotEqual(str(event.get("event_type", "")).upper(), "TOOL_CALL")


if __name__ == "__main__":
    unittest.main()
