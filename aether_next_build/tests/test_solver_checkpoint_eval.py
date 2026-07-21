from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


BUILD_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = BUILD_ROOT / "scripts" / "run_solver_checkpoint_eval.py"
CASES = BUILD_ROOT / "evals" / "solver_checkpoints.v1.json"


def test_solver_checkpoint_board_has_eight_distinct_causal_cases() -> None:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    cases = payload["cases"]
    ids = [case["id"] for case in cases]
    assert len(cases) == 8
    assert len(ids) == len(set(ids))
    assert payload["rules"]["production_model_hooks_required"] is True
    assert payload["rules"]["strict_parser_required"] is True
    assert payload["rules"]["one_causal_action_required"] is True
    for case in cases:
        assert case["official_archetypes"]
        assert case["task_prompt"]
        assert case["context"]
        assert case["expected"]["turn_kind"] in {"act", "submit_outcome"}


def test_solver_checkpoint_runner_defaults_to_plan_only(tmp_path: Path) -> None:
    out = tmp_path / "plan"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(out)],
        cwd=BUILD_ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["model_execution_requested"] is False
    assert len(plan["case_ids"]) == 8
    assert (out / "FINALIZED.json").is_file()
    assert not (out / "cases").exists()


def test_solver_checkpoint_runner_requires_deterministic_pass_for_models(tmp_path: Path) -> None:
    out = tmp_path / "blocked"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--allow-model", "--output-dir", str(out)],
        cwd=BUILD_ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
    )
    assert proc.returncode != 0
    assert "--deterministic-summary is required" in proc.stderr
    assert not (out / "FINALIZED.json").exists()


def _load_runner_module():
    spec = importlib.util.spec_from_file_location("solver_checkpoint_eval", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_checkpoint_compiles_against_production_action_schema() -> None:
    module = _load_runner_module()
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        compiled = module._compiled(case)
        assert compiled.action_schema
        assert compiled.task_prompt == case["task_prompt"]


def test_checkpoint_score_separates_optional_audit_commitment_from_protocol() -> None:
    module = _load_runner_module()
    from aether_next.runtime_ir import ActionRequest, SolverTurn

    turn = SolverTurn(
        kind="act",
        summary="inspect the file",
        actions=(ActionRequest(
            action_id="read-1",
            kind="read_file",
            capability_id="filesystem",
            arguments={"path": "config.json"},
            intent="",
            expected_observation="",
            if_fail_next="",
        ),),
        evidence_gap="",
    )
    score = module._score_turn(turn, {
        "turn_kind": "act",
        "allowed_action_kinds": ["read_file"],
        "argument_equals": {"path": "config.json"},
    })

    assert score["passed"] is True
    assert score["advisory_findings"]
