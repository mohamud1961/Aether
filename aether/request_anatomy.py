"""Per-request model-facing anatomy provenance (X3 treatment-isolation law).

When ``AETHER_REQUEST_ANATOMY`` is enabled, every provider request is reduced
to plane-separated digests and byte counts before it leaves the harness:

* ``instructions``          stable authority text (MUST_REPEAT plane)
* ``input``                 the explicit Aether boundary items (MUST_REFRESH /
                            DELTA_ONLY / HANDLE_ONLY planes)
* ``reasoning``             private-reasoning continuity parameters
                            (the ONLY intended X3 treatment field)
* ``tools`` / ``tool_choice`` tool contract surface
* continuity metadata       previous_response_id presence + ``store``

Rows are appended as deterministic JSON Lines (no timestamps inside the row;
correlate through provider job ids in existing telemetry).  Per-input-item
digests allow post-run attribution of byte growth to genuine trajectory
divergence rather than hidden re-serialization of history.

The recorder is disabled by default so deterministic qualification remains
byte-identical.  When enabled, evidence integrity fails closed: a missing
output path aborts the call instead of silently losing provenance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ENV_ENABLED = "AETHER_REQUEST_ANATOMY"
ENV_PATH = "AETHER_REQUEST_ANATOMY_PATH"

SCHEMA = "aether.request_anatomy.v1"

_TRUE = {"1", "true", "yes", "on"}


def enabled() -> bool:
    return os.environ.get(ENV_ENABLED, "").strip().lower() in _TRUE


def _digest(value: Any) -> dict[str, Any]:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str,
        ).encode("utf-8")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


_COVERED_PLANES = frozenset({
    "instructions", "input", "reasoning", "tools", "tool_choice",
    "max_output_tokens", "previous_response_id", "store",
})


def observe_request(
    *,
    role: str,
    request: Mapping[str, Any],
    turn_index: int | None = None,
    run_id: str = "",
    task_id: str = "",
    call_id: str = "",
) -> None:
    """Append one anatomy row for ``request`` when instrumentation is enabled.

    ``run_id``/``task_id``/``call_id`` are opaque correlation strings supplied
    by the call site (they never enter the provider payload)."""

    if not enabled():
        return
    out_path = os.environ.get(ENV_PATH, "").strip()
    if not out_path:
        raise RuntimeError(
            "AETHER_REQUEST_ANATOMY is enabled but AETHER_REQUEST_ANATOMY_PATH is not set"
        )
    input_items = request.get("input")
    residual = {k: v for k, v in request.items() if k not in _COVERED_PLANES}
    row: dict[str, Any] = {
        "schema_version": SCHEMA,
        "role": role,
        "run_id": run_id,
        "task_id": task_id,
        "call_id": call_id,
        "turn_index": turn_index,
        "residual_request_keys": sorted(residual),
        "planes": {
            "instructions": _digest(request.get("instructions")),
            "input": _digest(input_items),
            "reasoning": _digest(request.get("reasoning")),
            "tools": _digest(request.get("tools")),
            "tool_choice": _digest(request.get("tool_choice")),
            "max_output_tokens": _digest(request.get("max_output_tokens")),
            # Whole-request completeness law: every model-facing key outside the
            # named planes is bound here, so an unhashed treatment channel can
            # never hide inside "some other field".
            "residual": _digest(residual),
        },
        "continuity": {
            "previous_response_id_present": bool(request.get("previous_response_id")),
            "previous_response_id_digest16": hashlib.sha256(
                str(request.get("previous_response_id") or "").encode("utf-8"),
            ).hexdigest()[:16],
            "store": request.get("store"),
        },
    }
    if isinstance(input_items, list):
        row["input_item_digests"] = [_digest(item) for item in input_items]
    line = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    parent = Path(out_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
