from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .hashing import hash_canonical_json, sha256_hex
from .policy_config import WORKSPACE_IGNORE_PATTERNS


@dataclass(frozen=True)
class FileHashEntry:
    path: str
    hash: str
    size_bytes: int


@dataclass(frozen=True)
class WorkspaceFingerprint:
    fingerprint_hash: str
    file_hashes: List[FileHashEntry]
    diff_summary: Dict[str, object]
    dirty_since_last_verify: bool
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class _CacheEntry:
    hash: str
    size_bytes: int
    mtime_ns: int


@dataclass
class WorkspaceFingerprintCache:
    entries: Dict[str, _CacheEntry] = field(default_factory=dict)


_FINGERPRINT_CACHES: Dict[str, WorkspaceFingerprintCache] = {}


def compute_workspace_fingerprint(
    root: Path,
    *,
    ignore_patterns: Optional[Sequence[str]] = None,
    last_verified_hash: Optional[str] = None,
    previous_fingerprint: Optional[WorkspaceFingerprint] = None,
    fingerprint_cache: Optional[WorkspaceFingerprintCache] = None,
) -> WorkspaceFingerprint:
    if not root.exists():
        raise FileNotFoundError(f"Workspace root does not exist: {root}")

    patterns = _resolve_ignore_patterns(ignore_patterns)
    cache = fingerprint_cache or _FINGERPRINT_CACHES.setdefault(
        root.resolve().as_posix(), WorkspaceFingerprintCache()
    )

    entries = list(_walk_files_incremental(root, patterns, cache))
    fingerprint_hash = _hash_entries(entries)
    diff_summary = _diff_summary(previous_fingerprint, entries)

    # Fail closed: if metadata-driven incremental result appears inconsistent,
    # recompute from bytes and refresh cache.
    if _requires_full_rescan(previous_fingerprint, diff_summary, fingerprint_hash):
        entries = list(_walk_files_full(root, patterns))
        _refresh_cache_from_entries(root, patterns, cache, entries)
        fingerprint_hash = _hash_entries(entries)
        diff_summary = _diff_summary(previous_fingerprint, entries)

    dirty_since_last_verify = last_verified_hash is None or last_verified_hash != fingerprint_hash
    metadata = {
        "ignore_patterns": list(patterns),
        "ignore_list_hash": hash_canonical_json(list(patterns)),
    }
    return WorkspaceFingerprint(
        fingerprint_hash=fingerprint_hash,
        file_hashes=entries,
        diff_summary=diff_summary,
        dirty_since_last_verify=dirty_since_last_verify,
        metadata=metadata,
    )


def compute_workspace_fingerprint_full(
    root: Path,
    *,
    ignore_patterns: Optional[Sequence[str]] = None,
    last_verified_hash: Optional[str] = None,
    previous_fingerprint: Optional[WorkspaceFingerprint] = None,
) -> WorkspaceFingerprint:
    if not root.exists():
        raise FileNotFoundError(f"Workspace root does not exist: {root}")

    patterns = _resolve_ignore_patterns(ignore_patterns)
    entries = list(_walk_files_full(root, patterns))
    fingerprint_hash = _hash_entries(entries)
    diff_summary = _diff_summary(previous_fingerprint, entries)
    dirty_since_last_verify = last_verified_hash is None or last_verified_hash != fingerprint_hash
    metadata = {
        "ignore_patterns": list(patterns),
        "ignore_list_hash": hash_canonical_json(list(patterns)),
    }
    return WorkspaceFingerprint(
        fingerprint_hash=fingerprint_hash,
        file_hashes=entries,
        diff_summary=diff_summary,
        dirty_since_last_verify=dirty_since_last_verify,
        metadata=metadata,
    )


def _resolve_ignore_patterns(ignore_patterns: Optional[Sequence[str]]) -> Sequence[str]:
    if ignore_patterns is None:
        return WORKSPACE_IGNORE_PATTERNS
    return tuple(ignore_patterns)


