from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PathSandboxError(ValueError):
    reason_code: str

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        object.__setattr__(self, "reason_code", reason_code)


def resolve_sandboxed_path(workspace_root: Path, requested_path: Path) -> Path:
    return resolve_sandboxed_path_for_op(
        workspace_root,
        requested_path,
        for_write=False,
        artifact_store_root=None,
    )


def resolve_sandboxed_path_for_op(
    workspace_root: Path,
    requested_path: Path,
    *,
    for_write: bool,
    artifact_store_root: Optional[Path],
) -> Path:
    try:
        root = workspace_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathSandboxError("root_missing", f"Workspace root does not exist: {workspace_root}") from exc
    if not root.exists():
        raise PathSandboxError("root_missing", f"Workspace root does not exist: {root}")

    if requested_path.is_absolute():
        candidate = requested_path
        reason_code = "absolute_outside_root"
    else:
        candidate = root / requested_path
        reason_code = "relative_escape"

    resolved = candidate.resolve(strict=False)

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathSandboxError(reason_code, "Requested path escapes workspace root") from exc

    if for_write and artifact_store_root is not None:
        artifact_root = artifact_store_root.resolve(strict=False)
        try:
            resolved.relative_to(artifact_root)
        except ValueError:
            pass
        else:
            raise PathSandboxError(
                "PATH_SANDBOX_VIOLATION",
                "Writes to artifact store are denied",
            )

    return resolved
