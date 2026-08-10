"""Generic method-integrity regressions from the final Verifier promotion board."""
from __future__ import annotations

import json
from types import SimpleNamespace

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger
from aether.method_independence import overlapping_accumulator_problem
from aether.model_hooks import ModelHooks
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.verifier import MethodValidityRecord, parse_model_verifier_result
from aether.verify_completion_protocol import _method_authority_problem


def _receipt(receipt_id: str, payload: dict):
    return SimpleNamespace(receipt_id=receipt_id, payload=payload)


def test_same_method_risk_rejects_direct_execution_of_inspected_implementation() -> None:
    source_id = "inspection:0:0:source"
    derived_id = "inspection:0:1:derived"
    ledger = SimpleNamespace(all_receipts=lambda: [
        _receipt(source_id, {
            "inspection_id": source_id,
            "route_kind": "read_file",
            "route_parameters": {"path": "/app/solver.py"},
        }),
        _receipt(derived_id, {
            "inspection_id": derived_id,
            "route_parameters": {
                "command": "python3 /app/solver.py /app/input.dat && cat /app/output.txt",
                "basis_refs": (source_id,),
                "bound_input_refs": (source_id,),
                "authoritative_structure": "the solver executable and emitted output",
                "method_summary": "run the implementation and inspect its output",
            },
        }),
    ])

    problem = _method_authority_problem(
        ledger,
        {derived_id},
        reject_same_method_overlap=True,
        observed_source_texts=("def solve(): return 7",),
    )

    assert "directly executes an inspected implementation" in problem
    assert "/app/solver.py" in problem


def test_same_method_risk_allows_distinct_checker_not_executing_inspected_source() -> None:
    source_id = "inspection:0:0:source"
    derived_id = "inspection:0:1:derived"
    ledger = SimpleNamespace(all_receipts=lambda: [
        _receipt(source_id, {
            "inspection_id": source_id,
            "route_kind": "read_file",
            "route_parameters": {"path": "/app/solver.py"},
        }),
        _receipt(derived_id, {
            "inspection_id": derived_id,
            "route_parameters": {
                "command": "python3 - <<'PY'\nfrom pathlib import Path\nprint(Path('/app/input.dat').stat().st_size)\nPY",
                "basis_refs": (source_id,),
                "bound_input_refs": (source_id,),
                "authoritative_structure": "raw input bytes",
                "method_summary": "measure raw input independently",
            },
        }),
    ])

    assert _method_authority_problem(
        ledger,
        {derived_id},
        reject_same_method_overlap=True,
        observed_source_texts=("def solve(): return 7",),
    ) == ""


def test_overlapping_accumulator_paths_are_rejected_generically() -> None:
    command = """python3 - <<'PY'
periods = {'today': (1, 1), 'total': (0, 1)}
counts = {p: {'ERROR': 0} for p in periods}
for row in rows:
    sev = 'ERROR'
    counts['total'][sev] += 1
    for period, bounds in periods.items():
        counts[period][sev] += 1
PY"""
    problem = overlapping_accumulator_problem(command)
    assert "updates bucket 'total' directly" in problem
    assert "iteration over mapping 'periods'" in problem


def test_single_path_accumulator_is_not_rejected() -> None:
    command = """python3 - <<'PY'
periods = {'today': (1, 1), 'total': (0, 1)}
counts = {p: {'ERROR': 0} for p in periods}
for row in rows:
    sev = 'ERROR'
    for period, bounds in periods.items():
        counts[period][sev] += 1
PY"""
    assert overlapping_accumulator_problem(command) == ""


def test_only_cited_execution_is_audited_after_method_revision() -> None:
    bad_id = "inspection:0:1:bad"
    good_id = "inspection:0:2:good"
    ledger = SimpleNamespace(all_receipts=lambda: [
        _receipt(bad_id, {
            "inspection_id": bad_id,
            "route_parameters": {
                "command": "python3 - <<'PY'\nperiods={'total': 1}\ncounts={p:0 for p in periods}\ncounts['total'] += 1\nfor p in periods: counts[p] += 1\nPY",
            },
        }),
        _receipt(good_id, {
            "inspection_id": good_id,
            "route_parameters": {
                "command": "python3 - <<'PY'\nperiods={'total': 1}\ncounts={p:0 for p in periods}\nfor p in periods: counts[p] += 1\nPY",
            },
        }),
    ])

    assert "internally inconsistent" in _method_authority_problem(ledger, {bad_id})
    assert _method_authority_problem(ledger, {good_id}) == ""



