#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", default="candidate")
    args = parser.parse_args()

    candidate_dir = Path(args.candidate_dir).resolve()
    report_path = candidate_dir / "extraction_report.json"

    reasons = []
    if not report_path.exists():
        reasons.append("missing_extraction_report")
    else:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not report.get("source_asset"):
            reasons.append("missing_source_asset")
        if int(report.get("frames_processed", 0)) <= 0:
            reasons.append("frames_not_processed")
        contradictions = report.get("contradictions_resolved", [])
        if not isinstance(contradictions, list) or not contradictions:
            reasons.append("missing_contradiction_reconciliation")
        if not str(report.get("pgn_prefix", "")).strip():
            reasons.append("missing_pgn_prefix")

    result = {"passed": not reasons, "reason_codes": sorted(set(reasons))}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
