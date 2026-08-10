from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.ledger import Receipt
from aether.persistent_capabilities import persistent_capability_contract
from aether.persistent_evidence import (
    PERSISTENT_COMPLETION_EVIDENCE_KINDS,
    PERSISTENT_PRIMARY_ACTION_RESULT_KINDS,
    is_persistent_completion_evidence,
    is_persistent_primary_action_result,
)
from aether.persistent_primary import persistent_primary_runtime_ir
from aether.runners.docker_runner import _resolve_certified_source_identity


_TERMINAL_ACTIONS = {
    "start_terminal_session",
    "terminal_send",
    "terminal_read",
    "terminal_wait",
    "terminal_interrupt",
    "terminal_close",
}
_TERMINAL_RECEIPTS = {
    "terminal_start",
    "terminal_send",
    "terminal_read",
    "terminal_wait",
    "terminal_interrupt",
    "terminal_close",
}


def _compiled(tmp_path):
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Interact with the task computer and inspect its resulting artifact.",
        workspace_root=str(tmp_path),
    )
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
    objective, eval_index = compiler.analyze_envmap(envmap)
    compiled = compiler.compile(
        persistent_primary_runtime_ir(envmap, eval_index),
        envmap,
        objective_graph=objective,
        eval_index=eval_index,
    )
    return envmap, compiled


def test_envmap_truthfully_advertises_terminal_and_artifact_history(tmp_path) -> None:
    envmap, compiled = _compiled(tmp_path)
    terminal = envmap.capabilities["persistent_terminal"]
    assert set(terminal.tool_names) == _TERMINAL_ACTIONS
    artifact = envmap.capabilities["artifact_inspection"]
    assert {"inspect_artifact", "inspect_diff", "query_artifact_history"} <= set(artifact.tool_names)

    contract = persistent_capability_contract(compiled)
    for action in _TERMINAL_ACTIONS:
        assert "persistent_terminal" in contract[action]
    assert "artifact_inspection" in contract["inspect_diff"]
    assert "artifact_inspection" in contract["query_artifact_history"]


def test_terminal_receipts_cross_primary_result_and_completion_evidence_boundary() -> None:
    assert _TERMINAL_RECEIPTS <= PERSISTENT_COMPLETION_EVIDENCE_KINDS
    assert _TERMINAL_RECEIPTS <= PERSISTENT_PRIMARY_ACTION_RESULT_KINDS
    for kind in sorted(_TERMINAL_RECEIPTS):
        receipt = Receipt(
            receipt_id=f"step-1:persistent-terminal:{kind}",
            step=1,
            kind=kind,
            success=True,
            summary=kind,
            payload={"session_id": "terminal:1"},
        )
        assert is_persistent_primary_action_result(receipt) is True
        assert is_persistent_completion_evidence(receipt) is True


def _observed(*, git_available: bool, clean: bool, commit: str = "b" * 40, tree: str = "c" * 40):
    return {
        "git_available": git_available,
        "clean": clean,
        "commit": commit if git_available else "",
        "tree": tree if git_available else "",
        "status": "" if clean else " M aether/example.py",
        "git_error": "git metadata unavailable" if not git_available else "",
        "source_manifest": {"aggregate_sha256": "a" * 64, "file_count": 3},
    }


def _certified(**overrides):
    row = {
        "commit": "b" * 40,
        "tree": "c" * 40,
        "clean": True,
        "custody_mode": "sealed_current_runtime_manifest_plus_execution_body",
        "current_runtime_manifest_sha256": "d" * 64,
        "current_runtime_aggregate_sha256": "e" * 64,
        "execution_body_manifest_sha256": "f" * 64,
        "execution_body_aggregate_sha256": "1" * 64,
        "source_manifest_aggregate_sha256": "a" * 64,
        "source_manifest_file_count": 3,
    }
    row.update(overrides)
    return row


def test_source_certification_defaults_fail_closed_without_git() -> None:
    observed = _observed(git_available=False, clean=False)
    assert _resolve_certified_source_identity(observed, None) == observed
    assert _resolve_certified_source_identity(observed, None)["clean"] is False


def test_source_certification_accepts_no_git_only_after_exact_manifest_match() -> None:
    observed = _observed(git_available=False, clean=False)
    resolved = _resolve_certified_source_identity(observed, _certified())
    assert resolved["clean"] is True
    assert resolved["commit"] == "b" * 40
    assert resolved["tree"] == "c" * 40
    assert resolved["identity_authority"] == "certified_external_binding_after_manifest_match"
    assert resolved["observed_source_identity"] == observed


def test_source_certification_rejects_manifest_mismatch_and_malformed_identity() -> None:
    observed = _observed(git_available=False, clean=False)
    with pytest.raises(ValueError, match="manifest does not match"):
        _resolve_certified_source_identity(
            observed,
            _certified(source_manifest_aggregate_sha256="9" * 64),
        )
    with pytest.raises(ValueError, match="40-hex"):
        _resolve_certified_source_identity(observed, _certified(commit="not-a-commit"))
    with pytest.raises(ValueError, match="current_runtime_manifest_sha256"):
        _resolve_certified_source_identity(observed, _certified(current_runtime_manifest_sha256="short"))


def test_source_certification_cannot_hide_dirty_or_mismatched_local_git() -> None:
    with pytest.raises(ValueError, match="dirty local Git"):
        _resolve_certified_source_identity(
            _observed(git_available=True, clean=False),
            _certified(),
        )
    with pytest.raises(ValueError, match="does not match local Git truth"):
        _resolve_certified_source_identity(
            _observed(git_available=True, clean=True, commit="8" * 40),
            _certified(),
        )


def test_source_certification_accepts_matching_clean_git_without_replacing_git_truth() -> None:
    observed = _observed(git_available=True, clean=True)
    resolved = _resolve_certified_source_identity(observed, _certified())
    assert resolved["clean"] is True
    assert resolved["git_available"] is True
    assert resolved["commit"] == observed["commit"]
    assert resolved["tree"] == observed["tree"]
    assert resolved["identity_authority"] == "clean_git_plus_certified_manifest_binding"
