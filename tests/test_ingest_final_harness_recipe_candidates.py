from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ingest_final_harness_recipe_candidates import _dump_yaml, _load_yaml, materialize


FIXTURE_ROOT = (
    REPO_ROOT / "tracking/collab/final_harness_eval_suite/fixtures/recipe_ingestion_governance"
)


def _recipes_by_id(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = payload.get("recipes", [])
    assert isinstance(rows, list)
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        assert isinstance(row, dict)
        recipe_id = row.get("recipe_id")
        assert isinstance(recipe_id, str)
        result[recipe_id] = row
    return result


def test_materialize_enforces_recipe_allow_deny_constraints(tmp_path: Path) -> None:
    output_path = tmp_path / "recipe_candidates.yaml"
    materialize(
        family_winner_registry_path=FIXTURE_ROOT / "family_winner_registry.yaml",
        current_stack_manifest_path=FIXTURE_ROOT / "current_stack_manifest.yaml",
        output_path=output_path,
        generated_at="2026-05-25T12:00:00Z",
    )

    payload = _load_yaml(output_path)
    recipes = _recipes_by_id(payload)

    candidate_a = recipes["recipe_candidate_a"]
    candidate_b = recipes["recipe_candidate_b"]

    assert candidate_a["included_mechanism_ids"] == ["sc_b_01", "mech_alpha"]
    assert candidate_b["included_mechanism_ids"] == ["sc_b_01", "mech_beta"]
    assert candidate_a["included_family_winner_refs"] == ["family_alpha:winner_alpha"]
    assert candidate_b["included_family_winner_refs"] == ["family_beta:winner_beta"]

    candidate_b_notes = candidate_b["compatibility_risk_notes"]
    assert isinstance(candidate_b_notes, list)
    assert any(
        note
        == "excluded_winner:family_gamma:winner_gamma:for_recipe_candidate_b:recipe_in_excluded_recipe_ids|recipe_not_in_eligible_recipe_ids"
        for note in candidate_b_notes
    )


def test_materialize_is_deterministic_under_winner_input_order(tmp_path: Path) -> None:
    first_registry = _load_yaml(FIXTURE_ROOT / "family_winner_registry.yaml")
    assert isinstance(first_registry, dict)
    second_registry = copy.deepcopy(first_registry)
    winners = second_registry.get("winners")
    assert isinstance(winners, list)
    winners.reverse()

    registry_path = tmp_path / "family_registry.yaml"
    _dump_yaml(registry_path, first_registry)

    output_a = tmp_path / "output_a.yaml"
    output_b = tmp_path / "output_b.yaml"
    generated_at = "2026-05-25T12:00:00Z"
    stack_path = FIXTURE_ROOT / "current_stack_manifest.yaml"
    materialize(registry_path, stack_path, output_a, generated_at)
    _dump_yaml(registry_path, second_registry)
    materialize(registry_path, stack_path, output_b, generated_at)

    assert _load_yaml(output_a) == _load_yaml(output_b)
