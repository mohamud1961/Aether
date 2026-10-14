#!/usr/bin/env python3
"""Build simulator. Progress goes to stdout. A fatal error goes to stderr and ends the run with the configured exit code."""
import json
import sys
from pathlib import Path


def main() -> int:
    config_path = Path(__file__).resolve().parents[1] / "config" / "build_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    planned = config["components_planned"]
    crash_at = config.get("crash_at_component")

    for i in range(1, planned + 1):
        if crash_at is not None and i == crash_at:
            print(f"[FATAL] Segmentation fault in component {i}", file=sys.stderr)
            return config["exit_code"]
        print(f"Building component {i}... [OK]")

    print(f"[OK] all {planned} components built")
    return config["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
