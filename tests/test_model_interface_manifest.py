from __future__ import annotations

import json
from pathlib import Path

from aether.model_hooks import ModelHooks
from aether.model_interface import (
    MODEL_INTERFACE_SCHEMA_VERSION,
    build_model_interface_capture,
    compact_model_interface_manifests,
    write_model_interface_captures,
)
from aether.runtime_ir import ACTION_SCHEMA


class _Compiled:
    action_schema = ACTION_SCHEMA


def test_manifest_preserves_exact_order_and_accounts_stable_vs_volatile() -> None:
    messages = [
        {"role": "system", "content": "[kernel_contract]\nfixed"},
        {"role": "system", "content": "[task_contract]\n{\"x\":1}"},
        {"role": "system", "content": "[context_packet]\n{\"recent\":[]}"},
    ]
    capture = build_model_interface_capture(
        messages,
        model_role="solver",
        role_call_ordinal=3,
        max_output_tokens=16000,
        stable_prefix_count=2,
    )
    manifest = capture["manifest"]
    assert capture["schema_version"] == MODEL_INTERFACE_SCHEMA_VERSION
    assert capture["messages"] == messages
    assert manifest["role_sequence"] == ["system", "system", "system"]
    assert manifest["section_sequence"] == [
        "kernel_contract", "task_contract", "context_packet"
    ]
    assert manifest["stable_prefix"]["messages"] == 2
    assert manifest["volatile"]["messages"] == 1
    assert manifest["aggregate"]["utf8_bytes"] == (
        manifest["stable_prefix"]["utf8_bytes"]
        + manifest["volatile"]["utf8_bytes"]
    )
    assert manifest["messages"][0]["stable_prefix"] is True
    assert manifest["messages"][2]["stable_prefix"] is False


def test_manifest_records_json_keys_and_exact_duplicate_messages() -> None:
    duplicate = '{"b":2,"a":1}'
    capture = build_model_interface_capture(
        [
            {"role": "user", "content": duplicate},
            {"role": "assistant", "content": duplicate},
        ],
        model_role="verifier",
        role_call_ordinal=1,
        max_output_tokens=4000,
    )
    manifest = capture["manifest"]
    assert manifest["messages"][0]["json_top_level_keys"] == ["b", "a"]
    assert manifest["messages"][0]["sha256"] == manifest["messages"][1]["sha256"]
    assert manifest["exact_duplicate_messages"] == [{
        "sha256": manifest["messages"][0]["sha256"],
        "message_indices": [0, 1],
    }]


def test_transcript_hash_is_order_sensitive() -> None:
    left = build_model_interface_capture(
        [
            {"role": "system", "content": "one"},
            {"role": "user", "content": "two"},
        ],
        model_role="solver",
        role_call_ordinal=1,
        max_output_tokens=1000,
    )
    right = build_model_interface_capture(
        [
            {"role": "user", "content": "two"},
            {"role": "system", "content": "one"},
        ],
        model_role="solver",
        role_call_ordinal=1,
        max_output_tokens=1000,
    )
    assert left["manifest"]["transcript_sha256"] != right["manifest"]["transcript_sha256"]


def test_model_hooks_capture_exact_solver_and_verifier_interfaces() -> None:
    seen: list[list[dict[str, str]]] = []

    def model(messages, *, max_output_tokens=8000):
        seen.append([dict(item) for item in messages])
        if messages and messages[0]["content"].startswith("[solver_identity]"):
            return json.dumps({"kind": "submit", "claim": "done", "evidence_refs": ["evidence:0123456789abcdef"]})
        return json.dumps({"verdict": "uncertain_missing_evidence", "confidence": "high", "summary": "need evidence", "missing_evidence_requests": ["inspect"]})

    hooks = ModelHooks(model, model)
    solver_messages = [
        {"role": "system", "content": "[solver_identity]\nsolve"},
        {"role": "system", "content": "[task_contract]\n{}"},
        {"role": "system", "content": "[context_packet]\n{}"},
    ]
    hooks.solve(solver_messages, _Compiled())  # type: ignore[arg-type]
    verifier_messages = [
        {"role": "system", "content": "verify"},
        {"role": "user", "content": "{}"},
        {"role": "assistant", "content": "prior"},
        {"role": "user", "content": "more evidence"},
    ]
    hooks.call_verifier(verifier_messages, max_output_tokens=4000)

    captures = hooks.drain_model_interface_captures()
    assert seen == [solver_messages, verifier_messages]
    assert len(captures) == 2
    solver = captures[0]
    verifier = captures[1]
    assert solver["messages"] == solver_messages
    assert solver["manifest"]["model_role"] == "solver"
    assert solver["manifest"]["stable_prefix_count"] == 2
    assert verifier["messages"] == verifier_messages
    assert verifier["manifest"]["model_role"] == "verifier"
    assert verifier["manifest"]["stable_prefix_count"] == 2
    assert hooks.drain_model_interface_captures() == ()


def test_write_model_interface_captures_separates_exact_transcripts(tmp_path: Path) -> None:
    captures = [
        build_model_interface_capture(
            [{"role": "system", "content": "[task_contract]\nsecret exact bytes"}],
            model_role="solver",
            role_call_ordinal=1,
            max_output_tokens=16000,
            stable_prefix_count=1,
        )
    ]
    written = write_model_interface_captures(captures, tmp_path / "interfaces")
    index = json.loads(Path(written["index_path"]).read_text(encoding="utf-8"))
    transcript_path = Path(written["directory"]) / index["captures"][0]["path"]
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert written["capture_count"] == 1
    assert transcript["messages"] == captures[0]["messages"]
    assert compact_model_interface_manifests(captures) == [captures[0]["manifest"]]
