"""Opt-in arm that stops pushing unrequested bulk in the per-turn ``[context_packet]``.

Under ``packet_lean_v1`` two fields of the model-visible packet are shortened; nothing the
model can obtain on request is removed:

* ``linked_history.artifacts_present`` (a full workspace listing) becomes a count, up to
  ``RECENT_PATH_LIMIT`` paths the solver's own actions changed (newest first), and a
  pointer to the existing ``run_command`` action for listing files.
* ``evidence_index`` keeps the newest ``EVIDENCE_KEEP`` rows plus a count of older ones;
  older receipts stay reachable through ``query_history`` and ``read_output receipt:<id>``.

The projection is applied to a copy at the request boundary only. The canonical packet used
for submission binding and finish validation is never touched, so every evidence_ref that
resolved before still resolves.
"""
from __future__ import annotations

import argparse
from copy import copy
from typing import Any, Mapping

CONTROL = "control"
PACKET_LEAN_V1 = "packet_lean_v1"
SUPPORTED_PACKET_MODES = frozenset({CONTROL, PACKET_LEAN_V1})
PACKET_MODE_ENV = "AETHER_G4_PACKET_MODE"
RECENT_PATH_LIMIT = 40
EVIDENCE_KEEP = 20
LIST_FILES_VIA = "run_command (for example: ls, find)"
OLDER_EVIDENCE_VIA = "query_history (empty query lists recent receipts); read_output receipt:<receipt_id>"


class PacketModeError(ValueError):
    """An unknown mode or an unexpected packet shape was supplied."""


def resolve_packet_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(PACKET_MODE_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_PACKET_MODES:
        raise PacketModeError(f"unknown packet mode: {selected!r}")
    return selected


def add_packet_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--packet-mode", choices=sorted(SUPPORTED_PACKET_MODES), default=CONTROL,
        help="shorten the per-turn workspace listing and old evidence rows in the context packet (opt-in)",
    )


def build_packet_launch_binding(mode: str | None) -> dict[str, Any]:
    selected = resolve_packet_mode(mode)
    return {"packet_mode": selected, "env": {PACKET_MODE_ENV: selected}, "manifest": {"packet_mode": selected}}


def recent_changed_paths(ledger: Any, limit: int = RECENT_PATH_LIMIT) -> list[str]:
    """Paths named by the solver's action receipts, newest first, minus removed ones."""
    present = ledger.current_artifacts()
    removed = set(ledger.removed_paths()) - present
    seen: set[str] = set()
    out: list[str] = []
    for receipt in reversed(ledger.all_receipts()):
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        names = [*(payload.get("modified_paths") or ()), *(payload.get("artifact_paths") or ())]
        for raw in sorted({str(item).strip() for item in names}, reverse=True):
            if raw and raw not in seen and raw not in removed:
                seen.add(raw)
                out.append(raw)
                if len(out) >= limit:
                    return out
    return out


def lean_packet(packet: Mapping[str, Any], recent_paths: list[str]) -> dict[str, Any]:
    """Return a shallow copy with the two bulky fields shortened; the input is not mutated."""
    out = dict(packet)
    linked = out.get("linked_history")
    if isinstance(linked, Mapping) and "artifacts_present" in linked:
        artifacts = linked["artifacts_present"]
        if not isinstance(artifacts, list):
            raise PacketModeError("artifacts_present is not a list; refusing to guess a lean view")
        names = [str(item) for item in artifacts]
        known = set(names)
        shown = list(recent_paths[:RECENT_PATH_LIMIT])
        if not shown:  # no change tracking hit: deterministic first paths
            shown = sorted(known)[:RECENT_PATH_LIMIT]
        linked = copy(linked) if not isinstance(linked, dict) else dict(linked)
        linked["artifacts_present"] = {
            "count": len(known),
            "recently_changed": shown,
            "omitted": len(known - set(shown)),
            "how_to_list": LIST_FILES_VIA,
        }
        out["linked_history"] = linked
    rows = out.get("evidence_index")
    if rows is not None:
        if not isinstance(rows, list):
            raise PacketModeError("evidence_index is not a list; refusing to guess a lean view")
        if len(rows) > EVIDENCE_KEEP:
            out["evidence_index"] = list(rows[:EVIDENCE_KEEP])
            out["evidence_index_older"] = {"count": len(rows) - EVIDENCE_KEEP, "retrieve_via": OLDER_EVIDENCE_VIA}
    return out
