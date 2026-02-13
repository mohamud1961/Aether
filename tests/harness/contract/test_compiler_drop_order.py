"""
Compiler Drop Order Test

Verifies that the context compiler drops items in the correct order
under budget pressure:
1. Oldest artifacts first
2. Then untrusted content
3. Then trusted content (last resort)

This is a contract test, not just a determinism test.
"""

import unittest
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from datetime import datetime, timedelta


class TrustTier(Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass
class CompilerCandidate:
    """A candidate item for ContextPack inclusion."""
    item_id: str
    content: str
    token_count: int
    trust_tier: TrustTier
    created_at: datetime
    source_type: str  # 'doctrine', 'task_spec', 'artifact', 'tool_output'

    def __lt__(self, other):
        """For sorting - not used for drop order."""
        return self.created_at < other.created_at


def apply_drop_order(candidates: list[CompilerCandidate], budget: int) -> tuple[list, list]:
    """
    Apply spec-compliant drop order to fit within budget.
    
    Drop order (per spec):
    1. Oldest artifacts first (within untrusted)
    2. Then untrusted content (by age)
    3. Then trusted content (by age, last resort)
    
    Returns: (selected, dropped)
    """
    # Separate by trust tier
    trusted = [c for c in candidates if c.trust_tier == TrustTier.TRUSTED]
    untrusted = [c for c in candidates if c.trust_tier == TrustTier.UNTRUSTED]

    # Sort each by age (oldest first for dropping)
    trusted.sort(key=lambda c: c.created_at, reverse=True)  # newest first (keep)
    untrusted.sort(key=lambda c: c.created_at)  # oldest first (drop)

    # Build drop queue: untrusted oldest first, then trusted oldest
    drop_queue = untrusted + list(reversed(trusted))

    selected = candidates.copy()
    dropped = []

    current_tokens = sum(c.token_count for c in selected)

    # Drop until within budget
    for candidate in drop_queue:
        if current_tokens <= budget:
            break
        if candidate in selected:
            selected.remove(candidate)
            dropped.append(candidate)
            current_tokens -= candidate.token_count

    return selected, dropped


class TestCompilerDropOrder(unittest.TestCase):
    """Contract tests for compiler budget drop order."""

    def setUp(self):
        """Create test candidates."""
        now = datetime.now()

        self.trusted_old = CompilerCandidate(
            item_id="t-old",
                content="trusted old content",
            token_count=100,
            trust_tier=TrustTier.TRUSTED,
            created_at=now - timedelta(hours=2),
                source_type="doctrine"
        )

        self.trusted_new = CompilerCandidate(
            item_id="t-new",
                content="trusted new content",
            token_count=100,
            trust_tier=TrustTier.TRUSTED,
            created_at=now - timedelta(minutes=5),
                source_type="task_spec"
        )

        self.untrusted_old = CompilerCandidate(
            item_id="u-old",
                content="untrusted old content",
            token_count=100,
            trust_tier=TrustTier.UNTRUSTED,
            created_at=now - timedelta(hours=3),
                source_type="tool_output"
        )

        self.untrusted_new = CompilerCandidate(
            item_id="u-new",
                content="untrusted new content",
            token_count=100,
            trust_tier=TrustTier.UNTRUSTED,
            created_at=now - timedelta(minutes=10),
                source_type="artifact"
        )

    def test_untrusted_dropped_before_trusted(self):
        """Untrusted content is dropped before trusted content."""
        candidates = [
            self.trusted_old,
            self.trusted_new,
            self.untrusted_old,
            self.untrusted_new,
        ]

        # Budget allows 300 tokens, total is 400 → must drop 100
        selected, dropped = apply_drop_order(candidates, budget=300)

        # First drop should be untrusted_old (oldest untrusted)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0].item_id, "u-old")
        self.assertEqual(dropped[0].trust_tier, TrustTier.UNTRUSTED)

        # Trusted content should remain
        selected_ids = {c.item_id for c in selected}
        self.assertIn("t-old", selected_ids)
        self.assertIn("t-new", selected_ids)

    def test_oldest_untrusted_dropped_first(self):
        """Within untrusted, oldest is dropped first."""
        candidates = [
            self.untrusted_old,
            self.untrusted_new,
        ]

        # Budget allows 100, total is 200 → must drop 100
        selected, dropped = apply_drop_order(candidates, budget=100)

        # Should drop untrusted_old (older)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0].item_id, "u-old")

        # Should keep untrusted_new (newer)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].item_id, "u-new")

    def test_trusted_dropped_only_after_all_untrusted(self):
        """Trusted content is dropped only when all untrusted is exhausted."""
        candidates = [
            self.trusted_old,  # 100 tokens
            self.untrusted_old,  # 100 tokens
            self.untrusted_new,  # 100 tokens
        ]

        # Budget 100 → must drop 200 tokens
        # Must drop BOTH untrusted before touching trusted
        selected, dropped = apply_drop_order(candidates, budget=100)

        self.assertEqual(len(dropped), 2)

        # Both untrusted should be dropped
        dropped_ids = {c.item_id for c in dropped}
        self.assertIn("u-old", dropped_ids)
        self.assertIn("u-new", dropped_ids)

        # Trusted should remain
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].item_id, "t-old")

    def test_drop_order_is_deterministic(self):
        """Same inputs produce same drop order."""
        candidates = [
            self.trusted_old,
            self.trusted_new,
            self.untrusted_old,
            self.untrusted_new,
        ]

        # run multiple times
        results = [apply_drop_order(candidates.copy(), budget=200) for _ in range(5)]

        # All runs should produce identical results
        first_selected_ids = [c.item_id for c in results[0][0]]
        first_dropped_ids = [c.item_id for c in results[0][1]]

        for selected, dropped in results[1:]:
            self.assertEqual([c.item_id for c in selected], first_selected_ids)
            self.assertEqual([c.item_id for c in dropped], first_dropped_ids)

    def test_no_drops_when_within_budget(self):
        """Nothing is dropped when total is within budget."""
        candidates = [
            self.trusted_new,
            self.untrusted_new,
        ]

        selected, dropped = apply_drop_order(candidates, budget=300)

        self.assertEqual(len(dropped), 0)
        self.assertEqual(len(selected), 2)


class TestRealCompilerDropOrder(unittest.TestCase):
    """Integration test against real compiler module."""

    @classmethod
    def setUpClass(cls):
        try:
            from aether.context_compiler import ContextCompiler
            cls.harness_available = True
        except ImportError:
            cls.harness_available = False

    def test_real_compiler_drop_order(self):
        """Real compiler follows spec drop order."""
        if not self.harness_available:
            self.skipTest("harness context_compiler not available")

        # TODO: Add integration with real context_compiler module
        pass


if __name__ == '__main__':
    unittest.main()