def test_final_method_validity_not_transport_placeholder_controls_authority() -> None:
    derived_id = "inspection:0:1:derived"
    ledger = SimpleNamespace(all_receipts=lambda: [
        _receipt(derived_id, {
            "inspection_id": derived_id,
            "route_parameters": {
                "command": "python3 verify_behavior.py",
                # Deliberately benign PERSISTENT transport placeholders. They must not
                # be able to launder a semantically proxy-only final method.
                "authoritative_structure": "PERSISTENT transport placeholder: final audit owns this",
                "method_summary": "PERSISTENT transport placeholder: final audit owns this",
            },
        }),
    ])
    bad_final = MethodValidityRecord(
        observed_structure="header label and summary metadata",
        executed_rule="extract the header label and compare strings",
        method_alignment="string equality with the descriptive label",
        authoritative_source_refs=("inspection:0:0:source",),
        execution_ref=derived_id,
    )
    problem = _method_authority_problem(
        ledger, {derived_id}, method_validity=bad_final,
    )
    assert "descriptive metadata" in problem


def test_good_final_method_validity_not_bad_transport_prose_controls_authority() -> None:
    derived_id = "inspection:0:1:derived"
    ledger = SimpleNamespace(all_receipts=lambda: [
        _receipt(derived_id, {
            "inspection_id": derived_id,
            "route_parameters": {
                "command": "python3 verify_behavior.py",
                # Historical/pre-execution prose is intentionally bad. F89's
                # production path must ignore it once a final validity record is
                # supplied and audit the post-execution method instead.
                "authoritative_structure": "header label metadata",
                "method_summary": "extract header and compare label",
            },
        }),
    ])
    good_final = MethodValidityRecord(
        observed_structure="raw behavioral input bytes",
        executed_rule="execute an independent checker over the raw bytes",
        method_alignment="the checker measures the behavioral effect rather than a descriptive proxy",
        authoritative_source_refs=("inspection:0:0:source",),
        execution_ref=derived_id,
    )
    assert _method_authority_problem(
        ledger, {derived_id}, method_validity=good_final,
    ) == ""


def test_circular_proxy_guard_uses_final_executed_rule_and_alignment() -> None:
    derived_id = "inspection:0:1:derived"
    ledger = SimpleNamespace(all_receipts=lambda: [
        _receipt(derived_id, {
            "inspection_id": derived_id,
            "route_parameters": {
                "command": "python3 checker.py",
                "authoritative_structure": "PERSISTENT transport placeholder",
                "method_summary": "PERSISTENT transport placeholder",
            },
        }),
    ])
    validity = MethodValidityRecord(
        observed_structure="raw source",
        executed_rule="regex extract declared expected value then compare == generated output",
        method_alignment="compare the extracted expected label to the output",
        authoritative_source_refs=("inspection:0:0:source",),
        execution_ref=derived_id,
    )
    problem = _method_authority_problem(
        ledger, {derived_id}, method_validity=validity,
        reject_circular_extraction_comparison=True,
    )
    assert "circularly extracts" in problem

def _compiled() -> tuple[EnvMap, object]:
    env = EnvMap(
        task_prompt="Verify an independently re-derivable result.",
        workspace_root="/app",
        visible_files=("solver.py",),
        capabilities={
            "shell": CapabilityDescriptor("shell", "Run commands"),
            "filesystem": CapabilityDescriptor("filesystem", "Read files"),
        },
    )
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(
        RuntimeConfigIR(
            architect_summary="test",
            solver_identity_prompt="solver",
            verifier_identity_prompt="verifier",
            selected_capabilities=("shell", "filesystem"),
        ),
        env,
    )
    return env, compiled


def _completion(execution_ref: str, *, incomplete_validity: bool = False) -> str:
    source_ref = "inspection:0:0:source"
    payload = {
        "verdict": "completed",
        "confidence": "high",
        "summary": "The independently derived result matches.",
        "completion_evidence": [{
            "requirement": "the result is independently re-derived",
            "observed": "the cited derived execution produced the matching result",
            "inspection_refs": [source_ref, execution_ref],
            "falsification_check": "a different independently derived value would contradict completion",
            "risk_refs": ["The result can look plausible while validated only by the same method."],
        }],
        "method_validity": ({
            "method_alignment": "the rule measures the determinant",
        } if incomplete_validity else {
            "observed_structure": "raw input was directly observed",
            "executed_rule": "derive the result without invoking the inspected solver implementation",
            "method_alignment": "the rule uses a method independent of the inspected implementation",
            "authoritative_source_refs": [source_ref],
            "execution_ref": execution_ref,
        }),
    }
    return json.dumps(payload)


