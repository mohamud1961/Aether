# Variant Families

Mechanism-level competing implementations within behavioral families.

Each family directory contains:
- `code/` — verbatim code snapshots from `blocks/` (source of truth is `blocks/`)
- `hypothesis.md` — grounded hypothesis with phase evidence
- `variant_cards/` — per-variant YAML cards (where available)
- `README.md` — family summary and status

Code snapshots reference `blocks.*` imports and are not standalone-runnable
outside the repo root. They are preserved as readable records, not deployable code.

## Families

| Directory | Behavioral class | Scored data? |
|---|---|---|
| `attribution_guard_tournament/` | Result-attribution guard mechanisms | YES (decision_table + scoreboard) |
| `tooling_tool_contract_tournament/` | Tool-call contract classification + receipt closure | PARTIAL (Phase-3 data; see README) |
| `finalization_truth_family/` | Layer-2 acceptance gating; `ungoverned_model_claim` prevention | NO |
| `filesystem_target_selection_family/` | cwd/path invariant + decoy-resistant target selection | NO |
| `dependency_config_environment/` | Environment bootstrap normalization | NO |
| `filesystem_open_workflow/` | Open-workflow path evidence normalization | NO |
| `verifier_repair/` | Verifier-episode repair (benchmark prefix stripped) | NO |

## Honest score notes

- `attribution_guard_tournament` is the only family with a proper prediction →
  run → comparison → keep/kill cycle documented in scored data.
- `tooling_tool_contract_tournament` carries Phase-3 attribution tournament JSON,
  not a separate Goal-1b tournament result. See that family's README.
- All other families have no scored tournament data. Nothing has been fabricated.
