from __future__ import annotations

from types import SimpleNamespace

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.ledger import ExecutionLedger, Receipt
from aether.persistent_task_contract import compile_persistent_task_contract
from aether.persistent_verifier_bridge import admit_persistent_completed_task_clauses
from aether.persistent_primary import persistent_primary_runtime_ir


def test_persistent_task_contract_preserves_raw_prompt_and_stable_source_text() -> None:
    prompt = (
        "Create /app/result.txt from the visible input.\n\n"
        "Requirements:\n"
        "- Preserve all non-target text exactly.\n"
        "- Remove every target marker.\n"
        "- Accept the input path as argv[1] and modify it in place.\n"
    )
    first = compile_persistent_task_contract(prompt)
    second = compile_persistent_task_contract(prompt)

    assert first.raw_task_prompt == prompt
    assert first.schema_version == "persistent_v0_source_faithful"
    assert first.as_payload() == second.as_payload()
    assert [clause.text for clause in first.clauses] == [
        "Create /app/result.txt from the visible input.",
        "Preserve all non-target text exactly.",
        "Remove every target marker.",
        "Accept the input path as argv[1] and modify it in place.",
    ]
    assert all(clause.clause_id.startswith("task:") for clause in first.clauses)


def test_persistent_task_contract_drops_heading_only_units_and_deduplicates_exact_repeats() -> None:
    prompt = "Task:\n- produce a.txt\n- verify b.txt\n- verify b.txt\n"
    contract = compile_persistent_task_contract(prompt)

    assert [clause.text for clause in contract.clauses] == [
        "produce a.txt",
        "verify b.txt",
    ]
    assert "a.txt" in contract.clauses[0].exact_atoms
    assert "b.txt" in contract.clauses[1].exact_atoms


def test_persistent_task_contract_splits_long_visible_paragraph_without_paraphrase() -> None:
    prompt = (
        "Create a current-state report that contains every requested value exactly as observed and "
        "retains the original labels from the visible source. "
        "Preserve the original ordering and do not invent missing values, substitute guessed values, "
        "or silently omit a requested field. "
        "Write the final report to /app/report.txt and keep the output plain text so the required "
        "state can be inspected directly."
    )
    contract = compile_persistent_task_contract(prompt)

    assert len(contract.clauses) == 3
    assert contract.raw_task_prompt == prompt
    normalized_prompt = " ".join(prompt.split())
    for clause in contract.clauses:
        assert " ".join(clause.text.split()) in normalized_prompt


def test_persistent_primary_compiles_each_source_clause_as_an_outcome_obligation(tmp_path) -> None:
    prompt = (
        "Create result.txt.\n\n"
        "- Preserve existing safe content.\n"
        "- Remove all prohibited markers.\n"
        "- Keep formatting unchanged.\n"
    )
    envmap = build_envmap_from_task(
        str(tmp_path),
        prompt,
        workspace_root=str(tmp_path),
    )
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
    objective, eval_index = compiler.analyze_envmap(envmap)
    runtime_ir = persistent_primary_runtime_ir(envmap, eval_index)
    compiled = compiler.compile(
        runtime_ir,
        envmap,
        objective_graph=objective,
        eval_index=eval_index,
    )

    assert runtime_ir.task_contract is not None
    assert compiled.task_contract is runtime_ir.task_contract
    expected_ids = tuple(clause.clause_id for clause in runtime_ir.task_contract.clauses)
    task_obligations = tuple(
        obligation.obligation_id
        for obligation in compiled.objective_graph.obligations
        if obligation.kind == "task"
    )
    assert task_obligations == expected_ids
    assert len(task_obligations) == 4


