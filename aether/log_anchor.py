from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .hashing import canonical_json_bytes, sha256_hex


def compute_log_root(events: List[Dict]) -> str:
    """SHA-256 over ordered event hashes."""
    event_hashes = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_hashes.append(sha256_hex(canonical_json_bytes(event)))
    return sha256_hex(canonical_json_bytes(event_hashes))


def anchor_log(log_root: str, anchor_sink: Path) -> None:
    """Write log root to append-only anchor sink. Prod only."""
    anchor_sink.parent.mkdir(parents=True, exist_ok=True)
    with anchor_sink.open("a", encoding="utf-8") as handle:
        handle.write(f"{log_root}\n")


def verify_anchor(log_root: str, anchor_sink: Path) -> bool:
    """Verify log root matches anchored value."""
    if not anchor_sink.exists():
        return False
    lines = [line.strip() for line in anchor_sink.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return False
    return lines[-1] == log_root
