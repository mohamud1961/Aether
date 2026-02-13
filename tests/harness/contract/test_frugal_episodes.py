import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, sha256_text, stable_hash
from aether.evals.frugal_evals.episodes import EpisodeExtractionError, extract_and_write_episodes


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


def _build_binding_artifacts(
    run_dir: Path,
    *,
    step_id: int,
    timestamp: str,
    include_contract_digest: bool,
    workspace_fingerprint_hash: str,
    policy_profile_id: str,
    plan_version_id: str,
    completion_contract_id: str,
) -> Dict[str, str]:
    contracts = [{"source_ref": "completion_contract_digest", "kind": "contract_digest"}] if include_contract_digest else []
    context_pack = {
        "POLICY": [],
        "SYSTEM": [{"source_ref": "doctrine_digest"}],
        "CONTRACTS": contracts,
        "TASK": [{"source_ref": "task_spec"}],
        "EVIDENCE": [],
        "STATE": [{"source_ref": "runtime_state"}],
        "SCRATCH": [],
    }
    context_pack_ref = _write_cas_json(run_dir, context_pack)

    manifest = {
        "context_window_tokens": 2000,
        "total_tokens_estimate": 500,
        "sweet_zone_pct": 0.25,
        "reasons": [],
    }
    manifest_ref = _write_cas_json(run_dir, manifest)

    model_request = {
        "model_identifier": "default_model_v1",
        "messages": [],
        "max_tokens": 64,
        "temperature": 0.0,
        "tools": [],
    }
    model_request_ref = _write_cas_json(run_dir, model_request)

    context_slice_payload = {
        "version": "context_slice.v1",
        "step_id": step_id,
        "timestamp": timestamp,
        "context_pack_hash": context_pack_ref,
        "manifest_hash": manifest_ref,
        "context_pack_ref": context_pack_ref,
        "manifest_ref": manifest_ref,
        "model_request_hash": model_request_ref,
        "model_request_ref": model_request_ref,
        "workspace_fingerprint_hash": workspace_fingerprint_hash,
        "policy_profile_id": policy_profile_id,
        "plan_version_id": plan_version_id,
        "completion_contract_id": completion_contract_id,
    }
    context_slice_ref = _write_cas_json(run_dir, context_slice_payload)

    return {
        "context_slice_ref": context_slice_ref,
        "context_slice_hash": context_slice_ref,
        "context_pack_ref": context_pack_ref,
        "context_pack_hash": context_pack_ref,
        "manifest_ref": manifest_ref,
        "manifest_hash": manifest_ref,
        "model_request_ref": model_request_ref,
        "model_request_hash": model_request_ref,
        "workspace_fingerprint_hash": workspace_fingerprint_hash,
        "policy_profile_id": policy_profile_id,
        "plan_version_id": plan_version_id,
        "completion_contract_id": completion_contract_id,
    }


