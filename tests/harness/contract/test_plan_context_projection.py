import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.context_compiler import compile_and_log
from aether.context_pack import ContextPackProjection
from aether.event_log import EventLog
from aether.hashing import hash_canonical_json
from aether.plan_state import default_task_and_plan, persist_plan_defined
from aether.policy_config import PolicyConfig


class TestPlanContextProjection(unittest.TestCase):
    def test_implement_compilation_renders_plan_block_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = ArtifactStore(root / "artifacts")
            event_log = EventLog(root / "event_log.jsonl")
            task_list, plan = default_task_and_plan(
                intent_contract_ref="intent_contract:v1",
                completion_contract_ref="completion_contract:v1",
                task_item_titles=["Create output file"],
            )
            persisted = persist_plan_defined(
                task_list=task_list,
                plan=plan,
                artifact_store=store,
                event_log=event_log,
                timestamp="2026-02-22T12:00:00Z",
                cwd=root.as_posix(),
            )
            artifact_payload = json.loads(store.read_bytes(persisted["artifact_id"]).decode("utf-8"))
            expected_plan = artifact_payload["implementation_plan"]

            state_content = json.dumps(
                {"phase": "Implement", "state": "Implement"},
                sort_keys=True,
                separators=(",", ":"),
            )
            candidates = [
                {
                    "section": "TaskSpec",
                    "kind": "task_spec",
                    "content": "Write output.txt from input.txt.",
                    "source_ref": "task_spec",
                    "observed_at": "2026-02-22T12:00:01Z",
                    "authority_tier": "runtime",
                    "validity_ttl": "P1D",
                    "content_hash": hash_canonical_json("Write output.txt from input.txt."),
                },
                {
                    "section": "State",
                    "kind": "runtime_state",
                    "content": state_content,
                    "source_ref": "runtime_state",
                    "observed_at": "2026-02-22T12:00:01Z",
                    "authority_tier": "runtime",
                    "validity_ttl": "PT1S",
                    "content_hash": hash_canonical_json(state_content),
                },
            ]

            tampered_plan = asdict(plan)
            tampered_plan["plan_id"] = "tampered-plan-id"
            outputs = compile_and_log(
                candidates,
                policy_config=PolicyConfig.from_env(),
                event_log=event_log,
                timestamp="2026-02-22T12:00:02Z",
                cwd=root.as_posix(),
                artifact_store=store,
                implementation_plan=tampered_plan,
                current_plan_step_id=plan.steps[0].step_id,
            )

            self.assertIn("PLAN", outputs.context_pack)
            self.assertEqual(len(outputs.context_pack["PLAN"]), 1)
            self.assertEqual(outputs.context_pack["PLAN"][0]["content"], expected_plan)

            projection = ContextPackProjection(outputs.context_pack)
            conversation_text = "\n".join(
                str(item.get("content", "")) for item in projection.get_tier_items("CONVERSATION")
            )
            self.assertIn("[PLAN]", conversation_text)
            self.assertIn("<<SECTION:PLAN:BEGIN>>", conversation_text)
            self.assertIn(json.dumps(expected_plan, sort_keys=True, separators=(",", ":")), conversation_text)


if __name__ == "__main__":
    unittest.main()
