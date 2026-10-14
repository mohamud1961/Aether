#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must decode to an object")
    return payload


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _expected_runner_command(workspace_root: Path) -> str:
    contract_path = workspace_root / "config" / "toolchain_contract.json"
    contract = _load_json(contract_path)
    test_runner = contract.get("test_runner")
    test_target = contract.get("test_target")
    if not isinstance(test_runner, str) or not isinstance(test_target, str):
        raise ValueError(f"{contract_path} must define string test_runner and test_target fields")
    return _normalize_whitespace(f"{test_runner} {test_target}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()

    candidate_path = Path(args.candidate).resolve()
    if not candidate_path.exists():
        print(json.dumps({"passed": False, "reason_codes": ["candidate_missing"]}, sort_keys=True))
        return 1

    try:
        data = _load_json(candidate_path)
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"passed": False, "reason_codes": [f"candidate_invalid:{type(exc).__name__}"]}, sort_keys=True))
        return 1

    required = ["runner_command", "package_manager", "preflight_success", "evidence"]
    missing = [field for field in required if field not in data]
    if missing:
        print(json.dumps({"passed": False, "missing": missing, "reason_codes": ["missing_required_fields"]}, sort_keys=True))
        return 1

    workspace_root = Path(__file__).resolve().parents[1]
    try:
        expected_runner_command = _expected_runner_command(workspace_root)
    except FileNotFoundError:
        print(json.dumps({"passed": False, "reason_codes": ["toolchain_contract_missing"]}, sort_keys=True))
        return 1
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"passed": False, "reason_codes": [f"toolchain_contract_invalid:{type(exc).__name__}"]}, sort_keys=True))
        return 1

    runner_command = data.get("runner_command")
    if not isinstance(runner_command, str) or _normalize_whitespace(runner_command) != expected_runner_command:
        print(
            json.dumps(
                {
                    "passed": False,
                    "expected_runner_command": expected_runner_command,
                    "reason_codes": ["runner_command_mismatch"],
                },
                sort_keys=True,
            )
        )
        return 1

    if data.get("preflight_success") is not True:
        print(json.dumps({"passed": False, "reason_codes": ["preflight_not_successful"]}))
        return 1

    print(json.dumps({"passed": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
