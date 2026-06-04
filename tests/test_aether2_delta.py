from __future__ import annotations

import importlib
from types import SimpleNamespace

DELTA = importlib.import_module("harness.aether2.traces.delta")
DELTA_COMPAT = importlib.import_module("runner.aether2.delta")

assert DELTA_COMPAT is DELTA

from harness.aether2.traces.delta import (
    DeltaReport,
    FileDelta,
    build_evidence_ledger,
    diff,
    ensure_stated_requirements,
    mark_blockers_candidate_resolved,
    mark_blockers_exhausted,
    record_check_results,
    record_observation_evidence,
    record_terminal_claim,
    record_verifier_report,
    serialize_evidence_ledger,
    should_suppress_verifier_call,
    snapshot,
    with_evidence_ledger,
)


def _blocker_by_requirement(ledger, requirement: str):
    matches = [item for item in ledger["blockers"] if item["requirement"] == requirement]
    assert matches
    assert len(matches) == 1
    return matches[0]


def _blocker_by_id(ledger, blocker_id: str):
    matches = [item for item in ledger["blockers"] if item["blocker_id"] == blocker_id]
    assert matches
    assert len(matches) == 1
    return matches[0]


def test_snapshot_and_diff_detect_file_modification(tmp_path):
    target = tmp_path / "artifact.txt"
    target.write_text("alpha\n", encoding="utf-8")

    before = snapshot(tmp_path)

    target.write_text("beta\n", encoding="utf-8")

    after = snapshot(tmp_path)
    report = diff(before, after)

    assert isinstance(report, DeltaReport)
    assert report.files_changed == [
        FileDelta(
            path="artifact.txt",
            hash_before=before.files["artifact.txt"],
            hash_after=after.files["artifact.txt"],
            change_type="modified",
        )
    ]
    assert report.modified_paths == ("artifact.txt",)
    assert report.added_paths == ()
    assert report.deleted_paths == ()
    assert report.is_empty is False


def test_snapshot_and_diff_report_no_op_as_empty(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "note.txt").write_text("steady state\n", encoding="utf-8")

    before = snapshot(tmp_path)
    after = snapshot(tmp_path)
    report = diff(before, after)

    assert report.files_changed == []
    assert report.added_paths == ()
    assert report.modified_paths == ()
    assert report.deleted_paths == ()
    assert report.is_empty is True


def test_evidence_ledger_requires_visible_evidence_and_verifier_can_prove(tmp_path):
    ledger = build_evidence_ledger(["write final artifact"])
    ledger = record_observation_evidence(
        ledger,
        requirement="write final artifact",
        tool_name="run_command",
        step=2,
        exit_code=0,
        raw_log_path=str(tmp_path / "raw.log"),
    )

    requirement = ledger["requirements"][0]
    assert requirement["status"] == "unproven"
    assert requirement["evidence_refs"] == []
    assert requirement["evidence_strength"] == "none"

    ledger = record_observation_evidence(
        ledger,
        requirement="write final artifact",
        tool_name="write_file",
        step=3,
        exit_code=0,
        raw_log_path=str(tmp_path / "raw.log"),
        artifact_paths=["artifacts/out.txt"],
        note="wrote artifacts/out.txt",
    )
    requirement = ledger["requirements"][0]
    assert requirement["status"] == "partial"
    assert requirement["evidence_strength"] == "weak"
    assert any("artifacts=artifacts/out.txt" in ref for ref in requirement["evidence_refs"])
    assert requirement["next_required_evidence"] == [
        "direct visible proof for requirement: write final artifact"
    ]

    unresolved = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="write final artifact",
                    verdict="unverifiable",
                    evidence="artifact path alone is not enough to prove the final result",
                ),
            ),
            reason_codes=("needs_semantic_confirmation",),
            summary="needs stronger proof",
        ),
        verifier_ref="verifier:step=4",
    )
    blocker = _blocker_by_requirement(unresolved, "write final artifact")
    assert blocker["status"] == "active"
    assert blocker["created_step"] == 4
    assert blocker["last_updated_step"] == 4
    assert blocker["age_steps"] == 0
    assert blocker["verdict"] == "unproven"
    assert blocker["reason_codes"] == ["needs_semantic_confirmation"]
    assert blocker["requirement_id"].startswith("req_")
    assert blocker["blocker_id"].startswith("blk_")

    resolved = record_verifier_report(
        unresolved,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="write final artifact",
                    verdict="satisfied",
                    evidence="artifact contains the requested final result",
                ),
            ),
            reason_codes=(),
            summary="verified",
        ),
        verifier_ref="verifier:step=5",
    )
    requirement = resolved["requirements"][0]
    blocker = _blocker_by_id(resolved, blocker["blocker_id"])
    assert requirement["status"] == "proven"
    assert requirement["evidence_strength"] == "strong"
    assert requirement["verifier_blockers"] == []
    assert requirement["next_required_evidence"] == []
    assert blocker["status"] == "resolved"
    assert blocker["age_steps"] == 1
    assert blocker["resolution_evidence"] == "artifact contains the requested final result"
    assert "verdict=proven" in blocker["verifier_confirmation"]
    assert any("verdict=proven" in ref for ref in requirement["evidence_refs"])


