"""Run the transparent provided-state diagnostic with a scripted provider."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace

from aether.core import facts_probe
from aether.core.loop import CoreConfig, Trace, run_agent
from tests.core_fakes import LocalEnv
from tests.test_core_responses import ResponsesClient, provider, turn_events


ROOT = Path(__file__).resolve().parent


class InitialProbeFailure(LocalEnv):
    def __init__(self, root: Path, fail: bool):
        super().__init__(root)
        self.fail_once = fail

    async def exec(self, command, **kwargs):
        if self.fail_once and "AETHER_FACTS_V1" in command:
            self.fail_once = False
            return SimpleNamespace(return_code=1, stdout="", stderr="synthetic observation failure")
        return await super().exec(command, **kwargs)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grade(work: Path, expected: dict[str, str]) -> int:
    """Independent final-artifact rule for this transparent synthetic pack."""
    return int(all((work / name).is_file() and (work / name).read_bytes() == text.encode()
                   for name, text in expected.items()))


async def episode(case: dict, work: Path, evidence: Path) -> dict:
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)
    for name, content in case["initial"].items():
        if not re.fullmatch(r"[a-z0-9_.-]+", name):
            raise ValueError("unsafe synthetic fixture path")
        (work / name).write_bytes(content.encode())
    client = ResponsesClient([
        turn_events(1, call=("terminal", {"input": case["command"]}, "c1")),
        turn_events(2, call=("finish", {"summary": "done"}, "c2")),
    ])
    env = InitialProbeFailure(work, case.get("fail_initial_probe", False))
    result = await run_agent(
        env=env, task=case["task"], workdir=str(work), provider=provider(client, evidence / "calls"),
        timeout_s=600, trace=Trace(evidence / "trace.jsonl"),
        config=CoreConfig(control_dir=str(work.parent / "ctl"), end_processes="stop", managed_facts=True),
    )
    if result.status != "finished":
        raise RuntimeError(f"{case['id']}: scripted Core did not finish: {result.status}")
    (evidence / "requests.json").write_text(json.dumps(client.requests, indent=2) + "\n")
    artifact_dir = evidence / "artifact"
    artifact_dir.mkdir()
    for name in set(case["initial"]) | set(case["expected_files"]):
        path = work / name
        if path.is_file():
            (artifact_dir / name).write_bytes(path.read_bytes())
    observation = result.extras.get("core_facts") or {}
    initial = observation.get("initial_workspace")
    changes = observation.get("initial_workspace_changes")
    supported = isinstance(initial, dict) and isinstance(changes, list)
    matched = next((x for x in changes or [] if x.get("path") == "source.txt"), None)
    outputs = [item.get("output", "") for request in client.requests for item in request.get("input", [])
               if item.get("type") == "function_call_output"]
    visible = any("source.txt" in output and "initial workspace observation" in output
                  and "metadata" in output for output in outputs)
    if not supported:
        sensor = "not_implemented"
    elif case["expected_start_change"] is None:
        sensor = "pass" if initial.get("status") == "unknown" and matched is None and not visible else "fail"
    elif case["expected_start_change"]:
        sensor = ("pass" if initial.get("status") == "observed" and matched is not None
                  and matched.get("first_observed_step") == 1 and matched.get("kind") == "metadata_changed"
                  and visible else "fail")
    else:
        sensor = "pass" if initial.get("status") == "observed" and matched is None and not visible else "fail"
    # The observation is a fact about metadata, never a behavioral verdict or content claim.
    relevant = " ".join(o for o in outputs if "initial workspace observation" in o)
    if any(word in relevant.lower() for word in ("content changed", "forbidden", "wrong", "violation")):
        sensor = "fail"
    score = grade(work, case["expected_files"])
    row = {"case": case["id"], "status": result.status, "artifact_score": score,
           "artifact_expected": case["expected_score"], "sensor": sensor,
           "expected_start_change": case["expected_start_change"], "model_visible_relation": visible}
    (evidence / "row.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    pack_path = ROOT / "cases.json"
    pack = json.loads(pack_path.read_text())
    if pack.get("schema") != 1 or len(pack.get("cases", [])) != 5:
        raise ValueError("unexpected task pack")
    facts_probe.HOSTS = ()
    facts_probe.SYSTEM_PYTHON_PATHS = (os.path.realpath(sys.executable),)
    rows = []
    with tempfile.TemporaryDirectory(prefix="codex-provided-state-eval-") as temp:
        for case in pack["cases"]:
            if not re.fullmatch(r"[a-z_]+", case["id"]):
                raise ValueError("unsafe case identity")
            rows.append(asyncio.run(episode(case, Path(temp) / case["id"] / "work", args.evidence / case["id"])))
    report = {
        "scope": "scripted local provider, transparent synthetic tasks, no model or VM",
        "pack_sha256": sha(pack_path), "runner_sha256": sha(Path(__file__)),
        "source_sha256": {name: sha(ROOT.parents[2] / "src/aether/core" / name)
                          for name in ("facts.py", "facts_probe.py", "loop.py")},
        "artifact_controls_pass": all(r["artifact_score"] == r["artifact_expected"] for r in rows),
        "sensor_pass_count": sum(r["sensor"] == "pass" for r in rows),
        "sensor_unimplemented_count": sum(r["sensor"] == "not_implemented" for r in rows),
        "rows": rows,
    }
    (args.evidence / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not report["artifact_controls_pass"]:
        raise SystemExit("artifact grader controls failed; sensor result is not usable")


if __name__ == "__main__":
    main()
