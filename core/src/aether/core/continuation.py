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
  recording ``captured``/``unstable``/``missing``/``timeout``/``error``. Paths inside the workdir land in
  ``capture/work/<relative path>``; any other absolute path lands in ``capture/abs/<path without the leading
  slash>``, so ``/etc/result.txt`` and ``etc/result.txt`` cannot collide. A ``..`` escape is refused before any
  seed or message work, and two requests that resolve to the same container path are captured once.
- ``AETHER_CORE_CAPTURE_TIMEOUT_S``: seconds allowed per container call made by capture (default 120). Every
  ``sha256sum`` and ``download_file`` is bounded; a timed-out file is recorded as ``timeout``. The manifest is
  rewritten after every file, so a killed run still has the rows finished so far.

Each captured file is hashed in the container before and after its download. Its status is ``captured`` only when
both container hashes equal the downloaded bytes' hash; otherwise it is ``unstable`` and all three hashes are
recorded. No process is ever stopped for capture. If seeding or the message step raises inside ``begin``, ``begin``
captures anyway and records the failure as ``begin_error`` before re-raising it unchanged. Capture problems are
recorded, never raised: they must not mask the run's own outcome.

With none of the continuation settings set, nothing is written and no sandbox command is run.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import posixpath
import shlex
from typing import Any, Mapping

from .env import exit_code

SEED_ENV = "AETHER_CORE_SEED_DIR"
CONTINUE_ENV = "AETHER_CORE_CONTINUE_FILE"
FEEDBACK_ENV = "AETHER_CORE_FEEDBACK_FILE"
CAPTURE_ENV = "AETHER_CORE_CAPTURE"
CAPTURE_TIMEOUT_ENV = "AETHER_CORE_CAPTURE_TIMEOUT_S"
CAPTURE_TIMEOUT_S = 120.0
SUBDIR = "continuation"
EXEC_TIMEOUT_S = 120
_MISSING_MARKERS = ("no such file", "does not exist", "not found")


@dataclass(frozen=True)
class Capture:
    """The capture plan: (container path, path under the capture directory) and the per-call timeout."""

    targets: tuple[tuple[str, str], ...]
    timeout_s: float


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


def _capture_timeout(environ: Mapping[str, str]) -> float:
    raw = (environ.get(CAPTURE_TIMEOUT_ENV) or "").strip()
    if not raw:
        return CAPTURE_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{CAPTURE_TIMEOUT_ENV} must be a positive number of seconds, got {raw!r}")
    return value


def _capture_target(requested: str, workdir: str) -> tuple[str, str]:
    """The container path to download and its safe path under the capture directory."""
    base = posixpath.normpath(workdir)
    remote = posixpath.normpath(
        requested if posixpath.isabs(requested) else posixpath.join(base, requested)
    )
    relative = posixpath.relpath(remote, base)
    if relative == ".." or relative.startswith("../"):
        if not posixpath.isabs(requested):
            raise ValueError(f"{CAPTURE_ENV}: {requested!r} escapes the workdir {base!r}")
        local = "abs/" + remote.lstrip("/")
    else:
        local = "work/" + relative
    parts = local.split("/")
    if not parts[-1] or "." in parts or ".." in parts:
        raise ValueError(f"{CAPTURE_ENV}: {requested!r} does not name a file to capture")
    return remote, local


def _capture_plan(requested: list[str], workdir: str, timeout_s: float) -> Capture:
    targets, seen = [], set()
    for path in requested:
        remote, local = _capture_target(path, workdir)
        if remote in seen:  # two requests for one container file are captured once
            continue
        seen.add(remote)
        targets.append((remote, local))
    return Capture(tuple(targets), timeout_s)


async def _container_sha256(environment: Any, remote: str, timeout_s: float) -> str:
    """The container's own hash of ``remote``; a missing file raises ``FileNotFoundError``."""
    command = f"sha256sum {shlex.quote(remote)}"
    result = await asyncio.wait_for(
        environment.exec(
            command=command, cwd=None, env=None, timeout_sec=max(1, math.ceil(timeout_s))
        ),
        timeout_s,
    )
    fields = str(getattr(result, "stdout", "") or "").split()
    if exit_code(result) != 0 or not fields:
        detail = str(getattr(result, "stderr", "") or "").strip()[:300]
        message = f"sha256sum {remote}: {detail}"
        if any(marker in detail.lower() for marker in _MISSING_MARKERS):
            raise FileNotFoundError(message)
        raise OSError(message)
    return fields[0]


