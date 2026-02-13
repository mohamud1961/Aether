import unittest

from aether.context_compiler import compile_context
from aether.hashing import hash_canonical_json
from aether.policy_config import PolicyConfig


class TestConflictSurfacing(unittest.TestCase):
    def test_conflicts_are_surfaced(self) -> None:
        candidates = [
            {
                "section": "TaskSpec",
                "content": "A",
                "authority_tier": "runtime",
                "source_ref": "ref_a",
                "observed_at": "2026-01-26T00:00:00Z",
                "validity_ttl": "P1D",
                "content_hash": hash_canonical_json("A"),
                "conflict_key": "task_spec",
            },
            {
                "section": "TaskSpec",
                "content": "B",
                "authority_tier": "runtime",
                "source_ref": "ref_b",
                "observed_at": "2026-01-26T00:00:01Z",
                "validity_ttl": "P1D",
                "content_hash": hash_canonical_json("B"),
                "conflict_key": "task_spec",
            },
        ]
        policy = PolicyConfig.from_env()
        outputs = compile_context(candidates, policy_config=policy)

        self.assertTrue(outputs.manifest["conflicts"])
        self.assertTrue(outputs.context_pack["Conflicts"])
        self.assertEqual(outputs.manifest["conflicts"][0]["conflict_key"], "task_spec")


if __name__ == "__main__":
    unittest.main()
