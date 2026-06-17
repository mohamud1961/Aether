from __future__ import annotations

import ast
import importlib
import sys
from contextlib import contextmanager
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

MODULE_PAIRS = [
    ("runner.aether2.cleanup_accounting", "harness.aether2.runtime.cleanup_accounting"),
    ("runner.aether2.bridge_harbor", "harness.aether2.runtime.bridge_harbor"),
    ("runner.aether2.compactor", "harness.aether2.runtime.compactor"),
    ("runner.aether2.context", "harness.aether2.runtime.context"),
    ("runner.aether2.escalation", "harness.aether2.runtime.escalation"),
    ("runner.aether2.executor", "harness.aether2.runtime.executor"),
    ("runner.aether2.metrics", "harness.aether2.runtime.metrics"),
    ("runner.aether2.orientation", "harness.aether2.runtime.orientation"),
    ("runner.aether2.prompts", "harness.aether2.runtime.prompts"),
    ("runner.aether2.verify", "harness.aether2.runtime.verify"),
    ("runner.aether2.jobs", "harness.aether2.runtime.jobs"),
    ("runner.aether2.loop", "harness.aether2.control.loop"),
    ("runner.aether2.model_client", "harness.aether2.runtime.model_client"),
    ("runner.aether2.sessions", "harness.aether2.runtime.sessions"),
    ("runner.aether2.tools", "harness.aether2.tools.native"),
]


@contextmanager
def _without_modules(*module_names: str):
    saved = {name: sys.modules.pop(name) for name in module_names if name in sys.modules}
    try:
        yield
    finally:
        sys.modules.update(saved)


def test_runner_and_harness_runtime_modules_share_identity() -> None:
    for legacy_name, canonical_name in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_name)
        canonical_module = importlib.import_module(canonical_name)

        assert legacy_module is canonical_module
        assert legacy_module.__name__ == canonical_name


def test_runner_and_harness_runtime_modules_share_identity_in_both_import_orders() -> None:
    for legacy_name, canonical_name in MODULE_PAIRS:
        for first_name, second_name in ((legacy_name, canonical_name), (canonical_name, legacy_name)):
            with _without_modules(legacy_name, canonical_name):
                first_module = importlib.import_module(first_name)
                second_module = importlib.import_module(second_name)

            assert first_module is second_module
            assert first_module.__name__ == canonical_name


def test_public_aether2_objects_are_shared_between_packages() -> None:
    runner_pkg = importlib.import_module("runner.aether2")
    harness_pkg = importlib.import_module("harness.aether2")
    control_pkg = importlib.import_module("harness.aether2.control")
    runtime_pkg = importlib.import_module("harness.aether2.runtime")
    tools_pkg = importlib.import_module("harness.aether2.tools")

    assert runner_pkg.build_fact_ledger is runtime_pkg.build_fact_ledger
    assert runner_pkg.build_scorecard is runtime_pkg.build_scorecard
    assert runner_pkg.orient is runtime_pkg.orient
    assert runner_pkg.verify_fresh_context is runtime_pkg.verify_fresh_context
    assert runner_pkg.HANDOFF_TEMPLATE is runtime_pkg.HANDOFF_TEMPLATE
    assert runner_pkg.ContainerExecutor is harness_pkg.ContainerExecutor
    assert runner_pkg.JobRegistry is harness_pkg.JobRegistry
    assert runner_pkg.Aether2ModelClient is harness_pkg.Aether2ModelClient
    assert runner_pkg.ContextManager is harness_pkg.ContextManager
    assert runner_pkg.TaskSpec is harness_pkg.TaskSpec
    assert runner_pkg.SessionRegistry is harness_pkg.SessionRegistry
    assert runner_pkg.ExecutionContext is harness_pkg.ExecutionContext
    assert runner_pkg.RunResult is harness_pkg.RunResult
    assert runner_pkg.ToolInvocationRecord is harness_pkg.ToolInvocationRecord
    assert runner_pkg.run_aether2_loop is harness_pkg.run_aether2_loop
    assert runner_pkg.run_aether2_loop is control_pkg.run_aether2_loop
    assert runner_pkg.TOOL_NAMES is harness_pkg.TOOL_NAMES
    assert runner_pkg.TOOL_SCHEMAS is harness_pkg.TOOL_SCHEMAS
    assert runner_pkg.dispatch is harness_pkg.dispatch
    assert runner_pkg.dispatch is tools_pkg.dispatch
    assert runner_pkg.run_aether2_loop.__module__ == "harness.aether2.control.loop"
    assert runner_pkg.dispatch.__module__ == "harness.aether2.tools.native"


def test_control_and_tools_monkeypatches_are_shared(monkeypatch) -> None:
    legacy_loop = importlib.import_module("runner.aether2.loop")
    canonical_loop = importlib.import_module("harness.aether2.control.loop")
    legacy_tools = importlib.import_module("runner.aether2.tools")
    canonical_tools = importlib.import_module("harness.aether2.tools.native")

    monkeypatch.setattr(legacy_loop, "STEP_CAP", 7)
    assert canonical_loop.STEP_CAP == 7

    sentinel = object()
    monkeypatch.setattr(canonical_tools, "dispatch", sentinel)
    assert legacy_tools.dispatch is sentinel


def test_runner_package_aggregates_canonical_public_modules_only() -> None:
    source = (REPO_ROOT / "runner/aether2/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="runner/aether2/__init__.py")

    legacy_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("runner.aether2")
    ]
    canonical_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("harness.aether2")
    ]

    assert not legacy_imports
    assert canonical_imports


def test_legacy_aether2_modules_are_shims_not_duplicate_implementations() -> None:
    for path in sorted((REPO_ROOT / "runner/aether2").glob("*.py")):
        if path.name == "__init__.py":
            continue

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        defs = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        assert not defs, f"{path} still defines runtime objects: {defs}"
        assert "_sys.modules[__name__]" in source or "sys.modules[__name__]" in source