def test_persistent_bridge_rejects_completed_verdict_that_covers_only_one_source_clause() -> None:
    contract = compile_persistent_task_contract("Create result.txt.\n- Keep safe content.\n- Remove markers.\n")
    assert len(contract.clauses) == 3
    ledger = ExecutionLedger()
    generation = ledger.task_state_generation()
    ledger.record(Receipt(
        receipt_id="claim",
        step=1,
        kind="primary_submission_claim",
        success=True,
        summary="claim",
        payload={
            "task_state_generation": generation,
            "evidence_set_sha256": "a" * 64,
        },
    ))
    ledger.record(Receipt(
        receipt_id="inspection:1",
        step=1,
        kind="inspection_record",
        success=True,
        summary="one narrow inspection",
        payload={
            "inspection_id": "inspection:1",
            "task_state_generation": generation,
            "packet_signature": "packet-1",
            "eligible_for_proof": True,
            "actual_evidence_class": "exact_contract",
        },
    ))
    entry = SimpleNamespace(
        clause_ids=(contract.clauses[0].clause_id,),
        inspection_refs=("inspection:1",),
        evidence_class="exact_contract",
    )
    result = SimpleNamespace(verdict="completed", completion_evidence=(entry,))
    compiled = SimpleNamespace(solver_turn_protocol="persistent_v0", task_contract=contract)

    receipts = admit_persistent_completed_task_clauses(
        ledger,
        result=result,
        compiled=compiled,
        step=1,
        packet_signature="packet-1",
    )

    assert len(receipts) == 1
    assert receipts[0].success is False
    assert receipts[0].failure_class == "persistent_verifier_clause_coverage_incomplete"
    assert set(receipts[0].payload["missing_clause_ids"]) == {
        contract.clauses[1].clause_id,
        contract.clauses[2].clause_id,
    }


def test_source_factoring_adds_no_generated_semantic_text() -> None:
    prompt = "Do one thing.\n\n- Keep X.\n- Remove Y.\n"
    contract = compile_persistent_task_contract(prompt)

    normalized_prompt = " ".join(prompt.split())
    assert all(" ".join(clause.text.split()) in normalized_prompt for clause in contract.clauses)
    assert all("hidden" not in clause.text.lower() for clause in contract.clauses)
    assert all("grader" not in clause.text.lower() for clause in contract.clauses)



def test_f79_persistent_raw_clause_bridge_rejects_claimed_strength_above_actual_observation() -> None:
    contract = compile_persistent_task_contract("Create result.txt.\n")
    ledger = ExecutionLedger()
    generation = ledger.task_state_generation()
    ledger.record(Receipt(
        receipt_id="claim", step=1, kind="primary_submission_claim", success=True,
        summary="claim", payload={"task_state_generation": generation, "evidence_set_sha256": "a" * 64},
    ))
    ledger.record(Receipt(
        receipt_id="inspection:weak", step=1, kind="inspection_record", success=True,
        summary="partial observation", payload={
            "inspection_id": "inspection:weak",
            "task_state_generation": generation,
            "packet_signature": "packet-f79",
            "eligible_for_proof": True,
            "actual_evidence_class": "metadata_proxy",
        },
    ))
    entry = SimpleNamespace(
        clause_ids=(contract.clauses[0].clause_id,),
        inspection_refs=("inspection:weak",),
        evidence_class="exact_contract",
    )
    result = SimpleNamespace(verdict="completed", completion_evidence=(entry,))
    compiled = SimpleNamespace(solver_turn_protocol="persistent_v0", task_contract=contract)
    receipts = admit_persistent_completed_task_clauses(
        ledger, result=result, compiled=compiled, step=1, packet_signature="packet-f79",
    )
    assert len(receipts) == 1
    assert receipts[0].success is False
    assert receipts[0].failure_class == "persistent_verifier_clause_coverage_incomplete"
    assert contract.clauses[0].clause_id in receipts[0].payload["missing_clause_ids"]


