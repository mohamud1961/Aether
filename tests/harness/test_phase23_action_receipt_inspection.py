from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether.inspection_registry import register_inspection_results
from aether.execution import MemoryExecutor, ProcessOrchestratorV2
from aether.ledger import ExecutionLedger, Receipt
from aether.providers.azure_model import _VERIFIER_DIRECT_TURN_SCHEMA
from aether.runtime_ir import ActionRequest, EnvMap
from aether.verifier_budget import DIRECT_OBSERVATION_KINDS
from aether.verifier_inspector import (
    execute_verifier_inspection_requests,
    parse_verifier_inspection_requests,
)


def _compiled():
    return SimpleNamespace(planned_checks=lambda: ())


def _executor():
    return SimpleNamespace()


def test_parser_accepts_clause_bound_action_history_only() -> None:
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "method-history",
            "kind": "inspect_action_receipts",
            "receipt_kind": "process_launch",
            "limit": 4,
            "clause_ids": ["use_worker"],
        }],
    })
    assert requests[0].clause_ids == ("use_worker",)
    assert requests[0].receipt_kind == "process_launch"
    direct = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "tagged-direct", "kind": "read_file",
            "path": "out.txt", "clause_ids": ["use_worker"],
        }],
    })[0]
    assert direct.clause_ids == ("use_worker",)
    # Direct tags are descriptive only. Kernel method binding remains limited
    # to inspect_action_receipts in verify_completion_protocol.invalid_clause_bindings.


def test_action_history_exposes_exact_safe_fields_without_outputs_or_narrative() -> None:
    ledger = ExecutionLedger()
    action = ActionRequest(
        action_id="launch", kind="launch_process", capability_id="managed_process",
        arguments={"service_name": "worker", "command": "python3 /app/worker.py"},
        intent="hidden model rationale", expected_observation="", if_fail_next="",
    )
    actual = ProcessOrchestratorV2().launch(
        action, 1, MemoryExecutor(), workspace_root="/app", interactive=False,
    )
    actual.payload["stdout_full"] = "secret output"
    actual.payload["stderr_full"] = "secret error"
    ledger.record(actual)
    request = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "method-history", "kind": "inspect_action_receipts",
            "receipt_kind": "process_launch", "limit": 5,
            "clause_ids": ["use_worker"],
        }],
    })
    results = execute_verifier_inspection_requests(
        request, compiled=_compiled(), ledger=ledger, executor=_executor(),
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    row = results[0]
    assert row["observation_origin"] == "ledger_action_history"
    assert row["clause_ids"] == ["use_worker"]
    item = row["rows"][0]
    assert item["payload"]["command"] == "python3 /app/worker.py"
    assert item["payload"]["process_id"].startswith("process:")
    assert item["state_change"] is True
    encoded = str(item)
    assert "secret output" not in encoded
    assert "secret error" not in encoded
    assert "hidden model rationale" not in encoded
    assert "model-authored narrative" not in encoded


def test_registered_action_history_is_direct_exact_contract_evidence() -> None:
    ledger = ExecutionLedger()
    action = ActionRequest(
        action_id="launch", kind="launch_process", capability_id="managed_process",
        arguments={"service_name": "worker", "command": "python3 worker.py"},
        intent="", expected_observation="", if_fail_next="",
    )
    ledger.record(ProcessOrchestratorV2().launch(
        action, 1, MemoryExecutor(), workspace_root="/app", interactive=False,
    ))
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "history", "kind": "inspect_action_receipts",
            "limit": 3, "clause_ids": ["use_worker"],
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests, compiled=_compiled(), ledger=ledger, executor=_executor(),
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    enriched = register_inspection_results(
        requests, raw, ledger=ledger, step=2, requester="model_verifier",
        executor=_executor(), overlay=None, packet_signature="packet",
    )
    assert enriched[0]["evidence_ceiling"] == "exact_contract"
    assert enriched[0]["observation_type"] == "execution_history"
    assert enriched[0]["method_evidence_only"] is True
    assert enriched[0]["admissibility"] == "direct_admissible"
    assert enriched[0]["eligible_for_proof"] is True


def test_provider_and_budget_advertise_action_history_route() -> None:
    kinds = (
        _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["inspection_request"]
        ["properties"]["kind"]["enum"]
    )
    properties = (
        _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["inspection_request"]
        ["properties"]
    )
    assert "inspect_action_receipts" in kinds
    assert "clause_ids" in properties
    assert "proof_ids" in properties
    assert "inspect_action_receipts" in DIRECT_OBSERVATION_KINDS


def test_empty_or_failed_history_is_not_affirmative_method_evidence() -> None:
    ledger = ExecutionLedger()
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "history", "kind": "inspect_action_receipts",
            "receipt_kind": "run_command", "limit": 3,
            "clause_ids": ["use_worker"],
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests, compiled=_compiled(), ledger=ledger, executor=_executor(),
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    assert raw[0]["success"] is False
    assert raw[0]["returned_count"] == 0
    enriched = register_inspection_results(
        requests, raw, ledger=ledger, step=2, requester="model_verifier",
        executor=_executor(), overlay=None, packet_signature="packet",
    )
    assert enriched[0]["eligible_for_proof"] is False
    assert enriched[0]["admissibility"] == "direct_admissible"


def test_legacy_receipt_aliases_do_not_impersonate_current_action_history() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="legacy", step=1, kind="command", success=True,
        summary="legacy alias", payload={"command": "python3 worker.py", "exit_code": 0},
    ))
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "history", "kind": "inspect_action_receipts",
            "limit": 3, "clause_ids": ["use_worker"],
        }],
    })
    raw = execute_verifier_inspection_requests(
        requests, compiled=_compiled(), ledger=ledger, executor=_executor(),
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )
    assert raw[0]["matching_count"] == 0
    assert raw[0]["success"] is False


def test_action_history_can_page_to_older_method_receipts() -> None:
    ledger = ExecutionLedger()
    for step, command in enumerate(("first", "second", "third"), start=1):
        ledger.record(Receipt(
            receipt_id=f"cmd-{step}", step=step, kind="run_command",
            success=True, summary=command,
            payload={"command": command, "exit_code": 0},
        ))
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "older-history",
            "kind": "inspect_action_receipts",
            "receipt_kind": "run_command",
            "limit": 1,
            "offset": 2,
            "clause_ids": ["use_worker"],
        }],
    })
    row = execute_verifier_inspection_requests(
        requests, compiled=_compiled(), ledger=ledger, executor=_executor(),
        envmap=EnvMap(task_prompt="task", workspace_root="/app"),
    )[0]
    assert row["rows"][0]["payload"]["command"] == "first"
    assert row["offset"] == 2
    assert row["older_available_count"] == 0
    assert row["newer_skipped_count"] == 2


def test_direct_read_file_preserves_compiled_proof_binding() -> None:
    request = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "request_id": "read-report",
            "kind": "read_file",
            "path": "report.txt",
            "clause_ids": ["outcome_report_file_exact_content"],
            "proof_ids": ["proof_report_file_exact_content"],
        }],
    })[0]
    assert request.clause_ids == ("outcome_report_file_exact_content",)
    assert request.proof_ids == ("proof_report_file_exact_content",)
