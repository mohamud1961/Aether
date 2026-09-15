"""Lossless transport deltas for provider-native PERSISTENT continuity experiments.

This module deliberately does *not* choose or compact the model-visible PERSISTENT
projection.  Callers first build the existing projection (for the audited V3
experiment, production ``continuity_fresh_delta_v1``), then may encode that
snapshot either in full or as a top-level set/clear delta against the previous
snapshot.

The separation is the causal contract: snapshot representation and delta
transport are distinct treatments.  Reconstructing an accepted delta must
produce exactly the same Python/JSON value as sending the current snapshot in
full.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping


SCHEMA = "aether.persistent_reality_delta_transport.v1"
FULL_MODE = "full_snapshot_v1"
DELTA_MODE = "delta_only_v1"
REPRESENTATION_CONTRACT = (
    "Start from the previous projected snapshot; replace or add top-level keys in set; "
    "remove top-level keys in clear; keys in omitted_unchanged_top_level_keys are unchanged."
)


def _snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("PERSISTENT reality snapshot must be a mapping")
    result = {str(key): deepcopy(item) for key, item in value.items()}
    if len(result) != len(value):
        raise ValueError("PERSISTENT reality snapshot keys must have unique string identities")
    return result


def snapshot_sha256(value: Mapping[str, Any]) -> str:
    """Return the canonical JSON identity of one projected PERSISTENT snapshot."""
    raw = json.dumps(
        _snapshot(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def full_snapshot_envelope(current: Mapping[str, Any]) -> dict[str, Any]:
    """Encode one full projected snapshot for first-turn/re-anchor transport."""
    snapshot = _snapshot(current)
    return {
        "schema": SCHEMA,
        "mode": FULL_MODE,
        "representation_contract": REPRESENTATION_CONTRACT,
        "base_snapshot_sha256": None,
        "result_snapshot_sha256": snapshot_sha256(snapshot),
        "set": snapshot,
        "clear": [],
        "omitted_unchanged_top_level_keys": [],
    }


def delta_snapshot_envelope(
    previous: Mapping[str, Any], current: Mapping[str, Any],
) -> dict[str, Any]:
    """Encode only changed/deleted top-level sections of the current snapshot.

    A changed section is sent in full.  This intentionally avoids a second
    semantic/representation treatment inside nested PERSISTENT structures.  Unchanged
    sections are omitted and named explicitly; deleted sections use ``clear``.
    """
    before = _snapshot(previous)
    after = _snapshot(current)
    set_values = {
        key: deepcopy(after[key])
        for key in sorted(after)
        if key not in before or before[key] != after[key]
    }
    clear = sorted(key for key in before if key not in after)
    omitted = sorted(
        key for key in after
        if key in before and before[key] == after[key]
    )
    return {
        "schema": SCHEMA,
        "mode": DELTA_MODE,
        "representation_contract": REPRESENTATION_CONTRACT,
        "base_snapshot_sha256": snapshot_sha256(before),
        "result_snapshot_sha256": snapshot_sha256(after),
        "set": set_values,
        "clear": clear,
        "omitted_unchanged_top_level_keys": omitted,
    }


def transport_envelope(
    current: Mapping[str, Any], *, previous: Mapping[str, Any] | None,
    force_full: bool = False,
) -> dict[str, Any]:
    """Select full transport for first/re-anchor turns, otherwise delta-only."""
    if previous is None or force_full:
        return full_snapshot_envelope(current)
    return delta_snapshot_envelope(previous, current)


def reconstruct_snapshot(
    previous: Mapping[str, Any] | None, envelope: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless an envelope reconstructs its exact bound snapshot."""
    if not isinstance(envelope, Mapping):
        raise TypeError("PERSISTENT reality delta envelope must be a mapping")
    allowed = {
        "schema", "mode", "representation_contract", "base_snapshot_sha256",
        "result_snapshot_sha256", "set", "clear",
        "omitted_unchanged_top_level_keys",
    }
    if set(envelope) != allowed:
        raise ValueError("PERSISTENT reality delta envelope shape mismatch")
    if envelope.get("schema") != SCHEMA:
        raise ValueError("PERSISTENT reality delta schema mismatch")
    if envelope.get("representation_contract") != REPRESENTATION_CONTRACT:
        raise ValueError("PERSISTENT reality delta representation contract mismatch")

    mode = str(envelope.get("mode") or "")
    raw_set = envelope.get("set")
    raw_clear = envelope.get("clear")
    raw_omitted = envelope.get("omitted_unchanged_top_level_keys")
    if not isinstance(raw_set, Mapping):
        raise ValueError("PERSISTENT reality delta set must be a mapping")
    set_values = _snapshot(raw_set)
    if not isinstance(raw_clear, list) or any(not isinstance(key, str) for key in raw_clear):
        raise ValueError("PERSISTENT reality delta clear must be a string list")
    if not isinstance(raw_omitted, list) or any(not isinstance(key, str) for key in raw_omitted):
        raise ValueError("PERSISTENT reality delta omitted keys must be a string list")
    clear = list(raw_clear)
    omitted = list(raw_omitted)
    if clear != sorted(set(clear)) or omitted != sorted(set(omitted)):
        raise ValueError("PERSISTENT reality delta key lists must be sorted and unique")
    if set(set_values) & set(clear):
        raise ValueError("PERSISTENT reality delta cannot both set and clear one key")
    if (set(set_values) | set(clear)) & set(omitted):
        raise ValueError("PERSISTENT reality delta omitted keys cannot be transmitted changes")

    expected_result_hash = str(envelope.get("result_snapshot_sha256") or "").lower()
    if len(expected_result_hash) != 64 or any(ch not in "0123456789abcdef" for ch in expected_result_hash):
        raise ValueError("PERSISTENT reality delta result hash is invalid")

    if mode == FULL_MODE:
        if previous is not None and envelope.get("base_snapshot_sha256") not in (None, ""):
            raise ValueError("full PERSISTENT reality snapshot must not bind a delta base")
        if clear or omitted:
            raise ValueError("full PERSISTENT reality snapshot cannot contain clear/omitted keys")
        result = deepcopy(set_values)
    elif mode == DELTA_MODE:
        if previous is None:
            raise ValueError("delta-only PERSISTENT reality transport requires a previous snapshot")
        before = _snapshot(previous)
        expected_base_hash = str(envelope.get("base_snapshot_sha256") or "").lower()
        if expected_base_hash != snapshot_sha256(before):
            raise ValueError("PERSISTENT reality delta base snapshot mismatch")
        if any(key not in before for key in clear):
            raise ValueError("PERSISTENT reality delta clears a key absent from its base")
        if any(key not in before for key in omitted):
            raise ValueError("PERSISTENT reality delta omits a key absent from its base")
        result = deepcopy(before)
        for key in clear:
            result.pop(key)
        result.update(deepcopy(set_values))
        actual_omitted = sorted(
            key for key in result
            if key in before and key not in set_values and before[key] == result[key]
        )
        if actual_omitted != omitted:
            raise ValueError("PERSISTENT reality delta omitted-key accounting mismatch")
    else:
        raise ValueError(f"unsupported PERSISTENT reality delta mode: {mode}")

    if snapshot_sha256(result) != expected_result_hash:
        raise ValueError("PERSISTENT reality delta result snapshot hash mismatch")
    return result


__all__ = [
    "DELTA_MODE", "FULL_MODE", "REPRESENTATION_CONTRACT", "SCHEMA",
    "delta_snapshot_envelope", "full_snapshot_envelope", "reconstruct_snapshot",
    "snapshot_sha256", "transport_envelope",
]
