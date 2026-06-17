"""Run the public manifest repair smoke pack without any model calls."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runner.eval_substrate_contracts import validate_result_row, validate_task_pack
from runner.eval_substrate_scoreboard import aggregate_result_rows

PACK_ROOT = REPO_ROOT / "eval_suite" / "custom" / "public_manifest_repair_smoke"
TASK_PACK_PATH = PACK_ROOT / "task_pack.json"
BOARD_PATH = REPO_ROOT / "eval_suite" / "boards" / "public_manifest_repair_smoke_v1.json"
EXAMPLE_SCOREBOARD_PATH = REPO_ROOT / "eval_suite" / "scoreboards" / "public_manifest_repair_smoke_v1.example.scoreboard.json"
GRADER_PATH = PACK_ROOT / "grader.py"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _load_grader_module():
    spec = importlib.util.spec_from_file_location("public_manifest_repair_smoke_grader", GRADER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load public manifest repair grader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _build_result_row(
    *,
    run_id: str,
    grade: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    row = {
        "run_id": run_id,
        "eval_id": "public_manifest_repair_smoke_v1",
        "task_pack_id": "public_manifest_repair_smoke_v1",
        "family": "public_manifest_repair_smoke",
        "surface_type": "verifier_repair",
        "admission_level": "diagnostic",
        "backend_ref": "debug_local_no_sandbox",
        "environment_ref": f"{label}/environment_manifest.json",
        "artifact_refs": [f"{label}/artifact_bundle.json"],
        "trace_refs": [f"{label}/trace.json"],
        "closure_status": "closed",
        "task_truth_status": "pass" if grade["verdict"] == "pass" else "fail",
        "contamination_status": "clean",
        "failure_class": "none" if grade["verdict"] == "pass" else "verification_grading",
        "reason_codes": list(grade["reason_codes"]),
        "verifier_ref": str(GRADER_PATH.relative_to(REPO_ROOT)),
        "grader_ref": f"{label}/grader_output.json",
        "score": float(grade["score"]),
    }
    return validate_result_row(row)


def run_public_manifest_repair_smoke(*, output_root: Path) -> dict[str, Any]:
    task_pack = validate_task_pack(_load_json(TASK_PACK_PATH))
    board = _load_json(BOARD_PATH)
    grader = _load_grader_module()
    pass_root = output_root / "pass"
    fail_root = output_root / "known_bad"

    fixture_root = PACK_ROOT / "fixture"
    _copy_tree(fixture_root / "workspace", pass_root / "workspace")
    _copy_tree(fixture_root / "reference", pass_root / "reference")
    _copy_tree(fixture_root / "workspace", fail_root / "workspace")
    _copy_tree(fixture_root / "reference", fail_root / "reference")

    pass_workspace = pass_root / "workspace"
    pass_reference = pass_root / "reference"
    pass_workspace_release = pass_workspace / "release"
    pass_workspace_release.joinpath("manifest.json").write_text(
        (pass_reference / "manifest.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    pass_workspace_release.joinpath("summary.txt").write_text(
        (pass_reference / "summary.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    pass_workspace_release.joinpath("checksum.txt").write_text(
        (pass_reference / "checksum.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    grades = {
        "pass": grader.grade_workspace(
            workspace_root=pass_workspace,
            reference_root=pass_reference,
            mode="visible",
        ),
        "known_bad": grader.grade_workspace(
            workspace_root=fail_root / "workspace",
            reference_root=fail_root / "reference",
            mode="visible",
        ),
    }

    result_rows = []
    for label, grade in grades.items():
        artifact_root = output_root / label
        grader_output = _write_json(artifact_root / "grader_output.json", grade)
        _write_json(
            artifact_root / "environment_manifest.json",
            {
                "sandbox_type": "debug_local_no_sandbox",
                "python_command": "python3",
                "cwd": str(REPO_ROOT),
                "fixture_root_ref": str(fixture_root.relative_to(REPO_ROOT)),
                "board_ref": str(BOARD_PATH.relative_to(REPO_ROOT)),
                "task_pack_ref": str(TASK_PACK_PATH.relative_to(REPO_ROOT)),
                "reference_root_ref": str((artifact_root / "reference").relative_to(output_root)),
            },
        )
        _write_json(
            artifact_root / "artifact_bundle.json",
            {
                "board_id": board["board_id"],
                "task_pack_id": task_pack["task_id"],
                "workspace_ref": f"{label}/workspace",
                "reference_ref": f"{label}/reference",
                "grader_output_ref": f"{label}/grader_output.json",
                "grade": grade,
            },
        )
        _write_json(
            artifact_root / "trace.json",
            {
                "board_id": board["board_id"],
                "run_label": label,
                "mode": "public_smoke_example",
                "tool_calls": [],
                "notes": "No model call. Deterministic grader-only public smoke.",
            },
        )
        result_rows.append(
            _build_result_row(
                run_id=f"public_manifest_repair_smoke_{label}",
                grade=grade,
                label=label,
            )
        )

    scoreboard = aggregate_result_rows(result_rows)
    output = {
        "board_id": board["board_id"],
        "example_only": True,
        "scope_label": "public_smoke_example_not_benchmark_evidence",
        "result_rows": result_rows,
        "scoreboard": scoreboard,
    }
    _write_json(output_root / "public_manifest_repair_smoke_example.json", output)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the public manifest repair smoke pack.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)

    run_public_manifest_repair_smoke(output_root=args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
