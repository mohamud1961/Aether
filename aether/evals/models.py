from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class TestExecutionContext:
    artifact_dir: Path
    events: List[Any]
    artifact_store: Any
    enum_registry: Any
    profile: str
    mode: str
    fixture_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TestResult:
    test_id: str
    name: str
    pack: str
    profile: str
    mode: str
    passed: bool
    fail_signature: Optional[str]
    required_events: List[str]
    observed_events: List[str]
    evidence_refs: List[str]
    timings: Optional[Dict[str, float]] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TestCase:
    id: str
    name: str
    pack: str
    objective: str
    required_event_types: Sequence[str]
    run: Callable[[TestExecutionContext], TestResult]
