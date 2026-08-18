#!/usr/bin/env python3
"""Deterministic fixture grader byte for provenance-contract tests."""

import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    return 0 if payload.get("verdict") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
