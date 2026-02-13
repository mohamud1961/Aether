"""
Phase 2.1 Contract Tests: Authority Ladder for Conflict Resolution

Tests for CC-V02: When context items conflict, the compiler resolves
by authority rank.
"""

import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from enum import Enum


class TrustTier(Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


# Default authority ranking (highest to lowest)
AUTHORITY_LADDER: Dict[str, int] = {
    "user_instruction": 100,   # User always wins
    "governance_policy": 90,   # Safety rules
    "task_spec": 80,           # Task definition
    "verifier_result": 70,     # Verified facts
    "tool_output": 50,         # Tool observations
    "model_inference": 30,     # Model-generated content
    "cached_memory": 20,       # Historical context
}


@dataclass
class ContextItem:
    """An item in the context compiler's candidate pool."""
    item_id: str
    content: str
    source: str
    trust_tier: TrustTier
    created_at_step: int
    token_count: int
    observed_at: datetime
    conflict_key: Optional[str] = None  # Items with same conflict_key are in conflict
    expires_at: Optional[datetime] = None
    validity_steps: Optional[int] = None

    def authority_rank(self) -> int:
        """Get authority rank for this item."""
        return AUTHORITY_LADDER.get(self.source, 0)

    def is_valid(self, current_step: int, current_time: datetime) -> bool:
        """Check if this item is still valid."""
        if self.expires_at and current_time > self.expires_at:
            return False
        if self.validity_steps is not None:
            if (current_step - self.created_at_step) > self.validity_steps:
                return False
        return True


@dataclass
class ConflictResolution:
    """Record of a conflict resolution."""
    conflict_key: str
    winner_id: str
    loser_id: str
    winner_source: str
    loser_source: str
    reason: str  # "authority" or "recency" or "validity"


def resolve_conflicts(
    candidates: List[ContextItem],
    current_step: int,
    current_time: datetime,
    ff_authority_ladder: bool = True
) -> tuple[List[ContextItem], List[ConflictResolution]]:
    """
    Resolve conflicts among context items.
    
    Items with the same conflict_key are in conflict.
    Resolution order:
    1. Invalid items lose to valid items (validity)
    2. Higher authority wins (authority)
    3. More recent wins (recency)
    
    Returns: (resolved_items, conflict_log)
    """
    if not ff_authority_ladder:
        return candidates.copy(), []

    # Group by conflict_key
    conflict_groups: Dict[str, List[ContextItem]] = {}
    no_conflict: List[ContextItem] = []
    
    for item in candidates:
        if item.conflict_key:
            if item.conflict_key not in conflict_groups:
                conflict_groups[item.conflict_key] = []
            conflict_groups[item.conflict_key].append(item)
        else:
            no_conflict.append(item)

    # Resolve each conflict group
    resolved = no_conflict.copy()
    conflict_log: List[ConflictResolution] = []

    for conflict_key, items in conflict_groups.items():
        if len(items) == 1:
            resolved.append(items[0])
            continue

        # Find winner by comparing all pairs
        winner = items[0]
        for item in items[1:]:
            winner_valid = winner.is_valid(current_step, current_time)
            item_valid = item.is_valid(current_step, current_time)

            # Determine who wins this comparison
            new_winner = winner
            reason = "authority"  # default

            # 1. Validity trumps all
            if winner_valid and not item_valid:
                new_winner = winner
                reason = "validity"
            elif item_valid and not winner_valid:
                new_winner = item
                reason = "validity"
            # 2. Authority rank
            elif item.authority_rank() > winner.authority_rank():
                new_winner = item
                reason = "authority"
            elif item.authority_rank() == winner.authority_rank():
                # 3. Recency
                if item.observed_at > winner.observed_at:
                    new_winner = item
                    reason = "recency"

            # Log the conflict resolution
            if new_winner == item:
                conflict_log.append(ConflictResolution(
                    conflict_key=conflict_key,
                winner_id=item.item_id,
                    loser_id=winner.item_id,
                    winner_source=item.source,
                    loser_source=winner.source,
                    reason=reason
                ))
            else:
                conflict_log.append(ConflictResolution(
                    conflict_key=conflict_key,
                winner_id=winner.item_id,
                    loser_id=item.item_id,
                    winner_source=winner.source,
                    loser_source=item.source,
                    reason=reason
                ))
            winner = new_winner

        resolved.append(winner)

    return resolved, conflict_log


class TestAuthorityLadderContract(unittest.TestCase):
    """Contract tests for CC-V02: Authority Ladder."""

    def setUp(self):
        """Set up test fixtures."""
        self.now = datetime.now()
        self.current_step = 10

    def test_user_instruction_wins(self):
        """V02-CON-001: user_instruction beats tool_output."""
        user_item = ContextItem(
            item_id="user-1",
                content="User says: use Python 3.11",
            source="user_instruction",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=1,
            token_count=50,
            observed_at=self.now - timedelta(hours=1),
                conflict_key="python_version"
        )

        tool_item = ContextItem(
            item_id="tool-1",
                content="Detected Python 3.9",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=8,
            token_count=50,
            observed_at=self.now,  # More recent
            conflict_key="python_version"
        )

        resolved, log = resolve_conflicts(
            [user_item, tool_item],
            self.current_step,
            self.now
        )

        # User instruction should win
        result_ids = [item.item_id for item in resolved]
        self.assertIn("user-1", result_ids)
        self.assertNotIn("tool-1", result_ids)

        # Conflict should be logged
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].winner_id, "user-1")
        self.assertEqual(log[0].reason, "authority")

    def test_governance_beats_task_spec(self):
        """V02-CON-002: governance_policy beats task_spec."""
        governance_item = ContextItem(
            item_id="gov-1",
                content="Never run rm -rf",
            source="governance_policy",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=0,
            token_count=30,
            observed_at=self.now - timedelta(days=1),
                conflict_key="delete_policy"
        )

        task_item = ContextItem(
            item_id="task-1",
                content="Clean up by removing all files",
            source="task_spec",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=1,
            token_count=40,
            observed_at=self.now,
            conflict_key="delete_policy"
        )

        resolved, log = resolve_conflicts(
            [governance_item, task_item],
            self.current_step,
            self.now
        )

        result_ids = [item.item_id for item in resolved]
        self.assertIn("gov-1", result_ids)
        self.assertNotIn("task-1", result_ids)

    def test_verifier_beats_model_inference(self):
        """V02-CON-003: verifier_result beats model_inference."""
        verifier_item = ContextItem(
            item_id="verifier-1",
                content="Tests FAILED: 3 errors",
            source="verifier_result",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=9,
            token_count=50,
            observed_at=self.now,
            conflict_key="test_status"
        )

        model_item = ContextItem(
            item_id="model-1",
                content="I believe the tests pass",
            source="model_inference",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=10,
            token_count=40,
            observed_at=self.now,
            conflict_key="test_status"
        )

        resolved, _ = resolve_conflicts(
            [verifier_item, model_item],
            self.current_step,
            self.now
        )

        result_ids = [item.item_id for item in resolved]
        self.assertIn("verifier-1", result_ids)
        self.assertNotIn("model-1", result_ids)

    def test_same_authority_uses_recency(self):
        """V02-CON-004: Same authority level uses recency as tiebreaker."""
        old_tool = ContextItem(
            item_id="tool-old",
                content="File size: 100 bytes",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=5,
            token_count=30,
            observed_at=self.now - timedelta(minutes=10),
                conflict_key="file_size"
        )

        new_tool = ContextItem(
            item_id="tool-new",
                content="File size: 200 bytes",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=9,
            token_count=30,
            observed_at=self.now,  # More recent
            conflict_key="file_size"
        )

        resolved, log = resolve_conflicts(
            [old_tool, new_tool],
            self.current_step,
            self.now
        )

        result_ids = [item.item_id for item in resolved]
        self.assertIn("tool-new", result_ids)
        self.assertNotIn("tool-old", result_ids)

        self.assertEqual(log[0].reason, "recency")


