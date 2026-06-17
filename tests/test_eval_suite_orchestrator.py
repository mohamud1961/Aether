from __future__ import annotations

import json
from pathlib import Path

import yaml

from tools.eval_suite_orchestrator import queue_bootstrap
from tools.eval_suite_orchestrator.finish_pipeline import (
    enqueue_next_finish_phase,
    parse_review_text,
    semantic_repair_targets,
)
from tools.eval_suite_orchestrator.graph import build_graph
from tools.eval_suite_orchestrator.queue_bootstrap import build_queue
from tools.eval_suite_orchestrator.state_schema import OrchestratorState, RunConfig
from tools.eval_suite_orchestrator.validators import validate_family_outputs


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _base_registry() -> dict:
    return {"schema_version": "v1", "families": {"demo_family": {"status": "planned", "seeds": {}}}}


def _base_state(tmp_path: Path) -> tuple[RunConfig, OrchestratorState]:
    build_status = tmp_path / "build_status.json"
    family_registry = tmp_path / "family_registry.yaml"
    _write(build_status, {"active_workers": [], "updated_at": "2026-01-01T00:00:00Z"})
    _write_yaml(family_registry, _base_registry())
    config = RunConfig(
        backend="dry_run",
        dry_run=True,
        one_job=True,
        state_path=str(tmp_path / "state.json"),
        event_log_path=str(tmp_path / "events.jsonl"),
    )
    state = OrchestratorState(
        queue=[
            {
                "job_id": "job_demo",
                "job_type": "family_seed_build",
                "family_id": "demo_family",
                "status": "queued",
                "attempt_count": 0,
                "input_paths": [],
                "allowed_write_scopes": ["tracking/collab/eval_suite_v1_build/families/demo_family"],
                "output_paths": [],
                "command_metadata": {},
                "timestamps": {},
                "failure_reason": None,
                "next_action": "launch_worker",
            }
        ],
        build_status_path=str(build_status),
        family_registry_path=str(family_registry),
        artifact_index_path=str(tmp_path / "artifact_index.json"),
    )
    return config, state


def test_graph_runs_dry_run_and_advances_queue(tmp_path: Path) -> None:
    config, state = _base_state(tmp_path)
    graph = build_graph()
    result = graph.invoke(
        {
            "run_config": config.to_dict(),
            "orchestrator_state": state.to_dict(),
            "loop_continue": True,
            "pre_snapshot": {},
        }
    )
    out = result["orchestrator_state"]
    assert out["processed_jobs"] == 1
    assert out["stop_reason"] == "one_job_complete"
    assert out["queue"][0]["status"] in {"blocked", "completed_structural"}


def test_no_worker_launches_occur_in_dry_run(tmp_path: Path) -> None:
    config, state = _base_state(tmp_path)
    result = build_graph().invoke(
        {
            "run_config": config.to_dict(),
            "orchestrator_state": state.to_dict(),
            "loop_continue": True,
            "pre_snapshot": {},
        }
    )
    job = result["orchestrator_state"]["history"][0]
    assert job["command_metadata"]["launched"] is False
    assert job["command_metadata"]["backend"] == "dry_run"


def test_stale_active_workers_are_cleared(tmp_path: Path) -> None:
    config, state = _base_state(tmp_path)
    config.clear_stale_active_workers = True
    _write(Path(state.build_status_path), {"active_workers": [{"family_id": "x"}], "updated_at": "old"})
    result = build_graph().invoke(
        {
            "run_config": config.to_dict(),
            "orchestrator_state": state.to_dict(),
            "loop_continue": True,
            "pre_snapshot": {},
        }
    )
    payload = json.loads(Path(state.build_status_path).read_text(encoding="utf-8"))
    assert payload["active_workers"] == []
    assert payload["stale_workers"][0]["status"] == "stale_terminated_process"
    assert result["orchestrator_state"]["processed_jobs"] == 1


