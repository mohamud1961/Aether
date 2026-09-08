from __future__ import annotations

import json
from pathlib import Path

from evals.performance.context_interface_experiment import (
    adjudicate, load_manifest, materialize_fixture, qualify_provider_free,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evals" / "performance" / "PHASE_C_CONTEXT_INTERFACE_V1.json"


def test_phase_c_manifest_is_exact_paired_private_experiment() -> None:
    doc = load_manifest(MANIFEST)
    assert [row["family"] for row in doc["fixtures"]] == [
        "filesystem_inventory", "path_command_inventory", "python_module_inventory",
    ]
    assert sum(len(row["arm_order"]) for row in doc["fixtures"]) == 6
    assert doc["protected_benchmark_content_used"] is False
    assert doc["arms"]["FULL"]["solver_context_mode"] == "full"
    assert doc["arms"]["COMPACT"]["solver_context_mode"] == "compact"


def test_phase_c_materialization_is_truthful_and_grade_sources_exist(tmp_path: Path) -> None:
    doc = load_manifest(MANIFEST)
    for fixture in doc["fixtures"]:
        root = tmp_path / fixture["id"]
        row = materialize_fixture(fixture, doc["fixture_bulk"], root)
        probe = row["envmap"].task_metadata["environment_probe"]
        assert probe["schema_version"] == "environment_probe.v1"
        assert len(probe["command_names"]) >= doc["fixture_bulk"]["command_decoys"]
        assert len(probe["python"]["modules"]) == doc["fixture_bulk"]["python_module_decoys"]
        if fixture["family"] == "filesystem_inventory":
            assert any("TARGET_TOKEN=" in p.read_text() for p in (root / "data").glob("*.txt"))
        elif fixture["family"] == "path_command_inventory":
            assert any(
                row.get("detail") == "private_fixture_token_source"
                for row in probe["command_names"].values()
            )
        else:
            assert any(
                row.get("detail") == "private_fixture_token_source"
                for row in probe["python"]["modules"].values()
            )


def _rows(*, compact_valid=3, full_valid=3, compact_input=100, full_input=300,
          compact_actions=6, full_actions=5, compact_fail=0, full_fail=0,
          compact_latency=10.0, full_latency=10.0):
    rows=[]
    fixtures=["private-file-inventory-discovery-v1","private-path-tool-discovery-v1","private-python-module-discovery-v1"]
    for index,fid in enumerate(fixtures):
        for arm in ("FULL","COMPACT"):
            compact=arm=="COMPACT"
            valid_count=compact_valid if compact else full_valid
            valid=index < valid_count
            rows.append({
                "fixture_id":fid,"arm":arm,"status":"completed","valid_completion":valid,
                "wall_elapsed_s": compact_latency if compact else full_latency,
                "metrics":{
                    "first_solver_input_utf8_bytes": (compact_input if compact else full_input),
                    "total_solver_input_utf8_bytes": (compact_input if compact else full_input),
                    "action_count": (compact_actions if compact else full_actions)//3,
                    "environment_assumption_failures": (compact_fail if compact else full_fail)//3,
                }
            })
    return rows


def test_phase_c_adjudication_retains_only_when_all_preregistered_gates_pass() -> None:
    manifest=load_manifest(MANIFEST)
    result=adjudicate(_rows(),manifest)
    assert result["decision"]=="RETAIN_COMPACT"
    worse=adjudicate(_rows(compact_valid=2),manifest)
    assert worse["decision"]=="KEEP_FULL"
    assert worse["gates"]["valid_completion_not_lower"] is False


def test_phase_c_provider_failure_is_inconclusive_not_silently_scored() -> None:
    manifest=load_manifest(MANIFEST)
    rows=_rows()
    rows[0]["status"]="provider_failure"
    result=adjudicate(rows,manifest)
    assert result["decision"]=="INCONCLUSIVE_PROVIDER_FAILURE"


def test_phase_c_provider_free_qualification_proves_real_treatment_contrast(tmp_path: Path) -> None:
    result = qualify_provider_free(MANIFEST, evidence_root=tmp_path / "qualification")
    assert result["status"] == "PASS"
    assert result["provider_calls"] == 0
    assert result["fixture_count"] == 3
    assert all(row["full_has_contrast_marker"] for row in result["rows"])
    assert all(not row["compact_has_contrast_marker"] for row in result["rows"])
    assert all(row["fixture_shell_reality_pass"] for row in result["rows"])
    assert all(row["ceiling_pass"] and row["known_bad_rejected"] for row in result["rows"])
    assert all(row["compact_to_full_ratio"] < 0.10 for row in result["rows"])


def test_phase_c_partial_provider_failure_stops_as_inconclusive() -> None:
    manifest = load_manifest(MANIFEST)
    rows = _rows()[:3]
    rows[-1]["status"] = "provider_failure"
    result = adjudicate(rows, manifest)
    assert result["decision"] == "INCONCLUSIVE_PROVIDER_FAILURE"
    assert result["attempted_arm_count"] == 3
    assert result["planned_arm_count"] == 6


def test_phase_c_partial_without_provider_invalid_is_incomplete() -> None:
    manifest = load_manifest(MANIFEST)
    result = adjudicate(_rows()[:2], manifest)
    assert result["decision"] == "INCONCLUSIVE_INCOMPLETE"
    assert result["attempted_arm_count"] == 2
