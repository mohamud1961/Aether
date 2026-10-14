#!/usr/bin/env bash
# expect: missing_submission
# Writes an answer to a file name the ticket did not ask for, and leaves out/late_shipments.json absent.
set -euo pipefail
mkdir -p out
printf '{"shipped_time_source": "event_log", "late_orders": []}\n' > out/late_orders.json
