"""Exercise Step 0 detectors with synthetic inputs; inspect data names only."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripts", type=Path, required=True)
    parser.add_argument("--metadata-root", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.scripts.resolve(strict=True)))
    beliefs = importlib.import_module("env_beliefs")
    signatures = importlib.import_module("signatures")

    samples = (
        ("positive_install", "Python is installed.", {"kind": "cmd_ok", "subject": "python"}),
        ("separate_command_names", "Python is not installed.", {"kind": "cmd_ok", "subject": "python3"}),
        ("memory_without_threshold", "There is insufficient memory.", {"kind": "mem_seen", "subject": "free"}),
    )
    results = {}
    for name, sentence, evidence in samples:
        extracted = beliefs.extract_beliefs(sentence, 1)
        results[name] = {
            "categories": [row["category"] for row in extracted],
            "reported_contradiction": any(beliefs.contradicts(row, evidence) for row in extracted),
        }
    pending = {"name": "terminal", "args": {"input": "python solver.py"},
               "result": "[still running after 1s; terminal main]"}
    results["pending_command"] = {
        "reported_passing": signatures.check_passes(pending),
        "file_treated_as_checked": "solver.py" in signatures.io_event(1, pending)[2],
    }
    results["useful_python_action_counted_as_probe"] = bool(
        beliefs.PROBE.search("python -c 'print(2 + 2)'")
    )
    protected = re.compile(
        r"(?:^|[._/\-])(?:keys?|secrets?|credentials?|passwords?|passwd)(?:$|[._/\-])", re.I,
    )
    restricted = re.compile(
        r"rolling-shutter|extract-elf|make-doom|sanitize-git-repo|openssl-selfsigned-cert|"
        r"feal-linear-cryptanalysis|configure-git-webserver|git-leak|fix-git|"
        r"qemu-alpine-ssh|code-from-image", re.I,
    )
    counts: Counter[str] = Counter()
    for parent, _dirs, names in os.walk(args.metadata_root, followlinks=False):
        relative = os.path.relpath(parent, args.metadata_root)
        for name in names:
            if name == "core_trace.jsonl":
                counts["trace_paths"] += 1
                counts["trace_paths_in_previously_excluded_families"] += bool(restricted.search(relative))
            elif name.endswith(".json") and protected.search(name):
                counts["json_with_sensitive_name"] += 1
    results["metadata_only_inventory"] = dict(counts)
    results["detector_source_sha256"] = {
        name: hashlib.sha256((args.scripts / name).read_bytes()).hexdigest()
        for name in ("inventory.py", "env_beliefs.py", "signatures.py", "trace_lib.py")
    }
    results["limitations"] = [
        "Synthetic controls establish detector failure modes, not their real-world frequencies.",
        "Names are metadata only; no data-file contents were opened by this reproduction.",
        "A sensitive-looking name does not establish that a file contains credentials.",
        "The reproduction does not establish what Freebuff sent to its model provider.",
    ]
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
