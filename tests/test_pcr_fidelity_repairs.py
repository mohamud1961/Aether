from __future__ import annotations

from types import SimpleNamespace

from aether.task_contract import TaskClause, TaskContract
from aether.task_metadata_loader import load_task_metadata
from aether.verifier_budget import VerifierPhaseBudget
from aether.verify_completion_protocol import (
    _budget_correction_payload,
    _compiled_outcome_clause_ids,
)


def test_pcr_raw_task_clause_is_valid_outcome_binding_when_proof_contract_empty() -> None:
    contract = TaskContract.create(
        "Create out.txt containing hello.",
        (TaskClause("task:raw", "Create out.txt containing hello."),),
        schema_version="pcr_v0_raw_task",
    )
    compiled = SimpleNamespace(proof_contract=(), task_contract=contract)
    assert _compiled_outcome_clause_ids(compiled) == {"task:raw"}


def test_certified_proof_contract_takes_precedence_over_task_clause_fallback() -> None:
    contract = TaskContract.create(
        "Do the task.",
        (TaskClause("task:raw", "Do the task."),),
        schema_version="pcr_v0_raw_task",
    )
    compiled = SimpleNamespace(
        proof_contract=({"clause_id": "proof:exact"},),
        task_contract=contract,
    )
    assert _compiled_outcome_clause_ids(compiled) == {"proof:exact"}


def test_budget_correction_exposes_exact_direct_observation_byte_limit() -> None:
    budget = VerifierPhaseBudget(
        max_result_bytes_per_request=8192,
        max_result_bytes_per_batch=65536,
    )
    payload = _budget_correction_payload(
        ValueError("direct observation span exceeds per-result byte budget"),
        budget,
    )
    assert payload["budget_limits"] == {
        "max_result_bytes_per_request": 8192,
        "max_result_bytes_per_batch": 65536,
    }
    assert "at most 8192 bytes" in payload["instruction"]


def test_terminal_bench_yaml_network_fields_are_preserved(tmp_path) -> None:
    (tmp_path / "task.yaml").write_text(
        "instruction: |\n  Do the task.\nnetwork_mode: no-network\nallow_internet: false\n",
        encoding="utf-8",
    )
    metadata = load_task_metadata(tmp_path)
    assert metadata["environment"]["network_mode"] == "no-network"
    assert metadata["environment"]["allow_internet"] is False
