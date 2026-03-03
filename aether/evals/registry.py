from __future__ import annotations

from functools import lru_cache
from typing import Callable, Dict, List, Sequence

from .models import TestCase
from .packs import (
    audit,
    candidate,
    capability,
    chopshop,
    context,
    contextvnext,
    contract,
    determinism,
    integrity,
    ingest,
    intent,
    interface,
    loop,
    loopvnext,
    phaseworkflow,
    plan,
    security,
    tool,
    toolhardening,
    userstory,
    userstoryvnext,
    verification,
)


PackLoader = Callable[[], Sequence[TestCase]]


PACK_LOADERS: Dict[str, PackLoader] = {
    "contract": contract.list_tests,
    "intent": intent.list_tests,
    "plan": plan.list_tests,
    "tool": tool.list_tests,
    "context": context.list_tests,
    "loop": loop.list_tests,
    "audit": audit.list_tests,
    "security": security.list_tests,
    "candidate": candidate.list_tests,
    "capability": capability.list_tests,
    "userstory": userstory.list_tests,
    "interface": interface.list_tests,
    "ingest": ingest.list_tests,
    "phaseworkflow": phaseworkflow.list_tests,
    "contextvnext": contextvnext.list_tests,
    "toolhardening": toolhardening.list_tests,
    "verification": verification.list_tests,
    "loopvnext": loopvnext.list_tests,
    "determinism": determinism.list_tests,
    "integrity": integrity.list_tests,
    "chopshop": chopshop.list_tests,
    "userstoryvnext": userstoryvnext.list_tests,
}


@lru_cache(maxsize=1)
def _registry() -> Dict[str, List[TestCase]]:
    resolved: Dict[str, List[TestCase]] = {}
    all_ids: set[str] = set()

    for pack_name, loader in PACK_LOADERS.items():
        tests = sorted(list(loader()), key=lambda case: case.id)
        for test in tests:
            if test.pack != pack_name:
                raise ValueError(
                    f"Pack mismatch for test {test.id}: test.pack={test.pack} loader={pack_name}"
                )
            if test.id in all_ids:
                raise ValueError(f"Duplicate test id detected: {test.id}")
            all_ids.add(test.id)
        resolved[pack_name] = tests

    return resolved


def list_packs() -> List[str]:
    return sorted(_registry().keys())


def list_tests(pack: str | None = None) -> List[TestCase]:
    registry = _registry()
    if pack is None or pack == "all":
        tests: List[TestCase] = []
        for pack_name in list_packs():
            tests.extend(registry[pack_name])
        return tests

    if pack not in registry:
        raise KeyError(f"Unknown eval pack: {pack}")
    return list(registry[pack])


def get_test(test_id: str) -> TestCase:
    for test in list_tests():
        if test.id == test_id:
            return test
    raise KeyError(f"Unknown test id: {test_id}")


def resolve(pack: str, test_id: str | None = None) -> List[TestCase]:
    if test_id is not None:
        test = get_test(test_id)
        if pack not in {"all", test.pack}:
            raise ValueError(f"Test {test_id} belongs to pack {test.pack}, not {pack}")
        return [test]

    return list_tests(pack=pack)
