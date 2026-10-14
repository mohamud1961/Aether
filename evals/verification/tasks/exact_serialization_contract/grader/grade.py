"""Grader for the exact_serialization_contract task (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line.
Reads <workspace_dir>/out/canonical.json and grader/expected.json (next to this file).
Every input file (data, spec, checks) must keep its pristine bytes; the stale snapshot,
the v1 spec and the stale README are decoys.

Checks run in order. Structural checks report one reason code per defect; the value check
runs only when the structure is sound; the byte check runs only when values and structure
are correct, so a formatting defect is reported on its own.
"""

import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

KEY_ORDER = ["id", "name", "balance", "active", "tags"]
BALANCE_LITERAL = re.compile(r"-?\d+\.\d{2}")
EXPECTED_PATH = Path(__file__).resolve().parent / "expected.json"


def _emit(passed: bool, reasons: list[str]) -> int:
    result = {"passed": passed, "score": 1.0 if passed else 0.0, "reasons": reasons}
    print(json.dumps(result, sort_keys=True))
    return 0


def _parse(text: str) -> list:
    # parse_float=Decimal keeps the literal form, so 1234.50 and 1234.5 stay distinguishable.
    return json.loads(text, parse_float=Decimal)


def _record_reasons(record) -> list[str]:
    if not isinstance(record, dict):
        return ["record_not_object"]
    reasons: list[str] = []
    keys = list(record.keys())
    if sorted(keys) != sorted(KEY_ORDER):
        return ["key_set_mismatch"]
    if keys != KEY_ORDER:
        reasons.append("key_order_mismatch")
    if type(record["id"]) is not int:
        reasons.append("id_not_integer")
    if not isinstance(record["name"], str):
        reasons.append("name_not_string")
    balance = record["balance"]
    if not isinstance(balance, Decimal):
        reasons.append("balance_not_number")
    elif not BALANCE_LITERAL.fullmatch(str(balance)):
        reasons.append("balance_precision_mismatch")
    if type(record["active"]) is not bool:
        reasons.append("active_not_boolean")
    tags = record["tags"]
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        reasons.append("tags_not_string_array")
    return reasons


def _structure_reasons(data) -> list[str]:
    if not isinstance(data, list):
        return ["root_not_array"]
    reasons: list[str] = []
    for record in data:
        reasons.extend(_record_reasons(record))
    ids = [record.get("id") for record in data if isinstance(record, dict)]
    if all(type(value) is int for value in ids) and ids != sorted(ids):
        reasons.append("root_not_sorted_by_id")
    return list(dict.fromkeys(reasons))


def _pristine_reasons(workspace: Path, sealed: dict) -> list[str]:
    decoys = set(sealed["decoy_paths"])
    reasons: list[str] = []
    for rel, digest in sorted(sealed["pristine_sha256"].items()):
        try:
            current = hashlib.sha256((workspace / rel).read_bytes()).hexdigest()
        except OSError:
            current = None
        if current != digest:
            reasons.append("decoy_file_modified" if rel in decoys else "input_file_modified")
    return reasons


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: grade.py <workspace_dir>", file=sys.stderr)
        return 2
    workspace = Path(sys.argv[1])
    sealed = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    expected_text = sealed["canonical_output"]
    reasons = _pristine_reasons(workspace, sealed)
    candidate = workspace / "out" / "canonical.json"
    if not candidate.is_file():
        return _emit(False, sorted(set(reasons + ["output_missing"])))
    try:
        text = candidate.read_text(encoding="utf-8")
        data = _parse(text)
    except ValueError:
        return _emit(False, sorted(set(reasons + ["output_not_json"])))
    expected = _parse(expected_text)

    shape = _structure_reasons(data)
    reasons += shape
    if not shape:
        if len(data) != len(expected):
            reasons.append("record_count_mismatch")
        elif data != expected:
            reasons.append("record_value_mismatch")
    if not shape and "record_count_mismatch" not in reasons and "record_value_mismatch" not in reasons and text != expected_text:
        reasons.append("formatting_mismatch")
    if reasons:
        return _emit(False, sorted(set(reasons)))
    return _emit(True, ["canonical_output_ok"])


if __name__ == "__main__":
    raise SystemExit(main())
