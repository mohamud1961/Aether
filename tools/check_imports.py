"""Fail if a package imports upward: eval tooling and the harness must stay independent.

The harness (`aether`) never imports the eval tooling (`harness_evals`), and the eval tooling
never imports the harness. Task graders under `evals/` import neither.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = {
    "aether": {"harness_evals"},
    "harness_evals": {"aether"},
    "evals": {"aether", "harness_evals"},
}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def main() -> int:
    violations = []
    for package, banned in FORBIDDEN.items():
        base = ROOT / package
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            bad = imported_roots(path) & banned
            if bad:
                violations.append(f"{path.relative_to(ROOT)} imports {', '.join(sorted(bad))}")
    for line in violations:
        print(line)
    print(f"dependency direction: {'FAIL' if violations else 'ok'} ({len(violations)} violations)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