def test_evidence_ledger_tracks_failed_checks_blockers_and_failure_families(tmp_path):
    ledger = ensure_stated_requirements(None, ["keep service available"])
    failed_check = SimpleNamespace(
        command="curl -fsS http://127.0.0.1:8000/healthz",
        exit_code=7,
        stdout="",
        stderr="connection refused",
        cwd="/workspace",
        duration_sec=0.2,
        timed_out=False,
        error_kind=None,
        error_reason_code=None,
    )

    ledger = record_check_results(
        ledger,
        requirement="keep service available",
        check_results=[failed_check, failed_check],
        step=7,
        raw_log_path=str(tmp_path / "check.log"),
    )
    ledger = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="keep service available",
                    verdict="unverifiable",
                    evidence="service state could not be confirmed from visible artifacts",
                ),
            ),
            reason_codes=("needs_live_service_probe",),
            summary="needs stronger live evidence",
        ),
        verifier_ref="verifier:step=8",
    )

    requirement = ledger["requirements"][0]
    blocker = _blocker_by_requirement(ledger, "keep service available")
    assert requirement["status"] == "contradicted"
    assert requirement["evidence_strength"] == "strong"
    assert requirement["failed_checks"] == [
        "cmd=curl -fsS http://127.0.0.1:8000/healthz exit=7"
    ]
    assert requirement["disproven_assumptions"] == [
        "declared check would verify requirement: curl -fsS http://127.0.0.1:8000/healthz"
    ]
    assert requirement["verifier_blockers"] == [
        "service state could not be confirmed from visible artifacts"
    ]
    assert requirement["next_required_evidence"] == [
        "repair and rerun a visible check for: keep service available",
        "direct visible evidence for: keep service available",
    ]
    assert blocker["status"] == "active"
    assert blocker["created_step"] == 8
    assert blocker["rejected_evidence_refs"]
    assert blocker["required_next_evidence"] == ["direct visible evidence for: keep service available"]
    families = {item["family"]: item for item in ledger["repeated_failure_families"]}
    assert families["check_exit_nonzero"]["count"] == 2
    assert families["verifier_unverifiable"]["count"] == 1
    assert families["verifier_reason:needs_live_service_probe"]["count"] == 1


def test_verifier_parse_and_schema_findings_become_persistent_blockers():
    ledger = record_verifier_report(
        build_evidence_ledger(["collect final answer"]),
        report=SimpleNamespace(
            requirements=(),
            parse_error="verifier returned malformed JSON",
            schema_errors=("missing requirements field",),
            summary="verifier output invalid",
        ),
        verifier_ref="verifier:step=11",
    )

    integrity_entries = [item for item in ledger["requirements"] if item["requirement"] == "verifier report integrity"]
    assert len(integrity_entries) == 1
    assert integrity_entries[0]["status"] == "contradicted"

    blockers = [item for item in ledger["blockers"] if item["requirement"] == "verifier report integrity"]
    assert len(blockers) == 2
    assert {item["status"] for item in blockers} == {"active"}
    assert {tuple(item["reason_codes"]) for item in blockers} == {
        ("verifier_parse_failure",),
        ("verifier_schema_failure",),
    }
    assert {item["created_step"] for item in blockers} == {11}
    assert {item["last_updated_step"] for item in blockers} == {11}
    assert {item["age_steps"] for item in blockers} == {0}
    assert any(item["insufficiency_reason"] == "verifier returned malformed JSON" for item in blockers)
    assert any(item["insufficiency_reason"] == "missing requirements field" for item in blockers)

    families = {item["family"]: item["count"] for item in ledger["repeated_failure_families"]}
    assert families["verifier_parse_failure"] == 1
    assert families["verifier_schema_failure"] == 1


