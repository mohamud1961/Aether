from __future__ import annotations

from aether.verify_inspection_requests import _completed_inspection_is_semantically_grounded


def _shape_only():
    return [
        {"kind": "read_file", "path": "jump_analyzer.py", "excerpt": "print('ok')"},
        {"kind": "inspect_recent_receipts", "rows": []},
    ]


def _grounded():
    return [
        {
            "kind": "read_output",
            "handle": "9:a-1:stdout",
            "excerpt": "takeoff=87 landing=119 sampled_scores=[...]",
        }
    ]


def test_v3_nested_semantic_controls_reject_shape_only_inspection() -> None:
    packet = {
        "schema_version": "verifier_packet.v3",
        "verifier_evidence_admissibility_version": "v3",
        "evidence_requirements": {
            "false_positive_risks": ["shape-valid artifact may still be semantically wrong"],
            "local_limits": [
                {"source": "runtime_config", "statement": "shape-only checks are insufficient"}
            ],
        },
    }
    assert _completed_inspection_is_semantically_grounded(packet, _shape_only()) is False
    assert _completed_inspection_is_semantically_grounded(packet, _grounded()) is True


def test_legacy_top_level_semantic_controls_remain_supported() -> None:
    packet = {
        "false_positive_risks": ["shape-valid artifact may still be semantically wrong"],
        "local_verification_limits": [
            {"source": "runtime_config", "statement": "shape-only checks are insufficient"}
        ],
    }
    assert _completed_inspection_is_semantically_grounded(packet, _shape_only()) is False
    assert _completed_inspection_is_semantically_grounded(packet, _grounded()) is True


def test_semantic_grounding_guard_remains_inactive_without_declared_risk_or_limit() -> None:
    packet = {
        "schema_version": "verifier_packet.v3",
        "evidence_requirements": {"false_positive_risks": [], "local_limits": []},
    }
    assert _completed_inspection_is_semantically_grounded(packet, _shape_only()) is True


def test_verdict_eligible_derived_execution_is_result_bearing_semantic_evidence() -> None:
    packet = {
        "schema_version": "verifier_packet.v3",
        "evidence_requirements": {
            "false_positive_risks": ["same-method confirmation can repeat the same error"],
            "local_limits": [],
        },
    }
    derived = [{
        "kind": "overlay_run_command",
        "success": True,
        "admissibility": "verdict_eligible",
        "eligible_for_proof": True,
        "exit_code": 0,
        "stdout": "independent=7",
    }]
    assert _completed_inspection_is_semantically_grounded(packet, derived) is True


def test_exploratory_overlay_or_fixture_never_becomes_semantic_grounding() -> None:
    packet = {
        "schema_version": "verifier_packet.v3",
        "evidence_requirements": {
            "false_positive_risks": ["shape-only evidence is insufficient"],
            "local_limits": [],
        },
    }
    exploratory_command = [{
        "kind": "overlay_run_command",
        "success": True,
        "admissibility": "exploratory",
        "eligible_for_proof": False,
        "exit_code": 0,
        "stdout": "looks-good",
    }]
    fixture = [{
        "kind": "overlay_write_fixture",
        "success": True,
        "admissibility": "exploratory",
        "eligible_for_proof": False,
    }]
    assert _completed_inspection_is_semantically_grounded(packet, exploratory_command) is False
    assert _completed_inspection_is_semantically_grounded(packet, fixture) is False
