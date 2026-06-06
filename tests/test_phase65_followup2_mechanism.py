from __future__ import annotations

from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
)
from blocks.verification.followup2_closure_truth_gate import check
from blocks.verification.followup2_closure_truth_state import build_followup2_closure_state


def test_followup2_route_manifest_exposes_distinct_mechanism_surface():
    manifest = build_packet04_route_manifest(
        "candidate_plus_path_normalized_verifier_repair_projection_01",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    load_runtime_callables(manifest)

    routed = {row["runtime_key"]: row for row in manifest["routed_modules"]}
    assert {
        "orientation",
        "tools_getter",
        "tool_executor",
        "context",
        "verification",
    } <= set(routed)
    assert (
        routed["orientation"]["module_import_path"]
        == "blocks.orientation.phase65_followup2_doctrine:orient_path_normalized_verifier_repair_projection"
    )
    assert routed["context"]["module_import_path"] == (
        "blocks.context.path_normalized_verifier_repair_projection:manage"
    )
    assert routed["verification"]["module_import_path"] == (
        "blocks.verification.followup2_closure_truth_gate:check"
    )


def test_followup2_state_requires_real_verifier_rerun_and_splits_truth(tmp_path):
    (tmp_path / "output.txt").write_text("status=complete", encoding="utf-8")
    (tmp_path / "verify.sh").write_text(
        "#!/bin/bash\nif [ \"$(cat /app/output.txt)\" = \"status=complete\" ]; then echo PASS; exit 0; fi\necho FAIL\nexit 1\n",
        encoding="utf-8",
    )

    state = build_followup2_closure_state(
        "Run /app/verify.sh, repair /app/output.txt, rerun the verifier, and close only after /app/output.txt exists.",
        {
            "cwd": str(tmp_path),
            "closure_contract": {
                "required_deliverables": ["/app/output.txt", "/app/verify.sh"],
                "required_artifact_paths": ["/app/output.txt"],
                "requires_verifier": True,
                "initial_workspace_fingerprints": {"output.txt": "seed", "verify.sh": "seed"},
            },
            "execution_result": {
                "last_completion": {"text": "Updated /app/output.txt and reran verify.sh with PASS."},
                "steps": [
                    {"step": 0, "results": [{"command": "bash ./.phase65_verify.sh", "exit_code": 1, "stdout": "FAIL\n", "stderr": ""}]},
                    {"step": 1, "results": [{"command": "cat verify.sh && echo '---' && cat output.txt", "exit_code": 0, "stdout": "PASS\n", "stderr": ""}]},
                    {"step": 2, "results": [{"command": "bash ./.phase65_verify.sh; echo EXIT:$?", "exit_code": 0, "stdout": "PASS\nEXIT:0\n", "stderr": ""}]},
                ],
            },
        },
    )

    assert [row["step"] for row in state["verifier_attempts"]] == [0, 2]
    assert state["latest_verifier_result"]["status"] == "pass"
    assert state["closure_contract_status"] == "pass"
    assert state["task_truth_status"] == "ungraded"
    assert state["verifier_repair_status"] == "repaired_and_reran_to_pass"


def test_followup2_gate_persists_split_truth_state(tmp_path):
    (tmp_path / "output.txt").write_text("status=complete", encoding="utf-8")
    (tmp_path / "verify.sh").write_text("#!/bin/bash\necho PASS\nexit 0\n", encoding="utf-8")
    workspace_state = {
        "cwd": str(tmp_path),
        "model_claimed_done": True,
        "closure_contract": {
            "required_deliverables": ["/app/output.txt", "/app/verify.sh"],
            "required_artifact_paths": ["/app/output.txt"],
            "requires_verifier": True,
            "initial_workspace_fingerprints": {"output.txt": "seed", "verify.sh": "seed"},
        },
        "execution_result": {
            "last_completion": {"text": "Done. Wrote /app/output.txt and reran verify.sh with PASS."},
            "steps": [
                {"step": 1, "results": [{"command": "bash ./verify.sh", "exit_code": 0, "stdout": "PASS\n", "stderr": ""}]}
            ],
        },
    }

    assert check("Run /app/verify.sh and close after /app/output.txt exists.", workspace_state) is True
    assert workspace_state["authoritative_closure_state"]["closure_contract_status"] == "pass"
    assert workspace_state["authoritative_closure_state"]["task_truth_status"] == "ungraded"
