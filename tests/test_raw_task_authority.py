from __future__ import annotations

import json
from dataclasses import replace

import pytest

from aether.ledger import ExecutionLedger, Receipt
from aether.kernel_messages import build_solver_messages
from aether.model_interface import build_model_interface_capture
from aether.raw_task_authority import (
    RawTaskAuthorityError,
    text_sha256,
    validate_solver_messages,
    validate_verifier_packet,
)
from aether.runtime_ir import (
    BootstrapPolicy,
    CompiledRuntime,
    CompletionPolicy,
    ContextPolicy,
    EnvMap,
    EvalIndex,
    HelperToolPolicy,
    ObjectiveGraph,
    ProcessPolicy,
    RefusalPolicy,
)
from aether.task_contract import TaskClause, TaskContract
from aether.verifier_packets import build_verifier_packet


def _claim_bound_ledger() -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-0:primary_submission_claim:test",
        step=0,
        kind="primary_submission_claim",
        success=True,
        summary="test claim bound to current PCR state",
        payload={
            "claim_id": "test-claim",
            "claim": "current evidence supports verification",
            "evidence_refs": [],
            "evidence_receipt_ids": [],
            "evidence_bindings": [],
            **ledger.current_snapshot_binding_payload(),
        },
    ))
    return ledger


def _compiled(task: str = "Create the required artifact.") -> CompiledRuntime:
    contract = TaskContract.create(
        raw_task_prompt=task,
        clauses=(TaskClause("artifact", "The required artifact exists."),),
        schema_version="aether.test.contract.v1",
    )
    return CompiledRuntime(
        task_prompt=task,
        env_digest="env",
        objective_graph=ObjectiveGraph(),
        eval_index=EvalIndex(),
        selected_capabilities=(),
        stable_prefix_sections=(("task_contract", json.dumps(contract.as_payload(), sort_keys=True)),),
        context_policy=ContextPolicy(),
        process_policy=ProcessPolicy(),
        helper_tool_policy=HelperToolPolicy(),
        bootstrap_policy=BootstrapPolicy(),
        completion_policy=CompletionPolicy(),
        refusal_policy=RefusalPolicy(),
        enforced_monitors=(),
        check_plan_ids=(),
        forbidden_paths=(),
        task_contract=contract,
    )


def test_solver_packet_has_independent_exact_task_and_separate_contract_hash() -> None:
    compiled = _compiled("Preserve this exact task text.\nDo not shorten it.")
    messages = compiled.prefix_messages()
    raw = next(item["content"] for item in messages if item["content"].startswith("[raw_user_task]\n"))
    binding = json.loads(
        next(item["content"] for item in messages if item["content"].startswith("[raw_task_binding]\n"))
        .split("\n", 1)[1]
    )

    assert raw == "[raw_user_task]\n" + compiled.task_prompt
    assert binding["raw_task_sha256"] == text_sha256(compiled.task_prompt)
    assert binding["contract_sha256"] == compiled.task_contract_payload_sha256
    assert binding["raw_task_sha256"] != binding["contract_sha256"]


def test_solver_ordinary_compacted_and_correction_paths_keep_the_same_authority() -> None:
    compiled = _compiled("Keep this exact task across every Solver turn.")
    ordinary = build_solver_messages(compiled, {"context_epoch": 1, "state": {}})
    compacted = build_solver_messages(
        compiled,
        {"context_epoch": 2, "compression": "compacted", "state": {"files": {}}},
    )
    correction = [
        *ordinary,
        {"role": "user", "content": "Protocol correction: return one valid turn."},
    ]
    for messages in (ordinary, compacted, correction):
        validate_solver_messages(
            messages,
            expected_raw_task=compiled.task_prompt,
            expected_contract_sha256=compiled.task_contract_payload_sha256,
        )
        assert sum(
            item["content"].startswith("[raw_user_task]\n")
            for item in messages
        ) == 1


def test_cached_and_uncached_interface_captures_preserve_exact_solver_sections() -> None:
    compiled = _compiled("Cache status must not change the task authority.")
    messages = build_solver_messages(compiled, {"state": {}})
    cached = build_model_interface_capture(
        messages,
        model_role="solver",
        role_call_ordinal=1,
        max_output_tokens=16000,
        stable_prefix_count=len(messages) - 1,
    )
    uncached = build_model_interface_capture(
        messages,
        model_role="solver",
        role_call_ordinal=2,
        max_output_tokens=16000,
        stable_prefix_count=0,
    )
    for capture in (cached, uncached):
        exact = capture["messages"]
        validate_solver_messages(
            exact,
            expected_raw_task=compiled.task_prompt,
            expected_contract_sha256=compiled.task_contract_payload_sha256,
        )
        assert any(item["content"].startswith("[raw_task_binding]\n") for item in exact)


