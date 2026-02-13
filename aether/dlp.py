from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from .policy_config import PolicyConfig


@dataclass(frozen=True)
class DlpScanResult:
    hit: bool
    pattern_types: List[str]
    blocked: bool


_DLP_PATTERNS = [
    ("PASSWORD", re.compile(r"(?i)(?:password|passwd|pwd)\s*[:=]\s*\S+")),
    ("API_KEY", re.compile(r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*\S+")),
    ("TOKEN", re.compile(r"(?i)(?:token|bearer)\s*[:=]\s*\S+")),
    ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA) PRIVATE KEY-----")),
]


def scan_output(output: str, policy: PolicyConfig) -> DlpScanResult:
    """Scan final output for sensitive data patterns."""
    if not isinstance(output, str):
        output = str(output)

    pattern_types: List[str] = []
    for pattern_type, compiled in _DLP_PATTERNS:
        if compiled.search(output):
            pattern_types.append(pattern_type)

    hit = bool(pattern_types)
    blocked = hit
    return DlpScanResult(hit=hit, pattern_types=sorted(set(pattern_types)), blocked=blocked)
