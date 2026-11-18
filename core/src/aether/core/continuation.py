"""Continuation runs: supplied seed files in, an appended message, the final deliverables captured out.

Gate 1 of the repair pilot. Off by default; every setting comes from the launcher's environment:
- ``AETHER_CORE_SEED_DIR``: host directory whose regular files are uploaded to ``<workdir>/<relative path>`` and
  read back with ``sha256sum`` before the run starts; a failed upload or a differing readback stops the run.
- ``AETHER_CORE_CONTINUE_FILE``: host UTF-8 text appended to the instruction as ``instruction + "\\n\\n" + text``;
  ``AETHER_CORE_FEEDBACK_FILE`` (optional) follows it the same way, and needs a continuation file.
- ``AETHER_CORE_CAPTURE``: comma-separated container paths (absolute, or relative to the workdir), captured under
  ``<logs_dir>/continuation/capture/`` whatever the run's outcome. Workdir paths land at ``capture/work/<relative>``;
  other absolute paths at ``capture/abs/<path>``, so ``/etc/x`` and ``etc/x`` cannot collide. A ``..`` escape is
  refused before any seed or message work, and duplicate requests are captured once.
- ``AETHER_CORE_CAPTURE_TIMEOUT_S``: seconds per container call made by capture (default 120); a timed-out capture
  records every remaining row as ``timeout``.

One manifest, ``continuation/capture_manifest.json``: a JSON object with ``version`` (1), ``workdir``, ``complete``,
``begin_error``, ``cancelled``, ``active_writers``, ``snapshot`` and ``rows``. A row is ``{"remote", "local",
"target", "status", "sha256", "bytes", "error"}``: ``remote`` the container path, ``local`` its path under
``continuation/capture/``, ``target`` its path relative to the workdir (null outside it), ``status`` one of
``captured``/``missing``/``timeout``/``unstable``/``error``/``cancelled``. Only confirmed bytes are stored, at
``capture/<local>``. The manifest is rewritten after every row, so a killed run keeps the rows finished so far.

One snapshot, not a sandwich per file: one bounded ``exec`` runs ``sha256sum`` over every target, tars them into one
``/tmp`` archive, then runs ``sha256sum`` again. Capture downloads that one archive, refuses members with absolute
paths or ``..``, extracts it and hashes each file. A file is ``captured`` only when its before hash, after hash and
extracted hash are equal, so every row comes from a file set that existed at one moment; a writer moving a file
makes that row ``unstable``. A file missing in the container is ``missing``.

``complete`` is true only when every row is ``captured``, the snapshot hashes match, ``active_writers`` is empty,
``begin_error`` is null and ``cancelled`` is false. ``finish`` takes ``active_writers`` (the processes Core's result
says were left running) and records it; no process is ever stopped for capture.

``begin`` captures anyway when seeding or the message step raises, records ``begin_error`` and re-raises unchanged.
Capture problems are recorded, never raised, so they cannot mask the run's outcome. Cancellation is the exception:
on ``asyncio.CancelledError`` capture writes what it has, marks every remaining row ``cancelled``, sets
``cancelled: true`` and re-raises, so the adapter's own cleanup still runs.

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
import secrets
import shutil
import tarfile
import tempfile
from typing import Any, Callable, Mapping

from .env import exit_code

SEED_ENV = "AETHER_CORE_SEED_DIR"
CONTINUE_ENV = "AETHER_CORE_CONTINUE_FILE"
FEEDBACK_ENV = "AETHER_CORE_FEEDBACK_FILE"
CAPTURE_ENV = "AETHER_CORE_CAPTURE"
CAPTURE_TIMEOUT_ENV = "AETHER_CORE_CAPTURE_TIMEOUT_S"
CAPTURE_TIMEOUT_S = 120.0
SUBDIR, CAPTURE_DIR = "continuation", "capture"
MANIFEST_FILE, MANIFEST_VERSION, SNAPSHOT_METHOD = "capture_manifest.json", 1, "tar"
BEFORE_MARK, AFTER_MARK = "@@aether-capture-before@@", "@@aether-capture-after@@"
EXEC_TIMEOUT_S = 120


@dataclass(frozen=True)
class Target:
    """One capture request: the container path, its path under the capture dir, and its workdir-relative path."""

    remote: str
    local: str
    target: str | None


@dataclass(frozen=True)
class Capture:
    """The capture plan: its targets, the workdir they were resolved against, and the per-call timeout."""

    workdir: str
    targets: tuple[Target, ...]
    timeout_s: float


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _quoted(path: str) -> str:
    """A container path, always single-quoted: tests map container paths into a fake root by this prefix."""
    return "'" + path.replace("'", "'\\''") + "'"


async def _create_parents(environment: Any, remote: str) -> None:
    parent = posixpath.dirname(remote) or "/"
    created = await environment.exec(
        command=f"mkdir -p {_quoted(parent)}", cwd=None, env=None, timeout_sec=EXEC_TIMEOUT_S
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
            command=f"sha256sum {_quoted(remote)}", cwd=None, env=None, timeout_sec=EXEC_TIMEOUT_S
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
    _write(out / "message_manifest.json", {"instruction_sha256": sha256(text.encode("utf-8")), **recorded})
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


def _capture_target(requested: str, workdir: str) -> Target:
    """The mapping for one request: container path, capture-dir path and workdir-relative target."""
    base = posixpath.normpath(workdir)
    remote = posixpath.normpath(requested if posixpath.isabs(requested) else posixpath.join(base, requested))
    relative = posixpath.relpath(remote, base)
    if relative == ".." or relative.startswith("../"):
        if not posixpath.isabs(requested):
            raise ValueError(f"{CAPTURE_ENV}: {requested!r} escapes the workdir {base!r}")
        local, target = "abs/" + remote.lstrip("/"), None
    else:
        local, target = "work/" + relative, relative
    parts = local.split("/")
    if not parts[-1] or "." in parts or ".." in parts:
        raise ValueError(f"{CAPTURE_ENV}: {requested!r} does not name a file to capture")
    return Target(remote, local, target)


def _capture_plan(requested: list[str], workdir: str, timeout_s: float) -> Capture:
    targets, seen = [], set()
    for path in requested:
        target = _capture_target(path, workdir)
        if target.remote in seen:  # two requests for one container file are captured once
            continue
        seen.add(target.remote)
        targets.append(target)
    return Capture(posixpath.normpath(workdir), tuple(targets), timeout_s)


def _row(target: Target, status: str, *, sha: str | None = None, size: int | None = None,
         error: str | None = None) -> dict[str, Any]:
    return {"remote": target.remote, "local": target.local, "target": target.target, "status": status,
            "sha256": sha, "bytes": size, "error": error}


def _snapshot_digest(capture: Capture, hashes: Mapping[int, str]) -> str | None:
    """One digest over (path, hash) for every target, or None when any target has no hash."""
    digest = hashlib.sha256()
    for index, target in enumerate(capture.targets):
        value = hashes.get(index)
        if not value:
            return None
        digest.update(target.remote.encode("utf-8") + b"\0" + value.encode("ascii") + b"\0")
    return digest.hexdigest()


def _complete(capture: Capture, rows: list[dict[str, Any]], snapshot: Mapping[str, Any],
              begin_error: str | None, cancelled: bool, active_writers: list[str]) -> bool:
    before, after = snapshot.get("sha256_before"), snapshot.get("sha256_after")
    return (
        not cancelled
        and begin_error is None
        and not active_writers
        and before is not None
        and before == after
        and len(rows) == len(capture.targets)
        and all(row["status"] == "captured" for row in rows)
    )


def _save(out: Path, capture: Capture, rows: list[dict[str, Any]], snapshot: Mapping[str, Any], *,
          begin_error: str | None, cancelled: bool, active_writers: list[str]) -> None:
    payload = {
        "version": MANIFEST_VERSION,
        "workdir": capture.workdir,
        "complete": _complete(capture, rows, snapshot, begin_error, cancelled, active_writers),
        "begin_error": begin_error,
        "cancelled": cancelled,
        "active_writers": list(active_writers),
        "snapshot": dict(snapshot),
        "rows": rows,
    }
    try:
        _write(out / MANIFEST_FILE, payload)
    except OSError:
        pass  # the run's outcome remains authoritative; an unwritable log dir is already a trial error


def _snapshot_command(capture: Capture) -> tuple[str, str]:
    """The one shell command: hash every target, tar them into one archive, then hash every target again."""
    archive = f"/tmp/aether-capture-{secrets.token_hex(8)}.tar"
    lines: list[str] = []

    def hashes(tag: str) -> None:
        for index, target in enumerate(capture.targets):
            lines.append(f"h=$(sha256sum {_quoted(target.remote)} 2>/dev/null | cut -c1-64)")
            lines.append(f"printf '{tag}\\t{index}\\t%s\\n' \"${{h:-none}}\"")

    hashes("B")
    lines.append(f"printf '%s\\n' {_quoted(BEFORE_MARK)}")
    members = " ".join(_quoted(target.remote.lstrip("/")) for target in capture.targets)
    lines.append(f"tar -cf {_quoted(archive)} -C / {members} 2>/dev/null")
    lines.append(f"printf '%s\\n' {_quoted(AFTER_MARK)}")
    hashes("A")
    return archive, "\n".join(lines) + "\n"


def _parse_hashes(stdout: str) -> tuple[dict[int, str], dict[int, str], bool]:
    """The before and after (target index, hash) tables of a snapshot command, and whether both markers were seen."""
    before: dict[int, str] = {}
    after: dict[int, str] = {}
    seen_before = seen_after = False
    section = "before"
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped == BEFORE_MARK:
            seen_before, section = True, "tar"
            continue
        if stripped == AFTER_MARK:
            seen_after, section = True, "after"
            continue
        fields = line.split("\t")
        if len(fields) != 3 or fields[0] not in ("B", "A") or section == "tar":
            continue
        tag, index, digest = fields
        if digest != "none" and index.isdigit():
            (before if tag == "B" else after)[int(index)] = digest
    return before, after, seen_before and seen_after


def _extract(archive: Path, root: Path) -> set[str]:
    """Extract the snapshot's regular files and directories, refusing any member that could leave ``root``.

    Returns the names of the other members (a symlink or hard link in the request): their rows are errors of their
    own, and every other row is still captured. Refusing the whole archive voided good rows for one link.
    """
    with tarfile.open(archive, mode="r:") as tar:
        members, other = [], set()
        for member in tar.getmembers():
            name = member.name
            if not name or posixpath.isabs(name) or ".." in Path(name).parts:
                raise ValueError(f"snapshot member escapes the archive: {name!r}")
            if member.isfile() or member.isdir():
                members.append(member)
            else:
                other.add(name)
        tar.extractall(root, members=members)
    return other


def _row_for(target: Target, index: int, before: Mapping[int, str], after: Mapping[int, str],
             root: Path) -> tuple[dict[str, Any], bytes | None]:
    """The row for one target and, only when it is captured, its bytes."""
    previous, following = before.get(index), after.get(index)
    if previous is None:
        return _row(target, "missing", error="not found in the container"), None
    if following is None:
        return _row(target, "unstable", error="the file disappeared during the snapshot"), None
    try:
        data = (root / target.remote.lstrip("/")).read_bytes()
    except OSError as exc:
        return _row(target, "unstable", error=f"{type(exc).__name__}: {exc}"), None
    digest = sha256(data)
    if previous != following or digest != previous:
        return (
            _row(target, "unstable", sha=digest, size=len(data),
                 error="the snapshot hashes disagree: the file moved during the snapshot"),
            None,
        )
    return _row(target, "captured", sha=digest, size=len(data)), data


async def _populate(environment: Any, out: Path, capture: Capture, rows: list[dict[str, Any]],
                    snapshot: dict[str, Any], save: Callable[[], None]) -> None:
    """One snapshot: bounded hash/tar/hash command, bounded archive download, checked extraction."""
    archive, command = _snapshot_command(capture)
    result = await asyncio.wait_for(
        environment.exec(command=command, cwd=None, env=None,
                         timeout_sec=max(1, math.ceil(capture.timeout_s))),
        capture.timeout_s,
    )
    before, after, parsed = _parse_hashes(str(getattr(result, "stdout", "") or ""))
    if not parsed:
        detail = str(getattr(result, "stderr", "") or "").strip()[:300]
        raise OSError(f"snapshot command produced no hashes: {detail or exit_code(result)}")
    snapshot["sha256_before"] = _snapshot_digest(capture, before)
    snapshot["sha256_after"] = _snapshot_digest(capture, after)
    local_archive = out / f"snapshot-{secrets.token_hex(6)}.tar"
    staging = Path(tempfile.mkdtemp(prefix="snapshot-", dir=out))
    try:
        await asyncio.wait_for(environment.download_file(archive, local_archive), capture.timeout_s)
        other = _extract(local_archive, staging)
        for index, target in enumerate(capture.targets):
            if target.remote.lstrip("/") in other:
                row, data = _row(target, "error", error="not a regular file (a symlink or link); not captured"), None
            else:
                row, data = _row_for(target, index, before, after, staging)
            if data is not None:
                try:
                    stored = out / CAPTURE_DIR / target.local
                    stored.parent.mkdir(parents=True, exist_ok=True)
                    stored.write_bytes(data)
                except OSError as exc:
                    row = _row(target, "error", error=f"{type(exc).__name__}: {exc}")
            rows.append(row)
            save()
    finally:
        _discard(local_archive)
        shutil.rmtree(staging, ignore_errors=True)


def _discard(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass  # a leftover partial file must not turn a recorded outcome into a raised one


def _fill(rows: list[dict[str, Any]], capture: Capture, status: str, error: str) -> None:
    """Every target without a row yet gets ``status``: the rows done so far are kept in order."""
    for target in capture.targets[len(rows):]:
        rows.append(_row(target, status, error=error))


async def _capture(environment: Any, out: Path, capture: Capture | None, begin_error: str | None = None,
                   active_writers: list[str] | None = None) -> None:
    """Take one snapshot of every target and record it; never raises, except on cancellation (which re-raises)."""
    if capture is None:
        return
    rows: list[dict[str, Any]] = []
    snapshot: dict[str, Any] = {"method": SNAPSHOT_METHOD, "sha256_before": None, "sha256_after": None}
    writers = [str(writer) for writer in (active_writers or [])]

    def save(cancelled: bool = False) -> None:
        _save(out, capture, rows, snapshot, begin_error=begin_error, cancelled=cancelled,
              active_writers=writers)

    try:
        await _populate(environment, out, capture, rows, snapshot, save)
    except asyncio.CancelledError:
        _fill(rows, capture, "cancelled", "capture was cancelled")
        save(cancelled=True)
        raise
    except Exception as exc:  # noqa: BLE001 - recorded, never raised: it must not mask the run's outcome
        status = "timeout" if isinstance(exc, TimeoutError) else "error"
        _fill(rows, capture, status, f"{type(exc).__name__}: {exc}")
        save()
        return
    save()


async def begin(environment: Any, environ: Mapping[str, str], logs: Path, instruction: str,
                workdir: str) -> tuple[str, Capture | None]:
    """Seed the container and/or append the continuation message; the instruction and capture plan."""
    seed = (environ.get(SEED_ENV) or "").strip()
    continue_file = (environ.get(CONTINUE_ENV) or "").strip()
    feedback_file = (environ.get(FEEDBACK_ENV) or "").strip()
    requested = [p.strip() for p in (environ.get(CAPTURE_ENV) or "").split(",") if p.strip()]
    if feedback_file and not continue_file:
        raise ValueError(f"{FEEDBACK_ENV} needs {CONTINUE_ENV}")
    # The capture plan is parsed and validated before any seed or message work, so a failure in that work still
    # leaves a plan to capture with.
    capture = _capture_plan(requested, workdir, _capture_timeout(environ)) if requested else None
    if not (seed or continue_file or requested):
        return instruction, None
    out = Path(logs) / SUBDIR
    out.mkdir(parents=True, exist_ok=True)
    try:
        if seed:
            await _seed(environment, Path(seed), workdir, out)
        if continue_file:
            instruction = _message(
                instruction, Path(continue_file), Path(feedback_file) if feedback_file else None, out
            )
    except Exception as exc:
        await _capture(environment, out, capture, f"{type(exc).__name__}: {exc}")
        raise
    return instruction, capture


async def finish(environment: Any, logs: Path, capture: Capture | None,
                 active_writers: list[str] | None = None) -> None:
    """Snapshot the capture plan and record it; never raises, so it cannot mask the run's outcome.

    ``active_writers`` is what Core's own result says was still running when the run ended; any non-empty list
    makes the manifest incomplete. It is recorded, never acted on: no process is stopped for capture. A
    cancellation during capture writes the manifest (remaining rows ``cancelled``) and re-raises.
    """
    if capture is None:
        return
    await _capture(environment, Path(logs) / SUBDIR, capture, active_writers=active_writers)
