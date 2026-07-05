#!/usr/bin/env python3
"""Static generic capability audit for an official task corpus.

This uses task.toml, instruction.md, and environment-visible files as a coverage
corpus.  It intentionally ignores solution/ and tests/ contents and does not
emit task-specific success logic.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aether_next.task_capability import classify_capability_needs, flatten_task_toml, required_tool_hints


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _environment_files(task_dir: Path) -> tuple[str, ...]:
    files: list[str] = []
    for base_name in ("environment",):
        base = task_dir / base_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                files.append(str(path.relative_to(task_dir)))
    # Top-level non-hidden artifacts other than task metadata are visible surface too.
    for path in task_dir.iterdir():
        if path.is_file() and path.name not in {"instruction.md", "task.toml"}:
            files.append(path.name)
    return tuple(sorted(set(files)))


def _readiness(needs: list[str]) -> str:
    if any(cap in needs for cap in ("qemu_vm", "video_processing", "background_service", "http_service", "ssh_or_telnet_service")):
        return "needs_p2_verifier_or_service_support"
    if any(cap in needs for cap in ("long_running_command", "compiler_build", "ml_training_or_inference", "scientific_computing")):
        return "needs_long_command_budget_and_verifier_execution"
    if any(cap in needs for cap in ("image_processing", "ocr_pdf_document", "binary_reverse_engineering")):
        return "needs_generic_artifact_probe_support"
    return "locally_ready_or_model_hard"


def audit_task(task_dir: Path) -> dict[str, str]:
    instruction = _read_text(task_dir / "instruction.md")
    task_toml = _load_toml(task_dir / "task.toml")
    metadata = flatten_task_toml(task_toml)
    visible_files = _environment_files(task_dir)
    needs = classify_capability_needs(instruction, task_metadata=metadata, visible_files=visible_files)
    caps = [need.capability for need in needs]
    tools = required_tool_hints(needs)
    verifier_needs = sorted({tool for need in needs for tool in need.verifier_needs})
    budget = metadata.get("resource_budget", {}) if isinstance(metadata.get("resource_budget"), dict) else {}
    return {
        "task_name": task_dir.name,
        "category": str(metadata.get("category", "")),
        "difficulty": str(metadata.get("difficulty", "")),
        "tags": ";".join(metadata.get("tags", ()) or ()),
        "agent_timeout_sec": str(metadata.get("agent_timeout_sec", "")),
        "verifier_timeout_sec": str(metadata.get("verifier_timeout_sec", "")),
        "build_timeout_sec": str(budget.get("build_timeout_sec", "")),
        "docker_image": str(budget.get("docker_image", "")),
        "visible_environment_files": str(len(visible_files)),
        "capability_classes": ";".join(caps),
        "required_tool_hints": ";".join(tools),
        "verifier_capability_needs": ";".join(verifier_needs),
        "readiness": _readiness(caps),
        "notes": "generic coverage audit; no solution/tests inspected",
    }


def write_outputs(rows: list[dict[str, str]], csv_path: Path, md_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "task_name", "category", "difficulty", "tags", "agent_timeout_sec", "verifier_timeout_sec",
        "build_timeout_sec", "docker_image", "visible_environment_files", "capability_classes",
        "required_tool_hints", "verifier_capability_needs", "readiness", "notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    cap_counts: Counter[str] = Counter()
    readiness_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()
    verifier_counts: Counter[str] = Counter()
    for row in rows:
        readiness_counts[row["readiness"]] += 1
        for cap in filter(None, row["capability_classes"].split(";")):
            cap_counts[cap] += 1
        for tool in filter(None, row["required_tool_hints"].split(";")):
            tool_counts[tool] += 1
        for need in filter(None, row["verifier_capability_needs"].split(";")):
            verifier_counts[need] += 1
    lines = [
        "# Official Task Generic Capability Audit (Local Static)",
        "",
        "This audit uses official tasks as a generic coverage corpus. It does not inspect solution/ or tests/ contents and does not encode task-name-specific behavior.",
        "",
        f"Tasks audited: {len(rows)}",
        "",
        "## Readiness buckets",
    ]
    for key, count in readiness_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines += ["", "## Capability class coverage"]
    for key, count in cap_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines += ["", "## Most common required tool hints"]
    for key, count in tool_counts.most_common(40):
        lines.append(f"- {key}: {count}")
    lines += ["", "## Verifier capability needs"]
    for key, count in verifier_counts.most_common(40):
        lines.append(f"- {key}: {count}")
    lines += ["", "## Per-task table", "", "| task | category | capability classes | readiness |", "|---|---|---|---|"]
    for row in sorted(rows, key=lambda r: r["task_name"]):
        lines.append(f"| {row['task_name']} | {row['category']} | {row['capability_classes']} | {row['readiness']} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks_root", type=Path)
    parser.add_argument("--csv", type=Path, default=Path("OFFICIAL_TASK_CAPABILITY_AUDIT_LOCAL.csv"))
    parser.add_argument("--md", type=Path, default=Path("OFFICIAL_TASK_CAPABILITY_AUDIT_LOCAL.md"))
    args = parser.parse_args()
    task_dirs = sorted(path for path in args.tasks_root.iterdir() if (path / "task.toml").exists())
    rows = [audit_task(path) for path in task_dirs]
    write_outputs(rows, args.csv, args.md)
    print(json.dumps({"tasks": len(rows), "csv": str(args.csv), "md": str(args.md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
