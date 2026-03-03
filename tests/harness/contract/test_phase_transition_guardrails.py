import tempfile
import unittest
from pathlib import Path

from aether.control_plane import ControlPlane
from aether.event_log import EventLog
from aether.tool_schema_translator import ToolSchemaTranslator


class TestPhaseTransitionGuardrails(unittest.TestCase):
    def _transition(
        self,
        *,
        control_plane: ControlPlane,
        current_state: str,
        requested_state: str,
        phase_reason_code: str,
        backtrack_context=None,
    ):
        return control_plane.transition(
            current_state=current_state,
            requested_state=requested_state,
            dirty_since_last_verify=False,
            verifier_result=None,
            workspace_fingerprint_hash="fp_hash",
            last_verified_fingerprint_hash="fp_hash",
            timestamp="2026-02-21T00:00:00Z",
            cwd="/tmp/workspace",
            phase_reason_code=phase_reason_code,
            backtrack_context=backtrack_context,
            transition_source="tool_request",
        )

    def test_no_op_transition_is_denied_with_closed_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log = EventLog(Path(tmpdir) / "events.jsonl")
            control_plane = ControlPlane(event_log=event_log)

            outcome = self._transition(
                control_plane=control_plane,
                current_state="Plan",
                requested_state="Plan",
                phase_reason_code="manual_request",
            )

            denied = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION_DENIED"
            ]
            self.assertTrue(denied)
            self.assertEqual(denied[-1].get("deny_reason_code"), "NO_OP_TRANSITION")
            self.assertIn(
                "requested_phase_differs_from_current_phase",
                denied[-1].get("missing_conditions", []),
            )
            self.assertEqual(outcome.next_state, "Plan")

    def test_backward_transition_without_context_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log = EventLog(Path(tmpdir) / "events.jsonl")
            control_plane = ControlPlane(event_log=event_log)

            outcome = self._transition(
                control_plane=control_plane,
                current_state="Implement",
                requested_state="Plan",
                phase_reason_code="plan_update_required",
            )

            denied = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION_DENIED"
            ]
            self.assertTrue(denied)
            self.assertEqual(denied[-1].get("deny_reason_code"), "BACKTRACK_CONTEXT_REQUIRED")
            self.assertIn(
                "backtrack_context_non_empty_object",
                denied[-1].get("missing_conditions", []),
            )
            self.assertEqual(outcome.next_state, "Implement")

    def test_backward_transition_with_context_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log = EventLog(Path(tmpdir) / "events.jsonl")
            control_plane = ControlPlane(event_log=event_log)

            outcome = self._transition(
                control_plane=control_plane,
                current_state="Implement",
                requested_state="Plan",
                phase_reason_code="plan_update_required",
                backtrack_context={
                    "failed_precondition": "plan_status_not_executing",
                    "next_action": "update_plan",
                },
            )

            transitions = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION"
            ]
            denied = [
                event
                for event in event_log.events
                if event.get("event_type") == "PHASE_TRANSITION_DENIED"
            ]

            self.assertFalse(denied)
            self.assertTrue(transitions)
            self.assertEqual(transitions[-1].get("from_phase"), "Implement")
            self.assertEqual(transitions[-1].get("to_phase"), "Plan")
            self.assertEqual(transitions[-1].get("phase_reason_code"), "plan_update_required")
            self.assertEqual(
                transitions[-1].get("backtrack_context", {}).get("failed_precondition"),
                "plan_status_not_executing",
            )
            self.assertEqual(outcome.next_state, "Plan")

    def test_transition_tool_schema_includes_backtrack_context(self) -> None:
        translator = ToolSchemaTranslator()
        tool = next(
            item for item in translator.get_harness_tools() if item.get("name") == "request_phase_transition"
        )
        properties = tool["parameters"]["properties"]
        self.assertIn("backtrack_context", properties)
        self.assertIn("enum", properties["phase_reason_code"])


if __name__ == "__main__":
    unittest.main()
