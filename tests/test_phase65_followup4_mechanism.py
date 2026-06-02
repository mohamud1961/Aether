from __future__ import annotations

from blocks.verification.followup4_closure_truth_gate import check
from blocks.verification.followup4_closure_truth_state import build_followup4_closure_state
from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
)


def test_followup4_route_manifest_exposes_merged_exact_target_surface():
    manifest = build_packet04_route_manifest(
        "candidate_plus_path_normalized_exact_target_projection_01",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    load_runtime_callables(manifest)
    routed = {row["runtime_key"]: row for row in manifest["routed_modules"]}
    assert {"orientation", "tools_getter", "tool_executor", "context", "verification"} <= set(routed)
    assert (
        routed["orientation"]["module_import_path"]
        == "blocks.orientation.phase65_followup4_doctrine:orient_path_normalized_exact_target_projection"
    )
    assert routed["context"]["module_import_path"] == "blocks.context.path_normalized_exact_target_projection:manage"
    assert routed["verification"]["module_import_path"] == "blocks.verification.followup4_closure_truth_gate:check"


def test_followup4_state_counts_multi_verifier_episodes_inside_single_shell_result(tmp_path):
    (tmp_path / "output.txt").write_text("status=complete\n", encoding="utf-8")
    (tmp_path / "verify.sh").write_text("#!/bin/bash\necho PASS\nexit 0\n", encoding="utf-8")
    state = build_followup4_closure_state(
        "Run /app/verify.sh, repair, rerun, and close after latest pass with /app/output.txt.",
        {
            "cwd": str(tmp_path),
            "closure_contract": {
                "required_deliverables": ["/app/output.txt", "/app/verify.sh"],
                "required_artifact_paths": ["/app/output.txt"],
                "requires_verifier": True,
                "initial_workspace_fingerprints": {},
            },
            "execution_result": {
                "last_completion": {"text": "Updated /app/output.txt. verifier failed first, latest verifier pass."},
                "steps": [
                    {
                        "step": 1,
                        "results": [
                            {
                                "command": "bash ./verify.sh; sed -i '' 's/partial/complete/' output.txt; bash ./verify.sh; echo EXIT:$?",
                                "exit_code": 0,
                                "stdout": "FAIL\nEXIT:1\nPASS\nEXIT:0\n",
                                "stderr": "",
                            }
                        ],
                    }
                ],
            },
            "model_claimed_done": True,
        },
    )
    summary = state["verifier_episode_summary"]
    assert summary["attempt_count"] == 2
    assert summary["shell_result_count"] == 1
    assert summary["multi_verifier_shell_results"] == 1
    assert state["latest_verifier_result"]["status"] == "pass"
    assert state["closure_contract_status"] == "pass"


def test_followup4_gate_accepts_truthful_latest_pass_with_fail_then_pass_history(tmp_path):
    (tmp_path / "output.txt").write_text("status=complete\n", encoding="utf-8")
    (tmp_path / "verify.sh").write_text("#!/bin/bash\necho PASS\nexit 0\n", encoding="utf-8")
    workspace_state = {
        "cwd": str(tmp_path),
        "model_claimed_done": True,
        "closure_contract": {
            "required_deliverables": ["/app/output.txt", "/app/verify.sh"],
            "required_artifact_paths": ["/app/output.txt"],
            "requires_verifier": True,
            "initial_workspace_fingerprints": {},
        },
        "execution_result": {
            "last_completion": {"text": "Done. /app/output.txt updated. verifier failed first, latest verifier pass."},
            "steps": [
                {
                    "step": 1,
                    "results": [
                        {
                            "command": "bash ./verify.sh; bash ./verify.sh",
                            "exit_code": 0,
                            "stdout": "FAIL\nEXIT:1\nPASS\nEXIT:0\n",
                            "stderr": "",
                        }
                    ],
                }
            ],
        },
    }
    assert check("Run verify and close when /app/output.txt is ready.", workspace_state) is True
