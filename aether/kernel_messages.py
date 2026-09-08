"""Model message construction for the PCR Solver boundary."""
from __future__ import annotations

import json
from typing import Any, Mapping

from .runtime_ir import CompiledRuntime


def build_solver_messages(
    compiled: CompiledRuntime,
    context_packet: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Build the exact stable prefix plus one factual volatile context packet."""
    messages = compiled.prefix_messages()
    messages.append({
        "role": "system",
        "content": "[context_packet]\n" + json.dumps(
            context_packet,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ),
    })
    return messages


__all__ = ["build_solver_messages"]
