"""Fixed model-attention projection for the S5 PCR production baseline.

The evidence plane is never changed here. The selected S5 implementation keeps
the executor's existing bounded command stdout/stderr view byte-for-byte; exact
streams remain in immutable receipts/spools and are retrievable by handle.

Alternative projection treatments belong to the explicit S6 experimental
boundary and are intentionally not installed as dormant production selectors.
"""
from __future__ import annotations

from typing import Any, Mapping


CONTROL_MODE = "control_8k"


def attention_projection_policy() -> dict[str, Any]:
    """Return the one installed S5 attention implementation identity."""
    return {
        "schema_version": "aether.attention_projection.v1",
        "mode": CONTROL_MODE,
        "command_stream_inline_chars": 8000,
        "head_chars": 4000,
        "tail_chars": 4000,
        "large_stream_exact_access": "existing_output_handle",
        "explicit_retrieval_actions_remain_unprojected": True,
    }


def project_command_stream_for_attention(payload: Mapping[str, Any], stream: str) -> str:
    """Return the existing executor-bounded stream without a treatment selector."""
    if stream not in {"stdout", "stderr"}:
        raise ValueError(f"unsupported command stream: {stream}")
    return str(payload.get(stream, "") or "")


__all__ = [
    "CONTROL_MODE",
    "attention_projection_policy",
    "project_command_stream_for_attention",
]
