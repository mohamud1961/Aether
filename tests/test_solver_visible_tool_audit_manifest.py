from __future__ import annotations

import json
from pathlib import Path

from aether.pcr_provider_protocol import PCR_DIRECT_PROVIDER_TOOLS

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tracking" / "releases" / "SOLVER_VISIBLE_TOOL_TRUTHFULNESS_AUDIT_20260906.json"


def test_solver_visible_tool_audit_covers_exact_current_native_surface() -> None:
    doc = json.loads(AUDIT.read_text(encoding="utf-8"))
    audited = {row["name"] for row in doc["surfaces"]}
    provider_functions = {row["name"] for row in PCR_DIRECT_PROVIDER_TOOLS}
    assert audited == provider_functions | {"computer"}
    assert doc["audited_surface_count"] == len(audited) == 26
    assert all(row["verdict"] == "PASS" for row in doc["surfaces"])
    assert doc["status"] == "PASS_ALL_VISIBLE_SURFACES_AUDITED"


def test_audit_rows_bind_every_truthfulness_dimension_and_test_evidence() -> None:
    doc = json.loads(AUDIT.read_text(encoding="utf-8"))
    required = {
        "name", "visibility", "ownership_domain", "meaning", "success_semantics",
        "bounded_output_or_paging", "absence_vs_failure", "evidence_tests", "verdict",
    }
    for row in doc["surfaces"]:
        assert set(row) == required
        assert all(str(row[key]).strip() for key in required - {"evidence_tests"})
        assert row["evidence_tests"]
        for path in row["evidence_tests"]:
            assert (ROOT / path).is_file(), (row["name"], path)
