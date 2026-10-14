#!/usr/bin/env bash
# expect: missing_policy_audit
# Derives nothing and removes the audit file.
set -euo pipefail
rm -f policy_audit.json
