"""Same-Primary native image observation staging for Aether-Next.

This module owns no semantic interpretation. It binds an already-identified
artifact to exact bytes, then asks the persistent Primary provider adapter to
stage those bytes for the *next* causal function-call-output boundary.

The ledger stores hashes/path/media metadata only. Raw image bytes remain in
executor/provider task-scoped memory and are never converted into a textual
caption by this route. A separate vision callable may remain as compatibility
or independent-Verifier fallback when the Primary native route is unavailable.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .ledger import Receipt


SUPPORTED_NATIVE_IMAGE_MEDIA = frozenset({
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
})
# Conservative transport bound inherited from the already-qualified vision
# lane. Larger artifacts can be transformed/downscaled through ordinary
# provenance-bound run_command before native inspection.
MAX_NATIVE_IMAGE_BYTES = 8_000_000


def _artifact_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return {}
    identity = metadata.get("artifact_identity")
    return dict(identity) if isinstance(identity, Mapping) else {}


def stage_same_primary_native_image(
    kernel: Any,
    action: Any,
    step: int,
    executor: Any,
    base_receipt: Receipt,
) -> Receipt | None:
    """Stage one exact supported image for the next persistent Primary turn.

    ``None`` means this route is not applicable/available and lets the caller
    use its existing compatibility fallback. A returned Receipt is terminal for
    this inspection attempt: either exact native staging succeeded or a
    custody/size failure was observed and must not be hidden by another route.
    """
    hooks = getattr(kernel, "active_hooks", None)
    stage = getattr(hooks, "stage_primary_native_image_observation", None)
    if not callable(stage):
        return None

    payload = dict(base_receipt.payload or {})
    identity = _artifact_identity(payload)
    media_type = str(identity.get("media_type") or "").strip().lower()
    if media_type not in SUPPORTED_NATIVE_IMAGE_MEDIA:
        return None
    path = str(identity.get("path") or payload.get("path") or "").strip()
    expected_sha = str(identity.get("sha256") or "").strip().lower()
    expected_bytes = identity.get("bytes")
    if not path or len(expected_sha) != 64:
        return Receipt(
            receipt_id=base_receipt.receipt_id + ":native_primary",
            step=step,
            kind="artifact_inspection",
            success=False,
            summary="native Primary image staging rejected incomplete artifact identity",
            failure_class="perception_required",
            payload={**payload, "native_primary_perception_status": "identity_incomplete"},
        )

    read_bytes = getattr(executor, "read_file_bytes", None)
    if not callable(read_bytes):
        return None
    try:
        raw = bytes(read_bytes(path))
    except Exception as exc:  # noqa: BLE001 - truthful executor failure
        return Receipt(
            receipt_id=base_receipt.receipt_id + ":native_primary",
            step=step,
            kind="artifact_inspection",
            success=False,
            summary=f"native Primary image staging could not read exact artifact {path}",
            failure_class="perception_required",
            payload={
                **payload,
                "native_primary_perception_status": "source_read_failed",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
            },
        )
    observed_sha = sha256(raw).hexdigest()
    if observed_sha != expected_sha or (
        expected_bytes is not None and int(expected_bytes) != len(raw)
    ):
        return Receipt(
            receipt_id=base_receipt.receipt_id + ":native_primary",
            step=step,
            kind="artifact_inspection",
            success=False,
            summary=f"native Primary image staging rejected artifact identity drift for {path}",
            failure_class="integrity_violation",
            payload={
                **payload,
                "native_primary_perception_status": "identity_mismatch",
                "expected_sha256": expected_sha,
                "observed_sha256": observed_sha,
                "expected_bytes": expected_bytes,
                "observed_bytes": len(raw),
            },
        )
    if len(raw) > MAX_NATIVE_IMAGE_BYTES:
        return Receipt(
            receipt_id=base_receipt.receipt_id + ":native_primary",
            step=step,
            kind="artifact_inspection",
            success=False,
            summary=(
                f"native Primary image staging skipped {path}: {len(raw)} bytes exceeds "
                f"the {MAX_NATIVE_IMAGE_BYTES}-byte transport bound; derive a smaller exact view first"
            ),
            failure_class="perception_required",
            payload={
                **payload,
                "native_primary_perception_status": "artifact_too_large",
                "native_primary_transport_max_bytes": MAX_NATIVE_IMAGE_BYTES,
            },
        )

    try:
        accepted = bool(stage(
            image_bytes=raw,
            media_type=media_type,
            artifact_sha256=expected_sha,
            artifact_path=path,
            source_receipt_id=base_receipt.receipt_id,
        ))
    except Exception as exc:  # noqa: BLE001 - staging is a harness boundary
        return Receipt(
            receipt_id=base_receipt.receipt_id + ":native_primary",
            step=step,
            kind="artifact_inspection",
            success=False,
            summary=f"same-Primary native image staging failed for {path}: {type(exc).__name__}: {exc}",
            failure_class="perception_required",
            payload={
                **payload,
                "native_primary_perception_status": "staging_failed",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
            },
        )
    if not accepted:
        return None

    metadata = dict(payload.get("metadata") or {})
    metadata.update({
        "semantic_content_available": True,
        "semantic_content_status": "exact_image_staged_for_same_primary_native_input",
        "native_primary_perception": True,
    })
    payload.update({
        "metadata": metadata,
        "extracted_text": "",
        "extraction_route": "same_primary_native_image",
        "extraction_authority": "exact_pixels_no_textual_intermediary",
        "native_primary_perception_status": "staged",
        "native_primary_artifact_sha256": expected_sha,
        "native_primary_artifact_bytes": len(raw),
        "native_primary_media_type": media_type,
        "native_primary_raw_bytes_persisted_in_receipt": False,
    })
    # Raw bytes are deliberately absent from this receipt. The exact artifact
    # identity plus executor custody is the durable reality authority.
    return Receipt(
        receipt_id=base_receipt.receipt_id + ":native_primary",
        step=step,
        kind="artifact_inspection",
        success=True,
        summary=f"staged exact {media_type} artifact {path} for same-Primary native perception",
        state_change=False,
        payload=payload,
    )


__all__ = [
    "SUPPORTED_NATIVE_IMAGE_MEDIA",
    "MAX_NATIVE_IMAGE_BYTES",
    "stage_same_primary_native_image",
]
