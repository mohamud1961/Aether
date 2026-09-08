"""Production suite must exercise the root Aether package directly."""
from pathlib import Path
import aether
_ROOT = Path(__file__).resolve().parents[1]
_MODULE = Path(aether.__file__).resolve()
if _ROOT not in _MODULE.parents:
    raise RuntimeError(f"tests imported Aether outside checkout: {_MODULE}")
