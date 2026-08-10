"""Message-building helpers extracted from kernel.py to stay under 500 LOC."""
from __future__ import annotations

import json
from typing import Any, Mapping

from .architect_input import build_architect_input
from .compiler import ConfigCompiler
from .runtime_ir import CompiledRuntime, EnvMap


def build_architect_request(
    envmap: EnvMap,
    compiler: ConfigCompiler,
) -> dict[str, Any]:
    """Build the compact factual request sent to the Architect.

    ``compiler`` remains in the signature for API compatibility.  It is not
    used to pre-author task semantics: objective clauses and proof strategy
    belong to the Architect, while the request contains only visible facts,
    observed environment support, and exact runtime controls.
    """
    del compiler
    return build_architect_input(envmap)


def build_solver_messages(
    compiled: CompiledRuntime,
    context_packet: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Build the full message list sent to the solver hook."""
    messages = compiled.prefix_messages()
    messages.append(
        {
            "role": "system",
            "content": "[context_packet]\n"
            + json.dumps(
                context_packet,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        }
    )
    return messages
