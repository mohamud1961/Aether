from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class VerifierDefinition:
    name: str
    command: List[str]
    timeout_ms: Optional[int] = None


@dataclass(frozen=True)
class VerifierPlan:
    verifiers: List[VerifierDefinition]
