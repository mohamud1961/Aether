#!/usr/bin/env bash
set -euo pipefail

python -m pytest tests/test_legacy_runner_contract.py -q
