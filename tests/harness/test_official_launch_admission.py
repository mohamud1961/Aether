from __future__ import annotations

import json
from pathlib import Path

import pytest

from aether.official_launch_admission import (
    OfficialLaunchAdmission,
    OfficialLaunchAdmissionError,
    identity_sha256,
)


def _identity() -> dict[str, object]:
    return {
        "schema_version": "aether.official_launch_identity.v1",
        "package_closure_sha256": "a" * 64,
        "task_closure_sha256": "b" * 64,
        "runtime_profile_sha256": "c" * 64,
        "provider_route_sha256": "d" * 64,
    }


def _state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / "admission-state"
    monkeypatch.setenv("AETHER_OFFICIAL_LAUNCH_STATE_DIR", str(state))
    return state


def test_process_lock_refuses_concurrent_identity_even_without_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _state(tmp_path, monkeypatch)
    first = OfficialLaunchAdmission.acquire(_identity(), run_id="one", evidence_root="/evidence/one")
    try:
        # A missing record must not turn a held process lease into an opening
        # for another dispatch.
        first.record_path.unlink()
        with pytest.raises(OfficialLaunchAdmissionError, match="duplicate official launch admission is active"):
            OfficialLaunchAdmission.acquire(_identity(), run_id="two", evidence_root="/evidence/two")
    finally:
        first.release()


def test_durable_terminal_record_refuses_later_run_with_new_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path, monkeypatch)
    identity = _identity()
    first = OfficialLaunchAdmission.acquire(identity, run_id="one", evidence_root="/evidence/one")
    first.mark_dispatch_started()
    first.finalize(status="completed", exit_code=0)

    with pytest.raises(OfficialLaunchAdmissionError, match="already durably recorded"):
        OfficialLaunchAdmission.acquire(identity, run_id="two", evidence_root="/evidence/two")
    records = list(state.glob("launch-*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["identity_sha256"] == identity_sha256(identity)
    assert record["status"] == "completed"
    assert record["dispatch_started"] is True
    assert record["run_id"] == "one"


def test_pre_dispatch_abandon_allows_retry_after_safe_setup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _state(tmp_path, monkeypatch)
    identity = _identity()
    first = OfficialLaunchAdmission.acquire(identity, run_id="one", evidence_root="/evidence/one")
    first.abandon_before_dispatch()
    assert list((tmp_path / "admission-state").glob("launch-*.json")) == []

    second = OfficialLaunchAdmission.acquire(identity, run_id="two", evidence_root="/evidence/two")
    second.abandon_before_dispatch()


def test_corrupt_durable_record_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state(tmp_path, monkeypatch)
    identity = _identity()
    first = OfficialLaunchAdmission.acquire(identity, run_id="one", evidence_root="/evidence/one")
    record_path = first.record_path
    first.release()
    record_path.write_text("{corrupt\n", encoding="utf-8")

    with pytest.raises(OfficialLaunchAdmissionError, match="state is invalid"):
        OfficialLaunchAdmission.acquire(identity, run_id="two", evidence_root="/evidence/two")


def test_symlinked_state_directory_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = tmp_path / "real-state"
    real.mkdir()
    alias = tmp_path / "alias-state"
    alias.symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("AETHER_OFFICIAL_LAUNCH_STATE_DIR", str(alias))

    with pytest.raises(OfficialLaunchAdmissionError, match="contains a symlink"):
        OfficialLaunchAdmission.acquire(_identity(), run_id="one", evidence_root="/evidence/one")


def test_identity_lock_is_local_to_the_selected_state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Record the cross-host/state-root limitation instead of implying global custody.

    The production lock is deliberately durable and fail-closed within one
    selected state root.  A different host or state root has no way to observe
    that record, so a campaign manifest must pin one dispatch owner and preserve
    that root across teardown.  This counterexample prevents tests from
    silently treating the local fcntl lock as a global duplicate-launch guard.
    """
    identity = _identity()
    first_root = tmp_path / "first-state"
    second_root = tmp_path / "second-state"
    monkeypatch.setenv("AETHER_OFFICIAL_LAUNCH_STATE_DIR", str(first_root))
    first = OfficialLaunchAdmission.acquire(identity, run_id="one", evidence_root="/evidence/one")
    try:
        monkeypatch.setenv("AETHER_OFFICIAL_LAUNCH_STATE_DIR", str(second_root))
        second = OfficialLaunchAdmission.acquire(identity, run_id="two", evidence_root="/evidence/two")
        second.abandon_before_dispatch()
    finally:
        first.abandon_before_dispatch()
    assert list(first_root.glob("launch-*.json")) == []
    assert list(second_root.glob("launch-*.json")) == []
