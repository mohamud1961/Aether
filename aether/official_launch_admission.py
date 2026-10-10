"""Fail-closed at-most-once admission for official provider launches.

The launcher already namespaces evidence by ``run_id``.  That is not enough
when two callers choose different run ids for the same frozen task/runtime.
This module adds a stable identity, an OS-level process lock, and a durable
terminal record.  A record is retained after dispatch, including an uncertain
failure, so a later caller cannot turn delivery ambiguity into a benchmark
retry.
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import time
from typing import Any, Mapping


SCHEMA = "aether.official_launch_admission.v1"
IDENTITY_SCHEMA = "aether.official_launch_identity.v1"
STATE_DIR_ENV = "AETHER_OFFICIAL_LAUNCH_STATE_DIR"


class OfficialLaunchAdmissionError(RuntimeError):
    """Raised when an official launch cannot be admitted safely."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def identity_sha256(identity: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _safe_state_dir() -> Path:
    raw = os.environ.get(STATE_DIR_ENV)
    root = Path(raw).expanduser() if raw else Path.home() / ".aether" / "official_launch_admission_v1"
    absolute = root.absolute()
    if absolute == Path(absolute.anchor):
        raise OfficialLaunchAdmissionError("official launch admission state directory may not be filesystem root")
    # Do not follow a user-controlled alias for durable identity.  The state
    # directory may be new, so inspect existing components before mkdir.
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise OfficialLaunchAdmissionError(
                f"official launch admission state directory contains a symlink: {cursor}"
            )
    try:
        absolute.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise OfficialLaunchAdmissionError(
            f"official launch admission state directory is unavailable: {absolute}: {exc}"
        ) from exc
    if absolute.is_symlink() or not absolute.is_dir():
        raise OfficialLaunchAdmissionError(
            f"official launch admission state directory is not a real directory: {absolute}"
        )
    if absolute.stat().st_mode & 0o077:
        raise OfficialLaunchAdmissionError(
            f"official launch admission state directory permissions are too broad: {absolute}"
        )
    return absolute


def _open_no_follow(path: Path, flags: int, mode: int = 0o600) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(str(path), flags | no_follow, mode)
    except FileExistsError:
        # O_EXCL callers use this to distinguish a racing durable record from
        # an unrelated filesystem failure.
        raise
    except OSError as exc:
        raise OfficialLaunchAdmissionError(f"official launch admission file is unavailable: {path}: {exc}") from exc


def _write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        offset += os.write(fd, data[offset:])


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    data = (_canonical_json(payload) + "\n").encode("utf-8")
    fd = _open_no_follow(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    data = (_canonical_json(payload) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{time.monotonic_ns()}")
    fd = _open_no_follow(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.replace(temporary, path)
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise OfficialLaunchAdmissionError(
            f"official launch admission record could not be made durable: {path}: {exc}"
        ) from exc


def _read_record(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise OfficialLaunchAdmissionError(
            f"official launch admission state is invalid; refusing to dispatch: {path} is not a regular file"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialLaunchAdmissionError(
            f"official launch admission state is invalid; refusing to dispatch: {path}: {exc}"
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != SCHEMA
        or value.get("identity_schema_version") != IDENTITY_SCHEMA
    ):
        raise OfficialLaunchAdmissionError(
            f"official launch admission state is invalid; refusing to dispatch: {path} schema mismatch"
        )
    recorded_identity = value.get("identity")
    recorded_hash = value.get("identity_sha256")
    if not isinstance(recorded_identity, Mapping) or identity_sha256(recorded_identity) != recorded_hash:
        raise OfficialLaunchAdmissionError(
            f"official launch admission state is invalid; refusing to dispatch: {path} identity mismatch"
        )
    return value


@dataclass
class OfficialLaunchAdmission:
    """One held process lease and its durable identity record."""

    identity: dict[str, Any]
    identity_sha256: str
    record_path: Path
    lock_path: Path
    lock_fd: int
    run_id: str
    evidence_root: str
    _closed: bool = False

    @classmethod
    def acquire(
        cls,
        identity: Mapping[str, Any],
        *,
        run_id: str,
        evidence_root: str,
    ) -> "OfficialLaunchAdmission":
        if not isinstance(identity, Mapping) or identity.get("schema_version") != IDENTITY_SCHEMA:
            raise OfficialLaunchAdmissionError("official launch identity schema is invalid")
        stable_identity = json.loads(_canonical_json(identity))
        identity_hash = identity_sha256(stable_identity)
        state_dir = _safe_state_dir()
        lock_path = state_dir / f"launch-{identity_hash}.lock"
        record_path = state_dir / f"launch-{identity_hash}.json"
        lock_fd = _open_no_follow(lock_path, os.O_CREAT | os.O_RDWR)
        try:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise OfficialLaunchAdmissionError(
                    f"duplicate official launch admission is active for identity {identity_hash}"
                ) from exc
            except OSError as exc:
                raise OfficialLaunchAdmissionError(
                    f"official launch admission lock is unavailable for identity {identity_hash}: {exc}"
                ) from exc
            if record_path.exists() or record_path.is_symlink():
                current = _read_record(record_path)
                raise OfficialLaunchAdmissionError(
                    "duplicate official launch is already durably recorded for "
                    f"identity {identity_hash} (status={current.get('status')!r})"
                )
            record = {
                "schema_version": SCHEMA,
                "identity_schema_version": IDENTITY_SCHEMA,
                "identity_sha256": identity_hash,
                "identity": stable_identity,
                "run_id": str(run_id),
                "evidence_root": str(evidence_root),
                "owner": {
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "started_at_unix_s": time.time(),
                },
                "status": "admitted",
                "dispatch_started": False,
            }
            try:
                _write_exclusive(record_path, record)
            except FileExistsError as exc:
                raise OfficialLaunchAdmissionError(
                    f"duplicate official launch is already durably recorded for identity {identity_hash}"
                ) from exc
            return cls(
                identity=stable_identity,
                identity_sha256=identity_hash,
                record_path=record_path,
                lock_path=lock_path,
                lock_fd=lock_fd,
                run_id=str(run_id),
                evidence_root=str(evidence_root),
            )
        except Exception:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)
            raise

    def _record(self) -> dict[str, Any]:
        return _read_record(self.record_path)

    def snapshot(self) -> dict[str, Any]:
        value = self._record()
        value["record_path"] = str(self.record_path)
        value["lock_path"] = str(self.lock_path)
        return value

    def _update(self, **fields: Any) -> None:
        value = self._record()
        value.update(fields)
        _write_atomic(self.record_path, value)

    def mark_dispatch_started(self) -> None:
        if self._closed:
            raise OfficialLaunchAdmissionError("official launch admission lease is already closed")
        self._update(
            status="dispatch_started",
            dispatch_started=True,
            dispatch_started_at_unix_s=time.time(),
        )

    def finalize(self, *, status: str, exit_code: int | None = None, error: str | None = None) -> None:
        if self._closed:
            return
        try:
            fields: dict[str, Any] = {
                "status": str(status),
                "finished_at_unix_s": time.time(),
            }
            if exit_code is not None:
                fields["exit_code"] = int(exit_code)
            if error is not None:
                fields["error"] = str(error)
            self._update(**fields)
        finally:
            self.release()

    def abandon_before_dispatch(self) -> None:
        """Release bookkeeping that failed before any child could start."""
        if self._closed:
            return
        try:
            if self.record_path.exists() and not self.record_path.is_symlink():
                self.record_path.unlink()
        finally:
            self.release()

    def release(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(self.lock_fd)