def test_validator_detects_missing_family_artifacts(tmp_path: Path) -> None:
    registry_path = tmp_path / "family_registry.yaml"
    _write_yaml(
        registry_path,
        {
            "families": {
                "demo_family": {
                    "seeds": {
                        "seed1": {
                            "paths": {
                                "seed_root": "tracking/collab/eval_suite_v1_build/families/demo_family/seeds/seed1",
                                "task_pack": "tracking/collab/eval_suite_v1_build/families/demo_family/seeds/seed1/task_pack.json",
                                "trace_lens": "tracking/collab/eval_suite_v1_build/families/demo_family/seeds/seed1/trace_lens/eval_contract_trace_lens.yaml",
                                "bypass_exploit": "tracking/collab/eval_suite_v1_build/families/demo_family/seeds/seed1/bypass_exploit.py",
                            }
                        }
                    }
                }
            }
        },
    )
    (
        tmp_path
        / "tracking/collab/eval_suite_v1_build/families/demo_family/seeds/seed1"
    ).mkdir(parents=True)
    errors = validate_family_outputs(family_id="demo_family", family_registry_path=registry_path, repo_root=tmp_path)
    assert errors
    assert any("missing" in err for err in errors)
    assert any("solver_pack/README.md" in err for err in errors)
    assert any("grader/timeout_policy.json" in err for err in errors)


def test_force_worker_overrides_existing_partial_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(queue_bootstrap, "REPO_ROOT", tmp_path)
    registry_path = tmp_path / "family_registry.yaml"
    resume_queue_path = tmp_path / "resume_queue.json"
    family_root = tmp_path / "tracking/collab/eval_suite_v1_build/families/demo_family"
    _write_yaml(
        registry_path,
        {
            "families": {
                "demo_family": {
                    "write_scope": str(family_root.relative_to(tmp_path)),
                    "seeds": {},
                }
            }
        },
    )
    _write(resume_queue_path, {"resume_order": [{"family_id": "demo_family"}]})
    jobs = build_queue(
        family_registry_path=registry_path,
        resume_queue_path=resume_queue_path,
        family_filter="demo_family",
        force_worker=True,
    )
    assert jobs[0].next_action == "launch_worker"


def test_full_queue_skips_completed_families(tmp_path: Path) -> None:
    registry_path = tmp_path / "family_registry.yaml"
    resume_queue_path = tmp_path / "resume_queue.json"
    _write_yaml(
        registry_path,
        {
            "families": {
                "done_family": {
                    "status": "completed_structural_validation_pending_semantic_admission",
                    "seeds": {},
                },
                "todo_family": {"status": "resume_pending", "seeds": {}},
            }
        },
    )
    _write(
        resume_queue_path,
        {"resume_order": [{"family_id": "done_family"}, {"family_id": "todo_family"}]},
    )
    jobs = build_queue(
        family_registry_path=registry_path,
        resume_queue_path=resume_queue_path,
    )
    assert [job.family_id for job in jobs] == ["todo_family"]


def test_runner_recursion_limit_formula_has_room_for_full_queue() -> None:
    queue_size = 8
    limit = max(100, 8 * max(1, queue_size) + 20)
    assert limit >= 84


def test_finish_pipeline_blocks_on_unresolved_structural_failures() -> None:
    from tools.eval_suite_orchestrator.finish_pipeline import enqueue_next_finish_phase

    config = RunConfig(pipeline="finish", max_repair_rounds=1)
    state = OrchestratorState(
        pipeline="finish",
        pipeline_phase="strict_seed_structure",
        repair_round=1,
        build_root_path="/private/tmp/eval-suite-finish-test",
        history=[
            {
                "job_id": "strict_demo",
                "job_type": "strict_seed_structure",
                "family_id": "demo_family",
                "status": "blocked",
                "attempt_count": 1,
                "input_paths": [],
                "allowed_write_scopes": [],
                "output_paths": [],
                "command_metadata": {"pipeline_phase": "strict_seed_structure", "repair_round": 1},
                "timestamps": {},
                "failure_reason": "missing files",
                "next_action": "blocked",
                "max_attempts": 1,
            }
        ],
    )
    assert enqueue_next_finish_phase(state, config) is False
    assert state.stop_reason == "finish_pipeline_blocked_structural"
    assert state.pipeline_phase == "blocked"


