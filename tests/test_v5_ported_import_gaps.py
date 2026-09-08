"""Deterministic custody gate for the archived V5 reference corpus.

The superseded V5 API topology is preserved byte-for-byte as non-collectable
reference sources. Current production behavior is qualified through maintained
Aether tests bound by V5_REPLACEMENT_COVERAGE_V1.json; no parallel V5 harness or
compatibility shim is permitted.
"""

from importlib.util import find_spec
from pathlib import Path


def test_v5_reference_package_is_not_a_parallel_harness() -> None:
    assert find_spec("aether_upgrade") is None, (
        "aether_upgrade appeared as a parallel harness; retained behavior "
        "must remain implemented and tested in canonical aether"
    )


def test_v5_reference_sources_remain_visible_but_noncollectable() -> None:
    root = Path(__file__).with_name("v5_ported")
    references = sorted(root.glob("reference_test_*.py"))
    assert len(references) == 23
    assert (root / "reference_conftest.py").is_file()
    assert (root / "V5_PORT_MANIFEST.md").is_file()
    assert (root / "V5_REPLACEMENT_COVERAGE_V1.json").is_file()
    assert not list(root.glob("test_*.py"))
    assert not (root / "conftest.py").exists()
