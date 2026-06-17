#!/bin/bash
set -euo pipefail

python3 -m unittest -q tests.test_execution_gate
