#!/usr/bin/env bash
# expect: missing_final_submission
# Edits the loaded config correctly, then stops before writing the submission or running the check.
set -euo pipefail
sed -i.bak 's/^retries: .*/retries: 5/' app/config/service.yaml && rm -f app/config/service.yaml.bak
