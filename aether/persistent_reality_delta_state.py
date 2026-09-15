"""Admission-aware state for lossless PERSISTENT reality-delta transport.

The provider-native response chain and the reality snapshot chain must advance
atomically.  This module mirrors Aether's existing staged-response admission
pattern without owning provider calls: prepare a full/delta payload against the
last *committed* parent, stage the returned response candidate, then commit only
a locally admitted Solver turn.  Clearing provider continuity must clear this
state too so the next call re-anchors with a full snapshot.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import threading
from typing import Any, Mapping

from .persistent_reality_delta import (
    DELTA_MODE,
    FULL_MODE,
    reconstruct_snapshot,
    snapshot_sha256,
    transport_envelope,
)


ScopeKey = tuple[str, str]


def _scope(run_id: str, task_id: str) -> ScopeKey:
    key = (str(run_id or "").strip(), str(task_id or "").strip())
    if not all(key):
        raise ValueError("PERSISTENT reality-delta scope requires non-empty run_id and task_id")
    return key


def _copy_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("PERSISTENT reality-delta snapshot must be a mapping")
    return {str(key): deepcopy(item) for key, item in value.items()}


@dataclass(frozen=True)
class PreparedRealityTransport:
    scope_key: ScopeKey
    parent_response_id: str | None
    current_snapshot: dict[str, Any]
    envelope: dict[str, Any]

    @property
    def mode(self) -> str:
        return str(self.envelope.get("mode") or "")


@dataclass(frozen=True)
class _CommittedReality:
    response_id: str
    snapshot: dict[str, Any]


class RealityDeltaTransportState:
    """Task-scoped, two-phase snapshot state aligned with response admission."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._committed: dict[ScopeKey, _CommittedReality] = {}
        self._pending: dict[ScopeKey, _CommittedReality] = {}

    def prepare(
        self,
        current_snapshot: Mapping[str, Any],
        *,
        run_id: str,
        task_id: str,
        previous_response_id: str | None,
    ) -> PreparedRealityTransport:
        key = _scope(run_id, task_id)
        current = _copy_snapshot(current_snapshot)
        parent = str(previous_response_id or "").strip() or None
        with self._lock:
            if key in self._pending:
                raise RuntimeError("PERSISTENT reality-delta pending candidate requires admission")
            committed = self._committed.get(key)
            parent_matches = bool(
                committed is not None
                and parent is not None
                and parent == committed.response_id
            )
            envelope = transport_envelope(
                current,
                previous=(committed.snapshot if parent_matches else None),
                force_full=not parent_matches,
            )
        if parent_matches and envelope.get("mode") != DELTA_MODE:
            raise RuntimeError("PERSISTENT reality-delta healthy continuation did not produce delta transport")
        if not parent_matches and envelope.get("mode") != FULL_MODE:
            raise RuntimeError("PERSISTENT reality-delta re-anchor did not produce full transport")
        return PreparedRealityTransport(
            scope_key=key,
            parent_response_id=parent,
            current_snapshot=current,
            envelope=envelope,
        )

    def stage_candidate(
        self,
        prepared: PreparedRealityTransport,
        *,
        response_id: str,
    ) -> None:
        response = str(response_id or "").strip()
        if not response:
            raise ValueError("PERSISTENT reality-delta response candidate requires response_id")
        key = prepared.scope_key
        with self._lock:
            if key in self._pending:
                raise RuntimeError("PERSISTENT reality-delta candidate already staged")
            committed = self._committed.get(key)
            if prepared.mode == DELTA_MODE:
                if committed is None:
                    raise RuntimeError("PERSISTENT reality-delta lost its committed base before staging")
                if prepared.parent_response_id != committed.response_id:
                    raise RuntimeError("PERSISTENT reality-delta provider parent drift before staging")
                reconstructed = reconstruct_snapshot(committed.snapshot, prepared.envelope)
            elif prepared.mode == FULL_MODE:
                reconstructed = reconstruct_snapshot(None, prepared.envelope)
            else:
                raise RuntimeError("PERSISTENT reality-delta prepared mode is unsupported")
            if reconstructed != prepared.current_snapshot:
                raise RuntimeError("PERSISTENT reality-delta prepared snapshot reconstruction mismatch")
            if snapshot_sha256(reconstructed) != snapshot_sha256(prepared.current_snapshot):
                raise RuntimeError("PERSISTENT reality-delta prepared snapshot identity mismatch")
            self._pending[key] = _CommittedReality(
                response_id=response,
                snapshot=_copy_snapshot(prepared.current_snapshot),
            )

    def commit_candidate(self, *, run_id: str, task_id: str, response_id: str) -> None:
        key = _scope(run_id, task_id)
        response = str(response_id or "").strip()
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                raise RuntimeError("PERSISTENT reality-delta has no pending candidate to commit")
            if response != pending.response_id:
                raise RuntimeError("PERSISTENT reality-delta commit response identity mismatch")
            self._pending.pop(key, None)
            self._committed[key] = _CommittedReality(
                response_id=pending.response_id,
                snapshot=_copy_snapshot(pending.snapshot),
            )

    def reject_candidate(self, *, run_id: str, task_id: str, response_id: str) -> None:
        key = _scope(run_id, task_id)
        response = str(response_id or "").strip()
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                return
            if response != pending.response_id:
                raise RuntimeError("PERSISTENT reality-delta reject response identity mismatch")
            self._pending.pop(key, None)

    def clear_scope(self, *, run_id: str, task_id: str) -> None:
        """Drop all transport memory so the next call must send a full snapshot."""
        key = _scope(run_id, task_id)
        with self._lock:
            self._pending.pop(key, None)
            self._committed.pop(key, None)

    def committed_identity(self, *, run_id: str, task_id: str) -> dict[str, str] | None:
        """Evidence-only state projection; never used to infer task semantics."""
        key = _scope(run_id, task_id)
        with self._lock:
            committed = self._committed.get(key)
            if committed is None:
                return None
            return {
                "response_id": committed.response_id,
                "snapshot_sha256": snapshot_sha256(committed.snapshot),
            }


__all__ = ["PreparedRealityTransport", "RealityDeltaTransportState", "ScopeKey"]
