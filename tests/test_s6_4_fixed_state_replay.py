from __future__ import annotations

from pathlib import Path
import json

import pytest

from evals.performance.s6_4_fixed_state_replay import (
    FixedStateReplayError,
    envmap_from_packet,
    filtered_replay_ledger,
    primary_replay_actions,
    prepare_case,
)


def _record() -> dict:
    packet = {
        "raw_user_task": "Create /app/out.txt",
        "task_contract_identity": "",
        "stable_envmap": {
            "facts": {
                "workspace_root": "/app",
                "visible_files": ["in.txt"],
                "visible_dirs": [],
                "capabilities": {
                    "filesystem": {
                        "capability_id": "filesystem", "summary": "files", "available": True,
                        "cost_hint": "cheap", "tool_names": ["read_file", "write_file"],
                    },
                    "shell": {
                        "capability_id": "shell", "summary": "shell", "available": True,
                        "cost_hint": "cheap", "tool_names": ["run_command"],
                    },
                },
            },
        },
    }
    return {
        "receipt_records": [
            {"receipt_id":"r0","step":0,"kind":"primary_action_result_index","success":True,"summary":"", "payload":{"action_kind":"read_file","outcome_receipt_ids":["read"]}},
            {"receipt_id":"read","step":0,"kind":"read_file","success":True,"summary":"", "payload":{"content":"x"}},
            {"receipt_id":"r1","step":1,"kind":"primary_action_result_index","success":True,"summary":"", "payload":{"action_kind":"write_file","outcome_receipt_ids":["write"]}},
            {"receipt_id":"write","step":1,"kind":"write_file","success":True,"summary":"", "state_change":True, "payload":{"artifact_paths":["out.txt"],"content":"ok","content_sha256":"2689367b205c16ce32ed4200942b8b1e154d4a4f062869a922c986d5bb5d7f1b"}},
            {"receipt_id":"r2","step":2,"kind":"primary_action_result_index","success":True,"summary":"", "payload":{"action_kind":"run_command","outcome_receipt_ids":["cmd"]}},
            {"receipt_id":"cmd","step":2,"kind":"run_command","success":False,"summary":"", "payload":{"command":"false","exit_code":1,"timed_out":False}},
            {"receipt_id":"submit-old","step":2,"kind":"primary_submission_claim","success":True,"summary":"old","payload":{}},
            {"receipt_id":"old-verifier","step":2,"kind":"model_verifier_result","success":False,"summary":"needs repair","payload":{}},
            {"receipt_id":"submit","step":3,"kind":"primary_submission_claim","success":True,"summary":"new","payload":{}},
            {"receipt_id":"packet","step":3,"kind":"model_verifier_packet","success":True,"summary":"", "payload":{"packet":packet}},
        ]
    }


def test_replay_plan_uses_only_mutating_primary_outcomes() -> None:
    rows = primary_replay_actions(_record(), through_step=3)
    assert [x["kind"] for x in rows] == ["write_file", "run_command"]
    assert rows[0]["path"] == "out.txt"
    assert rows[1]["expected_exit_code"] == 1


def test_replay_ledger_removes_prior_verifier_semantics_and_old_submissions() -> None:
    ledger = filtered_replay_ledger(_record(), packet_step=3)
    kinds = [r.kind for r in ledger.all_receipts()]
    ids = [r.receipt_id for r in ledger.all_receipts()]
    assert "model_verifier_result" not in kinds
    assert "submit-old" not in ids
    assert "submit" in ids
    assert "cmd" in ids


def test_envmap_is_derived_from_exact_packet_facts() -> None:
    packet = _record()["receipt_records"][-1]["payload"]["packet"]
    env = envmap_from_packet(packet)
    assert env.task_prompt == "Create /app/out.txt"
    assert env.workspace_root == "/app"
    assert set(env.capabilities) == {"filesystem", "shell"}
    assert env.visible_files == ("in.txt",)


def test_unsupported_stateful_action_fails_closed() -> None:
    row = _record()
    row["receipt_records"].insert(0, {
        "receipt_id":"xidx","step":0,"kind":"primary_action_result_index","success":True,"summary":"",
        "payload":{"action_kind":"launch_process","outcome_receipt_ids":["xout"]},
    })
    row["receipt_records"].insert(1, {
        "receipt_id":"xout","step":0,"kind":"launch_process","success":True,"summary":"","payload":{},
    })
    with pytest.raises(FixedStateReplayError, match="unsupported historical Primary outcome"):
        primary_replay_actions(row, through_step=3)


def test_prepare_never_reads_tests_or_solution_content(tmp_path: Path) -> None:
    task = tmp_path / "task"
    task.mkdir()
    (task / "tests").mkdir(); (task / "solution").mkdir()
    (task / "tests" / "SECRET").write_text("grader secret")
    (task / "solution" / "SECRET").write_text("solution secret")
    (task / "task.toml").write_text('[environment]\ndocker_image="example/image:tag"\ncpus=1\nmemory_mb=512\n')
    record_path = tmp_path / "record.json"
    record_path.write_text(json.dumps(_record()))
    prepared = prepare_case(run_record_path=record_path, task_dir=task)
    assert prepared["grader_content_loaded"] is False
    assert prepared["solution_content_loaded"] is False
    assert prepared["exact_historical_packet_reused"] is True
    assert prepared["replay_action_count"] == 2


def test_frozen_case_contains_no_grader_or_solution_payload(tmp_path: Path) -> None:
    from evals.performance.s6_4_fixed_state_replay import freeze_case_bundle, validate_frozen_case
    task = tmp_path / "task2"; task.mkdir()
    (task / "tests").mkdir(); (task / "solution").mkdir()
    (task / "tests" / "hidden.txt").write_text("HIDDEN_GRADER_SENTINEL")
    (task / "solution" / "solve.sh").write_text("HIDDEN_SOLUTION_SENTINEL")
    (task / "task.toml").write_text('[environment]\ndocker_image="example/image:tag"\n')
    rp = tmp_path / "record2.json"; rp.write_text(json.dumps(_record()))
    case = freeze_case_bundle(
        run_record_path=rp, task_dir=task, case_id="c", adjudication_label="known_defective",
    )
    raw = json.dumps(case, sort_keys=True)
    assert "HIDDEN_GRADER_SENTINEL" not in raw
    assert "HIDDEN_SOLUTION_SENTINEL" not in raw
    assert case["adjudication_label"] == "known_defective"
    assert validate_frozen_case(case)["case_id"] == "c"


def test_frozen_case_rejects_verifier_semantic_history(tmp_path: Path) -> None:
    from evals.performance.s6_4_fixed_state_replay import CASE_SCHEMA, validate_frozen_case
    packet = _record()["receipt_records"][-1]["payload"]["packet"]
    from evals.performance.s6_4_fixed_state_replay import _canonical_sha256, envmap_from_packet
    from aether.pcr_runtime import build_pcr_runtime
    contract = build_pcr_runtime(envmap_from_packet(packet)).compiled.task_contract_identity
    case = {
        "schema_version": CASE_SCHEMA, "case_id":"x", "packet":packet,
        "packet_sha256":_canonical_sha256(packet), "actions":[],
        "replay_actions_sha256":_canonical_sha256([]), "replay_action_count":0,
        "task_contract_identity":contract,
        "ledger_receipts":[{"receipt_id":"v","step":1,"kind":"model_verifier_result","success":True,"summary":"","payload":{}}],
    }
    with pytest.raises(FixedStateReplayError, match="historical Verifier semantics"):
        validate_frozen_case(case)
