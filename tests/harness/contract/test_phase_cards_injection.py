import unittest

from aether.context_compiler import compile_context
from aether.context_pack import ContextPackProjection, SECTION_POLICY_V11, SECTION_STATE_V11
from aether.hashing import hash_canonical_json
from aether.policy_config import PolicyConfig


class TestChunkH3PhaseCardsInjection(unittest.TestCase):
    def _runtime_state_candidate(self, phase: str) -> dict:
        payload = {
            "phase": phase,
            "state": phase,
            "dirty_since_last_verify": False,
            "last_phase_transition_denied": None,
        }
        return {
            "section": SECTION_STATE_V11,
            "content": payload,
            "source_ref": "runtime_state",
            "observed_at": "2026-03-03T00:00:00Z",
            "authority_tier": "runtime",
            "validity_ttl": "PT1S",
            "content_hash": hash_canonical_json(payload),
        }

    def test_explore_phase_card_injected_exactly_into_policy_layer(self) -> None:
        policy = PolicyConfig.from_env()
        outputs = compile_context(
            [self._runtime_state_candidate("Explore")],
            policy_config=policy,
        )
        policy_items = outputs.context_pack.get(SECTION_POLICY_V11, [])
        phase_cards = [item for item in policy_items if item.get("kind") == "phase_card"]
        self.assertEqual(len(phase_cards), 1)
        content = phase_cards[0].get("content", "")
        self.assertIn("PHASE CARD — EXPLORE", content)
        self.assertIn("Do not request Verify or Review from Explore", content)

        state_items = outputs.context_pack.get(SECTION_STATE_V11, [])
        self.assertFalse(any(item.get("kind") == "phase_card" for item in state_items))

    def test_phase_card_visible_in_projection_doctrine_and_deterministic(self) -> None:
        policy = PolicyConfig.from_env()
        candidates = [self._runtime_state_candidate("Plan")]
        first = compile_context(candidates, policy_config=policy)
        second = compile_context(candidates, policy_config=policy)

        self.assertEqual(first.context_pack_hash, second.context_pack_hash)
        self.assertEqual(first.manifest_hash, second.manifest_hash)

        projection = ContextPackProjection(first.context_pack)
        doctrine_items = projection.get_tier_items("DOCTRINE")
        combined = "\n\n".join(str(item.get("content", "")) for item in doctrine_items)
        self.assertIn("PHASE CARD — PLAN", combined)
        self.assertIn("Plan must be stepwise and dependency-ordered", combined)

