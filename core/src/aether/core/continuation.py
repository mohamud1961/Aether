"""Continuation runs: supplied seed files in, an appended message, the final deliverables captured out.

Gate 1 of the repair pilot. Off by default; every setting comes from the launcher's environment:
- ``AETHER_CORE_SEED_DIR``: host directory whose regular files are uploaded to ``<workdir>/<relative path>``
  and read back with ``sha256sum`` before the run starts. A failed upload or a readback that differs from the
  host file stops the run: never continue on a wrong seed.
- ``AETHER_CORE_CONTINUE_FILE``: host UTF-8 text appended to the task instruction as
  ``instruction + "\\n\\n" + text``. ``AETHER_CORE_FEEDBACK_FILE`` (optional) is appended after it the same way,
  and needs a continuation file.
- ``AETHER_CORE_CAPTURE``: comma-separated container paths (absolute, or relative to the workdir). Each is
  downloaded under ``<logs_dir>/continuation/capture/`` after the run, whatever its outcome, with a manifest
  recording ``captured``/``missing``/``error``. Capture problems are recorded, never raised: they must not
  mask the run's own outcome.

With none of the three set, nothing is written and no sandbox command is run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import posixpath
import shlex
from typing import Any, Mapping

from .env import exit_code

SEED_ENV = "AETHER_CORE_SEED_DIR"
CONTINUE_ENV = "AETHER_CORE_CONTINUE_FILE"
FEEDBACK_ENV = "AETHER_CORE_FEEDBACK_FILE"
CAPTURE_ENV = "AETHER_CORE_CAPTURE"
SUBDIR = "continuation"
EXEC_TIMEOUT_S = 120
_MISSING_MARKERS = ("no such file", "does not exist", "not found")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


async def _create_parents(environment: Any, remote: str) -> None:
    parent = posixpath.dirname(remote) or "/"
    created = await environment.exec(
        command=f"mkdir -p {shlex.quote(parent)}",
        cwd=None,
        env=None,
        timeout_sec=EXEC_TIMEOUT_S,
    )
    if exit_code(created) != 0:
        detail = str(getattr(created, "stderr", "") or "").strip()[:300]
        raise RuntimeError(f"seed: cannot create {parent!r} in the container: {detail}")


async def _seed(environment: Any, seed_dir: Path, workdir: str, out: Path) -> None:
    if not seed_dir.is_dir():
        raise RuntimeError(f"{SEED_ENV}={str(seed_dir)!r} is not a directory")
    rows = []
    for local in sorted(p for p in seed_dir.rglob("*") if p.is_file()):
        relative = local.relative_to(seed_dir).as_posix()
        remote = posixpath.normpath(posixpath.join(workdir, relative))
        data = local.read_bytes()
        await _create_parents(environment, remote)
        try:
            await environment.upload_file(local, remote)
        except Exception as exc:  # noqa: BLE001 - any upload failure stops the run, with its cause
            raise RuntimeError(
                f"seed: upload of {relative!r} to {remote!r} failed: {type(exc).__name__}: {exc}"
            ) from exc
        readback = await environment.exec(
            command=f"sha256sum {shlex.quote(remote)}",
            cwd=None,
            env=None,
            timeout_sec=EXEC_TIMEOUT_S,
        )
        fields = str(getattr(readback, "stdout", "") or "").split()
        if exit_code(readback) != 0 or not fields:
            detail = str(getattr(readback, "stderr", "") or "").strip()[:300]
            raise RuntimeError(f"seed: readback of {relative!r} at {remote!r} failed: {detail}")
        expected = sha256(data)
        if fields[0] != expected:
            raise RuntimeError(
                f"seed: readback of {relative!r} at {remote!r} differs from the host file "
                f"({fields[0]} != {expected})"
            )
        rows.append({"path": remote, "sha256": expected, "bytes": len(data)})
    _write(out / "seed_manifest.json", rows)


def _message(instruction: str, continue_file: Path, feedback_file: Path | None, out: Path) -> str:
    text, recorded = instruction, {"continue": None, "feedback": None}
    for key, path in (("continue", continue_file), ("feedback", feedback_file)):
        if path is None:
            continue
        try:
            data = path.read_bytes()
            body = data.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"{key} file {str(path)!r} is not readable UTF-8 text: {exc}") from exc
        recorded[key] = {"path": str(path), "sha256": sha256(data), "chars": len(body)}
        text = text + "\n\n" + body
    _write(
        out / "message_manifest.json",
        {"instruction_sha256": sha256(text.encode("utf-8")), **recorded},
    )
    return text


def _capture_target(requested: str, workdir: str) -> tuple[str, str]:
    """The container path to download and its safe path under the capture directory."""
    remote = (
        posixpath.normpath(requested)
        if posixpath.isabs(requested)
        else posixpath.normpath(posixpath.join(workdir, requested))
    )
    relative = posixpath.relpath(remote, workdir)
    if relative == ".." or relative.startswith("../"):
        relative = remote.lstrip("/") or posixpath.basename(remote)
    return remote, relative


async def begin(
    environment: Any,
    environ: Mapping[str, str],
    logs: Path,
    instruction: str,
    workdir: str,
) -> tuple[str, list[tuple[str, str]] | None]:
    """Seed the container and/or append the continuation message; the instruction and capture plan."""
    seed = (environ.get(SEED_ENV) or "").strip()
    continue_file = (environ.get(CONTINUE_ENV) or "").strip()
    feedback_file = (environ.get(FEEDBACK_ENV) or "").strip()
    requested = [p.strip() for p in (environ.get(CAPTURE_ENV) or "").split(",") if p.strip()]
    if feedback_file and not continue_file:
        raise ValueError(f"{FEEDBACK_ENV} needs {CONTINUE_ENV}")
    if not (seed or continue_file or requested):
        return instruction, None
    out = Path(logs) / SUBDIR
    out.mkdir(parents=True, exist_ok=True)
    if seed:
        await _seed(environment, Path(seed), workdir, out)
    if continue_file:
        instruction = _message(
            instruction,
            Path(continue_file),
            Path(feedback_file) if feedback_file else None,
            out,
        )
    capture = [_capture_target(path, workdir) for path in requested] or None
    return instruction, capture


def _missing(exc: Exception) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    text = str(exc).lower()
    return any(marker in text for marker in _MISSING_MARKERS)


async def finish(environment: Any, logs: Path, capture: list[tuple[str, str]] | None) -> None:
    """Download the capture list and record it; never raises, so it cannot mask the run's outcome."""
    if not capture:
        return
    out = Path(logs) / SUBDIR / "capture"
    rows = []
    for remote, relative in capture:
        target = out / relative
        row = {"path": remote, "status": "error", "sha256": None, "bytes": None, "error": None}
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            await environment.download_file(remote, target)
            data = target.read_bytes()
            row.update(status="captured", sha256=sha256(data), bytes=len(data))
        except Exception as exc:  # noqa: BLE001 - recorded, never raised
            row["status"] = "missing" if _missing(exc) else "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    try:
        _write(Path(logs) / SUBDIR / "capture_manifest.json", rows)
    except OSError:
        pass  # the run's outcome remains authoritative; an unwritable log dir is already a trial error
