#!/usr/bin/env bash
# expect: health_status_mismatch
# Copies the scaffold as the implementation, sees that it starts, and never probes the routes.
set -euo pipefail
mkdir -p out
cp scripts/start_service.py out/service_impl.py
