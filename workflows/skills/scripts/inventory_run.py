#!/usr/bin/env python3
"""Inventory common run-analysis artifacts without interpreting results."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


INTERESTING_NAMES = {
    "result_rows.jsonl",
    "row.json",
    "scoreboard.json",
    "scoreboard.md",
    "aether2_result.json",
    "official_verifier.json",
    "grader_output.json",
    "verifier_output.json",
    "reasoning_trace.json",
    "trace.json",
    "run_events.jsonl",
    "environment_contract.json",
    "environment_manifest.json",
    "service_evidence.json",
    "grader_isolation_contract.json",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    files = [path for path in root.rglob("*") if path.is_file()]
    interesting = [
        path
        for path in files
        if path.name in INTERESTING_NAMES or path.name.startswith("model_exchange_")
    ]
    counts = Counter(
        path.name if not path.name.startswith("model_exchange_") else "model_exchange_*.json"
        for path in interesting
    )
    payload = {
        "root": str(root),
        "total_files": len(files),
        "artifact_counts": dict(sorted(counts.items())),
        "artifact_paths": [str(path) for path in sorted(interesting)],
    }

    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"root: {root}")
        print(f"total_files: {len(files)}")
        for name, count in sorted(counts.items()):
            print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

