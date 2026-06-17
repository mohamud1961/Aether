# Tooling Tool-Contract Tournament

This family extends the attribution guard tournament with two additional
mechanism variants: `contract_classifier` and `service_contract_first_receipt_closure`.

## Included

- `prediction.json`, `comparison_summary.json`, `scoreboard.json` — these three
  files are the same Phase-3 attribution guard tournament data that appears in
  `attribution_guard_tournament/`. They are **not** a separate Goal-1b certified
  tournament result for the tooling/contract family. See the scoreboard honesty
  note below.
- `variant_cards/v04_tb_01.yaml` — variant card for the contract classifier.
- `code/` — mechanism snapshots for the full variant set (5 attribution guard
  files + `contract_classifier.py` + `service_contract_first_receipt_closure.py`).

## Mechanisms

| Variant | File | Added by this family? |
|---|---|---|
| `control_no_mechanism` | (baseline, no code file) | No (carried from attribution_guard) |
| `ignored_result_ids_guard` | `code/ignored_result_ids_guard.py` | No |
| `no_call_attribution_guard` | `code/no_call_attribution_guard.py` | No |
| `combined_guard` | `code/combined_result_attribution_guard.py` | No |
| `contract_classifier` | `code/contract_classifier.py` | YES |
| `service_contract_first_receipt_closure` | `code/service_contract_first_receipt_closure.py` | YES |

## Scoreboard honesty note

The `scoreboard.json`, `prediction.json`, and `comparison_summary.json` in this
directory are bit-for-bit identical to the same files in `attribution_guard_tournament/`.
They record the Phase-3 clean-tool-contract-semantics run (2026-05-17), not a
separate certified tooling tournament.

The Goal-1b certified tournament run for this family was partially executed
(per-run directories exist privately) but **no aggregated scoreboard JSON was
produced**. A `tooling_tool_contract_certified_v2.json` scoreboard does not
exist and has not been fabricated. The Phase-3 data is the only scored evidence
available for this family.

## Key lesson

The interesting result from the Phase-3 data is not "a guard won." It is that
`combined_guard` improved the target rows while regressing the sentinel —
exactly the interaction failure the public eval workflow is meant to catch.
The `contract_classifier` and `service_contract_first_receipt_closure` add
mechanism coverage for the tool-call contract layer, but their isolated impact
has not been scored against a certified baseline.
