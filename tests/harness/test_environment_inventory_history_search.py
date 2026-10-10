from __future__ import annotations

from aether.compiler_prefix import persistent_model_environment_probe_compact
from aether.context_views import receipt_inline_view
from aether.history_query import query_history
from aether.ledger import Receipt
from aether.persistent_evidence import is_persistent_completion_evidence


def _config_receipt() -> Receipt:
    return Receipt(
        receipt_id="config:realization",
        step=0,
        kind="config_realization",
        success=True,
        summary="compiled mechanical runtime realization",
        payload={
            "config_realization": {
                "schema_version": "aether.persistent_runtime_realization.v1",
                "environment_probe": {
                    "schema_version": "environment_probe.v1",
                    "workspace_root": "/app",
                    "command_names": {
                        "ordinary": {"available": True, "path": "/usr/bin/ordinary", "detail": "ordinary"},
                        "hidden-tool": {
                            "available": True,
                            "path": "/private/bin/hidden-tool",
                            "version": "private_fixture_token_source",
                            "detail": "private_fixture_token_source",
                            "api_key": "MUST-NOT-BE-SEARCHABLE",
                        },
                    },
                    "python": {
                        "preferred": "python3",
                        "modules": {
                            "plainmod": {"available": True, "available_in": ["python3"], "detail": "ordinary"},
                            "hiddenmod": {
                                "available": True,
                                "available_in": ["python3"],
                                "detail": "private_fixture_module_source",
                                "secret": "MODULE-SECRET-MUST-NOT-BE-SEARCHABLE",
                            },
                        },
                    },
                    "credential_dump": "TOP-LEVEL-SECRET-MUST-NOT-BE-SEARCHABLE",
                },
            }
        },
    )


def test_literal_environment_inventory_search_returns_bounded_exact_command_identity() -> None:
    result = query_history([_config_receipt()], "private_fixture_token_source")
    assert result["total_matches"] == 1
    row = result["results"][0]
    matches = row["environment_inventory_matches"]
    assert len(matches) == 1
    assert matches[0]["kind"] == "command"
    assert matches[0]["name"] == "hidden-tool"
    assert matches[0]["path"] == "/private/bin/hidden-tool"
    assert matches[0]["historical_observation"] is True
    assert matches[0]["current_task_state"] is False
    assert matches[0]["completion_evidence_eligible"] is False
    assert matches[0]["requires_live_revalidation"] is True
    assert row["environment_inventory_semantics"]["mutable_availability_requires_live_revalidation"] is True


def test_literal_environment_inventory_search_returns_python_module_identity() -> None:
    result = query_history([_config_receipt()], "private_fixture_module_source")
    match = result["results"][0]["environment_inventory_matches"][0]
    assert match["kind"] == "python_module"
    assert match["name"] == "hiddenmod"
    assert match["available_in"] == ["python3"]


def test_environment_inventory_search_does_not_index_unknown_or_secret_fields() -> None:
    receipt = _config_receipt()
    for secret in (
        "MUST-NOT-BE-SEARCHABLE",
        "MODULE-SECRET-MUST-NOT-BE-SEARCHABLE",
        "TOP-LEVEL-SECRET-MUST-NOT-BE-SEARCHABLE",
    ):
        assert query_history([receipt], secret)["total_matches"] == 0


def test_empty_history_query_never_dumps_environment_inventory() -> None:
    result = query_history([_config_receipt()], "")
    assert result["total_matches"] == 1
    assert "environment_inventory_matches" not in result["results"][0]


def test_environment_inventory_search_is_bounded_to_eight_rows() -> None:
    receipt = _config_receipt()
    commands = receipt.payload["config_realization"]["environment_probe"]["command_names"]
    for index in range(20):
        commands[f"match-{index:02d}"] = {
            "available": True,
            "path": f"/private/bin/match-{index:02d}",
            "detail": "shared-literal-marker",
        }
    result = query_history([receipt], "shared-literal-marker")
    assert result["total_matches"] == 1
    assert len(result["results"][0]["environment_inventory_matches"]) == 8


