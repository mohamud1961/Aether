from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator, List

from .hashes import sha256_bytes


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class ArtifactStoreView:
    def __init__(self, artifact_dir: str | Path) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.cas_roots: List[Path] = [
            self.artifact_dir / "cas",
            self.artifact_dir / "artifacts" / "objects",
        ]

    def _validate_hash(self, content_hash: str) -> None:
        if not _HEX_64.match(content_hash):
            raise ValueError(f"Invalid content hash: {content_hash}")

    def _find_path(self, content_hash: str) -> Path:
        self._validate_hash(content_hash)
        for root in self.cas_roots:
            candidate = root / content_hash
            if candidate.exists() and candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"CAS object not found for hash {content_hash} in {', '.join(root.as_posix() for root in self.cas_roots)}"
        )

    def exists(self, content_hash: str) -> bool:
        try:
            self._find_path(content_hash)
            return True
        except Exception:
            return False

    def read_bytes(self, content_hash: str) -> bytes:
        path = self._find_path(content_hash)
        data = path.read_bytes()
        observed_hash = sha256_bytes(data)
        if observed_hash != content_hash:
            raise ValueError(
                f"CAS object hash mismatch for {content_hash}: observed {observed_hash}"
            )
        return data

    def resolve_hash(self, content_hash: str) -> bytes | str:
        data = self.read_bytes(content_hash)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data

    def load_json(self, content_hash: str) -> dict[str, Any]:
        resolved = self.resolve_hash(content_hash)
        if isinstance(resolved, bytes):
            text = resolved.decode("utf-8")
        else:
            text = resolved
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError(f"CAS JSON payload must be an object: {content_hash}")
        return payload

    def iter_hashes(self) -> Iterator[str]:
        seen: set[str] = set()
        for root in self.cas_roots:
            if not root.exists():
                continue
            for path in sorted(root.iterdir(), key=lambda p: p.name):
                if not path.is_file():
                    continue
                if _HEX_64.match(path.name) and path.name not in seen:
                    seen.add(path.name)
                    yield path.name


def open_artifact_store(artifact_dir: str | Path) -> ArtifactStoreView:
    return ArtifactStoreView(artifact_dir)
