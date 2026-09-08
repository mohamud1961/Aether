from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from aether.ledger import ExecutionLedger, Receipt
from aether.pcr_provider_protocol import pcr_primary_turn_schema
from aether.runtime_ir import normalize_relpath
from aether.submission_coherence import evaluate_submission_coherence
from evals.performance import run as performance_run
from evals.performance.adjudicate import compare, summarize_arm
from evals.performance.profile import PerformanceProfile

ROOT = Path(__file__).resolve().parents[1]
PERF = ROOT / "evals" / "performance"


def _profile_mapping() -> dict:
    return json.loads((PERF / "S6_CONTROL_S5D_V1.json").read_text(encoding="utf-8"))


def test_s6_profile_is_strict_single_attempt_canonical_runner() -> None:
    profile = PerformanceProfile.from_mapping(_profile_mapping())
    assert profile.max_attempts == 1
    assert profile.max_retries == 0
    assert profile.canonical_runner_only is True
    assert profile.provider_calls_allowed is True
    changed = _profile_mapping()
    changed["launch"]["max_retries"] = 1
    with pytest.raises(ValueError, match="one attempt, zero retries"):
        PerformanceProfile.from_mapping(changed)


def test_s6_calibration_board_is_fresh_and_reserved_disjoint() -> None:
    board = json.loads((PERF / "CALIBRATION_BOARD_V1.json").read_text(encoding="utf-8"))
    reserved = json.loads((PERF / "RESERVED_BOARD_IDS_V1.json").read_text(encoding="utf-8"))
    ids = [row["task_id"] for row in board["tasks"]]
    assert len(ids) == len(set(ids)) == 12
    assert not set(ids).intersection(reserved["excluded_from_calibration_task_ids"])
    excluded = reserved["excluded_from_calibration_task_ids"]
    assert len(excluded) == reserved["excluded_count"] == 113
    assert {"git-multibranch", "multi-source-data-merger", "cobol-modernization", "caffe-cifar-10", "adaptive-rejection-sampler", "overfull-hbox", "distribution-search", "rstan-to-pystan", "mailman", "pytorch-model-recovery", "mcmc-sampling-stan", "feal-linear-cryptanalysis", "query-optimize"} <= set(excluded)
    assert "git-multibranch" not in ids
    assert "sanitize-git-repo" in ids
    assert all(len(row["closure_sha256"]) == 64 and row["file_count"] > 0 for row in board["tasks"])
    assert set(board["funnel_groups"]["context_prompt_stage1"]) <= set(ids)


def test_s6_runner_builds_only_canonical_aether_run_command() -> None:
    profile = PerformanceProfile.from_mapping(_profile_mapping())
    argv = performance_run.build_argv(
        profile,
        task_path=Path("/tasks/example"),
        run_id="s6-unit",
        evidence_root=Path("/evidence"),
        dry_run=True,
    )
    assert argv[0] == profile.aether_executable
    assert argv[1] == "run"
    assert "--allow-provider" in argv
    assert "--dry-run" in argv
    rendered = " ".join(argv)
    assert "harbor.cli" not in rendered
    assert "aether.harbor_agent" not in rendered


def test_s6_prepare_rejects_reserved_before_task_closure_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_path = tmp_path / "profile.json"
    profile = _profile_mapping()
    profile["candidate"]["python_executable"] = str(tmp_path / "python")
    profile["candidate"]["aether_executable"] = str(tmp_path / "aether")
    for executable in (profile["candidate"]["python_executable"], profile["candidate"]["aether_executable"]):
        p = Path(executable); p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8"); p.chmod(0o755)
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    board_path = tmp_path / "board.json"
    board_path.write_text(json.dumps({"tasks": [{"task_id": "reserved-row", "closure_sha256": "0" * 64, "file_count": 1}]}), encoding="utf-8")
    reserved_path = tmp_path / "reserved.json"
    reserved_path.write_text(json.dumps({"excluded_from_calibration_task_ids": ["reserved-row"]}), encoding="utf-8")
    task = tmp_path / "reserved-row"; task.mkdir()
    called = False
    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("closure probe must not run for a reserved task")
    monkeypatch.setattr(performance_run, "_candidate_closure", forbidden)
    with pytest.raises(performance_run.PerformanceRunError, match="reserved task"):
        performance_run.prepare_run(
            profile_path=profile_path,
            board_path=board_path,
            reserved_path=reserved_path,
            task_id="reserved-row",
            task_path=task,
            run_id="s6-reserved",
            evidence_root=tmp_path / "evidence",
            dry_run=True,
        )
    assert called is False


