from __future__ import annotations

from typing import Mapping, Sequence


BENCHIFY_PATTERN_REGISTRY_VERSION = "v1.1.0"

# Static banned-pattern registry for CT-04. CT-04 must only rely on this registry.
BENCHIFY_BANNED_PATTERNS: Sequence[str] = (
    "BENCHIFY_STATIC_ROUTE",
    "TASK_ID_ROUTE",
    "BENCHMARK_ID_ROUTE",
    "HELDOUT_FINGERPRINT_ROUTE",
)


def matches_benchify_pattern(event: Mapping[str, object]) -> bool:
    violation_code = str(event.get("violation_code", "")).upper()
    if violation_code in BENCHIFY_BANNED_PATTERNS:
        return True

    detail = event.get("violation_detail")
    if isinstance(detail, Mapping):
        pattern = str(detail.get("pattern", "")).upper()
        if pattern in BENCHIFY_BANNED_PATTERNS:
            return True

    return False
