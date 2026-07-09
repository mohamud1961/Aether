"""Completion-evidence protocol: content-blind gate on completed verdicts.

Design of record: audit addendum (FABLE5_ADVERSARIAL_AUDIT_20260708T165639Z.md)
Concern 1 — the harness checks presence, non-emptiness, and that
inspection_refs resolve to inspections actually performed in the round.
It never evaluates reasoning content.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from aether_next.compiler import CapabilityRegistry, ConfigCompiler
from aether_next.model_hooks import (
    ModelHooks,
    VERIFIER_RUNTIME_CONTRACT,
    _completion_record_problem,
    _refs_from_inspections,
)
from aether_next.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether_next.verifier import (
    CompletionEvidenceEntry,
    parse_model_verifier_result,
)
from aether_next.verifier_inspector import VerifierInspectionRequest
from aether_next.workbench_compile import harness_config_to_runtime_ir
from aether_next.workbench_config import parse_harness_config_ir
from aether_next.workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT


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
    return type("_L", (), {"all_receipts": lambda self: []})()


_INSPECT_REQUEST = json.dumps({
    "kind": "inspect",
    "summary": "Read the decisive output transcript.",
    "requests": [
        {"request_id": "probe-1", "kind": "read_output", "handle": "5:a-1:stdout", "span": 4000}
    ],
})


def _grounded_inspector(requests):
    return [
        {
            "request_id": req.request_id,
            "kind": req.kind,
            "handle": req.handle,
            "path": req.path,
            "excerpt": "observed value=7 matches requirement value=7",
        }
        for req in requests
    ]


def _completed(record: list[dict[str, Any]] | None) -> str:
    payload: dict[str, Any] = {
        "verdict": "completed",
        "confidence": "high",
        "summary": "Deliverable matches the requirement.",
    }
    if record is not None:
        payload["completion_evidence"] = record
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


def _run_verify(responses: list[str]) -> tuple[str, list[list[dict[str, str]]]]:
    calls: list[list[dict[str, str]]] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        calls.append(list(messages))
        return responses[min(len(calls) - 1, len(responses) - 1)]

    hooks = ModelHooks(
        architect_model=lambda m, *, max_output_tokens=8000: "{}",
        solver_model=lambda m, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )
    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Write out.txt", "artifacts_present": ["out.txt"]},
        _compiled(),
        ledger=_ledger_stub(),
        inspector=_grounded_inspector,
    )
    return raw, calls


# ---------------------------------------------------------------------------
# Runtime gate behavior
# ---------------------------------------------------------------------------

def test_completed_without_record_gets_one_protocol_retry_then_accepts_valid_record() -> None:
    raw, calls = _run_verify([
        _INSPECT_REQUEST,
        _completed(None),
        _completed(_valid_record(["probe-1"])),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(parsed.completion_evidence) == 1
    assert parsed.completion_evidence[0].inspection_refs == ("probe-1",)
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
        _completed(_valid_record(["5:a-1:stdout"])),
    ])
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "completed"
    assert len(calls) == 2


def test_record_with_empty_falsification_field_is_rejected() -> None:
    record = _valid_record(["probe-1"])
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


def test_refs_collected_from_requests_and_results() -> None:
    request = VerifierInspectionRequest(request_id="r-1", kind="read_file", path="out.txt")
    refs = _refs_from_inspections((request,), [{"request_id": "r-1", "handle": "2:a-1:stdout"}])
    assert {"r-1", "out.txt", "2:a-1:stdout"} <= refs


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
                "falsification_check": "would differ",
            }
        ],
    }))
    assert parsed.completion_evidence[0].inspection_refs == ("probe-1",)
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
    assert set(shape) == {"requirement", "observed", "inspection_refs", "falsification_check"}
    rules = " ".join(VERIFIER_RUNTIME_CONTRACT["rules"])
    assert "machine-re-derivable" in rules
    assert "overlay_run_command" in rules


def test_architect_doctrine_requires_method_independent_minimum_evidence() -> None:
    assert "method-independent" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "machine-re-derivable" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "around the solver's reported values" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "model_context_window_tokens" in WORKBENCH_ARCHITECT_SYSTEM_PROMPT


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
    from aether_next.model_hooks import ModelOutputError

    with pytest.raises(ModelOutputError):
        parse_harness_config_ir(_raw_config(model_context_window_tokens=500))
    with pytest.raises(ModelOutputError):
        parse_harness_config_ir(_raw_config(model_context_window_tokens="lots"))