def test_s6_task_storage_metadata_is_normalized_without_semantic_guessing() -> None:
    assert performance_run._task_storage_bytes({"storage": 10240}) == (10 * 1024**3, "task.storage_integer_mb")
    assert performance_run._task_storage_bytes({"storage": "10G"}) == (10 * 1024**3, "task.storage_human")
    assert performance_run._task_storage_bytes({"storage": None}) == (
        performance_run.DEFAULT_TASK_STORAGE_BYTES, "fixed_missing_metadata_floor"
    )


def test_s6_host_storage_admission_rejects_before_child_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = {
        "status": "prepared",
        "argv": ["/bin/false"],
        "evidence_root": str(tmp_path / "evidence"),
        "run_id": "s6-low-disk",
        "dry_run": False,
        "task_storage_bytes": 10 * 1024**3,
        "task_storage_source": "unit",
    }
    usage = shutil._ntuple_diskusage(20 * 1024**3, 19 * 1024**3, 1 * 1024**3)
    monkeypatch.setattr(performance_run, "_docker_root_path", lambda: None)
    monkeypatch.setattr(performance_run.shutil, "disk_usage", lambda _path: usage)
    def forbidden(*_args, **_kwargs):
        raise AssertionError("child subprocess must not start after disk admission rejection")
    monkeypatch.setattr(performance_run.subprocess, "run", forbidden)
    result = performance_run.execute_prepared(prepared)
    assert result["status"] == "admission_rejected_host_storage"
    assert result["controller_returncode"] is None
    assert result["host_storage_admission"]["valid"] is False
    assert result["host_storage_admission"]["required_free_bytes"] == 12 * 1024**3
    assert result["child_custody"]["valid"] is False


def test_s6_adjudication_never_trades_correctness_for_efficiency() -> None:
    control = summarize_arm("control", [{
        "task_id": "paired-task", "valid": True, "official_reward": 1.0, "verifier_false_clean": 0,
        "verifier_false_block": 0, "first_submit_good": 1, "actions": 12,
        "provider_turns": 13, "input_tokens": 100000, "output_tokens": 4000, "latency_s": 100.0,
    }])
    cheap_wrong = summarize_arm("cheap-wrong", [{
        "task_id": "paired-task", "valid": True, "official_reward": 0.0, "verifier_false_clean": 0,
        "verifier_false_block": 0, "first_submit_good": 1, "actions": 2,
        "provider_turns": 2, "input_tokens": 1000, "output_tokens": 100, "latency_s": 5.0,
    }])
    decision = compare(control, cheap_wrong)
    assert decision == {"decision": "KEEP_CONTROL", "reason": "whole_task_official_passes"}


def test_s6_sentinel_manifest_points_to_real_pytest_surfaces() -> None:
    manifest = json.loads((PERF / "SENTINELS_V1.json").read_text(encoding="utf-8"))
    assert len(manifest["sentinels"]) == 18
    ids = [row["id"] for row in manifest["sentinels"]]
    assert len(ids) == len(set(ids))
    assert {
        "binary_read_evidence_strength_fail_closed",
        "corrected_submission_retry_not_poisoned",
        "host_storage_admission_before_child_launch",
        "foreground_provider_http_cancellation",
        "harbor_timeout_worker_drain",
        "harbor_detached_descendant_subreaper_binding",
        "previous_response_not_found_bounded_reanchor",
    } <= set(ids)
    for sentinel in manifest["sentinels"]:
        assert sentinel["pytest_nodes"]
        for node in sentinel["pytest_nodes"]:
            rel = node.split("::", 1)[0]
            assert (ROOT / rel).is_file(), node


