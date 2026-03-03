import json
import tempfile
import unittest
from pathlib import Path

from aether.context_compiler import compile_and_log
from aether.context_pack import ContextPackProjection
from aether.event_log import EventLog
from aether.hashing import hash_canonical_json
from aether.policy_config import PolicyConfig


class TestStateReadinessProjection(unittest.TestCase):
    def test_projection_contains_compact_readiness_block_and_state_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "event_log.jsonl")

            event_log.append_event(
                {
                    "event_type": "TOOL_CALL",
                    "timestamp": "2026-02-22T12:00:00Z",
                    "cwd": root.as_posix(),
                    "tool_name": "run",
                    "tool_args": {"command": ["ls", "-la"]},
                    "exit_code": 0,
                }
            )
            event_log.append_event(
                {
                    "event_type": "PLAN_STATUS_CHANGED",
                    "timestamp": "2026-02-22T12:00:01Z",
                    "cwd": root.as_posix(),
                    "from_status": "DRAFT",
                    "to_status": "APPROVED",
                    "status": "APPROVED",
                }
            )
            event_log.append_event(
                {
                    "event_type": "PHASE_TRANSITION_DENIED",
                    "timestamp": "2026-02-22T12:00:02Z",
                    "cwd": root.as_posix(),
                    "from_phase": "Explore",
                    "to_phase": "Implement",
                    "deny_reason_code": "PLAN_MISSING_LINKAGE",
                    "missing_conditions": ["plan_status_approved_or_executing"],
                }
            )

            runtime_state = {
                "phase": "Implement",
                "state": "Implement",
                "dirty_since_last_verify": False,
                "last_phase_transition_denied": {"deny_reason_code": "PLAN_MISSING_LINKAGE"},
            }
            runtime_state_text = json.dumps(runtime_state, sort_keys=True, separators=(",", ":"))
            candidates = [
                {
                    "section": "State",
                    "kind": "runtime_state",
                    "content": runtime_state_text,
                    "source_ref": "runtime_state",
                    "observed_at": "2026-02-22T12:00:03Z",
                    "authority_tier": "runtime",
                    "validity_ttl": "PT1S",
                    "content_hash": hash_canonical_json(runtime_state_text),
                }
            ]

            compiled = compile_and_log(
                candidates,
                policy_config=PolicyConfig.from_env(),
                event_log=event_log,
                timestamp="2026-02-22T12:00:04Z",
                cwd=root.as_posix(),
                workspace_fingerprint_hash="fp-current",
            )

            projection = ContextPackProjection(compiled.context_pack)
            conversation = "\n".join(
                str(item.get("content", "")) for item in projection.get_tier_items("CONVERSATION")
            )

            self.assertIn("STATE_SUMMARY phase=Implement denial=PLAN_MISSING_LINKAGE readiness=E1P1V0R1", conversation)
            self.assertIn(
                "readiness: {explore_floor_passed=true, plan_approved=true, needs_verify=false, can_review=true}",
                conversation,
            )
            self.assertIn("last_denial_code: PLAN_MISSING_LINKAGE", conversation)


if __name__ == "__main__":
    unittest.main()
