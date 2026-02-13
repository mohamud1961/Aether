import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from .hashing import canonical_json_bytes, sha256_hex


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    size_bytes: int
    content_type: str
    preview_ref: str
    offsets: List[Dict[str, int]]


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects_dir = root / "objects"
        self.metadata_dir = root / "metadata"
        self.previews_dir = root / "previews"
        self.mismatch_log = root / "artifact_mismatch.log"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        data: bytes,
        *,
        content_type: str,
        source_event_id: Optional[str] = None,
        offsets: Optional[List[Dict[str, int]]] = None,
        preview_bytes: int = 128,
    ) -> ArtifactRef:
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("Artifact data must be bytes")

        artifact_id = sha256_hex(data)
        size_bytes = len(data)
        preview_ref = self._write_preview(bytes(data), preview_bytes)
        self._write_blob(self.objects_dir / artifact_id, bytes(data))

        validated_offsets = offsets or []
        self._validate_offsets(validated_offsets, size_bytes)
        metadata = {
            "artifact_id": artifact_id,
            "size_bytes": size_bytes,
            "content_type": content_type,
            "preview_ref": preview_ref,
            "offsets": validated_offsets,
            "source_event_id": source_event_id,
        }
        self._write_metadata(artifact_id, metadata)

        return ArtifactRef(
            artifact_id=artifact_id,
            size_bytes=size_bytes,
            content_type=content_type,
            preview_ref=preview_ref,
            offsets=metadata["offsets"],
        )

    def write_json_canonical(self, payload: Any, *, content_type: str = "application/json") -> tuple[ArtifactRef, str]:
        data = canonical_json_bytes(payload)
        content_hash = sha256_hex(data)
        artifact = self.put_bytes(data, content_type=content_type)
        return artifact, content_hash

    def read_bytes(self, artifact_id: str) -> bytes:
        path = self.objects_dir / artifact_id
        if not path.exists():
            raise FileNotFoundError(f"Missing artifact: {artifact_id}")
        data = path.read_bytes()
        if sha256_hex(data) != artifact_id:
            raise ValueError("Artifact hash mismatch")
        return data

    def get_metadata(self, artifact_id: str) -> Dict[str, Any]:
        path = self.metadata_dir / f"{artifact_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing artifact metadata: {artifact_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def write_manifest(self, path: Path) -> None:
        metadata_files = sorted(self.metadata_dir.glob("*.json"))
        artifacts = [
            json.loads(metadata.read_text(encoding="utf-8"))
            for metadata in metadata_files
        ]
        manifest = {"artifacts": artifacts}
        path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def _write_preview(self, data: bytes, preview_bytes: int) -> str:
        preview = data[:preview_bytes]
        preview_hash = sha256_hex(preview)
        self._write_blob(self.previews_dir / preview_hash, preview)
        return preview_hash

    def _write_blob(self, path: Path, data: bytes) -> None:
        if path.exists():
            existing = path.read_bytes()
            if existing != data:
                self._record_mismatch(path, existing, data)
            return
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_bytes(data)
        tmp_path.replace(path)

    def _record_mismatch(self, path: Path, existing: bytes, data: bytes) -> None:
        timestamp = datetime.utcnow().isoformat() + "Z"
        entry = {
            "timestamp": timestamp,
            "path": str(path),
            "existing_size": len(existing),
            "new_size": len(data),
            "existing_head": existing[:20].hex(),
            "new_head": data[:20].hex(),
        }
        line = json.dumps(entry, sort_keys=True)
        with self.mismatch_log.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _write_metadata(self, artifact_id: str, metadata: Dict[str, Any]) -> None:
        path = self.metadata_dir / f"{artifact_id}.json"
        serialized = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise ValueError("Artifact metadata mismatch")
            return
        path.write_text(serialized, encoding="utf-8")

    def _validate_offsets(self, offsets: List[Dict[str, int]], size_bytes: int) -> None:
        for entry in offsets:
            if not isinstance(entry, dict):
                raise ValueError("Offset entry must be a dict")
            if "offset" not in entry or "length" not in entry:
                raise ValueError("Offset entry missing offset or length")
            offset = entry["offset"]
            length = entry["length"]
            if not isinstance(offset, int) or not isinstance(length, int):
                raise ValueError("Offset values must be integers")
            if offset < 0 or length < 0:
                raise ValueError("Offset values must be non-negative")
            if offset + length > size_bytes:
                raise ValueError("Offset range exceeds artifact size")
