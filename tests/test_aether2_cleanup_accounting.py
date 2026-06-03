from __future__ import annotations

from runner.aether2.cleanup_accounting import (
    account_for_cleanup,
    classify_unowned_state,
)


def test_already_exited_resource_is_accounted_without_stop_attempt() -> None:
    accounting = account_for_cleanup(
        [{"resource_id": "job-1", "resource_kind": "job"}],
        observed_state={"job-1": {"alive": False}},
    )
    counts = accounting.counts
    assert counts["already_exited"] == 1
    assert accounting.attempted_count == 0
    assert accounting.unexplained_count == 0
    assert accounting.is_fully_attributable is True


def test_stopped_by_run_is_recorded_when_stop_succeeds() -> None:
    accounting = account_for_cleanup(
        [{"resource_id": "proc-1", "resource_kind": "process"}],
        observed_state={"proc-1": {"alive": True}},
        stop_results={"proc-1": {"attempted": True, "alive_after": False}},
    )
    assert accounting.counts["stopped_by_run"] == 1
    assert accounting.attempted_count == 1
    assert accounting.unexplained_count == 0
    assert accounting.is_fully_attributable is True


def test_stop_failed_is_unexplained_and_surfaced() -> None:
    accounting = account_for_cleanup(
        [{"resource_id": "proc-2", "resource_kind": "process"}],
        observed_state={"proc-2": {"alive": True}},
        stop_results={"proc-2": {"attempted": True, "alive_after": True}},
    )
    assert accounting.counts["stop_failed"] == 1
    assert accounting.attempted_count == 1
    assert accounting.unexplained_count == 1
    assert accounting.is_fully_attributable is False


def test_owned_live_resource_with_no_stop_attempt_is_unknown_state() -> None:
    accounting = account_for_cleanup(
        [{"resource_id": "session-1", "resource_kind": "session"}],
        observed_state={"session-1": {"alive": True}},
        stop_results={},
    )
    assert accounting.counts["unknown_state"] == 1
    assert accounting.unexplained_count == 1
    assert accounting.is_fully_attributable is False


def test_owned_resource_with_no_observed_state_is_unknown_not_silently_dropped() -> None:
    accounting = account_for_cleanup(
        [{"resource_id": "job-missing", "resource_kind": "job"}],
        observed_state={},
    )
    assert accounting.counts["unknown_state"] == 1
    record = accounting.records[0]
    assert record.resource_id == "job-missing"
    assert "no observed pre-cleanup state" in record.detail


def test_as_dict_round_trips_records_and_summary() -> None:
    accounting = account_for_cleanup(
        [
            {"resource_id": "job-1", "resource_kind": "job"},
            {"resource_id": "proc-1", "resource_kind": "process"},
        ],
        observed_state={
            "job-1": {"alive": False},
            "proc-1": {"alive": True},
        },
        stop_results={"proc-1": {"attempted": True, "alive_after": False}},
    )
    payload = accounting.as_dict()
    assert payload["counts"]["already_exited"] == 1
    assert payload["counts"]["stopped_by_run"] == 1
    assert payload["attempted_count"] == 1
    assert payload["unexplained_count"] == 0
    assert payload["is_fully_attributable"] is True
    assert len(payload["records"]) == 2


def test_classify_unowned_state_never_marks_unowned_resources_as_cleaned_up() -> None:
    leftover = classify_unowned_state(
        owned_resource_ids=["job-1"],
        observed_live_resource_ids=["job-1", "job-2-not-ours"],
    )
    assert leftover == ("job-2-not-ours",)

    # Even though job-2-not-ours is live, accounting for owned resources only
    # never reports it as part of this run's cleanup.
    accounting = account_for_cleanup(
        [{"resource_id": "job-1", "resource_kind": "job"}],
        observed_state={"job-1": {"alive": False}, "job-2-not-ours": {"alive": True}},
    )
    resource_ids = {record.resource_id for record in accounting.records}
    assert "job-2-not-ours" not in resource_ids


def test_missing_resource_id_is_unknown_state_and_does_not_crash() -> None:
    accounting = account_for_cleanup(
        [{"resource_kind": "job"}],
        observed_state={},
    )
    assert accounting.counts["unknown_state"] == 1
    assert accounting.records[0].resource_id == ""
