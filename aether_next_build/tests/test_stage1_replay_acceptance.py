from __future__ import annotations

from pathlib import Path

from run_stage1_replay_acceptance import run


def test_stage1_replay_acceptance_flags_observed_failures(tmp_path: Path) -> None:
    root = Path("vm_goal_runs/20260701T144500Z_aether_next_vm_stage1_py311")
    summary = run(root, tmp_path)

    assert summary["passed"] is True
    rows = {row["case"]: row for row in summary["rows"]}
    assert rows["filter_false_clean"]["passed"] is True
    assert rows["sparql_repeated_evidence_display"]["passed"] is True
    assert rows["sparql_invented_predicates"]["passed"] is True

    # Slice A rows, replayed against the real repair-slice VM rerun traces.
    assert rows["openssl_structural_evidence"]["passed"] is True
    assert rows["openssl_structural_evidence"].get("gate", True) is True
    # Documented Slice A/B boundary: informational, does not gate the summary.
    assert rows["filter_semantic_phrase_independence"]["gate"] is False
