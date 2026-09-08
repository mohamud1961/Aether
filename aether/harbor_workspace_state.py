"""Bounded workspace mutation observation for remote Harbor task worlds.

Harbor's BaseEnvironment executes inside a remote/container task world, so the
host-side workspace snapshot helper cannot observe its filesystem directly.
This module derives a bounded, read-only stat inventory through the task shell
and compares two inventories mechanically.

This is a *freshness* detector, not artifact identity authority. Exact artifact
bytes are content-addressed by the artifact plane when they are read/inspected.
For production Linux/GNU stat we retain high-resolution mtime/ctime, size, kind,
mode and ownership. A same-size rewrite therefore changes the filesystem ctime
even when a caller restores mtime. BSD stat exposes only second-resolution times
through the portable surface used here, so BSD snapshots are explicitly marked
``coarse`` and become conservative freshness boundaries rather than false proof
that state stayed unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import shlex
from typing import Any


REMOTE_WORKSPACE_STATE_SCHEMA = "aether.remote_workspace_state.v2"
MAX_REMOTE_WORKSPACE_ENTRIES = 5_000
_HEADER = "__AETHER_REMOTE_WORKSPACE_STATE_V2__"
_UNAVAILABLE = "__AETHER_REMOTE_WORKSPACE_STATE_UNAVAILABLE__"
_STAT = "__AETHER_REMOTE_WORKSPACE_STAT__"
_SKIP_NAMES = (".git", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache")


@dataclass(frozen=True)
class RemotePathState:
    path: str
    kind: str
    size: int
    mtime: str
    ctime: str
    mode: str
    uid: str
    gid: str


@dataclass(frozen=True)
class RemoteWorkspaceSnapshot:
    root: str
    entries: tuple[RemotePathState, ...] = ()
    available: bool = True
    truncated: bool = False
    stat_backend: str = ""
    time_precision: str = ""
    detail: str = ""
    malformed_rows: int = 0

    def by_path(self) -> dict[str, RemotePathState]:
        return {row.path: row for row in self.entries}

    @property
    def digest(self) -> str:
        digest = hashlib.sha256()
        digest.update(REMOTE_WORKSPACE_STATE_SCHEMA.encode("ascii"))
        digest.update(b"\n")
        for row in self.entries:
            digest.update(repr(row).encode("utf-8", "surrogateescape"))
            digest.update(b"\n")
        digest.update(
            (
                f"available={self.available};truncated={self.truncated};"
                f"stat={self.stat_backend};precision={self.time_precision};"
                f"malformed={self.malformed_rows}"
            ).encode("utf-8")
        )
        return digest.hexdigest()


def _find_prefix(root: str) -> str:
    qroot = shlex.quote(root)
    clean_root = str(root).rstrip("/")
    harness_internal = (
        f"{clean_root}/.aether/harbor_jobs",
        f"{clean_root}/.aether/harbor_terminals",
    )
    prune_terms = [f"-name {shlex.quote(name)}" for name in _SKIP_NAMES]
    prune_terms.extend(f"-path {shlex.quote(path)}" for path in harness_internal)
    prune = " -o ".join(prune_terms)
    return (
        f"find {qroot} -mindepth 1 \\( {prune} \\) -prune -o "
        "\\( -type f -o -type l \\) "
    )


def remote_workspace_snapshot_command(
    root: str,
    *,
    max_entries: int = MAX_REMOTE_WORKSPACE_ENTRIES,
) -> str:
    """Build one bounded read-only stat inventory command.

    GNU ``%y``/``%z`` retain sub-second timestamp precision. The BSD fallback
    uses portable epoch-second fields and is labelled coarse by the header.
    One overflow row is retained so truncation is mechanically observable.
    """
    clean_root = str(root or "").strip()
    if not clean_root.startswith("/"):
        raise ValueError("remote workspace snapshot requires an absolute root")
    qroot = shlex.quote(clean_root)
    section_lines = max(1, int(max_entries)) + 1
    all_paths = _find_prefix(clean_root)
    gnu_stat = (
        all_paths
        + "-exec stat -c '%n\t%s\t%y\t%z\t%a\t%u\t%g\t%F' {} + 2>/dev/null"
    )
    bsd_stat = (
        all_paths
        + "-exec stat -f '%N\t%z\t%m\t%c\t%Lp\t%u\t%g\t%HT' {} + 2>/dev/null"
    )
    return (
        "LC_ALL=C; export LC_ALL; "
        f"if stat -c '%n' {qroot} >/dev/null 2>&1; then sb=gnu; tp=nanosecond; "
        f"elif stat -f '%N' {qroot} >/dev/null 2>&1; then sb=bsd; tp=seconds; "
        "else printf '" + _UNAVAILABLE + "\tstat_backend_missing\n'; exit 0; fi; "
        f"printf '{_HEADER}\t%s\t%s\n' \"$sb\" \"$tp\"; "
        f"printf '{_STAT}\n'; "
        f"if [ \"$sb\" = gnu ]; then {gnu_stat} | head -n {section_lines}; "
        f"else {bsd_stat} | head -n {section_lines}; fi"
    )


def _relative_path(absolute: str, root: str) -> str:
    prefix = str(root).rstrip("/") + "/"
    if not absolute.startswith(prefix):
        return ""
    relative = absolute[len(prefix):]
    if not relative or relative.startswith("../"):
        return ""
    return relative


def parse_remote_workspace_snapshot(
    stdout: str,
    *,
    root: str,
    max_entries: int = MAX_REMOTE_WORKSPACE_ENTRIES,
    command_succeeded: bool = True,
    detail: str = "",
) -> RemoteWorkspaceSnapshot:
    """Parse one bounded remote stat inventory without guessing malformed data."""
    lines = str(stdout or "").splitlines()
    if not command_succeeded:
        return RemoteWorkspaceSnapshot(
            root=root, available=False, detail=detail or "snapshot command failed",
        )
    if not lines:
        return RemoteWorkspaceSnapshot(
            root=root, available=False,
            detail=detail or "snapshot command returned no authority header",
        )
    first = lines[0].split("\t")
    if first[0] == _UNAVAILABLE:
        return RemoteWorkspaceSnapshot(
            root=root,
            available=False,
            detail=(first[1] if len(first) > 1 else "remote snapshot backend unavailable"),
        )
    if len(first) != 3 or first[0] != _HEADER:
        return RemoteWorkspaceSnapshot(
            root=root, available=False, detail="snapshot authority header malformed",
        )
    stat_backend, time_precision = first[1].strip(), first[2].strip()
    if stat_backend not in {"gnu", "bsd"} or time_precision not in {"nanosecond", "seconds"}:
        return RemoteWorkspaceSnapshot(
            root=root, available=False,
            stat_backend=stat_backend, time_precision=time_precision,
            detail="snapshot backend or time precision identity is unknown",
        )
    if len(lines) < 2 or lines[1] != _STAT:
        return RemoteWorkspaceSnapshot(
            root=root, available=False,
            stat_backend=stat_backend, time_precision=time_precision,
            detail="snapshot stat section marker missing",
        )

    limit = max(1, int(max_entries))
    stat_rows = lines[2:]
    truncated = len(stat_rows) > limit
    stat_rows = stat_rows[:limit]
    malformed = 0
    entries: list[RemotePathState] = []
    seen: set[str] = set()
    for line in stat_rows:
        fields = line.split("\t")
        if len(fields) != 8:
            malformed += 1
            continue
        absolute, size_text, mtime, ctime, mode, uid, gid, kind = fields
        relative = _relative_path(absolute, root)
        if not relative or relative in seen:
            malformed += 1
            continue
        try:
            size = int(size_text)
        except ValueError:
            malformed += 1
            continue
        lower_kind = kind.lower()
        is_regular = "regular" in lower_kind
        is_symlink = "symbolic" in lower_kind or lower_kind == "symlink"
        if not (is_regular or is_symlink):
            malformed += 1
            continue
        seen.add(relative)
        entries.append(RemotePathState(
            path=relative,
            kind=kind,
            size=size,
            mtime=mtime,
            ctime=ctime,
            mode=mode,
            uid=uid,
            gid=gid,
        ))

    if malformed:
        return RemoteWorkspaceSnapshot(
            root=root,
            entries=tuple(sorted(entries, key=lambda row: row.path)),
            available=False,
            truncated=truncated,
            stat_backend=stat_backend,
            time_precision=time_precision,
            detail=f"snapshot contained {malformed} malformed or incomplete row(s)",
            malformed_rows=malformed,
        )
    return RemoteWorkspaceSnapshot(
        root=root,
        entries=tuple(sorted(entries, key=lambda row: row.path)),
        available=True,
        truncated=truncated,
        stat_backend=stat_backend,
        time_precision=time_precision,
    )


def diff_remote_workspace_snapshots(
    before: RemoteWorkspaceSnapshot,
    after: RemoteWorkspaceSnapshot,
) -> dict[str, Any]:
    """Return a mechanical remote-workspace delta with explicit completeness."""
    common = {
        "before_digest": before.digest,
        "after_digest": after.digest,
        "before_truncated": before.truncated,
        "after_truncated": after.truncated,
        "before_stat_backend": before.stat_backend,
        "after_stat_backend": after.stat_backend,
        "before_time_precision": before.time_precision,
        "after_time_precision": after.time_precision,
        "mutation_detection_basis": (
            "bounded_stat_kind_size_mtime_ctime_mode_uid_gid"
        ),
        "mutation_actor_status": "mutation_actor_unknown",
        "mutation_actor_detail": (
            "change is bounded to this Harbor action interval; no subprocess actor is asserted"
        ),
    }
    if not before.available or not after.available:
        return {
            **common,
            "mutation_detection_status": "unavailable",
            "before_available": before.available,
            "after_available": after.available,
            "before_detail": before.detail,
            "after_detail": after.detail,
            "created_paths": [],
            "removed_paths": [],
            "content_changed_paths": [],
            "metadata_changed_paths": [],
        }

    before_map = before.by_path()
    after_map = after.by_path()
    truncated = before.truncated or after.truncated
    # Absence from a truncated prefix is not evidence of filesystem absence.
    # Never turn sampling-boundary movement into fabricated create/remove facts.
    created = [] if truncated else sorted(set(after_map) - set(before_map))
    removed = [] if truncated else sorted(set(before_map) - set(after_map))
    content_changed: list[str] = []
    metadata_changed: list[str] = []
    for path in sorted(set(before_map) & set(after_map)):
        old = before_map[path]
        new = after_map[path]
        if (old.kind, old.size) != (new.kind, new.size):
            content_changed.append(path)
        elif (old.mode, old.uid, old.gid, old.mtime, old.ctime) != (
            new.mode, new.uid, new.gid, new.mtime, new.ctime
        ):
            # Timestamp change is deliberately called metadata change here. It
            # proves the path changed during the interval without overclaiming
            # that bytes changed; exact byte identity belongs to artifact reads.
            metadata_changed.append(path)

    if truncated:
        status = "truncated"
    elif before.time_precision != "nanosecond" or after.time_precision != "nanosecond":
        status = "coarse"
    else:
        status = "complete"
    return {
        **common,
        "mutation_detection_status": status,
        "before_available": True,
        "after_available": True,
        "created_paths": created,
        "removed_paths": removed,
        "content_changed_paths": content_changed,
        "metadata_changed_paths": metadata_changed,
        "path_set_delta_status": (
            "unknown_due_truncation" if truncated else "complete"
        ),
    }


__all__ = [
    "REMOTE_WORKSPACE_STATE_SCHEMA",
    "MAX_REMOTE_WORKSPACE_ENTRIES",
    "RemotePathState",
    "RemoteWorkspaceSnapshot",
    "remote_workspace_snapshot_command",
    "parse_remote_workspace_snapshot",
    "diff_remote_workspace_snapshots",
]
