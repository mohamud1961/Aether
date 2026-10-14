"""Grader for filesystem/manifest_repair (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last stdout line.
Reads only files under <workspace_dir> and expected.json next to this file.

The manifest values, the summary line and the canonical checksum are checked against the
release contract. Every file outside release/ must keep its pristine bytes; the stale notes
(including the v1 contract that describes a file-bytes checksum) are decoys.

Reason codes (stable):
  missing_release_manifest, manifest_not_json_object, manifest_mismatch,
  missing_release_summary, summary_mismatch,
  missing_release_checksum, checksum_file_mismatch,
  decoy_file_modified, other_file_modified
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))


def canonical(manifest):
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"))


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path):
    """File contents with trailing newlines stripped, or None when absent or not UTF-8."""
    try:
        return path.read_text(encoding="utf-8").rstrip("\n")
    except (OSError, UnicodeDecodeError):
        return None


def grade(workspace):
    release = workspace / "release"
    reasons = []

    manifest_text = read_text(release / "manifest.json")
    manifest = None
    if manifest_text is None:
        reasons.append("missing_release_manifest" if not (release / "manifest.json").is_file()
                       else "manifest_not_json_object")
    else:
        try:
            parsed = json.loads(manifest_text)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            manifest = parsed
        else:
            reasons.append("manifest_not_json_object")

    if manifest is not None and manifest != EXPECTED["manifest"]:
        reasons.append("manifest_mismatch")

    summary = read_text(release / "summary.txt")
    if summary is None:
        reasons.append("missing_release_summary")
    elif summary != EXPECTED["summary"]:
        reasons.append("summary_mismatch")

    checksum = read_text(release / "checksum.txt")
    if checksum is None:
        reasons.append("missing_release_checksum")
    elif checksum != sha256_text(canonical(EXPECTED["manifest"])):
        reasons.append("checksum_file_mismatch")
    elif manifest is not None and checksum != sha256_text(canonical(manifest)):
        reasons.append("checksum_file_mismatch")

    decoys = set(EXPECTED["decoy_paths"])
    release_paths = set(EXPECTED["release_paths"])
    for relative, digest in sorted(EXPECTED["pristine_sha256"].items()):
        if relative in release_paths:
            continue
        try:
            current = hashlib.sha256((workspace / relative).read_bytes()).hexdigest()
        except OSError:
            current = None
        if current != digest:
            reasons.append("decoy_file_modified" if relative in decoys else "other_file_modified")

    if reasons:
        return {"passed": False, "score": 0.0, "reasons": sorted(set(reasons))}
    return {
        "passed": True,
        "score": 1.0,
        "reasons": ["manifest_ok", "summary_ok", "checksum_ok", "out_of_scope_untouched"],
    }


def main():
    workspace = Path(sys.argv[1]).resolve()
    print(json.dumps(grade(workspace), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