def test_unrelated_deltas_do_not_mark_candidate_resolved_and_suppress_redundant_verifier_calls(tmp_path):
    ledger = build_evidence_ledger(["write final artifact"])
    ledger = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="write final artifact",
                    verdict="unverifiable",
                    evidence="final artifact contents were not visible",
                ),
            ),
            reason_codes=("needs_visible_artifact",),
            summary="not enough proof",
        ),
        verifier_ref="verifier:step=2",
    )
    blocker = _blocker_by_requirement(ledger, "write final artifact")

    assert should_suppress_verifier_call(ledger, requirement="write final artifact") is True
    assert (
        should_suppress_verifier_call(
            ledger,
            requirement="write final artifact",
            relevant_evidence_refs=["tool=write_file step=3 artifacts=notes/debug.txt note=updated debug notes"],
        )
        is True
    )

    unchanged = mark_blockers_candidate_resolved(
        ledger,
        step=3,
        requirement="write final artifact",
        relevant_evidence_refs=["tool=write_file step=3 artifacts=notes/debug.txt note=updated debug notes"],
    )
    assert _blocker_by_id(unchanged, blocker["blocker_id"])["status"] == "active"

    relevant = record_observation_evidence(
        ledger,
        requirement="write final artifact",
        tool_name="write_file",
        step=4,
        exit_code=0,
        raw_log_path=str(tmp_path / "raw.log"),
        artifact_paths=["artifacts/final.txt"],
        note="rewrote final artifact with the requested result",
    )
    assert should_suppress_verifier_call(relevant, requirement="write final artifact") is False


def test_relevant_new_evidence_can_mark_candidate_resolved_and_only_verifier_confirms_resolution(tmp_path):
    ledger = build_evidence_ledger(["write final artifact"])
    ledger = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="write final artifact",
                    verdict="unverifiable",
                    evidence="artifact exists but the final result is still not visible",
                ),
            ),
            reason_codes=("needs_visible_artifact",),
            summary="needs direct proof",
        ),
        verifier_ref="verifier:step=2",
    )
    blocker = _blocker_by_requirement(ledger, "write final artifact")
    first_version = blocker["evidence_version_last_evaluated"]

    ledger = record_observation_evidence(
        ledger,
        requirement="write final artifact",
        tool_name="write_file",
        step=5,
        exit_code=0,
        raw_log_path=str(tmp_path / "raw.log"),
        artifact_paths=["artifacts/final.txt"],
        note="final artifact now contains the requested result",
    )
    ledger = mark_blockers_candidate_resolved(ledger, step=5, requirement="write final artifact")
    blocker = _blocker_by_id(ledger, blocker["blocker_id"])
    assert blocker["status"] == "candidate_resolved"
    assert blocker["age_steps"] == 3
    assert blocker["evidence_version_last_evaluated"] != first_version
    assert blocker["resolution_evidence"] == ""
    assert blocker["verifier_confirmation"] == ""

    ledger = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="write final artifact",
                    verdict="satisfied",
                    evidence="artifact now visibly contains the requested final result",
                ),
            ),
            reason_codes=(),
            summary="verified",
        ),
        verifier_ref="verifier:step=6",
    )
    blocker = _blocker_by_id(ledger, blocker["blocker_id"])
    assert blocker["status"] == "resolved"
    assert blocker["age_steps"] == 4
    assert blocker["resolution_evidence"] == "artifact now visibly contains the requested final result"


def test_repeated_failed_candidate_resolution_can_become_exhausted():
    ledger = build_evidence_ledger(["keep service available"])
    ledger = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="keep service available",
                    verdict="unverifiable",
                    evidence="service state is still not visible from artifacts",
                ),
            ),
            reason_codes=("needs_live_service_probe",),
            summary="needs a live check",
        ),
        verifier_ref="verifier:step=1",
    )
    blocker = _blocker_by_requirement(ledger, "keep service available")

    ledger = mark_blockers_candidate_resolved(
        ledger,
        step=2,
        requirement="keep service available",
        relevant_failed_checks=["cmd=curl -fsS http://127.0.0.1:8000/healthz exit=0"],
    )
    blocker = _blocker_by_id(ledger, blocker["blocker_id"])
    assert blocker["status"] == "candidate_resolved"

    ledger = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="keep service available",
                    verdict="unverifiable",
                    evidence="service state is still not visible from artifacts",
                ),
            ),
            reason_codes=("needs_live_service_probe",),
            summary="still needs a live check",
        ),
        verifier_ref="verifier:step=3",
        exhaustion_round_limit=1,
    )
    blocker = _blocker_by_id(ledger, blocker["blocker_id"])
    assert blocker["status"] == "exhausted"
    assert blocker["candidate_resolution_attempts"] == 1
    assert blocker["age_steps"] == 2

    refreshed = mark_blockers_candidate_resolved(
        ledger,
        step=4,
        requirement="keep service available",
        relevant_failed_checks=["cmd=python -m smoke_probe exit=0 note=service health snapshot now visible"],
    )
    blocker = _blocker_by_id(refreshed, blocker["blocker_id"])
    assert blocker["status"] == "candidate_resolved"

    exhausted_again = mark_blockers_exhausted(
        refreshed,
        step=5,
        requirement="keep service available",
        exhaustion_round_limit=1,
    )
    blocker = _blocker_by_id(exhausted_again, blocker["blocker_id"])
    assert blocker["status"] == "exhausted"