# --- deterministic production sentinels that did not previously have one exact node ---

def test_s6_sentinel_harbor_detached_descendant_subreaper_binding() -> None:
    helper = ROOT / "aether" / "harbor_subreaper_linux_x86_64"
    source = (ROOT / "aether" / "harbor_executor.py").read_text(encoding="utf-8")
    helper_sha = hashlib.sha256(helper.read_bytes()).hexdigest()
    assert helper_sha == "b5c68b3f11f357ba14fed69d82a192d7a2853e05f059af32a0415da0301dc2f4"
    assert helper.stat().st_size == 878520
    assert helper_sha in source
    assert "harbor:subreaper_descendant_tree" in source
    assert "subreaper cleanup proof missing" in source
    assert "remote_descendant_tree_terminated" in source
    assert "harbor_subreaper_linux_x86_64" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")

def test_s6_sentinel_app_app_path_identity() -> None:
    # /app is the workspace root. A literal /app/app/X therefore maps to the
    # real workspace-relative app/X and must not be collapsed to X.
    assert normalize_relpath("/app/app/result.txt", "/app") == "app/result.txt"
    assert normalize_relpath("/app/result.txt", "/app") == "result.txt"


def test_s6_sentinel_mixed_result_is_not_collapsed_to_success() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-2:progress",
        step=2,
        kind="solver_progress_assessment",
        success=False,
        summary="mixed result",
        payload={
            "classification": "mixed_results_no_state_change",
            "progress_signals": ["new_evidence"],
        },
    ))
    decision = evaluate_submission_coherence(ledger, current_step=3)
    assert decision.allowed is False
    assert decision.reason_code == "mixed_action_result_without_recovery"


def test_s6_sentinel_primary_schema_has_one_action_slot() -> None:
    schema = pcr_primary_turn_schema()
    variants = schema["properties"]["turn"]["anyOf"]
    act_variants = [row for row in variants if row.get("properties", {}).get("kind", {}).get("enum") == ["act"]]
    assert act_variants
    for row in act_variants:
        assert row["required"] == ["kind", "action"]
        assert "action" in row["properties"]
        assert "actions" not in row["properties"]
        assert row.get("additionalProperties") is False



def test_s6_controller_exports_frozen_source_and_campaign_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv, *, text, capture_output, env, shell, check):
        del text, capture_output, shell, check
        captured["argv"] = list(argv)
        captured["env"] = dict(env)
        return __import__("subprocess").CompletedProcess(argv, 1, stdout="", stderr="synthetic")

    monkeypatch.setattr(performance_run.subprocess, "run", fake_run)
    prepared = {
        "status": "prepared",
        "argv": ["/bin/aether", "run", "/task"],
        "evidence_root": str(tmp_path / "evidence"),
        "run_id": "campaign-custody",
        "dry_run": True,
        "profile_id": "FRESH_POST_F4_V1",
        "candidate": {"source_commit": "a" * 40},
    }
    performance_run.execute_prepared(prepared)
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["AETHER_SOURCE_COMMIT"] == "a" * 40
    assert env["AETHER_CAMPAIGN_ID"] == "FRESH_POST_F4_V1"


def test_s6_adjudication_rejects_unpaired_task_sets() -> None:
    control = summarize_arm("control", [{"task_id": "a", "valid": True, "official_reward": 1.0}])
    challenger = summarize_arm("challenger", [{"task_id": "b", "valid": True, "official_reward": 1.0}])
    assert compare(control, challenger) == {
        "decision": "INVALID_COMPARISON",
        "reason": "paired arms must contain the same unique task IDs",
    }


def test_s6_profile_rejects_unknown_keys_and_duplicate_changed_controls() -> None:
    unknown = _profile_mapping()
    unknown["candidate"]["mystery"] = "x"
    with pytest.raises(ValueError, match="candidate keys invalid"):
        PerformanceProfile.from_mapping(unknown)
    duplicate = _profile_mapping()
    duplicate["treatment"]["changed_controls"] = ["x", "x"]
    with pytest.raises(ValueError, match="must be unique"):
        PerformanceProfile.from_mapping(duplicate)


