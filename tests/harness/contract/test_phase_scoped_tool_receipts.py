import json
import tempfile
import unittest
from pathlib import Path

from aether.context_compiler import compile_and_log
from aether.context_pack import ContextPackProjection
from aether.event_log import EventLog
from aether.hashing import hash_canonical_json
from aether.policy_config import PolicyConfig


class TestPhaseScopedToolReceipts(unittest.TestCase):
    def test_tool_receipts_empty_after_plan_to_implement_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "events.jsonl")

            event_log.append_event(
                {
                    "event_type": "PHASE_TRANSITION",
                    "timestamp": "2026-02-22T12:00:02Z",
                    "cwd": root.as_posix(),
                    "from_phase": "Plan",
                    "to_phase": "Implement",
                    "phase_reason_code": "default_allow",
                    "triggers_fired": [],
                    "trigger_explanation": None,
                }
            )

            tool_summary = {
                "tool_name": "run",
                "exit_code": 0,
                "duration_ms": 3,
                "stdout_line_count": 1,
                "stderr_line_count": 0,
                "stderr_excerpt": "",
                "key_lines": [],
                "stdout_tail": ["planning output"],
                "truncation_flags": "NONE",
                "command_synopsis": "ls -la",
            }
            tool_candidate_content = json.dumps(tool_summary, sort_keys=True, separators=(",", ":"))
            runtime_state = {
                "phase": "Implement",
                "state": "Implement",
                "dirty_since_last_verify": False,
            }
            runtime_state_text = json.dumps(runtime_state, sort_keys=True, separators=(",", ":"))
            candidates = [
                {
                    "section": "State",
                    "kind": "tool_output_summary",
                    "content": tool_candidate_content,
                    "tool_summary": tool_summary,
                    "source_ref": "tool_result",
                    "observed_at": "2026-02-22T12:00:01Z",
                    "authority_tier": "runtime",
                    "validity_ttl": "PT1S",
                    "content_hash": hash_canonical_json(tool_candidate_content),
                },
                {
                    "section": "State",
                    "kind": "runtime_state",
                    "content": runtime_state_text,
                    "source_ref": "runtime_state",
                    "observed_at": "2026-02-22T12:00:03Z",
                    "authority_tier": "runtime",
                    "validity_ttl": "PT1S",
                    "content_hash": hash_canonical_json(runtime_state_text),
                },
            ]

            compiled = compile_and_log(
                candidates,
                policy_config=PolicyConfig.from_env(),
                event_log=event_log,
                timestamp="2026-02-22T12:00:04Z",
                cwd=root.as_posix(),
                workspace_fingerprint_hash="fp-1",
            )
            projection = ContextPackProjection(compiled.context_pack)
            conversation = "\n".join(
                str(item.get("content", "")) for item in projection.get_tier_items("CONVERSATION")
            )

            self.assertIn("tool_receipts: []", conversation)
            self.assertNotIn("Tool receipt summary:", conversation)


if __name__ == "__main__":
    unittest.main()
