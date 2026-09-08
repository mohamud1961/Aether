from __future__ import annotations

from aether.inspection_registry import admissible_verdict_refs, register_inspection_results
from aether.ledger import ExecutionLedger
from aether.verifier import parse_model_verifier_result
from aether.verifier_inspector import VerifierInspectionRequest
from aether.verify_completion_protocol import _verdict_admissibility_problem


class _Executor:
    pass


_DOMAIN_CONTRACT = {
    "filesystem_view": "task_rootfs_snapshot",
    "parent_processes_preserved": False,
    "parent_network_namespace_preserved": False,
    "outbound_network_enabled": False,
}


def _register_source(ledger: ExecutionLedger) -> str:
    row = register_inspection_results(
        (VerifierInspectionRequest(request_id="source", kind="read_file", path="/git/server/HEAD"),),
        ({
            "request_id": "source",
            "kind": "read_file",
            "path": "/git/server/HEAD",
            "content_hash": "head-v1",
            "excerpt": "ref: refs/heads/master\n",
            "bytes": 23,
            "offset": 0,
            "observation_origin": "executor_read",
        },),
        ledger=ledger,
        step=1,
        requester="model_verifier",
        executor=_Executor(),
        overlay=_Executor(),
        packet_signature="packet",
    )[0]
    return row["inspection_id"]


def _register_overlay(
    ledger: ExecutionLedger,
    *,
    source: str,
    command: str,
    exit_code: int,
    step: int = 2,
) -> dict:
    return register_inspection_results(
        (VerifierInspectionRequest(
            request_id="derive",
            kind="overlay_run_command",
            command=command,
            evidence_mode="derived",
            basis_refs=(source,),
            bound_input_refs=(source,),
        ),),
        ({
            "request_id": "derive",
            "kind": "overlay_run_command",
            "exit_code": exit_code,
            "success": exit_code == 0,
            "stdout": "",
            "stderr": "failed" if exit_code else "",
            "stdout_bytes": 0,
            "stderr_bytes": 6 if exit_code else 0,
            "observation_origin": "verifier_overlay",
            "executed_in": "verifier_overlay",
            "execution_isolation": "harbor_docker_snapshot_sibling",
            "isolation_backend": "harbor0200_docker_snapshot_sibling",
            "independent_isolation_verified": True,
            "isolation_cleanup_verified": True,
            "network_scope": "docker_none",
            "world_domain_contract": dict(_DOMAIN_CONTRACT),
        },),
        ledger=ledger,
        step=step,
        requester="model_verifier",
        executor=_Executor(),
        overlay=_Executor(),
        packet_signature="packet",
        require_independent_isolation=True,
    )[0]


def test_networkless_snapshot_failure_cannot_falsify_parent_live_http_service() -> None:
    ledger = ExecutionLedger()
    source = _register_source(ledger)
    row = _register_overlay(
        ledger,
        source=source,
        command=(
            "set -eu\n"
            "git clone /git/server repo\n"
            "curl --fail --silent http://127.0.0.1:8080/hello.html"
        ),
        exit_code=1,
    )

    direct, derived = admissible_verdict_refs(ledger)
    assert source in direct
    assert row["inspection_id"] not in derived
    assert row["observation_valid"] is True
    assert row["observed_outcome_success"] is False
    assert row["admissibility"] == "exploratory"
    assert row["method_domain_status"] == "substrate_limited"
    assert row["method_domain_dependencies"] == ["live_network_or_service"]
    assert row["method_domain_missing"] == ["parent_network_or_service"]
    assert row["world_domain_contract"] == _DOMAIN_CONTRACT


def test_negative_filesystem_or_computation_overlay_remains_falsifying_evidence() -> None:
    ledger = ExecutionLedger()
    source = _register_source(ledger)
    row = _register_overlay(
        ledger,
        source=source,
        command="python3 -c 'import sys; sys.exit(1)'",
        exit_code=1,
    )

    direct, derived = admissible_verdict_refs(ledger)
    assert source in direct
    assert row["inspection_id"] in derived
    assert row["admissibility"] == "verdict_eligible"
    assert row["method_domain_status"] == "compatible"
    assert row["method_domain_dependencies"] == []
    assert row["method_domain_missing"] == []


def test_private_pid_namespace_failure_cannot_falsify_parent_process_lifecycle() -> None:
    ledger = ExecutionLedger()
    source = _register_source(ledger)
    row = _register_overlay(
        ledger,
        source=source,
        command="pgrep -f 'python3 -m http.server 8080'",
        exit_code=1,
    )

    _, derived = admissible_verdict_refs(ledger)
    assert row["inspection_id"] not in derived
    assert row["method_domain_status"] == "substrate_limited"
    assert row["method_domain_dependencies"] == ["parent_process_lifecycle"]
    assert row["method_domain_missing"] == ["parent_process_lifecycle"]


def test_nonblocking_priority_cannot_launder_nonadmissible_repair_evidence() -> None:
    result = parse_model_verifier_result({
        "verdict": "needs_repair",
        "confidence": 0.98,
        "summary": "derived test failed",
        "findings": [{
            "finding_id": "end_to_end_push_deployment_failed",
            "verdict": "needs_repair",
            "priority": "high",
            "summary": "isolated test failed",
            "evidence": ["overlay exited 1"],
            "supporting_inspection_ids": ["inspection:limited"],
            "repair_instruction": "repair it",
            "applies_to": ["raw_task"],
        }],
        "method_validity": None,
    })
    problem = _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:direct"},
        derived_refs=set(),
    )
    assert "Solver-repair finding" in problem
    assert "inspection:limited" in problem



def test_live_sentinel_violated_finding_cannot_launder_exploratory_overlay() -> None:
    # Exact nested finding vocabulary from the retained configure-git-webserver
    # false rejection: top-level needs_repair, finding.verdict="violated".
    result = parse_model_verifier_result({
        "verdict": "needs_repair",
        "confidence": 0.98,
        "summary": "independent workflow failed",
        "findings": [{
            "finding_id": "end_to_end_push_deployment_failed",
            "verdict": "violated",
            "priority": "high",
            "summary": "isolated test failed",
            "evidence": ["overlay exited 1"],
            "supporting_inspection_ids": ["inspection:limited"],
            "repair_instruction": "repair the deployment path",
            "applies_to": ["raw_task"],
        }],
        "method_validity": None,
    })
    problem = _verdict_admissibility_problem(
        result,
        direct_refs={"inspection:direct"},
        derived_refs=set(),
    )
    assert "Solver-repair finding" in problem
    assert "inspection:limited" in problem


def test_top_level_needs_repair_controls_direct_grounding_not_nested_label() -> None:
    from aether.verify_completion_protocol import _solver_repair_is_fully_directly_grounded

    result = parse_model_verifier_result({
        "verdict": "needs_repair",
        "confidence": "high",
        "summary": "direct live probe shows a defect",
        "findings": [{
            "finding_id": "service-closed",
            "verdict": "violated",
            "priority": "high",
            "summary": "service endpoint is closed",
            "evidence": ["direct probe closed"],
            "supporting_inspection_ids": ["inspection:live-port"],
            "repair_instruction": "start service",
            "applies_to": ["raw_task"],
        }],
        "method_validity": None,
    })
    assert _solver_repair_is_fully_directly_grounded(
        result, {"inspection:live-port"}
    ) is True
    assert _solver_repair_is_fully_directly_grounded(result, set()) is False
