import tempfile
import unittest
from pathlib import Path

from aether.control_plane import ControlPlane
from aether.event_log import EventLog


class TestPhaseGatesHardDenies(unittest.TestCase):
    def _transition(
        self,
        *,
        control_plane: ControlPlane,
        current_state: str,
        requested_state: str,
        transition_source: str,
    ):
        return control_plane.transition(
            current_state=current_state,
            requested_state=requested_state,
            dirty_since_last_verify=False,
            verifier_result=None,
            workspace_fingerprint_hash="fp_hash",
            last_verified_fingerprint_hash="fp_hash",
            timestamp="2026-03-03T00:00:00Z",
            cwd="/tmp/workspace",
            phase_reason_code="manual_request",
            transition_source=transition_source,
        )

    def test_explore_and_plan_cannot_enter_verify_or_review_regardless_source(self) -> None:
        illegal = [
            ("Explore", "Verify"),
            ("Explore", "Review"),
            ("Plan", "Verify"),
            ("Plan", "Review"),
        ]

        for transition_source in ("tool_request", "system"):
            with self.subTest(transition_source=transition_source):
                with tempfile.TemporaryDirectory() as tmpdir:
                    event_log = EventLog(Path(tmpdir) / "events.jsonl")
                    control_plane = ControlPlane(event_log=event_log)

                    for current_state, requested_state in illegal:
                        outcome = self._transition(
                            control_plane=control_plane,
                            current_state=current_state,
                            requested_state=requested_state,
                            transition_source=transition_source,
                        )
                        self.assertEqual(outcome.next_state, current_state)

                    denied = [
                        event
                        for event in event_log.events
                        if event.get("event_type") == "PHASE_TRANSITION_DENIED"
                    ]
                    self.assertEqual(len(denied), len(illegal))
                    for event in denied:
                        self.assertEqual(event.get("deny_reason_code"), "PHASE_ORDER_VIOLATION")
                        self.assertIn(
                            "phase_legal_transition",
                            event.get("missing_conditions", []),
                        )


if __name__ == "__main__":
    unittest.main()
