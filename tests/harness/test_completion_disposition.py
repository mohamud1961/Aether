from __future__ import annotations

from types import SimpleNamespace
import json

import pytest

from aether.completion_disposition import (
    COMPLETION_DISPOSITION_V1,
    CONTROL,
    evaluate_completion_dispositions,
)
from aether.harbor_runtime import (
    P1_COMPLETION_DISPOSITION_ARM,
    P1_COMPLETION_DISPOSITION_ARM_ENV,
    P1_CONTROL_ARM,
    build_selected_frontier_models,
    selected_p1_completion_disposition_mode,
)
from aether.model_parse import parse_solver_turn
from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.runtime_ir import ActionRequest, SolverTurn
from tests.harness.test_prompt_cache_stability import _env
from aether.providers.azure_model import AzureModelCallable
from aether.persistent_provider_protocol import (
    PERSISTENT_DIRECT_PROVIDER_TOOLS,
    PERSISTENT_DIRECT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1,
    canonicalize_persistent_direct_tool_call,
)


def _packet(*finding_ids: str) -> dict:
    return {
        "open_completion_findings": [
            {"finding_id": finding_id, "review_claim_summary": "claim"}
            for finding_id in finding_ids
        ]
    }


def _turn(*, evidence_refs=("receipt:new",), dispositions=()):
    return SimpleNamespace(
        evidence_refs=tuple(evidence_refs),
        finding_dispositions=tuple(dispositions),
    )


def test_control_is_noop_even_with_open_findings() -> None:
    decision = evaluate_completion_dispositions(
        _turn(), _packet("cf-1"), mode=CONTROL,
    )
    assert decision.allowed is True
    assert decision.reason == "control_mode"


