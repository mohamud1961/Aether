from __future__ import annotations

from aether.attention_projection import (
    CONTROL_MODE,
    attention_projection_policy,
    project_command_stream_for_attention,
)
from aether.context_views import receipt_inline_view
from aether.ledger import Receipt
from aether.model_interface import build_model_interface_capture


def test_control_policy_is_single_fixed_s5_projection() -> None:
    assert attention_projection_policy() == {
        "schema_version": "aether.attention_projection.v1",
        "mode": CONTROL_MODE,
        "command_stream_inline_chars": 8000,
        "head_chars": 4000,
        "tail_chars": 4000,
        "large_stream_exact_access": "existing_output_handle",
        "explicit_retrieval_actions_remain_unprojected": True,
    }


def test_control_projection_preserves_existing_command_attention_field_byte_for_byte() -> None:
    payload = {
        "stdout": "existing-control-view",
        "stdout_full": "different-full-authority",
        "stdout_bytes": 9999,
    }
    assert project_command_stream_for_attention(payload, "stdout") == "existing-control-view"


def test_explicit_read_output_chunk_is_not_reprojected() -> None:
    chunk = "R" * 6000
    receipt = Receipt(
        receipt_id="step-2:r1:output",
        step=2,
        kind="read_output",
        success=True,
        summary="explicit output retrieval",
        payload={
            "handle": "1:a1:stdout",
            "chunk": chunk,
            "bytes": 9000,
            "offset": 0,
            "span": 6000,
        },
    )
    assert receipt_inline_view(receipt)["chunk"] == chunk


def test_model_interface_manifest_derives_installed_attention_implementation() -> None:
    capture = build_model_interface_capture(
        [{"role": "system", "content": "stable"}, {"role": "user", "content": "dynamic"}],
        model_role="solver",
        role_call_ordinal=1,
        max_output_tokens=100,
        stable_prefix_count=1,
    )
    manifest = capture["manifest"]
    assert manifest["attention_projection"] == {"mode": CONTROL_MODE}
    assert manifest["model_profile"]["profile_id"] == "production-pcr-v1"
    assert len(manifest["model_profile_sha256"]) == 64