def test_finish_pipeline_blocks_on_unresolved_semantic_repairs() -> None:
    from tools.eval_suite_orchestrator.finish_pipeline import enqueue_next_finish_phase

    config = RunConfig(pipeline="finish", max_repair_rounds=1)
    state = OrchestratorState(
        pipeline="finish",
        pipeline_phase="semantic_admission_review",
        review_repair_round=1,
        build_root_path="/private/tmp/eval-suite-finish-test",
        review_results={
            "seeds": {
                "demo_family": {
                    "seeds": {
                        "seed1": {"status": "repair_required", "findings": ["bad grader"]}
                    }
                }
            }
        },
    )
    assert enqueue_next_finish_phase(state, config) is False
    assert state.stop_reason == "finish_pipeline_blocked_semantic"
    assert state.pipeline_phase == "blocked"


def test_repair_blocked_queue_only_includes_blocked_families(tmp_path: Path) -> None:
    registry_path = tmp_path / "family_registry.yaml"
    resume_queue_path = tmp_path / "resume_queue.json"
    _write_yaml(
        registry_path,
        {
            "families": {
                "blocked_family": {"status": "blocked", "seeds": {}},
                "done_family": {
                    "status": "completed_structural_validation_pending_semantic_admission",
                    "seeds": {},
                },
            }
        },
    )
    _write(
        resume_queue_path,
        {"resume_order": [{"family_id": "blocked_family"}, {"family_id": "done_family"}]},
    )
    jobs = build_queue(
        family_registry_path=registry_path,
        resume_queue_path=resume_queue_path,
        repair_blocked=True,
        force_worker=True,
    )
    assert [job.family_id for job in jobs] == ["blocked_family"]
    assert jobs[0].job_type == "family_repair"
    assert jobs[0].next_action == "launch_worker"


def test_repair_queue_includes_completed_family_with_strict_validation_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(queue_bootstrap, "REPO_ROOT", tmp_path)
    registry_path = tmp_path / "family_registry.yaml"
    resume_queue_path = tmp_path / "resume_queue.json"
    seed_root = "tracking/collab/eval_suite_v1_build/families/incomplete_family/seeds/seed1"
    _write_yaml(
        registry_path,
        {
            "families": {
                "incomplete_family": {
                    "status": "completed_structural_validation_pending_semantic_admission",
                    "seeds": {"seed1": {"paths": {"seed_root": seed_root}}},
                },
                "clean_family": {
                    "status": "completed_structural_validation_pending_semantic_admission",
                    "seeds": {},
                },
            }
        },
    )
    (tmp_path / seed_root).mkdir(parents=True, exist_ok=True)
    _write(
        resume_queue_path,
        {"resume_order": [{"family_id": "incomplete_family"}, {"family_id": "clean_family"}]},
    )
    jobs = build_queue(
        family_registry_path=registry_path,
        resume_queue_path=resume_queue_path,
        repair_blocked=True,
        force_worker=True,
    )
    assert [job.family_id for job in jobs] == ["incomplete_family"]


def _finish_state(tmp_path: Path, families: list[str]) -> tuple[RunConfig, OrchestratorState]:
    build_root = tmp_path / "eval_suite_v1_build"
    _write(build_root / "build_status.json", {"active_workers": []})
    _write(build_root / "artifact_index.json", {"families": {}})
    _write_yaml(
        build_root / "family_registry.yaml",
        {"families": {family_id: {"status": "planned", "seeds": {}} for family_id in families}},
    )
    config = RunConfig(
        backend="dry_run",
        dry_run=True,
        pipeline="finish",
        build_root=str(build_root),
        state_path=str(build_root / "_orchestrator/state.json"),
        event_log_path=str(build_root / "_orchestrator/events.jsonl"),
        max_repair_rounds=1,
    )
    state = OrchestratorState(
        queue=[],
        build_status_path=str(build_root / "build_status.json"),
        family_registry_path=str(build_root / "family_registry.yaml"),
        artifact_index_path=str(build_root / "artifact_index.json"),
        build_root_path=str(build_root),
        pipeline="finish",
        pipeline_phase="seed_build",
    )
    return config, state


