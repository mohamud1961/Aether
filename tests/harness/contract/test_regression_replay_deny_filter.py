import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aether.evals.utils.events import NULL_EVENT_HASH
from aether.evals.utils.hashes import canonical_json_dumps, sha256_text, stable_hash
from aether.evals.frugal_evals import failure_clusters


def _write_cas_json(run_dir: Path, payload: dict) -> str:
    serialized = canonical_json_dumps(payload)
    content_hash = sha256_text(serialized)
    objects = run_dir / "artifacts" / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    (objects / content_hash).write_text(serialized, encoding="utf-8")
    return content_hash


def _append_event(events: list[dict], payload: dict) -> None:
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


class TestND2RegressionReplayDenyFilter(unittest.TestCase):
    def test_nd1_pipeline_ignores_replay_mode_tool_deny_in_clusters_and_episodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runs_root = root / "runs"
            run_dir = runs_root / "synthetic-task_20260214_000000"
            run_dir.mkdir(parents=True)
            (run_dir / "artifacts" / "objects").mkdir(parents=True, exist_ok=True)

            context_pack_ref = _write_cas_json(
                run_dir,
                {
                    "POLICY": [],
                    "SYSTEM": [{"source_ref": "doctrine"}],
                    "CONTRACTS": [{"source_ref": "completion_contract_digest", "kind": "completion_contract_digest"}],
                    "TASK": [{"source_ref": "task"}],
                    "EVIDENCE": [],
                    "STATE": [],
                    "SCRATCH": [],
                },
            )
            manifest_ref = _write_cas_json(
                run_dir,
                {
                    "sweet_zone_pct": 0.2,
                    "total_tokens_estimate": 100,
                    "context_window_tokens": 1000,
                    "reasons": [],
                },
            )
            model_request_ref = _write_cas_json(
                run_dir,
                {
                    "model_identifier": "mock",
                    "messages": [],
                    "tools": [],
                    "max_tokens": 64,
                    "temperature": 0.0,
                },
            )
            context_slice_ref = _write_cas_json(
                run_dir,
                {
                    "version": "context_slice.v1",
                    "step_id": 3,
                    "timestamp": "2026-02-14T00:00:03Z",
                    "context_pack_hash": context_pack_ref,
                    "manifest_hash": manifest_ref,
                    "context_pack_ref": context_pack_ref,
                    "manifest_ref": manifest_ref,
                    "model_request_hash": model_request_ref,
                    "model_request_ref": model_request_ref,
                    "workspace_fingerprint_hash": "wf-hash",
                    "policy_profile_id": "eval",
                    "plan_version_id": "1",
                    "completion_contract_id": "completion-1",
                },
            )

            events: list[dict] = []
            _append_event(
                events,
                {
                    "run_id": "run_replay_filter",
                    "event_type": "run_START",
                    "step_id": 1,
                    "timestamp": "2026-02-14T00:00:01Z",
                    "cwd": "/tmp/replay-filter",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_replay_filter",
                    "event_type": "CONTEXTPACK_COMPILED",
                    "step_id": 2,
                    "timestamp": "2026-02-14T00:00:02Z",
                    "cwd": "/tmp/replay-filter",
                    "context_pack_hash": context_pack_ref,
                    "manifest_hash": manifest_ref,
                    "context_pack_ref": context_pack_ref,
                    "manifest_ref": manifest_ref,
                    "artifact_refs": [context_pack_ref, manifest_ref],
                    "sweet_zone_pct": 0.2,
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_replay_filter",
                    "event_type": "context_slice_bound",
                    "step_id": 3,
                    "timestamp": "2026-02-14T00:00:03Z",
                    "cwd": "/tmp/replay-filter",
                    "context_slice_ref": context_slice_ref,
                    "context_slice_hash": context_slice_ref,
                    "context_pack_ref": context_pack_ref,
                    "context_pack_hash": context_pack_ref,
                    "manifest_ref": manifest_ref,
                    "manifest_hash": manifest_ref,
                    "model_request_ref": model_request_ref,
                    "model_request_hash": model_request_ref,
                    "workspace_fingerprint_hash": "wf-hash",
                    "policy_profile_id": "eval",
                    "plan_version_id": "1",
                    "completion_contract_id": "completion-1",
                    "intent_contract_id": "intent-1",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_replay_filter",
                    "event_type": "run_END",
                    "step_id": 4,
                    "timestamp": "2026-02-14T00:00:04Z",
                    "cwd": "/tmp/replay-filter",
                    "summary_reason_code": "fail_state",
                    "termination_reason": "fail_state",
                    "terminal_outcome": "FAIL_UNKNOWN",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_replay_filter",
                    "event_type": "REPLAY_START",
                    "step_id": 5,
                    "timestamp": "2026-02-14T00:00:05Z",
                    "cwd": "/tmp/replay-filter",
                    "replay_mode": "recorded",
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_replay_filter",
                    "event_type": "TOOL_DENY",
                    "step_id": 6,
                    "timestamp": "2026-02-14T00:00:06Z",
                    "cwd": "/tmp/replay-filter",
                    "tool_name": "run",
                    "deny_reason_code": "UNKNOWN",
                    "replay_mode": True,
                },
            )
            _append_event(
                events,
                {
                    "run_id": "run_replay_filter",
                    "event_type": "REPLAY_END",
                    "step_id": 7,
                    "timestamp": "2026-02-14T00:00:07Z",
                    "cwd": "/tmp/replay-filter",
                    "pass": True,
                },
            )

            (run_dir / "event_log.jsonl").write_text(
                "\n".join(canonical_json_dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )

            out_root = root / "nd1_out"
            with patch.dict(failure_clusters.RUN_ROOTS, {"claude": runs_root}, clear=True):
                failure_clusters.run_nd1(out_root)

            episodes = [
                json.loads(line)
                for line in (out_root / "episodes.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            deny_decision_episodes = [episode for episode in episodes if episode.get("episode_type") == "decision_tool_deny"]
            self.assertEqual(len(deny_decision_episodes), 0)

            failure_map = json.loads((out_root / "failure_map.json").read_text(encoding="utf-8"))
            secondary_indicators = [
                indicator
                for cluster in failure_map.get("clusters", [])
                for indicator in cluster.get("signature", {}).get("secondary_indicators", [])
            ]
            self.assertNotIn("first_deny_reason_code=UNKNOWN", secondary_indicators)


if __name__ == "__main__":
    unittest.main()