def test_s6_child_launch_custody_fails_closed_on_package_drift() -> None:
    prepared = {
        "candidate": {
            "package_closure_sha256": "a" * 64,
            "model_profile_sha256": "b" * 64,
            "tool_schema_sha256": "c" * 64,
            "harbor_version": "0.20.0",
        },
        "task_closure_sha256": "d" * 64,
        "task_file_count": 3,
        "provider_calls_allowed": True,
        "max_attempts": 1,
        "max_retries": 0,
    }
    spec = {
        "package": {"closure_sha256": "e" * 64},
        "runtime": {"profile_sha256": "b" * 64, "tool_schema_sha256": "c" * 64},
        "harbor": {"version": "0.20.0"},
        "task": {"closure_sha256": "d" * 64, "file_count": 3},
        "provider": {"calls_allowed": True},
        "retry": {"max_attempts": 1, "max_retries": 0},
    }
    result = performance_run.verify_child_launch_spec(prepared, spec)
    assert result["valid"] is False
    assert any(row.startswith("package.closure_sha256:") for row in result["mismatches"])


def _write_s6_collector_fixture(tmp_path: Path, *, reward: float, aether_status: str = "completed", later_action: bool = False) -> Path:
    from evals.performance.collect import collect_completed_run
    del collect_completed_run
    evidence = tmp_path / "evidence"; run_id = "fixture-run"
    trial = evidence / run_id / "harbor" / run_id / "task__abc"
    agent = trial / "agent"; agent.mkdir(parents=True)
    receipts = [
        {"kind":"primary_action_result_index","success":True,"state_change":False,"payload":{}},
        {"kind":"solver_progress_assessment","success":True,"state_change":False,"payload":{"state_change_count":1}},
        {"kind":"primary_submission_claim","success":True,"state_change":False,"payload":{}},
    ]
    if later_action:
        receipts.append({"kind":"primary_action_result_index","success":True,"state_change":False,"payload":{}})
    run = {
        "status": aether_status, "step": 3, "blockers": [], "receipt_records": receipts,
        "run_metrics": {"submit_receipt_count":1,"repeated_command_count":0,"repeated_write_count":0,"solver_parse_error_count":0,"verifier_parse_error_count":0,"action_validation_error_count":0,"tool_schema_error_count":0},
        "runtime_identity":{"model_profile":{"solver_reasoning_effort":"low","verifier_reasoning_effort":"low"}},
        "model_call_telemetry":[
            {"role":"solver","status":"completed","response_id":"r1","pcr_continuity_request_previous_response_id":None,"pcr_continuity_prior_call_id_match_count":0,"pcr_continuity_current_boundary_function_output_match_count":0},
            {"role":"solver","status":"completed","response_id":"r2","pcr_continuity_request_previous_response_id":"r1","pcr_continuity_prior_call_id_match_count":1,"pcr_continuity_current_boundary_function_output_match_count":1},
        ],
    }
    x0 = {
        "status":"OBSERVED_NO_MODEL_FACING_BEHAVIOR_CHANGE",
        "provider":{"attempt_count":2,"failed_attempt_count":0,"compaction_event_count":0,"attempts":[
            {"status":"completed","role":"solver","response_id":"r1","reasoning_context_requested":"all_turns","reasoning_context_effective":"all_turns"},
            {"status":"completed","role":"verifier","response_id":"v1","reasoning_context_requested":"all_turns","reasoning_context_effective":"all_turns"},
        ],"fresh_reasoning_tokens":{"status":"reported","sum_if_all_reported":11},"cache_write_tokens":{"status":"reported","sum_if_all_reported":75},"latency_seconds":{"status":"reported","sum_if_all_reported":2.5}},
        "context":{"calls":[{"aggregate":{"utf8_bytes":100},"stable_prefix":{"utf8_bytes":80},"dynamic_or_volatile":{"utf8_bytes":20}}]},
        "receipts":{"equivalent_repeat_event_count":0},
    }
    (agent/"aether_run_record.json").write_text(json.dumps(run),encoding="utf-8")
    (agent/"aether_x0_observability.json").write_text(json.dumps(x0),encoding="utf-8")
    trial_result={"task_name":"fixture-task","started_at":"2026-09-02T00:00:00Z","finished_at":"2026-09-02T00:00:05Z","exception_info":None,"agent_result":{"n_input_tokens":1000,"n_cache_tokens":400,"n_output_tokens":50,"cost_usd":None},"verifier_result":{"rewards":{"reward":reward}}}
    (trial/"result.json").write_text(json.dumps(trial_result),encoding="utf-8")
    controller={"status":"executed_valid","run_id":run_id,"evidence_root":str(evidence),"task_id":"fixture-task","child_custody":{"valid":True}}
    cp=tmp_path/"controller.json"; cp.write_text(json.dumps(controller),encoding="utf-8")
    return cp