def _missing(exc: Exception) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    text = str(exc).lower()
    return any(marker in text for marker in _MISSING_MARKERS)


def _discard(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass  # a leftover partial file must not turn a recorded outcome into a raised one


async def _capture_file(
    environment: Any, out: Path, remote: str, relative: str, timeout_s: float
) -> dict[str, Any]:
    """One manifest row: download bounded, and stable only if both container hashes match the bytes."""
    target = out / relative
    row: dict[str, Any] = {
        "path": remote,
        "status": "error",
        "sha256": None,
        "bytes": None,
        "error": None,
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        try:
            before = await _container_sha256(environment, remote, timeout_s)
        except FileNotFoundError:
            before = None  # the download below reports a missing path; capture it as one
        await asyncio.wait_for(environment.download_file(remote, target), timeout_s)
        data = target.read_bytes()
        digest = sha256(data)
        row.update(sha256=digest, bytes=len(data))
        try:
            after = await _container_sha256(environment, remote, timeout_s)
        except FileNotFoundError:
            after = None
        if before is not None and before == digest == after:
            row["status"] = "captured"
        else:
            row["status"] = "unstable"
            row.update(sha256_before=before, sha256_after=after)
            row["error"] = "container sha256sum does not match the downloaded bytes"
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        _discard(target)  # never leave a partial download looking like a capture
        if isinstance(exc, TimeoutError):
            row["status"] = "timeout"
        elif _missing(exc):
            row["status"] = "missing"
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def _save(out: Path, rows: list[dict[str, Any]], begin_error: str | None) -> None:
    payload: Any = [*rows, {"begin_error": begin_error}] if begin_error is not None else rows
    try:
        _write(out / "capture_manifest.json", payload)
    except OSError:
        pass  # the run's outcome remains authoritative; an unwritable log dir is already a trial error


async def _capture(
    environment: Any, out: Path, capture: Capture | None, begin_error: str | None = None
) -> None:
    """Download and hash every target, rewriting the manifest after each; never raises."""
    if capture is None:
        return
    rows: list[dict[str, Any]] = []
    try:
        for remote, relative in capture.targets:
            rows.append(
                await _capture_file(environment, out / "capture", remote, relative, capture.timeout_s)
            )
            _save(out, rows, begin_error)
    except Exception:  # noqa: BLE001 - capture never masks the run's or begin's own failure
        pass


async def begin(
    environment: Any,
    environ: Mapping[str, str],
    logs: Path,
    instruction: str,
    workdir: str,
) -> tuple[str, Capture | None]:
    """Seed the container and/or append the continuation message; the instruction and capture plan."""
    seed = (environ.get(SEED_ENV) or "").strip()
    continue_file = (environ.get(CONTINUE_ENV) or "").strip()
    feedback_file = (environ.get(FEEDBACK_ENV) or "").strip()
    requested = [p.strip() for p in (environ.get(CAPTURE_ENV) or "").split(",") if p.strip()]
    if feedback_file and not continue_file:
        raise ValueError(f"{FEEDBACK_ENV} needs {CONTINUE_ENV}")
    # The capture plan is parsed and validated before any seed or message work, so a failure in that work still
    # leaves a plan to capture with.
    capture = (
        _capture_plan(requested, workdir, _capture_timeout(environ)) if requested else None
    )
    if not (seed or continue_file or requested):
        return instruction, None
    out = Path(logs) / SUBDIR
    out.mkdir(parents=True, exist_ok=True)
    try:
        if seed:
            await _seed(environment, Path(seed), workdir, out)
        if continue_file:
            instruction = _message(
                instruction,
                Path(continue_file),
                Path(feedback_file) if feedback_file else None,
                out,
            )
    except Exception as exc:
        await _capture(environment, out, capture, f"{type(exc).__name__}: {exc}")
        raise
    return instruction, capture


async def finish(environment: Any, logs: Path, capture: Capture | None) -> None:
    """Download the capture plan and record it; never raises, so it cannot mask the run's outcome."""
    if capture is None:
        return
    await _capture(environment, Path(logs) / SUBDIR, capture)