def test_blockers_survive_compaction_with_deterministic_serialization():
    ledger = ensure_stated_requirements(
        {
            "requirements": [
                {"requirement": "b requirement", "status": "partial"},
                {"requirement": "a requirement", "status": "unproven"},
            ],
            "blockers": [
                {
                    "requirement": "b requirement",
                    "requirement_id": "req_manual_b",
                    "verdict": "unverifiable",
                    "reason_codes": ["beta"],
                    "insufficiency_reason": "beta blocker",
                    "required_next_evidence": ["collect beta proof"],
                    "blocker_id": "blk_b",
                    "created_step": 5,
                    "last_updated_step": 7,
                    "status": "active",
                    "evidence_version_last_evaluated": "bbb",
                },
                {
                    "requirement": "a requirement",
                    "requirement_id": "req_manual_a",
                    "verdict": "unsatisfied",
                    "reason_codes": ["alpha"],
                    "insufficiency_reason": "alpha blocker",
                    "required_next_evidence": ["collect alpha proof"],
                    "blocker_id": "blk_a",
                    "created_step": 1,
                    "last_updated_step": 2,
                    "status": "active",
                    "evidence_version_last_evaluated": "aaa",
                },
            ],
        },
        ["a requirement", "b requirement"],
    )

    serial_a = serialize_evidence_ledger(ledger)
    serial_b = serialize_evidence_ledger(
        {
            "blockers": list(reversed(ledger["blockers"])),
            "requirements": list(reversed(ledger["requirements"])),
            "repeated_failure_families": [],
        }
    )

    assert serial_a == serial_b
    assert [item["requirement"] for item in ledger["requirements"]] == ["a requirement", "b requirement"]
    assert [item["blocker_id"] for item in ledger["blockers"]] == ["blk_a", "blk_b"]


def test_with_evidence_ledger_attaches_compact_serializable_state(tmp_path):
    before = snapshot(tmp_path)
    ledger = build_evidence_ledger(["finish task"])
    ledger = record_observation_evidence(
        ledger,
        requirement="finish task",
        tool_name="write_file",
        step=1,
        exit_code=0,
        raw_log_path=str(tmp_path / "raw.log"),
        artifact_paths=["result.txt"],
        note="wrote result",
    )

    after = with_evidence_ledger(before, ledger)

    assert after.evidence_ledger["version"] == 1
    assert after.evidence_ledger["requirements"][0]["requirement"] == "finish task"


def test_circular_same_method_task_done_does_not_resolve_blocker(tmp_path):
    """W5.3 homolog: a circular/same-method re-`task_done` (no new independent
    evidence -- just the model re-asserting completion via the same method
    that was already rejected) must NOT move a blocker candidate->resolved.
    Only relevant NEW evidence resolves it.
    """

    ledger = build_evidence_ledger(["produce correct final report"])
    ledger = record_verifier_report(
        ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="produce correct final report",
                    verdict="unverifiable",
                    evidence="claim re-read its own just-written output; no independent check was run",
                ),
            ),
            reason_codes=("needs_independent_evidence",),
            summary="self-readback is not independent evidence",
        ),
        verifier_ref="verifier:step=2",
    )
    blocker = _blocker_by_requirement(ledger, "produce correct final report")
    first_version = blocker["evidence_version_last_evaluated"]

    # Model re-asserts task_done via the same self-readback method, with no
    # new artifact paths or checks -- a circular re-claim.
    ledger = record_terminal_claim(
        ledger,
        claim={"summary": "Re-read output.txt and confirmed it still says done.", "requirement": "produce correct final report"},
        outcome="task_done",
        step=3,
        raw_log_path=str(tmp_path / "raw.log"),
    )

    unchanged = mark_blockers_candidate_resolved(
        ledger,
        step=3,
        requirement="produce correct final report",
    )
    blocker = _blocker_by_id(unchanged, blocker["blocker_id"])
    assert blocker["status"] == "active"
    assert blocker["evidence_version_last_evaluated"] == first_version

    # Now genuinely new, relevant evidence (a fresh artifact write) arrives.
    relevant = record_observation_evidence(
        unchanged,
        requirement="produce correct final report",
        tool_name="write_file",
        step=4,
        exit_code=0,
        raw_log_path=str(tmp_path / "raw2.log"),
        artifact_paths=["output/final_report.txt"],
        note="wrote final report after independent recomputation",
    )
    resolved = mark_blockers_candidate_resolved(
        relevant,
        step=4,
        requirement="produce correct final report",
    )
    blocker = _blocker_by_id(resolved, blocker["blocker_id"])
    assert blocker["status"] == "candidate_resolved"
    assert blocker["evidence_version_last_evaluated"] != first_version
