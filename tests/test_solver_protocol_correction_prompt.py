from __future__ import annotations

from aether.kernel_solver_turn import handle_solver_parse_error
from aether.ledger import ExecutionLedger
from aether.model_hooks import ModelOutputError
from aether.runtime_ir import SolverTurn


class _Hooks:
    def __init__(self) -> None:
        self.last_raw_solver_output = '{"turn":{"kind":"act"}}\n{"turn":{"kind":"submit_outcome"}}'
        self.retry_messages = None

    def solve(self, messages, compiled):
        self.retry_messages = list(messages)
        return SolverTurn(kind="submit_outcome", summary="current evidence supports completion")


def test_pcr_format_correction_preserves_current_turn_semantics() -> None:
    hooks = _Hooks()
    ledger = ExecutionLedger()
    result = handle_solver_parse_error(
        hooks,
        ModelOutputError("provider_pcr_v0_invalid_json"),
        0, object(),
        [{"role": "system", "content": "stable solver context"}],
        ledger, {}, None, 0,
    )

    assert result is not None and result.kind == "submit_outcome"
    assert hooks.retry_messages is not None
    assert hooks.retry_messages[-2] == {
        "role": "assistant",
        "content": '{"turn":{"kind":"act"}}\n{"turn":{"kind":"submit_outcome"}}',
    }
    content = hooks.retry_messages[-1]["content"]
    lower = content.lower()
    assert "authorized pcr v0 turn" in lower
    assert "selection-and-copy format correction" in lower
    assert "not replanning" in lower
    assert "preserve the chosen action kind, arguments, claim, evidence references" in lower
    assert "capability" not in lower
    assert "working_state checkpoint" not in content
    assert "one current turn only" in lower
    assert "remove only invalid wrapping, prose, or extra candidate turns" in lower
    assert "do not simulate an observation" in lower
    assert "completion controls from unobserved state" in lower
    assert "sole key is turn" in content
    assert ledger.accounting_value("solver_protocol_correction_calls") == 1
    assert ledger.accounting_value("solver_provider_turns") == 1
    assert any(receipt.kind == "solver_parse_error" for receipt in ledger.all_receipts())


class _FreshDistinctHooks:
    def __init__(self) -> None:
        self.last_raw_solver_output = (
            '{"turn":{"kind":"act","summary":"current"}}\n'
            '{"turn":{"kind":"submit_outcome","summary":"future"}}'
        )
        self.retry_messages = None
        self.solve_calls = 0

    def solve(self, messages, compiled):
        self.solve_calls += 1
        self.retry_messages = list(messages)
        return SolverTurn(kind="act", summary="fresh current decision", actions=(), evidence_gap="The next action must resolve the current evidence gap")


def test_multi_distinct_solver_output_requests_one_fresh_turn() -> None:
    hooks = _FreshDistinctHooks()
    ledger = ExecutionLedger()
    original_messages = [{"role": "system", "content": "stable observed context"}]
    result = handle_solver_parse_error(
        hooks,
        ModelOutputError(
            "solver call failed: provider_pcr_v0_multiple_distinct_semantic_payloads"
        ),
        0,
        object(),
        original_messages,
        ledger,
        {},
        None,
        0,
    )

    assert result is not None and result.summary == "fresh current decision"
    assert hooks.solve_calls == 1
    assert hooks.retry_messages is not None
    assert hooks.retry_messages[:-1] == original_messages
    assert all(item.get("content") != hooks.last_raw_solver_output for item in hooks.retry_messages)
    notice = hooks.retry_messages[-1]
    assert notice["role"] == "user"
    lower = notice["content"].lower()
    assert "multiple distinct complete solver turns" in lower
    assert "none of its proposed actions or submissions executed" in lower
    assert "state are unchanged" in lower
    assert "one fresh current solver decision" in lower
    assert "do not assume" in lower
    assert "exactly one strict provider json object" in lower
    assert "dependency" not in lower
    assert "suggested recovery" not in lower
    receipt = next(item for item in ledger.all_receipts() if item.kind == "solver_protocol_correction_result")
    assert receipt.success is True
    assert receipt.payload["correction_mode"] == "fresh_single_turn_after_ambiguous_response"
    assert receipt.payload["rejected_output_provided_to_retry"] is False
    assert receipt.payload["candidate_execution_before_correction"] is False
    assert receipt.payload["observed_state_changed_before_correction"] is False
    assert ledger.accounting_value("solver_protocol_correction_calls") == 1
    assert ledger.accounting_value("solver_provider_turns") == 1


class _FreshDistinctInvalidHooks(_FreshDistinctHooks):
    def solve(self, messages, compiled):
        self.solve_calls += 1
        self.retry_messages = list(messages)
        self.last_raw_solver_output = '{"turn":'
        raise ModelOutputError("fresh correction still invalid")


def test_multi_distinct_solver_output_fails_closed_when_fresh_turn_invalid() -> None:
    hooks = _FreshDistinctInvalidHooks()
    ledger = ExecutionLedger()
    result = handle_solver_parse_error(
        hooks,
        ModelOutputError(
            "solver call failed: provider_pcr_v0_multiple_distinct_semantic_payloads"
        ),
        0,
        object(),
        [{"role": "system", "content": "stable observed context"}],
        ledger,
        {},
        None,
        0,
    )
    assert result is None
    assert hooks.solve_calls == 1
    retry = next(item for item in ledger.all_receipts() if item.receipt_id.endswith("solver_parse_error_retry"))
    assert retry.success is False
    assert retry.payload["correction_mode"] == "fresh_single_turn_after_ambiguous_response"
    assert retry.payload["rejected_output_provided_to_retry"] is False
    assert retry.payload["candidate_execution_before_correction"] is False


class _FieldRepairHooks:
    def __init__(self) -> None:
        self.last_raw_solver_output = (
            '{"kind":"act","summary":"write exact token","requested_check_ids":[],'
            '"claimed_artifacts":["out.txt"],"evidence_gap":"","actions":[{'
            '"action_id":"a1","kind":"write_file","capability_id":"filesystem",'
            '"arguments":{"path":"out.txt","content":"PASS-123"},'
            '"intent":"repair exact token","expected_observation":"file written",'
            '"if_fail_next":"inspect path"}]}'
        )
        self.retry_messages = None

    def solve(self, messages, compiled):
        self.retry_messages = list(messages)
        return SolverTurn(
            kind="act", summary="write exact token", evidence_gap="out.txt still has the wrong token",
            actions=(),
        )


def test_empty_evidence_gap_uses_bounded_protocol_field_correction() -> None:
    hooks = _FieldRepairHooks()
    ledger = ExecutionLedger()
    result = handle_solver_parse_error(
        hooks, ModelOutputError("provider_pcr_v0_schema_validation: claim must be non-empty"), 0, object(),
        [{"role": "system", "content": "stable context"}], ledger, {}, None, 0,
    )
    assert result is not None
    notice = hooks.retry_messages[-1]["content"]
    lower = notice.lower()
    assert "bounded protocol-field correction" in lower
    assert "change only the minimum field" in lower
    assert "active pcr v0 contract" in lower
    assert "preserve the selected action or submission" in lower
    assert "unless the stated error names that exact field as invalid" in lower
    assert "copy that chosen turn's field values unchanged" not in lower
    receipt = next(r for r in ledger.all_receipts() if r.kind == "solver_protocol_correction_result")
    assert receipt.payload["correction_mode"] == "bounded_protocol_field_correction"
    assert "protocol-field correction" in receipt.summary
