from __future__ import annotations

from aether.judge_verifier_policy import build_inspection_candidates, _requirements


def packet(raw: str, routes: list[str]) -> dict:
    return {
        "raw_user_task": raw,
        "task_contract": {
            "schema_version": "persistent_v11_raw",
            "clauses": [{"clause_id": "raw_task", "text": raw, "exact_atoms": []}],
        },
        "verifier_runtime_capabilities": {
            "available_direct_observation_kinds": routes,
        },
        "state_inspection_handles": [],
        "authoritative_check_ids": [],
        "primary_submission": {"cited_evidence_index": []},
        "dynamic_state": {},
    }


def requests_for(p: dict, prior: list[dict]) -> list[dict]:
    raw = p["raw_user_task"]
    return [
        dict(item.request)
        for item in build_inspection_candidates(
            p,
            prior,
            raw_task=raw,
            requirements=_requirements(p, raw),
            limit=30,
        )
    ]


def test_long_file_gets_next_page_candidate_after_partial_read() -> None:
    p = packet("Inspect result.txt and validate its full contents.", ["read_file"])
    p["state_inspection_handles"] = [{"kind": "file", "path": "result.txt"}]
    prior = [{
        "inspection_id": "inspection:page0",
        "kind": "read_file",
        "path": "result.txt",
        "requested_path": "result.txt",
        "offset": 0,
        "span": 4000,
        "content_chars": 9100,
        "excerpt": "x" * 100,
        "observation_valid": True,
        "error": "",
    }]
    rows = requests_for(p, prior)
    assert any(
        row.get("kind") == "read_file"
        and row.get("path") == "result.txt"
        and row.get("offset") == 4000
        for row in rows
    )


def test_visible_image_exposes_read_metadata_and_perception_candidates() -> None:
    p = packet(
        "Inspect code.png and determine the exact visible pseudocode.",
        ["read_file", "inspect_artifact", "perceive_artifact", "compare_initial_path"],
    )
    p["state_inspection_handles"] = [{"kind": "file", "path": "code.png"}]
    rows = requests_for(p, [])
    kinds = {row.get("kind") for row in rows}
    assert "read_file" in kinds
    assert "inspect_artifact" in kinds
    assert "perceive_artifact" in kinds
    assert "compare_initial_path" in kinds


def test_primary_cited_current_path_is_candidate_even_without_hot_handle() -> None:
    p = packet("Validate result.txt.", ["read_file", "inspect_action_receipts"])
    p["primary_submission"] = {
        "cited_evidence_index": [{
            "kind": "read_file",
            "current_payload_projection": {"path": "result.txt"},
        }]
    }
    rows = requests_for(p, [])
    assert any(
        row.get("kind") == "read_file" and row.get("path") == "result.txt"
        for row in rows
    )


def test_task_declared_port_probe_is_not_starved_by_many_file_handles() -> None:
    p = packet(
        "Run the service on port 5328 and keep it available.",
        ["read_file", "inspect_artifact", "compare_initial_path", "probe_port"],
    )
    p["state_inspection_handles"] = [
        {"kind": "file", "path": f"artifact_{index}.txt"}
        for index in range(10)
    ]
    raw = p["raw_user_task"]
    rows = [
        dict(item.request)
        for item in build_inspection_candidates(
            p,
            [],
            raw_task=raw,
            requirements=_requirements(p, raw),
            limit=12,
        )
    ]
    assert any(
        row.get("kind") == "probe_port" and row.get("target") == "5328"
        for row in rows
    )


def test_current_dynamic_service_and_job_facts_become_probe_candidates() -> None:
    p = packet(
        "Keep the service and background job healthy.",
        ["probe_port", "probe_job"],
    )
    p["dynamic_state"] = {
        "services": {
            "server-main": {"state": "listening", "port": 5328},
        },
        "jobs": {
            "worker-main": {"state": "running", "job_id": "job-abc"},
        },
    }
    rows = requests_for(p, [])
    assert any(
        row.get("kind") == "probe_port" and row.get("target") == "5328"
        for row in rows
    )
    assert any(
        row.get("kind") == "probe_job" and row.get("target") == "job-abc"
        for row in rows
    )


def test_generic_action_history_candidate_exists_without_primary_citation() -> None:
    p = packet(
        "Validate the result independently.",
        ["inspect_action_receipts"],
    )
    rows = requests_for(p, [])
    matches = [row for row in rows if row.get("kind") == "inspect_action_receipts"]
    assert matches
    assert "receipt_kind" not in matches[0]
    assert matches[0].get("limit") == 8


def test_authoritative_check_id_exposes_derived_rerun_candidate() -> None:
    p = packet(
        "Run the declared validation check before completion.",
        ["read_file", "inspect_action_receipts"],
    )
    p["authoritative_check_ids"] = ["validate-current"]
    rows = requests_for(p, [])
    assert any(
        row.get("kind") == "rerun_check"
        and row.get("check_id") == "validate-current"
        for row in rows
    )


def test_visible_file_exposes_artifact_history_when_route_available() -> None:
    p = packet(
        "Validate result.txt and its current provenance.",
        ["read_file", "inspect_artifact_history"],
    )
    p["state_inspection_handles"] = [{"kind": "file", "path": "result.txt"}]
    rows = requests_for(p, [])
    assert any(
        row.get("kind") == "inspect_artifact_history"
        and row.get("path") == "result.txt"
        for row in rows
    )


def test_bounded_recent_receipt_metadata_is_available_as_finite_candidate() -> None:
    p = packet(
        "Validate the current result using available evidence.",
        ["inspect_recent_receipts"],
    )
    rows = requests_for(p, [])
    matches = [row for row in rows if row.get("kind") == "inspect_recent_receipts"]
    assert matches
    assert matches[0].get("limit") == 8
    assert "receipt_kind" not in matches[0]
