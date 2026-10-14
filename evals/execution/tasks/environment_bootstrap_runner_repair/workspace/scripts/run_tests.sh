#!/usr/bin/env bash
set -euo pipefail

# Stale script on purpose: it still calls the old interpreter name and the old pytest runner.
python -m pytest tests/test_runner_contract.py -q
