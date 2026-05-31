#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", default="candidate")
    args = parser.parse_args()

    candidate_dir = Path(args.candidate_dir).resolve()
    receipt_path = candidate_dir / "readiness_receipt.json"

    reasons = []
    if not receipt_path.exists():
        reasons.append("missing_readiness_receipt")
    else:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        
        expected_port = None
        config_path = candidate_dir / "service" / "config" / "service_config.json"
        if config_path.exists():
            try:
                config_data = json.loads(config_path.read_text(encoding="utf-8"))
                expected_port = config_data.get("port")
            except Exception:
                pass

        service_url = str(receipt.get("service_url", ""))
        if not service_url:
            reasons.append("missing_service_url")
        else:
            if expected_port:
                expected_suffix = f":{expected_port}/healthz"
                if not service_url.endswith(expected_suffix):
                    reasons.append("wrong_service_port_or_route")
            elif not service_url.startswith("http://127.0.0.1:") or not service_url.endswith("/healthz"):
                reasons.append("service_url_not_local_healthz")

        if int(receipt.get("probes_passed", 0)) < 3:
            reasons.append("insufficient_probe_count")
        if not bool(receipt.get("wrong_port_rejected", False)):
            reasons.append("wrong_port_rejection_missing")
        if not bool(receipt.get("cleanup_performed", False)):
            reasons.append("cleanup_not_confirmed")
        notes = receipt.get("notes")
        if not isinstance(notes, list) or not notes:
            reasons.append("missing_probe_notes")

    result = {"passed": not reasons, "reason_codes": sorted(set(reasons))}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
