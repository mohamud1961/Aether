#!/usr/bin/env python3
"""Readiness gate: checks the dispatch plan has its required fields and agrees with the selector file.
It does not re-derive the selection from the snapshot."""
import argparse
import json
from pathlib import Path

REQUIRED = ["workspace_id", "ticket_id", "action_commands", "source_event_id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()
    dispatch = json.loads(Path(args.dispatch).read_text(encoding="utf-8"))
    selector = Path(args.workspace).read_text(encoding="utf-8").strip()
    missing = [key for key in REQUIRED if key not in dispatch]
    if missing:
        print(json.dumps({"passed": False, "missing": missing}, sort_keys=True))
        return 1
    if dispatch["workspace_id"] != selector:
        print(json.dumps({"passed": False, "reason": "selector_disagrees"}, sort_keys=True))
        return 1
    print(json.dumps({"passed": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
