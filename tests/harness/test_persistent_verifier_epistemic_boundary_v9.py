from __future__ import annotations

from types import SimpleNamespace

from aether.ledger import ExecutionLedger, Receipt
from aether.verifier_inspector import VerifierInspectionRequest, execute_verifier_inspection_requests


class _Executor:
    def __init__(self) -> None:
        self.files = {
            "forward.py": "SECRET_IMPLEMENTATION = 1\n",
            "steal.py": "print('solver output')\n",
            "generated.txt": "generated\n",
        }

    def read_file(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def glob(self, pattern: str):
        return ()


def _compiled(schema: str = "persistent_v11_raw"):
    return SimpleNamespace(
        planned_checks=lambda: (),
        task_contract=SimpleNamespace(schema_version=schema),
    )


def _env():
    return SimpleNamespace(workspace_root="/app")


def test_persistent_verifier_cannot_directly_read_unobserved_preexisting_source() -> None:
    ledger = ExecutionLedger()
    rows = execute_verifier_inspection_requests(
        (VerifierInspectionRequest(request_id="hidden", kind="read_file", path="forward.py"),),
        compiled=_compiled(), ledger=ledger, executor=_Executor(), envmap=_env(),
    )
    assert len(rows) == 1
    assert rows[0]["observation_origin"] == "persistent_epistemic_boundary"
    assert "pre-existing path not observed" in rows[0]["error"]
    assert "SECRET_IMPLEMENTATION" not in str(rows[0])


def test_persistent_verifier_may_read_path_already_observed_by_primary() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-0:read", step=0, kind="read_file", success=True,
        summary="primary read forward.py", payload={"path": "/app/forward.py"},
    ))
    rows = execute_verifier_inspection_requests(
        (VerifierInspectionRequest(request_id="seen", kind="read_file", path="forward.py"),),
        compiled=_compiled(), ledger=ledger, executor=_Executor(), envmap=_env(),
    )
    assert rows[0]["observation_origin"] == "executor_read"
    assert "SECRET_IMPLEMENTATION" in rows[0]["excerpt"]


def test_persistent_verifier_may_read_solver_created_or_reported_artifact() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-1:write", step=1, kind="write_file", success=True,
        summary="wrote steal.py", payload={"path": "steal.py", "modified_paths": ["steal.py"]},
    ))
    ledger.record(Receipt(
        receipt_id="step-2:command", step=2, kind="run_command", success=True,
        summary="generated output", payload={"artifact_paths": ["generated.txt"], "modified_paths": []},
    ))
    requests = (
        VerifierInspectionRequest(request_id="written", kind="read_file", path="/app/steal.py"),
        VerifierInspectionRequest(request_id="artifact", kind="read_file", path="generated.txt"),
    )
    rows = execute_verifier_inspection_requests(
        requests, compiled=_compiled(), ledger=ledger, executor=_Executor(), envmap=_env(),
    )
    assert [row["observation_origin"] for row in rows] == ["executor_read", "executor_read"]


def test_non_persistent_runtime_keeps_existing_direct_read_behavior() -> None:
    ledger = ExecutionLedger()
    rows = execute_verifier_inspection_requests(
        (VerifierInspectionRequest(request_id="legacy", kind="read_file", path="forward.py"),),
        compiled=_compiled("legacy"), ledger=ledger, executor=_Executor(), envmap=_env(),
    )
    assert rows[0]["observation_origin"] == "executor_read"
    assert "SECRET_IMPLEMENTATION" in rows[0]["excerpt"]


def test_persistent_verifier_wildcard_direct_read_is_rejected_before_glob() -> None:
    ledger = ExecutionLedger()
    rows = execute_verifier_inspection_requests(
        (VerifierInspectionRequest(request_id="wild", kind="read_file", path="*.py"),),
        compiled=_compiled(), ledger=ledger, executor=_Executor(), envmap=_env(),
    )
    assert rows[0]["observation_origin"] == "persistent_epistemic_boundary"
    assert "wildcard direct workspace inspection is unavailable" in rows[0]["error"]
