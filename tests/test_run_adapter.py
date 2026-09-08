"""Production run-adapter tests for the PCR-only Aether runtime."""
from __future__ import annotations

import json
import os
import tempfile
import threading


from aether.run_adapter import _build_runtime_identity, run_task
from aether.run_cancellation import RunCancellationRequested


class _OneWriteSolver:
    def __call__(self, messages, *, max_output_tokens=8000):
        del messages, max_output_tokens
        return json.dumps({
            "kind": "act",
            "action": {
                "kind": "write_file",
                "arguments": {"path": "out.txt", "content": "hello"},
            },
        })


class _ForbiddenVerifier:
    def __call__(self, messages, *, max_output_tokens=8000):
        del messages, max_output_tokens
        raise AssertionError("one-action incomplete run must not invoke verifier")


def _run_one_action() -> tuple[dict[str, object], str]:
    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        with open(os.path.join(task_dir, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("PCR adapter test")
        record = run_task(
            task_dir=task_dir,
            instruction_text="Create out.txt containing hello.",
            solver_model=_OneWriteSolver(),
            verifier_model=_ForbiddenVerifier(),
            workspace_root=workspace,
            max_steps=1,
            runtime_identity={
                "task_id": "adapter-test",
                "run_id": "adapter-run",
                "primary_agent_id": "adapter-primary",
                "source_commit": "a" * 40,
                "runtime_manifest_sha256": "b" * 64,
            },
        )
        exists = os.path.isfile(os.path.join(workspace, "out.txt"))
    assert exists
    return record, workspace


def test_run_task_has_one_production_runtime_mode_and_no_architect_role() -> None:
    record, _ = _run_one_action()
    assert record["runtime_mode"] == "pcr_v0"
    assert record["status"] == "incomplete"
    roles = [row["model_role"] for row in record["model_interface_manifests"]]
    assert roles == ["solver"]
    assert all("architect" not in role.lower() for role in roles)


def test_run_task_preserves_lossless_receipts_and_compact_summary() -> None:
    record, _ = _run_one_action()
    records = record["receipt_records"]
    summary = record["receipt_summary"]
    assert records and summary
    assert len(records) == len(summary)
    by_id = {row["receipt_id"]: row for row in records}
    for row in summary:
        full = by_id[row["receipt_id"]]
        assert row["kind"] == full["kind"]
        assert row["success"] == full["success"]
        assert "payload" in full
        assert "payload" not in row


def test_runtime_identity_is_stable_when_supplied_and_truthful_when_missing() -> None:
    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        supplied = {
            "task_id": "task-fixed",
            "run_id": "run-fixed",
            "primary_agent_id": "primary-fixed",
            "source_commit": "c" * 40,
            "runtime_manifest_sha256": "d" * 64,
            "budgets": {"agent_timeout_sec": 900.0},
        }
        first = _build_runtime_identity(
            task_dir=task_dir,
            instruction_text="raw task",
            workspace_root=workspace,
            environment_id="env-fixed",
            max_steps=12,
            supplied=supplied,
        )
        second = _build_runtime_identity(
            task_dir=task_dir,
            instruction_text="raw task",
            workspace_root=workspace,
            environment_id="env-fixed",
            max_steps=12,
            supplied=first,
        )
        assert first == second
        assert first["source_custody_complete"] is True
        assert first["budgets"] == {
            "agent_timeout_sec": 900.0,
            "max_kernel_steps": 12,
        }

        missing = _build_runtime_identity(
            task_dir=task_dir,
            instruction_text="raw task",
            workspace_root=workspace,
            environment_id="env-fixed",
            max_steps=12,
            supplied={"task_id": "task", "run_id": "run", "primary_agent_id": "primary"},
        )
        assert missing["source_custody_complete"] is False
        assert missing["source_commit_state"] == "not_supplied"
        assert missing["runtime_manifest_state"] == "not_supplied"


class _TelemetryOnlyModel:
    def __init__(self, rows):
        self.rows = list(rows)

    def drain_telemetry(self):
        rows = tuple(self.rows)
        self.rows = []
        return rows

    def __call__(self, messages, *, max_output_tokens=8000):
        del messages, max_output_tokens
        return '{}'


def test_model_hooks_stamp_frozen_runtime_attribution_and_quarantine_conflicts() -> None:
    from aether.model_hooks import ModelHooks

    owned = _TelemetryOnlyModel([{
        "event_kind": "provider_attempt", "run_id": "run-a", "task_id": "task-a",
        "status": "completed",
    }])
    quiet = _TelemetryOnlyModel([])
    hooks = ModelHooks(
        owned, quiet, run_id="run-a", task_id="task-a",
        telemetry_identity={
            "campaign_id": "campaign-a",
            "source_commit": "a" * 40,
            "task_closure_sha256": "b" * 64,
            "package_closure_sha256": "c" * 64,
        },
    )
    rows = hooks.drain_model_telemetry()
    assert len(rows) == 1
    row = rows[0]
    assert row["campaign_id"] == "campaign-a"
    assert row["source_commit"] == "a" * 40
    assert row["task_closure_sha256"] == "b" * 64
    assert row["package_closure_sha256"] == "c" * 64

    conflicting = _TelemetryOnlyModel([{
        "event_kind": "provider_attempt", "run_id": "run-b", "task_id": "task-b",
        "source_commit": "0" * 40,
    }])
    hooks = ModelHooks(
        conflicting, quiet, run_id="run-b", task_id="task-b",
        telemetry_identity={"source_commit": "1" * 40},
    )
    assert hooks.drain_model_telemetry() == ()
    quarantined = hooks.drain_quarantined_model_telemetry()
    assert len(quarantined) == 1
    assert quarantined[0]["telemetry_quarantine_reason"] == "telemetry_identity_conflict"
    assert quarantined[0]["telemetry_identity_conflict_fields"] == ["source_commit"]


def test_run_task_scopes_provider_to_authoritative_runtime_task_id() -> None:
    class ScopedSolver:
        def __init__(self) -> None:
            self.scope = None

        def call_with_telemetry_scope(self, messages, *, max_output_tokens, run_id, task_id):
            del messages, max_output_tokens
            self.scope = (run_id, task_id)
            return json.dumps({
                "kind": "act",
                "action": {"kind": "write_file", "arguments": {"path": "out.txt", "content": "x"}},
            })

    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        solver = ScopedSolver()
        run_task(
            task_dir=task_dir,
            instruction_text="Write out.txt",
            solver_model=solver,
            verifier_model=_ForbiddenVerifier(),
            workspace_root=workspace,
            max_steps=1,
            runtime_identity={
                "task_id": "sealed-authoritative-task",
                "run_id": "sealed-authoritative-run",
                "primary_agent_id": "primary",
            },
        )
        assert solver.scope == ("sealed-authoritative-run", "sealed-authoritative-task")


def test_run_task_hung_fake_provider_releases_on_bound_cancellation() -> None:
    provider_started = threading.Event()
    cancellation = threading.Event()

    class HangingSolver:
        def __init__(self) -> None:
            self.bound = None

        def bind_run_cancellation(self, event) -> None:
            self.bound = event

        def __call__(self, messages, *, max_output_tokens=16000):
            del messages, max_output_tokens
            provider_started.set()
            assert self.bound is cancellation
            assert self.bound.wait(timeout=2.0)
            raise RunCancellationRequested("fake provider released")

    solver = HangingSolver()

    def cancel_after_provider_entry() -> None:
        assert provider_started.wait(timeout=2.0)
        cancellation.set()

    canceller = threading.Thread(target=cancel_after_provider_entry, daemon=True)
    canceller.start()
    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        record = run_task(
            task_dir=task_dir, instruction_text="fake hung provider",
            solver_model=solver, verifier_model=_ForbiddenVerifier(),
            workspace_root=workspace, max_steps=2,
            runtime_identity={
                "task_id": "hung-provider", "run_id": "hung-provider-run",
                "primary_agent_id": "primary",
            },
            cancellation_event=cancellation,
        )
    canceller.join(timeout=2.0)
    assert provider_started.is_set()
    assert cancellation.is_set()
    assert record["status"] == "timeout"
    assert "external_run_cancellation" in record["blockers"]
    assert not any(
        row["kind"] == "primary_action_result_index"
        for row in record["receipt_records"]
    ), "revoked provider authority must not produce a later task action"



def test_run_task_solver_context_mode_round_trips_without_changing_default() -> None:
    class CapturingSolver:
        def __init__(self) -> None:
            self.messages = None

        def __call__(self, messages, *, max_output_tokens=16000):
            del max_output_tokens
            self.messages = messages
            return json.dumps({"kind": "report_blocker", "blocker": "stop fixture", "evidence": "captured"})

    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        with open(os.path.join(task_dir, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("context treatment fixture")
        full_solver = CapturingSolver()
        compact_solver = CapturingSolver()
        common = dict(
            task_dir=task_dir,
            instruction_text="Inspect the environment then stop.",
            verifier_model=_ForbiddenVerifier(),
            workspace_root=workspace,
            max_steps=1,
            runtime_identity={"task_id": "ctx", "run_id": "ctx-run", "primary_agent_id": "primary"},
        )
        full = run_task(solver_model=full_solver, **common)
        compact = run_task(solver_model=compact_solver, solver_context_mode="compact", **common)

    assert full["runtime_identity"]["task_id"] == compact["runtime_identity"]["task_id"] == "ctx"
    assert full_solver.messages is not None and compact_solver.messages is not None
    full_prefix = "\n".join(row["content"] for row in full_solver.messages[:-1])
    compact_prefix = "\n".join(row["content"] for row in compact_solver.messages[:-1])
    assert "[envmap_file_tree]" in full_prefix
    assert "[envmap_file_tree]" not in compact_prefix
    assert "[environment_discovery]" in compact_prefix
    assert len(compact_prefix) < len(full_prefix)