def test_solver_packet_fails_closed_when_raw_section_is_removed_or_changed() -> None:
    compiled = _compiled()
    messages = compiled.prefix_messages()
    without_raw = [item for item in messages if not item["content"].startswith("[raw_user_task]\n")]
    with pytest.raises(RawTaskAuthorityError, match="exactly one"):
        validate_solver_messages(
            without_raw,
            expected_raw_task=compiled.task_prompt,
            expected_contract_sha256=compiled.task_contract_payload_sha256,
        )

    changed = [dict(item) for item in messages]
    raw_index = next(i for i, item in enumerate(changed) if item["content"].startswith("[raw_user_task]\n"))
    changed[raw_index]["content"] += "\nchanged"
    with pytest.raises(RawTaskAuthorityError, match="changed or truncated"):
        validate_solver_messages(
            changed,
            expected_raw_task=compiled.task_prompt,
            expected_contract_sha256=compiled.task_contract_payload_sha256,
        )

    legacy = [
        *messages,
        {"role": "system", "content": "[task_prompt]\nold representation"},
    ]
    with pytest.raises(RawTaskAuthorityError, match="legacy task_prompt"):
        validate_solver_messages(
            legacy,
            expected_raw_task=compiled.task_prompt,
            expected_contract_sha256=compiled.task_contract_payload_sha256,
        )


def test_compiled_contract_cannot_disagree_with_independent_task() -> None:
    compiled = _compiled()
    conflicting = TaskContract.create(
        raw_task_prompt="A different task.",
        clauses=(TaskClause("artifact", "The required artifact exists."),),
        schema_version="aether.test.contract.v1",
    )
    with pytest.raises(RawTaskAuthorityError, match="differs"):
        replace(compiled, task_contract=conflicting, task_contract_payload_sha256="")


def test_verifier_packet_exposes_and_binds_raw_task_independently() -> None:
    compiled = _compiled("Verify the current artifact without changing this task.")
    packet = build_verifier_packet(
        compiled,
        _claim_bound_ledger(),
        envmap=EnvMap(task_prompt=compiled.task_prompt, workspace_root="/app"),
    )

    assert packet["raw_user_task"] == compiled.task_prompt
    assert packet["raw_task_sha256"] == text_sha256(compiled.task_prompt)
    assert packet["task_contract_sha256"] == compiled.task_contract_payload_sha256
    assert packet["raw_task_binding"]["relationship"] == "contract_is_additive_not_replacement"
    validate_verifier_packet(packet, expected_raw_task=compiled.task_prompt)


def test_verifier_ordinary_and_compacted_state_paths_keep_raw_binding() -> None:
    compiled = _compiled("Verify this exact task after compacting dynamic state.")
    ledger = _claim_bound_ledger()
    ordinary = build_verifier_packet(
        compiled,
        ledger,
        step=1,
        reason="ordinary",
        envmap=EnvMap(task_prompt=compiled.task_prompt, workspace_root="/app"),
    )
    compacted = build_verifier_packet(
        compiled,
        ledger,
        step=2,
        reason="compacted",
        envmap=EnvMap(task_prompt=compiled.task_prompt, workspace_root="/app"),
        dynamic_state={
            "schema_version": "dynamic_world_state.v1",
            "state_version": 2,
            "artifacts": {"/app/out.txt": {"status": "present"}},
        },
    )
    for packet in (ordinary, compacted):
        validate_verifier_packet(packet, expected_raw_task=compiled.task_prompt)
        assert packet["raw_task_sha256"] == text_sha256(compiled.task_prompt)
        assert packet["task_contract_sha256"] == compiled.task_contract_payload_sha256


def test_verifier_packet_fails_closed_when_raw_binding_is_missing_or_contract_differs() -> None:
    compiled = _compiled()
    packet = dict(
        build_verifier_packet(
            compiled,
            _claim_bound_ledger(),
            envmap=EnvMap(task_prompt=compiled.task_prompt, workspace_root="/app"),
        )
    )
    packet.pop("raw_user_task")
    with pytest.raises(RawTaskAuthorityError, match="missing or changed"):
        validate_verifier_packet(packet, expected_raw_task=compiled.task_prompt)

    conflicting = TaskContract.create(
        raw_task_prompt="A different task.",
        clauses=(TaskClause("artifact", "The required artifact exists."),),
        schema_version="aether.test.contract.v1",
    )
    with pytest.raises(RawTaskAuthorityError, match="differs"):
        build_verifier_packet(
            compiled,
            ExecutionLedger(),
            envmap=EnvMap(task_prompt=compiled.task_prompt, workspace_root="/app"),
            contract=conflicting,
        )

    forged = dict(
        build_verifier_packet(
            compiled,
            _claim_bound_ledger(),
            envmap=EnvMap(task_prompt=compiled.task_prompt, workspace_root="/app"),
        )
    )
    forged["task_contract_sha256"] = ""
    with pytest.raises(RawTaskAuthorityError, match="contract hash"):
        validate_verifier_packet(forged, expected_raw_task=compiled.task_prompt)


def test_duplicate_legacy_contract_sections_fail_closed() -> None:
    compiled = _compiled()
    with pytest.raises(RawTaskAuthorityError, match="duplicate"):
        replace(
            compiled,
            task_contract=None,
            stable_prefix_sections=(
                ("task_contract", dict(compiled.task_contract.as_payload()).__repr__()),
                ("task_contract", dict(compiled.task_contract.as_payload()).__repr__()),
            ),
        )
