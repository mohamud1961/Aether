import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.context_compiler import ADVISORY_MEMO_MAX_NOTES, compile_context
from aether.context_pack import ContextPackProjection, SECTION_STATE_V11
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.hashing import hash_canonical_json
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway


class TestF4AdvisoryMemoChannel(unittest.TestCase):
    def test_tool_receipt_persists_assistant_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            gate = GovernanceGate(GovernancePolicy(allowlist={"run"}, blocklist=set()), event_log)

            note = "Checked ls first; next step should inspect package manifest"
            tool_args = {
                "command": ["python3", "-c", "print('ok')"],
                "assistant_note": note,
            }
            gate.evaluate(
                "run",
                risk_tier="low",
                timestamp="2026-02-21T00:10:00Z",
                cwd=root.as_posix(),
                tool_args=tool_args,
            )

            gateway = ToolGateway(store, event_log, gate, root, PolicyConfig.from_env())
            result = gateway.execute(
                tool_name="run",
                tool_args=tool_args,
                timestamp="2026-02-21T00:10:01Z",
                cwd=Path("."),
            )

            self.assertEqual(result.assistant_note, note)
            self.assertEqual(result.summary.get("assistant_note"), note)
            self.assertEqual(result.event.get("assistant_note"), note)
            self.assertEqual(result.event.get("tool_summary", {}).get("assistant_note"), note)

    def test_context_pack_contains_bounded_advisory_memo(self) -> None:
        candidates = []
        for index in range(7):
            summary = {
                "tool_name": "run",
                "exit_code": 0,
                "duration_ms": 10 + index,
                "stdout_line_count": 1,
                "stderr_line_count": 0,
                "stderr_excerpt": "",
                "key_lines": [],
                "stdout_tail": [f"line-{index}"],
                "truncation_flags": "NONE",
                "assistant_note": f"note-{index}",
            }
            candidates.append(
                {
                    "section": SECTION_STATE_V11,
                    "kind": "tool_output_summary",
                    "content": summary,
                    "tool_output_summary": summary,
                    "source_ref": "tool_result",
                    "observed_at": f"2026-02-21T00:00:0{index}Z",
                    "authority_tier": "runtime",
                    "validity_ttl": "P1D",
                    "content_hash": hash_canonical_json(summary),
                }
            )

        policy = PolicyConfig.from_env()
        first = compile_context(candidates, policy_config=policy)
        second = compile_context(candidates, policy_config=policy)
        self.assertEqual(first.context_pack_hash, second.context_pack_hash)

        advisory_items = [
            item
            for item in first.context_pack[SECTION_STATE_V11]
            if str(item.get("kind", "")) == "advisory_memo"
        ]
        self.assertEqual(len(advisory_items), 1)
        entries = advisory_items[0]["content"]["entries"]
        self.assertEqual(len(entries), ADVISORY_MEMO_MAX_NOTES)
        self.assertEqual([entry["assistant_note"] for entry in entries], [f"note-{i}" for i in range(2, 7)])

        projection = ContextPackProjection(first.context_pack)
        conversation = "\n".join(
            str(item.get("content", "")) for item in projection.get_tier_items("CONVERSATION")
        )
        self.assertIn("Advisory Memo (non-authoritative; non-governance-driving)", conversation)
        self.assertIn('note="note-6"', conversation)


if __name__ == "__main__":
    unittest.main()
