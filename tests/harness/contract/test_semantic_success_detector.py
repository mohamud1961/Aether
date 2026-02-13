import unittest

from aether.detectors import (
    completion_claim_truthful,
    evidence_success_detected,
    semantic_success_detected,
    verification_hint_detected,
)


class TestSemanticSuccessDetector(unittest.TestCase):
    def test_evidence_success_rules(self) -> None:
        self.assertFalse(evidence_success_detected())
        self.assertFalse(
            evidence_success_detected(
                verifier_result={"status": "fail", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
            )
        )
        self.assertFalse(
            evidence_success_detected(
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp2",
            )
        )
        self.assertTrue(
            evidence_success_detected(
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
                verifier_plan_id=None,
            )
        )
        self.assertTrue(
            evidence_success_detected(
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
                verifier_plan_id="plan-1",
            )
        )
        self.assertFalse(
            evidence_success_detected(
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
                verifier_plan_id="",
            )
        )

    def test_completion_claim_truthful(self) -> None:
        self.assertFalse(
            completion_claim_truthful(
                completion_detected=False,
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
            )
        )
        self.assertFalse(
            completion_claim_truthful(
                completion_detected=True,
                verifier_result={"status": "fail", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
            )
        )
        self.assertTrue(
            completion_claim_truthful(
                completion_detected=True,
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
            )
        )

    def test_verification_hint_detected(self) -> None:
        self.assertFalse(
            verification_hint_detected(
                completion_detected=False,
                test_execution_detected=False,
            )
        )
        self.assertTrue(
            verification_hint_detected(
                completion_detected=True,
                test_execution_detected=False,
            )
        )
        self.assertTrue(
            verification_hint_detected(
                completion_detected=False,
                test_execution_detected=True,
            )
        )

    def test_semantic_success_alias(self) -> None:
        self.assertEqual(
            semantic_success_detected(
                completion_detected=True,
                test_execution_passed=False,
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
            ),
            completion_claim_truthful(
                completion_detected=True,
                verifier_result={"status": "pass", "workspace_fingerprint_hash": "fp1"},
                current_workspace_fingerprint_hash="fp1",
            ),
        )


if __name__ == "__main__":
    unittest.main()
