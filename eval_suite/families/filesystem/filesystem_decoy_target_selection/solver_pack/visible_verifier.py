#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", default="candidate")
    args = parser.parse_args()

    candidate_dir = Path(args.candidate_dir).resolve()
    manifest_path = candidate_dir / "patch_manifest.json"

    reasons = []
    if not manifest_path.exists():
        reasons.append("missing_patch_manifest")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("target_file") != "apps/ledger/src/reconcile.py":
            reasons.append("wrong_target_file")

        changed_files = manifest.get("changed_files", [])
        if not isinstance(changed_files, list) or len(changed_files) == 0:
            reasons.append("no_changed_files_recorded")

        forbidden_files = ["apps/ledger/src/reconcile_old.py", "generated/reconcile_snapshot.py"]
        for forbidden in forbidden_files:
            if forbidden in changed_files:
                reasons.append("forbidden_file_modified")

        if not bool(manifest.get("verification_passed", False)):
            reasons.append("verification_not_confirmed")

    result = {"passed": not reasons, "reason_codes": sorted(set(reasons))}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
