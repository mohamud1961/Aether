"""Completion-evidence protocol: content-blind gate on completed verdicts.

Design of record: audit addendum (FABLE5_ADVERSARIAL_AUDIT_20260708T165639Z.md)
Concern 1 — the harness checks presence, non-emptiness, and that
inspection_refs resolve to inspections actually performed in the round.
It never evaluates reasoning content.
"""
from __future__ import annotations

from dataclasses import replace
import json
from typing import Any

import pytest

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.model_hooks import (
    ModelHooks,
    ModelOutputError,
    VERIFIER_RUNTIME_CONTRACT,
    _completion_independence_problem,
    _completion_record_problem,
    _independent_derivation_refs,
    _refs_from_inspections,
)
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.proof_contract import ROUTE_EVIDENCE_CEILINGS
from aether.providers.azure_model import AzureProviderOutputError
from aether.verifier import (
    CompletionEvidenceEntry,
    CompletionEvidenceShapeError,
    METHOD_VALIDITY_REQUIRED_FIELDS,
    METHOD_VALIDITY_SHAPE,
    MethodValidityShapeError,
    parse_model_verifier_result,
)
from aether.verifier_inspector import (
    V3_DERIVED_INSPECTION_EXAMPLE,
    VerifierInspectionProtocolError,
    VerifierInspectionRequest,
    parse_verifier_inspection_requests,
)
from aether.verify_completion_protocol import (
    _inspection_protocol_correction,
    _budget_correction_payload,
    _provider_envelope_protocol_error,
    _provider_protocol_correction,
    _method_authority_problem,
    _packet_declares_circular_proxy_risk,
    _packet_declares_same_method_risk,
    _needs_repair_is_fully_directly_grounded,
    _refuse_admissibility,
    _verdict_admissibility_problem,
)
from aether.verifier_budget import VerifierBudgetError, VerifierPhaseBudget
from aether.verify_inspection_requests import _verifier_identity_prompt_for
from aether.workbench_compile import harness_config_to_runtime_ir
from aether.workbench_config import parse_harness_config_ir
from aether.workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT


def _make_envmap(**overrides: Any) -> EnvMap:
    defaults: dict[str, Any] = {
        "task_prompt": "Write out.txt with the decoded value.",
        "workspace_root": "/app",
        "visible_files": ("out.txt",),
        "capabilities": {
            "shell": CapabilityDescriptor(capability_id="shell", summary="run commands"),
            "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="read/write files"),
        },
    }
    defaults.update(overrides)
    return EnvMap(**defaults)


def _compiled():
    envmap = _make_envmap()
    return ConfigCompiler(CapabilityRegistry.from_envmap(envmap)).compile(
        RuntimeConfigIR(
            architect_summary="summary",
            solver_identity_prompt="solver",
            selected_capabilities=("shell", "filesystem"),
            verifier_identity_prompt="Task-specific verifier prompt.",
        ),
        envmap,
    )


def _ledger_stub():
    return type("_L", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()


def test_admissibility_refusal_is_itself_a_valid_uncertain_verdict() -> None:
    payload = json.loads(_refuse_admissibility("blocking finding lacks current evidence"))

    assert payload["verdict"] == "uncertain_missing_evidence"
    assert payload["missing_evidence_requests"]
    parsed = parse_model_verifier_result(payload)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert parsed.missing_evidence_requests


_INSPECT_REQUEST = json.dumps({
    "kind": "inspect",
    "summary": "Read the decisive output transcript.",
    "requests": [
        {"request_id": "probe-1", "kind": "read_output", "handle": "5:a-1:stdout", "span": 4000}
    ],
})


def _inspection_id(request_id: str) -> str:
    return f"inspection:test:{request_id}"


def _grounded_inspector(requests):
    return [
        {
            "request_id": req.request_id,
            "inspection_id": _inspection_id(req.request_id),
            "kind": req.kind,
            "handle": req.handle,
            "path": req.path,
            "excerpt": "observed value=7 matches requirement value=7",
            "eligible_for_proof": True,
            "evidence_ceiling": ROUTE_EVIDENCE_CEILINGS[req.kind],
        }
        for req in requests
    ]


def _completed(record: list[dict[str, Any]] | None, *, method_validity: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "verdict": "completed",
        "confidence": "high",
        "summary": "Deliverable matches the requirement.",
    }
    if record is not None:
        payload["completion_evidence"] = record
    if method_validity is not None:
        payload["method_validity"] = method_validity
    return json.dumps(payload)


def _valid_record(refs: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "requirement": "out.txt contains the decoded value per the task prompt",
            "observed": "read_output showed value=7 and out.txt contains 7",
            "inspection_refs": refs,
            "falsification_check": "a differing independently derived value would have contradicted the file",
        }
    ]


def _valid_method_validity(execution_ref: str, source_refs: list[str]) -> dict[str, Any]:
    return {
        "observed_structure": "The source record was observed before execution.",
        "executed_rule": "The command used the observed structure directly.",
        "method_alignment": "The command measures the authoritative structure rather than a descriptive proxy.",
        "authoritative_source_refs": source_refs,
        "execution_ref": execution_ref,
    }


def test_method_validity_runtime_contract_and_prompt_match_parser() -> None:
    assert tuple(METHOD_VALIDITY_SHAPE) == METHOD_VALIDITY_REQUIRED_FIELDS
    assert tuple(VERIFIER_RUNTIME_CONTRACT["method_validity_shape"]) == METHOD_VALIDITY_REQUIRED_FIELDS
    prompt = _verifier_identity_prompt_for(_compiled())
    for field in METHOD_VALIDITY_REQUIRED_FIELDS:
        assert field in prompt


def test_method_validity_parser_reports_exact_missing_fields() -> None:
    with pytest.raises(MethodValidityShapeError) as exc_info:
        parse_model_verifier_result({
            "verdict": "completed",
            "summary": "done",
            "method_validity": {
                "method_alignment": "the rule measures the determinant",
            },
        })
    assert exc_info.value.missing == (
        "observed_structure",
        "executed_rule",
        "authoritative_source_refs",
    )
    assert exc_info.value.invalid == ()


def test_method_validity_rejects_legacy_or_unknown_fields() -> None:
    with pytest.raises(MethodValidityShapeError) as exc_info:
        parse_model_verifier_result({
            "verdict": "completed",
            "summary": "done",
            "method_validity": {
                **_valid_method_validity("derived", ["direct"]),
                "behavioral_basis": "legacy prose must not be silently ignored",
            },
        })
    assert exc_info.value.invalid == (
        "method_validity.behavioral_basis is not accepted",
    )


def test_method_validity_non_object_is_a_schema_shape_error() -> None:
    with pytest.raises(MethodValidityShapeError) as exc_info:
        parse_model_verifier_result({
            "verdict": "completed",
            "summary": "done",
            "method_validity": "not-an-object",
        })
    assert exc_info.value.invalid == ("method_validity must be an object",)


def _run_verify(
    responses: list[str],
    *,
    packet_overrides: dict[str, Any] | None = None,
    inspector: Any = _grounded_inspector,
    compiled_override: Any | None = None,
) -> tuple[str, list[list[dict[str, str]]]]:
    calls: list[list[dict[str, str]]] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        calls.append(list(messages))
        return responses[min(len(calls) - 1, len(responses) - 1)]

    hooks = ModelHooks(
        architect_model=lambda m, *, max_output_tokens=8000: "{}",
        solver_model=lambda m, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )
    packet: dict[str, Any] = {
        "reason": "solver_submit", "task_prompt": "Write out.txt", "artifacts_present": ["out.txt"],
    }
    if packet_overrides:
        packet.update(packet_overrides)
    raw = hooks.verify_with_inspector(
        packet,
        compiled_override or _compiled(),
        ledger=_ledger_stub(),
        inspector=inspector,
    )
    return raw, calls


# ---------------------------------------------------------------------------
# Runtime gate behavior
# ---------------------------------------------------------------------------

