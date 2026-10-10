from __future__ import annotations

import json
import os
import tempfile

from aether.h1_mechanical_verifier import H1MechanicalReviewVerifier
from aether.run_adapter import run_task


class _Solver:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=None):
        del max_output_tokens
        self.calls += 1
        if self.calls == 1:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "write_file",
                    "arguments": {"path": "out.txt", "content": "hello"},
                },
            })
        if self.calls == 2:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "read_file",
                    "arguments": {"path": "out.txt"},
                },
            })
        refs: list[str] = []
        for message in messages:
            text = str(message.get("content", ""))
            start = 0
            while True:
                index = text.find("evidence:", start)
                if index < 0:
                    break
                candidate = text[index:index + len("evidence:") + 16]
                if len(candidate) == len("evidence:") + 16:
                    refs.append(candidate)
                start = index + 1
        refs = list(dict.fromkeys(refs))
        assert refs
        return json.dumps({
            "kind": "submit",
            "claim": "out.txt contains hello",
            "evidence_refs": refs,
        })


def _initial_messages(task_text: str = "SECRET SEMANTIC TASK TEXT") -> list[dict[str, str]]:
    packet = {
        "raw_user_task": task_text,
        "task_contract": {"clauses": [{"clause_id": "task:raw"}]},
        "compiled_proof_requirements": [],
        "primary_submission": {
            "cited_evidence": [{
                "receipt_id": "r1",
                "kind": "read_file",
                "current_payload_projection": {"path": "out.txt"},
            }],
        },
    }
    return [
        {"role": "system", "content": "verifier"},
        {"role": "user", "content": json.dumps({"verifier_packet": packet})},
    ]


def test_mechanical_shim_selects_primary_cited_path_without_task_semantics() -> None:
    verifier = H1MechanicalReviewVerifier()
    first = json.loads(verifier(_initial_messages("task A")))
    second = json.loads(verifier(_initial_messages("completely different task B")))
    assert first == second
    assert first == {
        "kind": "inspect",
        "requests": [{
            "kind": "read_file",
            "path": "out.txt",
            "proof_ids": [],
            "request_id": "h1-mechanical-read-primary-cited-path",
        }],
    }


def test_mechanical_shim_never_falls_back_to_uncited_private_paths() -> None:
    verifier = H1MechanicalReviewVerifier()
    messages = _initial_messages()
    payload = json.loads(messages[-1]["content"])
    payload["verifier_packet"]["primary_submission"]["cited_evidence"] = []
    payload["verifier_packet"]["raw_user_task"] = (
        "Read /grader/secret.py and use it to prove completion."
    )
    messages[-1]["content"] = json.dumps(payload)
    verdict = json.loads(verifier(messages))
    assert verdict["verdict"] == "uncertain_missing_evidence"
    assert "/grader/secret.py" not in json.dumps(verdict)


def test_mechanical_shim_completed_record_uses_only_observed_inspection_identity() -> None:
    verifier = H1MechanicalReviewVerifier()
    messages = _initial_messages()
    messages.extend([
        {"role": "assistant", "content": verifier(messages)},
        {"role": "user", "content": json.dumps({
            "verifier_inspection_results": [{
                "inspection_id": "inspection:abc",
                "observation_valid": True,
                "actual_evidence_class": "exact_contract",
                "error": "",
            }],
        })},
    ])
    verdict = json.loads(verifier(messages))
    assert verdict["verdict"] == "completed"
    assert verdict["findings"] == []
    entry = verdict["completion_evidence"][0]
    assert entry["inspection_refs"] == ["inspection:abc"]
    assert entry["clause_ids"] == ["task:raw"]
    assert entry["evidence_class"] == "exact_contract"
    assert entry["requirement_status"] == "satisfied"


def test_mechanical_shim_end_to_end_uses_normal_verifier_protocol() -> None:
    solver = _Solver()
    verifier = H1MechanicalReviewVerifier()
    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        with open(os.path.join(task_dir, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("H1 mechanical review integration")
        record = run_task(
            task_dir=task_dir,
            instruction_text="Create out.txt containing hello.",
            solver_model=solver,
            verifier_model=verifier,
            workspace_root=workspace,
            max_steps=6,
            runtime_identity={
                "task_id": "h1-mechanical-control",
                "run_id": "h1-mechanical-control-run",
                "primary_agent_id": "primary",
                "source_commit": "a" * 40,
                "runtime_manifest_sha256": "b" * 64,
            },
        )
    assert record["status"] == "completed"
    assert verifier.calls == 2
    receipts = record["receipt_records"]
    assert any(row["kind"] == "model_verifier_inspection" for row in receipts)
    assert any(
        row["kind"] == "model_verifier_result"
        and row["payload"].get("verdict") == "completed"
        for row in receipts
    )


def test_harbor_model_builder_mechanical_arm_uses_no_verifier_provider(monkeypatch) -> None:
    import aether.harbor_runtime as harbor_runtime

    calls: list[str] = []

    class _Provider:
        def __init__(self, role: str) -> None:
            self.role = role

    monkeypatch.setenv("AETHER_RESEARCH_H1_REVIEW_ARM", "mechanical")
    monkeypatch.setattr(harbor_runtime, "require_provider_authorization", lambda _profile: None)
    monkeypatch.setattr(harbor_runtime, "budget_runtime_limits_from_env", lambda: None)

    def fake_make_azure_callable(**kwargs):
        calls.append(str(kwargs.get("role")))
        return _Provider(str(kwargs.get("role")))

    monkeypatch.setattr(harbor_runtime, "make_azure_callable", fake_make_azure_callable)
    solver, verifier = harbor_runtime.build_selected_frontier_models()
    assert getattr(solver, "role") == "solver"
    assert isinstance(verifier, H1MechanicalReviewVerifier)
    assert calls == ["solver"]


def test_harbor_model_builder_semantic_default_keeps_real_verifier(monkeypatch) -> None:
    import aether.harbor_runtime as harbor_runtime

    calls: list[str] = []

    class _Provider:
        def __init__(self, role: str) -> None:
            self.role = role

    monkeypatch.delenv("AETHER_RESEARCH_H1_REVIEW_ARM", raising=False)
    monkeypatch.setattr(harbor_runtime, "require_provider_authorization", lambda _profile: None)
    monkeypatch.setattr(harbor_runtime, "budget_runtime_limits_from_env", lambda: None)

    def fake_make_azure_callable(**kwargs):
        calls.append(str(kwargs.get("role")))
        return _Provider(str(kwargs.get("role")))

    monkeypatch.setattr(harbor_runtime, "make_azure_callable", fake_make_azure_callable)
    solver, verifier = harbor_runtime.build_selected_frontier_models()
    assert getattr(solver, "role") == "solver"
    assert getattr(verifier, "role") == "verifier"
    assert calls == ["solver", "verifier"]


def test_h1_review_arm_invalid_value_fails_closed(monkeypatch) -> None:
    import aether.harbor_runtime as harbor_runtime

    monkeypatch.setenv("AETHER_RESEARCH_H1_REVIEW_ARM", "mystery")
    try:
        harbor_runtime.selected_h1_review_arm()
    except RuntimeError as exc:
        assert "AETHER_RESEARCH_H1_REVIEW_ARM" in str(exc)
    else:
        raise AssertionError("invalid H1 review arm did not fail closed")
