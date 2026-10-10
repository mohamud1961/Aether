from __future__ import annotations

from typing import Any

from aether.completion_signal import completion_signal_context
from aether.ledger import ExecutionLedger, Receipt

COMPLETE = {"workspace_mutation_detection_status": "complete", "mutation_detection_status": "coarse"}


def _index(ledger: ExecutionLedger, step: int, rid: str, kind: str) -> None:
    ledger.record(Receipt(
        receipt_id=f"step-{step}:idx", step=step, kind="primary_action_result_index",
        success=True, summary="idx",
        payload={"action_kind": kind, "outcome_receipt_ids": [rid]},
    ))


def run(ledger: ExecutionLedger, step: int, command: str, *, code: int = 0,
        changed: tuple[str, ...] = (), stdout: str = "", delta: dict[str, Any] | None = None,
        integrity_risk: str = "") -> None:
    rid = f"step-{step}:cmd"
    state_delta = dict(COMPLETE if delta is None else delta)
    state_delta.setdefault("content_changed_paths", list(changed))
    ledger.record(Receipt(
        receipt_id=rid, step=step, kind="run_command", success=code == 0,
        summary=f"exit={code}", state_change=bool(changed),
        payload={"command": command, "exit_code": code, "stdout": stdout,
                 "modified_paths": tuple(changed), "state_delta": state_delta,
                 **({"verification_integrity_risk": integrity_risk} if integrity_risk else {})},
    ))
    _index(ledger, step, rid, "run_command")


def write(
    ledger: ExecutionLedger, step: int, path: str, *, created: bool = False,
) -> None:
    rid = f"step-{step}:write"
    payload: dict[str, Any] = {"path": path, "modified_paths": (path,)}
    if not created:
        payload["before_bytes"] = 1
        payload["before_content_hash"] = "existing"
    ledger.record(Receipt(
        receipt_id=rid, step=step, kind="write_file", success=True, summary="wrote",
        state_change=True, payload=payload,
    ))
    _index(ledger, step, rid, "write_file")


def read(ledger: ExecutionLedger, step: int, path: str) -> None:
    rid = f"step-{step}:read"
    ledger.record(Receipt(
        receipt_id=rid, step=step, kind="read_file", success=True, summary="read",
        payload={"path": path},
    ))
    _index(ledger, step, rid, "read_file")


def _edit(ledger: ExecutionLedger):
    return (completion_signal_context(ledger, mode="verification_oracle_guard_v1") or {}).get(
        "verification_edit_observation"
    )


def test_edited_check_after_failure_is_reported_factually() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", code=1, stdout="[FAIL] x")
    write(ledger, 2, "verify.py")
    run(ledger, 3, "python3 verify.py", stdout="ALL PASS")
    signal = completion_signal_context(ledger, mode="verification_oracle_guard_v1")
    assert signal is not None and signal["mode"] == "verification_oracle_guard_v1"
    edit = signal["verification_edit_observation"]
    assert edit["verification_files_changed"] == ["verify.py"]
    assert edit["other_files_changed"] == []
    assert edit["failed_receipt_ids"] == ["step-1:cmd"]
    assert "no other file changed" in edit["observation"]
    for veto_word in ("incomplete", "do not finish", "must not finish"):
        assert veto_word not in str(signal).lower()


def test_shell_edit_attributed_through_complete_snapshot_delta() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", code=1)
    run(ledger, 2, "sed -i s/FAIL/OK/ verify.py", changed=("verify.py",))
    run(ledger, 3, "python3 verify.py")
    assert _edit(ledger)["verification_files_changed"] == ["verify.py"]


def test_v2_and_control_are_byte_identical_to_before() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", code=1)
    write(ledger, 2, "verify.py")
    run(ledger, 3, "python3 verify.py")
    assert completion_signal_context(ledger, mode="control") is None
    v2 = completion_signal_context(ledger, mode="verification_authority_v2")
    assert v2 is not None and "verification_edit_observation" not in v2
    guard = dict(completion_signal_context(ledger, mode="verification_oracle_guard_v1"))
    guard.pop("verification_edit_observation")
    guard["mode"] = "verification_authority_v2"
    assert guard == v2


