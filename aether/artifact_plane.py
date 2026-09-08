"""Exact artifact identity and deterministic-view provenance for Aether-Next.

The artifact plane owns no semantic interpretation. Original bytes remain
reality authority. Renderings, screenshots, extracted segments, frames and
other derived views are separately content-addressed and bind back to their
source through an explicit transform receipt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import mimetypes
from pathlib import Path
from typing import Any, Mapping


ARTIFACT_IDENTITY_SCHEMA = "aether.artifact_identity.v1"
ARTIFACT_DERIVATION_SCHEMA = "aether.artifact_derivation.v1"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _clean_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return {str(key): value[key] for key in sorted(value or {})}


def _media_type(path: str, explicit: str = "") -> str:
    if explicit:
        return str(explicit).strip().lower()
    guessed, _encoding = mimetypes.guess_type(str(path or ""), strict=False)
    return str(guessed or "application/octet-stream").lower()


@dataclass(frozen=True)
class ArtifactIdentity:
    sha256: str
    bytes: int
    media_type: str
    path: str = ""
    source: str = ""
    generation: str = ""
    schema_version: str = ARTIFACT_IDENTITY_SCHEMA

    @property
    def handle(self) -> str:
        return f"artifact:sha256:{self.sha256}"

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["handle"] = self.handle
        return row


@dataclass(frozen=True)
class ArtifactDerivation:
    source: ArtifactIdentity
    derivative: ArtifactIdentity
    transform: str
    transform_version: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    generation: str = ""
    captured_at: str = ""
    schema_version: str = ARTIFACT_DERIVATION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _clean_mapping(self.parameters))

    @property
    def identity(self) -> str:
        payload = {
            "source_sha256": self.source.sha256,
            "derivative_sha256": self.derivative.sha256,
            "transform": self.transform,
            "transform_version": self.transform_version,
            "parameters": dict(self.parameters),
            "generation": self.generation,
            "captured_at": self.captured_at,
        }
        return sha256(_stable_json(payload).encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "derivation_sha256": self.identity,
            "source": self.source.as_dict(),
            "derivative": self.derivative.as_dict(),
            "transform": self.transform,
            "transform_version": self.transform_version,
            "parameters": dict(self.parameters),
            "generation": self.generation,
            "captured_at": self.captured_at,
        }


def identify_bytes(
    data: bytes,
    *,
    path: str = "",
    media_type: str = "",
    source: str = "",
    generation: str = "",
) -> ArtifactIdentity:
    raw = bytes(data)
    return ArtifactIdentity(
        sha256=sha256(raw).hexdigest(),
        bytes=len(raw),
        media_type=_media_type(path, media_type),
        path=str(path or ""),
        source=str(source or ""),
        generation=str(generation or ""),
    )


def identify_file(
    path: str | Path,
    *,
    logical_path: str = "",
    media_type: str = "",
    source: str = "filesystem",
    generation: str = "",
) -> ArtifactIdentity:
    file_path = Path(path)
    h = sha256()
    total = 0
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            total += len(chunk)
    display_path = str(logical_path or file_path)
    return ArtifactIdentity(
        sha256=h.hexdigest(),
        bytes=total,
        media_type=_media_type(display_path, media_type),
        path=display_path,
        source=str(source or ""),
        generation=str(generation or ""),
    )


def derive_bytes(
    source_identity: ArtifactIdentity,
    derivative_bytes: bytes,
    *,
    derivative_path: str = "",
    derivative_media_type: str = "",
    transform: str,
    transform_version: str,
    parameters: Mapping[str, Any] | None = None,
    generation: str = "",
    captured_at: str = "",
    source: str = "aether:deterministic_transform",
) -> ArtifactDerivation:
    derivative = identify_bytes(
        derivative_bytes,
        path=derivative_path,
        media_type=derivative_media_type,
        source=source,
        generation=generation,
    )
    return ArtifactDerivation(
        source=source_identity,
        derivative=derivative,
        transform=str(transform),
        transform_version=str(transform_version),
        parameters=_clean_mapping(parameters),
        generation=str(generation or ""),
        captured_at=str(captured_at or ""),
    )


def exact_capture(
    captured_bytes: bytes,
    *,
    surface: str,
    media_type: str = "image/png",
    dimensions: tuple[int, int] | None = None,
    region: Mapping[str, Any] | None = None,
    capture_backend: str,
    capture_backend_version: str,
    generation: str = "",
    captured_at: str | None = None,
) -> ArtifactDerivation:
    """Record one exact visual capture without claiming repeatable pixels.

    A screenshot is a derivative of a named live surface state rather than a
    deterministic transform of static file bytes. The synthetic source identity
    binds the authorized surface and generation; the captured pixels themselves
    remain content-addressed exactly.
    """
    timestamp = captured_at or datetime.now(timezone.utc).isoformat()
    surface_payload = _stable_json({
        "surface": str(surface),
        "generation": str(generation or ""),
    }).encode("utf-8")
    source_identity = identify_bytes(
        surface_payload,
        path=f"surface:{surface}",
        media_type="application/x-aether-live-surface",
        source="aether:authorized_live_surface",
        generation=generation,
    )
    params: dict[str, Any] = {"surface": str(surface)}
    if dimensions is not None:
        params["dimensions"] = [int(dimensions[0]), int(dimensions[1])]
    if region:
        params["region"] = _clean_mapping(region)
    return derive_bytes(
        source_identity,
        captured_bytes,
        derivative_path=f"screenshot:{surface}",
        derivative_media_type=media_type,
        transform="exact_screen_capture",
        transform_version=f"{capture_backend}:{capture_backend_version}",
        parameters=params,
        generation=generation,
        captured_at=timestamp,
        source="aether:screen_capture",
    )


__all__ = [
    "ARTIFACT_IDENTITY_SCHEMA",
    "ARTIFACT_DERIVATION_SCHEMA",
    "ArtifactIdentity",
    "ArtifactDerivation",
    "identify_bytes",
    "identify_file",
    "derive_bytes",
    "exact_capture",
]