def test_completed_without_record_gets_one_protocol_retry_then_accepts_valid_record() -> None:
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed(None),
        _completed(_valid_record([_inspection_id("probe-1")])),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(parsed.completion_evidence) == 1
    assert parsed.completion_evidence[0].inspection_refs == (_inspection_id("probe-1"),)
    assert len(calls) == 3
    retry_instruction = calls[2][-1]["content"]
    assert "completion_evidence" in retry_instruction
    assert "missing or empty" in retry_instruction


def test_completed_with_unresolvable_refs_is_refused_as_protocol_event() -> None:
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed(_valid_record(["ghost.txt"])),
        _completed(_valid_record(["ghost.txt"])),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert parsed.findings
    assert parsed.findings[0].finding_id == "vf-completion-evidence-record"
    assert parsed.findings[0].applies_to == ("completion_evidence",)
    assert "do not match any inspection" in parsed.summary
    assert len(calls) == 3


def test_completed_with_valid_record_is_accepted_without_retry() -> None:
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed(_valid_record([_inspection_id("probe-1")])),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(calls) == 2


def test_record_with_empty_falsification_field_is_rejected() -> None:
    record = _valid_record([_inspection_id("probe-1")])
    record[0]["falsification_check"] = ""
    raw, _calls = _run_verify([
        _INSPECT_REQUEST,
        _completed(record),
        _completed(record),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert "empty requirement/observed/falsification_check" in parsed.summary


# ---------------------------------------------------------------------------
# Bug fix: refs from a FAILED inspection must not satisfy the gate
# ---------------------------------------------------------------------------

_FAILED_READ_INSPECT_REQUEST = json.dumps({
    "kind": "inspect",
    "summary": "Read the missing file.",
    "requests": [
        {"request_id": "probe-1", "kind": "read_file", "path": "missing.txt"},
    ],
})


def _failing_inspector(requests):
    return [
        {
            "request_id": req.request_id,
            "inspection_id": _inspection_id(req.request_id),
            "kind": req.kind,
            "path": req.path,
            "eligible_for_proof": False,
            "evidence_ceiling": ROUTE_EVIDENCE_CEILINGS[req.kind],
            "error": f"file not found: {req.path}",
        }
        for req in requests
    ]


def test_completed_citing_only_a_failed_inspection_ref_is_refused() -> None:
    raw, calls = _run_verify(
        [
            _FAILED_READ_INSPECT_REQUEST,
            _completed(_valid_record([_inspection_id("probe-1")])),
            _completed(_valid_record([_inspection_id("probe-1")])),
        ],
        inspector=_failing_inspector,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert parsed.findings
    assert parsed.findings[0].finding_id == "vf-completion-evidence-record"
    assert "do not match any inspection" in parsed.summary
    assert len(calls) == 3


# ---------------------------------------------------------------------------
# Bug fix: a malformed completion_evidence record retries as a record
# problem, never crashes into the generic "not valid protocol JSON" path
# ---------------------------------------------------------------------------

def _completed_with_malformed_record() -> str:
    return json.dumps({
        "verdict": "completed",
        "confidence": "high",
        "summary": "Deliverable matches the requirement.",
        "completion_evidence": ["not-an-object", "also-not-an-object"],
    })


def test_descriptive_metadata_cannot_be_authoritative_method_without_effect_check() -> None:
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "a source annotation label",
                "method_summary": "parse the annotation and compare strings",
                "behavioral_basis": "the label is exact",
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    problem = _method_authority_problem(ledger, {"inspection:2:0:derived"})
    assert "descriptive metadata" in problem


def test_descriptive_metadata_inflections_cannot_evade_authority_guard() -> None:
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "a raw object-region labeling followed by motion commands",
                "method_summary": "extract the label and compare strings",
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    assert "descriptive metadata" in _method_authority_problem(
        ledger, {"inspection:2:0:derived"},
    )


def test_declared_metadata_risk_rejects_circular_extraction_comparison() -> None:
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "a source command argument",
                "method_summary": "extract the declared value and compare it with output",
                "command": "value = re.search(pattern, source).group(1); print(value == output)",
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    assert "circularly extracts" in _method_authority_problem(
        ledger,
        {"inspection:2:0:derived"},
        reject_circular_extraction_comparison=True,
    )


def test_effect_check_can_authorize_metadata_inspection_without_proxy_authority() -> None:
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "a source annotation label",
                "method_summary": "execute an independent effect check",
                "effect_check": "rerun the behavior after perturbation",
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    assert _method_authority_problem(ledger, {"inspection:2:0:derived"}) == ""


def test_method_prose_and_summary_filename_do_not_create_metadata_authority() -> None:
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "raw records with typed severity tokens and numeric fields in /app/summary.csv",
                "method_summary": "recompute from raw records and compare against the summary header and rows",
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    assert _method_authority_problem(ledger, {"inspection:2:0:derived"}) == ""


def test_filename_date_can_be_part_of_an_authoritative_record_structure() -> None:
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "raw records with typed severity fields and a declared date encoded in each filename",
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    assert _method_authority_problem(ledger, {"inspection:2:0:derived"}) == ""


def test_malformed_completion_evidence_shape_retries_as_record_problem_not_json_crash() -> None:
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed_with_malformed_record(),
        _completed(_valid_record([_inspection_id("probe-1")])),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(calls) == 3
    retry_instruction = calls[2][-1]["content"]
    # The SPECIFIC shape problem must be surfaced (proves correct routing)...
    assert "completion_evidence" in retry_instruction
    assert "must be an object" in retry_instruction
    # ...never the generic malformed-JSON instruction, which would misdirect
    # the model toward resending a bare verdict/confidence/summary.
    assert "not valid protocol json" not in retry_instruction.lower()


def test_malformed_completion_evidence_shape_refuses_when_retry_budget_exhausted() -> None:
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed_with_malformed_record(),
        _completed_with_malformed_record(),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert parsed.findings
    assert parsed.findings[0].finding_id == "vf-completion-evidence-record"
    assert "must be an object" in parsed.summary
    assert len(calls) == 3


def test_malformed_completion_evidence_raises_shape_specific_error() -> None:
    with pytest.raises(CompletionEvidenceShapeError):
        parse_model_verifier_result(json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "ok",
            "completion_evidence": ["not-an-object"],
        }))
    # Still a ValueError: existing `except ValueError` / `pytest.raises
    # (ValueError)` call sites keep working unchanged.
    assert issubclass(CompletionEvidenceShapeError, ValueError)


# ---------------------------------------------------------------------------
# Independence-kind requirement (Phase 1.5): closes the gcode/video
# false-clean gap left by the content-blind structural gate alone. See
# FABLE5_BATCH_AUDIT_20260709T101515Z.md secs 4 and 6.
# ---------------------------------------------------------------------------

_READ_FILE_INSPECT_REQUEST = json.dumps({
    "kind": "inspect",
    "summary": "Read the output file directly.",
    "requests": [
        {"request_id": "probe-1", "kind": "read_file", "path": "out.txt"},
    ],
})

_OVERLAY_INSPECT_REQUEST = json.dumps({
    "kind": "inspect",
    "summary": "Read the file, then independently recompute the value in the overlay.",
    "requests": [
        {"request_id": "probe-1", "kind": "read_file", "path": "out.txt"},
        {
            "request_id": "probe-2",
            "kind": "overlay_run_command",
            "verification_plan": {
                "claim": "The reported value matches the source data.",
                "authoritative_source_refs": ["task:prompt"],
                "method_summary": "Parse that record directly and recompute the value.",
                "proxy_risk": "A broader textual proxy could select unrelated content.",
            },
            "execution": {"kind": "overlay_run_command", "command": "python3 recompute.py"},
        },
    ],
})

_RE_DERIVABLE_PACKET = {
    "evidence_requirements": {
        "re_derivable_claims": ["the decoded value in out.txt is machine-re-derivable"],
    },
}


def test_completed_with_only_read_file_refs_is_refused_when_independence_required() -> None:
    raw, calls = _run_verify(
        [
            _READ_FILE_INSPECT_REQUEST,
            _completed(_valid_record([_inspection_id("probe-1")])),
            _completed(_valid_record([_inspection_id("probe-1")])),
        ],
        packet_overrides=_RE_DERIVABLE_PACKET,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert parsed.findings
    assert parsed.findings[0].finding_id == "vf-completion-evidence-independence"
    assert "independent-derivation" in parsed.summary
    assert len(calls) == 3


def test_completed_with_overlay_run_command_ref_is_accepted_when_independence_required() -> None:
    raw, calls = _run_verify(
        [
            _READ_FILE_INSPECT_REQUEST,
            json.dumps({
                "kind": "inspect",
                "requests": [{
                    "request_id": "probe-2",
                    "kind": "overlay_run_command",
                    "verification_plan": {
                        "claim": "The reported value matches the source data.",
                        "authoritative_source_refs": [_inspection_id("probe-1")],
                        "method_summary": "Parse that record directly and recompute the value.",
                        "proxy_risk": "A broader textual proxy could select unrelated content.",
                    },
                    "execution": {"kind": "overlay_run_command", "command": "python3 recompute.py"},
                }],
            }),
            _completed(
                _valid_record([_inspection_id("probe-1"), _inspection_id("probe-2")]),
                method_validity=_valid_method_validity(_inspection_id("probe-2"), ["task:prompt"]),
            ),
        ],
        packet_overrides=_RE_DERIVABLE_PACKET,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(calls) == 3


def test_incomplete_method_validity_gets_schema_derived_verdict_correction() -> None:
    incomplete = _completed(
        _valid_record([_inspection_id("source"), _inspection_id("derive")]),
        method_validity={
            "method_alignment": "The rule measures the semantic determinant.",
        },
    )
    corrected = _completed(
        _valid_record([_inspection_id("source"), _inspection_id("derive")]),
        method_validity=_valid_method_validity(
            _inspection_id("derive"), [_inspection_id("source")],
        ),
    )
    raw, calls = _run_verify(
        [
            json.dumps({
                "kind": "inspect",
                "requests": [{"request_id": "source", "kind": "read_file", "path": "out.txt"}],
            }),
            json.dumps({
                "kind": "inspect",
                "requests": [{
                    "request_id": "derive",
                    "kind": "overlay_run_command",
                    "verification_plan": {
                        "claim": "The output matches the source.",
                        "authoritative_source_refs": [_inspection_id("source")],
                        "method_summary": "Parse the previously observed source.",
                        "proxy_risk": "A proxy can be misleading.",
                    },
                    "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
                }],
            }),
            incomplete,
            corrected,
        ],
        packet_overrides=_RE_DERIVABLE_PACKET,
    )
    assert parse_model_verifier_result(raw).verdict == "completed"
    assert len(calls) == 4
    correction = json.loads(calls[3][-1]["content"])
    assert correction["missing"] == [
        "observed_structure",
        "executed_rule",
        "authoritative_source_refs",
        "execution_ref",
    ]
    assert correction["invalid"] == []
    assert correction["method_validity_shape"] == METHOD_VALIDITY_SHAPE
    assert "verdict JSON parsed" in correction["instruction"]
    assert "inspection request" in correction["instruction"]


def test_overlay_command_cannot_cite_same_round_observation() -> None:
    raw, calls = _run_verify([
        json.dumps({
            "kind": "inspect",
            "requests": [
                {"request_id": "source", "kind": "read_file", "path": "out.txt"},
                {
                    "request_id": "derive",
                    "kind": "overlay_run_command",
                    "verification_plan": {
                        "claim": "The output matches the source.",
                        "authoritative_source_refs": ["inspection:future:source"],
                        "method_summary": "Parse the observed source.",
                        "proxy_risk": "A proxy can be misleading.",
                    },
                    "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
                },
            ],
        }),
        _INSPECT_REQUEST,
        _completed(_valid_record([_inspection_id("probe-1")])),
    ])
    assert parse_model_verifier_result(raw).verdict == "completed"
    correction = json.loads(calls[1][-1]["content"])
    assert "same round" in correction["instruction"]
    assert correction["available_authoritative_source_refs"] == ["task:prompt"]


def test_overlay_command_accepts_prior_inspection_reference() -> None:
    source_request = json.dumps({
        "kind": "inspect",
        "requests": [{"request_id": "source", "kind": "read_file", "path": "out.txt"}],
    })
    command_request = json.dumps({
        "kind": "inspect",
        "requests": [{
            "request_id": "derive",
            "kind": "overlay_run_command",
            "verification_plan": {
                "claim": "The output matches the source.",
                "authoritative_source_refs": [_inspection_id("source")],
                "method_summary": "Parse the previously observed source.",
                "proxy_risk": "A proxy can be misleading.",
            },
            "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
        }],
    })
    raw, calls = _run_verify([
        source_request,
        command_request,
        _completed(
            _valid_record([_inspection_id("source"), _inspection_id("derive")]),
            method_validity=_valid_method_validity(_inspection_id("derive"), [_inspection_id("source")]),
        ),
    ])
    assert parse_model_verifier_result(raw).verdict == "completed"
    assert len(calls) == 3


def test_missing_execution_command_gets_field_specific_correction() -> None:
    missing_command = json.dumps({
        "kind": "inspect",
        "requests": [{
            "request_id": "derive",
            "kind": "overlay_run_command",
            "verification_plan": {
                "claim": "The output matches the source.",
                "authoritative_source_refs": ["task:prompt"],
                "method_summary": "python3 derive.py",
                "proxy_risk": "A proxy can be misleading.",
            },
            "execution": {"kind": "overlay_run_command", "command": ""},
        }],
    })
    raw, calls = _run_verify([missing_command, _INSPECT_REQUEST, _completed(_valid_record([_inspection_id("probe-1")]))])
    assert parse_model_verifier_result(raw).verdict == "completed"
    assert "Put executable text in execution.command" in json.loads(calls[1][-1]["content"])["instruction"]


def test_missing_overlay_kind_gets_field_specific_correction() -> None:
    missing_kind = json.dumps({
        "kind": "inspect",
        "requests": [{
            "request_id": "derive",
            "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
        }],
    })
    raw, calls = _run_verify([missing_kind, _INSPECT_REQUEST, _completed(_valid_record([_inspection_id("probe-1")]))])
    assert parse_model_verifier_result(raw).verdict == "completed"
    assert "missing the top-level kind" in json.loads(calls[1][-1]["content"])["instruction"]


def test_missing_derived_evidence_mode_gets_field_specific_correction() -> None:
    missing_mode = json.dumps({
        "kind": "inspect",
        "requests": [{
            "request_id": "derive",
            "kind": "overlay_run_command",
            "verification_plan": {
                "claim": "The output matches the source.",
                "authoritative_structure": "the observed source structure",
                "authoritative_source_refs": ["inspection:old"],
                "method_summary": "Parse the structured field.",
                "proxy_risk": "A proxy can be misleading.",
                "basis": [{"ref": "inspection:old"}],
                "bound_input_refs": ["inspection:old"],
            },
            "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
        }],
    })
    raw, calls = _run_verify(
        [missing_mode, _INSPECT_REQUEST, _completed(_valid_record([_inspection_id("probe-1")]))],
        packet_overrides={"verifier_evidence_admissibility_version": "v3"},
    )
    correction = json.loads(calls[1][-1]["content"])
    assert correction["missing"] == ["verification_plan.evidence_mode"]
    assert correction["invalid"] == [
        "verification_plan.authoritative_source_refs is legacy-only in V3"
    ]
    assert "every missing field" in correction["instruction"]


def test_completed_with_only_read_file_refs_is_accepted_when_independence_not_flagged() -> None:
    # Same record/refs as the refused case above, but re_derivable_claims is
    # unset: unchanged legacy behavior, no independence requirement applied.
    raw, calls = _run_verify([
        _READ_FILE_INSPECT_REQUEST,
        _completed(_valid_record([_inspection_id("probe-1")])),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# Helper-level checks (content-blind semantics)
# ---------------------------------------------------------------------------

def test_completion_record_problem_is_content_blind() -> None:
    entry = CompletionEvidenceEntry(
        requirement="anything",
        observed="anything",
        falsification_check="anything",
        inspection_refs=("probe-1",),
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    assert _completion_record_problem(result, {"probe-1"}) == ""
    assert "do not match" in _completion_record_problem(result, {"other"})
    empty = type("_R", (), {"completion_evidence": ()})()
    assert "missing or empty" in _completion_record_problem(empty, {"probe-1"})


def test_completion_record_requires_declared_false_positive_risk_coverage() -> None:
    entry = CompletionEvidenceEntry(
        requirement="value", observed="7", falsification_check="would differ",
        inspection_refs=("probe-1",), risk_refs=("metadata is not authority",),
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    packet = {"evidence_requirements": {"false_positive_risks": [
        "metadata is not authority", "same method is not independent",
    ]}}
    problem = _completion_record_problem(result, {"probe-1"}, packet=packet, require_risk_coverage=True)
    assert "does not address every declared false_positive_risk" in problem
    assert "same method is not independent" in problem


def test_completion_record_ignores_extra_risk_annotation_when_declared_coverage_is_complete() -> None:
    entry = CompletionEvidenceEntry(
        requirement="value", observed="7", falsification_check="would differ",
        inspection_refs=("probe-1",), risk_refs=("declared risk", "extra explanation"),
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    packet = {"evidence_requirements": {"false_positive_risks": ["declared risk"]}}
    assert _completion_record_problem(
        result, {"probe-1"}, packet=packet, require_risk_coverage=True,
    ) == ""


def test_extra_risk_annotation_does_not_replace_missing_declared_coverage() -> None:
    entry = CompletionEvidenceEntry(
        requirement="value", observed="7", falsification_check="would differ",
        inspection_refs=("probe-1",), risk_refs=("extra explanation",),
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    packet = {"evidence_requirements": {"false_positive_risks": ["declared risk"]}}
    problem = _completion_record_problem(result, {"probe-1"}, packet=packet, require_risk_coverage=True)
    assert "does not address every declared false_positive_risk" in problem


def test_refs_include_only_registered_inspection_ids() -> None:
    request = VerifierInspectionRequest(request_id="r-1", kind="read_file", path="out.txt")
    refs = _refs_from_inspections((request,), [{
        "request_id": "r-1",
        "inspection_id": "inspection:test:r-1",
        "handle": "2:a-1:stdout",
        "eligible_for_proof": True,
    }])
    assert refs == {"inspection:test:r-1"}


def test_refs_from_errored_inspection_result_are_excluded() -> None:
    request = VerifierInspectionRequest(request_id="r-1", kind="read_file", path="missing.txt")
    refs = _refs_from_inspections(
        (request,),
        [{"request_id": "r-1", "path": "missing.txt", "error": "file not found: missing.txt"}],
    )
    assert refs == set()


def test_refs_from_negative_but_non_errored_probe_are_included() -> None:
    # A probe that ran successfully and observed a negative result (port
    # closed) is NOT an inspection error -- judging whether "closed" supports
    # or contradicts a claim is content, and content stays the model's job.
    request = VerifierInspectionRequest(request_id="r-1", kind="probe_port", target="127.0.0.1:9")
    refs = _refs_from_inspections(
        (request,),
        [{
            "request_id": "r-1",
            "inspection_id": "inspection:test:r-1",
            "kind": "probe_port",
            "host": "127.0.0.1",
            "port": 9,
            "state": "closed",
            "eligible_for_proof": True,
        }],
    )
    assert refs == {"inspection:test:r-1"}


def test_independent_derivation_refs_excludes_read_file_includes_overlay() -> None:
    read_request = VerifierInspectionRequest(request_id="r-1", kind="read_file", path="out.txt")
    overlay_request = VerifierInspectionRequest(request_id="r-2", kind="overlay_run_command", command="echo hi")
    results = [
        {"request_id": "r-1", "inspection_id": "inspection:test:r-1", "kind": "read_file", "path": "out.txt", "excerpt": "7", "eligible_for_proof": True},
        {"request_id": "r-2", "inspection_id": "inspection:test:r-2", "kind": "overlay_run_command", "exit_code": 0, "success": True, "stdout": "hi", "eligible_for_proof": True},
    ]
    refs = _independent_derivation_refs((read_request, overlay_request), results)
    assert refs == {"inspection:test:r-2"}


def test_independent_derivation_refs_excludes_errored_overlay_command() -> None:
    overlay_request = VerifierInspectionRequest(request_id="r-2", kind="overlay_run_command", command="echo hi")
    results = [{"request_id": "r-2", "kind": "overlay_run_command", "error": "no overlay available"}]
    refs = _independent_derivation_refs((overlay_request,), results)
    assert refs == set()


def test_completion_independence_problem_is_content_blind() -> None:
    entry = CompletionEvidenceEntry(
        requirement="anything", observed="anything", falsification_check="anything",
        inspection_refs=("r-1", "r-2"),
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    assert _completion_independence_problem(result, {"r-2"}) == ""
    problem = _completion_independence_problem(result, {"other"})
    assert "independent-derivation" in problem


# ---------------------------------------------------------------------------
# Parse-layer normalization
# ---------------------------------------------------------------------------

def test_parse_normalizes_completion_evidence_entries() -> None:
    parsed = parse_model_verifier_result(json.dumps({
        "verdict": "completed",
        "confidence": "high",
        "summary": "ok",
        "completion_evidence": [
            {
                "requirement": "req",
                "observed": "obs",
                "inspection_refs": "probe-1",
                "risk_refs": "metadata is not authority",
                "falsification_check": "would differ",
            }
        ],
    }))
    assert parsed.completion_evidence[0].inspection_refs == ("probe-1",)
    assert parsed.completion_evidence[0].risk_refs == ("metadata is not authority",)
    assert parsed.as_dict()["completion_evidence"][0]["requirement"] == "req"


def test_parse_rejects_malformed_completion_evidence() -> None:
    with pytest.raises(ValueError):
        parse_model_verifier_result(json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "ok",
            "completion_evidence": ["not-an-object"],
        }))
    with pytest.raises(ValueError):
        parse_model_verifier_result(json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "ok",
            "completion_evidence": [{"requirement": "r", "observed": "o", "inspection_refs": 7}],
        }))


# ---------------------------------------------------------------------------
# Contract + doctrine advertisement
# ---------------------------------------------------------------------------

def test_contract_advertises_completion_evidence_protocol() -> None:
    assert VERIFIER_RUNTIME_CONTRACT["required_fields"]["completed"] == ["completion_evidence"]
    shape = VERIFIER_RUNTIME_CONTRACT["completion_evidence_shape"]
    assert set(shape) == {
        "requirement", "observed", "inspection_refs", "clause_ids",
        "proof_ids", "evidence_class", "falsification_check", "risk_refs",
    }
    assert "exact_contract" in shape["evidence_class"]
    assert "independent_semantic" in shape["evidence_class"]
    rules = " ".join(VERIFIER_RUNTIME_CONTRACT["rules"])
    assert "machine-re-derivable" in rules
    assert "overlay_run_command" in rules


def test_v3_contract_renders_one_overlay_shape_without_legacy_guidance() -> None:
    inspector = VERIFIER_RUNTIME_CONTRACT["read_only_inspector"]
    rendered = json.dumps(inspector, sort_keys=True)
    plan = inspector["request_format"]["requests"][0]["verification_plan"]
    assert set(plan) == {
        "claim", "authoritative_structure", "method_summary", "proxy_risk", "evidence_mode", "clause_ids", "basis", "bound_input_refs",
    }
    assert "authoritative_source_refs" not in rendered
    assert "up to 12 requests" in " ".join(inspector["rules"])


def test_live_v3_prompt_manual_and_correction_share_parseable_overlay_example() -> None:
    rendered_contract = json.dumps(VERIFIER_RUNTIME_CONTRACT, sort_keys=True)
    rendered_system = _verifier_identity_prompt_for(_compiled())
    assert "method_validity_shape" in rendered_contract
    assert "authoritative_source_refs" in rendered_contract
    assert "authoritative_source_refs" in rendered_system
    assert "verification_plan.authoritative_source_refs" not in rendered_contract
    assert "verification_plan.authoritative_source_refs" not in rendered_system
    request = V3_DERIVED_INSPECTION_EXAMPLE["requests"][0]
    assert request["kind"] == "overlay_run_command"
    assert request["execution"]["kind"] == "overlay_run_command"
    assert parse_verifier_inspection_requests(
        V3_DERIVED_INSPECTION_EXAMPLE, require_derived_contract=True,
    )[0].kind == "overlay_run_command"

    correction = _inspection_protocol_correction(
        VerifierInspectionProtocolError(missing=("verification_plan.basis",)),
    )
    assert correction["v3_overlay_request_example"] == V3_DERIVED_INSPECTION_EXAMPLE
    assert parse_verifier_inspection_requests(
        correction["v3_overlay_request_example"], require_derived_contract=True,
    )[0].kind == "overlay_run_command"


def test_contract_states_independence_kind_requirement_plainly() -> None:
    rules = " ".join(VERIFIER_RUNTIME_CONTRACT["rules"])
    assert "Runtime-enforced, not prompt-only" in rules
    assert "re_derivable_claims" in rules
    assert "independent-derivation inspection kind" in rules
    for kind in (
        "overlay_run_command", "rerun_check", "probe_port", "probe_http",
        "probe_process", "perceive_artifact",
    ):
        assert kind in rules
    assert "will be refused" in rules


def test_contract_respects_structured_record_delimiters() -> None:
    rules = " ".join(VERIFIER_RUNTIME_CONTRACT["rules"])
    assert "declared record grammar or field delimiters" in rules


def test_architect_doctrine_requires_method_independent_minimum_evidence() -> None:
    prompt = WORKBENCH_ARCHITECT_SYSTEM_PROMPT.lower()
    assert "method-independent" in prompt
    assert "machine-re-derivable" in prompt
    assert "around the solver's reported values" in prompt
    assert "model_context_window_tokens" in prompt


# ---------------------------------------------------------------------------
# Context-window de-starvation
# ---------------------------------------------------------------------------

def _raw_config(**context_policy: Any) -> str:
    base = {
        "schema_version": "harness_config.v1",
        "task_understanding": "Write one output file.",
        "success_definition": "out.txt exists and matches the prompt.",
        "solver_system_prompt": {"role": "Careful file task solver"},
        "verifier_system_prompt": {
            "role": "Task-specific evidence verifier",
            "success_criteria": ["out.txt matches the requested result"],
            "required_evidence": ["artifact content checked against the task"],
        },
        "evidence_requirements": ["out.txt content matches the requested result"],
        "minimum_completion_evidence": ["independent content evidence"],
        "tool_policy": {"enabled_tools": ["read_file", "write_file", "run_command"]},
        "context_policy": {"mode": "default_bounded", **context_policy},
    }
    return json.dumps(base)


def test_context_window_default_is_modern_not_starved() -> None:
    config = parse_harness_config_ir(_raw_config())
    assert config.context_policy.model_context_window_tokens == 50_000
    runtime_ir = harness_config_to_runtime_ir(config, _make_envmap())
    assert runtime_ir.context_policy.model_context_window_tokens == 50_000


def test_architect_can_set_context_window_and_it_reaches_runtime() -> None:
    config = parse_harness_config_ir(_raw_config(model_context_window_tokens=120_000))
    assert config.context_policy.model_context_window_tokens == 120_000
    runtime_ir = harness_config_to_runtime_ir(config, _make_envmap())
    assert runtime_ir.context_policy.model_context_window_tokens == 120_000


def test_context_window_bounds_are_fail_closed() -> None:
    from aether.model_hooks import ModelOutputError

    with pytest.raises(ModelOutputError):
        parse_harness_config_ir(_raw_config(model_context_window_tokens=500))
    with pytest.raises(ModelOutputError):
        parse_harness_config_ir(_raw_config(model_context_window_tokens="lots"))


def test_architect_workbench_compiles_re_derivable_claims_and_reaches_runtime_ir() -> None:
    raw = {
        "schema_version": "harness_config.v1",
        "task_understanding": "Write one output file.",
        "success_definition": "out.txt exists and matches the prompt.",
        "solver_system_prompt": {"role": "Careful file task solver"},
        "verifier_system_prompt": {
            "role": "Task-specific evidence verifier",
            "success_criteria": ["out.txt matches the requested result"],
            "required_evidence": ["artifact content checked against the task"],
        },
        "evidence_requirements": ["out.txt content matches the requested result"],
        "minimum_completion_evidence": ["independent content evidence"],
        "re_derivable_claims": ["the hash of out.txt matches the expected"],
        "tool_policy": {"enabled_tools": ["read_file", "write_file", "run_command"]},
        "context_policy": {"mode": "default_bounded"},
    }
    config = parse_harness_config_ir(json.dumps(raw))
    assert config.re_derivable_claims == ("the hash of out.txt matches the expected",)
    runtime_ir = harness_config_to_runtime_ir(config, _make_envmap())
    assert runtime_ir.re_derivable_claims == ("the hash of out.txt matches the expected",)


def test_same_method_risk_is_declared_only_by_explicit_contract_language() -> None:
    assert _packet_declares_same_method_risk({
        "evidence_requirements": {
            "false_positive_risks": ["A detector can look plausible while validated only by the same method."],
        },
    }) is True
    assert _packet_declares_same_method_risk({
        "evidence_requirements": {
            "false_positive_risks": ["A result can be off by one while looking plausible."],
        },
    }) is False


def test_declared_same_method_risk_rejects_structurally_copied_verifier_algorithm() -> None:
    solver_source = """
import cv2
import numpy as np
def foreground_bottom(frame, first_gray):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray, first_gray)
    diff = cv2.GaussianBlur(diff, (5, 5), 0)
    _, th = cv2.threshold(diff, 35, 255, cv2.THRESH_BINARY)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(th, connectivity=8)
    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if x <= 0 or y <= 0:
            continue
        return y + bh - 1
"""
    copied_command = """
python3 - <<'PY'
import cv2
import numpy as np
def check(frame, first_gray):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray, first_gray)
    diff = cv2.GaussianBlur(diff, (5, 5), 0)
    _, th = cv2.threshold(diff, 35, 255, cv2.THRESH_BINARY)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(th, connectivity=8)
    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if x <= 0 or y <= 0:
            continue
        print(y + bh - 1)
PY
"""
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "raw frame pixels",
                "method_summary": "independently inspect foreground position",
                "command": copied_command,
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    problem = _method_authority_problem(
        ledger,
        {"inspection:2:0:derived"},
        reject_same_method_overlap=True,
        observed_source_texts=(solver_source,),
    )
    assert "substantially reuses an inspected implementation" in problem


def test_same_method_overlap_gate_does_not_block_distinct_countercheck() -> None:
    solver_source = "def solve(values):\n    return sum(values) / len(values)\n"
    distinct_command = "python3 - <<'PY'\nfrom statistics import median\nprint(median([1, 2, 3]))\nPY"
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:2:0:derived",
        "payload": {
            "inspection_id": "inspection:2:0:derived",
            "route_parameters": {
                "authoritative_structure": "independent samples",
                "method_summary": "use a distinct robust statistic",
                "command": distinct_command,
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    assert _method_authority_problem(
        ledger,
        {"inspection:2:0:derived"},
        reject_same_method_overlap=True,
        observed_source_texts=(solver_source,),
    ) == ""


# ---------------------------------------------------------------------------
# Integrated Verifier protocol recovery: direct evidence vs derived methods
# ---------------------------------------------------------------------------


def _direct_needs_repair(*, execution_ref: Any = None) -> dict[str, Any]:
    return {
        "verdict": "needs_repair",
        "confidence": "high",
        "summary": "The directly probed service endpoint is closed.",
        "findings": [{
            "finding_id": "service-closed",
            "verdict": "needs_repair",
            "priority": "blocking",
            "summary": "The service endpoint is closed.",
            "evidence": ["The direct port probe returned closed."],
            "repair_instruction": "Start the service and probe it again.",
            "supporting_inspection_ids": ["inspection:test:port"],
        }],
        "completion_evidence": [],
        "missing_evidence_requests": [],
        "method_validity": {
            "observed_structure": "The live endpoint state was observed directly.",
            "executed_rule": "Treat a closed required endpoint as incomplete state.",
            "method_alignment": "The direct probe measures the required live interface.",
            "authoritative_source_refs": ["inspection:test:port"],
            "execution_ref": execution_ref,
        },
    }


def test_direct_observation_verdict_does_not_require_derived_execution_ref() -> None:
    result = parse_model_verifier_result(_direct_needs_repair(execution_ref=None))

    assert result.verdict == "needs_repair"
    assert result.method_validity is None
    assert _verdict_admissibility_problem(
        result,
        {"inspection:test:port"},
        set(),
    ) == ""


def test_high_priority_needs_repair_is_fully_direct_when_all_findings_cite_direct_refs() -> None:
    payload = _direct_needs_repair(execution_ref=None)
    payload["findings"][0]["priority"] = "high"
    result = parse_model_verifier_result(payload)

    assert _needs_repair_is_fully_directly_grounded(
        result, {"inspection:test:port"},
    ) is True
    assert _needs_repair_is_fully_directly_grounded(result, set()) is False


def test_exploratory_overlay_does_not_poison_direct_needs_repair_verdict() -> None:
    direct = json.dumps({
        "kind": "inspect",
        "requests": [{"request_id": "source", "kind": "read_file", "path": "out.txt"}],
    })
    derived = json.dumps({
        "kind": "inspect",
        "requests": [{
            "request_id": "derive",
            "kind": "overlay_run_command",
            "verification_plan": {
                "claim": "The output matches the observed source.",
                "authoritative_source_refs": [_inspection_id("source")],
                "method_summary": "Recompute from the previously observed source.",
                "proxy_risk": "The exploratory method may repeat a production defect.",
            },
            "execution": {
                "kind": "overlay_run_command",
                "command": "python3 derive.py",
            },
        }],
    })
    verdict = {
        "verdict": "needs_repair",
        "confidence": "high",
        "summary": "The directly observed output violates the task contract.",
        "findings": [{
            "finding_id": "direct-output-mismatch",
            "verdict": "needs_repair",
            "priority": "blocking",
            "summary": "The output is wrong.",
            "evidence": ["The direct file read exposed the mismatch."],
            "repair_instruction": "Correct the output from the authoritative source.",
            "supporting_inspection_ids": [_inspection_id("source")],
        }],
        "completion_evidence": [],
        "missing_evidence_requests": [],
        "method_validity": {
            "observed_structure": "The output was read directly.",
            "executed_rule": "Compare the direct output with the visible requirement.",
            "method_alignment": "The direct observation measures the failing state.",
            "authoritative_source_refs": [_inspection_id("source")],
            "execution_ref": None,
        },
    }

    raw, calls = _run_verify([direct, derived, json.dumps(verdict)])

    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "needs_repair"
    assert parsed.method_validity is None
    assert parsed.findings[0].supporting_inspection_ids == (_inspection_id("source"),)
    assert len(calls) == 3


def test_nonempty_direct_probe_misused_as_execution_ref_is_rejected() -> None:
    result = parse_model_verifier_result(
        _direct_needs_repair(execution_ref="inspection:test:port")
    )

    assert result.method_validity is not None
    assert _verdict_admissibility_problem(
        result,
        {"inspection:test:port"},
        set(),
    ) == "method_validity.execution_ref is not a current verdict-eligible derived execution"


def test_overlay_execution_still_requires_a_verdict_eligible_execution_ref() -> None:
    direct = json.dumps({
        "kind": "inspect",
        "requests": [{
            "request_id": "source",
            "kind": "read_file",
            "path": "out.txt",
        }],
    })
    derived = json.dumps({
        "kind": "inspect",
        "requests": [{
            "request_id": "derive",
            "kind": "overlay_run_command",
            "verification_plan": {
                "claim": "The output matches the observed source.",
                "authoritative_source_refs": [_inspection_id("source")],
                "method_summary": "Recompute from the previously observed source.",
                "proxy_risk": "A textual proxy could agree accidentally.",
            },
            "execution": {
                "kind": "overlay_run_command",
                "command": "python3 derive.py",
            },
        }],
    })
    null_execution = _completed(
        _valid_record([_inspection_id("source"), _inspection_id("derive")]),
        method_validity={
            "observed_structure": "The source was observed directly.",
            "executed_rule": "The overlay recomputed the value.",
            "method_alignment": "The rule measures the source value.",
            "authoritative_source_refs": [_inspection_id("source")],
            "execution_ref": None,
        },
    )
    corrected = _completed(
        _valid_record([_inspection_id("source"), _inspection_id("derive")]),
        method_validity=_valid_method_validity(
            _inspection_id("derive"),
            [_inspection_id("source")],
        ),
    )

    raw, calls = _run_verify([direct, derived, null_execution, corrected])

    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert parsed.method_validity is not None
    assert parsed.method_validity.execution_ref == _inspection_id("derive")
    assert len(calls) == 4
    correction = json.loads(calls[3][-1]["content"])
    assert _inspection_id("derive") in correction["verdict_eligible_execution_refs"]


# ---------------------------------------------------------------------------
# One bounded provider restatement for rejected strict direct turns
# ---------------------------------------------------------------------------


def test_direct_turn_multi_payload_uses_one_bounded_provider_correction() -> None:
    calls: list[list[dict[str, str]]] = []
    inspections: list[Any] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        del max_output_tokens
        calls.append(list(messages))
        if len(calls) == 1:
            raise AzureProviderOutputError(
                "provider_direct_turn_multiple_distinct_semantic_payloads"
            )
        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "high",
            "summary": "A single corrected semantic decision.",
            "missing_evidence_requests": ["Inspect the decisive current state."],
            "findings": [],
            "completion_evidence": [],
            "method_validity": None,
        })

    hooks = ModelHooks(
        architect_model=lambda _m, *, max_output_tokens=8000: "{}",
        solver_model=lambda _m, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )

    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Inspect current state."},
        _compiled(),
        ledger=_ledger_stub(),
        inspector=lambda requests: inspections.append(requests) or [],
    )

    assert parse_model_verifier_result(raw).verdict == "uncertain_missing_evidence"
    assert len(calls) == 2
    assert inspections == []
    correction = json.loads(calls[1][-1]["content"])
    assert correction["provider_protocol_error"] == (
        "provider_direct_turn_multiple_distinct_semantic_payloads"
    )
    assert correction["rejected_response_executed"] == "false"
    assert "sole key turn" in correction["instruction"]
    assert "payload_json" not in correction["instruction"]


def test_second_direct_turn_provider_violation_exhausts_bounded_correction() -> None:
    calls: list[list[dict[str, str]]] = []
    inspections: list[Any] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        del max_output_tokens
        calls.append(list(messages))
        raise AzureProviderOutputError(
            "provider_direct_turn_multiple_distinct_semantic_payloads"
        )

    hooks = ModelHooks(
        architect_model=lambda _m, *, max_output_tokens=8000: "{}",
        solver_model=lambda _m, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )

    with pytest.raises(ModelOutputError, match="provider-correction budget exhausted"):
        hooks.verify_with_inspector(
            {"reason": "solver_submit", "task_prompt": "Inspect current state."},
            _compiled(),
            ledger=_ledger_stub(),
            inspector=lambda requests: inspections.append(requests) or [],
        )

    assert len(calls) == 2
    assert inspections == []


def test_provider_correction_classifier_remains_narrow() -> None:
    direct = AzureProviderOutputError("provider_direct_turn_invalid_shape")
    envelope = AzureProviderOutputError("provider_envelope_duplicate_key")
    refusal = AzureProviderOutputError("provider_refusal")

    assert _provider_envelope_protocol_error(direct) == "provider_direct_turn_invalid_shape"
    assert _provider_envelope_protocol_error(envelope) == "provider_envelope_duplicate_key"
    assert _provider_envelope_protocol_error(refusal) == ""
    assert "sole key turn" in _provider_protocol_correction(
        "provider_direct_turn_invalid_shape"
    )["instruction"]
    assert "payload_json" in _provider_protocol_correction(
        "provider_envelope_duplicate_key"
    )["instruction"]


# ---------------------------------------------------------------------------
# Evidence-composition recovery: precise proxy and budget boundaries
# ---------------------------------------------------------------------------


def test_circular_proxy_activation_excludes_regex_and_same_method_risks() -> None:
    assert _packet_declares_circular_proxy_risk({
        "evidence_requirements": {
            "false_positive_risks": [
                "A regex can use the wrong line boundary.",
                "A same-method self-check can repeat the production error.",
            ],
        },
    }) is False
    assert _packet_declares_circular_proxy_risk({
        "evidence_requirements": {
            "false_positive_risks": [
                "A metadata label can state a plausible but false answer.",
            ],
        },
    }) is True


def test_full_raw_record_aggregation_is_not_circular_source_value_extraction() -> None:
    receipt = type("Receipt", (), {
        "receipt_id": "inspection:5:2:aggregate",
        "payload": {
            "inspection_id": "inspection:5:2:aggregate",
            "route_parameters": {
                "authoritative_structure": "all raw records and their typed severity fields",
                "method_summary": (
                    "Parse every raw record with a regex, accumulate each value once into "
                    "the intended buckets, and compare the complete derived table with output."
                ),
                "command": (
                    "line_re = re.compile(pattern)\n"
                    "for path in all_paths:\n"
                    "    for line in open(path):\n"
                    "        severity = line_re.match(line).group(1)\n"
                    "        counts[bucket][severity] += 1\n"
                    "print(expected == actual)\n"
                ),
            },
        },
    })()
    ledger = type("Ledger", (), {"all_receipts": lambda self: [receipt]})()
    assert _method_authority_problem(
        ledger,
        {"inspection:5:2:aggregate"},
        reject_circular_extraction_comparison=True,
    ) == ""


def test_tool_timeout_budget_correction_names_limit_and_demands_cheaper_method() -> None:
    budget = VerifierPhaseBudget(max_tool_execution_s_per_batch=30)
    payload = _budget_correction_payload(
        VerifierBudgetError("verifier inspection batch exceeded tool-execution budget"),
        budget,
    )
    assert payload["budget_limits"] == {"max_tool_execution_s_per_batch": 30}
    assert payload["rejected_result_admitted"] is False
    assert "30-second" in payload["instruction"]
    assert "materially cheaper" in payload["instruction"]
    assert "cosmetic shortening" in payload["instruction"]


def test_v3_completion_record_recognizes_outcome_and_constraint_clause_ids() -> None:
    outcome = CompletionEvidenceEntry(
        requirement="root returns ok",
        observed="probe returned ok",
        falsification_check="a different body would falsify it",
        inspection_refs=("probe-http",),
        clause_ids=("service_returns_exact_ok_on_root",),
        proof_ids=("proof_root",),
        evidence_class="behavioral",
    )
    method = CompletionEvidenceEntry(
        requirement="start_job was used",
        observed="action history records start_job",
        falsification_check="a different launch tool would falsify it",
        inspection_refs=("history",),
        clause_ids=("use_start_job_tool",),
        proof_ids=("proof_start",),
        evidence_class="exact_contract",
    )
    result = type("_R", (), {"completion_evidence": (outcome, method)})()
    packet = {
        "task_contract": {
            "clauses": [{"clause_id": "service_returns_exact_ok_on_root"}],
            "method_constraints": [{"constraint_id": "use_start_job_tool"}],
        },
        "compiled_evidence_requirements": [{
            "clause_id": "use_start_job_tool",
            "minimum_class": "exact_contract",
            "allowed_route_kinds": ["inspect_action_receipts"],
        }],
        "compiled_proof_requirements": [
            {
                "proof_id": "proof_root",
                "target_type": "outcome",
                "target_id": "service_returns_exact_ok_on_root",
                "obligation_ids": ["service_returns_exact_ok_on_root"],
            },
            {
                "proof_id": "proof_start",
                "target_type": "constraint",
                "target_id": "use_start_job_tool",
                "obligation_ids": ["service_returns_exact_ok_on_root"],
            },
        ],
    }
    assert _completion_record_problem(
        result,
        {"probe-http", "history"},
        packet=packet,
        inspection_ceilings={
            "probe-http": "behavioral",
            "history": "exact_contract",
        },
        inspection_routes={
            "probe-http": "probe_http",
            "history": "inspect_action_receipts",
        },
    ) == ""


def test_v3_completion_record_still_rejects_invented_clause_id() -> None:
    entry = CompletionEvidenceEntry(
        requirement="invented",
        observed="something",
        falsification_check="something else",
        inspection_refs=("probe-http",),
        clause_ids=("invented_clause",),
        proof_ids=("proof_root",),
        evidence_class="behavioral",
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    packet = {
        "task_contract": {
            "clauses": [{"clause_id": "service_returns_exact_ok_on_root"}],
            "method_constraints": [],
        },
        "compiled_proof_requirements": [{
            "proof_id": "proof_root",
            "target_type": "outcome",
            "target_id": "service_returns_exact_ok_on_root",
            "obligation_ids": ["service_returns_exact_ok_on_root"],
        }],
    }
    problem = _completion_record_problem(
        result,
        {"probe-http"},
        packet=packet,
        inspection_ceilings={"probe-http": "behavioral"},
        inspection_routes={"probe-http": "probe_http"},
    )
    assert "unknown clause ID: invented_clause" in problem


# ---------------------------------------------------------------------------
# PERSISTENT F94 structured completion coherence
# ---------------------------------------------------------------------------

def _f94_entry(status: str = "") -> CompletionEvidenceEntry:
    return CompletionEvidenceEntry(
        requirement="both outputs satisfy the requirement",
        observed="current direct observations are recorded",
        falsification_check="a conflicting observation would falsify completion",
        inspection_refs=("probe-1",),
        requirement_status=status,
    )


def test_f94_completion_status_gate_is_persistent_opt_in_and_content_blind() -> None:
    violated = type("_R", (), {"completion_evidence": (_f94_entry("violated"),)})()
    # Generic/TRIAD compatibility: the new status is not consulted unless the
    # caller explicitly enables the PERSISTENT coherence law.
    assert _completion_record_problem(violated, {"probe-1"}) == ""
    problem = _completion_record_problem(
        violated, {"probe-1"}, require_requirement_status=True,
    )
    assert "requirement_status=violated" in problem
    assert "incompatible with completed" in problem


def test_f94_completed_requires_every_structured_status_satisfied() -> None:
    good = type("_R", (), {"completion_evidence": (_f94_entry("satisfied"),)})()
    assert _completion_record_problem(
        good, {"probe-1"}, require_requirement_status=True,
    ) == ""
    for status in ("violated", "unknown", ""):
        result = type("_R", (), {"completion_evidence": (_f94_entry(status),)})()
        problem = _completion_record_problem(
            result, {"probe-1"}, require_requirement_status=True,
        )
        rendered = status or "missing"
        assert f"requirement_status={rendered}" in problem


def test_f94_parser_transports_status_without_global_generic_enum_policy() -> None:
    payload = {
        "verdict": "completed",
        "confidence": "high",
        "summary": "structured record",
        "completion_evidence": [{
            "requirement": "req",
            "observed": "obs",
            "falsification_check": "countercheck",
            "inspection_refs": ["probe-1"],
            "requirement_status": "violated",
        }],
    }
    parsed = parse_model_verifier_result(payload)
    assert parsed.completion_evidence[0].requirement_status == "violated"
    assert parsed.as_dict()["completion_evidence"][0]["requirement_status"] == "violated"
    # Legacy/generic serialization stays unchanged when the field is absent.
    legacy = parse_model_verifier_result({
        **payload,
        "completion_evidence": [{
            "requirement": "req", "observed": "obs",
            "falsification_check": "countercheck", "inspection_refs": ["probe-1"],
        }],
    })
    assert legacy.completion_evidence[0].requirement_status == ""
    assert "requirement_status" not in legacy.as_dict()["completion_evidence"][0]
    # Shared parser is transport-only for this optional field; PERSISTENT's strict
    # provider schema owns the enum. This keeps generic/TRIAD runtime parsing
    # backward compatible even for callers outside the strict provider path.
    payload["completion_evidence"][0]["requirement_status"] = "maybe"
    assert parse_model_verifier_result(payload).completion_evidence[0].requirement_status == "maybe"


def test_f94_persistent_loop_refuses_repeated_completed_with_violated_status() -> None:
    compiled = replace(_compiled(), solver_turn_protocol="persistent_v0")
    record = _valid_record([_inspection_id("probe-1")])
    record[0]["requirement_status"] = "violated"
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed(record),
        _completed(record),
    ], compiled_override=compiled)
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert parsed.findings[0].finding_id == "vf-completion-evidence-record"
    assert "requirement_status=violated" in parsed.summary
    assert len(calls) == 3
    retry = json.loads(calls[2][-1]["content"])
    assert "requirement_status=violated" in retry["instruction"]
    assert "different verdict" in retry["instruction"]


def test_f94_persistent_loop_accepts_corrected_satisfied_status_after_one_record_retry() -> None:
    compiled = replace(_compiled(), solver_turn_protocol="persistent_v0")
    violated = _valid_record([_inspection_id("probe-1")])
    violated[0]["requirement_status"] = "violated"
    satisfied = _valid_record([_inspection_id("probe-1")])
    satisfied[0]["requirement_status"] = "satisfied"
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed(violated),
        _completed(satisfied),
    ], compiled_override=compiled)
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert parsed.completion_evidence[0].requirement_status == "satisfied"
    assert len(calls) == 3


# ---------------------------------------------------------------------------
# Post-vNext2 closure: keep PERSISTENT raw-clause binding correction inside Verifier
# ---------------------------------------------------------------------------

def test_persistent_completed_record_missing_raw_task_clause_retries_inside_verifier_loop() -> None:
    compiled = replace(_compiled(), solver_turn_protocol="persistent_v0")
    missing = _valid_record([_inspection_id("probe-1")])
    missing[0].update({
        "requirement_status": "satisfied",
        "clause_ids": ["task:a"],
    })
    corrected = _valid_record([_inspection_id("probe-1")])
    corrected[0].update({
        "requirement_status": "satisfied",
        "clause_ids": ["task:a", "task:b"],
    })
    raw, calls = _run_verify(
        [
            _INSPECT_REQUEST,
            _completed(missing),
            _completed(corrected),
        ],
        packet_overrides={
            "task_contract": {
                "clauses": [
                    {"clause_id": "task:a", "text": "first independent requirement"},
                    {"clause_id": "task:b", "text": "second independent requirement"},
                ],
                "method_constraints": [],
            },
        },
        compiled_override=compiled,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(calls) == 3
    retry = json.loads(calls[2][-1]["content"])
    assert "completion_evidence is missing raw task clause coverage: task:b" in retry["instruction"]
    covered = {
        clause_id
        for entry in parsed.completion_evidence
        for clause_id in entry.clause_ids
    }
    assert covered == {"task:a", "task:b"}


def test_persistent_completion_record_problem_requires_every_raw_task_clause_but_not_generic() -> None:
    entry = CompletionEvidenceEntry(
        requirement="first",
        observed="observed",
        falsification_check="counterexample would fail",
        inspection_refs=("probe-1",),
        clause_ids=("task:a",),
        requirement_status="satisfied",
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    packet = {
        "task_contract": {
            "clauses": [
                {"clause_id": "task:a"},
                {"clause_id": "task:b"},
            ],
            "method_constraints": [],
        },
    }
    assert _completion_record_problem(result, {"probe-1"}, packet=packet) == ""
    problem = _completion_record_problem(
        result,
        {"probe-1"},
        packet=packet,
        require_requirement_status=True,
    )
    assert "missing raw task clause coverage: task:b" in problem


def test_blocking_finding_rejects_any_failed_or_nonadmissible_supporting_ref() -> None:
    payload = _direct_needs_repair(execution_ref=None)
    payload["findings"][0]["supporting_inspection_ids"] = ["inspection:test:port", "inspection:test:failed-derived"]
    result = parse_model_verifier_result(payload)
    problem = _verdict_admissibility_problem(result, {"inspection:test:port"}, set())
    assert "cites non-admissible evidence" in problem
    assert "inspection:test:failed-derived" in problem


def test_mixed_direct_and_failed_derived_finding_is_not_fully_directly_grounded() -> None:
    payload = _direct_needs_repair(execution_ref=None)
    payload["findings"][0]["supporting_inspection_ids"] = ["inspection:test:port", "inspection:test:failed-derived"]
    result = parse_model_verifier_result(payload)
    assert _needs_repair_is_fully_directly_grounded(result, {"inspection:test:port"}) is False


def test_persistent_completed_record_rejects_evidence_class_above_kernel_actual_class() -> None:
    entry = CompletionEvidenceEntry(
        requirement="current package satisfies the clause",
        observed="direct reads plus isolated execution support the clause",
        falsification_check="a contrary isolated result would falsify completion",
        inspection_refs=("source", "derive"),
        clause_ids=("task:a",),
        evidence_class="independent_semantic",
        requirement_status="satisfied",
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    packet = {"task_contract": {"clauses": [{"clause_id": "task:a"}], "method_constraints": []}}
    problem = _completion_record_problem(
        result, {"source", "derive"}, packet=packet,
        inspection_actual_classes={"source": "exact_contract", "derive": "exact_contract"},
        require_requirement_status=True,
    )
    assert "evidence_class=independent_semantic exceeds" in problem
    assert "actual evidence class=exact_contract" in problem


def test_persistent_completed_record_accepts_claim_not_above_kernel_actual_class() -> None:
    entry = CompletionEvidenceEntry(
        requirement="current package satisfies the clause",
        observed="direct reads plus isolated execution support the clause",
        falsification_check="a contrary isolated result would falsify completion",
        inspection_refs=("source", "derive"),
        clause_ids=("task:a",),
        evidence_class="exact_contract",
        requirement_status="satisfied",
    )
    result = type("_R", (), {"completion_evidence": (entry,)})()
    packet = {"task_contract": {"clauses": [{"clause_id": "task:a"}], "method_constraints": []}}
    assert _completion_record_problem(
        result, {"source", "derive"}, packet=packet,
        inspection_actual_classes={"source": "exact_contract", "derive": "exact_contract"},
        require_requirement_status=True,
    ) == ""


def test_persistent_loop_corrects_overclaimed_evidence_class_inside_verifier_lane() -> None:
    compiled = replace(_compiled(), solver_turn_protocol="persistent_v0")
    def exact_inspector(requests):
        return [{
            "request_id": req.request_id,
            "inspection_id": _inspection_id(req.request_id),
            "kind": req.kind,
            "path": req.path,
            "excerpt": "current exact state",
            "eligible_for_proof": True,
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "exact_contract",
        } for req in requests]
    over = _valid_record([_inspection_id("probe-1")])
    over[0].update({
        "clause_ids": ["task:a"],
        "requirement_status": "satisfied",
        "evidence_class": "independent_semantic",
    })
    corrected = _valid_record([_inspection_id("probe-1")])
    corrected[0].update({
        "clause_ids": ["task:a"],
        "requirement_status": "satisfied",
        "evidence_class": "exact_contract",
    })
    raw, calls = _run_verify(
        [_INSPECT_REQUEST, _completed(over), _completed(corrected)],
        packet_overrides={
            "task_contract": {
                "clauses": [{"clause_id": "task:a", "text": "one clause"}],
                "method_constraints": [],
            },
        },
        inspector=exact_inspector,
        compiled_override=compiled,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert parsed.completion_evidence[0].evidence_class == "exact_contract"
    assert len(calls) == 3
    correction = json.loads(calls[2][-1]["content"])
    assert "evidence_class=independent_semantic exceeds" in correction["instruction"]
    assert "actual evidence class=exact_contract" in correction["instruction"]
