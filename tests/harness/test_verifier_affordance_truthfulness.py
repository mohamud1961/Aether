from __future__ import annotations

import json
from types import SimpleNamespace

from aether.execution import CommandResult
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_verifier_context import persistent_verifier_model_packet
from aether.providers.azure_model import _persistent_verifier_native_tool_for_input
from aether.runtime_ir import EnvMap
from aether.verifier_inspector import (
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
    verifier_inspection_route_capabilities,
)


def _executor_without_comparator() -> SimpleNamespace:
    return SimpleNamespace(
        read_file=lambda path: "observed",
        read_file_bytes=lambda path: b"observed",
        run_command=lambda command, **kwargs: CommandResult(command, 0),
        probe_job=lambda target: SimpleNamespace(
            found=False, status="unknown", completed=False, succeeded=False,
            detail="missing", job_id="", process_id="", process_generation="",
            process_generation_verified=False, lifecycle_authority="", pid=None,
            exit_code=None,
        ),
    )


def test_route_capabilities_report_missing_comparator_without_changing_path_policy() -> None:
    executor = _executor_without_comparator()
    hooks = SimpleNamespace(perceive_image=lambda prompt, image, media: "image")
    capabilities = verifier_inspection_route_capabilities(
        executor, ledger=ExecutionLedger(), hooks=hooks,
    )

    assert "compare_initial_path" not in capabilities["available_direct_observation_kinds"]
    assert capabilities["unavailable_direct_observation_kinds"]["compare_initial_path"] == (
        "executor.compare_initial_path method is missing"
    )
    assert "read_file" in capabilities["available_direct_observation_kinds"]
    assert capabilities["permission_boundary"]["availability_is_separate_from_permission"] is True


def test_persistent_native_provider_hides_unavailable_or_targetless_direct_route() -> None:
    capabilities = verifier_inspection_route_capabilities(
        _executor_without_comparator(), ledger=ExecutionLedger(),
        hooks=SimpleNamespace(perceive_image=lambda prompt, image, media: "image"),
    )
    packet = persistent_verifier_model_packet({
        "verifier_runtime_capabilities": capabilities,
    })
    assert packet["verifier_runtime_capabilities"] == capabilities

    tool, _ids = _persistent_verifier_native_tool_for_input([{
        "role": "user",
        "content": json.dumps({"verifier_packet": packet}, sort_keys=True),
    }])
    kinds = set(
        tool["parameters"]["$defs"]["persistent_direct_locator_request"]
        ["properties"]["kind"]["enum"]
    )
    assert "compare_initial_path" not in kinds
    assert "read_file" in kinds
    # The route exists in the executor, but an empty ledger exposes no concrete
    # output handle. PERSISTENT should not offer a dead free-text affordance.
    assert "read_output" not in kinds
    assert "observe_existing_process" in kinds

    verdict_only_tool, _ids = _persistent_verifier_native_tool_for_input([
        {
            "role": "user",
            "content": json.dumps({"verifier_packet": packet}, sort_keys=True),
        },
        {
            "role": "user",
            "content": json.dumps({"verifier_turn_constraint": "verdict_only"}),
        },
    ])
    assert verdict_only_tool["parameters"]["properties"]["turn"]["anyOf"] == [
        {"$ref": "#/$defs/verdict_turn"},
    ]


def test_permission_boundary_and_route_availability_are_distinct_observations() -> None:
    envmap = EnvMap(task_prompt="inspect", workspace_root="/app")
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        "read-visible", 1, "read_file", True, "read visible",
        payload={"path": "allowed.txt"},
    ))
    compiled = SimpleNamespace(
        task_contract=SimpleNamespace(schema_version="persistent_v11_raw"),
        planned_checks=lambda: (),
    )
    requests = (
        VerifierInspectionRequest(
            request_id="visible-unsupported", kind="compare_initial_path", path="allowed.txt",
        ),
        VerifierInspectionRequest(
            request_id="hidden-unsupported", kind="compare_initial_path", path="secret.txt",
        ),
    )

    rows = execute_verifier_inspection_requests(
        requests,
        compiled=compiled, ledger=ledger, executor=_executor_without_comparator(),
        envmap=envmap,
    )

    available_failure, permission_failure = rows
    assert available_failure["failure_class"] == "verifier_route_unavailable"
    assert available_failure["observation_origin"] == "verifier_executor_surface"
    assert available_failure["route_available"] is False
    assert permission_failure["observation_origin"] == "persistent_epistemic_boundary"
    assert "forbidden" in permission_failure["error"]
