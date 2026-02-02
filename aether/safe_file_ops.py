from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .hashing import sha256_hex
from .path_sandbox import resolve_sandboxed_path_for_op


@dataclass(frozen=True)
class SafeFileOpResult:
    resolved_path: Path
    files_read: List[str]
    files_written: List[str]
    observed_preimage_hashes: Dict[str, str] = field(default_factory=dict)


class PreimageMismatchError(RuntimeError):
    def __init__(self, *, path: str, expected_hash: str, observed_hash: str) -> None:
        self.path = path
        self.expected_hash = expected_hash
        self.observed_hash = observed_hash
        super().__init__(
            f"preimage_hash_mismatch path={path} expected={expected_hash} observed={observed_hash}"
        )


class SafeFileOps:
    def __init__(
        self,
        workspace_root: Path,
        *,
        enabled: bool = True,
        artifact_store_root: Optional[Path] = None,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.enabled = enabled
        self.artifact_store_root = artifact_store_root.resolve() if artifact_store_root else None

    def prepare_read(self, requested_path: Path) -> SafeFileOpResult:
        resolved = self._resolve_path(requested_path)
        if not resolved.exists():
            raise FileNotFoundError(f"Missing file: {resolved}")
        data = resolved.read_bytes()
        rel_path = self._format_path(resolved)
        files_read = [rel_path]
        return SafeFileOpResult(
            resolved_path=resolved,
            files_read=files_read,
            files_written=[],
            observed_preimage_hashes={rel_path: sha256_hex(data)},
        )

    def prepare_write(
        self,
        requested_path: Path,
        *,
        expected_preimage_hash: Optional[str] = None,
    ) -> SafeFileOpResult:
        resolved = self.resolve_write_path(requested_path)
        files_read: List[str] = []
        preimage_hashes: Dict[str, str] = {}
        if self.enabled and resolved.exists():
            data = resolved.read_bytes()
            rel_path = self._format_path(resolved)
            observed_hash = sha256_hex(data)
            preimage_hashes[rel_path] = observed_hash
            files_read.append(rel_path)

            if expected_preimage_hash is not None and expected_preimage_hash != observed_hash:
                raise PreimageMismatchError(
                    path=rel_path,
                    expected_hash=expected_preimage_hash,
                    observed_hash=observed_hash,
                )

        files_written = [self._format_path(resolved)]
        return SafeFileOpResult(
            resolved_path=resolved,
            files_read=files_read,
            files_written=files_written,
            observed_preimage_hashes=preimage_hashes,
        )

    def _resolve_path(self, requested_path: Path) -> Path:
        if self.enabled:
            return resolve_sandboxed_path_for_op(
                self.workspace_root,
                requested_path,
                for_write=False,
                artifact_store_root=self.artifact_store_root,
            )

        if requested_path.is_absolute():
            return requested_path.resolve()
        return (self.workspace_root / requested_path).resolve()

    def _format_path(self, resolved_path: Path) -> str:
        try:
            return resolved_path.relative_to(self.workspace_root).as_posix()
        except ValueError:
            return resolved_path.as_posix()

    def resolve_write_path(self, requested_path: Path) -> Path:
        if self.enabled:
            return resolve_sandboxed_path_for_op(
                self.workspace_root,
                requested_path,
                for_write=True,
                artifact_store_root=self.artifact_store_root,
            )
        if requested_path.is_absolute():
            return requested_path.resolve()
        return (self.workspace_root / requested_path).resolve()
