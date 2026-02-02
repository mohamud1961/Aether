from __future__ import annotations

from pathlib import Path


class CanonicalWorkdirError(ValueError):
    pass


def canonicalize_cwd(workspace_root: Path, requested_cwd: Path) -> Path:
    root = workspace_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Workspace root does not exist: {root}")

    if requested_cwd.is_absolute():
        candidate = requested_cwd
    else:
        candidate = root / requested_cwd

    resolved = candidate.resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CanonicalWorkdirError("Requested cwd is outside workspace root") from exc

    return resolved
