from __future__ import annotations

from typing import Any, List, Sequence

from .dlp import DlpHit, simulate_dlp_hits
from .hashes import stable_hash


def redact_text(text: str, hits: Sequence[DlpHit] | None = None) -> str:
    if hits is None:
        hits = simulate_dlp_hits(text)
    if not hits:
        return text

    # Replace from the back to keep offsets stable.
    redacted = text
    for hit in sorted(hits, key=lambda item: (item.start, item.end), reverse=True):
        token = f"[REDACTED:{hit.rule}]"
        redacted = redacted[: hit.start] + token + redacted[hit.end :]
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes):
        return redact_text(value.decode("utf-8", errors="replace"))
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, dict):
        return {key: redact_value(value[key]) for key in sorted(value)}
    return value


def redaction_hash(value: Any) -> str:
    return stable_hash(redact_value(value))
