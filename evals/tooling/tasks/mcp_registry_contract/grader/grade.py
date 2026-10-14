#!/usr/bin/env python3
"""Grader for tooling/mcp_registry_contract (v2).

python3 grade.py <workspace_dir> prints one JSON line {"passed", "score", "reasons"}.
Reads only <workspace_dir> and expected.json next to this file. The audit must equal the
derived truth section by section. The trace must carry the same six sections, and every
registry source, the challenge token and the reason table must be unchanged.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE_FOR_SECTION = {
    "discovery": "discovery_mismatch",
    "schema_mapping": "schema_mapping_mismatch",
    "invocation_results": "invocation_results_mismatch",
    "hook_permission_trace": "hook_permission_trace_mismatch",
    "native_regression": "native_regression_mismatch",
    "bundle_contract": "bundle_contract_mismatch",
    "challenge_response": "challenge_response_mismatch",
}


def _load(path: Path, missing_code: str, invalid_code: str):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [missing_code]
    except (OSError, ValueError):
        return None, [invalid_code]
    if not isinstance(value, dict):
        return None, [invalid_code]
    return value, []


def _section_reasons(doc: dict, truth: dict, sections: list[str], prefix: str) -> list[str]:
    reasons = []
    for section in sections:
        if section not in doc:
            reasons.append(f"{prefix}_section_missing")
        elif doc[section] != truth[section]:
            reasons.append(CODE_FOR_SECTION[section])
    return reasons


def _pristine_reasons(workspace: Path, expected: dict) -> list[str]:
    reasons = []
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        try:
            same = hashlib.sha256((workspace / rel).read_bytes()).hexdigest() == digest
        except OSError:
            same = False
        if not same:
            reasons.append("other_file_modified")
    return reasons


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    truth_audit = expected["audit"]
    reasons: list[str] = []

    audit, problems = _load(workspace / expected["audit_file"], "missing_audit_file", "invalid_audit_file")
    reasons += problems
    if audit is not None:
        reasons += _section_reasons(audit, truth_audit, list(truth_audit), "audit")

    trace, problems = _load(workspace / expected["trace_file"], "missing_trace_file", "invalid_trace_file")
    reasons += problems
    if trace is not None:
        reasons += _section_reasons(trace, truth_audit, expected["trace_sections"], "trace")

    reasons += _pristine_reasons(workspace, expected)
    reasons = sorted(set(reasons))
    passed = not reasons
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "reasons": ["mcp_bundle_derived"] if passed else reasons}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
