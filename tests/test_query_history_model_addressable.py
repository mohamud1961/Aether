from __future__ import annotations

from types import SimpleNamespace

from aether.history_query import query_history
from aether.kernel_actions import handle_kernel_owned_action
from aether.ledger import ExecutionLedger, Receipt
from aether.pcr_capabilities import pcr_capability_contract
from aether.pcr_provider_protocol import PCR_ACTION_ARGUMENT_VARIANTS
from aether.runtime_ir import ActionRequest, ContextPolicy


def _receipt(step: int, kind: str, summary: str, **payload):
    return Receipt(
        receipt_id=f"step-{step}:{kind}", step=step, kind=kind,
        success=True, summary=summary, payload=payload,
    )


def test_query_history_is_literal_newest_first_and_returns_exact_addresses() -> None:
    receipts = (
        _receipt(1, "run_command", "compiled project", command="make", stdout_handle="1:out"),
        _receipt(2, "read_file", "read config", path="config.toml", file_handle="file:config.toml"),
        _receipt(3, "run_command", "ran tests", command="pytest", stdout_handle="3:out"),
    )
    result = query_history(receipts, "run_command")
    assert [row["step"] for row in result["results"]] == [3, 1]
    assert result["match_mode"] == "case_insensitive_literal_substring"
    assert result["results"][0]["receipt_handle"] == "receipt:step-3:run_command"
    assert result["results"][0]["stdout_handle"] == "3:out"
    assert result["ordering"] == "newest_first"


def test_query_history_has_no_relevance_ranking_and_pages_mechanically() -> None:
    receipts = tuple(
        _receipt(i, "run_command", f"same literal token {i}", command=f"echo token {i}")
        for i in range(1, 7)
    )
    page = query_history(receipts, "token", offset=2, limit=2)
    assert [row["step"] for row in page["results"]] == [4, 3]
    assert page["total_matches"] == 6
    assert page["more_available"] is True


def test_query_history_excludes_its_own_receipts_to_avoid_self_referential_memory() -> None:
    receipts = (
        _receipt(1, "run_command", "useful result", command="echo useful"),
        _receipt(2, "query_history", "literal history query useful: 1/1 matches", query="useful"),
    )
    result = query_history(receipts, "useful")
    assert [row["kind"] for row in result["results"]] == ["run_command"]


def test_query_history_is_always_available_kernel_owned_read_only_action() -> None:
    assert "query_history" in PCR_ACTION_ARGUMENT_VARIANTS
    assert ContextPolicy().model_context_window_tokens == 200_000
    assert ContextPolicy().compression_trigger_ratio == 1.0
    compiled = SimpleNamespace(selected_capabilities=())
    assert pcr_capability_contract(compiled)["query_history"] == ("kernel",)


def test_kernel_query_history_returns_addresses_not_semantic_summary() -> None:
    ledger = ExecutionLedger()
    ledger.record(_receipt(1, "run_command", "built alpha", command="make alpha", stdout_handle="1:out"))
    action = ActionRequest(
        action_id="q1", kind="query_history", capability_id="kernel",
        arguments={"query": "alpha"}, intent="retrieve prior observed history",
        expected_observation="matching receipt addresses", if_fail_next="continue",
    )
    receipt = handle_kernel_owned_action(
        action, 2, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), ledger,
    )
    assert receipt is not None and receipt.success
    assert receipt.kind == "query_history"
    row = receipt.payload["results"][0]
    assert row["receipt_handle"] == "receipt:step-1:run_command"
    assert row["command"] == "make alpha"
    assert "relevance" not in receipt.payload
    assert "score" not in row


def test_query_history_roundtrips_through_production_solver_parser() -> None:
    import json
    from aether.model_parse import parse_solver_turn
    from aether.pcr_provider_protocol import canonicalize_pcr_direct_tool_call

    canonical, _receipt = canonicalize_pcr_direct_tool_call(
        "query_history", json.dumps({"arguments": {"query": "pytest", "offset": 0, "limit": 8}}),
    )
    turn = parse_solver_turn(canonical)
    assert turn.kind == "act"
    assert len(turn.actions) == 1
    action = turn.actions[0]
    assert action.kind == "query_history"
    assert action.capability_id == "kernel"
    assert action.arguments == {"query": "pytest", "offset": 0, "limit": 8}