def test_treatment_requires_every_open_finding_exactly_once() -> None:
    decision = evaluate_completion_dispositions(
        _turn(dispositions=({
            "finding_id": "cf-1",
            "disposition": "not_applicable",
            "explanation": "This claim does not apply to the raw task requirement.",
            "evidence_refs": [],
            "residual_uncertainty": "",
        },)),
        _packet("cf-1", "cf-2"),
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert decision.allowed is False
    assert decision.reason == "open_finding_not_dispositioned"


def test_resolved_does_not_require_ceremonial_explanation_when_evidence_is_cited() -> None:
    decision = evaluate_completion_dispositions(
        _turn(
            evidence_refs=("receipt:new",),
            dispositions=({
                "finding_id": "cf-1",
                "disposition": "resolved",
                "explanation": "",
                "evidence_refs": ["receipt:new"],
                "residual_uncertainty": "",
            },),
        ),
        _packet("cf-1"),
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert decision.allowed is True


def test_not_applicable_requires_model_authored_explanation() -> None:
    decision = evaluate_completion_dispositions(
        _turn(dispositions=({
            "finding_id": "cf-1",
            "disposition": "not_applicable",
            "explanation": "",
            "evidence_refs": [],
            "residual_uncertainty": "",
        },)),
        _packet("cf-1"),
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert decision.allowed is False
    assert decision.reason == "disposition_explanation_missing"


def test_resolved_requires_evidence_also_cited_by_finish() -> None:
    missing = evaluate_completion_dispositions(
        _turn(dispositions=({
            "finding_id": "cf-1",
            "disposition": "resolved",
            "explanation": "A fresh observation addresses the gap.",
            "evidence_refs": [],
            "residual_uncertainty": "",
        },)),
        _packet("cf-1"),
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert missing.allowed is False
    assert missing.reason == "resolved_disposition_requires_evidence"

    mismatched = evaluate_completion_dispositions(
        _turn(
            evidence_refs=("receipt:finish",),
            dispositions=({
                "finding_id": "cf-1",
                "disposition": "resolved",
                "explanation": "A fresh observation addresses the gap.",
                "evidence_refs": ["receipt:not-cited-by-finish"],
                "residual_uncertainty": "",
            },),
        ),
        _packet("cf-1"),
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert mismatched.allowed is False
    assert mismatched.reason == "disposition_evidence_not_in_finish_refs"


def test_override_requires_explicit_residual_uncertainty() -> None:
    decision = evaluate_completion_dispositions(
        _turn(dispositions=({
            "finding_id": "cf-1",
            "disposition": "override",
            "explanation": "I am completing despite the unresolved review claim.",
            "evidence_refs": [],
            "residual_uncertainty": "",
        },)),
        _packet("cf-1"),
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert decision.allowed is False
    assert decision.reason == "override_requires_residual_uncertainty"


def test_valid_mixed_dispositions_are_mechanically_accepted() -> None:
    decision = evaluate_completion_dispositions(
        _turn(
            evidence_refs=("receipt:new", "receipt:other"),
            dispositions=(
                {
                    "finding_id": "cf-1",
                    "disposition": "resolved",
                    "explanation": "The cited current observation addresses this gap.",
                    "evidence_refs": ["receipt:new"],
                    "residual_uncertainty": "",
                },
                {
                    "finding_id": "cf-2",
                    "disposition": "not_applicable",
                    "explanation": "The claim targets behavior outside the raw task contract.",
                    "evidence_refs": [],
                    "residual_uncertainty": "",
                },
                {
                    "finding_id": "cf-3",
                    "disposition": "override",
                    "explanation": "The task evidence is sufficient for my final decision.",
                    "evidence_refs": ["receipt:other"],
                    "residual_uncertainty": "The review concern remains possible but unconfirmed.",
                },
            ),
        ),
        _packet("cf-1", "cf-2", "cf-3"),
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert decision.allowed is True
    assert decision.reason == "all_open_findings_dispositioned"
    assert decision.as_payload()["harness_role"] == "mechanical_disposition_coverage_only"


def test_unknown_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported completion disposition mode"):
        evaluate_completion_dispositions(_turn(), _packet(), mode="decide_truth")


def _tool(tools, name: str) -> dict:
    return next(item for item in tools if item["name"] == name)


def test_provider_treatment_changes_only_final_finish_schema() -> None:
    control_finish = _tool(PERSISTENT_DIRECT_PROVIDER_TOOLS, "finish")["parameters"]
    treatment_finish = _tool(
        PERSISTENT_DIRECT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1, "finish"
    )["parameters"]
    control_intent = _tool(PERSISTENT_DIRECT_PROVIDER_TOOLS, "finish_intent")["parameters"]
    treatment_intent = _tool(
        PERSISTENT_DIRECT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1, "finish_intent"
    )["parameters"]

    assert "finding_dispositions" not in control_finish["properties"]
    assert control_finish["required"] == ["claim", "evidence_refs", "finish_metadata"]
    assert treatment_finish["required"] == [
        "claim", "evidence_refs", "finish_metadata", "finding_dispositions"
    ]
    assert "finding_dispositions" in treatment_finish["properties"]
    assert control_finish["properties"]["finish_metadata"] == treatment_finish["properties"]["finish_metadata"]
    assert treatment_intent == control_intent


def test_direct_finish_dispositions_survive_canonicalization_and_model_parse() -> None:
    payload = {
        "claim": "The current candidate is complete.",
        "evidence_refs": ["evidence:0123456789abcdef"],
        "finding_dispositions": [{
            "finding_id": "cf-1",
            "disposition": "resolved",
            "explanation": "The cited observation addresses the open gap.",
            "evidence_refs": ["evidence:0123456789abcdef"],
            "residual_uncertainty": "",
        }],
    }
    canonical, receipt = canonicalize_persistent_direct_tool_call(
        "finish", json.dumps(payload)
    )
    turn = parse_solver_turn(canonical)
    assert receipt["provider_direct_tool_name"] == "finish"
    assert turn.kind == "finish_outcome"
    assert turn.finding_dispositions[0]["finding_id"] == "cf-1"
    assert turn.finding_dispositions[0]["disposition"] == "resolved"


def test_harbor_selector_is_default_off_and_production_only(monkeypatch) -> None:
    monkeypatch.delenv(P1_COMPLETION_DISPOSITION_ARM_ENV, raising=False)
    assert selected_p1_completion_disposition_mode(build_selected_frontier_models) == P1_CONTROL_ARM
    monkeypatch.setenv(P1_COMPLETION_DISPOSITION_ARM_ENV, P1_COMPLETION_DISPOSITION_ARM)
    assert (
        selected_p1_completion_disposition_mode(build_selected_frontier_models)
        == P1_COMPLETION_DISPOSITION_ARM
    )
    assert selected_p1_completion_disposition_mode(object()) == P1_CONTROL_ARM


def test_harbor_selector_rejects_unknown_arm(monkeypatch) -> None:
    monkeypatch.setenv(P1_COMPLETION_DISPOSITION_ARM_ENV, "harness_decides_truth")
    with pytest.raises(RuntimeError, match="AETHER_RESEARCH_P1_COMPLETION_DISPOSITION"):
        selected_p1_completion_disposition_mode(build_selected_frontier_models)



def _context_packet(messages: list[dict[str, str]]) -> dict:
    content = messages[-1]["content"]
    assert content.startswith("[context_packet]\n")
    return json.loads(content.split("\n", 1)[1])


def _latest_primary_ref(messages: list[dict[str, str]]) -> str:
    packet = _context_packet(messages)
    refs = packet["latest_primary_result"]["outcome_receipts"]
    assert refs
    return str(refs[0]["evidence_ref"])


class _DispositionKernelHooks:
    def __init__(self, *, include_disposition: bool) -> None:
        self.solve_calls = 0
        self.include_disposition = include_disposition
        self.write_ref = ""
        self.disposition_modes: list[str] = []

    def configure_completion_disposition_mode(self, mode: str) -> None:
        self.disposition_modes.append(str(mode))

    def solve(self, messages, _compiled):
        self.solve_calls += 1
        if self.solve_calls == 1:
            return SolverTurn(
                kind="act",
                summary="write candidate",
                actions=(ActionRequest(
                    action_id="write-candidate",
                    kind="write_file",
                    capability_id="filesystem",
                    arguments={"path": "out.txt", "content": "candidate\n"},
                    intent="create the candidate",
                    expected_observation="out.txt exists",
                    if_fail_next="inspect the write failure",
                ),),
            )
        if not self.write_ref:
            self.write_ref = _latest_primary_ref(messages)
        if self.solve_calls == 2:
            return SolverTurn(
                kind="finish_intent",
                summary="request review",
                claim="candidate is complete",
                evidence_refs=(self.write_ref,),
            )
        dispositions = ()
        if self.include_disposition:
            packet = _context_packet(messages)
            findings = packet.get("open_completion_findings") or []
            assert findings
            dispositions = ({
                "finding_id": findings[0]["finding_id"],
                "disposition": "override",
                "explanation": "I retain the completion decision despite the open review claim.",
                "evidence_refs": [],
                "residual_uncertainty": "The independent concern remains unresolved.",
            },)
        return SolverTurn(
            kind="finish_outcome",
            summary="final completion decision",
            claim="candidate is complete",
            evidence_refs=(self.write_ref,),
            finding_dispositions=dispositions,
        )

    def verify(self, _packet, _compiled, _ledger):
        return json.dumps({
            "verdict": "needs_repair",
            "confidence": "high",
            "summary": "The candidate has an unresolved completion concern.",
            "findings": [{
                "finding_id": "open-gap",
                "verdict": "needs_repair",
                "priority": "blocking",
                "summary": "A central requirement remains unverified.",
                "evidence": ["review-observation"],
            }],
        })


def test_kernel_treatment_blocks_final_finish_without_explicit_disposition() -> None:
    hooks = _DispositionKernelHooks(include_disposition=False)
    result = AetherNextKernel(
        max_steps=3,
        completion_disposition_mode=COMPLETION_DISPOSITION_V1,
    ).run(_env(), MemoryExecutor(workspace_root="/app"), hooks)
    blocks = [
        row for row in result.receipts
        if row.kind == "completion_finding_disposition_block"
    ]
    assert len(blocks) == 1
    assert blocks[0].failure_class == "completion_finding_disposition_incomplete"
    assert blocks[0].payload["reason"] == "open_finding_not_dispositioned"
    assert blocks[0].payload["required_finding_ids"]
    assert hooks.disposition_modes[:2] == [CONTROL, CONTROL]
    assert hooks.disposition_modes[2] == COMPLETION_DISPOSITION_V1


def test_kernel_control_does_not_add_disposition_block() -> None:
    hooks = _DispositionKernelHooks(include_disposition=False)
    result = AetherNextKernel(max_steps=3).run(
        _env(), MemoryExecutor(workspace_root="/app"), hooks,
    )
    assert not any(
        row.kind == "completion_finding_disposition_block" for row in result.receipts
    )


def test_kernel_treatment_records_model_owned_override_disposition() -> None:
    hooks = _DispositionKernelHooks(include_disposition=True)
    result = AetherNextKernel(
        max_steps=3,
        completion_disposition_mode=COMPLETION_DISPOSITION_V1,
    ).run(_env(), MemoryExecutor(workspace_root="/app"), hooks)
    rows = [
        row for row in result.receipts
        if row.kind == "completion_finding_dispositions"
    ]
    assert len(rows) == 1
    assert rows[0].success is True
    assert rows[0].payload["harness_role"] == "mechanical_disposition_coverage_only"
    assert rows[0].payload["dispositions"][0]["disposition"] == "override"


def test_treatment_stays_provider_invisible_when_review_has_no_open_findings() -> None:
    class CleanHooks(_DispositionKernelHooks):
        def verify(self, _packet, _compiled, _ledger):
            return json.dumps({
                "verdict": "completed",
                "confidence": "high",
                "summary": "No open completion findings.",
                "findings": [],
            })

    hooks = CleanHooks(include_disposition=False)
    AetherNextKernel(
        max_steps=3,
        completion_disposition_mode=COMPLETION_DISPOSITION_V1,
    ).run(_env(), MemoryExecutor(workspace_root="/app"), hooks)
    assert hooks.disposition_modes == [CONTROL, CONTROL]


def test_provider_scope_selects_disposition_finish_without_mutating_actions_or_other_scope() -> None:
    model = AzureModelCallable(
        client=object(),  # type: ignore[arg-type]
        deployment="unit-test-frontier", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    scope = ("run-a", "task-a")
    control_tools, _ = model._primary_provider_tools_for_scope(scope)
    control_finish = _tool(tuple(control_tools), "finish")["parameters"]
    control_read = _tool(tuple(control_tools), "read_file")["parameters"]
    assert control_finish["required"] == ["claim", "evidence_refs", "finish_metadata"]

    model.set_completion_disposition_mode(
        COMPLETION_DISPOSITION_V1, run_id="run-a", task_id="task-a"
    )
    treatment_tools, _ = model._primary_provider_tools_for_scope(scope)
    treatment_finish = _tool(tuple(treatment_tools), "finish")["parameters"]
    treatment_read = _tool(tuple(treatment_tools), "read_file")["parameters"]
    assert treatment_finish["required"] == [
        "claim", "evidence_refs", "finish_metadata", "finding_dispositions"
    ]
    assert treatment_finish["properties"]["finish_metadata"] == control_finish["properties"]["finish_metadata"]
    assert treatment_read == control_read

    other_tools, _ = model._primary_provider_tools_for_scope(("run-b", "task-b"))
    assert _tool(tuple(other_tools), "finish")["parameters"] == control_finish


def test_provider_scope_combines_commitment_and_disposition_without_cross_contamination() -> None:
    model = AzureModelCallable(
        client=object(),  # type: ignore[arg-type]
        deployment="unit-test-frontier", effort="low", role="solver",
        responses_background=False, poll_interval_s=1.0, poll_timeout_s=30.0,
        max_retries=0, prompt_cache_mode="off",
    )
    model.set_solver_commitment_mode("commitment_v1", run_id="run-a", task_id="task-a")
    model.set_completion_disposition_mode(
        COMPLETION_DISPOSITION_V1, run_id="run-a", task_id="task-a"
    )
    tools, _ = model._primary_provider_tools_for_scope(("run-a", "task-a"))
    assert "finding_dispositions" in _tool(tuple(tools), "finish")["parameters"]["required"]
    assert set(_tool(tuple(tools), "read_file")["parameters"]["required"]) == {
        "summary", "evidence_gap", "intent", "expected_observation",
        "if_fail_next", "arguments",
    }


def test_historical_findings_do_not_become_current_completion_obligations() -> None:
    packet = {
        "open_completion_findings": [{
            "finding_id": "cf-old",
            "currentness": "historical_candidate",
            "review_claim_summary": "old concern",
        }]
    }
    decision = evaluate_completion_dispositions(
        _turn(), packet, mode=COMPLETION_DISPOSITION_V1,
    )
    assert decision.allowed is True
    assert decision.reason == "no_open_findings"
    assert decision.required_finding_ids == ()


def test_mixed_current_and_historical_findings_require_only_current_ids() -> None:
    packet = {
        "open_completion_findings": [
            {
                "finding_id": "cf-old",
                "currentness": "historical_candidate",
                "review_claim_summary": "old concern",
            },
            {
                "finding_id": "cf-now",
                "currentness": "current_candidate",
                "review_claim_summary": "current concern",
            },
        ]
    }
    decision = evaluate_completion_dispositions(
        _turn(dispositions=({
            "finding_id": "cf-now",
            "disposition": "not_applicable",
            "explanation": "The current concern does not apply to the raw contract.",
            "evidence_refs": [],
            "residual_uncertainty": "",
        },)),
        packet,
        mode=COMPLETION_DISPOSITION_V1,
    )
    assert decision.allowed is True
    assert decision.required_finding_ids == ("cf-now",)



def test_historical_only_findings_do_not_activate_provider_treatment_helper() -> None:
    from aether.completion_disposition import current_completion_finding_ids

    assert current_completion_finding_ids({
        "open_completion_findings": [{
            "finding_id": "cf-old",
            "currentness": "historical_candidate",
        }]
    }) == ()
