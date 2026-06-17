from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / "tracking/collab/autonomous_loop/eval_suite_v1_tournament_orchestration/scripts/update_candidate_memory.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("update_candidate_memory", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_candidate_iteration(
    root: Path,
    iteration: str,
    candidate_id: str,
    mechanism: str,
    *,
    route_id: str | None = None,
    target_cluster: list[str] | None = None,
    active_family: str | None = None,
    mechanism_family: str | None = None,
    candidate_meta_mechanism_family: str | None = None,
    static_status: str = "pass",
    review_approved: bool = True,
    route_plan_exit_code: int = 0,
    target_gate_passes: str = "1/2",
    full_board_passes: str = "",
    reason_codes: list[str] | None = None,
) -> None:
    iter_dir = root / "iterations" / iteration
    candidate_dir = iter_dir / "candidates" / candidate_id
    (candidate_dir / "target_gate").mkdir(parents=True, exist_ok=True)
    route_id_value = route_id or f"{candidate_id}_route"
    target_cluster_value = target_cluster or [
        "esv1_tooling_001_required_args_order_h001_workspace_band_transition"
    ]
    reason_codes_value = reason_codes or ["no_real_tool_result_evidence"]

    candidate_payload: dict[str, object] = {
        "candidate_id": candidate_id,
        "rank": 1,
        "mechanism": mechanism,
        "route_id_to_score": route_id_value,
        "target_cluster": target_cluster_value,
        "action": "new_variant",
    }
    if mechanism_family:
        candidate_payload["mechanism_family"] = mechanism_family

    slate_payload: dict[str, object] = {"candidates": [candidate_payload]}
    if active_family:
        slate_payload["active_family"] = active_family
    (iter_dir / "candidate_slate.json").write_text(json.dumps(slate_payload) + "\n", encoding="utf-8")

    candidate_meta_payload: dict[str, object] = {}
    if candidate_meta_mechanism_family:
        candidate_meta_payload["mechanism_family"] = candidate_meta_mechanism_family
    (candidate_dir / "candidate_meta.json").write_text(json.dumps(candidate_meta_payload) + "\n", encoding="utf-8")
    (candidate_dir / "static_filter.json").write_text(
        json.dumps({"static_status": static_status, "passed": static_status == "pass"}) + "\n", encoding="utf-8"
    )
    (candidate_dir / "patch_review.json").write_text(
        json.dumps({"approved_for_scoring": review_approved}) + "\n", encoding="utf-8"
    )
    (candidate_dir / "route_plan_only_exit_code.txt").write_text(f"{route_plan_exit_code}\n", encoding="utf-8")
    (candidate_dir / "target_gate_passes.txt").write_text(f"{target_gate_passes}\n", encoding="utf-8")
    if full_board_passes:
        (candidate_dir / "full_board_passes.txt").write_text(f"{full_board_passes}\n", encoding="utf-8")
    rows = []
    if target_gate_passes:
        rows.append(
            {
                "eval_id": "esv1_tooling_001_required_args_order",
                "verdict": "pass",
                "reason_codes": [],
            }
        )
        rows.append(
            {
                "eval_id": "esv1_tooling_001_required_args_order_h001_workspace_band_transition",
                "verdict": "fail",
                "reason_codes": reason_codes_value,
            }
        )
    (candidate_dir / "target_gate" / "result_rows.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_candidate_memory_derives_reason_surface_and_escalates_after_two_repeats(tmp_path: Path) -> None:
    module = _load_module()

    root = tmp_path / "tournament"
    (root / "iterations").mkdir(parents=True)
    (root / "status.json").write_text(json.dumps({"state": "running"}) + "\n", encoding="utf-8")

    _write_candidate_iteration(root, "iter_1", "cand_01", "receipt_completion_repair")
    _write_candidate_iteration(root, "iter_2", "cand_02", "toolcall_completion_guard")

    attempted = []
    for idir in sorted((root / "iterations").glob("iter_*")):
        attempted.extend(module.build_entry(idir, cand) for cand in module.iter_candidates(idir))
    attempted.sort(key=lambda row: (row.get("iteration", ""), int(row.get("rank", 1))))
    attempted, latest_repeat = module.annotate_attempts(attempted)

    first, second = attempted
    assert first["primary_reason_code"] == "no_real_tool_result_evidence"
    assert first["failure_surface"] == "tool_result_evidence"
    assert first["repeat_reason_streak"] == 1
    assert first["escalation_recommended"] is False

    assert second["primary_reason_code"] == "no_real_tool_result_evidence"
    assert second["failure_surface"] == "tool_result_evidence"
    assert second["repeat_reason_streak"] == 2
    assert second["escalation_recommended"] is True

    assert latest_repeat == {
        "repeat_reason_code": "no_real_tool_result_evidence",
        "repeat_failure_surface": "tool_result_evidence",
        "repeat_count": 2,
        "escalation_recommended": True,
    }


def test_candidate_memory_builds_mechanism_family_and_fingerprint_tables(tmp_path: Path) -> None:
    module = _load_module()

    root = tmp_path / "tournament"
    (root / "iterations").mkdir(parents=True)

    _write_candidate_iteration(
        root,
        "iter_1",
        "cand_01",
        "receipt_completion_repair",
        route_id="route_alpha",
        target_cluster=["eval_alpha"],
        active_family="tooling_tool_contract",
        target_gate_passes="1/2",
    )
    _write_candidate_iteration(
        root,
        "iter_2",
        "cand_02",
        "receipt_completion_repair",
        route_id="route_alpha",
        target_cluster=["eval_alpha"],
        active_family="tooling_tool_contract",
        target_gate_passes="2/2",
        full_board_passes="1/4",
    )
    _write_candidate_iteration(
        root,
        "iter_3",
        "cand_03",
        "toolcall_completion_guard",
        route_id="route_beta",
        target_cluster=["eval_beta"],
        active_family="tooling_tool_contract",
        target_gate_passes="",
        route_plan_exit_code=3,
    )

    attempted = []
    for idir in sorted((root / "iterations").glob("iter_*")):
        attempted.extend(module.build_entry(idir, cand) for cand in module.iter_candidates(idir))
    attempted.sort(key=lambda row: (row.get("iteration", ""), int(row.get("rank", 1))))
    attempted, _ = module.annotate_attempts(attempted)

    family_table = module.build_mechanism_family_table(attempted)
    assert len(family_table) == 1
    family = family_table[0]
    assert family["mechanism_family"] == "tooling_tool_contract"
    assert family["attempt_count"] == 3
    assert family["best_target_gate_result"] == {"raw": "2/2", "passes": 2, "total": 2}
    assert family["best_full_board_result"] == {"raw": "1/4", "passes": 1, "total": 4}
    assert family["common_failure_reasons"][0] == {"reason": "no_real_tool_result_evidence", "count": 2}
    assert family["last_attempted_iteration"] == "iter_3"
    assert family["scored_attempt_count"] == 2
    assert family["pre_score_failure_count"] == 1
    assert family["reached_scoring"] is True
    assert family["failed_pre_score"] is True

    fingerprint_table = module.build_mechanism_fingerprint_table(attempted)
    assert len(fingerprint_table) == 2
    top_fingerprint = fingerprint_table[0]
    assert top_fingerprint["mechanism_family"] == "tooling_tool_contract"
    assert top_fingerprint["mechanism"] == "receipt_completion_repair"
    assert top_fingerprint["route_id"] == "route_alpha"
    assert top_fingerprint["target_cluster"] == ["eval_alpha"]
    assert top_fingerprint["attempt_count"] == 2
    assert top_fingerprint["best_target_gate_result"] == {"raw": "2/2", "passes": 2, "total": 2}
    assert top_fingerprint["best_full_board_result"] == {"raw": "1/4", "passes": 1, "total": 4}
    assert top_fingerprint["scored_attempt_count"] == 2
    assert top_fingerprint["pre_score_failure_count"] == 0
