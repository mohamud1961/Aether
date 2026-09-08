#!/usr/bin/env python3
"""Emit a deterministic static import-graph receipt for the production package.

This report answers a narrow diligence question: which tracked Python modules are
statically reachable from Aether's canonical public entrypoints? It is not a
runtime tracer and it deliberately does not label unreached modules as dead;
optional/dynamic loading can make static reachability incomplete.
"""
from __future__ import annotations

import argparse
import ast
from collections import deque
from importlib.util import resolve_name
import json
import os
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "aether"
DEFAULT_ROOTS = ("aether", "aether.launch", "aether.harbor_agent")
SCHEMA_VERSION = "aether.runtime.static_import_graph.v1"


def _module_name(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_package(module: str, path: Path) -> str:
    if path.name == "__init__.py":
        return module
    return module.rpartition(".")[0]


def _candidate_module(target: str, known: set[str]) -> str | None:
    value = target.strip()
    if value in known:
        return value
    while "." in value:
        value = value.rpartition(".")[0]
        if value in known:
            return value
    return None


def _resolved_relative(name: str, package: str) -> str | None:
    try:
        return resolve_name(name, package)
    except (ImportError, ValueError):
        return None


def _imports_for(path: Path, module: str, known: set[str]) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    package = _module_package(module, path)
    imports: set[str] = set()

    def add(target: str | None) -> None:
        if not target:
            return
        candidate = _candidate_module(target, known)
        if candidate is not None and candidate != module:
            imports.add(candidate)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "aether" or alias.name.startswith("aether."):
                    add(alias.name)
            continue

        if isinstance(node, ast.ImportFrom):
            if node.level:
                prefix = "." * node.level + (node.module or "")
                base = _resolved_relative(prefix, package)
            else:
                base = node.module
            if not base or not (base == "aether" or base.startswith("aether.")):
                continue
            add(base)
            for alias in node.names:
                if alias.name == "*":
                    continue
                add(f"{base}.{alias.name}")
            continue

        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        is_dynamic_import = (
            isinstance(func, ast.Name) and func.id in {"import_module", "__import__"}
        ) or (
            isinstance(func, ast.Attribute) and func.attr == "import_module"
        )
        if not is_dynamic_import:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            continue
        target = first.value
        if target.startswith("."):
            target = _resolved_relative(target, package) or ""
        if target == "aether" or target.startswith("aether."):
            add(target)

    return imports


def _walk_reachable(roots: Iterable[str], graph: dict[str, set[str]]) -> set[str]:
    reachable: set[str] = set()
    queue: deque[str] = deque(root for root in roots if root in graph)
    while queue:
        module = queue.popleft()
        if module in reachable:
            continue
        reachable.add(module)
        for child in sorted(graph.get(module, ())):
            if child not in reachable:
                queue.append(child)
    return reachable


def build_report() -> dict[str, object]:
    paths = sorted(PACKAGE_ROOT.rglob("*.py"))
    path_by_module = {_module_name(path): path for path in paths}
    known = set(path_by_module)
    graph = {
        module: _imports_for(path, module, known)
        for module, path in sorted(path_by_module.items())
    }
    roots = [root for root in DEFAULT_ROOTS if root in graph]
    reachable = _walk_reachable(roots, graph)

    inbound: dict[str, set[str]] = {module: set() for module in graph}
    for source, targets in graph.items():
        for target in targets:
            inbound.setdefault(target, set()).add(source)

    modules = []
    for module in sorted(graph):
        path = path_by_module[module]
        modules.append(
            {
                "module": module,
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "reachable_from_canonical_roots": module in reachable,
                "imports": sorted(graph[module]),
                "imported_by": sorted(inbound.get(module, ())),
            }
        )

    unreached = sorted(known - reachable)
    no_inbound = sorted(
        module
        for module in known
        if not inbound.get(module) and module not in roots
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_commit": os.environ.get("GITHUB_SHA", ""),
        "analysis_kind": "static_ast_import_reachability",
        "canonical_roots": roots,
        "production_python_module_count": len(known),
        "production_python_bytes": sum(path.stat().st_size for path in paths),
        "reachable_module_count": len(reachable),
        "unreached_module_count": len(unreached),
        "unreached_modules": unreached,
        "no_static_inbound_count": len(no_inbound),
        "no_static_inbound_modules": no_inbound,
        "interpretation": (
            "Unreached/no-inbound modules are review candidates, not proof of dead code; "
            "dynamic, optional, registry or string-based loading can be invisible to this analysis."
        ),
        "modules": modules,
    }


def _text_summary(report: dict[str, object]) -> str:
    roots = ", ".join(report["canonical_roots"])
    unreached = report["unreached_modules"]
    no_inbound = report["no_static_inbound_modules"]
    lines = [
        "Aether static runtime-surface receipt",
        f"schema={report['schema_version']}",
        f"source_commit={report['source_commit']}",
        f"canonical_roots={roots}",
        f"production_python_modules={report['production_python_module_count']}",
        f"production_python_bytes={report['production_python_bytes']}",
        f"reachable_modules={report['reachable_module_count']}",
        f"unreached_modules={report['unreached_module_count']}",
        f"no_static_inbound_modules={report['no_static_inbound_count']}",
        "",
        "Unreached from canonical roots (static analysis only):",
        *([f"- {name}" for name in unreached] or ["- none"]),
        "",
        "No static inbound edge (excluding roots):",
        *([f"- {name}" for name in no_inbound] or ["- none"]),
        "",
        str(report["interpretation"]),
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--text", dest="text_path", type=Path)
    args = parser.parse_args()

    report = build_report()
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    text = _text_summary(report)

    if args.json_path:
        args.json_path.write_text(json_text, encoding="utf-8")
    else:
        print(json_text, end="")
    if args.text_path:
        args.text_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
