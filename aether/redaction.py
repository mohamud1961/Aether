from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


REDACTION_PATTERNS = [
    (r"(?i)(?:password|passwd|pwd)\s*[:=]\s*\S+", "[REDACTED:PASSWORD]", "PASSWORD"),
    (r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*\S+", "[REDACTED:API_KEY]", "API_KEY"),
    (r"(?i)(?:token|bearer)\s*[:=]\s*\S+", "[REDACTED:TOKEN]", "TOKEN"),
    (r"(?i)(?:secret)\s*[:=]\s*\S+", "[REDACTED:SECRET]", "SECRET"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED:AWS_KEY]", "AWS_KEY"),
    (r"(?i)aws_secret_access_key\s*[:=]\s*[A-Za-z0-9/+=]{20,}", "[REDACTED:AWS_SECRET]", "AWS_SECRET"),
    (r"-----BEGIN (?:RSA|EC|OPENSSH|DSA) PRIVATE KEY-----", "[REDACTED:PRIVATE_KEY]", "PRIVATE_KEY"),
]


@dataclass(frozen=True)
class RedactionRecord:
    redaction_type: str
    count: int


def redact(text: str) -> Tuple[str, List[RedactionRecord]]:
    """Returns redacted text and list of redactions applied."""
    if not isinstance(text, str) or not text:
        return text, []

    redacted = text
    records: List[RedactionRecord] = []
    for pattern, replacement, redaction_type in REDACTION_PATTERNS:
        compiled = re.compile(pattern)
        redacted, count = compiled.subn(replacement, redacted)
        if count > 0:
            records.append(RedactionRecord(redaction_type=redaction_type, count=count))

    return redacted, records
