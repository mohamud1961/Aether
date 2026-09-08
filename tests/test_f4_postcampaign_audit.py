import json
from pathlib import Path

import pytest

from evals.performance.f4_aggregate import EXPECTED
from evals.performance.f4_postcampaign_audit import audit_controller_receipts, audit_serial_log


CANDIDATE = {
    "harbor_version": "0.20.0",
    "model_profile_sha256": "a" * 64,
    "package_closure_sha256": "b" * 64,
    "source_commit": "c" * 40,
    "source_tree": "d" * 40,
    "tool_schema_sha256": "e" * 64,
    "wheel_sha256": "f" * 64,
}


def make_controller(root: Path):
    c = root / "_s6_controller"
    c.mkdir()
    for ordinal, _board, task_id in EXPECTED:
        run_id = f"f4-reg-{ordinal:02d}-{task_id}-20260905"
        doc = {
            "run_id": run_id,
            "task_id": task_id,
            "canonical_runner_only": True,
            "dry_run": False,
            "provider_calls_allowed": True,
            "max_attempts": 1,
            "max_retries": 0,
            "child_custody": {"valid": True, "mismatches": []},
            "candidate": CANDIDATE,
            "terminal_launch_receipt_sha256": f"{ordinal:064x}",
            "status": "executed_valid",
            "controller_returncode": 0,
        }
        (c / f"{run_id}.completed.json").write_text(json.dumps(doc))


def make_log(path: Path):
    lines = []
    for ordinal, _board, task_id in EXPECTED:
        oo = f"{ordinal:02d}"
        lines += [
            f"=== ADMIT {oo} {task_id} 2026-09-05T00:00:00Z ===",
            f"SENTINEL_PASS {oo} {task_id}",
            "F4_TIMEOUT_CLASSIFICATION_SENTINEL_PASS",
            f"ROW_TERMINAL {oo} {task_id} controller_status= executed_valid",
            f"=== SEALED_MECHANICALLY {oo} {task_id} 2026-09-05T00:00:01Z ===",
        ]
    lines.append("F4_REGRESSION_15_OF_15_TERMINAL 2026-09-05T00:00:02Z")
    path.write_text("\n".join(lines) + "\n")


def test_controller_receipts_require_exact_immutable_campaign(tmp_path):
    make_controller(tmp_path)
    out = audit_controller_receipts(tmp_path, {"candidate": CANDIDATE})
    assert out["row_count"] == 15
    assert out["candidate_immutable"] is True
    extra = tmp_path / "_s6_controller" / "f4-reg-99-extra-20260905.completed.json"
    extra.write_text("{}")
    with pytest.raises(ValueError, match="completion set mismatch"):
        audit_controller_receipts(tmp_path, {"candidate": CANDIDATE})


def test_controller_receipts_reject_candidate_change(tmp_path):
    make_controller(tmp_path)
    p = next((tmp_path / "_s6_controller").glob("*.completed.json"))
    d = json.loads(p.read_text())
    d["candidate"]["source_commit"] = "0" * 40
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="candidate mismatch"):
        audit_controller_receipts(tmp_path, {"candidate": CANDIDATE})


def test_serial_log_requires_every_gate_once(tmp_path):
    p = tmp_path / "serial.log"
    make_log(p)
    out = audit_serial_log(p)
    assert out["mechanical_seal_count"] == 15
    text = p.read_text().replace("F4_TIMEOUT_CLASSIFICATION_SENTINEL_PASS\n", "", 1)
    p.write_text(text)
    with pytest.raises(ValueError, match="timeout sentinel count mismatch"):
        audit_serial_log(p)
