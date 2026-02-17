"""Verify strict eval loader accepts all runtime event types from Phase 3."""
import unittest

from aether.evals.utils.events import canonicalize_event_type, load_events


PHASE_3_RUNTIME_EVENT_TYPES = [
    "governance_decision",
    "model_request",
    "model_response",
    "model_error",
    "state_transition",
    "replay_gate",
    "approval_denied",
    "verifier_plan",
    "permission_request",
    "proceed_injection",
    "loop_breaker_trigger",
    "repair_attempt",
    "repair_termination",
]


class TestEvalsLoaderIngestsRuntimeEventTypes(unittest.TestCase):
    def test_all_phase3_event_types_canonicalize(self):
        """Every event type emitted during Phase 3 must canonicalize without error."""
        for event_type in PHASE_3_RUNTIME_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                result = canonicalize_event_type(event_type)
                self.assertIsInstance(result, str)
                self.assertTrue(len(result) > 0)

    def test_governance_decision_is_distinct(self):
        """governance_decision must NOT map to APPROVAL_GRANTED (semantically different)."""
        result = canonicalize_event_type("governance_decision")
        self.assertEqual(result, "GOVERNANCE_DECISION")
        self.assertNotEqual(result, "APPROVAL_GRANTED")

    def test_state_transition_maps_to_phase_transition(self):
        """state_transition is an alias for PHASE_TRANSITION."""
        result = canonicalize_event_type("state_transition")
        self.assertEqual(result, "PHASE_TRANSITION")


if __name__ == "__main__":
    unittest.main()
