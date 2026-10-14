#!/usr/bin/env bash
# expect: checksum_file_mismatch
# Reference state, but the checksum is the SHA-256 of the manifest file's bytes (the superseded v1 rule).
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
sha256sum release/manifest.json | cut -d' ' -f1 > release/checksum.txt 2>/dev/null || shasum -a 256 release/manifest.json | cut -d' ' -f1 > release/checksum.txt
