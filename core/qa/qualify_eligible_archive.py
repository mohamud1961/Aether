#!/usr/bin/env python3
"""Build and verify T0/T1 for authority-named archive sources, without executing actions.

Metadata inputs are the exact frozen request index and coverage dashboard from
3d5fd065. The operator supplies source roots. Protected name matches are removed
before opening a trace or client log. Output contains counts/hashes, never payloads.
This is structured request reconstruction, not original-VM or task grading replay.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import replay_corpus as replay


def qualify(index, dashboard, seed, roots, out):
    # The Frozen-3 lock applies even to historical run records. Conservative
    # substring exclusion also avoids similarly named source paths.
    protected = ("rolling-shutter", "extract-elf", "make-doom")
    for root in roots.values():
        if any(n in str(Path(root).resolve()).lower() or n in str(root).lower() for n in protected):
            raise ValueError("protected source root denied before archive access")
    episodes = [e for e in dashboard["episodes"] if not any(n in e["trace_source"].lower() for n in protected)]
    allowed_hashes = {e["trace_sha256"] for e in episodes}
    selected_index = {**index, "rows": [r for r in index["rows"] if r["trace_sha256"] in allowed_hashes]}
    selected_dashboard = {**dashboard, "episodes": episodes}
    selection = {"coverage_cases": [
        {"cohort": e["cohort"], "case_id": e["case_id"], "trace_sha256": e["trace_sha256"], "family": "coverage"}
        for e in episodes
    ]}
    corpus = replay.build_corpus(seed=seed, selection=selection, dashboard=selected_dashboard,
                                 index=selected_index, root_map=roots)
    evaluation = replay.evaluate_manifest(corpus, roots, index_rows=selected_index["rows"])
    compressed = out.with_suffix(".corpus.json.gz")
    with gzip.open(compressed, "wt", encoding="utf-8") as stream:
        json.dump(corpus, stream, sort_keys=True, separators=(",", ":"))
    summary = {
        "tier": "T0/T1 only; no tool action execution or task-grade claim",
        "archive_commit": replay.ARCHIVE_COMMIT,
        "eligible_cases": len(episodes),
        "excluded_protected_metadata_names": len(dashboard["episodes"]) - len(episodes),
        "source_access_policy": "protected names excluded before resolution; rooted paths and adjacent logs reject traversal and symlink components; immutable archives assumed",
        "corpus_sha256": replay._manifest_digest(corpus),
        "compressed_corpus_sha256": hashlib.sha256(compressed.read_bytes()).hexdigest(),
        "t0": evaluation["t0"]["counts"], "t1": evaluation["t1"]["counts"],
        "corpus_problems": evaluation["corpus_problems"],
        "failed_cases": [{"case_key": c["case_key"], "failure_count": c["failure_count"]}
                         for c in evaluation["t0"]["cases"] if c["t0"]["status"] != "PASS" or c["t1"]["status"] == "FAIL"],
    }
    summary["ok"] = (not summary["corpus_problems"] and summary["t0"]["pass"] == len(episodes)
                     and summary["t0"]["fail"] == 0 and summary["t0"]["unavailable"] == 0
                     and summary["t1"]["pass"] > 0 and summary["t1"]["fail"] == 0)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("index", "dashboard", "seed", "roots", "out"):
        parser.add_argument("--" + arg, required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(qualify(*(json.loads(p.read_text()) for p in (args.index, args.dashboard, args.seed, args.roots)), args.out))
