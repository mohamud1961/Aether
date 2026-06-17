"""runner - Shared infrastructure constant across experiments.

Compatibility note: several historical ``runner.<module>`` files now live in
subpackages such as ``runner.legacy_packets``, ``runner.substrate``, and
``runner.kernel``. Keep those directories on the package search path so old
root imports continue to resolve while callers migrate to canonical paths.
"""

from __future__ import annotations

from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parent
for _relative in ("legacy_packets", "substrate", "kernel"):
    _candidate = str(_ROOT / _relative)
    if _candidate not in __path__:
        __path__.append(_candidate)
