import unittest

from aether.context_compiler import compile_context
from aether.hashing import hash_canonical_json
from aether.policy_config import PolicyConfig


class TestContextCompilerDeterminism(unittest.TestCase):
    def test_deterministic_hashes(self) -> None:
        candidates = [
            {
                "section": "Doctrine",
                "content": "Do X",
                "authority_tier": "doctrine",
                "source_ref": "doctrine.md",
                "observed_at": "2026-01-26T00:00:00Z",
                "validity_ttl": "P1D",
                "content_hash": hash_canonical_json("Do X"),
            },
            {
                "section": "TaskSpec",
                "content": "Task Y",
                "authority_tier": "runtime",
                "source_ref": "task_spec",
                "observed_at": "2026-01-26T00:00:01Z",
                "validity_ttl": "P1D",
                "content_hash": hash_canonical_json("Task Y"),
            },
        ]

        policy = PolicyConfig.from_env()
        first = compile_context(candidates, policy_config=policy)
        second = compile_context(candidates, policy_config=policy)

        self.assertEqual(first.context_pack_hash, second.context_pack_hash)
        self.assertEqual(first.manifest_hash, second.manifest_hash)


if __name__ == "__main__":
    unittest.main()