def test_production_file_also_changed_gives_no_observation() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", code=1)
    write(ledger, 2, "src/solution.py")
    write(ledger, 3, "verify.py")
    run(ledger, 4, "python3 verify.py")
    assert _edit(ledger) is None


def test_production_change_in_the_passing_command_itself_blocks_observation() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", code=1)
    run(ledger, 2, "sed -i s/a/b/ verify.py && python3 verify.py && sed -i s/c/d/ app.py",
        changed=("verify.py", "app.py"))
    assert _edit(ledger) is None


def test_never_failing_check_gives_no_observation() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py")
    write(ledger, 2, "verify.py")
    run(ledger, 3, "python3 verify.py")
    assert _edit(ledger) is None


def test_failure_marker_with_zero_exit_counts_as_reported_failure() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", stdout="Traceback (most recent call last):\n  boom")
    write(ledger, 2, "check_all.py")
    run(ledger, 3, "python3 verify.py")
    assert _edit(ledger) is not None




def test_masked_pipeline_verifier_failure_is_detected_only_with_integrity_risk() -> None:
    ledger = ExecutionLedger()
    write(ledger, 0, "verify_processor.py", created=True)
    run(
        ledger, 1, "python3 verify_processor.py 2>&1 | tail -40",
        stdout="ok first\nFAIL bridge_value_once: bad\n2 FAILURES\n",
        integrity_risk="verification_exit_status_masked_by_pipeline",
    )
    run(
        ledger, 2,
        "python3 - <<'EOF'\np='verify_processor.py'\nopen(p,'a').write('# fixed\\n')\nEOF\npython3 verify_processor.py; echo EXIT=$?",
        changed=("verify_processor.py",), stdout="ALL CHECKS PASSED\nEXIT=0\n",
    )
    run(ledger, 3, "python3 verify_processor.py", stdout="ALL CHECKS PASSED\n")
    edit = _edit(ledger)
    assert edit is not None
    assert edit["verification_files_changed"] == ["verify_processor.py"]
    assert edit["failed_receipt_ids"] == ["step-1:cmd"]

    control = ExecutionLedger()
    write(control, 0, "verify_processor.py", created=True)
    run(
        control, 1, "python3 verify_processor.py 2>&1 | tail -40",
        stdout="ok first\nFAIL bridge_value_once: bad\n2 FAILURES\n",
    )
    run(control, 2, "sed -i s/a/b/ verify_processor.py", changed=("verify_processor.py",))
    run(control, 3, "python3 verify_processor.py", stdout="ALL CHECKS PASSED\n")
    assert _edit(control) is None


def test_masked_pipeline_integrity_risk_does_not_make_passing_output_a_failure() -> None:
    ledger = ExecutionLedger()
    write(ledger, 0, "verify_processor.py", created=True)
    run(
        ledger, 1, "python3 verify_processor.py 2>&1 | tail -40",
        stdout="ALL CHECKS PASSED\n",
        integrity_risk="verification_exit_status_masked_by_pipeline",
    )
    write(ledger, 2, "verify_processor.py")
    run(ledger, 3, "python3 verify_processor.py", stdout="ALL CHECKS PASSED\n")
    assert _edit(ledger) is None


def test_test_named_file_edit_counts_but_conftest_does_not() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 -m pytest -q", code=1)
    write(ledger, 2, "tests/test_a.py")
    run(ledger, 3, "python3 -m pytest -q")
    assert _edit(ledger)["verification_files_changed"] == ["tests/test_a.py"]
    other = ExecutionLedger()
    run(other, 1, "python3 -m pytest -q", code=1)
    write(other, 2, "conftest.py")
    run(other, 3, "python3 -m pytest -q")
    assert _edit(other) is None