def _write_run(run_dir: Path, events: List[Dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "event_log.jsonl").write_text(
        "\n".join(canonical_json_dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )


class TestFrugalEpisodes(unittest.TestCase):
    def test_deterministic_extraction_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            runs_root.mkdir(parents=True, exist_ok=True)

            run_dir_a = runs_root / "a_run"
            run_dir_z = runs_root / "z_run"

            run_b_events: List[Dict[str, Any]] = []
            first_binding = _build_binding_artifacts(
                run_dir_a,
                step_id=4,
                timestamp="2026-02-13T00:00:04Z",
                include_contract_digest=True,
                workspace_fingerprint_hash="wf_run_b",
                policy_profile_id="eval",
                plan_version_id="1",
                completion_contract_id="completion_run_b",
            )
            second_binding = _build_binding_artifacts(
                run_dir_a,
                step_id=7,
                timestamp="2026-02-13T00:00:07Z",
                include_contract_digest=False,
                workspace_fingerprint_hash="wf_run_b",
                policy_profile_id="eval",
                plan_version_id="1",
                completion_contract_id="completion_run_b",
            )

            _append_event(
                run_b_events,
                {
                    "run_id": "run_b",
                    "event_type": "run_START",
                    "step_id": 1,
                    "timestamp": "2026-02-13T00:00:01Z",
                    "cwd": "/tmp/run_b",
                },
            )
            _append_event(
                run_b_events,
                {
                    "run_id": "run_b",
                    "event_type": "TOOL_DENY",
                    "step_id": 2,
                    "timestamp": "2026-02-13T00:00:02Z",
                    "cwd": "/tmp/run_b",
                    "tool_name": "run",
                    "deny_reason_code": "UNKNOWN",
                },
            )
            _append_event(
                run_b_events,
                {
                    "run_id": "run_b",
                    "event_type": "TOOL_CALL",
                    "step_id": 3,
                    "timestamp": "2026-02-13T00:00:03Z",
                    "cwd": "/tmp/run_b",
                    "tool_name": "run",
                    "tool_args": {"command": ["ls", "-la"]},
                    "risk_class": "LOW",
                },
            )
            _append_event(
                run_b_events,
                {
                    "run_id": "run_b",
                    "event_type": "context_slice_bound",
                    "step_id": 4,
                    "timestamp": "2026-02-13T00:00:04Z",
                    "cwd": "/tmp/run_b",
                    **first_binding,
                    "intent_contract_id": "intent_run_b",
                },
            )
            _append_event(
                run_b_events,
                {
                    "run_id": "run_b",
                    "event_type": "CONTEXTSLICE_BINDING",
                    "step_id": 5,
                    "timestamp": "2026-02-13T00:00:05Z",
                    "cwd": "/tmp/run_b",
                    **first_binding,
                    "intent_contract_id": "intent_run_b",
                },
            )
            _append_event(
                run_b_events,
                {
                    "run_id": "run_b",
                    "event_type": "TOOL_CALL",
                    "step_id": 6,
                    "timestamp": "2026-02-13T00:00:06Z",
                    "cwd": "/tmp/run_b",
                    "tool_name": "run",
                    "tool_args": {"command": ["ls", "-la"]},
                    "risk_class": "LOW",
                },
            )
            _append_event(
                run_b_events,
                {
                    "run_id": "run_b",
                    "event_type": "context_slice_bound",
                    "step_id": 7,
                    "timestamp": "2026-02-13T00:00:07Z",
                    "cwd": "/tmp/run_b",
                    **second_binding,
                    "intent_contract_id": "intent_run_b",
                },
            )
            _write_run(run_dir_a, run_b_events)

            run_a_events: List[Dict[str, Any]] = []
            run_a_binding = _build_binding_artifacts(
                run_dir_z,
                step_id=3,
                timestamp="2026-02-13T00:10:03Z",
                include_contract_digest=True,
                workspace_fingerprint_hash="wf_run_a",
                policy_profile_id="eval",
                plan_version_id="2",
                completion_contract_id="completion_run_a",
            )
            _append_event(
                run_a_events,
                {
                    "run_id": "run_a",
                    "event_type": "run_START",
                    "step_id": 1,
                    "timestamp": "2026-02-13T00:10:01Z",
                    "cwd": "/tmp/run_a",
                },
            )
            _append_event(
                run_a_events,
                {
                    "run_id": "run_a",
                    "event_type": "TOOL_CALL",
                    "step_id": 2,
                    "timestamp": "2026-02-13T00:10:02Z",
                    "cwd": "/tmp/run_a",
                    "tool_name": "run",
                    "tool_args": {"command": ["pwd"]},
                    "risk_class": "LOW",
                },
            )
            _append_event(
                run_a_events,
                {
                    "run_id": "run_a",
                    "event_type": "context_slice_bound",
                    "step_id": 3,
                    "timestamp": "2026-02-13T00:10:03Z",
                    "cwd": "/tmp/run_a",
                    **run_a_binding,
                    "intent_contract_id": "intent_run_a",
                },
            )
            _write_run(run_dir_z, run_a_events)

            out1 = root / "episodes_1.jsonl"
            idx1 = root / "episode_index_1.json"
            out2 = root / "episodes_2.jsonl"
            idx2 = root / "episode_index_2.json"

            extract_and_write_episodes(
                runs_root=runs_root,
                out_path=out1,
                index_out_path=idx1,
            )
            extract_and_write_episodes(
                runs_root=runs_root,
                out_path=out2,
                index_out_path=idx2,
            )

            digest1 = hashlib.sha256(out1.read_bytes()).hexdigest()
            digest2 = hashlib.sha256(out2.read_bytes()).hexdigest()
            self.assertEqual(digest1, digest2)

            lines = [line for line in out1.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 4)  # alias event must be deduplicated; TOOL_DENY emits a decision episode
            parsed = [json.loads(line) for line in lines]
            self.assertEqual([item["run_id"] for item in parsed], ["run_a", "run_b", "run_b", "run_b"])
            for line, item in zip(lines, parsed):
                self.assertEqual(line, canonical_json_dumps(item))

            run_b_items = [item for item in parsed if item["run_id"] == "run_b"]
            self.assertEqual([item["episode_type"] for item in run_b_items], ["decision_tool_deny", "context_slice", "context_slice"])

            deny_episode = run_b_items[0]
            self.assertEqual(deny_episode["step_id"], 2)
            self.assertEqual(len(deny_episode["prelude_event_ids"]), 1)
            self.assertIsNone(deny_episode["context_pack_ref"])
            self.assertEqual(deny_episode["tool_deny_count_before"], 0)

            second_context_run_b = run_b_items[2]
            self.assertEqual(second_context_run_b["retry_fingerprint_count"], 1)
            self.assertEqual(second_context_run_b["tool_deny_count_before"], 1)
            self.assertFalse(second_context_run_b["contract_digest_in_context"])
            self.assertEqual(second_context_run_b["context_utilization_pct"], 0.25)

            index_payload = json.loads(idx1.read_text(encoding="utf-8"))
            self.assertEqual(index_payload["episode_count"], 4)
            self.assertIn("episodes_by_policy_profile", index_payload["summary"])
            self.assertIn("truncation_flag_counts", index_payload["summary"])
            self.assertIn("risk_class_distribution", index_payload["summary"])

    def test_decision_episode_triggers_and_prelude_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            runs_root.mkdir(parents=True, exist_ok=True)
            run_dir = runs_root / "trigger_run"

            binding = _build_binding_artifacts(
                run_dir,
                step_id=7,
                timestamp="2026-02-13T00:00:07Z",
                include_contract_digest=True,
                workspace_fingerprint_hash="wf_trigger",
                policy_profile_id="eval",
                plan_version_id="1",
                completion_contract_id="completion_trigger",
            )

            events: List[Dict[str, Any]] = []
            _append_event(
                events,
                {
                    "run_id": "run_trigger",
                    "event_type": "run_START",
                    "step_id": 1,
                    "timestamp": "2026-02-13T00:00:01Z",
                    "cwd": "/tmp/run_trigger",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_trigger",
                    "event_type": "PHASE_TRANSITION",
                    "step_id": 2,
                    "timestamp": "2026-02-13T00:00:02Z",
                    "cwd": "/tmp/run_trigger",
                    "from_phase": "Orient",
                    "to_phase": "Explore",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_trigger",
                    "event_type": "PHASE_TRANSITION_DENIED",
                    "step_id": 3,
                    "timestamp": "2026-02-13T00:00:03Z",
                    "cwd": "/tmp/run_trigger",
                    "from_phase": "Explore",
                    "to_phase": "Implement",
                    "deny_reason_code": "PLAN_MISSING_LINKAGE",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_trigger",
                    "event_type": "VERIFIER_RESULT",
                    "step_id": 4,
                    "timestamp": "2026-02-13T00:00:04Z",
                    "cwd": "/tmp/run_trigger",
                    "status": "failed",
                    "verifier_id": "unit_tests",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_trigger",
                    "event_type": "REANCHOR_START",
                    "step_id": 5,
                    "timestamp": "2026-02-13T00:00:05Z",
                    "cwd": "/tmp/run_trigger",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_trigger",
                    "event_type": "REANCHOR_REPEAT_DETECTED",
                    "step_id": 6,
                    "timestamp": "2026-02-13T00:00:06Z",
                    "cwd": "/tmp/run_trigger",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_trigger",
                    "event_type": "context_slice_bound",
                    "step_id": 7,
                    "timestamp": "2026-02-13T00:00:07Z",
                    "cwd": "/tmp/run_trigger",
                    **binding,
                    "intent_contract_id": "intent_trigger",
                },
            )
            _write_run(run_dir, events)

            out_path = root / "episodes.jsonl"
            extract_and_write_episodes(
                runs_root=runs_root,
                out_path=out_path,
                index_out_path=root / "episode_index.json",
            )

            parsed = [
                json.loads(line)
                for line in out_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(parsed), 5)
            by_type = {item["episode_type"]: item for item in parsed}
            self.assertIn("decision_phase_deny", by_type)
            self.assertIn("decision_verifier_fail", by_type)
            self.assertIn("decision_reanchor", by_type)
            self.assertIn("decision_reanchor_repeat", by_type)
            self.assertIn("context_slice", by_type)

            self.assertEqual(len(by_type["decision_phase_deny"]["prelude_event_ids"]), 2)
            self.assertEqual(len(by_type["decision_verifier_fail"]["prelude_event_ids"]), 3)
            self.assertEqual(len(by_type["decision_reanchor"]["prelude_event_ids"]), 4)
            self.assertEqual(len(by_type["decision_reanchor_repeat"]["prelude_event_ids"]), 5)

    def test_missing_artifact_ref_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            runs_root.mkdir(parents=True, exist_ok=True)
            run_dir = runs_root / "broken_run"
            run_dir.mkdir(parents=True, exist_ok=True)

            context_pack_ref = _write_cas_json(run_dir, {"SYSTEM": [], "TASK": [], "CONTRACTS": []})
            model_request_ref = _write_cas_json(
                run_dir,
                {
                    "model_identifier": "default_model_v1",
                    "messages": [],
                    "max_tokens": 64,
                    "temperature": 0.0,
                    "tools": [],
                },
            )
            missing_manifest_ref = "f" * 64
            context_slice_payload = {
                "version": "context_slice.v1",
                "step_id": 1,
                "timestamp": "2026-02-13T00:00:01Z",
                "context_pack_hash": context_pack_ref,
                "manifest_hash": missing_manifest_ref,
                "context_pack_ref": context_pack_ref,
                "manifest_ref": missing_manifest_ref,
                "model_request_hash": model_request_ref,
                "model_request_ref": model_request_ref,
                "workspace_fingerprint_hash": "wf_broken",
                "policy_profile_id": "eval",
                "plan_version_id": "1",
                "completion_contract_id": "completion_broken",
            }
            context_slice_ref = _write_cas_json(run_dir, context_slice_payload)

            events: List[Dict[str, Any]] = []
            _append_event(
                events,
                {
                    "run_id": "run_broken",
                    "event_type": "context_slice_bound",
                    "step_id": 1,
                    "timestamp": "2026-02-13T00:00:01Z",
                    "cwd": "/tmp/run_broken",
                    "context_slice_ref": context_slice_ref,
                    "context_slice_hash": context_slice_ref,
                    "context_pack_ref": context_pack_ref,
                    "context_pack_hash": context_pack_ref,
                    "manifest_ref": missing_manifest_ref,
                    "manifest_hash": missing_manifest_ref,
                    "model_request_ref": model_request_ref,
                    "model_request_hash": model_request_ref,
                    "workspace_fingerprint_hash": "wf_broken",
                    "policy_profile_id": "eval",
                },
            )
            _write_run(run_dir, events)

            with self.assertRaises(EpisodeExtractionError) as ctx:
                extract_and_write_episodes(
                    runs_root=runs_root,
                    out_path=root / "episodes.jsonl",
                    index_out_path=root / "episode_index.json",
                )
            self.assertIn("manifest_ref", str(ctx.exception))
            self.assertIn("missing or unreadable artifact ref", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