def _walk_files_incremental(
    root: Path,
    ignore_patterns: Sequence[str],
    cache: WorkspaceFingerprintCache,
) -> Iterable[FileHashEntry]:
    seen_paths: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        for filename in filenames:
            full_path = Path(dirpath) / filename
            relative_path = full_path.relative_to(root).as_posix()
            if _is_ignored(relative_path, ignore_patterns):
                continue

            stat = full_path.stat()
            seen_paths.add(relative_path)
            cached = cache.entries.get(relative_path)
            if (
                cached is not None
                and cached.size_bytes == stat.st_size
                and cached.mtime_ns == stat.st_mtime_ns
            ):
                file_hash = cached.hash
            else:
                file_hash = sha256_hex(full_path.read_bytes())

            cache.entries[relative_path] = _CacheEntry(
                hash=file_hash,
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )

            yield FileHashEntry(
                path=relative_path,
                hash=file_hash,
                size_bytes=stat.st_size,
            )

    for path in list(cache.entries.keys()):
        if path not in seen_paths:
            del cache.entries[path]


def _walk_files_full(root: Path, ignore_patterns: Sequence[str]) -> Iterable[FileHashEntry]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        for filename in filenames:
            full_path = Path(dirpath) / filename
            relative_path = full_path.relative_to(root).as_posix()
            if _is_ignored(relative_path, ignore_patterns):
                continue
            data = full_path.read_bytes()
            yield FileHashEntry(
                path=relative_path,
                hash=sha256_hex(data),
                size_bytes=len(data),
            )


def _refresh_cache_from_entries(
    root: Path,
    ignore_patterns: Sequence[str],
    cache: WorkspaceFingerprintCache,
    entries: Sequence[FileHashEntry],
) -> None:
    cache.entries.clear()
    for entry in entries:
        full_path = root / entry.path
        if not full_path.exists() or _is_ignored(entry.path, ignore_patterns):
            continue
        stat = full_path.stat()
        cache.entries[entry.path] = _CacheEntry(
            hash=entry.hash,
            size_bytes=entry.size_bytes,
            mtime_ns=stat.st_mtime_ns,
        )


def _requires_full_rescan(
    previous_fingerprint: Optional[WorkspaceFingerprint],
    diff_summary: Dict[str, object],
    current_hash: str,
) -> bool:
    if previous_fingerprint is None:
        return False
    if diff_summary.get("no_file_diffs") is not True:
        return False
    return previous_fingerprint.fingerprint_hash != current_hash


def _is_ignored(path: str, ignore_patterns: Sequence[str]) -> bool:
    for pattern in ignore_patterns:
        # Directory-style patterns (e.g. ".git/") should match the directory
        # itself and any descendants in a path-stable way.
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            if not dir_pattern:
                continue
            parts = path.split("/")
            for index in range(1, len(parts) + 1):
                candidate = "/".join(parts[:index])
                if fnmatch.fnmatch(candidate, dir_pattern):
                    return True
            continue
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _hash_entries(entries: List[FileHashEntry]) -> str:
    payload = [
        {"path": entry.path, "hash": entry.hash, "size_bytes": entry.size_bytes}
        for entry in entries
    ]
    return hash_canonical_json(payload)


def _diff_summary(
    previous: Optional[WorkspaceFingerprint],
    current_entries: List[FileHashEntry],
) -> Dict[str, object]:
    current_map = {entry.path: entry.hash for entry in current_entries}
    previous_map = {entry.path: entry.hash for entry in previous.file_hashes} if previous else {}

    added = sorted(path for path in current_map if path not in previous_map)
    removed = sorted(path for path in previous_map if path not in current_map)
    modified = sorted(
        path
        for path in current_map
        if path in previous_map and current_map[path] != previous_map[path]
    )
    unchanged_count = len(current_map) - len(added) - len(modified)
    no_file_diffs = not added and not removed and not modified
    fingerprint_delta = len(added) + len(removed) + len(modified)

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "fingerprint_delta": fingerprint_delta,
        "unchanged_count": unchanged_count,
        "total_count": len(current_map),
        "no_file_diffs": no_file_diffs,
    }


def has_fingerprint_delta(diff_summary: Dict[str, object]) -> bool:
    if not isinstance(diff_summary, dict):
        return True

    delta = diff_summary.get("fingerprint_delta")
    if isinstance(delta, int):
        return delta > 0

    added = diff_summary.get("added", [])
    removed = diff_summary.get("removed", [])
    modified = diff_summary.get("modified", [])
    return bool(added or removed or modified)
