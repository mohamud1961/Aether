#!/usr/bin/env python3
"""Reserved runner entrypoint for future fake-progress homolog execution.

This script is intentionally non-executing in the implementation-only phase.
It exists so reserved commands and manifests point at a concrete future
entrypoint instead of a placeholder string.
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-id", required=True)
    parser.add_argument("--control", required=True)
    args = parser.parse_args(argv)
    raise SystemExit(
        "Reserved for separate runner phase: "
        f"eval_id={args.eval_id} control={args.control}. "
        "Implementation-only scope does not execute model-backed homolog runs."
    )


if __name__ == "__main__":
    raise SystemExit(main())
