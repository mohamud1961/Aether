"""Shared asset resolution for mirrored BFCL adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BFCL_SAMPLE_PATH_CANDIDATES = (
    REPO_ROOT / "research/sources/codebases/deepagents/libs/evals/tests/evals/data/benchmark_samples/bfcl_v3_final.json",
    REPO_ROOT / "tracking/collab/final_harness_eval_suite/adapter_fixtures/bfcl/benchmark_samples/bfcl_v3_final.json",
)
BFCL_API_DIR_CANDIDATES = (
    REPO_ROOT / "research/sources/codebases/deepagents/libs/evals/tests/evals/data/bfcl_apis",
    REPO_ROOT / "tracking/collab/final_harness_eval_suite/adapter_fixtures/bfcl/bfcl_apis",
)


def resolve_bfcl_samples_path() -> Path:
    return _resolve_existing_path(BFCL_SAMPLE_PATH_CANDIDATES, asset_label="BFCL mirrored sample payload")


def resolve_bfcl_apis_dir() -> Path:
    return _resolve_existing_path(BFCL_API_DIR_CANDIDATES, asset_label="BFCL mirrored API directory")


def bfcl_asset_preflight() -> dict[str, Any]:
    selected_sample_path = _first_existing_path(BFCL_SAMPLE_PATH_CANDIDATES)
    selected_apis_dir = _first_existing_path(BFCL_API_DIR_CANDIDATES)
    missing_paths = [str(path) for path in (*BFCL_SAMPLE_PATH_CANDIDATES, *BFCL_API_DIR_CANDIDATES) if not path.exists()]
    blockers: list[str] = []
    if selected_sample_path is None or selected_apis_dir is None:
        blockers.append("missing_bfcl_mirrored_assets")
    return {
        "native_runtime_available": not blockers,
        "blocker_codes": blockers,
        "missing_paths": missing_paths,
        "selected_sample_path": str(selected_sample_path) if selected_sample_path else "",
        "selected_apis_dir": str(selected_apis_dir) if selected_apis_dir else "",
        "sample_path_candidates": [str(path) for path in BFCL_SAMPLE_PATH_CANDIDATES],
        "api_dir_candidates": [str(path) for path in BFCL_API_DIR_CANDIDATES],
    }


def _first_existing_path(candidates: tuple[Path, ...]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_existing_path(candidates: tuple[Path, ...], *, asset_label: str) -> Path:
    selected = _first_existing_path(candidates)
    if selected is not None:
        return selected
    checked = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"{asset_label} missing; checked {checked}")
