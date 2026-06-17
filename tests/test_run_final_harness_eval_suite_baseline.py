from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from runner.final_harness_eval_suite_adapter import FinalSuiteRowSpec
from tools import run_final_harness_eval_suite_baseline as mod


def _fake_row(row_id: str, row_type: str) -> dict[str, object]:
    return {
        "run_id": f"{row_id}__recipe_control",
        "eval_id": "final_harness_eval_suite_baseline_control",
        "task_pack_id": row_id,
        "family": "final_harness_eval_suite",
        "surface_type": "filesystem",
        "admission_level": "certified",
        "backend_ref": "azure_vm_docker",
        "environment_ref": "/tmp/environment_manifest.json",
        "artifact_refs": ["/tmp/artifact_bundle.json"],
        "trace_refs": ["/tmp/trace.json"],
        "closure_status": "closed",
        "task_truth_status": "pass",
        "contamination_status": "clean",
        "failure_class": "none",
        "reason_codes": ["row_passed"],
        "verifier_ref": "/tmp/verifier_output.json",
        "grader_ref": "/tmp/grader_output.json",
        "score": 1.0,
        "final_board": {
            "board_id": "final_harness_eval_suite_v1",
            "board_version": 1,
            "recipe_id": "recipe_control",
            "recipe_snapshot_ref": "tracking/collab/final_harness_eval_suite/recipe_candidates.yaml",
            "row_id": row_id,
            "row_type": row_type,
            "is_flagship": False,
            "critical_clusters": ["filesystem/path"],
            "provenance_type": "original_private",
            "contamination_gate": "clean",
            "invalidity_gate": "valid",
            "current_stack_ref": "tracking/collab/final_harness_eval_suite/current_stack_manifest.yaml",
        },
        "verdict": "pass",
        "model_route_mode": "local_stub",
    }


def test_build_row_prompt_treats_visible_verifier_as_diagnostic_not_completion_gate(tmp_path):
    task_pack_root = tmp_path / "task_pack"
    solver_pack = task_pack_root / "solver_pack"
    solver_pack.mkdir(parents=True)
    (solver_pack / "visible_prompt.md").write_text("Complete the task.", encoding="utf-8")
    row_spec = FinalSuiteRowSpec(
        row_id="fhard_02_service_orchestration_flagship",
        row_type="hard",
        is_flagship=True,
        provenance_type="benchmark_derived_customized",
        critical_clusters=("service/process",),
        task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_02_service_orchestration_flagship/task_pack.yaml",
        task_pack_id="fhard_02_service_orchestration_flagship",
        canonical_workspace_root="/workspace/fhard_02",
        runtime_python_command="python3",
        max_solver_seconds=180,
        surface_type="terminal",
        legacy_layout=True,
        expected_candidate_output="candidate/readiness_receipt.json",
    )

    prompt = mod._build_row_prompt(task_pack_root, row_spec)

    assert "visible verifier as a diagnostic" in prompt
    assert "necessary and not sufficient" in prompt
    assert "grounded in solver-visible evidence and provenance" in prompt


def test_run_final_harness_eval_suite_baseline_writes_required_artifacts(tmp_path, monkeypatch):
    specs = [
        FinalSuiteRowSpec(
            row_id="fhard_01_toolchain_runner_repair",
            row_type="hard",
            is_flagship=False,
            provenance_type="benchmark_derived_customized",
            critical_clusters=("environment/toolchain",),
            task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_01_toolchain_runner_repair/task_pack.yaml",
            task_pack_id="fhard_01_toolchain_runner_repair",
            canonical_workspace_root="/workspace/fhard_01",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=True,
            expected_candidate_output="candidate",
        ),
        FinalSuiteRowSpec(
            row_id="fsent_01_tool_call_bfcl_composite",
            row_type="sentinel",
            is_flagship=False,
            provenance_type="private_homolog",
            critical_clusters=("tooling/tool-call",),
            task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/sentinel/fsent_01_tool_call_bfcl_composite/task_pack.yaml",
            task_pack_id="fsent_01_tool_call_bfcl_composite",
            canonical_workspace_root="/workspace/toolcall",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="tool_call",
            legacy_layout=False,
            expected_candidate_output="/workspace/toolcall/out/final_submission.json",
        ),
    ]

    monkeypatch.setattr(mod, "load_final_suite_row_specs", lambda _repo_root: specs)
    monkeypatch.setattr(mod, "_resolve_model_route", lambda _mode: ({"provider": "stub", "model": "stub"}, "local_stub"))
    monkeypatch.setattr(
        mod,
        "_docker_runtime_status",
        lambda: {"available": True, "reason_code": "docker_runtime_ready", "reason": "ready", "probe": {}},
    )
    monkeypatch.setattr(
        mod,
        "_run_row",
        lambda **kwargs: {
            **_fake_row(kwargs["row_spec"].row_id, kwargs["row_spec"].row_type),
            "token_and_cost_summary": {
                "fhard_01_toolchain_runner_repair": {
                    "total_input_messages": 1,
                    "input_tokens": 100,
                    "cached_input_tokens": 25,
                    "billable_input_tokens": 75,
                    "total_output_tokens": 40,
                    "output_tokens": 40,
                    "total_tokens": 140,
                    "usd": 0.01,
                    "usd_estimate": 0.01,
                    "cost_breakdown_usd": {
                        "input_cost": 0.003,
                        "cached_input_cost": 0.001,
                        "output_cost": 0.006,
                        "total_cost": 0.01,
                    },
                    "pricing_model_ids": ["gpt-5.4-mini"],
                },
                "fsent_01_tool_call_bfcl_composite": {
                    "total_input_messages": 2,
                    "input_tokens": 50,
                    "cached_input_tokens": 5,
                    "billable_input_tokens": 45,
                    "total_output_tokens": 10,
                    "output_tokens": 10,
                    "total_tokens": 60,
                    "usd": 0.02,
                    "usd_estimate": 0.02,
                    "cost_breakdown_usd": {
                        "input_cost": 0.01,
                        "cached_input_cost": 0.002,
                        "output_cost": 0.008,
                        "total_cost": 0.02,
                    },
                    "pricing_model_ids": ["gpt-5.3-codex"],
                },
            }[kwargs["row_spec"].row_id],
        },
    )

    result = mod.run_final_harness_eval_suite_baseline(output_root=tmp_path, model_mode="stub")
    run_root = Path(result["run_root"])

    assert result["row_count"] == 2
    assert (run_root / "run_summary.json").exists()
    assert (run_root / "result_rows.jsonl").exists()
    assert (run_root / "recipe_manifest_snapshot.yaml").exists()
    assert (run_root / "contamination_review.json").exists()
    assert (run_root / "invalidity_report.json").exists()
    assert (run_root / "scoreboard.json").exists()
    assert (run_root / "scoreboard.md").exists()
    assert (run_root / "finalist_selection.md").exists()

    rows = [json.loads(line) for line in (run_root / "result_rows.jsonl").read_text(encoding="utf-8").splitlines() if line]
    summary = json.loads((run_root / "run_summary.json").read_text(encoding="utf-8"))
    row_scoreboard = json.loads((run_root / "result_rows_scoreboard.json").read_text(encoding="utf-8"))
    final_scoreboard = json.loads((run_root / "scoreboard.json").read_text(encoding="utf-8"))
    assert summary["recipe_id"] == "recipe_control"
    assert summary["row_count"] == 2
    assert summary["model_route_mode"] == "local_stub"
    assert summary["docker_runtime_status"]["available"] is True
    assert summary["cost_summary"]["run_count"] == 2
    assert summary["cost_summary"]["input_tokens"] == 150
    assert row_scoreboard["cost_summary"]["billable_input_tokens"] == 120
    assert row_scoreboard["cost_summary"]["pricing_model_ids"] == ["gpt-5.3-codex", "gpt-5.4-mini"]
    assert final_scoreboard["cost_summary"]["total_tokens"] == 200
    assert "Cost summary:" in (run_root / "scoreboard.md").read_text(encoding="utf-8")
    assert {row["token_and_cost_summary"]["total_tokens"] for row in rows} == {60, 140}
    assert "No benchmark-facing finalist or winner claim is made from this artifact." in (
        run_root / "finalist_selection.md"
    ).read_text(encoding="utf-8")