def test_method_shape_correction_does_not_consume_method_revision_correction() -> None:
    env, compiled = _compiled()
    ledger = ExecutionLedger()
    source_ref = "inspection:0:0:source"
    bad_ref = "inspection:0:1:bad-method"
    good_ref = "inspection:0:2:good-method"
    responses = [
        json.dumps({
            "kind": "inspect",
            "requests": [{"request_id": "source", "kind": "read_file", "path": "/app/solver.py"}],
        }),
        json.dumps({
            "kind": "inspect",
            "requests": [{
                "request_id": "bad-method",
                "kind": "overlay_run_command",
                "verification_plan": {
                    "claim": "the result matches",
                    "authoritative_structure": "the executable implementation and its output",
                    "method_summary": "run the inspected implementation",
                    "proxy_risk": "the same method can repeat the same error",
                    "evidence_mode": "derived",
                    "basis": [{"ref": source_ref, "supported_fact": "the implementation path was observed"}],
                    "bound_input_refs": [source_ref],
                },
                "execution": {"kind": "overlay_run_command", "command": "python3 /app/solver.py"},
            }],
        }),
        _completion(bad_ref, incomplete_validity=True),
        _completion(bad_ref),
        json.dumps({
            "kind": "inspect",
            "requests": [{
                "request_id": "good-method",
                "kind": "overlay_run_command",
                "verification_plan": {
                    "claim": "the result matches",
                    "authoritative_structure": "raw input structure",
                    "method_summary": "derive a check from raw input without executing the implementation",
                    "proxy_risk": "the same method can repeat the same error",
                    "evidence_mode": "derived",
                    "basis": [{"ref": source_ref, "supported_fact": "raw structure was observed"}],
                    "bound_input_refs": [source_ref],
                },
                "execution": {"kind": "overlay_run_command", "command": "python3 - <<'PY'\nprint('independent=7')\nPY"},
            }],
        }),
        _completion(good_ref),
    ]
    calls=[]
    def verifier_model(messages, *, max_output_tokens=8000):
        calls.append(list(messages))
        return responses[len(calls)-1]
    hooks=ModelHooks(
        architect_model=lambda messages, max_output_tokens=8000: "{}",
        solver_model=lambda messages, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )
    class Executor: pass
    executor=Executor()
    def inspector(requests):
        raw=[]
        for request in requests:
            if request.kind == "read_file":
                raw.append({
                    "request_id": request.request_id,
                    "kind": request.kind,
                    "path": request.path,
                    "content_hash": "source-hash",
                    "excerpt": "def solve(): return 7",
                    "read_only": True,
                })
            else:
                raw.append({
                    "request_id": request.request_id,
                    "kind": request.kind,
                    "executed_in": "verifier_overlay",
                    "success": True,
                    "exit_code": 0,
                    "stdout": "independent=7",
                    "stderr": "",
                })
        return register_inspection_results(
            requests,
            raw,
            ledger=ledger,
            step=0,
            requester="model_verifier",
            executor=executor,
            overlay=executor,
            packet_signature="packet",
        )
    packet={
        "reason": "solver_submit",
        "verifier_evidence_admissibility_version": "v3",
        "evidence_requirements": {
            "re_derivable_claims": ["the result is independently re-derivable"],
            "false_positive_risks": ["The result can look plausible while validated only by the same method."],
        },
    }
    raw=hooks.verify_with_inspector(packet, compiled, ledger=ledger, inspector=inspector)
    assert parse_model_verifier_result(raw).verdict == "completed"
    assert len(calls) == 6
    shape_correction=json.loads(calls[3][-1]["content"])
    assert "method_validity is incomplete" in shape_correction["instruction"]
    revision_correction=json.loads(calls[4][-1]["content"])
    assert "not independent or internally self-consistent" in revision_correction["instruction"]
    assert "directly executes an inspected implementation" in revision_correction["problem"]