def test_s6_collector_extracts_typed_correctness_first_metrics(tmp_path: Path) -> None:
    from evals.performance.collect import collect_completed_run
    row=collect_completed_run(_write_s6_collector_fixture(tmp_path,reward=1.0))
    assert row["valid"] is True
    assert row["official_reward"] == 1.0
    assert row["verifier_false_clean"] == row["verifier_false_block"] == 0
    assert row["first_submit_good"] == 1
    assert row["actions"] == 1
    assert row["state_changing_actions"] == 1
    assert row["provider_turns"] == 2
    assert row["input_tokens"] == 1000 and row["cached_input_tokens"] == 400
    assert row["cache_write_tokens"] == 75 and row["cache_write_tokens_status"] == "reported"
    assert row["uncached_input_tokens"] == 600 and row["output_tokens"] == 50
    assert row["reasoning_tokens"] == 11 and row["provider_latency_s"] == 2.5
    assert row["latency_s"] == 5.0
    assert row["context"]["serialized_bytes"] == 100
    assert row["solver_previous_response_chain_intact"] is True
    assert row["tool_schema_bytes"] is None


def test_s6_collector_marks_false_clean_and_false_block_against_harbor(tmp_path: Path) -> None:
    from evals.performance.collect import collect_completed_run
    false_clean=collect_completed_run(_write_s6_collector_fixture(tmp_path/"a",reward=0.0,aether_status="completed"))
    false_block=collect_completed_run(_write_s6_collector_fixture(tmp_path/"b",reward=1.0,aether_status="solver_submit_stalemate"))
    assert false_clean["valid"] is True and false_clean["verifier_false_clean"] == 1
    assert false_block["valid"] is True and false_block["verifier_false_block"] == 1


def test_s6_collector_provider_failure_is_invalid_experiment(tmp_path: Path) -> None:
    from evals.performance.collect import collect_completed_run
    row=collect_completed_run(_write_s6_collector_fixture(tmp_path,reward=0.0,aether_status="provider_failure"))
    assert row["valid"] is False
    assert "aether_status_invalid:provider_failure" in row["invalid_reasons"]


def test_s6_custody_hash_binds_board_reserved_and_freshness() -> None:
    import hashlib
    custody=json.loads((PERF/"CALIBRATION_CUSTODY_V1.json").read_text(encoding="utf-8"))
    board_sha=hashlib.sha256((PERF/"CALIBRATION_BOARD_V1.json").read_bytes()).hexdigest()
    reserved_sha=hashlib.sha256((PERF/"RESERVED_BOARD_IDS_V1.json").read_bytes()).hexdigest()
    freshness_sha=hashlib.sha256((PERF/"HISTORICAL_FRESHNESS_CENSUS_V1.json").read_bytes()).hexdigest()
    assert custody["canonical_dry_run"]["board_file_sha256"] == board_sha
    assert custody["canonical_dry_run"]["reserved_file_sha256"] == reserved_sha
    assert custody["reserved"]["sha256"] == reserved_sha
    assert custody["historical_freshness"]["sha256"] == freshness_sha
    assert custody["historical_freshness"]["all_current_rows_fresh"] is True
    assert custody["fresh_export_verification"]["matched"] == custody["fresh_export_verification"]["total"] == 12
