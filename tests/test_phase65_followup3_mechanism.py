from __future__ import annotations

from blocks.verification.followup3_closure_truth_gate import check
from blocks.verification.followup3_closure_truth_state import build_followup3_closure_state
from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
)


def test_followup3_route_manifest_exposes_distinct_mechanism_surface():
    manifest = build_packet04_route_manifest(
        "candidate_plus_path_normalized_target_resolution_guard_01",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    load_runtime_callables(manifest)

    routed = {row["runtime_key"]: row for row in manifest["routed_modules"]}
    assert {"orientation", "tools_getter", "tool_executor", "context", "verification"} <= set(routed)
    assert (
        routed["orientation"]["module_import_path"]
        == "blocks.orientation.phase65_followup3_doctrine:orient_path_normalized_target_resolution_guard"
    )
    assert routed["context"]["module_import_path"] == (
        "blocks.context.path_normalized_target_resolution_guard:manage"
    )
    assert routed["verification"]["module_import_path"] == (
        "blocks.verification.followup3_closure_truth_gate:check"
    )


def test_followup3_state_rejects_wrong_sibling_target_write(tmp_path):
    (tmp_path / "personal-site").mkdir(parents=True)
    (tmp_path / "personal-site" / "about.md").write_text("wrong target", encoding="utf-8")

    state = build_followup3_closure_state(
        "Recover /app/personal-site/_includes/about.md and close only when that exact target is fixed.",
        {
            "cwd": str(tmp_path),
            "closure_contract": {
                "required_deliverables": ["/app/personal-site/_includes/about.md"],
                "required_artifact_paths": ["/app/personal-site/_includes/about.md"],
                "requires_verifier": False,
                "initial_workspace_fingerprints": {},
            },
            "execution_result": {
                "last_completion": {
                    "text": "Done. Updated /app/personal-site/about.md and fixed the site.",
                },
                "steps": [],
            },
        },
    )

    assert state["closure_contract_status"] != "pass"
    assert "/app/personal-site/_includes/about.md" in state["path_mismatches"]
    assert "/app/personal-site/about.md" in state["wrong_target_written_paths"]
    assert "required_artifact_missing" in state["unresolved_blockers"]
    assert "wrong_target_path_write_detected" in state["unresolved_blockers"]


def test_followup3_projection_requires_exact_target_path_and_truthful_latest_verifier_state(tmp_path):
    (tmp_path / "output.txt").write_text("status=complete\n", encoding="utf-8")
    (tmp_path / "verify.sh").write_text("#!/bin/bash\necho PASS\nexit 0\n", encoding="utf-8")
    contract = {
        "required_deliverables": ["/app/output.txt", "/app/verify.sh"],
        "required_artifact_paths": ["/app/output.txt"],
        "requires_verifier": True,
        "initial_workspace_fingerprints": {},
    }
    steps = [
        {"step": 1, "results": [{"command": "bash ./verify.sh; echo EXIT:$?", "exit_code": 0, "stdout": "PASS\nEXIT:0\n", "stderr": ""}]}
    ]

    bad_state = build_followup3_closure_state(
        "Run /app/verify.sh and close only after /app/output.txt exists.",
        {
            "cwd": str(tmp_path),
            "closure_contract": contract,
            "execution_result": {"last_completion": {"text": "Done. Wrote /app/output.txt and latest verifier fail."}, "steps": steps},
            "model_claimed_done": True,
        },
    )
    assert bad_state["closure_contract_status"] != "pass"
    assert "final_answer_missing_or_incorrect_latest_verifier_state" in bad_state["unresolved_blockers"]

    workspace_state = {
        "cwd": str(tmp_path),
        "model_claimed_done": True,
        "closure_contract": contract,
        "execution_result": {
            "last_completion": {"text": "Done. Wrote /app/output.txt and latest verifier pass."},
            "steps": steps,
        },
    }
    assert check("Run /app/verify.sh and close only after /app/output.txt exists.", workspace_state) is True
    state = workspace_state["authoritative_closure_state"]
    assert state["closure_contract_status"] == "pass"
    assert state["task_truth_status"] == "ungraded"
    assert state["final_answer_projection"]["required_artifact_path_mentions"]["/app/output.txt"] is True
    assert state["final_answer_projection"]["latest_truthful_verifier_state_mentioned"] is True


def test_followup3_state_tracks_multiple_verifier_episodes_in_one_shell_result(tmp_path):
    (tmp_path / "output.txt").write_text("status=complete\n", encoding="utf-8")
    (tmp_path / "verify.sh").write_text("#!/bin/bash\necho PASS\nexit 0\n", encoding="utf-8")
    state = build_followup3_closure_state(
        "Run verify, repair, rerun, and close when latest verifier is pass with /app/output.txt.",
        {
            "cwd": str(tmp_path),
            "closure_contract": {
                "required_deliverables": ["/app/output.txt", "/app/verify.sh"],
                "required_artifact_paths": ["/app/output.txt"],
                "requires_verifier": True,
                "initial_workspace_fingerprints": {},
            },
            "execution_result": {
                "last_completion": {"text": "Done. /app/output.txt repaired, verifier fail then latest verifier pass."},
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
            "model_claimed_done": True,
        },
    )
    assert len(state["verifier_attempts"]) == 2
    assert state["latest_verifier_result"]["status"] == "pass"
    assert state["final_answer_projection"]["latest_truthful_verifier_state_mentioned"] is True