def test_finish_pipeline_enqueues_strict_structure_for_all_families(tmp_path: Path) -> None:
    config, state = _finish_state(tmp_path, ["family_a", "family_b"])
    assert enqueue_next_finish_phase(state, config) is True
    assert state.pipeline_phase == "strict_seed_structure"
    assert [row["job_type"] for row in state.queue] == ["strict_seed_structure", "strict_seed_structure"]
    assert {row["family_id"] for row in state.queue} == {"family_a", "family_b"}
    assert all(row["next_action"] == "validate_existing_output" for row in state.queue)


def test_finish_pipeline_repair_then_review_routing(tmp_path: Path) -> None:
    config, state = _finish_state(tmp_path, ["family_a", "family_b"])
    state.pipeline_phase = "strict_seed_structure"
    state.history = [
        {
            "job_id": "strict_a",
            "job_type": "strict_seed_structure",
            "family_id": "family_a",
            "status": "blocked",
            "command_metadata": {"pipeline_phase": "strict_seed_structure", "repair_round": 0},
        },
        {
            "job_id": "strict_b",
            "job_type": "strict_seed_structure",
            "family_id": "family_b",
            "status": "completed_structural",
            "command_metadata": {"pipeline_phase": "strict_seed_structure", "repair_round": 0},
        },
    ]
    assert enqueue_next_finish_phase(state, config) is True
    assert state.pipeline_phase == "structural_repair"
    assert state.repair_round == 1
    assert [row["family_id"] for row in state.queue] == ["family_a"]

    state.queue = []
    assert enqueue_next_finish_phase(state, config) is True
    assert state.pipeline_phase == "strict_seed_structure"
    assert {row["family_id"] for row in state.queue} == {"family_a", "family_b"}

    state.queue = []
    state.history.extend(
        [
            {
                "job_id": "strict_a_r1",
                "job_type": "strict_seed_structure",
                "family_id": "family_a",
                "status": "completed_structural",
                "command_metadata": {"pipeline_phase": "strict_seed_structure", "repair_round": 1},
            },
            {
                "job_id": "strict_b_r1",
                "job_type": "strict_seed_structure",
                "family_id": "family_b",
                "status": "completed_structural",
                "command_metadata": {"pipeline_phase": "strict_seed_structure", "repair_round": 1},
            },
        ]
    )
    assert enqueue_next_finish_phase(state, config) is True
    assert state.pipeline_phase == "semantic_admission_review"
    assert [row["job_type"] for row in state.queue] == ["semantic_admission_review", "semantic_admission_review"]


def test_review_parser_accepts_yaml_and_semantic_repair_targets(tmp_path: Path) -> None:
    parsed = parse_review_text(
        """
```yaml
family_id: family_a
seeds:
  seed_good:
    status: admitted
  seed_fix:
    status: repair_required
    findings:
      - grader timeout is missing
```
"""
    )
    assert parsed["seeds"]["seed_good"]["status"] == "admitted"
    assert parsed["seeds"]["seed_fix"]["status"] == "repair_required"

    config, state = _finish_state(tmp_path, ["family_a"])
    state.review_results = {"seeds": {"family_a": parsed}}
    targets, finding_paths = semantic_repair_targets(state)
    assert targets == ["family_a"]
    assert "family_a" in finding_paths
    assert (Path(finding_paths["family_a"]) if Path(finding_paths["family_a"]).is_absolute() else Path("/Users/mohamud/Downloads/harnesseng") / finding_paths["family_a"]).exists()