def test_run_final_harness_eval_suite_baseline_filters_by_certification_manifest(tmp_path, monkeypatch):
    specs = [
        FinalSuiteRowSpec(
            row_id="fhard_01_toolchain_runner_repair",
            row_type="hard",
            is_flagship=False,
            provenance_type="benchmark_derived_customized",
            critical_clusters=("environment/toolchain",),
            task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_01_toolchain_runner_repair/task_pack.yaml",
            task_pack_id="fhard_01_toolchain_runner_repair",
            canonical_workspace_root="/workspace/fhard_01",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=True,
            expected_candidate_output="candidate",
        ),
        FinalSuiteRowSpec(
            row_id="fhard_02_service_orchestration_flagship",
            row_type="hard",
            is_flagship=True,
            provenance_type="benchmark_derived_customized",
            critical_clusters=("environment/toolchain", "tooling/tool-call"),
            task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_02_service_orchestration_flagship/task_pack.yaml",
            task_pack_id="fhard_02_service_orchestration_flagship",
            canonical_workspace_root="/workspace/fhard_02",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=True,
            expected_candidate_output="candidate",
        ),
        FinalSuiteRowSpec(
            row_id="fsent_05_long_handoff_composition_smoke",
            row_type="composition",
            is_flagship=False,
            provenance_type="original_private",
            critical_clusters=("long-horizon orchestration",),
            task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/composition/fsent_05_long_handoff_composition_smoke/task_pack.yaml",
            task_pack_id="fsent_05_long_handoff_composition_smoke",
            canonical_workspace_root="/workspace/fsent_05",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=False,
            expected_candidate_output="candidate",
        ),
    ]
    manifest_path = tmp_path / "row_certification_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "custom_eval_row_certification_manifest.v1",
                "board_id": "final_harness_eval_suite_v1",
                "board_version": 1,
                "generated_at_utc": "2026-06-05T00:00:00Z",
                "selection_sets": {
                    "promotion_math": ["fhard_01_toolchain_runner_repair"],
                    "diagnostic_only": ["fhard_02_service_orchestration_flagship"],
                    "quarantine": ["fsent_05_long_handoff_composition_smoke"],
                    "holdout": [],
                },
                "rows": {
                    "fhard_01_toolchain_runner_repair": {
                        "admission_label": "certified_for_promotion_math",
                        "prompt_hidden_alignment": "aligned",
                        "oracle_pass": "pass",
                        "known_bad_fail": "pass",
                        "contamination_audit": "clean",
                        "deterministic_runner": "pass",
                        "repeatability": "pass",
                        "result_semantics": "stable",
                        "trace_attribution": "supported",
                        "evidence_paths": ["tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_01_toolchain_runner_repair/solver_pack/README.md"],
                    },
                    "fhard_02_service_orchestration_flagship": {
                        "admission_label": "diagnostic_only",
                        "prompt_hidden_alignment": "partial",
                        "oracle_pass": "pass",
                        "known_bad_fail": "pass",
                        "contamination_audit": "clean",
                        "deterministic_runner": "pass",
                        "repeatability": "pass",
                        "result_semantics": "stable",
                        "trace_attribution": "mixed",
                        "evidence_paths": ["tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_02_service_orchestration_flagship/solver_pack/README.md"],
                    },
                    "fsent_05_long_handoff_composition_smoke": {
                        "admission_label": "quarantine",
                        "prompt_hidden_alignment": "blocked",
                        "oracle_pass": "blocked",
                        "known_bad_fail": "blocked",
                        "contamination_audit": "blocked",
                        "deterministic_runner": "blocked",
                        "repeatability": "blocked",
                        "result_semantics": "blocked",
                        "trace_attribution": "blocked",
                        "evidence_paths": ["tracking/collab/final_harness_eval_suite/task_packs/composition/fsent_05_long_handoff_composition_smoke/solver_pack/README.md"],
                    },
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "load_final_suite_row_specs", lambda _repo_root: specs)
    monkeypatch.setattr(mod, "_resolve_model_route", lambda _mode: ({"provider": "stub", "model": "stub"}, "local_stub"))
    monkeypatch.setattr(
        mod,
        "_docker_runtime_status",
        lambda: {"available": True, "reason_code": "docker_runtime_ready", "reason": "ready", "probe": {}},
    )

    def fake_run_row(**kwargs):
        row = {
            **_fake_row(kwargs["row_spec"].row_id, kwargs["row_spec"].row_type),
            "token_and_cost_summary": {
                "total_input_messages": 1,
                "input_tokens": 10,
                "cached_input_tokens": 0,
                "billable_input_tokens": 10,
                "total_output_tokens": 4,
                "output_tokens": 4,
                "total_tokens": 14,
                "usd": 0.01,
                "usd_estimate": 0.01,
                "cost_breakdown_usd": {
                    "input_cost": 0.003,
                    "cached_input_cost": 0.0,
                    "output_cost": 0.007,
                    "total_cost": 0.01,
                },
                "pricing_model_ids": ["gpt-5.4-mini"],
            },
        }
        return row

    monkeypatch.setattr(mod, "_run_row", fake_run_row)

    result = mod.run_final_harness_eval_suite_baseline(
        output_root=tmp_path,
        model_mode="stub",
        row_certification_manifest=manifest_path,
        admission_labels=("certified_for_promotion_math",),
    )

    run_root = Path(result["run_root"])
    rows = [
        json.loads(line)
        for line in (run_root / "result_rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    summary = json.loads((run_root / "run_summary.json").read_text(encoding="utf-8"))
    copied_manifest = json.loads((run_root / "row_certification_manifest.json").read_text(encoding="utf-8"))

    assert result["row_count"] == 1
    assert summary["selected_row_count"] == 1
    assert summary["row_certification_selection_labels"] == ["certified_for_promotion_math"]
    assert summary["row_certification_selected_row_ids"] == ["fhard_01_toolchain_runner_repair"]
    assert summary["promotion_math_selected_row_ids"] == ["fhard_01_toolchain_runner_repair"]
    assert copied_manifest["rows"]["fhard_01_toolchain_runner_repair"]["admission_label"] == "certified_for_promotion_math"
    assert [row["task_pack_id"] for row in rows] == ["fhard_01_toolchain_runner_repair"]
    assert rows[0]["final_board"]["admission_label"] == "certified_for_promotion_math"
    assert rows[0]["final_board"]["promotion_math_included"] is True
    assert rows[0]["final_board"]["row_certification_manifest_ref"] == str(run_root / "row_certification_manifest.json")

    diagnostic_result = mod.run_final_harness_eval_suite_baseline(
        output_root=tmp_path,
        model_mode="stub",
        row_certification_manifest=manifest_path,
        admission_labels=("diagnostic_only",),
    )
    diagnostic_run_root = Path(diagnostic_result["run_root"])
    diagnostic_rows = [
        json.loads(line)
        for line in (diagnostic_run_root / "result_rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    diagnostic_summary = json.loads((diagnostic_run_root / "run_summary.json").read_text(encoding="utf-8"))

    assert diagnostic_result["row_count"] == 1
    assert diagnostic_summary["selected_row_count"] == 1
    assert diagnostic_summary["row_certification_selected_row_ids"] == ["fhard_02_service_orchestration_flagship"]
    assert diagnostic_summary["promotion_math_selected_row_ids"] == []
    assert [row["task_pack_id"] for row in diagnostic_rows] == ["fhard_02_service_orchestration_flagship"]
    assert diagnostic_rows[0]["final_board"]["admission_label"] == "diagnostic_only"
    assert diagnostic_rows[0]["final_board"]["promotion_math_included"] is False


def test_main_defaults_variant_to_active_evidence_kernel(tmp_path, monkeypatch, capsys):
    captured_kwargs: dict[str, object] = {}

    def fake_run_final_harness_eval_suite_baseline(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "run_id": "stub_run",
            "run_root": str(tmp_path),
            "row_count": 0,
            "variant_id": kwargs["variant_id"],
            "model_route_mode": kwargs["model_mode"],
            "result_rows_jsonl": str(tmp_path / "result_rows.jsonl"),
            "scoreboard_json": str(tmp_path / "scoreboard.json"),
            "route_manifest_ref": str(tmp_path / "route_manifest.json"),
            "docker_available": True,
        }

    monkeypatch.setattr(mod, "run_final_harness_eval_suite_baseline", fake_run_final_harness_eval_suite_baseline)
    monkeypatch.setattr(sys, "argv", ["run_final_harness_eval_suite_baseline.py", "--output-root", str(tmp_path)])

    mod.main()
    capsys.readouterr()

    assert captured_kwargs["variant_id"] == "active_evidence_kernel_v1"


def test_function_defaults_variant_to_active_evidence_kernel():
    assert mod.run_final_harness_eval_suite_baseline.__kwdefaults__["variant_id"] == "active_evidence_kernel_v1"


def test_container_path_to_rel_handles_workspace_and_app_prefixes():
    assert mod._container_path_to_rel("/workspace/repo/out/final_submission.json") == "repo/out/final_submission.json"
    assert mod._container_path_to_rel("/app/candidate/report.json") == "candidate/report.json"
    assert mod._container_path_to_rel("candidate/report.json") == "candidate/report.json"


def test_build_trace_payload_includes_model_client_error_event(tmp_path):
    row_root = tmp_path / "row"
    route_trace = row_root / "route_trace"
    route_trace.mkdir(parents=True)
    events = [
        {
            "event_type": "model_client_error",
            "payload": {"details": {"message": "bad request", "status_code": 400, "error_kind": "http_error"}},
        }
    ]
    (route_trace / "run_events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    row_spec = FinalSuiteRowSpec(
        row_id="fhard_01_toolchain_runner_repair",
        row_type="hard",
        is_flagship=False,
        provenance_type="benchmark_derived_customized",
        critical_clusters=("environment/toolchain",),
        task_pack_ref="x",
        task_pack_id="fhard_01_toolchain_runner_repair",
        canonical_workspace_root="/workspace/fhard_01",
        runtime_python_command="python3",
        max_solver_seconds=180,
        surface_type="terminal",
        legacy_layout=True,
        expected_candidate_output="candidate",
    )

    trace = mod._build_trace_payload(
        row_root,
        row_spec,
        {"runtime_timing": {"execution_sec": 1}},
        {"exit_code": 0, "command": "true"},
        {},
        {},
    )

    assert trace["events"][0]["event_type"] == "model_client_error"
    assert trace["events"][0]["status_code"] == 400


def test_run_row_persists_token_and_cost_summary(tmp_path, monkeypatch):
    row_spec = next(spec for spec in mod.load_final_suite_row_specs(mod.REPO_ROOT) if spec.execution_source == "task_pack")
    route = {"model_name": "dep-gpt54-mini", "request_settings": {"pricing_model_id": "gpt-5.4-mini"}}
    route_result = {
        "runtime_timing": {"execution_sec": 1.0},
        "execution": {
            "status": "completed",
            "steps": [
                {
                    "completion": {
                        "model_route": route,
                        "usage": {
                            "input_messages": 1,
                            "input_tokens": 120,
                            "cached_input_tokens": 30,
                            "output_tokens": 20,
                            "total_tokens": 140,
                        },
                    }
                }
            ],
        },
        "verification": {"verified": True},
        "action_bus": {},
        "evidence_kernel": {},
        "evidence_kernel_working_context_pack": {},
        "run_events": [],
    }

    monkeypatch.setattr(mod, "_stage_workspace", lambda _task_pack_root, workspace_root, _row_spec: workspace_root.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(mod, "_stage_grading_pack", lambda _task_pack_root, grading_root: grading_root.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(mod, "_run_visible_verifier", lambda *_args, **_kwargs: {"exit_code": 0, "command": "python3 visible_verifier.py"})
    monkeypatch.setattr(
        mod,
        "_run_grader",
        lambda *_args, **_kwargs: {"passed": True, "verdict": "pass", "score": 1.0, "reason_codes": ["row_passed"]},
    )
    monkeypatch.setattr(mod, "run_reference_baseline", lambda **_kwargs: route_result)

    row = mod._run_row(
        run_root=tmp_path,
        row_spec=row_spec,
        image="python:3.12-slim",
        backend_ref="azure_vm_docker",
        recipe_id="recipe_control",
        model_route=route,
        model_route_mode="azure_gpt54_mini",
        max_steps=1,
        model_timeout_sec=1,
        variant_id="active_evidence_kernel_v1",
        route_manifest={"variant_id": "active_evidence_kernel_v1"},
    )
    persisted_row = json.loads((tmp_path / "result_rows" / f"{row_spec.row_id}.json").read_text(encoding="utf-8"))

    assert row["token_and_cost_summary"]["total_input_messages"] == 1
    assert row["token_and_cost_summary"]["input_tokens"] == 120
    assert row["token_and_cost_summary"]["cached_input_tokens"] == 30
    assert row["token_and_cost_summary"]["billable_input_tokens"] == 90
    assert row["token_and_cost_summary"]["output_tokens"] == 20
    assert row["token_and_cost_summary"]["total_tokens"] == 140
    assert row["token_and_cost_summary"]["pricing_model_ids"] == ["gpt-5.4-mini"]
    assert row["token_and_cost_summary"]["usd"] == pytest.approx(0.00015975, rel=0.0, abs=1e-12)
    assert row["token_and_cost_summary"]["usd_estimate"] == pytest.approx(0.00015975, rel=0.0, abs=1e-12)
    assert persisted_row["token_and_cost_summary"] == row["token_and_cost_summary"]


def test_resolve_model_route_supports_explicit_gpt53_codex(monkeypatch):
    monkeypatch.setattr(
        mod,
        "_resolve_azure_gpt53_codex_route",
        lambda: {"provider": "azure", "model": "gpt-5.3-codex"},
    )
    route, mode = mod._resolve_model_route("azure_gpt53_codex")
    assert mode == "azure_gpt53_codex"
    assert route["model"] == "gpt-5.3-codex"


def test_resolve_model_route_rejects_codex_subscription_for_certified_runs():
    with pytest.raises(mod.CertifiedRouteResolutionError) as excinfo:
        mod._resolve_model_route("codex_subscription")
    assert excinfo.value.reason_code == "certified_route_codex_subscription_disallowed"


def test_resolve_model_route_auto_requires_azure_route(monkeypatch):
    monkeypatch.setattr(
        mod,
        "detect_azure_openai_routes",
        lambda: {
            "routes": [
                {
                    "available": False,
                    "missing_envs": ["AZURE_OPENAI_GPT54_MINI_KEY"],
                    "checked_env_groups": {"AZURE_OPENAI_GPT54_MINI_KEY": ["AZURE_OPENAI_GPT54_MINI_KEY"]},
                }
            ]
        },
    )
    with pytest.raises(mod.CertifiedRouteResolutionError) as excinfo:
        mod._resolve_model_route("auto")
    assert excinfo.value.reason_code == "invalid_due_to_environment_missing_azure_gpt54_mini_route"


def test_run_final_harness_eval_suite_baseline_marks_rows_invalid_when_docker_unavailable(tmp_path, monkeypatch):
    specs = [
        FinalSuiteRowSpec(
            row_id="fhard_01_toolchain_runner_repair",
            row_type="hard",
            is_flagship=False,
            provenance_type="benchmark_derived_customized",
            critical_clusters=("environment/toolchain",),
            task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/hard/fhard_01_toolchain_runner_repair/task_pack.yaml",
            task_pack_id="fhard_01_toolchain_runner_repair",
            canonical_workspace_root="/workspace/fhard_01",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=True,
            expected_candidate_output="candidate",
        )
    ]
    monkeypatch.setattr(mod, "load_final_suite_row_specs", lambda _repo_root: specs)
    monkeypatch.setattr(mod, "_resolve_model_route", lambda _mode: ({"provider": "stub", "model": "stub"}, "local_stub"))
    monkeypatch.setattr(
        mod,
        "_docker_runtime_status",
        lambda: {
            "available": False,
            "reason_code": "invalid_environment_docker_unavailable",
            "reason": "docker daemon unavailable",
            "probe": {"command": ["docker", "version"], "returncode": 1},
        },
    )
    result = mod.run_final_harness_eval_suite_baseline(output_root=tmp_path, model_mode="stub")
    rows = [json.loads(line) for line in (Path(result["run_root"]) / "result_rows.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert rows[0]["verdict"] == "invalid"
    assert rows[0]["failure_class"] == "sandbox"
    assert rows[0]["reason_codes"] == ["invalid_environment_docker_unavailable"]


def test_run_final_harness_eval_suite_baseline_marks_rows_invalid_when_route_resolution_fails(tmp_path, monkeypatch):
    specs = [
        FinalSuiteRowSpec(
            row_id="fhard_01_toolchain_runner_repair",
            row_type="hard",
            is_flagship=False,
            provenance_type="benchmark_derived_customized",
            critical_clusters=("environment/toolchain",),
            task_pack_ref="x",
            task_pack_id="fhard_01_toolchain_runner_repair",
            canonical_workspace_root="/workspace/fhard_01",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=True,
            expected_candidate_output="candidate",
            execution_source="task_pack",
        )
    ]
    monkeypatch.setattr(mod, "load_final_suite_row_specs", lambda _repo_root: specs)
    monkeypatch.setattr(
        mod,
        "_resolve_model_route",
        lambda _mode: (_ for _ in ()).throw(
            mod.CertifiedRouteResolutionError(
                "invalid_due_to_environment_missing_azure_gpt54_mini_route",
                "missing azure route",
                details={"missing_envs": ["AZURE_OPENAI_GPT54_MINI_KEY"]},
            )
        ),
    )
    monkeypatch.setattr(
        mod,
        "_docker_runtime_status",
        lambda: {"available": True, "reason_code": "docker_runtime_ready", "reason": "ready", "probe": {}},
    )
    result = mod.run_final_harness_eval_suite_baseline(output_root=tmp_path, model_mode="auto")
    rows = [
        json.loads(line)
        for line in (Path(result["run_root"]) / "result_rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert rows[0]["verdict"] == "invalid"
    assert rows[0]["failure_class"] == "provider"
    assert rows[0]["reason_codes"][0] == "invalid_due_to_environment_missing_azure_gpt54_mini_route"


def test_run_final_harness_eval_suite_baseline_short_circuits_all_docker_rows_when_runtime_unavailable(tmp_path, monkeypatch):
    specs = [
        FinalSuiteRowSpec(
            row_id="fhard_one",
            row_type="hard",
            is_flagship=False,
            provenance_type="benchmark_derived_customized",
            critical_clusters=("environment/toolchain",),
            task_pack_ref="x",
            task_pack_id="fhard_one",
            canonical_workspace_root="/workspace/h1",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=True,
            expected_candidate_output="candidate",
            execution_source="task_pack",
        ),
        FinalSuiteRowSpec(
            row_id="fbench_one",
            row_type="official_benchmark",
            is_flagship=False,
            provenance_type="official_benchmark",
            critical_clusters=("tooling/tool-call",),
            task_pack_ref=None,
            task_pack_id="fbench_one",
            canonical_workspace_root="/app",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=False,
            expected_candidate_output="candidate",
            execution_source="benchmark_adapter",
            benchmark_adapter="bfcl",
            benchmark_case_id="dummy_case",
            benchmark_name="BFCL",
        ),
        FinalSuiteRowSpec(
            row_id="ftb_one",
            row_type="terminalbench_challenge",
            is_flagship=False,
            provenance_type="official_benchmark",
            critical_clusters=("verification/completion",),
            task_pack_ref=None,
            task_pack_id="ftb_one",
            canonical_workspace_root="/app",
            runtime_python_command="python3",
            max_solver_seconds=180,
            surface_type="terminal",
            legacy_layout=False,
            expected_candidate_output="candidate",
            execution_source="terminalbench_challenge",
            challenge_task_id="dummy_task",
        ),
    ]
    monkeypatch.setattr(mod, "load_final_suite_row_specs", lambda _repo_root: specs)
    monkeypatch.setattr(mod, "_resolve_model_route", lambda _mode: ({"provider": "stub", "model": "stub"}, "local_stub"))
    monkeypatch.setattr(
        mod,
        "_docker_runtime_status",
        lambda: {
            "available": False,
            "reason_code": "invalid_environment_docker_unavailable",
            "reason": "docker daemon unavailable",
            "probe": {"command": ["docker", "version"], "returncode": 1},
        },
    )
    monkeypatch.setattr(mod, "_run_row", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("_run_row should not be called")))
    monkeypatch.setattr(
        mod,
        "_run_benchmark_adapter_row",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("_run_benchmark_adapter_row should not be called")),
    )
    monkeypatch.setattr(
        mod,
        "_run_terminalbench_challenge_row",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("_run_terminalbench_challenge_row should not be called")),
    )

    result = mod.run_final_harness_eval_suite_baseline(output_root=tmp_path, model_mode="stub")
    rows = [
        json.loads(line)
        for line in (Path(result["run_root"]) / "result_rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(rows) == 3
    assert all(row["verdict"] == "invalid" for row in rows)
    assert all(row["reason_codes"] == ["invalid_environment_docker_unavailable"] for row in rows)


@pytest.mark.parametrize(
    ("row_id", "adapter_key", "expected_authority_label", "grade_stub"),
    [
        (
            "fbench_contextbench_verified_02",
            "contextbench",
            "equivalent",
            lambda: {"verdict": "pass", "reason_codes": [], "score": 1.0, "authority_label": "native", "authority_detail": "contextbench_native_verified_csv_runtime"},
        ),
        (
            "fbench_letta_filesystem_006_medium",
            "letta",
            "equivalent",
            lambda: {"verdict": "pass", "reason_codes": [], "score": 1.0, "authority_label": "native", "authority_detail": "letta_native_filesystem_suite_runtime"},
        ),
    ],
)
def test_benchmark_adapter_rows_preserve_equivalent_authority_labels(tmp_path, monkeypatch, row_id, adapter_key, expected_authority_label, grade_stub):
    specs = {spec.row_id: spec for spec in mod.load_final_suite_row_specs(mod.REPO_ROOT)}
    row_spec = specs[row_id]

    def _stub_run_reference_baseline(**kwargs):
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").parent.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("", encoding="utf-8")
        return {
            "runtime_timing": {"execution_sec": 1.0},
            "action_bus": {},
            "evidence_kernel": {},
            "evidence_kernel_working_context_pack": {},
            "verification": {"verified": True},
            "execution": {"status": "completed"},
        }

    monkeypatch.setattr(mod, "run_reference_baseline", _stub_run_reference_baseline)
    monkeypatch.setattr(mod, "_run_visible_verifier", lambda **_kwargs: {"exit_code": 0, "command": "bash /app/tests/test.sh"})
    monkeypatch.setattr(mod, "_extract_final_assistant_text", lambda _row_root: "{\"answer\": true}")

    if adapter_key == "contextbench":
        monkeypatch.setattr(
            mod.contextbench_adapter,
            "native_grader_preflight",
            lambda: {"native_runtime_available": True, "blocker_codes": []},
        )
        monkeypatch.setattr(mod.contextbench_adapter, "grade_contextbench_case_native", lambda _spec, _assistant_text: grade_stub())
    else:
        monkeypatch.setattr(
            mod.letta_adapter,
            "native_grader_preflight",
            lambda: {"native_runtime_available": True, "blocker_codes": []},
        )
        monkeypatch.setattr(mod.letta_adapter, "grade_letta_case_native", lambda _spec, _assistant_text: grade_stub())

    row = mod._run_benchmark_adapter_row(
        run_root=tmp_path,
        row_spec=row_spec,
        backend_ref="azure_vm_docker",
        recipe_id="recipe_control",
        model_route={"provider": "stub", "model": "stub"},
        model_route_mode="azure_gpt54_mini",
        max_steps=2,
        model_timeout_sec=1,
        benchmark_mode="native",
    )

    row_root = tmp_path / "rows" / row_id
    artifact_bundle = json.loads((row_root / "artifacts" / "artifact_bundle.json").read_text(encoding="utf-8"))
    environment_manifest = json.loads((row_root / "artifacts" / "environment_manifest.json").read_text(encoding="utf-8"))

    assert row["authority_label"] == expected_authority_label
    assert row["authority_detail"] == (
        mod.contextbench_adapter.ADAPTER_AUTHORITY_DETAIL
        if adapter_key == "contextbench"
        else mod.letta_adapter.ADAPTER_AUTHORITY_DETAIL
    )
    assert artifact_bundle["authority_label"] == expected_authority_label
    assert environment_manifest["authority_label"] == expected_authority_label


def test_terminalbench_public_benchmark_rows_are_supported(tmp_path, monkeypatch):
    task_root = tmp_path / "terminalbench" / "official_tasks" / "financial-document-processor"
    documents_root = task_root / "environment" / "documents"
    documents_root.mkdir(parents=True, exist_ok=True)
    (documents_root / "invoice_a.txt").write_text("invoice a", encoding="utf-8")
    (task_root / "task.toml").write_text('version = "1.0"\n', encoding="utf-8")
    (task_root / "instruction.md").write_text("Process documents.", encoding="utf-8")
    (task_root / "tests").mkdir(parents=True, exist_ok=True)
    (task_root / "tests" / "test_outputs.py").write_text("def noop():\n    return True\n", encoding="utf-8")

    row_spec = FinalSuiteRowSpec(
        row_id="terminalbench_public_financial-document-processor",
        row_type="official_benchmark",
        is_flagship=False,
        provenance_type="official_benchmark",
        critical_clusters=("filesystem/path", "retrieval/reduction", "verification/completion"),
        task_pack_ref=None,
        task_pack_id="terminalbench_public_financial-document-processor",
        canonical_workspace_root="/app",
        runtime_python_command="python3",
        max_solver_seconds=240,
        surface_type="filesystem",
        legacy_layout=False,
        expected_candidate_output="candidate",
        execution_source="benchmark_adapter",
        benchmark_adapter="terminalbench",
        benchmark_case_id="financial-document-processor",
        benchmark_name="TerminalBench",
        difficulty_tier="medium",
        authority_label="equivalent",
    )

    monkeypatch.setattr(
        mod.terminalbench_adapter,
        "load_selected_cases",
        lambda: {
            "financial-document-processor": {
                "task_id": "financial-document-processor",
                "probe_id": "terminalbench_public_financial-document-processor",
                "difficulty": "medium",
                "task_prompt": "Process the files under /app/documents into /app/invoices and /app/other.",
                "request_payload": {"required_artifact_path": "/app/invoices/summary.csv"},
            }
        },
    )
    monkeypatch.setattr(mod, "resolve_terminalbench_task_root", lambda _task_id: task_root)
    monkeypatch.setattr(
        mod,
        "run_reference_baseline",
        lambda **_kwargs: {
            "runtime_timing": {"execution_sec": 1.0},
            "action_bus": {},
            "evidence_kernel": {},
            "evidence_kernel_working_context_pack": {},
            "verification": {"verified": True},
            "execution": {"status": "completed", "steps": []},
        },
    )
    monkeypatch.setattr(mod, "_run_visible_verifier", lambda **_kwargs: {"exit_code": 0, "command": "bash /app/tests/test.sh"})
    monkeypatch.setattr(mod, "_extract_final_assistant_text", lambda _row_root: "summary.csv")
    monkeypatch.setattr(
        mod.terminalbench_adapter,
        "grade_terminalbench_case_equivalent",
        lambda *, task_id, workspace: {
            "verdict": "pass",
            "reason_codes": [],
            "artifact_path": str(workspace / "invoices" / "summary.csv"),
        },
    )

    row = mod._run_benchmark_adapter_row(
        run_root=tmp_path,
        row_spec=row_spec,
        backend_ref="azure_vm_docker",
        recipe_id="recipe_control",
        model_route={"provider": "stub", "model": "stub"},
        model_route_mode="azure_gpt54_mini",
        max_steps=2,
        model_timeout_sec=1,
        benchmark_mode="native",
    )

    workspace_root = tmp_path / "rows" / row_spec.row_id / "workspace"
    assert (workspace_root / "documents" / "invoice_a.txt").exists()
    assert (workspace_root / "invoices").exists()
    assert (workspace_root / "other").exists()
    assert row["verdict"] == "pass"
    assert row["failure_class"] == "none"


@pytest.mark.parametrize(
    ("row_id", "adapter_key", "native_tool_definitions"),
    [
        (
            "fbench_bfcl_multi_turn_composite_97",
            "bfcl",
            [
                {
                    "name": "native_bfcl_tool",
                    "description": "BFCL native schema bridge",
                    "parameters": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                    "input_schema": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                }
            ],
        ),
        (
            "fbench_acebench_normal_atom_bool_0",
            "acebench",
            [
                {
                    "name": "native_acebench_tool",
                    "description": "ACEBench native schema bridge",
                    "parameters": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                    "input_schema": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                }
            ],
        ),
    ],
)
def test_benchmark_adapter_rows_inject_native_tool_definitions_into_route_manifest(
    tmp_path,
    monkeypatch,
    row_id,
    adapter_key,
    native_tool_definitions,
):
    specs = {spec.row_id: spec for spec in mod.load_final_suite_row_specs(mod.REPO_ROOT)}
    row_spec = specs[row_id]
    captured: dict[str, object] = {}

    def _stub_run_reference_baseline(**kwargs):
        captured["route_manifest"] = kwargs["route_manifest"]
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").parent.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("", encoding="utf-8")
        return {
            "runtime_timing": {"execution_sec": 1.0},
            "action_bus": {},
            "evidence_kernel": {},
            "evidence_kernel_working_context_pack": {},
            "verification": {"verified": True},
            "execution": {"status": "completed"},
        }

    monkeypatch.setattr(mod, "run_reference_baseline", _stub_run_reference_baseline)
    monkeypatch.setattr(mod, "_run_visible_verifier", lambda **_kwargs: {"exit_code": 0, "command": "bash /app/tests/test.sh"})
    monkeypatch.setattr(mod, "_extract_final_assistant_text", lambda _row_root: "[]")

    if adapter_key == "bfcl":
        monkeypatch.setattr(mod.bfcl_adapter, "build_native_tool_definitions", lambda _case: native_tool_definitions)
        monkeypatch.setattr(
            mod.bfcl_native_adapter,
            "grade_bfcl_case_native",
            lambda _case, _calls: {"verdict": "pass", "reason_codes": [], "score": 1.0},
        )
    else:
        monkeypatch.setattr(
            mod.acebench_adapter,
            "build_native_tool_definitions",
            lambda **_kwargs: native_tool_definitions,
        )
        monkeypatch.setattr(
            mod.acebench_adapter,
            "native_grader_preflight",
            lambda: {"native_runtime_available": True, "blocker_codes": []},
        )
        monkeypatch.setattr(
            mod.acebench_adapter,
            "grade_case_native",
            lambda **_kwargs: {"verdict": "pass", "reason_codes": [], "score": 1.0},
        )

    mod._run_benchmark_adapter_row(
        run_root=tmp_path,
        row_spec=row_spec,
        backend_ref="azure_vm_docker",
        recipe_id="recipe_control",
        model_route={"provider": "stub", "model": "stub"},
        model_route_mode="azure_gpt54_mini",
        max_steps=2,
        model_timeout_sec=1,
        benchmark_mode="native",
    )

    route_manifest = captured["route_manifest"]
    assert isinstance(route_manifest, dict)
    assert route_manifest["native_tool_definitions"] == native_tool_definitions


def test_bfcl_rows_short_circuit_on_asset_preflight_failure(tmp_path, monkeypatch):
    specs = {spec.row_id: spec for spec in mod.load_final_suite_row_specs(mod.REPO_ROOT)}
    row_spec = specs["fbench_bfcl_multi_turn_composite_97"]

    monkeypatch.setattr(
        mod.bfcl_assets,
        "bfcl_asset_preflight",
        lambda: {
            "native_runtime_available": False,
            "blocker_codes": ["missing_bfcl_mirrored_assets"],
            "missing_paths": [
                "/missing/research/sources/codebases/deepagents/libs/evals/tests/evals/data/benchmark_samples/bfcl_v3_final.json",
                "/missing/tracking/collab/final_harness_eval_suite/adapter_fixtures/bfcl/benchmark_samples/bfcl_v3_final.json",
                "/missing/research/sources/codebases/deepagents/libs/evals/tests/evals/data/bfcl_apis",
                "/missing/tracking/collab/final_harness_eval_suite/adapter_fixtures/bfcl/bfcl_apis",
            ],
            "selected_sample_path": "",
            "selected_apis_dir": "",
            "sample_path_candidates": [],
            "api_dir_candidates": [],
        },
    )
    monkeypatch.setattr(
        mod,
        "run_reference_baseline",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("run_reference_baseline should not be called")),
    )
    monkeypatch.setattr(
        mod.bfcl_adapter,
        "load_mirrored_cases",
        lambda: (_ for _ in ()).throw(AssertionError("load_mirrored_cases should not be called")),
    )
    monkeypatch.setattr(
        mod.bfcl_native_adapter,
        "load_official_curated_cases",
        lambda: (_ for _ in ()).throw(AssertionError("load_official_curated_cases should not be called")),
    )

    row = mod._run_benchmark_adapter_row(
        run_root=tmp_path,
        row_spec=row_spec,
        backend_ref="azure_vm_docker",
        recipe_id="recipe_control",
        model_route={"provider": "stub", "model": "stub"},
        model_route_mode="azure_gpt54_mini",
        max_steps=2,
        model_timeout_sec=1,
        benchmark_mode="native",
    )
    persisted_row = json.loads((tmp_path / "result_rows" / f"{row_spec.row_id}.json").read_text(encoding="utf-8"))

    assert row["closure_status"] == "invalid"
    assert row["task_truth_status"] == "invalid"
    assert row["reason_codes"] == ["bfcl_asset_preflight_failed"]
    assert row["verdict"] == "invalid"
    assert persisted_row["closure_status"] == "invalid"
    assert persisted_row["task_truth_status"] == "invalid"
    assert persisted_row["reason_codes"] == ["bfcl_asset_preflight_failed"]
    assert persisted_row["verdict"] == "invalid"


def test_acebench_native_rows_follow_kernel_runtime_unavailable_truth(tmp_path, monkeypatch):
    specs = {spec.row_id: spec for spec in mod.load_final_suite_row_specs(mod.REPO_ROOT)}
    row_spec = specs["fbench_acebench_normal_atom_bool_0"]

    def _stub_run_reference_baseline(**kwargs):
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("", encoding="utf-8")
        return {
            "runtime_timing": {"execution_sec": 1.0},
            "action_bus": {},
            "evidence_kernel": {
                "native_tool_state": {
                    "runtime_status": "native_tool_runtime_unavailable",
                    "attempted_native_tool_call": True,
                }
            },
            "evidence_kernel_working_context_pack": {},
            "verification": {"verified": False},
            "execution": {
                "status": "max_steps_exhausted",
                "governed_status": "invalid_environment",
                "reason_codes": ["native_tool_runtime_unavailable"],
            },
        }

    monkeypatch.setattr(mod, "run_reference_baseline", _stub_run_reference_baseline)
    monkeypatch.setattr(mod, "_run_visible_verifier", lambda **_kwargs: {"exit_code": 0, "command": "bash /app/tests/test.sh"})
    monkeypatch.setattr(
        mod.acebench_adapter,
        "native_grader_preflight",
        lambda: {
            "native_runtime_available": True,
            "blocker_codes": [],
            "upstream_root": "/tmp/acebench",
            "python_executable": "python3",
        },
    )
    monkeypatch.setattr(
        mod.acebench_adapter,
        "build_native_tool_definitions",
        lambda **_kwargs: [
            {
                "name": "ProteinRichMealPlanner_generateList",
                "description": "ACEBench schema-only tool",
                "parameters": {"type": "object", "properties": {"meal_type": {"type": "string"}}},
                "input_schema": {"type": "object", "properties": {"meal_type": {"type": "string"}}},
            }
        ],
    )
    monkeypatch.setattr(mod, "_extract_final_assistant_text", lambda _row_root: "[]")
    monkeypatch.setattr(
        mod.acebench_adapter,
        "grade_case_native",
        lambda **_kwargs: {"verdict": "fail", "reason_codes": ["acebench_wrong_output_format"], "score": 0.0},
    )

    row = mod._run_benchmark_adapter_row(
        run_root=tmp_path,
        row_spec=row_spec,
        backend_ref="azure_vm_docker",
        recipe_id="recipe_control",
        model_route={"provider": "stub", "model": "stub"},
        model_route_mode="azure_gpt54_mini",
        max_steps=2,
        model_timeout_sec=1,
        benchmark_mode="native",
    )
    persisted_row = json.loads((tmp_path / "result_rows" / f"{row_spec.row_id}.json").read_text(encoding="utf-8"))

    assert row["closure_status"] == "invalid"
    assert row["task_truth_status"] == "invalid"
    assert row["failure_class"] == "runtime"
    assert row["reason_codes"] == ["native_tool_runtime_unavailable"]
    assert row["verdict"] == "invalid"
    assert persisted_row["closure_status"] == "invalid"
    assert persisted_row["task_truth_status"] == "invalid"
    assert persisted_row["failure_class"] == "runtime"
    assert persisted_row["reason_codes"] == ["native_tool_runtime_unavailable"]
    assert persisted_row["verdict"] == "invalid"


def test_acebench_native_rows_follow_live_finalization_shape_for_runtime_unavailable(tmp_path, monkeypatch):
    specs = {spec.row_id: spec for spec in mod.load_final_suite_row_specs(mod.REPO_ROOT)}
    row_spec = specs["fbench_acebench_normal_atom_bool_0"]

    def _stub_run_reference_baseline(**kwargs):
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("", encoding="utf-8")
        return {
            "runtime_timing": {"execution_sec": 1.0},
            "action_bus": {},
            "evidence_kernel": {},
            "evidence_kernel_working_context_pack": {},
            "verification": {"verified": False},
            "execution": {
                "status": "max_steps_exhausted",
                "governed_status": "invalid_environment",
                "finalization_reason_codes": ["native_tool_runtime_unavailable"],
                "finalization_bundle": {
                    "native_tool_status": {
                        "status": "unavailable",
                        "reason_codes": ["native_tool_runtime_unavailable"],
                        "output_summary": "native_tool_runtime_unavailable",
                    }
                },
            },
            "score_envelope": {
                "layers": {
                    "L4_final_acceptance": {
                        "reason_codes": ["native_tool_runtime_unavailable"],
                    }
                }
            },
        }

    monkeypatch.setattr(mod, "run_reference_baseline", _stub_run_reference_baseline)
    monkeypatch.setattr(mod, "_run_visible_verifier", lambda **_kwargs: {"exit_code": 0, "command": "bash /app/tests/test.sh"})
    monkeypatch.setattr(
        mod.acebench_adapter,
        "native_grader_preflight",
        lambda: {
            "native_runtime_available": True,
            "blocker_codes": [],
            "upstream_root": "/tmp/acebench",
            "python_executable": "python3",
        },
    )
    monkeypatch.setattr(
        mod.acebench_adapter,
        "build_native_tool_definitions",
        lambda **_kwargs: [
            {
                "name": "ProteinRichMealPlanner_generateList",
                "description": "ACEBench schema-only tool",
                "parameters": {"type": "object", "properties": {"meal_type": {"type": "string"}}},
                "input_schema": {"type": "object", "properties": {"meal_type": {"type": "string"}}},
            }
        ],
    )
    monkeypatch.setattr(mod, "_extract_final_assistant_text", lambda _row_root: "[]")
    monkeypatch.setattr(
        mod.acebench_adapter,
        "grade_case_native",
        lambda **_kwargs: {"verdict": "fail", "reason_codes": ["acebench_wrong_output_format"], "score": 0.0},
    )

    row = mod._run_benchmark_adapter_row(
        run_root=tmp_path,
        row_spec=row_spec,
        backend_ref="azure_vm_docker",
        recipe_id="recipe_control",
        model_route={"provider": "stub", "model": "stub"},
        model_route_mode="azure_gpt54_mini",
        max_steps=2,
        model_timeout_sec=1,
        benchmark_mode="native",
    )
    persisted_row = json.loads((tmp_path / "result_rows" / f"{row_spec.row_id}.json").read_text(encoding="utf-8"))

    assert row["closure_status"] == "invalid"
    assert row["task_truth_status"] == "invalid"
    assert row["failure_class"] == "runtime"
    assert row["reason_codes"] == ["native_tool_runtime_unavailable"]
    assert row["verdict"] == "invalid"
    assert persisted_row["closure_status"] == "invalid"
    assert persisted_row["task_truth_status"] == "invalid"
    assert persisted_row["failure_class"] == "runtime"
    assert persisted_row["reason_codes"] == ["native_tool_runtime_unavailable"]
    assert persisted_row["verdict"] == "invalid"


def test_terminalbench_exec_verifier_prepares_tests_mount():
    command = mod._terminalbench_exec_tests_mount_command()

    assert "mkdir -p /tests" in command
    assert "cp -a /app/tests/. /tests/" in command
    assert "/workspace" not in command


def test_terminalbench_task_root_resolver_uses_requested_task_id(monkeypatch):
    seen: dict[str, str] = {}

    def fake_resolve(task_id: str) -> Path:
        seen["task_id"] = task_id
        return Path("/tmp/terminalbench") / task_id

    monkeypatch.setattr(mod, "resolve_terminalbench_tasks_root", fake_resolve)

    result = mod._resolve_terminalbench_tasks_root("install-windows-3.11")

    assert result == Path("/tmp/terminalbench/install-windows-3.11")
    assert seen["task_id"] == "install-windows-3.11"


def test_root_mapped_docker_sandbox_stop_cleans_container_unless_preserved(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))

        class _Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Completed()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    sandbox = mod.RootMappedDockerSandbox(tmp_path / "sandbox")
    sandbox._container_id = "cid-123"
    sandbox._active = True
    mod.RootMappedDockerSandbox.last_container_id = "cid-123"
    mod.RootMappedDockerSandbox.last_container_active = True
    mod.RootMappedDockerSandbox.preserve_container_until_external_cleanup = False

    sandbox.stop()

    assert any(cmd[:4] == ["docker", "rm", "-f", "cid-123"] for cmd in calls)
    assert mod.RootMappedDockerSandbox.last_container_id is None
    assert mod.RootMappedDockerSandbox.last_container_active is False

    calls.clear()
    sandbox._container_id = "cid-456"
    sandbox._active = True
    mod.RootMappedDockerSandbox.last_container_id = "cid-456"
    mod.RootMappedDockerSandbox.last_container_active = True
    mod.RootMappedDockerSandbox.preserve_container_until_external_cleanup = True

    sandbox.stop()

    assert not any(cmd[:4] == ["docker", "rm", "-f", "cid-456"] for cmd in calls)
    assert mod.RootMappedDockerSandbox.last_container_id == "cid-456"
    assert mod.RootMappedDockerSandbox.last_container_active is True
    mod.RootMappedDockerSandbox.preserve_container_until_external_cleanup = False
    mod.RootMappedDockerSandbox.last_container_id = None
    mod.RootMappedDockerSandbox.last_container_active = False


def test_trace_payload_captures_action_and_kernel_receipt_events(tmp_path):
    row_root = tmp_path / "row"
    route_trace = row_root / "route_trace"
    route_trace.mkdir(parents=True)
    events = [
        {
            "event_type": "raw_bash_result",
            "payload": {"details": {"tool_name": "raw_bash", "command": "echo x", "exit_code": 0}},
        },
        {
            "event_type": "action_bus_recorded",
            "payload": {"details": {"action_id": "run-a0001", "action_type": "command", "tool_name": "raw_bash", "phase": "execute", "command": "echo x"}},
        },
        {
            "event_type": "evidence_kernel_receipt",
            "payload": {"details": {"receipt_id": "r0001", "action_id": "run-a0001", "action_type": "command", "tool_name": "raw_bash", "command": "echo x", "exit_code": 0}},
        },
    ]
    (route_trace / "run_events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    row_spec = FinalSuiteRowSpec(
        row_id="row",
        row_type="hard",
        is_flagship=False,
        provenance_type="original_private",
        critical_clusters=("cluster",),
        task_pack_ref="x",
        task_pack_id="row",
        canonical_workspace_root="/app",
        runtime_python_command="python3",
        max_solver_seconds=180,
        surface_type="terminal",
        legacy_layout=False,
        expected_candidate_output="candidate",
    )
    payload = mod._build_trace_payload(
        row_root=row_root,
        row_spec=row_spec,
        route_result={"runtime_timing": {"execution_sec": 1}},
        visible_result={"exit_code": 0, "command": "bash /tests/test.sh"},
        before_hashes={},
        after_hashes={},
    )
    event_types = [event["event_type"] for event in payload["events"]]
    assert "tool_call" in event_types
    assert "action_record" in event_types
    assert "kernel_receipt" in event_types


def test_execution_truth_payload_includes_action_bus_and_kernel_summaries():
    payload = mod._build_execution_truth_payload(
        route_result={
            "action_bus": {"action_count": 2},
            "evidence_kernel": {"receipt_count": 2, "native_tool_mode_active": True, "verifier_gate": {"status": "pass"}, "artifact_gate": {"status": "pass"}, "service_registry": {"svc": {"status": "ready"}}},
            "evidence_kernel_working_context_pack": {"recent_receipts": []},
            "verification": {"verified": True},
            "execution": {"status": "completed"},
        },
        visible_result={"exit_code": 0, "command": "bash /tests/test.sh"},
        grader_result={"passed": True, "score": 1.0, "reason_codes": ["row_passed"]},
        truth_alignment={"aligned": True, "reason_codes": []},
    )
    assert payload["action_bus_summary"]["action_count"] == 2
    assert payload["kernel_summary"]["receipt_count"] == 2
    assert payload["hidden_grader"]["passed"] is True
    assert payload["truth_alignment"]["aligned"] is True


def test_route_grader_truth_alignment_flags_visible_and_route_mismatches():
    alignment = mod._route_grader_truth_alignment(
        route_result={"verification": {"verified": True}},
        visible_result={"exit_code": 0},
        grader_result={"passed": False, "score": 0.0, "reason_codes": ["grader_failed"]},
    )
    assert alignment["aligned"] is False
    assert "route_verification_vs_grader_mismatch" in alignment["reason_codes"]
    assert "visible_verifier_vs_grader_mismatch" in alignment["reason_codes"]


def test_corroborated_row_status_downgrades_hidden_only_pass():
    row = _fake_row("fhard_08_original_noisy_open_workflow", "hard")
    row["truth_alignment"] = {"aligned": False}
    assert mod._corroborated_row_status(row) == "fail"


def test_render_final_board_scoreboard_uses_corroborated_row_statuses(monkeypatch, tmp_path):
    rows = [
        _fake_row("fhard_01_toolchain_runner_repair", "hard"),
        _fake_row("fsent_02_runtime_workspace_contract", "sentinel"),
    ]
    rows[0]["truth_alignment"] = {"aligned": False}
    rows[1]["truth_alignment"] = {"aligned": True}
    rows[0]["token_and_cost_summary"] = {
        "total_input_messages": 1,
        "input_tokens": 10,
        "cached_input_tokens": 2,
        "billable_input_tokens": 8,
        "total_output_tokens": 4,
        "output_tokens": 4,
        "total_tokens": 14,
        "usd": 0.01,
        "usd_estimate": 0.01,
        "cost_breakdown_usd": {"input_cost": 0.003, "cached_input_cost": 0.001, "output_cost": 0.006, "total_cost": 0.01},
        "pricing_model_ids": ["gpt-5.4-mini"],
    }
    rows[1]["token_and_cost_summary"] = {
        "total_input_messages": 2,
        "input_tokens": 20,
        "cached_input_tokens": 4,
        "billable_input_tokens": 16,
        "total_output_tokens": 6,
        "output_tokens": 6,
        "total_tokens": 26,
        "usd": 0.02,
        "usd_estimate": 0.02,
        "cost_breakdown_usd": {"input_cost": 0.01, "cached_input_cost": 0.002, "output_cost": 0.008, "total_cost": 0.02},
        "pricing_model_ids": ["gpt-5.3-codex"],
    }

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        mod,
        "_load_yaml",
        lambda _path: {
            "board_id": "final_harness_eval_suite_v1",
            "board_version": 1,
            "hard_rows": [{"row_id": "fhard_01_toolchain_runner_repair"}],
            "sentinel_or_composition_rows": [{"row_id": "fsent_02_runtime_workspace_contract"}],
            "flagship_row_ids": [],
            "required_critical_clusters": [],
            "critical_cluster_map": {},
        },
    )
    monkeypatch.setattr(
        mod,
        "render_scoreboard",
        lambda payload, registry, allow_pre_stability: captured.update(
            {"payload": payload, "registry": registry, "allow_pre_stability": allow_pre_stability}
        )
        or {
            "run_id": payload["run_id"],
            "board_id": "final_harness_eval_suite_v1",
            "board_version": 1,
            "generated_at_utc": "2026-06-03T00:00:00Z",
            "allow_pre_stability_eligibility": False,
            "ranking_tiebreak_order": [],
            "recipes": [],
            "finalists": [],
        },
    )
    monkeypatch.setattr(
        mod,
        "write_scoreboard_outputs",
        lambda scoreboard, output_dir: (output_dir / "scoreboard.json", output_dir / "scoreboard.md"),
    )

    mod._render_final_board_scoreboard(
        run_id="run-1",
        rows=rows,
        recipe_id="recipe_control",
        run_root=tmp_path,
        cost_summary=mod.aggregate_result_rows(rows)["cost_summary"],
    )

    recipe_payload = captured["payload"]["recipes"][0]
    assert recipe_payload["row_statuses"]["fhard_01_toolchain_runner_repair"] == "fail"
    assert recipe_payload["row_statuses"]["fsent_02_runtime_workspace_contract"] == "pass"
    assert captured["payload"]["cost_summary"]["run_count"] == 2
    assert captured["payload"]["cost_summary"]["total_tokens"] == 40


def test_merged_reason_codes_deduplicates_in_order():
    merged = mod._merged_reason_codes(
        ["grader_failed", "visible_verifier_vs_grader_mismatch"],
        ["visible_verifier_vs_grader_mismatch", "route_verification_vs_grader_mismatch"],
    )
    assert merged == [
        "grader_failed",
        "visible_verifier_vs_grader_mismatch",
        "route_verification_vs_grader_mismatch",
    ]