def test_f79_persistent_raw_clause_bridge_admits_claim_not_stronger_than_actual_observation() -> None:
    contract = compile_persistent_task_contract("Create result.txt.\n")
    ledger = ExecutionLedger()
    generation = ledger.task_state_generation()
    ledger.record(Receipt(
        receipt_id="claim", step=1, kind="primary_submission_claim", success=True,
        summary="claim", payload={"task_state_generation": generation, "evidence_set_sha256": "a" * 64},
    ))
    ledger.record(Receipt(
        receipt_id="inspection:strong", step=1, kind="inspection_record", success=True,
        summary="exact observation", payload={
            "inspection_id": "inspection:strong",
            "task_state_generation": generation,
            "packet_signature": "packet-f79-strong",
            "eligible_for_proof": True,
            "actual_evidence_class": "exact_contract",
        },
    ))
    entry = SimpleNamespace(
        clause_ids=(contract.clauses[0].clause_id,),
        inspection_refs=("inspection:strong",),
        evidence_class="exact_contract",
    )
    result = SimpleNamespace(verdict="completed", completion_evidence=(entry,))
    compiled = SimpleNamespace(solver_turn_protocol="persistent_v0", task_contract=contract)
    receipts = admit_persistent_completed_task_clauses(
        ledger, result=result, compiled=compiled, step=1, packet_signature="packet-f79-strong",
    )
    assert len(receipts) == 1
    assert receipts[0].success is True
    assert receipts[0].payload["evidence_classes"] == ["exact_contract"]
    assert receipts[0].payload["actual_evidence_classes"] == ["exact_contract"]


def test_persistent_bridge_admits_composite_evidence_at_strongest_valid_cited_class() -> None:
    contract = compile_persistent_task_contract("Create result.txt.\n")
    ledger = ExecutionLedger(); generation = ledger.task_state_generation()
    ledger.record(Receipt(receipt_id="claim", step=1, kind="primary_submission_claim", success=True, summary="claim", payload={"task_state_generation": generation, "evidence_set_sha256": "a" * 64}))
    for rid, actual in (("inspection:source", "metadata_proxy"), ("inspection:derive", "independent_semantic")):
        ledger.record(Receipt(receipt_id=rid, step=1, kind="inspection_record", success=True, summary=rid, payload={"inspection_id": rid, "task_state_generation": generation, "packet_signature": "packet-composite", "eligible_for_proof": True, "actual_evidence_class": actual}))
    entry = SimpleNamespace(clause_ids=(contract.clauses[0].clause_id,), inspection_refs=("inspection:source", "inspection:derive"), evidence_class="independent_semantic")
    receipts = admit_persistent_completed_task_clauses(ledger, result=SimpleNamespace(verdict="completed", completion_evidence=(entry,)), compiled=SimpleNamespace(solver_turn_protocol="persistent_v0", task_contract=contract), step=1, packet_signature="packet-composite")
    assert len(receipts) == 1 and receipts[0].success is True
    assert receipts[0].payload["actual_evidence_classes"] == ["independent_semantic", "metadata_proxy"]


def test_persistent_bridge_composite_still_rejects_failed_supporting_ref() -> None:
    contract = compile_persistent_task_contract("Create result.txt.\n")
    ledger = ExecutionLedger(); generation = ledger.task_state_generation()
    ledger.record(Receipt(receipt_id="claim", step=1, kind="primary_submission_claim", success=True, summary="claim", payload={"task_state_generation": generation, "evidence_set_sha256": "a" * 64}))
    ledger.record(Receipt(receipt_id="inspection:source", step=1, kind="inspection_record", success=False, summary="failed", payload={"inspection_id":"inspection:source","task_state_generation":generation,"packet_signature":"packet-failed","eligible_for_proof":False,"actual_evidence_class":"metadata_proxy"}))
    ledger.record(Receipt(receipt_id="inspection:derive", step=1, kind="inspection_record", success=True, summary="derive", payload={"inspection_id":"inspection:derive","task_state_generation":generation,"packet_signature":"packet-failed","eligible_for_proof":True,"actual_evidence_class":"independent_semantic"}))
    entry=SimpleNamespace(clause_ids=(contract.clauses[0].clause_id,), inspection_refs=("inspection:source","inspection:derive"), evidence_class="independent_semantic")
    receipts=admit_persistent_completed_task_clauses(ledger,result=SimpleNamespace(verdict="completed",completion_evidence=(entry,)),compiled=SimpleNamespace(solver_turn_protocol="persistent_v0",task_contract=contract),step=1,packet_signature="packet-failed")
    assert len(receipts)==1 and receipts[0].success is False
    assert receipts[0].failure_class=="persistent_verifier_clause_coverage_incomplete"
