#!/usr/bin/env python3
"""Run the authoritative final harness eval suite board for one selected recipe + route variant."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runner import agent as agent_module
from runner.azure_openai_env import detect_azure_openai_routes
from runner import benchmark_adapter_acebench as acebench_adapter
from runner import benchmark_adapter_bfcl as bfcl_adapter
from runner import benchmark_adapter_bfcl_native as bfcl_native_adapter
from runner import benchmark_adapter_contextbench as contextbench_adapter
from runner import benchmark_adapter_letta as letta_adapter
from runner import benchmark_adapter_terminalbench as terminalbench_adapter
from runner import bfcl_assets
from runner.agent import run_reference_baseline
from runner.certified_sandbox import build_environment_manifest
from runner.eval_batch_runner import _token_and_cost_summary
from runner.eval_substrate_contracts import result_row_verdict, validate_result_row
from runner.eval_substrate_scoreboard import aggregate_result_rows
from runner.final_harness_eval_suite_adapter import FinalSuiteRowSpec, load_final_suite_row_specs
from runner.model_client import (
    LocalStubModelClient,
    make_azure_gpt53_codex_route_from_env,
    make_azure_gpt54_mini_route_from_env,
)
from runner.terminalbench_paths import resolve_terminalbench_tasks_root
from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
)
from runner.terminalbench_paths import resolve_terminalbench_task_root
from tools.render_final_harness_scoreboard import _load_yaml, _registry_view, render_scoreboard, write_scoreboard_outputs

DEFAULT_OUTPUT_ROOT = REPO_ROOT / "tracking/collab/final_harness_eval_suite/runs"
DEFAULT_IMAGE = "python:3.12-slim"
DEFAULT_BACKEND_REF = "azure_vm_docker"
ROW_CERTIFICATION_LABELS = {
    "certified_for_promotion_math",
    "diagnostic_only",
    "quarantine",
    "holdout",
}


class CertifiedRouteResolutionError(RuntimeError):
    """Fail-closed route resolution error for certified baseline runs."""

    def __init__(self, reason_code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.details = dict(details or {})


def _load_row_certification_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"row certification manifest must be a JSON object: {path}")
    rows = data.get("rows")
    if not isinstance(rows, dict):
        raise ValueError(f"row certification manifest missing rows mapping: {path}")
    selection_sets = data.get("selection_sets")
    if selection_sets is not None and not isinstance(selection_sets, dict):
        raise ValueError(f"row certification manifest selection_sets must be an object: {path}")
    return data


def _row_certification_entry(
    manifest: dict[str, Any] | None,
    row_id: str,
) -> dict[str, Any] | None:
    if not isinstance(manifest, dict):
        return None
    rows = manifest.get("rows")
    if not isinstance(rows, dict):
        raise ValueError("row certification manifest rows must be a mapping")
    entry = rows.get(row_id)
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise ValueError(f"row certification entry for {row_id} must be an object")
    admission_label = entry.get("admission_label")
    if admission_label not in ROW_CERTIFICATION_LABELS:
        raise ValueError(f"row certification entry for {row_id} has invalid admission label: {admission_label!r}")
    evidence_paths = entry.get("evidence_paths")
    if not isinstance(evidence_paths, list) or not evidence_paths:
        raise ValueError(f"row certification entry for {row_id} must include evidence_paths: []")
    for index, value in enumerate(evidence_paths):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"row certification entry for {row_id} evidence_paths[{index}] must be a string")
    return entry


def _apply_row_certification_metadata(
    *,
    row: dict[str, Any],
    row_spec: FinalSuiteRowSpec,
    certification_entry: dict[str, Any] | None,
    manifest_ref: str | None,
) -> dict[str, Any]:
    if certification_entry is None:
        return row
    final_board = row.get("final_board")
    if not isinstance(final_board, dict):
        raise ValueError(f"result row {row_spec.row_id} missing final_board for certification metadata")
    admission_label = str(certification_entry["admission_label"])
    evidence_paths = [str(path) for path in certification_entry["evidence_paths"]]
    final_board["admission_label"] = admission_label
    final_board["promotion_math_included"] = admission_label == "certified_for_promotion_math"
    final_board["certification_evidence_refs"] = evidence_paths
    if isinstance(manifest_ref, str) and manifest_ref.strip():
        final_board["row_certification_manifest_ref"] = manifest_ref
    row["certification_claim"] = "promotion_math" if final_board["promotion_math_included"] else "none"
    return row


class RootMappedDockerSandbox:
    """Docker sandbox with configurable container workspace root."""

    container_workspace_root = "/app"
    network_enabled = False
    last_container_id = None
    last_container_active = False
    preserve_container_until_external_cleanup = False

    def __init__(
        self,
        cwd: str | Path,
        timeout_sec: int = 600,
        sandbox_type: str = "docker",
        sandbox_image: str | None = None,
    ) -> None:
        self.host_cwd = Path(cwd).resolve()
        self.timeout_sec = max(timeout_sec, 600)
        self.sandbox_type = sandbox_type
        self.sandbox_image = sandbox_image or DEFAULT_IMAGE
        self.network_enabled = RootMappedDockerSandbox.network_enabled
        self._container_id: str | None = None
        self._active = False

    def __enter__(self) -> "RootMappedDockerSandbox":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.stop()
        return False

    def start(self) -> None:
        self.host_cwd.mkdir(parents=True, exist_ok=True)
        if self._active:
            return
        if self.sandbox_type != "docker":
            raise ValueError("final suite baseline requires sandbox_type=docker")

        network_mode = "bridge" if self.network_enabled else "none"
        completed = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "-w",
                self.container_workspace_root,
                "-v",
                f"{self.host_cwd}:{self.container_workspace_root}",
                "--network",
                network_mode,
                self.sandbox_image,
                "sleep",
                "infinity",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"failed to start docker sandbox: {completed.stderr.strip()}")
        self._container_id = completed.stdout.strip()
        self._active = True
        RootMappedDockerSandbox.last_container_id = self._container_id
        RootMappedDockerSandbox.last_container_active = True

    def exec(self, command: str, timeout_sec: int | None = None) -> dict[str, Any]:
        if not self._active or not self._container_id:
            raise RuntimeError("sandbox must be started before exec")

        try:
            completed = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-w",
                    self.container_workspace_root,
                    self._container_id,
                    "bash",
                    "-lc",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=int(timeout_sec if timeout_sec is not None else self.timeout_sec),
                check=False,
            )
            return {
                "command": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "command": command,
                "exit_code": 124,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "timed_out": True,
            }

    def workspace_state(self) -> dict[str, Any]:
        return {
            "sandbox_type": "docker",
            "sandbox_image": self.sandbox_image,
            "cwd": self.container_workspace_root,
            "host_cwd": str(self.host_cwd),
            "active": self._active,
            "container_id": self._container_id,
        }

    def stop(self) -> None:
        container_id = self._container_id
        preserve_container = RootMappedDockerSandbox.preserve_container_until_external_cleanup
        if container_id and not preserve_container:
            subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, text=True, check=False)
        if not preserve_container and RootMappedDockerSandbox.last_container_id == container_id:
            RootMappedDockerSandbox.last_container_id = None
            RootMappedDockerSandbox.last_container_active = False
        self._container_id = None
        self._active = False


def run_final_harness_eval_suite_baseline(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    image: str = DEFAULT_IMAGE,
    backend_ref: str = DEFAULT_BACKEND_REF,
    recipe_id: str = "recipe_control",
    model_mode: str = "auto",
    max_steps: int = 14,
    model_timeout_sec: int = 120,
    include_sources: tuple[str, ...] = ("task_pack", "benchmark_adapter", "terminalbench_challenge"),
    benchmark_mode: str = "native",
    variant_id: str = "active_evidence_kernel_v1",
    row_ids: tuple[str, ...] | None = None,
    row_certification_manifest: Path | None = None,
    admission_labels: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = output_root.resolve() / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    recipe = _load_recipe(REPO_ROOT, recipe_id)
    all_row_specs = load_final_suite_row_specs(REPO_ROOT)
    row_specs = [row for row in all_row_specs if row.execution_source in include_sources]
    if row_ids is not None:
        row_specs = [row for row in row_specs if row.row_id in row_ids]
    certification_manifest: dict[str, Any] | None = None
    certification_manifest_ref: str | None = None
    if row_certification_manifest is not None:
        certification_manifest = _load_row_certification_manifest(row_certification_manifest)
        certification_manifest_path = run_root / "row_certification_manifest.json"
        _write_json(certification_manifest_path, certification_manifest)
        certification_manifest_ref = str(certification_manifest_path)
        missing_custom_row_ids = [
            row.row_id
            for row in all_row_specs
            if row.execution_source == "task_pack" and _row_certification_entry(certification_manifest, row.row_id) is None
        ]
        if missing_custom_row_ids:
            raise ValueError(
                "row certification manifest missing custom row ids: " + ", ".join(sorted(missing_custom_row_ids))
            )
    if admission_labels is not None and certification_manifest is None:
        raise ValueError("admission_labels require row_certification_manifest")
    requested_admission_labels = tuple(admission_labels or ())
    requested_admission_label_set = set(requested_admission_labels)
    selected_row_specs: list[FinalSuiteRowSpec] = []
    selection_row_ids: list[str] = []
    for row_spec in row_specs:
        certification_entry = _row_certification_entry(certification_manifest, row_spec.row_id)
        if requested_admission_labels:
            if certification_entry is None:
                continue
            if str(certification_entry["admission_label"]) not in requested_admission_label_set:
                continue
        selected_row_specs.append(row_spec)
        selection_row_ids.append(row_spec.row_id)
    if requested_admission_labels and not selected_row_specs:
        raise ValueError(
            "no rows selected for admission labels: " + ", ".join(sorted(requested_admission_label_set))
        )
    promotion_math_row_ids = [
        row_spec.row_id
        for row_spec in selected_row_specs
        if str((_row_certification_entry(certification_manifest, row_spec.row_id) or {}).get("admission_label"))
        == "certified_for_promotion_math"
    ]
    route_manifest = build_packet04_route_manifest(
        variant_id=variant_id,
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    route_manifest_path = _write_json(run_root / "route_manifest.json", route_manifest)
    docker_runtime_status = _docker_runtime_status()
    docker_available = bool(docker_runtime_status.get("available", False))
    _write_json(
        run_root / "recipe_manifest_snapshot.yaml.json",
        {"recipe_id": recipe_id, "recipe": recipe, "source": "tracking/collab/final_harness_eval_suite/recipe_candidates.yaml"},
    )
    shutil.copy2(
        REPO_ROOT / "tracking/collab/final_harness_eval_suite/recipe_candidates.yaml",
        run_root / "recipe_manifest_snapshot.yaml",
    )

    route_resolution_error: CertifiedRouteResolutionError | None = None
    selected_model_route: dict[str, Any] | None = None
    try:
        selected_model_route, model_route_mode = _resolve_model_route(model_mode)
    except CertifiedRouteResolutionError as exc:
        route_resolution_error = exc
        model_route_mode = exc.reason_code

    rows: list[dict[str, Any]] = []
    original_sandbox = agent_module.DockerSandbox
    if docker_available:
        agent_module.DockerSandbox = RootMappedDockerSandbox
    try:
        for row_spec in selected_row_specs:
            certification_entry = _row_certification_entry(certification_manifest, row_spec.row_id)
            if route_resolution_error is not None:
                row = _build_route_resolution_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    backend_ref=backend_ref,
                    recipe_id=recipe_id,
                    model_route_mode=model_route_mode,
                    route_error=route_resolution_error,
                )
                row = _apply_row_certification_metadata(
                    row=row,
                    row_spec=row_spec,
                    certification_entry=certification_entry,
                    manifest_ref=certification_manifest_ref,
                )
                _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
                rows.append(row)
                continue
            row_route_manifest = dict(route_manifest)
            if row_spec.execution_source == "task_pack":
                row_route_manifest["required_artifact_paths"] = [row_spec.expected_candidate_output]
            if not docker_available and _row_requires_docker(row_spec):
                row = _build_environment_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    backend_ref=backend_ref,
                    recipe_id=recipe_id,
                    docker_runtime_status=docker_runtime_status,
                )
                row = _apply_row_certification_metadata(
                    row=row,
                    row_spec=row_spec,
                    certification_entry=certification_entry,
                    manifest_ref=certification_manifest_ref,
                )
                _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
                rows.append(row)
                continue
            if row_spec.execution_source == "task_pack":
                row = _run_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    image=image,
                    backend_ref=backend_ref,
                    recipe_id=recipe_id,
                    model_route=dict(selected_model_route or {}),
                    model_route_mode=model_route_mode,
                    max_steps=max_steps,
                    model_timeout_sec=model_timeout_sec,
                    variant_id=variant_id,
                    route_manifest=row_route_manifest,
                )
                row = _apply_row_certification_metadata(
                    row=row,
                    row_spec=row_spec,
                    certification_entry=certification_entry,
                    manifest_ref=certification_manifest_ref,
                )
                _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
                rows.append(row)
                continue
            if row_spec.execution_source == "benchmark_adapter":
                row = _run_benchmark_adapter_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    backend_ref=backend_ref,
                    recipe_id=recipe_id,
                    model_route=dict(selected_model_route or {}),
                    model_route_mode=model_route_mode,
                    max_steps=max_steps,
                    model_timeout_sec=model_timeout_sec,
                    variant_id=variant_id,
                    benchmark_mode=benchmark_mode,
                    route_manifest=route_manifest,
                )
                row = _apply_row_certification_metadata(
                    row=row,
                    row_spec=row_spec,
                    certification_entry=certification_entry,
                    manifest_ref=certification_manifest_ref,
                )
                _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
                rows.append(row)
                continue
            if row_spec.execution_source == "terminalbench_challenge":
                row = _run_terminalbench_challenge_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    backend_ref=backend_ref,
                    recipe_id=recipe_id,
                    model_route=dict(selected_model_route or {}),
                    model_route_mode=model_route_mode,
                    max_steps=max_steps,
                    model_timeout_sec=model_timeout_sec,
                    variant_id=variant_id,
                    route_manifest=route_manifest,
                )
                row = _apply_row_certification_metadata(
                    row=row,
                    row_spec=row_spec,
                    certification_entry=certification_entry,
                    manifest_ref=certification_manifest_ref,
                )
                _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
                rows.append(row)
                continue
            raise ValueError(f"unsupported final suite execution source: {row_spec.execution_source}")
    finally:
        agent_module.DockerSandbox = original_sandbox

    result_rows_jsonl = run_root / "result_rows.jsonl"
    result_rows_jsonl.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    scoreboard = aggregate_result_rows(rows)
    scoreboard_path = _write_json(run_root / "result_rows_scoreboard.json", scoreboard)
    contamination_review = _build_contamination_review(rows)
    contamination_path = _write_json(run_root / "contamination_review.json", contamination_review)
    invalidity_report = _build_invalidity_report(rows)
    invalidity_path = _write_json(run_root / "invalidity_report.json", invalidity_report)

    final_board_score = _render_final_board_scoreboard(
        run_id=run_id,
        rows=rows,
        recipe_id=recipe_id,
        run_root=run_root,
        cost_summary=scoreboard["cost_summary"],
    )
    finalist_selection_path = _write_non_claiming_finalist_selection(run_root / "finalist_selection.md", run_id, recipe_id)
    _write_json(
        run_root / "run_summary.json",
        {
            "schema_version": "final_harness_eval_suite_baseline_run.v1",
            "run_id": run_id,
            "board_id": "final_harness_eval_suite_v1",
            "recipe_id": recipe_id,
            "row_count": len(rows),
            "selected_row_count": len(selection_row_ids),
            "loaded_row_count": len(row_specs),
            "private_task_pack_row_count": sum(1 for row in selected_row_specs if row.execution_source == "task_pack"),
            "official_benchmark_row_count": sum(1 for row in selected_row_specs if row.execution_source == "benchmark_adapter"),
            "terminalbench_challenge_row_count": sum(1 for row in selected_row_specs if row.execution_source == "terminalbench_challenge"),
            "backend_ref": backend_ref,
            "image": image,
            "variant_id": variant_id,
            "route_manifest_ref": str(route_manifest_path),
            "model_route_mode": model_route_mode,
            "docker_available": docker_available,
            "docker_runtime_status": docker_runtime_status,
            "row_certification_manifest_ref": certification_manifest_ref,
            "row_certification_manifest_source_ref": str(row_certification_manifest) if row_certification_manifest is not None else None,
            "row_certification_selection_labels": list(requested_admission_labels),
            "row_certification_selected_row_ids": selection_row_ids,
            "promotion_math_selected_row_ids": promotion_math_row_ids,
            "result_rows_jsonl": str(result_rows_jsonl),
            "result_rows_scoreboard_json": str(scoreboard_path),
            "contamination_review_json": str(contamination_path),
            "invalidity_report_json": str(invalidity_path),
            "scoreboard_json": str(final_board_score["scoreboard_json"]),
            "scoreboard_md": str(final_board_score["scoreboard_md"]),
            "cost_summary": scoreboard["cost_summary"],
            "finalist_selection_md": str(finalist_selection_path),
            "notes": [
                f"Board executed for recipe `{recipe_id}` with route variant `{variant_id}`.",
                "No finalist or winner claims are produced from this single-recipe run.",
                "Private task-pack rows are marked invalid when Docker is unavailable in the local environment.",
                "Official benchmark rows are adapter-driven contract checks, not native benchmark authority claims.",
                "Certified route policy is Azure-first: auto/default uses Azure gpt-5.4-mini and does not fall back to codex_subscription.",
                "Explicit stub mode remains debug-only and is not benchmark-grade evidence.",
                f"Benchmark mode: {benchmark_mode}.",
            ]
            + (
                [
                    f"Route resolution failed closed before row execution: {route_resolution_error.reason_code}.",
                ]
                if route_resolution_error is not None
                else []
            ),
        },
    )
    return {
        "run_id": run_id,
        "run_root": str(run_root),
        "row_count": len(rows),
        "selected_row_count": len(selection_row_ids),
        "variant_id": variant_id,
        "model_route_mode": model_route_mode,
        "result_rows_jsonl": str(result_rows_jsonl),
        "scoreboard_json": str(final_board_score["scoreboard_json"]),
        "route_manifest_ref": str(route_manifest_path),
        "row_certification_manifest_ref": certification_manifest_ref,
        "row_certification_selection_labels": list(requested_admission_labels),
        "row_certification_selected_row_ids": selection_row_ids,
        "promotion_math_selected_row_ids": promotion_math_row_ids,
        "docker_available": docker_available,
        "cost_summary": scoreboard["cost_summary"],
    }


def _run_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    image: str,
    backend_ref: str,
    recipe_id: str,
    model_route: dict[str, Any],
    model_route_mode: str,
    max_steps: int,
    model_timeout_sec: int,
    variant_id: str = "active_evidence_kernel_v1",
    route_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_root = run_root / "rows" / row_spec.row_id
    workspace_root = row_root / "workspace"
    grading_root = row_root / "grading_pack"
    task_pack_root = (REPO_ROOT / row_spec.task_pack_ref).parent
    _stage_workspace(task_pack_root, workspace_root, row_spec)
    _stage_grading_pack(task_pack_root, grading_root)
    before_hashes = _hash_workspace(workspace_root)

    container_root = row_spec.canonical_workspace_root
    RootMappedDockerSandbox.container_workspace_root = container_root
    manifest = build_environment_manifest(
        host_workspace_path=str(workspace_root),
        backend_type="linux_container",
        image_metadata={"image": image, "backend": backend_ref},
        python_interpreter=row_spec.runtime_python_command,
        sandbox_type="docker",
        task_declared_canonical_root=container_root,
        container_workspace_path=container_root,
        initial_cwd=container_root,
        workspace_root_override_reason=f"row_level_workspace_contract:{row_spec.row_id}",
        network_policy={
            "enabled": _row_network_enabled(row_spec),
            "rationale": "final-suite certified baseline docker execution" if not _row_network_enabled(row_spec) else "task-declared outbound network access allowed",
            "allowed_endpoints": [] if not _row_network_enabled(row_spec) else ["*"],
            "grading_impact": "none" if not _row_network_enabled(row_spec) else "dynamic network enabled",
            "reproducibility_note": "network disabled for row execution" if not _row_network_enabled(row_spec) else "network enabled for row execution",
        },
    )
    manifest_ref = _write_json(row_root / "artifacts" / "environment_manifest.json", manifest)

    route_result = run_reference_baseline(
        run_id=row_spec.row_id,
        run_dir=row_root / "route_trace",
        task_id=row_spec.task_pack_id,
        task_prompt=_build_row_prompt(task_pack_root, row_spec),
        benchmark_family="final_harness_eval_suite_baseline_control",
        case_id=row_spec.row_id,
        seed_id=variant_id,
        model_route=model_route,
        model_client_kwargs=_model_client_kwargs(model_timeout_sec),
        max_steps=max_steps,
        timeout_sec=max(row_spec.max_solver_seconds, 120),
        sandbox_type="docker",
        sandbox_image=image,
        cwd=workspace_root,
        orientation_env_overrides={"cwd": container_root, "task_id": row_spec.task_pack_id},
        route_manifest=route_manifest,
        enforce_packet04_route_contract=True,
    )
    model_client_error = _extract_model_client_error(route_result)
    if model_client_error is not None:
        return _build_model_client_invalid_row(
            run_root=run_root,
            row_spec=row_spec,
            backend_ref=backend_ref,
            recipe_id=recipe_id,
            model_route_mode=model_route_mode,
            route_result=route_result,
            model_client_error=model_client_error,
        )

    visible_result = _run_visible_verifier(task_pack_root, workspace_root, container_root, image, row_spec)
    trace_payload = _build_trace_payload(row_root, row_spec, route_result, visible_result, before_hashes, _hash_workspace(workspace_root))
    trace_path = _write_json(row_root / "traces" / "trace.json", trace_payload)
    grader_result = _run_grader(task_pack_root, grading_root, workspace_root, trace_path, row_spec)
    grader_ref = _write_json(row_root / "artifacts" / "grader_output.json", grader_result)
    verifier_ref = _write_json(row_root / "artifacts" / "verifier_output.json", visible_result)
    truth_alignment = _route_grader_truth_alignment(
        route_result=route_result,
        visible_result=visible_result,
        grader_result=grader_result,
    )
    token_and_cost_summary = _row_token_and_cost_summary(route_result)
    control_plane_artifact_refs = route_result.get("control_plane_artifacts") if isinstance(route_result.get("control_plane_artifacts"), dict) else {}
    execution_truth_ref = _write_json(
        row_root / "artifacts" / "execution_truth.json",
        _build_execution_truth_payload(
            route_result=route_result,
            visible_result=visible_result,
            grader_result=grader_result,
            truth_alignment=truth_alignment,
        ),
    )
    artifact_ref = _write_json(
        row_root / "artifacts" / "artifact_bundle.json",
        {
            "environment_manifest_ref": str(manifest_ref),
            "verifier_ref": str(verifier_ref),
            "grader_ref": str(grader_ref),
            "execution_truth_ref": str(execution_truth_ref),
            "trace_ref": str(trace_path),
            "route_trace_ref": str(row_root / "route_trace" / "run_events.jsonl"),
            **(
                {"control_plane_artifact_refs": dict(control_plane_artifact_refs)}
                if isinstance(control_plane_artifact_refs, dict) and control_plane_artifact_refs
                else {}
            ),
        },
    )

    passed = _grader_passed(grader_result)
    score = float(grader_result.get("score", 1.0 if passed else 0.0))
    contamination_status = "contaminated" if "hidden_truth_access_attempt" in _grader_reason_codes(grader_result) else "clean"
    failure_class = _normalize_failure_class(str(grader_result.get("failure_class", "none")), passed)
    row_reason_codes = _merged_reason_codes(
        _grader_reason_codes(grader_result) or (["row_passed"] if passed else ["grader_failed"]),
        truth_alignment.get("reason_codes", []),
    )
    row = {
        "run_id": f"{row_spec.row_id}__{recipe_id}",
        "eval_id": "final_harness_eval_suite_baseline_control",
        "task_pack_id": row_spec.task_pack_id,
        "family": "final_harness_eval_suite",
        "surface_type": row_spec.surface_type,
        "admission_level": "certified",
        "backend_ref": backend_ref,
        "environment_ref": str(manifest_ref),
        "artifact_refs": [str(artifact_ref)],
        "trace_refs": [str(trace_path), str(row_root / "route_trace" / "run_events.jsonl")],
        "closure_status": "closed",
        "task_truth_status": "pass" if passed else "fail",
        "contamination_status": contamination_status,
        "failure_class": failure_class,
        "reason_codes": row_reason_codes,
        "verifier_ref": str(verifier_ref),
        "grader_ref": str(grader_ref),
        "score": score,
        "truth_alignment": truth_alignment,
        "token_and_cost_summary": token_and_cost_summary,
        **(
            {"control_plane_artifact_refs": dict(control_plane_artifact_refs)}
            if isinstance(control_plane_artifact_refs, dict) and control_plane_artifact_refs
            else {}
        ),
        "final_board": {
            "board_id": "final_harness_eval_suite_v1",
            "board_version": 1,
            "recipe_id": recipe_id,
            "recipe_snapshot_ref": str(run_root / "recipe_manifest_snapshot.yaml"),
            "row_id": row_spec.row_id,
            "row_type": row_spec.row_type,
            "is_flagship": row_spec.is_flagship,
            "critical_clusters": list(row_spec.critical_clusters),
            "provenance_type": row_spec.provenance_type,
            "contamination_gate": "clean" if contamination_status == "clean" else "contaminated_blocked",
            "invalidity_gate": "valid",
            "current_stack_ref": "tracking/collab/final_harness_eval_suite/current_stack_manifest.yaml",
            "lane_id": row_spec.lane_id,
            "execution_source": row_spec.execution_source,
        },
        "model_route_mode": model_route_mode,
    }
    row["verdict"] = result_row_verdict(row)
    validate_result_row(row)
    _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
    return row


def _row_token_and_cost_summary(route_result: dict[str, Any] | None) -> dict[str, Any]:
    execution_result = dict(route_result) if isinstance(route_result, dict) else {}
    if not isinstance(execution_result.get("execution"), dict):
        execution_result["execution"] = {"steps": []}
    return _token_and_cost_summary(execution_result)


def _build_environment_invalid_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    backend_ref: str,
    recipe_id: str,
    docker_runtime_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_status = docker_runtime_status if isinstance(docker_runtime_status, dict) else {}
    docker_reason_code = runtime_status.get("reason_code")
    if not isinstance(docker_reason_code, str) or not docker_reason_code:
        docker_reason_code = "invalid_environment_docker_unavailable"
    docker_reason = runtime_status.get("reason")
    if not isinstance(docker_reason, str) or not docker_reason:
        docker_reason = "docker runtime unavailable"
    docker_probe = runtime_status.get("probe")
    if not isinstance(docker_probe, dict):
        docker_probe = {}
    row_root = run_root / "rows" / row_spec.row_id
    manifest_ref = _write_json(
        row_root / "artifacts" / "environment_manifest.json",
        {
            "status": "invalid_due_to_environment",
            "reason_code": docker_reason_code,
            "reason": docker_reason,
            "docker_probe": docker_probe,
            "expected_canonical_workspace_root": row_spec.canonical_workspace_root,
        },
    )
    verifier_ref = _write_json(
        row_root / "artifacts" / "verifier_output.json",
        {"status": "not_executed", "reason_code": docker_reason_code, "reason": docker_reason},
    )
    grader_ref = _write_json(
        row_root / "artifacts" / "grader_output.json",
        {"status": "not_executed", "reason_codes": [docker_reason_code], "reason": docker_reason},
    )
    trace_ref = _write_json(
        row_root / "traces" / "trace.json",
        {
            "meta": {"workspace_root": row_spec.canonical_workspace_root, "timed_out": False, "infrastructure_timeout": True},
            "events": [],
        },
    )
    execution_truth_ref = _write_json(
        row_root / "artifacts" / "execution_truth.json",
        _build_invalid_execution_truth_payload(
            row_spec=row_spec,
            reason_code=docker_reason_code,
            reason=docker_reason,
            verifier_ref=verifier_ref,
            grader_ref=grader_ref,
            trace_ref=trace_ref,
            runtime_details={"docker_probe": docker_probe},
        ),
    )
    artifact_ref = _write_json(
        row_root / "artifacts" / "artifact_bundle.json",
        {
            "environment_manifest_ref": str(manifest_ref),
            "verifier_ref": str(verifier_ref),
            "grader_ref": str(grader_ref),
            "trace_ref": str(trace_ref),
            "execution_truth_ref": str(execution_truth_ref),
            "status": "invalid_due_to_environment",
        },
    )
    row = {
        "run_id": f"{row_spec.row_id}__{recipe_id}",
        "eval_id": "final_harness_eval_suite_baseline_control",
        "task_pack_id": row_spec.task_pack_id,
        "family": "final_harness_eval_suite",
        "surface_type": row_spec.surface_type,
        "admission_level": "certified",
        "backend_ref": backend_ref,
        "environment_ref": str(manifest_ref),
        "artifact_refs": [str(artifact_ref)],
        "trace_refs": [str(trace_ref)],
        "closure_status": "invalid",
        "task_truth_status": "invalid",
        "contamination_status": "unknown",
        "failure_class": "sandbox",
        "reason_codes": [docker_reason_code],
        "verifier_ref": str(verifier_ref),
        "grader_ref": str(grader_ref),
        "score": 0.0,
        "token_and_cost_summary": _row_token_and_cost_summary(None),
        "final_board": {
            "board_id": "final_harness_eval_suite_v1",
            "board_version": 1,
            "recipe_id": recipe_id,
            "recipe_snapshot_ref": str(run_root / "recipe_manifest_snapshot.yaml"),
            "row_id": row_spec.row_id,
            "row_type": row_spec.row_type,
            "is_flagship": row_spec.is_flagship,
            "critical_clusters": list(row_spec.critical_clusters),
            "provenance_type": row_spec.provenance_type,
            "contamination_gate": "clean",
            "invalidity_gate": "invalid_blocked",
            "current_stack_ref": "tracking/collab/final_harness_eval_suite/current_stack_manifest.yaml",
            "lane_id": row_spec.lane_id,
            "execution_source": row_spec.execution_source,
        },
        "model_route_mode": "not_executed_environment_invalid",
    }
    row["verdict"] = result_row_verdict(row)
    validate_result_row(row)
    _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
    return row


def _row_requires_docker(row_spec: FinalSuiteRowSpec) -> bool:
    return row_spec.execution_source in {"task_pack", "benchmark_adapter", "terminalbench_challenge"}


def _run_benchmark_adapter_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    backend_ref: str,
    recipe_id: str,
    model_route: dict[str, Any],
    model_route_mode: str,
    max_steps: int,
    model_timeout_sec: int,
    variant_id: str = "active_evidence_kernel_v1",
    benchmark_mode: str = "native",
    route_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_root = run_root / "rows" / row_spec.row_id
    workspace_root = row_root / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    RootMappedDockerSandbox.container_workspace_root = "/workspace"
    RootMappedDockerSandbox.network_enabled = _row_network_enabled(row_spec)
    authority_label = row_spec.authority_label or "equivalent"
    manifest_path = row_root / "artifacts" / "environment_manifest.json"
    manifest_ref = _write_json(
        manifest_path,
        {
            "status": "adapter_model_attempt" if benchmark_mode != "native" else "native_model_attempt",
            "adapter_key": row_spec.benchmark_adapter,
            "benchmark_name": row_spec.benchmark_name,
            "benchmark_case_id": row_spec.benchmark_case_id,
            "authority_label": authority_label,
            "certification_claim": "none",
        },
    )
    verifier_ref = _write_json(
        row_root / "artifacts" / "verifier_output.json",
        {"adapter_key": row_spec.benchmark_adapter, "benchmark_case_id": row_spec.benchmark_case_id},
    )

    adapter_key = row_spec.benchmark_adapter or ""
    benchmark_case_id = row_spec.benchmark_case_id or ""
    native_tool_definitions: list[dict[str, Any]] = []
    grader_payload: dict[str, Any]
    try:
        prompt = ""
        if adapter_key == "bfcl":
            preflight = bfcl_assets.bfcl_asset_preflight()
            if not preflight.get("native_runtime_available", False):
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="bfcl_asset_preflight_failed",
                    reason=f"bfcl mirrored assets missing: {preflight.get('missing_paths', [])}",
                )
            try:
                case_native = bfcl_native_adapter.load_official_curated_cases().get(benchmark_case_id)
                case = bfcl_adapter.load_mirrored_cases().get(benchmark_case_id)
            except FileNotFoundError as exc:
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="bfcl_asset_preflight_failed",
                    reason=str(exc),
                )
            if case is None:
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="benchmark_case_not_found",
                    reason=f"bfcl case not found: {benchmark_case_id}",
                )
            if benchmark_mode == "native" and case_native is None:
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="native_benchmark_case_not_found",
                    reason=f"bfcl native case not found: {benchmark_case_id}",
                )
            native_tool_definitions = bfcl_adapter.build_native_tool_definitions(case_native if benchmark_mode == "native" and case_native is not None else case)
            prompt = (
                "Return only a Python list literal of function-call expressions that solve this case.\n"
                "Do not include prose. Example format: [ping(tag='a'), ping(tag='b')].\n"
                f"Case ID: {benchmark_case_id}\n"
                f"Involved classes: {case.get('involved_classes', [])}\n"
                f"Initial config: {json.dumps(case.get('initial_config', {}), sort_keys=True)}\n"
                "Target behavior: follow the intended multi-turn tool sequence for this case."
            )
        elif adapter_key == "acebench":
            spec = acebench_adapter.selected_case_spec(benchmark_case_id)
            if benchmark_mode == "native":
                preflight = acebench_adapter.native_grader_preflight()
                if not preflight.get("native_runtime_available", False):
                    return _build_adapter_invalid_row(
                        run_root=run_root,
                        row_spec=row_spec,
                        recipe_id=recipe_id,
                        backend_ref=backend_ref,
                    reason_code="native_runtime_preflight_failed",
                    reason=f"acebench native preflight blockers: {preflight.get('blocker_codes', [])}",
                )
            native_tool_definitions = acebench_adapter.build_native_tool_definitions(case_id=benchmark_case_id)
            prompt = (
                spec["task_prompt"]
                + "\n\nOutput must be a Python list with exactly one function call expression."
            )
        elif adapter_key == "contextbench":
            spec = contextbench_adapter.load_selected_cases().get(benchmark_case_id)
            if spec is None:
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="benchmark_case_not_found",
                    reason=f"contextbench probe not found: {benchmark_case_id}",
                )
            if benchmark_mode == "native":
                preflight = contextbench_adapter.native_grader_preflight()
                if not preflight.get("native_runtime_available", False):
                    return _build_adapter_invalid_row(
                        run_root=run_root,
                        row_spec=row_spec,
                        recipe_id=recipe_id,
                        backend_ref=backend_ref,
                        reason_code="native_runtime_preflight_failed",
                        reason=f"contextbench native preflight blockers: {preflight.get('blocker_codes', [])}",
                    )
            context_root = workspace_root / "contextbench"
            context_root.mkdir(parents=True, exist_ok=True)
            _write_json(context_root / "request.json", spec["request_payload"])
            shutil.copy2(contextbench_adapter.VERIFIED_CSV_PATH, context_root / "Verified.csv")
            prompt = spec["task_prompt"]
        elif adapter_key == "letta":
            spec = letta_adapter.load_selected_cases().get(benchmark_case_id)
            if spec is None:
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="benchmark_case_not_found",
                    reason=f"letta probe not found: {benchmark_case_id}",
                )
            if benchmark_mode == "native":
                preflight = letta_adapter.native_grader_preflight()
                if not preflight.get("native_runtime_available", False):
                    return _build_adapter_invalid_row(
                        run_root=run_root,
                        row_spec=row_spec,
                        recipe_id=recipe_id,
                        backend_ref=backend_ref,
                        reason_code="native_runtime_preflight_failed",
                        reason=f"letta native preflight blockers: {preflight.get('blocker_codes', [])}",
                    )
            letta_root = workspace_root / "letta" / "filesystem"
            letta_root.mkdir(parents=True, exist_ok=True)
            for rel_path, content in spec.get("workspace_files", {}).items():
                target = workspace_root / rel_path.lstrip("/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(content), encoding="utf-8")
            prompt = spec["task_prompt"]
        elif adapter_key == "terminalbench":
            spec = terminalbench_adapter.load_selected_cases().get(benchmark_case_id)
            if spec is None:
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="benchmark_case_not_found",
                    reason=f"terminalbench public case not found: {benchmark_case_id}",
                )
            task_root = resolve_terminalbench_task_root(benchmark_case_id)
            documents_src = task_root / "environment" / "documents"
            if not documents_src.exists():
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="terminalbench_task_seed_missing",
                    reason=f"terminalbench task seed missing: {documents_src}",
                )
            shutil.copytree(documents_src, workspace_root / "documents", dirs_exist_ok=True)
            (workspace_root / "invoices").mkdir(parents=True, exist_ok=True)
            (workspace_root / "other").mkdir(parents=True, exist_ok=True)
            prompt = spec["task_prompt"]
        else:
            return _build_adapter_invalid_row(
                run_root=run_root,
                row_spec=row_spec,
                recipe_id=recipe_id,
                backend_ref=backend_ref,
                reason_code="unsupported_benchmark_adapter",
                reason=f"unsupported benchmark adapter key: {adapter_key}",
            )

        benchmark_route_manifest = route_manifest
        if native_tool_definitions:
            benchmark_route_manifest = dict(route_manifest or {})
            benchmark_route_manifest["native_tool_definitions"] = native_tool_definitions

        route_result = run_reference_baseline(
            run_id=row_spec.row_id,
            run_dir=row_root / "route_trace",
            task_id=row_spec.task_pack_id,
            task_prompt=prompt,
            benchmark_family="final_harness_eval_suite_baseline_control",
            case_id=benchmark_case_id,
            seed_id=variant_id,
            model_route=model_route,
            model_client_kwargs=_model_client_kwargs(model_timeout_sec),
            max_steps=max_steps,
            timeout_sec=max(120, row_spec.max_solver_seconds),
            sandbox_type="docker",
            sandbox_image=DEFAULT_IMAGE,
            cwd=workspace_root,
            orientation_env_overrides={"cwd": "/app", "task_id": row_spec.task_pack_id},
            route_manifest=benchmark_route_manifest,
            enforce_packet04_route_contract=False,
            )
        model_client_error = _extract_model_client_error(route_result)
        if model_client_error is not None:
            return _build_model_client_invalid_row(
                run_root=run_root,
                row_spec=row_spec,
                backend_ref=backend_ref,
                recipe_id=recipe_id,
                model_route_mode=model_route_mode,
                route_result=route_result,
                model_client_error=model_client_error,
            )
        assistant_text = _extract_final_assistant_text(row_root)
        trace_ref = _write_json(
            row_root / "traces" / "trace.json",
            {
                "control_label": "model_attempt",
                "tool_io": [{"tool": "raw_bash", "assistant_text_len": len(assistant_text)}],
                "runtime_timing": route_result.get("runtime_timing", {}),
            },
        )

        if adapter_key == "bfcl":
            if not bfcl_adapter.supported_case(case):
                return _build_adapter_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    recipe_id=recipe_id,
                    backend_ref=backend_ref,
                    reason_code="benchmark_case_unsupported",
                    reason=f"bfcl case unsupported by mirrored api set: {benchmark_case_id}",
                )
            observed_calls = _extract_bfcl_calls_from_text(assistant_text)
            if benchmark_mode == "native":
                grade = bfcl_native_adapter.grade_bfcl_case_native(case_native, observed_calls)
            else:
                grade = bfcl_adapter.grade_bfcl_case_equivalent(case, observed_calls)
            grader_payload = {"grade": grade, "adapter_key": adapter_key, "benchmark_case_id": benchmark_case_id}
            grader_ref = _write_json(row_root / "artifacts" / "grader_output.json", grader_payload)
            artifact_ref = _write_json(
                row_root / "artifacts" / "artifact_bundle.json",
                {
                    "environment_manifest_ref": str(manifest_ref),
                    "verifier_ref": str(verifier_ref),
                    "grader_ref": str(grader_ref),
                    "trace_refs": [str(trace_ref)],
                    "authority_label": bfcl_native_adapter.ADAPTER_AUTHORITY_LABEL if benchmark_mode == "native" else bfcl_adapter.ADAPTER_AUTHORITY_LABEL,
                },
            )
            if benchmark_mode == "native":
                row = bfcl_native_adapter.build_result_row_for_grade(
                    run_id=f"{row_spec.row_id}__{recipe_id}",
                    eval_id="final_harness_eval_suite_baseline_control",
                    task_pack_id=row_spec.task_pack_id,
                    case_id=benchmark_case_id,
                    control_label="model_attempt",
                    environment_ref=str(manifest_ref),
                    artifact_refs=[str(artifact_ref)],
                    trace_refs=[str(trace_ref)],
                    verifier_ref=str(verifier_ref),
                    grader_ref=str(grader_ref),
                    grade=grade,
                    backend_ref=backend_ref,
                )
            else:
                row = bfcl_adapter.build_result_row_for_grade(
                    run_id=f"{row_spec.row_id}__{recipe_id}",
                    eval_id="final_harness_eval_suite_baseline_control",
                    task_pack_id=row_spec.task_pack_id,
                    case_id=benchmark_case_id,
                    control_label="model_attempt",
                    environment_ref=str(manifest_ref),
                    artifact_refs=[str(artifact_ref)],
                    trace_refs=[str(trace_ref)],
                    verifier_ref=str(verifier_ref),
                    grader_ref=str(grader_ref),
                    grade=grade,
                    backend_ref=backend_ref,
                )
        elif adapter_key == "acebench":
            if benchmark_mode == "native":
                preflight = acebench_adapter.native_grader_preflight()
                grade = acebench_adapter.grade_case_native(
                    observed_text=assistant_text,
                    upstream_root=Path(preflight["upstream_root"]),
                    python_executable=str(preflight["python_executable"]),
                    case_id=benchmark_case_id,
                )
                authority_label_ace = acebench_adapter.NATIVE_AUTHORITY_LABEL
                authority_detail_ace = acebench_adapter.NATIVE_AUTHORITY_DETAIL
            else:
                grade = acebench_adapter.grade_case_equivalent(assistant_text, case_id=benchmark_case_id)
                authority_label_ace = acebench_adapter.EQUIVALENT_AUTHORITY_LABEL
                authority_detail_ace = acebench_adapter.EQUIVALENT_AUTHORITY_DETAIL
            grader_payload = {"grade": grade, "adapter_key": adapter_key, "benchmark_case_id": benchmark_case_id}
            grader_ref = _write_json(row_root / "artifacts" / "grader_output.json", grader_payload)
            artifact_ref = _write_json(
                row_root / "artifacts" / "artifact_bundle.json",
                {
                    "environment_manifest_ref": str(manifest_ref),
                    "verifier_ref": str(verifier_ref),
                    "grader_ref": str(grader_ref),
                    "trace_refs": [str(trace_ref)],
                    "authority_label": authority_label_ace,
                },
            )
            row = acebench_adapter.build_result_row_for_grade(
                run_id=f"{row_spec.row_id}__{recipe_id}",
                eval_id="final_harness_eval_suite_baseline_control",
                task_pack_id=row_spec.task_pack_id,
                control_label="model_attempt",
                environment_ref=str(manifest_ref),
                artifact_refs=[str(artifact_ref)],
                trace_refs=[str(trace_ref)],
                verifier_ref=str(verifier_ref),
                grader_ref=str(grader_ref),
                grade=grade,
                authority_label=authority_label_ace,
                authority_detail=authority_detail_ace,
                case_id=benchmark_case_id,
                backend_ref=backend_ref,
            )
            row = _apply_native_runtime_invalid_override(
                row=row,
                route_result=route_result,
                benchmark_mode=benchmark_mode,
            )
            row["token_and_cost_summary"] = _row_token_and_cost_summary(route_result)
        elif adapter_key == "contextbench":
            if benchmark_mode == "native":
                grade = contextbench_adapter.grade_contextbench_case_native(spec, assistant_text)
            else:
                grade = contextbench_adapter.grade_contextbench_case_equivalent(spec, assistant_text)
            authority_label_ctx = contextbench_adapter.ADAPTER_AUTHORITY_LABEL
            authority_detail_ctx = contextbench_adapter.ADAPTER_AUTHORITY_DETAIL
            grader_payload = {"grade": grade, "adapter_key": adapter_key, "benchmark_case_id": benchmark_case_id}
            grader_ref = _write_json(row_root / "artifacts" / "grader_output.json", grader_payload)
            artifact_ref = _write_json(
                row_root / "artifacts" / "artifact_bundle.json",
                {
                    "environment_manifest_ref": str(manifest_ref),
                    "verifier_ref": str(verifier_ref),
                    "grader_ref": str(grader_ref),
                    "trace_refs": [str(trace_ref)],
                    "authority_label": authority_label_ctx,
                },
            )
            row = contextbench_adapter.build_result_row_for_grade(
                run_id=f"{row_spec.row_id}__{recipe_id}",
                eval_id="final_harness_eval_suite_baseline_control",
                task_pack_id=row_spec.task_pack_id,
                probe_id=benchmark_case_id,
                control_label="model_attempt",
                environment_ref=str(manifest_ref),
                artifact_refs=[str(artifact_ref)],
                trace_refs=[str(trace_ref)],
                verifier_ref=str(verifier_ref),
                grader_ref=str(grader_ref),
                grade=grade,
                backend_ref=backend_ref,
            )
        elif adapter_key == "letta":
            if benchmark_mode == "native":
                grade = letta_adapter.grade_letta_case_native(spec, assistant_text)
            else:
                grade = letta_adapter.grade_letta_case_equivalent(spec, assistant_text)
            authority_label_letta = letta_adapter.ADAPTER_AUTHORITY_LABEL
            authority_detail_letta = letta_adapter.ADAPTER_AUTHORITY_DETAIL
            grader_payload = {"grade": grade, "adapter_key": adapter_key, "benchmark_case_id": benchmark_case_id}
            grader_ref = _write_json(row_root / "artifacts" / "grader_output.json", grader_payload)
            artifact_ref = _write_json(
                row_root / "artifacts" / "artifact_bundle.json",
                {
                    "environment_manifest_ref": str(manifest_ref),
                    "verifier_ref": str(verifier_ref),
                    "grader_ref": str(grader_ref),
                    "trace_refs": [str(trace_ref)],
                    "authority_label": authority_label_letta,
                },
            )
            row = letta_adapter.build_result_row_for_grade(
                run_id=f"{row_spec.row_id}__{recipe_id}",
                eval_id="final_harness_eval_suite_baseline_control",
                task_pack_id=row_spec.task_pack_id,
                probe_id=benchmark_case_id,
                control_label="model_attempt",
                environment_ref=str(manifest_ref),
                artifact_refs=[str(artifact_ref)],
                trace_refs=[str(trace_ref)],
                verifier_ref=str(verifier_ref),
                grader_ref=str(grader_ref),
                grade=grade,
                backend_ref=backend_ref,
            )
        elif adapter_key == "terminalbench":
            grade = terminalbench_adapter.grade_terminalbench_case_equivalent(
                task_id=benchmark_case_id,
                workspace=workspace_root,
            )
            authority_label_terminalbench = terminalbench_adapter.ADAPTER_AUTHORITY_LABEL
            authority_detail_terminalbench = terminalbench_adapter.ADAPTER_AUTHORITY_DETAIL
            grader_payload = {"grade": grade, "adapter_key": adapter_key, "benchmark_case_id": benchmark_case_id}
            grader_ref = _write_json(row_root / "artifacts" / "grader_output.json", grader_payload)
            artifact_ref = _write_json(
                row_root / "artifacts" / "artifact_bundle.json",
                {
                    "environment_manifest_ref": str(manifest_ref),
                    "verifier_ref": str(verifier_ref),
                    "grader_ref": str(grader_ref),
                    "trace_refs": [str(trace_ref)],
                    "authority_label": authority_label_terminalbench,
                },
            )
            row = terminalbench_adapter.build_result_row_for_grade(
                run_id=f"{row_spec.row_id}__{recipe_id}",
                eval_id="final_harness_eval_suite_baseline_control",
                task_pack_id=row_spec.task_pack_id,
                task_id=benchmark_case_id,
                control_label="model_attempt",
                environment_ref=str(manifest_ref),
                artifact_refs=[str(artifact_ref)],
                trace_refs=[str(trace_ref)],
                verifier_ref=str(verifier_ref),
                grader_ref=str(grader_ref),
                grade=grade,
                backend_ref=backend_ref,
            )
    except Exception as exc:
        return _build_adapter_invalid_row(
            run_root=run_root,
            row_spec=row_spec,
            recipe_id=recipe_id,
            backend_ref=backend_ref,
            reason_code="adapter_execution_exception",
            reason=f"{type(exc).__name__}: {exc}",
        )

    _write_json(
        manifest_path,
        {
            "status": "adapter_model_attempt" if benchmark_mode != "native" else "native_model_attempt",
            "adapter_key": row_spec.benchmark_adapter,
            "benchmark_name": row_spec.benchmark_name,
            "benchmark_case_id": row_spec.benchmark_case_id,
            "authority_label": row["authority_label"],
            "certification_claim": "none",
        },
    )
    row["final_board"] = _final_board_metadata(
        run_root=run_root,
        row_spec=row_spec,
        recipe_id=recipe_id,
        contamination_status=row["contamination_status"],
        verdict=result_row_verdict(row),
    )
    row["model_route_mode"] = model_route_mode
    row["certification_claim"] = "none"
    row["verdict"] = result_row_verdict(row)
    validate_result_row(row)
    _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
    return row


def _run_terminalbench_challenge_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    backend_ref: str,
    recipe_id: str,
    model_route: dict[str, Any],
    model_route_mode: str,
    max_steps: int,
    model_timeout_sec: int,
    variant_id: str = "active_evidence_kernel_v1",
    route_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_id = row_spec.challenge_task_id or row_spec.benchmark_case_id or ""
    tasks_root = _resolve_terminalbench_tasks_root(task_id)
    task_root = tasks_root / task_id
    if not task_root.exists():
        return _build_adapter_invalid_row(
            run_root=run_root,
            row_spec=row_spec,
            recipe_id=recipe_id,
            backend_ref=backend_ref,
            reason_code="terminalbench_task_missing",
            reason=f"missing terminalbench task root: {task_root} (resolved from {tasks_root})",
        )
    try:
        task_meta = tomllib.loads((task_root / "task.toml").read_text(encoding="utf-8"))
        instruction = (task_root / "instruction.md").read_text(encoding="utf-8").strip()
    except Exception as exc:
        return _build_adapter_invalid_row(
            run_root=run_root,
            row_spec=row_spec,
            recipe_id=recipe_id,
            backend_ref=backend_ref,
            reason_code="terminalbench_task_load_failed",
            reason=f"{type(exc).__name__}: {exc}",
        )

    docker_image = str(task_meta.get("environment", {}).get("docker_image", "")).strip()
    if not docker_image:
        return _build_adapter_invalid_row(
            run_root=run_root,
            row_spec=row_spec,
            recipe_id=recipe_id,
            backend_ref=backend_ref,
            reason_code="terminalbench_task_missing_image",
            reason=f"task {task_id} has no docker_image in task.toml",
        )
    verifier_timeout_sec = int(float(task_meta.get("verifier", {}).get("timeout_sec", 1800)))
    agent_timeout_sec = int(float(task_meta.get("agent", {}).get("timeout_sec", row_spec.max_solver_seconds)))

    row_root = run_root / "rows" / row_spec.row_id
    workspace = row_root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "instruction.md").write_text(instruction + "\n", encoding="utf-8")
    logs_dir = row_root / "artifacts" / "terminalbench_verifier_logs"
    tests_root = task_root / "tests"

    RootMappedDockerSandbox.container_workspace_root = "/app"
    RootMappedDockerSandbox.network_enabled = _row_network_enabled(row_spec)
    RootMappedDockerSandbox.preserve_container_until_external_cleanup = True
    try:
        try:
            route_result = run_reference_baseline(
                run_id=row_spec.row_id,
                run_dir=row_root / "route_trace",
                task_id=task_id,
                task_prompt=instruction,
                benchmark_family="terminalbench_challenge",
                case_id=task_id,
                seed_id=variant_id,
                model_route=model_route,
                model_client_kwargs=_model_client_kwargs(model_timeout_sec),
                max_steps=max_steps,
                timeout_sec=max(agent_timeout_sec, row_spec.max_solver_seconds),
                sandbox_type="docker",
                sandbox_image=docker_image,
                cwd=workspace,
                orientation_env_overrides={"cwd": "/workspace", "task_id": task_id},
                route_manifest=route_manifest,
                enforce_packet04_route_contract=False,
            )
            model_client_error = _extract_model_client_error(route_result)
            if model_client_error is not None:
                return _build_model_client_invalid_row(
                    run_root=run_root,
                    row_spec=row_spec,
                    backend_ref=backend_ref,
                    recipe_id=recipe_id,
                    model_route_mode=model_route_mode,
                    route_result=route_result,
                    model_client_error=model_client_error,
                )
        except Exception as exc:  # noqa: BLE001
            return _build_adapter_invalid_row(
                run_root=run_root,
                row_spec=row_spec,
                recipe_id=recipe_id,
                backend_ref=backend_ref,
                reason_code="terminalbench_execution_exception",
                reason=f"{type(exc).__name__}: {exc}",
            )

        logs_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(tests_root, workspace / "tests", dirs_exist_ok=True)
        except Exception:
            pass

        try:
            if RootMappedDockerSandbox.last_container_active and RootMappedDockerSandbox.last_container_id:
                subprocess.run(
                    ["docker", "exec", RootMappedDockerSandbox.last_container_id, "mkdir", "-p", "/logs"],
                    capture_output=True,
                    check=False,
                )
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        RootMappedDockerSandbox.last_container_id,
                        "bash",
                        "-lc",
                        _terminalbench_exec_tests_mount_command(),
                    ],
                    capture_output=True,
                    check=False,
                )
                verifier_cp = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-w",
                        "/app",
                        RootMappedDockerSandbox.last_container_id,
                        "bash",
                        "/app/tests/test.sh",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=verifier_timeout_sec + 120,
                    check=False,
                )
                subprocess.run(
                    ["docker", "cp", f"{RootMappedDockerSandbox.last_container_id}:/logs/.", str(logs_dir)],
                    capture_output=True,
                    check=False,
                )
            else:
                verifier_cp = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        f"{workspace}:/workspace",
                        "-v",
                        f"{tests_root}:/tests:ro",
                        "-v",
                        f"{logs_dir}:/logs",
                        "-w",
                        "/workspace",
                        docker_image,
                        "bash",
                        "-lc",
                        "cp -a /workspace/. /app/ && cp -a /tests/. /app/tests/ && bash /app/tests/test.sh",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=verifier_timeout_sec + 120,
                    check=False,
                )
        except Exception as exc:  # noqa: BLE001
            return _build_adapter_invalid_row(
                run_root=run_root,
                row_spec=row_spec,
                recipe_id=recipe_id,
                backend_ref=backend_ref,
                reason_code="terminalbench_verifier_execution_exception",
                reason=f"{type(exc).__name__}: {exc}",
            )
    finally:
        RootMappedDockerSandbox.preserve_container_until_external_cleanup = False
        if RootMappedDockerSandbox.last_container_id:
            logs_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["docker", "cp", f"{RootMappedDockerSandbox.last_container_id}:/tmp", str(logs_dir / "tmp")],
                capture_output=True,
                check=False,
            )
            subprocess.run(["docker", "rm", "-f", RootMappedDockerSandbox.last_container_id], capture_output=True, check=False)
            RootMappedDockerSandbox.last_container_id = None
            RootMappedDockerSandbox.last_container_active = False
    reward_path = logs_dir / "verifier" / "reward.txt"
    reward = reward_path.read_text(encoding="utf-8").strip() if reward_path.exists() else ""
    verifier_passed = verifier_cp.returncode == 0 and reward == "1"
    task_truth_status = "pass" if verifier_passed else "fail"
    reason_codes = ["row_passed"] if verifier_passed else ["terminalbench_verifier_failed"]
    if reward == "":
        reason_codes.append("terminalbench_reward_missing")

    manifest_ref = _write_json(
        row_root / "artifacts" / "environment_manifest.json",
        {
            "status": "executed",
            "execution_source": "terminalbench_challenge_native_verifier",
            "benchmark_case_id": task_id,
            "docker_image": docker_image,
            "authority_label": "native",
            "certification_claim": "none",
        },
    )
    verifier_ref = _write_json(
        row_root / "artifacts" / "verifier_output.json",
        {
            "benchmark_case_id": task_id,
            "returncode": verifier_cp.returncode,
            "reward": reward,
            "reward_path": str(reward_path),
            "stdout_tail": verifier_cp.stdout[-4000:],
            "stderr_tail": verifier_cp.stderr[-4000:],
            "status": "pass" if verifier_passed else "fail",
        },
    )
    grader_ref = _write_json(
        row_root / "artifacts" / "grader_output.json",
        {
            "benchmark_case_id": task_id,
            "verdict": "pass" if verifier_passed else "fail",
            "score": 1.0 if verifier_passed else 0.0,
            "reason_codes": reason_codes,
            "failure_class": "none" if verifier_passed else "verification_grading",
        },
    )
    trace_ref = _write_json(
        row_root / "traces" / "trace.json",
        _build_trace_payload(row_root, row_spec, route_result, {"exit_code": 0, "command": "bash /tests/test.sh"}, {}, {}),
    )
    artifact_ref = _write_json(
        row_root / "artifacts" / "artifact_bundle.json",
        {
            "environment_manifest_ref": str(manifest_ref),
            "verifier_ref": str(verifier_ref),
            "grader_ref": str(grader_ref),
            "trace_refs": [str(trace_ref)],
            "route_trace_ref": str(row_root / "route_trace" / "run_events.jsonl"),
            "authority_label": "native",
        },
    )
    row = {
        "run_id": f"{row_spec.row_id}__{recipe_id}",
        "eval_id": "final_harness_eval_suite_baseline_control",
        "task_pack_id": row_spec.task_pack_id,
        "family": _row_family(row_spec),
        "surface_type": row_spec.surface_type,
        "admission_level": "diagnostic",
        "backend_ref": backend_ref,
        "environment_ref": str(manifest_ref),
        "artifact_refs": [str(artifact_ref)],
        "trace_refs": [str(trace_ref), str(row_root / "route_trace" / "run_events.jsonl")],
        "closure_status": "closed",
        "task_truth_status": task_truth_status,
            "contamination_status": "clean",
            "failure_class": "none" if verifier_passed else "verification_grading",
            "reason_codes": reason_codes,
            "verifier_ref": str(verifier_ref),
            "grader_ref": str(grader_ref),
            "score": 1.0 if verifier_passed else 0.0,
            "token_and_cost_summary": _row_token_and_cost_summary(route_result),
            "model_route_mode": model_route_mode,
            "certification_claim": "none",
            "authority_label": "native",
            "authority_detail": "terminalbench_official_task_native_verifier",
        }
    row["final_board"] = _final_board_metadata(
        run_root=run_root,
        row_spec=row_spec,
        recipe_id=recipe_id,
        contamination_status="clean",
        verdict="pass" if verifier_passed else "fail",
    )
    row["verdict"] = result_row_verdict(row)
    validate_result_row(row)
    _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
    return row


def _terminalbench_exec_tests_mount_command() -> str:
    return "mkdir -p /tests && cp -a /app/tests/. /tests/"


def _build_adapter_invalid_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    recipe_id: str,
    backend_ref: str,
    reason_code: str,
    reason: str,
) -> dict[str, Any]:
    row_root = run_root / "rows" / row_spec.row_id
    manifest_ref = _write_json(
        row_root / "artifacts" / "environment_manifest.json",
        {"status": "invalid", "reason": reason, "reason_code": reason_code},
    )
    verifier_ref = _write_json(
        row_root / "artifacts" / "verifier_output.json",
        {"status": "not_executed", "reason": reason, "reason_code": reason_code},
    )
    grader_ref = _write_json(
        row_root / "artifacts" / "grader_output.json",
        {"status": "not_executed", "reason": reason, "reason_code": reason_code},
    )
    trace_ref = _write_json(
        row_root / "traces" / "trace.json",
        {"meta": {"adapter_invalid": True, "reason": reason}, "events": []},
    )
    execution_truth_ref = _write_json(
        row_root / "artifacts" / "execution_truth.json",
        _build_invalid_execution_truth_payload(
            row_spec=row_spec,
            reason_code=reason_code,
            reason=reason,
            verifier_ref=verifier_ref,
            grader_ref=grader_ref,
            trace_ref=trace_ref,
            runtime_details={"adapter_invalid": True},
        ),
    )
    artifact_ref = _write_json(
        row_root / "artifacts" / "artifact_bundle.json",
        {
            "environment_manifest_ref": str(manifest_ref),
            "verifier_ref": str(verifier_ref),
            "grader_ref": str(grader_ref),
            "trace_ref": str(trace_ref),
            "execution_truth_ref": str(execution_truth_ref),
        },
    )
    row = {
        "run_id": f"{row_spec.row_id}__{recipe_id}",
        "eval_id": "final_harness_eval_suite_baseline_control",
        "task_pack_id": row_spec.task_pack_id,
        "family": _row_family(row_spec),
        "surface_type": row_spec.surface_type,
        "admission_level": "diagnostic",
        "backend_ref": backend_ref,
        "environment_ref": str(manifest_ref),
        "artifact_refs": [str(artifact_ref)],
        "trace_refs": [str(trace_ref)],
        "closure_status": "invalid",
        "task_truth_status": "invalid",
        "contamination_status": "unknown",
        "failure_class": "unclear",
        "reason_codes": [reason_code],
        "verifier_ref": str(verifier_ref),
        "grader_ref": str(grader_ref),
        "score": 0.0,
        "token_and_cost_summary": _row_token_and_cost_summary(None),
        "model_route_mode": "adapter_not_executed",
        "certification_claim": "none",
    }
    row["final_board"] = _final_board_metadata(
        run_root=run_root,
        row_spec=row_spec,
        recipe_id=recipe_id,
        contamination_status=row["contamination_status"],
        verdict="invalid",
    )
    row["verdict"] = result_row_verdict(row)
    validate_result_row(row)
    _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
    return row


def _build_invalid_execution_truth_payload(
    *,
    row_spec: FinalSuiteRowSpec,
    reason_code: str,
    reason: str,
    verifier_ref: Path,
    grader_ref: Path,
    trace_ref: Path,
    runtime_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details = runtime_details if isinstance(runtime_details, dict) else {}
    return {
        "execution_truth_version": "evidence_kernel_action_bus.v1",
        "route_status": "not_executed",
        "action_bus_summary": {"action_count": 0, "records": []},
        "kernel_summary": {
            "receipt_count": 0,
            "native_tool_mode_active": False,
            "verifier_gate": {"status": "not_run", "reason_codes": [reason_code]},
            "artifact_gate": {"status": "not_run", "required_paths": [], "missing_paths": []},
            "service_registry": {},
        },
        "working_context_pack": {
            "task_contract": {
                "task_id": row_spec.task_pack_id,
                "run_id": row_spec.row_id,
            },
            "open_obligations": {
                "invalid_execution_reason_code": reason_code,
            },
        },
        "verification_summary": {
            "verified": False,
            "reason_codes": [reason_code],
        },
        "visible_verifier": {
            "exit_code": None,
            "command": None,
        },
        "hidden_grader": {
            "passed": False,
            "score": 0.0,
            "reason_codes": [reason_code],
        },
        "truth_alignment": {
            "aligned": False,
            "route_verified": None,
            "visible_verifier_passed": None,
            "grader_passed": False,
            "reason_codes": ["invalid_execution_not_run"],
        },
        "invalid_execution": {
            "reason_code": reason_code,
            "reason": reason,
            "verifier_ref": str(verifier_ref),
            "grader_ref": str(grader_ref),
            "trace_ref": str(trace_ref),
            "runtime_details": details,
        },
    }


def _row_admission_level(row_spec: FinalSuiteRowSpec) -> str:
    return "certified" if row_spec.execution_source == "task_pack" else "diagnostic"


def _extract_model_client_error(route_result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(route_result, dict):
        return None
    run_events = route_result.get("run_events")
    if isinstance(run_events, list):
        for event in run_events:
            if not isinstance(event, dict) or event.get("event_type") != "model_client_error":
                continue
            details = event.get("payload", {}).get("details")
            sanitized = _sanitize_model_client_error(details)
            if sanitized:
                return sanitized
    execution = route_result.get("execution")
    if isinstance(execution, dict):
        sanitized = _sanitize_model_client_error(execution.get("last_model_client_error"))
        if sanitized:
            return sanitized
    return None


def _sanitize_model_client_error(details: Any) -> dict[str, Any] | None:
    if not isinstance(details, dict):
        return None
    payload: dict[str, Any] = {}
    for key in ("message", "error_kind", "status_code"):
        value = details.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            payload[key] = value
    response_body = details.get("response_body")
    if isinstance(response_body, str) and response_body.strip():
        payload["response_body_preview"] = response_body.strip()[:400]
    metadata = details.get("metadata")
    if isinstance(metadata, dict):
        sanitized_metadata = {
            str(key): value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float)) and not isinstance(value, bool)
        }
        if sanitized_metadata:
            payload["metadata"] = sanitized_metadata
    return payload or None


def _model_client_reason_codes(model_client_error: dict[str, Any]) -> list[str]:
    codes = ["invalid_due_to_environment_model_client_failure"]
    status_code = model_client_error.get("status_code")
    if isinstance(status_code, int):
        codes.append(f"model_client_http_{status_code}")
    error_kind = model_client_error.get("error_kind")
    if isinstance(error_kind, str) and error_kind.strip():
        normalized = "".join(ch if ch.isalnum() else "_" for ch in error_kind.strip().lower()).strip("_")
        if normalized:
            codes.append(f"model_client_{normalized}")
    return _dedupe(codes)


def _build_route_resolution_invalid_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    backend_ref: str,
    recipe_id: str,
    model_route_mode: str,
    route_error: CertifiedRouteResolutionError,
) -> dict[str, Any]:
    return _build_model_provider_invalid_row(
        run_root=run_root,
        row_spec=row_spec,
        backend_ref=backend_ref,
        recipe_id=recipe_id,
        model_route_mode=model_route_mode,
        reason_code=route_error.reason_code,
        reason=str(route_error),
        failure_class="provider",
        runtime_details={"route_resolution_error": dict(route_error.details)},
        trace_events=[
            {
                "event_type": "route_resolution_error",
                "reason_code": route_error.reason_code,
                "message": str(route_error),
                "details": dict(route_error.details),
            }
        ],
    )


def _build_model_client_invalid_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    backend_ref: str,
    recipe_id: str,
    model_route_mode: str,
    route_result: dict[str, Any],
    model_client_error: dict[str, Any],
) -> dict[str, Any]:
    row_root = run_root / "rows" / row_spec.row_id
    route_trace_path = row_root / "route_trace" / "run_events.jsonl"
    runtime_details = {
        "route_trace_ref": str(route_trace_path),
        "model_client_error": dict(model_client_error),
    }
    return _build_model_provider_invalid_row(
        run_root=run_root,
        row_spec=row_spec,
        backend_ref=backend_ref,
        recipe_id=recipe_id,
        model_route_mode=model_route_mode,
        route_result=route_result,
        reason_code="invalid_due_to_environment_model_client_failure",
        reason=str(model_client_error.get("message") or "model client failure"),
        failure_class="provider",
        runtime_details=runtime_details,
        trace_events=[
            {
                "event_type": "model_client_error",
                **dict(model_client_error),
                "causal_trace_ref": str(route_trace_path),
            }
        ],
        trace_refs=[str(route_trace_path)],
        extra_reason_codes=_model_client_reason_codes(model_client_error),
    )


def _build_model_provider_invalid_row(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    backend_ref: str,
    recipe_id: str,
    model_route_mode: str,
    reason_code: str,
    reason: str,
    failure_class: str,
    runtime_details: dict[str, Any],
    trace_events: list[dict[str, Any]],
    route_result: dict[str, Any] | None = None,
    trace_refs: list[str] | None = None,
    extra_reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    row_root = run_root / "rows" / row_spec.row_id
    manifest_ref = _write_json(
        row_root / "artifacts" / "environment_manifest.json",
        {
            "status": "invalid_due_to_environment",
            "reason_code": reason_code,
            "reason": reason,
            "runtime_details": runtime_details,
        },
    )
    verifier_ref = _write_json(
        row_root / "artifacts" / "verifier_output.json",
        {"status": "not_executed", "reason_code": reason_code, "reason": reason},
    )
    grader_ref = _write_json(
        row_root / "artifacts" / "grader_output.json",
        {"status": "not_executed", "reason_codes": _dedupe([reason_code, *(extra_reason_codes or [])]), "reason": reason},
    )
    trace_ref = _write_json(
        row_root / "traces" / "trace.json",
        {
            "meta": {
                "workspace_root": row_spec.canonical_workspace_root,
                "timed_out": False,
                "infrastructure_timeout": False,
                "status": "invalid_due_to_environment",
            },
            "events": trace_events,
        },
    )
    execution_truth_ref = _write_json(
        row_root / "artifacts" / "execution_truth.json",
        _build_invalid_execution_truth_payload(
            row_spec=row_spec,
            reason_code=reason_code,
            reason=reason,
            verifier_ref=verifier_ref,
            grader_ref=grader_ref,
            trace_ref=trace_ref,
            runtime_details=runtime_details,
        ),
    )
    artifact_payload = {
        "environment_manifest_ref": str(manifest_ref),
        "verifier_ref": str(verifier_ref),
        "grader_ref": str(grader_ref),
        "trace_ref": str(trace_ref),
        "execution_truth_ref": str(execution_truth_ref),
        "status": "invalid_due_to_environment",
    }
    if trace_refs:
        artifact_payload["causal_trace_refs"] = list(trace_refs)
    artifact_ref = _write_json(row_root / "artifacts" / "artifact_bundle.json", artifact_payload)
    row_trace_refs = [str(trace_ref)]
    if trace_refs:
        row_trace_refs.extend(str(ref) for ref in trace_refs)
    row = {
        "run_id": f"{row_spec.row_id}__{recipe_id}",
        "eval_id": "final_harness_eval_suite_baseline_control",
        "task_pack_id": row_spec.task_pack_id,
        "family": _row_family(row_spec),
        "surface_type": row_spec.surface_type,
        "admission_level": _row_admission_level(row_spec),
        "backend_ref": backend_ref,
        "environment_ref": str(manifest_ref),
        "artifact_refs": [str(artifact_ref)],
        "trace_refs": row_trace_refs,
        "closure_status": "invalid",
        "task_truth_status": "invalid",
        "contamination_status": "unknown",
        "failure_class": failure_class,
        "reason_codes": _dedupe([reason_code, *(extra_reason_codes or [])]),
        "verifier_ref": str(verifier_ref),
        "grader_ref": str(grader_ref),
        "score": 0.0,
        "token_and_cost_summary": _row_token_and_cost_summary(route_result),
        "model_route_mode": model_route_mode,
    }
    row["final_board"] = _final_board_metadata(
        run_root=run_root,
        row_spec=row_spec,
        recipe_id=recipe_id,
        contamination_status="clean",
        verdict="invalid",
    )
    row["verdict"] = result_row_verdict(row)
    validate_result_row(row)
    _write_json(run_root / "result_rows" / f"{row_spec.row_id}.json", row)
    return row


def _final_board_metadata(
    *,
    run_root: Path,
    row_spec: FinalSuiteRowSpec,
    recipe_id: str,
    contamination_status: str,
    verdict: str,
) -> dict[str, Any]:
    return {
        "board_id": "final_harness_eval_suite_v1",
        "board_version": 1,
        "recipe_id": recipe_id,
        "recipe_snapshot_ref": str(run_root / "recipe_manifest_snapshot.yaml"),
        "row_id": row_spec.row_id,
        "row_type": row_spec.row_type,
        "is_flagship": row_spec.is_flagship,
        "critical_clusters": list(row_spec.critical_clusters),
        "provenance_type": row_spec.provenance_type,
        "contamination_gate": "clean" if contamination_status == "clean" else "contaminated_blocked",
        "invalidity_gate": "valid" if verdict != "invalid" else "invalid_blocked",
        "current_stack_ref": "tracking/collab/final_harness_eval_suite/current_stack_manifest.yaml",
        "lane_id": row_spec.lane_id,
        "execution_source": row_spec.execution_source,
        "benchmark_name": row_spec.benchmark_name,
        "benchmark_case_id": row_spec.benchmark_case_id,
        "challenge_task_id": row_spec.challenge_task_id,
        "difficulty_tier": row_spec.difficulty_tier,
    }


def _row_family(row_spec: FinalSuiteRowSpec) -> str:
    if row_spec.execution_source == "task_pack":
        return "final_harness_eval_suite"
    return (row_spec.benchmark_name or row_spec.lane_id or "final_harness_eval_suite").lower().replace(" ", "_")


def _known_bad_letta_answer(truth: str) -> str:
    if truth.startswith("$"):
        stripped = truth.replace("$", "").replace(",", "")
        try:
            return f"{float(stripped) + 1.0:.2f}"
        except ValueError:
            return "0"
    if truth.isdigit():
        return str(int(truth) + 1)
    return "wrong_answer"


def _extract_final_assistant_text(row_root: Path) -> str:
    events = _read_events(row_root / "route_trace" / "run_events.jsonl")
    for event in reversed(events):
        if event.get("event_type") != "model_completion":
            continue
        details = event.get("payload", {}).get("details", {})
        text = details.get("assistant_text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _extract_bfcl_calls_from_text(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    if "```" in stripped:
        for chunk in stripped.split("```"):
            candidate = chunk.strip()
            if candidate.startswith("python"):
                candidate = candidate[len("python") :].strip()
            calls = _parse_call_list_literal(candidate)
            if calls:
                return calls
    return _parse_call_list_literal(stripped)


def _parse_call_list_literal(payload: str) -> list[str]:
    import ast

    try:
        parsed = ast.parse(payload, mode="eval")
    except SyntaxError:
        return []
    if not isinstance(parsed.body, ast.List):
        return []
    calls: list[str] = []
    for element in parsed.body.elts:
        if not isinstance(element, ast.Call):
            return []
        raw = ast.unparse(element).strip()
        if raw:
            calls.append(raw)
    return calls


def _build_row_prompt(task_pack_root: Path, row_spec: FinalSuiteRowSpec) -> str:
    prompt_path = task_pack_root / "solver_pack" / "visible_prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else f"Complete row {row_spec.row_id}."
    return (
        f"{prompt}\n\n"
        f"Runtime contract: operate only inside {row_spec.canonical_workspace_root}; use {row_spec.runtime_python_command} for python commands.\n"
        "Do not access reviewer_pack or grader files. Run the visible verifier as a diagnostic, but treat it as necessary and not sufficient; final completion must still be grounded in solver-visible evidence and provenance."
    )


def _stage_workspace(task_pack_root: Path, workspace_root: Path, row_spec: FinalSuiteRowSpec) -> None:
    workspace_root.mkdir(parents=True, exist_ok=True)
    if row_spec.legacy_layout:
        _copy_tree(task_pack_root / "solver_pack", workspace_root)
        (workspace_root / "candidate").mkdir(parents=True, exist_ok=True)
        return
    source_workspace = task_pack_root / "solver_pack" / "workspace"
    canonical_leaf = row_spec.canonical_workspace_root.strip("/").split("/")[-1]
    source_leaf = source_workspace / canonical_leaf
    if source_leaf.exists():
        _copy_tree(source_leaf, workspace_root)
    else:
        _copy_tree(source_workspace, workspace_root)


def _stage_grading_pack(task_pack_root: Path, grading_root: Path) -> None:
    grading_root.mkdir(parents=True, exist_ok=True)
    if (task_pack_root / "reviewer_pack").exists():
        _copy_tree(task_pack_root / "reviewer_pack", grading_root / "reviewer_pack")
    if (task_pack_root / "grader").exists():
        _copy_tree(task_pack_root / "grader", grading_root / "grader")


def _run_visible_verifier(task_pack_root: Path, workspace_root: Path, container_root: str, image: str, row_spec: FinalSuiteRowSpec) -> dict[str, Any]:
    if row_spec.legacy_layout:
        command = "python3 visible_verifier.py --candidate-dir candidate" if (workspace_root / "visible_verifier.py").exists() else "true"
    else:
        command = _select_visible_verifier_command(workspace_root, row_spec.expected_candidate_output)
    return _docker_exec(workspace_root, image, command, cwd=container_root, network_enabled=_row_network_enabled(row_spec))


def _select_visible_verifier_command(workspace_root: Path, expected_candidate_output: str) -> str:
    candidate_rel = _container_path_to_rel(expected_candidate_output)
    if (workspace_root / "checks" / "visible_check.py").exists():
        script = (workspace_root / "checks" / "visible_check.py").read_text(encoding="utf-8")
        if "--candidate" in script:
            return f"python3 checks/visible_check.py --candidate {candidate_rel}"
        if "--report" in script:
            return f"python3 checks/visible_check.py --report {candidate_rel}"
        return "python3 checks/visible_check.py"
    if (workspace_root / "scripts" / "verify_recovery.py").exists():
        return (
            "python3 scripts/verify_recovery.py "
            "--bundle artifacts/recovery/final/recovery_bundle.json "
            "--config services/catalog/config/runtime.env"
        )
    if (workspace_root / "scripts" / "visible_verify.py").exists():
        return "python3 scripts/visible_verify.py --dispatch out/dispatch_plan.json --workspace config/active_workspace.txt"
    return "true"


def _run_grader(
    task_pack_root: Path,
    grading_root: Path,
    workspace_root: Path,
    trace_path: Path,
    row_spec: FinalSuiteRowSpec,
) -> dict[str, Any]:
    grader_path = grading_root / "grader" / "grade.py"
    grader_src_text = grader_path.read_text(encoding="utf-8") if grader_path.exists() else ""
    if "--candidate" in grader_src_text and "--trace" in grader_src_text and "--output" in grader_src_text:
        candidate_abs = _resolve_candidate_path(workspace_root, row_spec.expected_candidate_output, row_spec)
        output_path = grading_root / "grader_result.json"
        cp = subprocess.run(
            [
                "python3",
                str(grader_path),
                "--candidate",
                str(candidate_abs),
                "--trace",
                str(trace_path),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            cwd=grading_root,
            check=False,
        )
        if output_path.exists():
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        else:
            payload = {"verdict": "fail", "score": 0.0, "reason_codes": ["grader_output_missing"]}
        payload["grader_returncode"] = cp.returncode
        payload["grader_stdout"] = cp.stdout
        payload["grader_stderr"] = cp.stderr
        return payload

    candidate_dir = workspace_root / "candidate"
    if candidate_dir.exists():
        _copy_tree(candidate_dir, grading_root / "candidate")
    cp = subprocess.run(
        ["python3", str(grader_path)],
        capture_output=True,
        text=True,
        cwd=grading_root,
        check=False,
    )
    payload = _parse_json_from_text(cp.stdout)
    if not isinstance(payload, dict):
        payload = {"passed": False, "score": 0.0, "reason_codes": ["grader_stdout_not_json"]}
    payload["grader_returncode"] = cp.returncode
    payload["grader_stdout"] = cp.stdout
    payload["grader_stderr"] = cp.stderr
    return payload


def _build_trace_payload(
    row_root: Path,
    row_spec: FinalSuiteRowSpec,
    route_result: dict[str, Any],
    visible_result: dict[str, Any],
    before_hashes: dict[str, str],
    after_hashes: dict[str, str],
) -> dict[str, Any]:
    events = []
    for event in _read_events(row_root / "route_trace" / "run_events.jsonl"):
        event_type = event.get("event_type")
        details = event.get("payload", {}).get("details", {})
        if event_type == "model_client_error":
            model_client_error = _sanitize_model_client_error(details)
            if model_client_error:
                events.append({"event_type": "model_client_error", **model_client_error})
            continue
        if event_type == "raw_bash_result":
            events.append(
                {
                    "event_type": "tool_call",
                    "tool_name": str(details.get("tool_name", "raw_bash")),
                    "command": str(details.get("command", "")),
                    "exit_code": int(details.get("exit_code", 0)),
                }
            )
            continue
        if event_type == "action_bus_recorded":
            events.append(
                {
                    "event_type": "action_record",
                    "action_id": str(details.get("action_id", "")),
                    "action_type": str(details.get("action_type", "")),
                    "tool_name": str(details.get("tool_name", "raw_bash")),
                    "phase": str(details.get("phase", "execute")),
                    "command": str(details.get("command", "")),
                }
            )
            continue
        if event_type == "evidence_kernel_receipt":
            events.append(
                {
                    "event_type": "kernel_receipt",
                    "receipt_id": str(details.get("receipt_id", "")),
                    "action_id": str(details.get("action_id", "")),
                    "action_type": str(details.get("action_type", "")),
                    "tool_name": str(details.get("tool_name", "")),
                    "command": str(details.get("command", "")),
                    "exit_code": int(details.get("exit_code", 0)),
                }
            )
            continue
    changed = _diff_hashes(before_hashes, after_hashes)
    for rel in changed:
        events.append({"event_type": "file_write", "path": rel})
    events.append(
        {
            "event_type": "verifier_run",
            "status": "pass" if int(visible_result.get("exit_code", 1)) == 0 else "fail",
            "command": str(visible_result.get("command", "")),
        }
    )
    runtime = route_result.get("runtime_timing", {})
    timed_out = bool(runtime.get("execution_sec", 0) > row_spec.max_solver_seconds)
    return {
        "meta": {
            "workspace_root": row_spec.canonical_workspace_root,
            "timed_out": timed_out,
            "infrastructure_timeout": False,
        },
        "events": events,
        **(
            {"control_plane_artifact_refs": dict(route_result.get("control_plane_artifacts", {}))}
            if isinstance(route_result.get("control_plane_artifacts"), dict) and route_result.get("control_plane_artifacts")
            else {}
        ),
    }


def _build_execution_truth_payload(
    *,
    route_result: dict[str, Any],
    visible_result: dict[str, Any],
    grader_result: dict[str, Any],
    truth_alignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action_bus = route_result.get("action_bus", {})
    kernel = route_result.get("evidence_kernel", {})
    working_pack = route_result.get("evidence_kernel_working_context_pack", {})
    verification = route_result.get("verification", {})
    return {
        "execution_truth_version": "evidence_kernel_action_bus.v1",
        "route_status": route_result.get("execution", {}).get("status"),
        "action_bus_summary": action_bus if isinstance(action_bus, dict) else {},
        "kernel_summary": {
            "receipt_count": kernel.get("receipt_count"),
            "native_tool_mode_active": kernel.get("native_tool_mode_active"),
            "verifier_gate": kernel.get("verifier_gate"),
            "artifact_gate": kernel.get("artifact_gate"),
            "service_registry": kernel.get("service_registry", {}),
        },
        "working_context_pack": working_pack if isinstance(working_pack, dict) else {},
        "verification_summary": verification if isinstance(verification, dict) else {},
        "visible_verifier": {
            "exit_code": visible_result.get("exit_code"),
            "command": visible_result.get("command"),
        },
        "hidden_grader": {
            "passed": grader_result.get("passed"),
            "score": grader_result.get("score"),
            "reason_codes": grader_result.get("reason_codes"),
        },
        "truth_alignment": truth_alignment if isinstance(truth_alignment, dict) else {},
    }


def _route_grader_truth_alignment(
    *,
    route_result: dict[str, Any],
    visible_result: dict[str, Any],
    grader_result: dict[str, Any],
) -> dict[str, Any]:
    verification = route_result.get("verification", {}) if isinstance(route_result, dict) else {}
    route_verified_raw = verification.get("verified") if isinstance(verification, dict) else None
    route_verified = bool(route_verified_raw) if isinstance(route_verified_raw, bool) else None
    visible_passed = _normalize_exit_code(visible_result.get("exit_code", 1), default=1) == 0
    grader_passed = _grader_passed(grader_result)
    reason_codes: list[str] = []
    if isinstance(route_verified, bool) and route_verified != grader_passed:
        reason_codes.append("route_verification_vs_grader_mismatch")
    if visible_passed != grader_passed:
        reason_codes.append("visible_verifier_vs_grader_mismatch")
    if isinstance(route_verified, bool) and route_verified != visible_passed:
        reason_codes.append("route_verification_vs_visible_verifier_mismatch")
    return {
        "aligned": not reason_codes,
        "route_verified": route_verified,
        "visible_verifier_passed": visible_passed,
        "grader_passed": grader_passed,
        "reason_codes": reason_codes,
    }


def _native_runtime_issue(route_result: dict[str, Any]) -> str | None:
    execution = route_result.get("execution", {}) if isinstance(route_result, dict) else {}
    if isinstance(execution, dict):
        governed_status = execution.get("governed_status")
        reason_codes = _as_string_list(
            execution.get("reason_codes"),
            execution.get("finalization_reason_codes"),
        )
        finalization_bundle = execution.get("finalization_bundle")
        if governed_status == "invalid_environment" and "native_tool_runtime_unavailable" in reason_codes:
            return "native_tool_runtime_unavailable"
        if isinstance(finalization_bundle, dict):
            native_tool_status = finalization_bundle.get("native_tool_status")
            if _native_tool_status_is_runtime_unavailable(native_tool_status):
                return "native_tool_runtime_unavailable"

    kernel = route_result.get("evidence_kernel", {}) if isinstance(route_result, dict) else {}
    if isinstance(kernel, dict):
        native_tool_state = kernel.get("native_tool_state", {})
        if isinstance(native_tool_state, dict):
            runtime_status = native_tool_state.get("runtime_status")
            attempted = native_tool_state.get("attempted_native_tool_call")
            if runtime_status == "native_tool_runtime_unavailable" and attempted is True:
                return "native_tool_runtime_unavailable"

    score_envelope = route_result.get("score_envelope", {}) if isinstance(route_result, dict) else {}
    if isinstance(score_envelope, dict):
        l4 = score_envelope.get("layers", {}).get("L4_final_acceptance", {})
        if isinstance(l4, dict):
            if "native_tool_runtime_unavailable" in _as_string_list(l4.get("reason_codes")):
                return "native_tool_runtime_unavailable"
    return None


def _apply_native_runtime_invalid_override(
    *,
    row: dict[str, Any],
    route_result: dict[str, Any],
    benchmark_mode: str,
) -> dict[str, Any]:
    if benchmark_mode != "native":
        return row
    reason_code = _native_runtime_issue(route_result)
    if reason_code is None:
        return row
    overridden = dict(row)
    overridden["closure_status"] = "invalid"
    overridden["task_truth_status"] = "invalid"
    overridden["failure_class"] = "runtime"
    overridden["reason_codes"] = [reason_code]
    overridden["score"] = 0.0
    return overridden


def _native_tool_status_is_runtime_unavailable(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("status") == "unavailable":
        return True
    return "native_tool_runtime_unavailable" in _as_string_list(value.get("reason_codes"))


def _as_string_list(*values: Any) -> list[str]:
    out: list[str] = []
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, str) or not item:
                continue
            out.append(item)
    return out


def _merged_reason_codes(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    for value in [*primary, *secondary]:
        if not isinstance(value, str) or not value:
            continue
        if value in merged:
            continue
        merged.append(value)
    return merged


def _dedupe(values: list[str]) -> list[str]:
    return _merged_reason_codes(values, [])


def _normalize_exit_code(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return default
    return default


def _render_final_board_scoreboard(
    *,
    run_id: str,
    rows: list[dict[str, Any]],
    recipe_id: str,
    run_root: Path,
    cost_summary: dict[str, Any] | None = None,
) -> dict[str, Path]:
    registry = _registry_view(_load_yaml(REPO_ROOT / "tracking/collab/final_harness_eval_suite/final_suite_registry.yaml"))
    row_statuses = {
        row["final_board"]["row_id"]: _corroborated_row_status(row)
        for row in rows
    }
    payload: dict[str, Any] = {
        "run_id": run_id,
        "recipes": [
            {
                "recipe_id": recipe_id,
                "row_statuses": row_statuses,
                "contamination": {
                    "contaminated_row_ids": [row["final_board"]["row_id"] for row in rows if row["contamination_status"] == "contaminated"],
                    "unresolved_suspect_excluded_row_ids": [],
                },
                "invalidity": {
                    "unresolved_invalid_row_ids": [row["final_board"]["row_id"] for row in rows if row["verdict"] == "invalid"],
                },
                "stability": {"status": "not_run"},
                "cost_step_gate": "pass",
                "composition_risk_complexity": 0,
                "known_weaknesses": [],
                "evidence_refs": [str(run_root / "result_rows.jsonl")],
            }
        ],
    }
    if isinstance(cost_summary, dict):
        payload["cost_summary"] = cost_summary
    scoreboard = render_scoreboard(payload, registry, allow_pre_stability=False)
    scoreboard_json, scoreboard_md = write_scoreboard_outputs(scoreboard, run_root)
    return {"scoreboard_json": scoreboard_json, "scoreboard_md": scoreboard_md}


def _corroborated_row_status(row: dict[str, Any]) -> str:
    verdict = str(row.get("verdict", "fail"))
    if verdict not in {"pass", "fail", "invalid"}:
        verdict = "fail"
    truth_alignment = row.get("truth_alignment", {})
    aligned = truth_alignment.get("aligned") if isinstance(truth_alignment, dict) else None
    if verdict == "pass" and aligned is False:
        return "fail"
    return verdict


def _write_non_claiming_finalist_selection(path: Path, run_id: str, recipe_id: str) -> Path:
    lines = [
        "# Finalist Selection",
        "",
        "Single-recipe board output (non-comparative).",
        "",
        f"- run_id: `{run_id}`",
        f"- recipe_scope: `{recipe_id}` only",
        "",
        "## Selection Status",
        "",
        "- none selected",
        "",
        "## Non-Claiming Notice",
        "",
        f"- This run executes `{recipe_id}` only and does not compare multiple recipes.",
        "- No benchmark-facing finalist or winner claim is made from this artifact.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _build_contamination_review(rows: list[dict[str, Any]]) -> dict[str, Any]:
    contaminated = [row["final_board"]["row_id"] for row in rows if row["contamination_status"] != "clean"]
    return {
        "schema_version": "final_harness_contamination_review.v1",
        "status": "deterministic",
        "contaminated_row_ids": contaminated,
        "contamination_gate": "pass" if not contaminated else "fail",
    }


def _build_invalidity_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = [row["final_board"]["row_id"] for row in rows if row["verdict"] == "invalid"]
    return {
        "schema_version": "final_harness_invalidity_report.v1",
        "status": "deterministic",
        "invalid_row_ids": invalid,
        "invalidity_gate": "pass" if not invalid else "fail",
    }


def _load_recipe(repo_root: Path, recipe_id: str) -> dict[str, Any]:
    payload = _load_yaml(repo_root / "tracking/collab/final_harness_eval_suite/recipe_candidates.yaml")
    recipes = payload.get("recipes", [])
    for recipe in recipes:
        if isinstance(recipe, dict) and recipe.get("recipe_id") == recipe_id:
            return recipe
    raise ValueError(f"recipe {recipe_id} not found")


def _model_client_kwargs(model_timeout_sec: int) -> dict[str, Any]:
    return {
        "timeout_sec": model_timeout_sec,
        "max_retries": 1,
        "tpm_pacer_enabled": _env_bool("HARNESS_TPM_PACER_ENABLED", default=True),
        "tpm_limit": _env_int("HARNESS_TPM_LIMIT", default=100000),
        "tpm_window_sec": _env_float("HARNESS_TPM_WINDOW_SEC", default=60.0),
        "tpm_throttle_fraction": _env_float("HARNESS_TPM_THROTTLE_FRACTION", default=0.85),
        "tpm_pause_sec": _env_float("HARNESS_TPM_PAUSE_SEC", default=4.0),
        "tpm_count_mode": os.environ.get("HARNESS_TPM_COUNT_MODE", "total"),
        "rpm_limit": _env_optional_int("HARNESS_RPM_LIMIT"),
        "rpm_window_sec": _env_float("HARNESS_RPM_WINDOW_SEC", default=60.0),
        "model_max_concurrency": _env_int("HARNESS_MODEL_MAX_CONCURRENCY", default=1),
    }


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, *, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _env_optional_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _env_float(name: str, *, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value >= 0 else default


def _resolve_model_route(model_mode: str) -> tuple[dict[str, Any], str]:
    if model_mode == "stub":
        return LocalStubModelClient.create(response_text="Baseline control stub completion.").route, "local_stub"
    if model_mode == "azure":
        return _resolve_azure_gpt54_mini_route(), "azure_gpt54_mini"
    if model_mode == "azure_gpt53_codex":
        return _resolve_azure_gpt53_codex_route(), "azure_gpt53_codex"
    if model_mode == "azure_gpt54_mini":
        return _resolve_azure_gpt54_mini_route(), "azure_gpt54_mini"
    if model_mode == "codex_subscription":
        raise CertifiedRouteResolutionError(
            "certified_route_codex_subscription_disallowed",
            "codex_subscription is disabled for certified baseline eval routing; use Azure gpt-5.4-mini or explicit stub debug mode.",
            details={"requested_model_mode": model_mode},
        )
    return _resolve_azure_gpt54_mini_route(), "azure_gpt54_mini"


def _resolve_azure_gpt54_mini_route() -> dict[str, Any]:
    detection = detect_azure_openai_routes()
    gpt54_route = detection["routes"][0] if detection.get("routes") else {}
    if not gpt54_route.get("available", False):
        raise CertifiedRouteResolutionError(
            "invalid_due_to_environment_missing_azure_gpt54_mini_route",
            "Azure gpt-5.4-mini route env is missing; certified baseline evals do not fall back to codex_subscription or stub.",
            details={
                "required_route_id": "azure_openai_gpt54_mini",
                "missing_envs": list(gpt54_route.get("missing_envs", [])),
                "checked_env_groups": dict(gpt54_route.get("checked_env_groups", {})),
            },
        )
    return make_azure_gpt54_mini_route_from_env(request_settings={"temperature": 0}, provider_scope="certified_eval")


def _resolve_azure_gpt53_codex_route() -> dict[str, Any]:
    detection = detect_azure_openai_routes()
    routes = detection.get("routes", [])
    gpt53_route = routes[1] if len(routes) > 1 else {}
    if not gpt53_route.get("available", False):
        raise CertifiedRouteResolutionError(
            "invalid_due_to_environment_missing_azure_gpt53_codex_route",
            "Azure gpt-5.3-codex route env is missing; this certified baseline runner does not fall back to codex_subscription or stub.",
            details={
                "required_route_id": "azure_openai_gpt53_codex",
                "missing_envs": list(gpt53_route.get("missing_envs", [])),
                "checked_env_groups": dict(gpt53_route.get("checked_env_groups", {})),
            },
        )
    return make_azure_gpt53_codex_route_from_env(request_settings={"temperature": 0}, provider_scope="certified_eval")


def _resolve_terminalbench_tasks_root(task_id: str) -> Path:
    return resolve_terminalbench_tasks_root(task_id)


def _resolve_candidate_path(workspace_root: Path, candidate_output: str, row_spec: FinalSuiteRowSpec) -> Path:
    canonical_root = row_spec.canonical_workspace_root
    if candidate_output.startswith(canonical_root):
        rel = candidate_output[len(canonical_root):].lstrip("/")
        return (workspace_root / rel).resolve()
    rel = _container_path_to_rel(candidate_output)
    return (workspace_root / rel).resolve()


def _container_path_to_rel(path: str) -> str:
    if path.startswith("/workspace/"):
        return path[len("/workspace/") :]
    if path.startswith("/app/"):
        return path[len("/app/") :]
    return path.strip("/")


def _docker_available() -> bool:
    return bool(_docker_runtime_status().get("available", False))


def _docker_runtime_status() -> dict[str, Any]:
    docker_path = shutil.which("docker")
    if docker_path is None:
        return {
            "available": False,
            "reason_code": "invalid_environment_docker_cli_missing",
            "reason": "docker CLI not found on PATH",
            "probe": {"command": ["docker", "version"], "returncode": None, "stdout": "", "stderr": ""},
        }
    probe = subprocess.run(["docker", "version"], capture_output=True, text=True, check=False)
    stdout = probe.stdout.strip()
    stderr = probe.stderr.strip()
    if probe.returncode == 0:
        return {
            "available": True,
            "reason_code": "docker_runtime_ready",
            "reason": "docker runtime ready",
            "probe": {"command": ["docker", "version"], "returncode": 0, "stdout": stdout, "stderr": stderr},
        }
    return {
        "available": False,
        "reason_code": "invalid_environment_docker_unavailable",
        "reason": stderr or stdout or "docker runtime probe failed",
        "probe": {
            "command": ["docker", "version"],
            "returncode": probe.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "docker_path": docker_path,
        },
    }


def _docker_exec(workspace: Path, image: str, command: str, *, cwd: str, network_enabled: bool = False) -> dict[str, Any]:
    network_mode = "bridge" if network_enabled else "none"
    completed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-w",
            cwd,
            "-v",
            f"{workspace}:{cwd}",
            "--network",
            network_mode,
            image,
            "sh",
            "-lc",
            command,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": command,
        "cwd": cwd,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
        "timeout": False,
    }


def _parse_json_from_text(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def _grader_passed(grader_result: dict[str, Any]) -> bool:
    if isinstance(grader_result.get("passed"), bool):
        return bool(grader_result["passed"])
    if isinstance(grader_result.get("verdict"), str):
        return grader_result["verdict"] == "pass"
    return float(grader_result.get("score", 0.0)) >= 1.0


def _grader_reason_codes(grader_result: dict[str, Any]) -> list[str]:
    reason_codes = grader_result.get("reason_codes", [])
    if isinstance(reason_codes, list):
        return [str(item) for item in reason_codes if str(item).strip()]
    reasons = grader_result.get("reasons", [])
    if isinstance(reasons, list):
        return [str(item) for item in reasons if str(item).strip()]
    return []


def _normalize_failure_class(raw: str, passed: bool) -> str:
    if passed:
        return "none"
    mapping = {
        "none": "unclear",
        "runtime": "runtime",
        "provider": "provider",
        "tool_contract": "tool_contract",
        "filesystem_path": "path_cwd",
        "path_cwd": "path_cwd",
        "verification_completion": "verification_grading",
        "verification_grading": "verification_grading",
        "environment_toolchain": "runtime",
        "retrieval_reduction": "reduction_selection",
        "reduction_selection": "reduction_selection",
        "invalid_environment": "sandbox",
        "contamination": "verification_grading",
        "schema_parsing": "schema_parsing",
        "evidence_acquisition": "evidence_acquisition",
        "model_capability": "model_capability",
        "unclear": "unclear",
    }
    return mapping.get(raw, "unclear")


def _row_network_enabled(row_spec: FinalSuiteRowSpec) -> bool:
    return bool(getattr(row_spec, "network_enabled", False))


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _hash_workspace(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(root))
        hashes[rel] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return hashes


def _diff_hashes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed = []
    keys = set(before) | set(after)
    for key in sorted(keys):
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--backend-ref", default=DEFAULT_BACKEND_REF)
    parser.add_argument("--recipe-id", default="recipe_control")
    parser.add_argument(
        "--model-mode",
        default="auto",
        choices=["auto", "azure", "azure_gpt54_mini", "azure_gpt53_codex", "codex_subscription", "stub"],
    )
    parser.add_argument("--max-steps", type=int, default=14)
    parser.add_argument("--model-timeout-sec", type=int, default=120)
    parser.add_argument(
        "--include-sources",
        default="task_pack,benchmark_adapter,terminalbench_challenge",
        help="Comma-separated execution sources to run.",
    )
    parser.add_argument(
        "--benchmark-mode",
        default="native",
        choices=["native", "adapter"],
        help="Execution mode for benchmark_adapter rows.",
    )
    parser.add_argument(
        "--variant",
        default="active_evidence_kernel_v1",
        help="Variant ID to evaluate. Defaults to the active kernel starter variant.",
    )
    parser.add_argument(
        "--row-ids",
        default=None,
        help="Comma-separated row IDs to execute.",
    )
    parser.add_argument(
        "--row-certification-manifest",
        type=Path,
        default=None,
        help="Path to a JSON row-certification manifest for custom board admission labels.",
    )
    parser.add_argument(
        "--admission-labels",
        nargs="+",
        default=None,
        help="One or more admission labels to execute from the certification manifest.",
    )
    args = parser.parse_args()
    include_sources = tuple(part.strip() for part in args.include_sources.split(",") if part.strip())
    row_ids = tuple(part.strip() for part in args.row_ids.split(",") if part.strip()) if args.row_ids else None
    result = run_final_harness_eval_suite_baseline(
        output_root=args.output_root,
        image=args.image,
        backend_ref=args.backend_ref,
        recipe_id=args.recipe_id,
        model_mode=args.model_mode,
        max_steps=args.max_steps,
        model_timeout_sec=args.model_timeout_sec,
        include_sources=include_sources,
        benchmark_mode=args.benchmark_mode,
        variant_id=args.variant,
        row_ids=row_ids,
        row_certification_manifest=args.row_certification_manifest,
        admission_labels=tuple(args.admission_labels) if args.admission_labels is not None else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
