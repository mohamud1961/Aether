#!/usr/bin/env python3
"""Fail-closed audit of Aether's installed production surface."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "aether"
PYPROJECT = ROOT / "pyproject.toml"
FORBIDDEN_IMPORT_PREFIXES = (
    "aether_next",
    "aether_next_build",
    "harness.aether2",
    "runner",
    "research",
    "evals",
    "eval_suite",
)
FORBIDDEN_MODULE_WORDS = ("architect", "workbench")
FORBIDDEN_PATH_LITERALS = (
    "/Users/",
    "/home/",
    "/mnt/aether",
    ".gateway-runtime/worktrees",
    "aether_next_build/",
    "harness/aether2",
    "runner/adapters",
)
FORBIDDEN_CONTROL_TOKENS = (
    "solver_v1",
    "AETHER_COMPLETION_DOCTRINE",
    "RuntimeConfigIR",
    "WorkflowPolicy",
    "ReconfigurePolicy",
    "WORKFLOW_MODES",
    "MODEL_TIERS",
    "thin_aether_v11",
    "PCR_WORKING_STATE_SCHEMA",
    "pcr_working_state_policy",
    "capability_mode",
)
FORBIDDEN_RUNTIME_SELECTOR_PATTERNS = (
    "compiled.solver_turn_protocol",
    'getattr(compiled, "solver_turn_protocol"',
    "getattr(compiled, 'solver_turn_protocol'",
)

NEUTRALITY_BOARD = ROOT / "tracking/handoffs/c0_board_aether_20_task_board_v1.json"
A5_B5_HANDOFF = ROOT / "tracking/collab/aether_a5_forensic_audit_20260830/A5_B5_COMBINED_HANDOFF_20260831.md"
VERIFIER_PROMOTION = ROOT / "tracking/handoffs/20260729_verifier_promotion_71a55d38/PROMOTION.json"
MASTER_PLAN = ROOT / "tracking/collab/aether_a5_forensic_audit_20260830/AETHER_FULL_PHASE_PLAN_SIMPLIFICATION_AND_PERFORMANCE_V1_20260901.md"


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source_label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _task_values(value: object) -> set[str]:
    rows: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"task", "task_id"} and isinstance(item, str) and item and "/" not in item and len(item) < 100:
                rows.add(item)
            rows.update(_task_values(item))
    elif isinstance(value, list):
        for item in value:
            rows.update(_task_values(item))
    return rows


def benchmark_neutrality_task_ids() -> tuple[tuple[str, ...], list[dict[str, object]]]:
    """Derive the audit denylist from frozen evidence outside production.

    Aether never imports these manifests. The release checker does, so board
    evolution cannot silently outgrow a hand-maintained tuple in this script.
    """
    for path in (NEUTRALITY_BOARD, A5_B5_HANDOFF, VERIFIER_PROMOTION, MASTER_PLAN):
        if not path.is_file():
            fail(f"benchmark-neutrality authority missing: {path.relative_to(ROOT)}")

    ids: set[str] = set()
    sources: list[dict[str, object]] = []

    board = json.loads(NEUTRALITY_BOARD.read_text(encoding="utf-8"))
    slots = board.get("slots")
    frontier = board.get("frontier_selection_authority")
    if not isinstance(slots, list) or len(slots) != int(board.get("slot_count", -1)):
        fail("20-task board slot_count does not match slots")
    if not isinstance(frontier, dict):
        fail("20-task board frontier selection authority missing")
    release_ids = frontier.get("release_task_ids")
    inventory = frontier.get("release_inventory_authority")
    if not isinstance(release_ids, list) or not isinstance(inventory, dict):
        fail("frontier release task inventory missing")
    if len(release_ids) != int(inventory.get("task_count", -1)):
        fail("frontier release task inventory count mismatch")
    slot_ids = {str(row.get("task_id", "")).strip() for row in slots if isinstance(row, dict)}
    if "" in slot_ids or len(slot_ids) != len(slots):
        fail("20-task board contains missing or duplicate task ids")
    ids.update(slot_ids)
    ids.update(str(value).strip() for value in release_ids if str(value).strip())
    sources.append({
        "path": _source_label(NEUTRALITY_BOARD),
        "sha256": _sha256_file(NEUTRALITY_BOARD),
        "slot_count": len(slot_ids),
        "frontier_release_task_count": len(release_ids),
    })

    handoff_text = A5_B5_HANDOFF.read_text(encoding="utf-8")
    handoff_ids = {
        match.group(1)
        for match in re.finditer(r"^\| `([^`]+)` \|", handoff_text, flags=re.MULTILINE)
    }
    if len(handoff_ids) != 10:
        fail(f"A5/B5 handoff task-table count drifted: expected 10, got {len(handoff_ids)}")
    ids.update(handoff_ids)
    sources.append({
        "path": _source_label(A5_B5_HANDOFF),
        "sha256": _sha256_file(A5_B5_HANDOFF),
        "derived_task_count": len(handoff_ids),
    })

    promotion = json.loads(VERIFIER_PROMOTION.read_text(encoding="utf-8"))
    promotion_ids = _task_values(promotion)
    if not promotion_ids:
        fail("historical Verifier promotion contains no derivable task ids")
    ids.update(promotion_ids)
    sources.append({
        "path": _source_label(VERIFIER_PROMOTION),
        "sha256": _sha256_file(VERIFIER_PROMOTION),
        "derived_task_count": len(promotion_ids),
    })

    plan_text = MASTER_PLAN.read_text(encoding="utf-8")
    historical = re.search(r"Historical candidates such as (.+?) may be used only", plan_text)
    if historical is None:
        fail("master plan historical calibration task inventory missing")
    historical_ids = set(re.findall(r"`([^`]+)`", historical.group(1)))
    if not historical_ids:
        fail("master plan historical calibration task inventory empty")
    ids.update(historical_ids)
    sources.append({
        "path": _source_label(MASTER_PLAN),
        "sha256": _sha256_file(MASTER_PLAN),
        "derived_historical_task_count": len(historical_ids),
    })

    return tuple(sorted(ids)), sources


def fail(message: str) -> None:
    raise SystemExit("PRODUCTION_SURFACE_INVALID: " + message)


def imports_for(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            rows.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            rows.append(node.module)
    return rows


def dynamic_package_files(path: Path) -> set[str]:
    """Collect literal package-local files loaded through known dynamic seams."""
    text = path.read_text(encoding="utf-8")
    names = set(re.findall(r"Path\(__file__\)\.with_name\([\"']([^\"']+)[\"']\)", text))
    names.update(re.findall(r"joinpath\([\"']([^\"']+)[\"']\)", text))
    return {name for name in names if "/" not in name and "\\" not in name}


def main() -> None:
    if not (PKG / "__init__.py").is_file():
        fail("root aether package missing")
    py_files = sorted(PKG.rglob("*.py"))
    if not py_files:
        fail("no production Python modules found")

    neutrality_task_ids, neutrality_sources = benchmark_neutrality_task_ids()

    for forbidden_path in ("thin_aether.py", "pcr_working_state.py", "memory_query.py"):
        if (PKG / forbidden_path).exists():
            fail(f"retired compatibility module remains in production: aether/{forbidden_path}")

    dynamic_files: set[str] = set()
    for path in py_files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        lowered = rel.lower()
        if any(word in lowered for word in FORBIDDEN_MODULE_WORDS):
            fail(f"historical cognition module remains in production: {rel}")
        for imported in imports_for(path):
            normalized = imported.lstrip(".")
            if any(normalized == prefix or normalized.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
                fail(f"forbidden production import {imported!r} in {rel}")
            if any(word in normalized.lower().split(".") for word in FORBIDDEN_MODULE_WORDS):
                fail(f"historical cognition import {imported!r} in {rel}")
        for literal in FORBIDDEN_PATH_LITERALS:
            if literal in text:
                fail(f"checkout/legacy path literal {literal!r} in {rel}")
        for token in FORBIDDEN_CONTROL_TOKENS:
            if token in text:
                fail(f"retired control token {token!r} in production module {rel}")
        for pattern in FORBIDDEN_RUNTIME_SELECTOR_PATTERNS:
            if pattern in text:
                fail(f"retired runtime selector {pattern!r} in production module {rel}")
        for task_id in neutrality_task_ids:
            if task_id in text:
                fail(f"benchmark task id {task_id!r} in production module {rel}")
        # Generic IPv4 literals are forbidden except loopback/wildcard addresses.
        for match in re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", text):
            if match not in {"127.0.0.1", "0.0.0.0"}:
                fail(f"hard-coded non-loopback IP {match!r} in {rel}")
        dynamic_files.update(dynamic_package_files(path))

    for name in sorted(dynamic_files):
        # Ignore ordinary importlib-resource metadata that is not package-local.
        if name.endswith((".py", ".json")) and not (PKG / name).is_file():
            fail(f"dynamic package dependency is missing: aether/{name}")

    pyproject = PYPROJECT.read_text(encoding="utf-8")
    if 'aether = "aether.launch:main"' not in pyproject:
        fail("single aether console entrypoint is missing")
    if 'where = ["."]' not in pyproject or 'include = ["aether*"]' not in pyproject:
        fail("package discovery is not rooted exclusively at aether*")
    if "aether_next" in pyproject or "harness-aether2" in pyproject:
        fail("legacy package identity remains in pyproject")

    lock = json.loads((PKG / "harbor_runtime_lock.json").read_text(encoding="utf-8"))
    if lock.get("harbor_version") != "0.20.0":
        fail("Harbor version lock drifted")
    if lock.get("agent_selector") != "aether.harbor_agent:AetherHarborAgent":
        fail("Harbor agent selector is not canonical root aether")
    if lock.get("lifecycle_authority") != "harbor" or lock.get("aether_owns_benchmark_lifecycle") is not False:
        fail("benchmark lifecycle ownership drifted from Harbor")

    schema = json.loads((PKG / "launch_schema.json").read_text(encoding="utf-8"))
    if schema.get("additionalProperties") is not False:
        fail("launch schema root is not fail-closed")
    required = set(schema.get("required", []))
    for key in {"schema_version", "run_id", "package", "runtime", "task", "harbor", "model", "evidence", "provider", "retry", "metadata"}:
        if key not in required:
            fail(f"launch schema missing required field {key!r}")

    print(json.dumps({
        "status": "VALID",
        "production_python_modules": len(py_files),
        "dynamic_package_files": sorted(dynamic_files),
        "harbor_agent_selector": lock["agent_selector"],
        "harbor_version": lock["harbor_version"],
        "console_entrypoint": "aether = aether.launch:main",
        "benchmark_neutrality_task_id_count": len(neutrality_task_ids),
        "benchmark_neutrality_sources": neutrality_sources,
        "benchmark_neutrality_task_ids_sha256": sha256(
            json.dumps(neutrality_task_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
