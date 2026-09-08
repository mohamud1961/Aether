#!/usr/bin/env python3
"""Measure the current tracked release surface independently of Git history."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "aether.release.tracked_surface.v1"


def _tracked_paths() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / value.decode("utf-8") for value in raw.split(b"\0") if value]


def _category(rel: str) -> str:
    first = rel.split("/", 1)[0]
    return {
        "aether": "production_runtime",
        "tests": "tests",
        "evidence": "evidence",
        "docs": "docs",
        "research": "historical_research",
        "tracking": "frozen_authorities",
        "website": "website",
        "tools": "tools",
        ".github": "github_automation",
    }.get(first, "top_level_or_other")


def build_report() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    categories: dict[str, dict[str, int]] = {}
    for path in _tracked_paths():
        rel = path.relative_to(ROOT).as_posix()
        if not path.exists():
            # A broken/missing tracked path should be visible instead of making
            # the measurement silently incomplete.
            size = 0
            present = False
        else:
            size = path.stat().st_size
            present = True
        category = _category(rel)
        bucket = categories.setdefault(category, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += size
        rows.append({"path": rel, "category": category, "bytes": size, "present": present})

    total_bytes = sum(int(row["bytes"]) for row in rows)
    largest = sorted(rows, key=lambda row: (-int(row["bytes"]), str(row["path"])))[:20]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_commit": os.environ.get("GITHUB_SHA", ""),
        "tracked_file_count": len(rows),
        "tracked_bytes": total_bytes,
        "tracked_mib": round(total_bytes / (1024 * 1024), 3),
        "categories": dict(sorted(categories.items())),
        "largest_tracked_files": largest,
        "interpretation": (
            "This measures the current checked-out tracked tree only. Git repository history size is a separate quantity."
        ),
    }


def _summary(report: dict[str, object]) -> str:
    lines = [
        "Aether tracked release-surface receipt",
        f"schema={report['schema_version']}",
        f"source_commit={report['source_commit']}",
        f"tracked_files={report['tracked_file_count']}",
        f"tracked_bytes={report['tracked_bytes']}",
        f"tracked_mib={report['tracked_mib']}",
        "",
        "Category breakdown:",
    ]
    for name, values in report["categories"].items():
        lines.append(f"- {name}: files={values['files']} bytes={values['bytes']}")
    lines.extend(["", str(report["interpretation"])])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--text", dest="text_path", type=Path)
    args = parser.parse_args()
    report = build_report()
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    text = _summary(report)
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