def test_environment_inventory_match_survives_solver_context_projection() -> None:
    query_result = query_history([_config_receipt()], "private_fixture_token_source")
    query_receipt = Receipt(
        receipt_id="step-0:history",
        step=0,
        kind="query_history",
        success=True,
        summary="literal history query",
        payload=query_result,
    )

    projected = receipt_inline_view(query_receipt)
    match = projected["results"][0]["environment_inventory_matches"][0]

    assert match["kind"] == "command"
    assert match["name"] == "hidden-tool"
    assert match["path"] == "/private/bin/hidden-tool"
    assert match["detail"] == "private_fixture_token_source"
    assert match["completion_evidence_eligible"] is False
    assert match["requires_live_revalidation"] is True
    assert projected["results"][0]["environment_inventory_semantics"] == {
        "source": "immutable_preflight_config_realization",
        "historical_results_are_current_state": False,
        "completion_evidence_eligible": False,
        "mutable_availability_requires_live_revalidation": True,
    }
    assert "MUST-NOT-BE-SEARCHABLE" not in str(projected)


def test_environment_inventory_projection_bounds_allowlisted_strings_and_lists() -> None:
    receipt = _config_receipt()
    probe = receipt.payload["config_realization"]["environment_probe"]
    marker = "bounded-environment-marker"
    oversized_name = "command-" + ("n" * 500)
    probe["command_names"][oversized_name] = {
        "available": True,
        "path": "/private/bin/" + ("p" * 500),
        "detail": marker + ("d" * 500),
    }
    probe["python"]["modules"]["boundedmod"] = {
        "available": True,
        "available_in": ["python3-" + ("i" * 300) for _ in range(20)],
        "detail": marker,
    }

    result = query_history([receipt], marker)
    matches = result["results"][0]["environment_inventory_matches"]
    command = next(row for row in matches if row["kind"] == "command")
    module = next(row for row in matches if row["kind"] == "python_module")

    assert len(command["name"]) == 256
    assert len(command["path"]) == 256
    assert len(command["detail"]) == 256
    assert len(module["available_in"]) == 8
    assert all(len(item) == 128 for item in module["available_in"])

    query_receipt = Receipt(
        receipt_id="step-0:bounded-history",
        step=0,
        kind="query_history",
        success=True,
        summary="bounded literal history query",
        payload=result,
    )
    projected = receipt_inline_view(query_receipt)
    projected_matches = projected["results"][0]["environment_inventory_matches"]
    projected_module = next(row for row in projected_matches if row["kind"] == "python_module")
    assert len(projected_module["available_in"]) == 8
    assert all(len(item) == 128 for item in projected_module["available_in"])


def test_config_realization_remains_control_plane_not_completion_evidence() -> None:
    assert is_persistent_completion_evidence(_config_receipt()) is False


def test_compact_probe_teaches_demand_loaded_inventory_and_live_revalidation() -> None:
    probe = _config_receipt().payload["config_realization"]["environment_probe"]
    compact = persistent_model_environment_probe_compact(probe)
    discovery = compact["discovery"]
    assert "query_history" in discovery["environment_inventory"]
    assert "literal marker" in discovery["environment_inventory"]
    assert "revalidate" in discovery["environment_inventory"]
    assert "exact paths" in discovery["paths"]


def test_provider_native_query_history_description_exposes_environment_inventory_contract() -> None:
    from aether.persistent_provider_protocol import PERSISTENT_DIRECT_PROVIDER_TOOLS

    tool = next(row for row in PERSISTENT_DIRECT_PROVIDER_TOOLS if row["name"] == "query_history")
    description = tool["description"]
    assert "preflight" in description
    assert "environment inventory" in description
    assert "revalidate" in description