def test_unattributable_shell_effects_are_not_guessed() -> None:
    truncated = ExecutionLedger()
    run(truncated, 1, "python3 verify.py", code=1)
    run(truncated, 2, "sed -i s/a/b/ verify.py", delta={"workspace_mutation_detection_status": "truncated"})
    run(truncated, 3, "python3 verify.py")
    assert _edit(truncated) is None
    no_delta = ExecutionLedger()
    run(no_delta, 1, "python3 verify.py", code=1)
    run(no_delta, 2, "sed -i s/a/b/ verify.py", delta={})
    run(no_delta, 3, "python3 verify.py")
    assert _edit(no_delta) is None


def test_reads_between_failure_and_pass_do_not_block() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", code=1)
    read(ledger, 2, "src/solution.py")
    write(ledger, 3, "verify.py")
    run(ledger, 4, "python3 verify.py")
    assert _edit(ledger) is not None


def test_unrelated_failing_check_is_not_the_oracle() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 other_check.py", code=1)
    write(ledger, 2, "verify.py")
    run(ledger, 3, "python3 verify.py")
    assert _edit(ledger) is None


def test_earlier_production_edit_inside_failure_streak_blocks() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python3 verify.py", code=1)
    write(ledger, 2, "src/solution.py")
    run(ledger, 3, "python3 verify.py", code=1)
    write(ledger, 4, "verify.py")
    run(ledger, 5, "python3 verify.py")
    assert _edit(ledger) is None


def test_solver_created_arbitrary_named_oracle_is_detected_without_filename_heuristic() -> None:
    ledger = ExecutionLedger()
    write(ledger, 0, "repro_bugs.py", created=True)
    run(
        ledger, 1, "python repro_bugs.py", code=1,
        stdout="PASS first invariant\nTraceback (most recent call last):\n  boom",
    )
    write(ledger, 2, "repro_bugs.py")
    run(
        ledger, 3, "python repro_bugs.py",
        stdout="PASS first invariant\nFAILURES: none",
    )
    signal = completion_signal_context(
        ledger, mode="verification_oracle_guard_v1"
    )
    assert signal is not None
    edit = signal["verification_edit_observation"]
    assert edit["verification_files_changed"] == ["repro_bugs.py"]
    assert edit["failed_receipt_ids"] == ["step-1:cmd"]


def test_preexisting_arbitrary_named_script_is_not_promoted_to_verification() -> None:
    ledger = ExecutionLedger()
    run(ledger, 1, "python worker.py", code=1)
    write(ledger, 2, "worker.py")
    run(ledger, 3, "python worker.py")
    assert completion_signal_context(
        ledger, mode="verification_oracle_guard_v1"
    ) is None


def test_solver_created_script_plus_production_change_is_not_oracle_only() -> None:
    ledger = ExecutionLedger()
    write(ledger, 0, "probe.py", created=True)
    run(ledger, 1, "python probe.py", code=1)
    write(ledger, 2, "app.py")
    write(ledger, 3, "probe.py")
    run(ledger, 4, "python probe.py")
    assert completion_signal_context(
        ledger, mode="verification_oracle_guard_v1"
    ) is None


def test_masked_pipeline_failures_none_is_not_treated_as_failure() -> None:
    ledger = ExecutionLedger()
    write(ledger, 0, "repro_bugs.py", created=True)
    run(
        ledger, 1, "python repro_bugs.py 2>&1 | tail -40",
        stdout="PASS first invariant\nFAILURES: none\n0 FAILURES\n",
        integrity_risk="verification_exit_status_masked_by_pipeline",
    )
    write(ledger, 2, "repro_bugs.py")
    run(ledger, 3, "python repro_bugs.py", stdout="PASS first invariant\nFAILURES: none\n")
    assert _edit(ledger) is None
