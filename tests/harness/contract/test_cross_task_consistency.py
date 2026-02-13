"""
Cross-Task Consistency Test (Layer 3)

Behavioral anti-hardcoding enforcement: verifies that policy decisions
are structurally invariant across different task identities.

Key invariant: policy(task_A, state) == policy(task_B, state) 
when the state structures are identical.
"""

import unittest
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SyntheticScenario:
    """A synthetic scenario for cross-task consistency testing."""
    # Task identity fields (should NOT affect policy decisions)
    task_name: str
    task_id: str
    task_category: str
    task_description: str

    # Structural fields (SHOULD affect policy decisions)
    exit_code: int
    files_written_count: int
    dirty_since_last_verify: bool
    verifier_result: Optional[str]  # 'pass', 'fail', None
    step_count: int
    truncation_detected: bool
    governance_tier: str  # 'safe', 'risky', 'destructive'


def make_scenario(
    task_name: str = "unknown-task",
    task_id: str = "task-000",
    task_category: str = "general",
    task_description: str = "A task",
    exit_code: int = 0,
    files_written_count: int = 5,
    dirty_since_last_verify: bool = True,
    verifier_result: Optional[str] = None,
    step_count: int = 10,
    truncation_detected: bool = False,
    governance_tier: str = "safe",
) -> SyntheticScenario:
    """Factory for creating synthetic test scenarios."""
    return SyntheticScenario(
        task_name=task_name,
                task_id=task_id,
        task_category=task_category,
        task_description=task_description,
        exit_code=exit_code,
        files_written_count=files_written_count,
        dirty_since_last_verify=dirty_since_last_verify,
        verifier_result=verifier_result,
        step_count=step_count,
        truncation_detected=truncation_detected,
        governance_tier=governance_tier,
    )


def policy_should_verify(scenario: SyntheticScenario) -> bool:
    """
    Example policy function: decides if verification is required.
    
    This function MUST be structurally invariant - it cannot use
    task_name, task_id, task_category, or task_description.
    """
    # CORRECT: uses only structural signals
    if scenario.dirty_since_last_verify and scenario.files_written_count > 0:
        return True
    if scenario.exit_code != 0:
        return True
    return False


def policy_governance_decision(scenario: SyntheticScenario) -> str:
    """
    Example policy: governance allow/deny decision.
    
    MUST NOT depend on task identity.
    """
    # CORRECT: uses only governance_tier
    if scenario.governance_tier == "destructive":
        return "deny"
    if scenario.governance_tier == "risky" and scenario.verifier_result != "pass":
        return "escalate"
    return "allow"


def policy_completion_valid(scenario: SyntheticScenario) -> bool:
    """
    Example policy: is a completion claim valid?
    
    MUST NOT depend on task identity.
    """
    # CORRECT: uses verifier_result and dirty flag
    if scenario.verifier_result != "pass":
        return False
    if scenario.dirty_since_last_verify:
        return False
    return True


