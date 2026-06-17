import json
from pathlib import Path


def _contains_any(text: str, tokens: list[str]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _coerce_non_negative_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _coerce_conflict_resolution_count(value) -> int:
    if isinstance(value, dict):
        return _coerce_non_negative_int(value.get("conflicting_frames_resolved", 0))
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        if stripped.isdigit():
            return int(stripped)
        return 1
    return _coerce_non_negative_int(value)


def evaluate(candidate_dir: Path, truth: dict) -> dict:
    report_path = candidate_dir / "extraction_report.json"
    reasons = []
    passed = True

    if not report_path.exists():
        return {"passed": False, "score": 0.0, "reasons": ["missing_extraction_report"]}

    data = json.loads(report_path.read_text())
    fetch_method = str(data.get("fetch_method", ""))
    if fetch_method not in truth["required_fetch_methods"]:
        passed = False
        reasons.append("missing_valid_fetch_path")

    ffmpeg_cmd = str(data.get("ffmpeg_command", ""))
    if truth["required_ffmpeg_token"] not in ffmpeg_cmd.lower():
        passed = False
        reasons.append("ffmpeg_extraction_not_evidenced")

    ocr_cmd = str(data.get("ocr_command", ""))
    if not _contains_any(ocr_cmd, truth["required_ocr_tokens"]):
        passed = False
        reasons.append("ocr_extraction_not_evidenced")

    extracted_moves = data.get("extracted_moves", [])
    if not isinstance(extracted_moves, list) or len(extracted_moves) < int(truth["minimum_move_count"]):
        passed = False
        reasons.append("insufficient_move_extraction")

    contradiction_resolution = data.get("contradiction_resolution", {})
    resolved = _coerce_conflict_resolution_count(contradiction_resolution)
    if resolved < int(truth["minimum_conflict_resolutions"]):
        passed = False
        reasons.append("contradictions_not_reconciled")

    if not bool(data.get("false_completion_guard", False)):
        passed = False
        reasons.append("false_completion_guard_missing")

    final_pgn = str(data.get("final_pgn", "")).strip()
    if not final_pgn.startswith(truth["required_pgn_prefix"]):
        passed = False
        reasons.append("final_pgn_prefix_mismatch")

    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": reasons,
    }


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    truth = json.loads((root / "reviewer_pack" / "hidden_truth.json").read_text())
    result = evaluate(root / "candidate", truth)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