class TestAuthorityLadderInteraction(unittest.TestCase):
    """Interaction tests for authority ladder edge cases."""

    def setUp(self):
        self.now = datetime.now()
        self.current_step = 10

    def test_stale_high_authority_vs_fresh_low(self):
        """V02-INT-001: Expired high-authority item loses to valid low-authority."""
        expired_user = ContextItem(
            item_id="user-expired",
                content="User instruction (expired)",
            source="user_instruction",
            trust_tier=TrustTier.TRUSTED,
            created_at_step=1,
            token_count=50,
            observed_at=self.now - timedelta(hours=2),
                expires_at=self.now - timedelta(hours=1),  # EXPIRED
            conflict_key="config_setting"
        )

        fresh_tool = ContextItem(
            item_id="tool-fresh",
                content="Current config from tool",
            source="tool_output",
            trust_tier=TrustTier.UNTRUSTED,
            created_at_step=9,
            token_count=50,
            observed_at=self.now,
            conflict_key="config_setting"
        )

        resolved, log = resolve_conflicts(
            [expired_user, fresh_tool],
            self.current_step,
            self.now
        )

        # Fresh low-authority beats expired high-authority
        result_ids = [item.item_id for item in resolved]
        self.assertIn("tool-fresh", result_ids)
        self.assertNotIn("user-expired", result_ids)

        # Reason should be validity
        self.assertEqual(log[0].reason, "validity")

    def test_conflict_resolution_logged(self):
        """V02-INT-002: All conflict resolutions are logged."""
        items = [
            ContextItem(
                item_id="item-a",
                content="A",
                source="tool_output",
                trust_tier=TrustTier.UNTRUSTED,
                created_at_step=5,
                token_count=10,
                observed_at=self.now - timedelta(minutes=5),
                conflict_key="key1"
            ),
            ContextItem(
                item_id="item-b",
                content="B",
                source="verifier_result",
                trust_tier=TrustTier.TRUSTED,
                created_at_step=8,
                token_count=10,
                observed_at=self.now,
                conflict_key="key1"
            ),
        ]

        resolved, log = resolve_conflicts(items, self.current_step, self.now)

        # Conflict should be logged
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].conflict_key, "key1")
        self.assertEqual(log[0].winner_id, "item-b")
        self.assertEqual(log[0].loser_id, "item-a")

    def test_no_conflict_no_log(self):
        """Items without conflict_key don't create log entries."""
        items = [
            ContextItem(
                item_id="item-1",
                content="Content 1",
                source="tool_output",
                trust_tier=TrustTier.UNTRUSTED,
                created_at_step=5,
                token_count=10,
                observed_at=self.now,
                conflict_key=None  # No conflict key
            ),
            ContextItem(
                item_id="item-2",
                content="Content 2",
                source="task_spec",
                trust_tier=TrustTier.TRUSTED,
                created_at_step=1,
                token_count=10,
                observed_at=self.now,
                conflict_key=None
            ),
        ]

        resolved, log = resolve_conflicts(items, self.current_step, self.now)

        # No conflicts → both included, no log
        self.assertEqual(len(resolved), 2)
        self.assertEqual(len(log), 0)


class TestAuthorityFeatureFlag(unittest.TestCase):
    """Test authority ladder feature flag behavior."""

    def test_ff_off_no_resolution(self):
        """When ff_authority_ladder=OFF, all items kept (no resolution)."""
        now = datetime.now()

        items = [
            ContextItem(
                item_id="item-1",
                content="Low authority",
                source="tool_output",
                trust_tier=TrustTier.UNTRUSTED,
                created_at_step=5,
                token_count=10,
                observed_at=now,
                conflict_key="same_key"
            ),
            ContextItem(
                item_id="item-2",
                content="High authority",
                source="user_instruction",
                trust_tier=TrustTier.TRUSTED,
                created_at_step=1,
                token_count=10,
                observed_at=now,
                conflict_key="same_key"
            ),
        ]

        # With FF OFF, both items kept
        resolved, log = resolve_conflicts(
            items, 10, now,
                ff_authority_ladder=False
        )
        self.assertEqual(len(resolved), 2)
        self.assertEqual(len(log), 0)

        # With FF ON, only winner kept
        resolved, log = resolve_conflicts(
            items, 10, now,
                ff_authority_ladder=True
        )
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].item_id, "item-2")


if __name__ == '__main__':
    unittest.main()
