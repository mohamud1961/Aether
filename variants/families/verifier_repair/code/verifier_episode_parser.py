from __future__ import annotations

import re
from typing import Any, Pattern


def parse_verifier_attempts(
    execution_result: Any,
    *,
    cwd: str,
    verify_exec_re: Pattern[str],
    exit_re: Pattern[str],
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    steps = execution_result.get("steps", []) if isinstance(execution_result, dict) else []
    for step in steps:
        step_no = step.get("step")
        for result_index, result in enumerate(step.get("results", [])):
            command = str(result.get("command", ""))
            if not verify_exec_re.search(command):
                continue
            stdout = str(result.get("stdout", ""))
            stderr = str(result.get("stderr", ""))
            exit_codes = _exit_codes(stdout=stdout, stderr=stderr, result=result, exit_re=exit_re)
            for episode_index, exit_code in enumerate(exit_codes):
                attempts.append(
                    {
                        "step": step_no,
                        "result_index": result_index,
                        "episode_index": episode_index,
                        "command": command,
                        "normalized_command": command.replace(cwd, "/app"),
                        "status": "pass" if exit_code == 0 else "fail",
                        "exit_code": exit_code,
                        "stdout": stdout,
                        "stderr": stderr,
                    }
                )
    return attempts


def _exit_codes(
    *,
    stdout: str,
    stderr: str,
    result: dict[str, Any],
    exit_re: Pattern[str],
) -> list[int]:
    joined = f"{stdout}\n{stderr}"
    explicit = [int(match.group("code")) for match in exit_re.finditer(joined)]
    if explicit:
        return explicit
    lowered = joined.lower()
    if "\npass" in lowered or lowered.strip() == "pass":
        return [0]
    if "\nfail" in lowered or lowered.strip() == "fail":
        return [1]
    raw = result.get("exit_code", 1)
    try:
        return [int(raw)]
    except Exception:
        return [1]
