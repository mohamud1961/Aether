#!/usr/bin/env bash
# expect: missing_row
# Trusts STATUS.txt and the backup: restores the backup as the output and stops there.
set -euo pipefail
cp backup/users_v2.jsonl.bak data/output/users_v2.jsonl
