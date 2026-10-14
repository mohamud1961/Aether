"""python3.11 -m harness_evals entry point."""

import sys

from harness_evals.cli import main

raise SystemExit(main(sys.argv[1:]))
