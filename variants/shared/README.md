# Shared

Cross-family helpers and reusable assets that apply across multiple variant families.

## Files

- `atomic_variant_cards.md` — the full set of Packet-04 atomic variant cards
  (v04_vc_01 through evidence_report_scaffold). These cards are the original
  combined form; individual cards have been extracted into each family's
  `variant_cards/` directory for discoverability.

  Cards extracted:
  - `v04_vc_01` → `families/finalization_truth_family/variant_cards/v04_vc_01.yaml`
  - `v04_ex_02` → `families/filesystem_target_selection_family/variant_cards/v04_ex_02.yaml`
  - `v04_cb_01` → `families/filesystem_target_selection_family/variant_cards/v04_cb_01.yaml`
  - `v04_tb_01` → `families/tooling_tool_contract_tournament/variant_cards/v04_tb_01.yaml`

  Cards NOT extracted (no matching family directory):
  - `v04_ex_01` (single_terminal_outcome_cleanup_order_guard) — lifecycle mechanism; no current family
  - `v04_tb_02` (permission_runtime_attribution_split) — tool attribution; no current family
  - `v04_rb_01` (interrupt_retry_spiral_breaker) — bounded diagnostic only
  - `prompt_plan_env` — orientation block; no current family
  - `evidence_report_scaffold` — context block; no current family

- `decision_rubric.md` — public keep/kill rubric for reading curated variant
  summaries and scoreboards. Defines the promotion / kill / pause criteria used
  across all families.

- `lineage_map.md` — route / kernel / Aether lineage map across the public
  variant lanes. Shows how the evidence kernel → active evidence kernel →
  aether2 line connects to the route manifest and family mechanism work.

## Note on sanitization

`anticipated_transfer_eval` fields in `atomic_variant_cards.md` originally
referenced a specific benchmark suite by name. The extracted YAML cards in
`variant_cards/` directories use the neutral prefix `pressure_transfer_`
in place of those names.
