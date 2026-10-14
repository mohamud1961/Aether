#!/usr/bin/env bash
# expect: missing_service_impl
# Copies the earlier pre-1.0 attempt, which still uses the superseded port, but saves it as out/service.py rather than out/service_impl.py.
set -euo pipefail
mkdir -p out
cp ops/previous_attempt/service_impl.py.old out/service.py
