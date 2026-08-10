from __future__ import annotations

from typing import Any

import pytest

from aether.architect_v2_contract import validate_architect_v2
from aether.proof_contract import PROOF_KINDS


def _contract(
    name: str,
    obligations: list[dict[str, Any]],
    proof_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    facts = [{
        "fact_id": "task_fact",
        "statement": f"The hand-authored {name} fixture supplies the visible task facts.",
        "source": "task_prompt",
                    "verbatim_anchors": [name],
    }]
    for obligation in obligations:
        obligation.setdefault("fact_refs", ["task_fact"])
    return {
        "schema_version": "aether_architect.v2",
        "method_constraints": [],
        "task_contract": {"exact_facts": facts, "obligations": obligations},
        "proof_intent": proof_groups,
        "solver_design": {
            "mission": f"Satisfy the obligations for the {name} fixture.",
            "strategy": "Inspect current state, act incrementally, and adapt to observations.",
        },
        "verifier_design": {
            "mission": "Judge the declared obligations from current Verifier evidence.",
            "verification_strategy": "Use the proof group for each obligation and reject unsupported evidence.",
        },
    }


def _group(proof_id: str, obligation_refs: list[str], proof_kind: str) -> dict[str, Any]:
    return {
        "proof_id": proof_id,
        "obligation_refs": obligation_refs,
        "proof_kind": proof_kind,
        "acceptance_observation": f"A current observation establishes {proof_id}.",
        "falsification_observation": f"A contradictory observation falsifies {proof_id}.",
    }


# These are hand-authored semantic designs, not task detectors.  The review
# record explains why each group is sufficient and whether a single obligation
# would need multiple proof modes.  Where a requirement genuinely spans static
# and behavioral evidence, it is split at an independently judgeable semantic
# boundary rather than hiding two modes in one obligation.
EXPRESSIVENESS_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "name": "grpc_generated_interface_consistency",
        "obligations": [
            {"obligation_id": "interface_fields_match", "statement": "The generated interface matches the declared request and response fields."},
            {"obligation_id": "public_round_trip_matches", "statement": "A live round trip obeys the declared field contract."},
        ],
        "proof_groups": [
            _group("interface_contract", ["interface_fields_match"], "exact_state"),
            _group("round_trip_behavior", ["public_round_trip_matches"], "public_behavior"),
        ],
        "grouping_sufficient": "Static interface and live behavior are separate judgeable obligations.",
    },
    {
        "name": "live_service_behavior",
        "obligations": [{"obligation_id": "service_behaves", "statement": "The live service returns the required public behavior."}],
        "proof_groups": [_group("service_behavior", ["service_behaves"], "public_behavior")],
        "grouping_sufficient": "One public-behavior obligation has one public-behavior proof group.",
    },
    {
        "name": "gcode_semantic_output",
        "obligations": [{"obligation_id": "geometry_matches_source", "statement": "The produced geometry is the independently re-derived result of the source instructions."}],
        "proof_groups": [_group("geometry_derivation", ["geometry_matches_source"], "independent_comparison")],
        "grouping_sufficient": "The semantic result is one comparison between source-derived and produced geometry.",
    },
    {
        "name": "video_visual_output",
        "obligations": [{"obligation_id": "visual_output_matches_target", "statement": "The visual output contains the required visible result."}],
        "proof_groups": [_group("visual_perception", ["visual_output_matches_target"], "direct_perception")],
        "grouping_sufficient": "The obligation is directly judgeable through eligible perceptual evidence.",
    },
    {
        "name": "log_summarisation",
        "obligations": [{"obligation_id": "summary_matches_log", "statement": "The summary agrees with an independently derived reading of the log."}],
        "proof_groups": [_group("log_comparison", ["summary_matches_log"], "independent_comparison")],
        "grouping_sufficient": "One independent comparison can falsify any material summary mismatch.",
    },
    {
        "name": "git_recovery",
        "obligations": [{"obligation_id": "recovered_tree_matches_commit", "statement": "The recovered tree matches the required commit identity and content."}],
        "proof_groups": [_group("git_exact_state", ["recovered_tree_matches_commit"], "exact_state")],
        "grouping_sufficient": "Commit, tree, and clean-state facts form one exact-state contract.",
    },
    {
        "name": "nginx_configuration_and_live_behavior",
        "obligations": [
            {"obligation_id": "nginx_config_declares_routes", "statement": "The configuration contains the required routes and directives."},
            {"obligation_id": "nginx_live_routes_behave", "statement": "The live service exposes the required route behavior."},
        ],
        "proof_groups": [
            _group("nginx_config_state", ["nginx_config_declares_routes"], "exact_state"),
            _group("nginx_route_behavior", ["nginx_live_routes_behave"], "public_behavior"),
        ],
        "grouping_sufficient": "Configuration correctness and live behavior are separate obligations with different evidence modes.",
    },
    {
        "name": "openssl_certificate_correctness",
        "obligations": [
            {"obligation_id": "certificate_state_matches_contract", "statement": "The certificate and key state match the declared contract."},
            {"obligation_id": "certificate_handshake_behaves", "statement": "A live handshake accepts the certificate under the required policy."},
        ],
        "proof_groups": [
            _group("certificate_exact_state", ["certificate_state_matches_contract"], "exact_state"),
            _group("certificate_handshake", ["certificate_handshake_behaves"], "public_behavior"),
        ],
        "grouping_sufficient": "Static certificate identity and handshake behavior are independently falsifiable.",
    },
    {
        "name": "regex_textual_transformation",
        "obligations": [{"obligation_id": "transformation_matches_examples", "statement": "The transformation maps inputs to outputs according to the required textual rule."}],
        "proof_groups": [_group("transformation_comparison", ["transformation_matches_examples"], "independent_comparison")],
        "grouping_sufficient": "A separately computed fixture comparison judges the transformation as a whole.",
    },
    {
        "name": "numerical_rederivation",
        "obligations": [{"obligation_id": "computed_value_matches_formula", "statement": "The reported numerical result matches an independent re-derivation."}],
        "proof_groups": [_group("numerical_comparison", ["computed_value_matches_formula"], "independent_comparison")],
        "grouping_sufficient": "The required result is one independently recalculated value.",
    },
    {
        "name": "filesystem_exact_state",
        "obligations": [{"obligation_id": "required_tree_state", "statement": "The required files, contents, and permissions are in the exact declared state."}],
        "proof_groups": [_group("filesystem_state", ["required_tree_state"], "exact_state")],
        "grouping_sufficient": "The filesystem obligation is explicitly an exact-state comparison.",
    },
    {
        "name": "multi_obligation_end_to_end",
        "obligations": [
            {"obligation_id": "artifact_state_complete", "statement": "The required artifact state is complete and exact."},
            {"obligation_id": "end_to_end_behavior", "statement": "The public end-to-end behavior is correct against the artifact state."},
        ],
        "proof_groups": [
            _group("artifact_state", ["artifact_state_complete"], "exact_state"),
            _group("end_to_end_behavior", ["end_to_end_behavior"], "public_behavior"),
        ],
        "grouping_sufficient": "The two obligations intentionally separate exact artifact state from end-to-end behavior.",
    },
)


@pytest.mark.parametrize("fixture", EXPRESSIVENESS_FIXTURES, ids=lambda item: item["name"])
def test_hand_authored_fixture_has_a_lossless_v2_proof_design(fixture: dict[str, Any]) -> None:
    payload = _contract(fixture["name"], fixture["obligations"], fixture["proof_groups"])
    contract = validate_architect_v2(payload)
    assert len(contract.obligation_ids) == len(fixture["obligations"])
    assert set(contract.proof_kinds) <= set(PROOF_KINDS)
    assert fixture["grouping_sufficient"]


def test_taxonomy_expressiveness_pregate_covers_all_four_kinds_without_distortion() -> None:
    used: set[str] = set()
    for fixture in EXPRESSIVENESS_FIXTURES:
        payload = _contract(fixture["name"], fixture["obligations"], fixture["proof_groups"])
        contract = validate_architect_v2(payload)
        used.update(contract.proof_kinds)
        # Every obligation is covered once by the validator; no fixture claims
        # that one obligation secretly needs multiple proof modes.
        assert len(contract.obligation_ids) == sum(
            len(group["obligation_refs"]) for group in fixture["proof_groups"]
        )
    assert used == set(PROOF_KINDS)
