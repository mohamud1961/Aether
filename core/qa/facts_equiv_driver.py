"""Run Core's scripted equivalence board without its broad host-process cleanup.

All scenarios use a unique owned temporary root, stop their own Core processes,
and use a one-second background job. No provider or VM is contacted. The
original helper's pkill and fixed shared directories are never used.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parents[2]
ORIGINAL = HERE / "tools/core_equiv"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected equivalence helper source for {old[:60]!r}")
    return text.replace(old, new, 1)


def capture(tool: Path, source: Path, target: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(tool), "run", str(source), str(target)],
        check=True, capture_output=True, text=True,
    )
    print(result.stdout.strip(), flush=True)
    rows = json.loads(target.read_text())
    errors = {name: row["exception"] for name, row in rows.items() if "exception" in row}
    if errors or len(rows) != 10:
        raise RuntimeError(f"invalid equivalence capture: {len(rows)} scenarios; exceptions={errors}")


def compare(tool: Path, first: Path, second: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(tool), "diff", str(first), str(second)],
        capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"equivalence comparison failed: {result.stderr[:600]}")
    return result.returncode == 0, result.stdout[:5000]


def normalize_capture(source: Path, target: Path, *, candidate: bool) -> None:
    """Normalize only documented cleanup artifacts, never model-visible output."""
    data = copy.deepcopy(json.loads(source.read_text()))
    for row in data.values():
        config = row.get("config")
        if candidate and (not isinstance(config, dict) or config.pop("managed_facts", None) is not False):
            raise RuntimeError("candidate lacks the expected disabled configuration field")
        cleanup = (row.get("result", {}).get("extras", {}).get("process_cleanup", {})
                   .get("terminals", {}))
        terminal_exit = row.get("ctl_files", {}).get("term/main/exit")
        if terminal_exit == "143\n":
            if cleanup.get("status") != "confirmed_stopped" or cleanup.get("still_running"):
                raise RuntimeError("unexpected terminal exit receipt; do not normalize")
            del row["ctl_files"]["term/main/exit"]
        paths = [cleanup]
        paths.extend(item.get("process_cleanup", {}).get("terminals", {})
                     for item in row.get("trace", []) if isinstance(item, dict))
        for record in paths:
            observed = record.get("observed")
            if isinstance(observed, list):
                record["observed"] = [
                    f"<child-pid-{i}>" if type(value) is int else value
                    for i, value in enumerate(observed)
                ]
    target.write_text(json.dumps(data, indent=1, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--reuse-root", type=Path, help="continue from two preserved baseline captures")
    args = parser.parse_args()
    evidence = args.evidence
    if args.reuse_root:
        if not evidence.is_dir():
            raise RuntimeError("baseline evidence is missing")
        owned = args.reuse_root
    else:
        evidence.mkdir(parents=True, exist_ok=False)
        owned = Path(tempfile.mkdtemp(prefix="codex-facts-equiv-"))
    helper = owned / "helper"
    if not args.reuse_root:
        helper.mkdir()
        shutil.copy2(ORIGINAL / "fakes.py", helper / "fakes.py")
    original = (ORIGINAL / "equiv.py").read_text()
    script = replace_once(original, "ROOT = Path('/tmp/aether-equiv')", f"ROOT = Path({str(owned / 'runtime')!r})")
    script = replace_once(script, "ROOT.parent / 'aether-equiv.lock'", "ROOT.parent / (ROOT.name + '.lock')")
    script = replace_once(script, "tempfile.mkdtemp(prefix='equiv-')", "tempfile.mkdtemp(prefix='equiv-', dir=ROOT)")
    script = replace_once(script, "'AETHER_CORE_CALLS': 'one'", "'AETHER_CORE_END_PROCESSES': 'stop', 'AETHER_CORE_CALLS': 'one'")
    script = replace_once(script, "nohup sleep 300", "nohup sleep 1")
    script = replace_once(script, "    subprocess.run(['pkill', '-f', 'sleep 300'], check=False)\n", "")
    script = replace_once(script, "    _stop_tree(CTL)\n", "")
    tool = helper / "equiv.py"
    if args.reuse_root:
        if tool.read_text() != script or (helper / "fakes.py").read_bytes() != (ORIGINAL / "fakes.py").read_bytes():
            raise RuntimeError("preserved equivalence helper differs from the regenerated source")
    else:
        tool.write_text(script)

    baseline, second, candidate, falsifier = (evidence / f"{x}.json" for x in
                                               ("baseline", "baseline_repeat", "candidate", "falsifier"))
    if not args.reuse_root:
        capture(tool, args.baseline, baseline)
        capture(tool, args.baseline, second)
    baseline_norm = evidence / "baseline_normalized.json"
    second_norm = evidence / "baseline_repeat_normalized.json"
    normalize_capture(baseline, baseline_norm, candidate=False)
    normalize_capture(second, second_norm, candidate=False)
    same_base, base_diff = compare(tool, baseline_norm, second_norm)
    if not same_base:
        (evidence / "baseline_diff.txt").write_text(base_diff)
        raise RuntimeError("baseline repeated capture differs; no equivalence claim")
    capture(tool, args.candidate, candidate)

    # Normalize only the newly introduced, disabled config field. All actual
    # prompts, calls, traces, results and files stay in the comparison.
    candidate_norm = evidence / "candidate_normalized.json"
    normalize_capture(candidate, candidate_norm, candidate=True)
    same_candidate, candidate_diff = compare(tool, baseline_norm, candidate_norm)
    (evidence / "candidate_diff.txt").write_text(candidate_diff)

    mutant = owned / "mutant-src"
    shutil.copytree(args.baseline, mutant, ignore=shutil.ignore_patterns("__pycache__"))
    loop = mutant / "aether/core/loop.py"
    loop_text = loop.read_text()
    loop_text = replace_once(loop_text, 'f"{task}\\n\\n(Working directory:',
                             'f"{task} [FACTS-CONTROL-MUTATION]\\n\\n(Working directory:')
    loop.write_text(loop_text)
    capture(tool, mutant, falsifier)
    bad_norm = evidence / "falsifier_normalized.json"
    normalize_capture(falsifier, bad_norm, candidate=False)
    same_bad, bad_diff = compare(tool, baseline_norm, bad_norm)
    (evidence / "falsifier_diff.txt").write_text(bad_diff)
    report = {
        "scenarios": 10,
        "baseline_repeat_equal": same_base,
        "candidate_equal_after_only_disabled_config_field_removed": same_candidate,
        "known_bad_detected": not same_bad,
        "candidate_normalization": "removed only config.managed_facts=false",
        "all_capture_normalization": "process_cleanup terminal observed PID values; optional 143 control exit receipt only when cleanup confirmed stopped",
        "limits": ["scripted local provider", "end_processes=stop", "background sleep=1s",
                   "no live model", "facts treatment disabled"],
        "source_helper_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "safe_helper_sha256": hashlib.sha256(script.encode()).hexdigest(),
        "owned_root": str(owned),
    }
    (evidence / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)
    if not same_candidate or same_bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
