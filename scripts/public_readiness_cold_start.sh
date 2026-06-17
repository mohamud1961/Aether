#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

TMP_ROOT="${TMPDIR:-/private/tmp}"
RUN_ROOT="$(mktemp -d "${TMP_ROOT%/}/harnesseng_public_readiness.XXXXXX")"
trap 'rm -rf "$RUN_ROOT"' EXIT

log() {
  printf '[public-readiness-cold-start] %s\n' "$*"
}

DOC_FILES=(
  README.md
  PUBLIC_REVIEWER_GUIDE.md
  docs/README.md
  docs/provenance/README.md
  docs/provenance/agent_runtime_adaptation_policy.md
  docs/provenance/third_party_notices.md
  docs/publication/README.md
  docs/publication/public_evidence_index.md
  docs/publication/publication_gap_list.md
  aether/hooks/README.md
  aether/agents/README.md
  aether/skills/loader.py
  aether/skills/registry.py
  aether/tools/mcp.py
  aether/tools/permissions.py
)

if rg -n -e 'quarantined|MIT licensing|root LICENSE|adapted from a quarantined external|quarantined external' "${DOC_FILES[@]}"; then
  printf '[public-readiness-cold-start] ERROR: public-facing provenance wording sweep found disallowed phrases\n' >&2
  exit 1
fi

python3 - "$REPO_ROOT" "$RUN_ROOT" <<'PY'
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
run_root = Path(sys.argv[2])
required_paths = [
    "README.md",
    "PUBLIC_REVIEWER_GUIDE.md",
    "docs/publication/public_readiness.md",
    "scripts/public_readiness_cold_start.sh",
    "scripts/public_manifest_repair_smoke.sh",
    "eval_suite/families/filesystem/public_manifest_repair_smoke/task_pack.json",
    "eval_suite/families/filesystem/public_manifest_repair_smoke/grader.py",
]
for rel_path in required_paths:
    path = repo_root / rel_path
    if not path.exists():
        raise SystemExit(f"missing required readiness file: {rel_path}")

task_pack = json.loads((repo_root / "eval_suite/families/filesystem/public_manifest_repair_smoke/task_pack.json").read_text(encoding="utf-8"))
if task_pack.get("task_id") != "public_manifest_repair_smoke_v1":
    raise SystemExit("unexpected public manifest smoke task id")

report_path = run_root / "launch_integrity.json"
report_path.write_text(json.dumps({"ok": True, "checked_paths": required_paths}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(report_path)
PY

log "cold-start checks passed"