class TestCrossTaskConsistency(unittest.TestCase):
    """
    Contract tests verifying policy functions are task-blind.
    
    The invariant: same structural inputs with different task identities
    must produce identical policy decisions.
    """

    def test_verify_policy_is_task_blind(self):
        """Policy decisions are identical across different task names."""
        # Create structurally identical scenarios with different task identities
        scenarios = [
            make_scenario(task_name="repair-history", task_id="t-001", task_category="git"),
            make_scenario(task_name="train-text-classifier", task_id="t-002", task_category="ml"),
            make_scenario(task_name="dual-language-build", task_id="t-003", task_category="languages"),
            make_scenario(task_name="completely-unknown-999", task_id="t-999", task_category="mystery"),
        ]

        decisions = [policy_should_verify(s) for s in scenarios]

        # All decisions must be identical
        self.assertTrue(
            all(d == decisions[0] for d in decisions),
            f"Policy depends on task identity! Decisions: {list(zip([s.task_name for s in scenarios], decisions))}"
        )

    def test_governance_policy_is_task_blind(self):
        """Governance decisions are identical across different task identities."""
        scenarios = [
            make_scenario(task_name="repair-history", governance_tier="risky", verifier_result=None),
            make_scenario(task_name="maze-escape", governance_tier="risky", verifier_result=None),
            make_scenario(task_name="security-audit", governance_tier="risky", verifier_result=None),
        ]

        decisions = [policy_governance_decision(s) for s in scenarios]

        self.assertTrue(
            all(d == decisions[0] for d in decisions),
            f"Governance depends on task identity! Decisions: {list(zip([s.task_name for s in scenarios], decisions))}"
        )

    def test_completion_policy_is_task_blind(self):
        """Completion validity is identical across different task identities."""
        # Scenario where completion IS valid
        valid_scenarios = [
            make_scenario(task_name="easy-task", verifier_result="pass", dirty_since_last_verify=False),
            make_scenario(task_name="hard-task", verifier_result="pass", dirty_since_last_verify=False),
            make_scenario(task_name="unknown-task", verifier_result="pass", dirty_since_last_verify=False),
        ]

        # Scenario where completion is NOT valid
        invalid_scenarios = [
            make_scenario(task_name="easy-task", verifier_result="fail", dirty_since_last_verify=False),
            make_scenario(task_name="hard-task", verifier_result="fail", dirty_since_last_verify=False),
            make_scenario(task_name="unknown-task", verifier_result="fail", dirty_since_last_verify=False),
        ]

        valid_decisions = [policy_completion_valid(s) for s in valid_scenarios]
        invalid_decisions = [policy_completion_valid(s) for s in invalid_scenarios]

        # All valid must be True, all invalid must be False
        self.assertTrue(all(valid_decisions), "Valid completion not recognized for all tasks")
        self.assertTrue(all(not d for d in invalid_decisions), "Invalid completion wrongly accepted")

    def test_structural_difference_changes_decision(self):
        """Structural differences (not task identity) produce different decisions."""
        # Same task, different structural state
        dirty_scenario = make_scenario(
            task_name="same-task",
                dirty_since_last_verify=True,
            files_written_count=5
        )
        clean_scenario = make_scenario(
            task_name="same-task",
                dirty_since_last_verify=False,
            files_written_count=0
        )

        dirty_decision = policy_should_verify(dirty_scenario)
        clean_decision = policy_should_verify(clean_scenario)

        # Structural difference SHOULD produce different decisions
        self.assertNotEqual(
            dirty_decision,
            clean_decision,
            "Structural difference did not change policy decision"
        )

    def test_category_and_description_are_ignored(self):
        """Task category and description must not affect decisions."""
        scenarios = [
            make_scenario(task_category="security", task_description="A security vulnerability task"),
            make_scenario(task_category="ml", task_description="A machine learning task"),
            make_scenario(task_category="crypto", task_description="A cryptography challenge"),
        ]

        verify_decisions = [policy_should_verify(s) for s in scenarios]
        gov_decisions = [policy_governance_decision(s) for s in scenarios]
        complete_decisions = [policy_completion_valid(s) for s in scenarios]

        self.assertTrue(all(d == verify_decisions[0] for d in verify_decisions))
        self.assertTrue(all(d == gov_decisions[0] for d in gov_decisions))
        self.assertTrue(all(d == complete_decisions[0] for d in complete_decisions))


class TestRealPolicyConsistency(unittest.TestCase):
    """
    Contract tests against actual harness policies.
    
    These tests import the real policy functions and verify they are task-blind.
    Skip if harness modules are not available.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from aether.control_plane import ControlPlane
            from aether.governance_gate import GovernanceGate
            cls.harness_available = True
        except ImportError:
            cls.harness_available = False

    def test_control_plane_is_task_blind(self):
        """Control plane state transitions are task-blind."""
        if not self.harness_available:
            self.skipTest("harness modules not available")

        # TODO: Add integration with real control_plane module
        # This is a placeholder for when harness is importable
        pass

    def test_governance_gate_is_task_blind(self):
        """Governance gate decisions are task-blind."""
        if not self.harness_available:
            self.skipTest("harness modules not available")

        # TODO: Add integration with real governance_gate module
        pass


if __name__ == '__main__':
    unittest.main()
