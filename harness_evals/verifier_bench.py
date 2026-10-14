"""Reference/known-bad verifier calibration, isolated from hidden grader inputs."""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from .grading import grade
from .sandbox import LocalSandbox
from .stats import summarize_rate


def build_cases(tasks, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    cases = []
    for task in tasks:
        states = [("reference", task.reference_script, True)] + [
            (b.path.stem, b.path, False) for b in task.known_bad
        ]
        for name, script, correct in states:
            sandbox = LocalSandbox(task, trusted=True)
            try:
                produced = sandbox.exec(
                    "bash " + shlex.quote(str(script)), task.timeout_s
                )
                result = grade(task, sandbox.root)
                if produced.code or result.error or result.passed != correct:
                    raise ValueError(f"invalid labelled state {task.id}/{name}")
                case_id = task.id + "--" + name
                shutil.copytree(sandbox.root, destination / case_id)
                cases.append(
                    {
                        "id": case_id,
                        "task_id": task.id,
                        "correct": correct,
                        "prompt": task.prompt,
                        "claim": "The requested task is complete.",
                        "reasons": list(result.reasons),
                    }
                )
            finally:
                sandbox.close()
    (destination / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    return cases


def evaluate(cases_dir, command, timeout_s=30):
    root = Path(cases_dir)
    cases = json.loads((root / "cases.json").read_text())
    outcomes = []
    for claims in (False, True):
        for case in cases:
            with tempfile.TemporaryDirectory(prefix="verifier-case-") as temp:
                state = Path(temp) / "state"
                shutil.copytree(root / case["id"], state)
                payload = {"workspace": str(state), "prompt": case["prompt"]}
                if claims:
                    payload["claim"] = case["claim"]
                try:
                    proc = subprocess.run(
                        command,
                        shell=True,
                        input=json.dumps(payload),
                        text=True,
                        capture_output=True,
                        timeout=timeout_s,
                        env={"PATH": os.environ.get("PATH", ""), "HOME": temp},
                        cwd=temp,
                    )
                    verdict = proc.stdout.strip()
                    valid = proc.returncode == 0 and verdict in {"met", "not_met"}
                except subprocess.TimeoutExpired:
                    verdict, valid = "timeout", False
            outcomes.append(
                {
                    "case": case["id"],
                    "correct": case["correct"],
                    "claims": claims,
                    "verdict": verdict,
                    "valid": valid,
                }
            )
    summaries = []
    for claims in (False, True):
        group = [r for r in outcomes if r["claims"] == claims]
        wrong = [r for r in group if not r["correct"] and r["valid"]]
        right = [r for r in group if r["correct"] and r["valid"]]
        summaries.append(
            {
                "claims": claims,
                "invalid": sum(not r["valid"] for r in group),
                "catch_rate": asdict(
                    summarize_rate(
                        sum(r["verdict"] == "not_met" for r in wrong), len(wrong)
                    )
                ),
                "false_hold_rate": asdict(
                    summarize_rate(
                        sum(r["verdict"] == "not_met" for r in right), len(right)
                    )
                ),
            }
        )
    return {
        "scope": "local command calibration; labels excluded from verifier input",
        "summaries": summaries,
        "rows": outcomes,
    }
