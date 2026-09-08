from __future__ import annotations

import json

import pytest

from aether.model_hooks import ModelHooks, ModelOutputError
from aether.pcr_runtime import build_pcr_runtime
from aether.runtime_ir import CapabilityDescriptor, EnvMap


def _compiled():
    envmap = EnvMap(
        task_prompt="Produce the requested current-state result.",
        workspace_root="/app",
        visible_files=("out.txt",),
        capabilities={
            "shell": CapabilityDescriptor(capability_id="shell", summary="run commands"),
            "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="read files"),
        },
    )
    resolved = build_pcr_runtime(envmap)
    assert resolved.compiled is not None
    return resolved.compiled


def _ledger():
    return type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()


def _completed() -> str:
    return json.dumps({
        "verdict": "completed",
        "confidence": "high",
        "summary": "done",
        "completion_evidence": [{
            "requirement": "result is complete",
            "observed": "packet says complete",
            "falsification_check": "inspect current state",
            "inspection_refs": ["not-yet-inspected"],
        }],
    })


def test_uninspected_completion_gets_one_model_owned_inspection_correction_not_auto_tool_selection() -> None:
    calls: list[list[dict[str, str]]] = []
    inspector_calls: list[object] = []

    def verifier(messages, *, max_output_tokens=None):
        del max_output_tokens
        calls.append([dict(row) for row in messages])
        return _completed()

    def inspector(requests):
        inspector_calls.append(requests)
        raise AssertionError("Aether must not choose an inspection for an uninspected completion")

    hooks = ModelHooks(lambda *_args, **_kwargs: "{}", verifier)
    with pytest.raises(
        ModelOutputError,
        match="completed without required typed inspection after correction",
    ):
        hooks.verify_with_inspector(
            {"reason": "solver_submit", "artifacts_present": ["out.txt"]},
            _compiled(), _ledger(), inspector,
        )

    assert len(calls) == 2
    assert inspector_calls == []
    correction = json.loads(calls[1][-1]["content"])
    assert correction["automatic_inspection_selected_by_harness"] is False
    assert "kind='inspect'" in correction["instruction"]


def test_uninspected_tooling_block_gets_one_model_owned_inspection_correction_not_auto_tool_selection() -> None:
    calls: list[list[dict[str, str]]] = []
    inspector_calls: list[object] = []

    blocked = json.dumps({
        "verdict": "blocked_by_tooling",
        "confidence": "medium",
        "summary": "tooling unavailable",
    })

    def verifier(messages, *, max_output_tokens=None):
        del max_output_tokens
        calls.append([dict(row) for row in messages])
        return blocked

    def inspector(requests):
        inspector_calls.append(requests)
        raise AssertionError("Aether must not invent the missing tooling inspection")

    hooks = ModelHooks(lambda *_args, **_kwargs: "{}", verifier)
    with pytest.raises(
        ModelOutputError,
        match="blocked_by_tooling without attempting a typed inspection after correction",
    ):
        hooks.verify_with_inspector(
            {"reason": "solver_submit", "artifacts_present": ["out.txt"]},
            _compiled(), _ledger(), inspector,
        )

    assert len(calls) == 2
    assert inspector_calls == []
    correction = json.loads(calls[1][-1]["content"])
    assert correction["automatic_inspection_selected_by_harness"] is False
    assert "kind='inspect'" in correction["instruction"]
