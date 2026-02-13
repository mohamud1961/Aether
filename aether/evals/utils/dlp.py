from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Sequence


@dataclass(frozen=True)
class DlpHit:
    rule: str
    match: str
    start: int
    end: int


_DLP_RULES: Sequence[tuple[str, re.Pattern[str]]] = (
    ("API_KEY", re.compile(r"\bsk-[A-Za-z0-9]{12,}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)


def simulate_dlp_hits(value: Any) -> List[DlpHit]:
    text = _to_text(value)
    hits: List[DlpHit] = []

    for rule_name, pattern in _DLP_RULES:
        for match in pattern.finditer(text):
            hits.append(
                DlpHit(
                    rule=rule_name,
                    match=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

    hits.sort(key=lambda hit: (hit.start, hit.end, hit.rule, hit.match))
    return hits


def contains_dlp(value: Any) -> bool:
    return bool(simulate_dlp_hits(value))


def block_on_dlp(value: Any) -> dict[str, Any]:
    hits = simulate_dlp_hits(value)
    return {
        "blocked": bool(hits),
        "hits": [
            {
                "rule": hit.rule,
                "match": hit.match,
                "start": hit.start,
                "end": hit.end,
            }
            for hit in hits
        ],
    }


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        for key in sorted(value):
            parts.append(f"{key}:{_to_text(value[key])}")
        return "\n".join(parts)
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_to_text(item) for item in value)
    return str(value)
