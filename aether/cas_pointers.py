from __future__ import annotations

from typing import Any, Dict, Tuple

from .artifact_store import ArtifactStore
from .hashing import hash_canonical_json
from .hashing import sha256_hex


class RehydrationError(ValueError):
    """Raised when CAS rehydration cannot prove exact hash identity."""


def build_pointer_excerpt(
    artifact_store: ArtifactStore,
    artifact_id: str,
    *,
    max_bytes: int = 2048,
) -> Tuple[str, Dict[str, Any]]:
    """
    Build a deterministic excerpt backed by a CAS pointer.
    """
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")

    data = artifact_store.read_bytes(artifact_id)
    excerpt = data[:max_bytes]
    text = excerpt.decode("utf-8", errors="replace")
    pointer = {
        "source_artifact_id": artifact_id,
        "source_hash": sha256_hex(data),
        "span": {"offset": 0, "length": len(excerpt)},
    }
    return text, pointer


def rehydrate(
    artifact_store: ArtifactStore,
    pointer: Dict[str, Any],
) -> bytes:
    source_artifact_id = pointer.get("source_artifact_id")
    source_hash = pointer.get("source_hash")
    if not isinstance(source_artifact_id, str) or not source_artifact_id:
        raise RehydrationError("pointer missing source_artifact_id")
    if not isinstance(source_hash, str) or not source_hash:
        raise RehydrationError("pointer missing source_hash")

    data = artifact_store.read_bytes(source_artifact_id)
    observed_hash = sha256_hex(data)
    if observed_hash != source_hash:
        raise RehydrationError("rehydrated hash mismatch")
    return data


def rehydrate_pointer_bytes(
    artifact_store: ArtifactStore,
    pointer: Dict[str, Any],
) -> bytes:
    span = pointer.get("span")

    if not isinstance(span, dict):
        raise RehydrationError("pointer missing span")

    offset = span.get("offset")
    length = span.get("length")
    if not isinstance(offset, int) or not isinstance(length, int):
        raise RehydrationError("pointer span must contain integer offset/length")
    if offset < 0 or length < 0:
        raise RehydrationError("pointer span values must be non-negative")

    data = rehydrate(artifact_store, pointer)
    if offset + length > len(data):
        raise RehydrationError("pointer span out of range")

    return data[offset : offset + length]


def pointer_excerpt_matches(
    artifact_store: ArtifactStore,
    pointer: Dict[str, Any],
    excerpt_text: str,
) -> bool:
    rehydrated = rehydrate_pointer_bytes(artifact_store, pointer)
    return excerpt_text == rehydrated.decode("utf-8", errors="replace")


def validate_derived_artifact_contract(artifact: Dict[str, Any]) -> None:
    source_artifact_ids = artifact.get("source_artifact_ids")
    span_pointers = artifact.get("span_pointers")
    source_hashes = artifact.get("source_hashes")

    if not isinstance(source_artifact_ids, list) or not source_artifact_ids:
        raise ValueError("derived artifact missing source_artifact_ids[]")
    if not isinstance(span_pointers, list) or not span_pointers:
        raise ValueError("derived artifact missing span_pointers[]")
    if not isinstance(source_hashes, list) or not source_hashes:
        raise ValueError("derived artifact missing source_hashes[]")

    if len(source_artifact_ids) != len(source_hashes):
        raise ValueError("derived artifact contract length mismatch")


def compute_cache_key(
    *,
    source_hashes: list[str],
    policy_hash: str,
    compiler_version: str,
    summarizer_model_id: str,
    summarizer_settings: Dict[str, Any],
) -> str:
    payload = {
        "source_hashes": sorted(str(value) for value in source_hashes),
        "policy_hash": str(policy_hash),
        "compiler_version": str(compiler_version),
        "summarizer_model_id": str(summarizer_model_id),
        "summarizer_settings": dict(summarizer_settings),
    }
    return hash_canonical_json(payload)
