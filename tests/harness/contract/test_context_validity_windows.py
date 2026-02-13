"""
Phase 2.1 Contract Tests: Context Item Validity Windows

Tests for CC-V01: Context items with validity metadata are correctly
filtered during ContextPack compilation.
"""

import unittest
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum


class TrustTier(Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass
class ContextItem:
    """An item in the context compiler's candidate pool."""
    item_id: str
    content: str
    source: str  # e.g., "task_spec", "tool_output", "user_instruction"
    trust_tier: TrustTier
    created_at_step: int
    token_count: int
    observed_at: datetime
    expires_at: Optional[datetime] = None  # None means never expires
    validity_steps: Optional[int] = None   # None means no step-based expiry

    def is_valid(self, current_step: int, current_time: datetime) -> bool:
        """Check if this item is still valid."""
        if self.expires_at and current_time > self.expires_at:
            return False
        if self.validity_steps is not None:
            if (current_step - self.created_at_step) > self.validity_steps:
                return False
        return True


def compile_context_pack(
    candidates: List[ContextItem],
    current_step: int,
    current_time: datetime,
    ff_validity_windows: bool = True
) -> List[ContextItem]:
    """
    Compile a context pack from candidates, filtering by validity.
    
    When ff_validity_windows is ON, invalid items are excluded.
    """
    if not ff_validity_windows:
        return candidates.copy()
    
    return [item for item in candidates if item.is_valid(current_step, current_time)]


class TestValidityWindowsContract(unittest.TestCase):
    """Contract tests for CC-V01: Validity Windows."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now()
        self.current_step = 10

    def test_expired_time_excluded(self):
        """V01-CON-001: Item with expires_at in the past is excluded."""
        expired_item = ContextItem(
            item_id="expired-1",
                content="This content has expired",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=1,
            token_count=50,
            observed_at=self.now - timedelta(hours=2),
                expires_at=self.now - timedelta(hours=1),  # Expired an hour ago
        )
        
        fresh_item = ContextItem(
            item_id="fresh-1",
                content="This content is fresh",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=9,
            token_count=50,
            observed_at=self.now,
            expires_at=self.now + timedelta(hours=1),  # Expires in an hour
        )

        candidates = [expired_item, fresh_item]
        result = compile_context_pack(candidates, self.current_step, self.now)

        # Expired item should be excluded
        result_ids = [item.item_id for item in result]
        self.assertNotIn("expired-1", result_ids)
        self.assertIn("fresh-1", result_ids)

    def test_expired_steps_excluded(self):
        """V01-CON-002: Item with validity_steps exceeded is excluded."""
        old_item = ContextItem(
            item_id="old-1",
                content="This content is too old by step count",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=2,
            token_count=50,
            observed_at=self.now - timedelta(minutes=30),
                validity_steps=5,  # Only valid for 5 steps
        )
        
        # Current step is 10, item created at step 2
        # Delta is 8 steps, validity_steps is 5 → EXPIRED

        recent_item = ContextItem(
            item_id="recent-1",
                content="This content is recent",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=8,
            token_count=50,
            observed_at=self.now,
            validity_steps=5,  # Only valid for 5 steps
        )
        # Delta is 2 steps, validity_steps is 5 → VALID

        candidates = [old_item, recent_item]
        result = compile_context_pack(candidates, self.current_step, self.now)

        result_ids = [item.item_id for item in result]
        self.assertNotIn("old-1", result_ids)
        self.assertIn("recent-1", result_ids)

    def test_fresh_item_included(self):
        """V01-CON-003: Item with expires_at in the future is included."""
        fresh_item = ContextItem(
            item_id="fresh-1",
                content="This content is still valid",
            source="task_spec",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=1,
            token_count=100,
            observed_at=self.now - timedelta(hours=1),
                expires_at=self.now + timedelta(days=1),  # Expires tomorrow
        )

        candidates = [fresh_item]
        result = compile_context_pack(candidates, self.current_step, self.now)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].item_id, "fresh-1")

    def test_no_expiry_always_valid(self):
        """V01-CON-004: Item with no expiry fields is always valid."""
        permanent_item = ContextItem(
            item_id="permanent-1",
                content="This content never expires",
            source="governance_policy",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=1,
            token_count=100,
            observed_at=self.now - timedelta(days=30),
                expires_at=None,  # Never expires
            validity_steps=None,  # No step limit
        )

        candidates = [permanent_item]
        
        # Test at many different steps
        for step in [10, 100, 1000]:
            result = compile_context_pack(candidates, step, self.now)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].item_id, "permanent-1")


class TestValidityWindowsDiagnostic(unittest.TestCase):
    """Diagnostic tests for validity windows."""

    def test_validity_check_deterministic(self):
        """V01-DIAG-001: Same inputs produce same validity decision."""
        now = datetime.now()
        current_step = 10

        item = ContextItem(
            item_id="test-1",
                content="Test content",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=8,
            token_count=50,
            observed_at=now,
            validity_steps=5,
        )

        # run validity check multiple times
        results = [item.is_valid(current_step, now) for _ in range(10)]

        # All results should be identical
        self.assertTrue(all(r == results[0] for r in results))

    def test_validity_does_not_affect_trust_tier(self):
        """V01-DIAG-002: Expired trusted item still has trust_tier=TRUSTED."""
        now = datetime.now()

        expired_trusted = ContextItem(
            item_id="expired-trusted-1",
                content="Expired but trusted",
            source="task_spec",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=1,
            token_count=100,
            observed_at=now - timedelta(hours=2),
                expires_at=now - timedelta(hours=1),  # Expired
        )

        # Item is invalid but trust tier unchanged
        self.assertFalse(expired_trusted.is_valid(10, now))
        self.assertEqual(expired_trusted.trust_tier, TrustTier.TRUSTED)


class TestValidityFeatureFlag(unittest.TestCase):
    """Test validity windows feature flag behavior."""

    def test_ff_off_includes_expired(self):
        """When ff_validity_windows=OFF, expired items are included."""
        now = datetime.now()

        expired_item = ContextItem(
            item_id="expired-1",
                content="Expired content",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=1,
            token_count=50,
            observed_at=now - timedelta(hours=2),
                expires_at=now - timedelta(hours=1),
        )

        candidates = [expired_item]
        
        # With FF OFF, expired items are included
        result = compile_context_pack(
            candidates, 10, now,
                ff_validity_windows=False
        )
        self.assertEqual(len(result), 1)

        # With FF ON, expired items are excluded
        result = compile_context_pack(
            candidates, 10, now,
                ff_validity_windows=True
        )
        self.assertEqual(len(result), 0)


if __name__ == '__main__':
    unittest.main()
