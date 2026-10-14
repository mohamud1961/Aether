#!/usr/bin/env bash
# expect: checksum_file_mismatch
# Writes release files with the right shape and plausible values, with a placeholder checksum.
set -euo pipefail
cat > release/manifest.json <<'JSON'
{"project": "Atlas Notes", "release": "1.4.0", "maintainer": "platform-ops", "status": "ready",
 "files": ["release/manifest.json", "release/summary.txt", "release/checksum.txt"]}
JSON
printf 'Atlas Notes 1.4.0 is ready; tracked files: 3.\n' > release/summary.txt
printf '%064d\n' 0 > release/checksum.txt
