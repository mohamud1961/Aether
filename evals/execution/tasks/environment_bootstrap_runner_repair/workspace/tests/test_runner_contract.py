"""Runner contract checks. Standard library only, so it runs on any python3 >= 3.9."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _contract_command() -> str:
    contract = json.loads((ROOT / "config" / "toolchain_contract.json").read_text(encoding="utf-8"))
    return " ".join(f"{contract['test_runner']} {contract['test_target']}".split())


class RunnerContractTest(unittest.TestCase):
    def test_interpreter_is_supported(self) -> None:
        self.assertGreaterEqual(sys.version_info[:2], (3, 9))

    def test_runner_script_invokes_contract_command(self) -> None:
        commands = []
        for line in (ROOT / "scripts" / "run_tests.sh").read_text(encoding="utf-8").splitlines():
            stripped = " ".join(line.split())
            if stripped and not stripped.startswith("#") and not stripped.startswith("set "):
                commands.append(stripped)
        self.assertIn(_contract_command(), commands)

    def test_contract_declares_package_manager(self) -> None:
        contract = json.loads((ROOT / "config" / "toolchain_contract.json").read_text(encoding="utf-8"))
        self.assertIn(contract.get("package_manager"), ("pip", "uv"))


if __name__ == "__main__":
    unittest.main()
