from __future__ import annotations

import json
from types import SimpleNamespace

from aether.model_prompts import VERIFIER_RUNTIME_CONTRACT
from aether.pcr_verifier_prompt import (
    PCR_VERIFIER_PROTOCOL_PROFILE,
    PCR_VERIFIER_SEMANTIC_GUIDE,
    pcr_verifier_identity_prompt,
    verifier_runtime_contract_for,
)
from aether.pcr_runtime import PCR_VERIFIER_CONSTITUTION
from aether.verify_inspection_requests import _verifier_identity_prompt_for


def _pcr_compiled() -> SimpleNamespace:
    return SimpleNamespace(
                verifier_identity_prompt=PCR_VERIFIER_CONSTITUTION,
        task_contract=SimpleNamespace(method_constraints=()),
    )


def test_pcr_verifier_prompt_keeps_semantic_authority_without_protocol_manual() -> None:
    prompt = _verifier_identity_prompt_for(_pcr_compiled())

    assert PCR_VERIFIER_CONSTITUTION in prompt
    assert PCR_VERIFIER_SEMANTIC_GUIDE.strip() in prompt
    assert "independently falsifiable obligation" in prompt
    assert "Evidence for one clause does not automatically discharge an unrelated clause" in prompt
    assert "Solver-authored checks" in prompt
    assert "current independent evidence supports every visible clause" in prompt
    assert "Do not provide hidden reasoning" in prompt

    # Provider/parser/kernel own these mechanics. PCR should not serialize the
    # old operational manual or a concrete derived-command recipe up front.
    assert "complete V3 shape" not in prompt
    assert "derived-check" not in prompt
    assert "method_validity using this complete shape" not in prompt
    assert len(prompt) < 2_700


def test_pcr_runtime_contract_is_thin_mechanical_authority_marker() -> None:
    projected = verifier_runtime_contract_for(_pcr_compiled(), VERIFIER_RUNTIME_CONTRACT)

    assert projected == PCR_VERIFIER_PROTOCOL_PROFILE
    assert len(json.dumps(projected, sort_keys=True, separators=(",", ":"))) < 500
    assert "rules" not in projected
    assert "read_only_inspector" not in projected
    assert "completion_evidence_shape" not in projected


def test_direct_prompt_helper_refuses_empty_identity() -> None:
    try:
        pcr_verifier_identity_prompt("")
    except ValueError as exc:
        assert "identity prompt must be non-empty" in str(exc)
    else:
        raise AssertionError("empty PCR Verifier identity must fail closed")
