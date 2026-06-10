# Variants

Public variant operating surface for mechanism families and whole-harness
lines. It contains real variant implementations, hypotheses, tournament
records, decision history, and scoreboards/scorecards where runs were actually
scored.

## Two levels

**Family-level** — competing mechanism implementations within one behavioral
family. Each family has real variant code, a hypothesis, variant cards, and,
where available, scored tournament data.

**Whole-harness** — complete runtime lines and larger orchestration routes.
These are full-line implementations and decision surfaces. Some are frozen
reference lines that depend on historical namespaces, while the live runnable
harness is `harness/aether2` (see `aether/`).

## Sections

- `families/` — mechanism-family tournaments, real variant implementations,
  variant cards, and family-local score surfaces.
- `harness/` — whole-harness lines, kernel/control-plane lineage, decision
  history, and hypothesis backlog.
- `aether/` — pointer to the current winning harness line (`harness/aether2`).
- `shared/` — variant cards, decision rubric, lineage map.
- `scoreboards/` — curated scored data and compact scorecard-style summaries.

## Families at a glance

| Family | Status | Scored data? |
|---|---|---|
| `attribution_guard_tournament` | Fully documented; keep/kill decided | YES — decision_table + scoreboard |
| `tooling_tool_contract_tournament` | Code in place; Phase-3 scoreboard (see honesty note) | PARTIAL |
| `finalization_truth_family` | Implemented + adversarially reviewed; no eval run yet | NO |
| `filesystem_target_selection_family` | Code in place; 0/6 diagnostic baseline | NO |
| `dependency_config_environment` | Code in place; partial uplift in Phase 4 | NO |
| `filesystem_open_workflow` | Code in place; failed target rows in Phase 4 | NO |
| `verifier_repair` | Code in place; non-discriminating eval in Phase 4 | NO |

## Honesty note on scoreboards

`attribution_guard_tournament` is the **only** family with a real scored decision
table from a controlled tournament (prediction → run → comparison → keep/kill).

`tooling_tool_contract_tournament` carries the same Phase-3 tournament data
(identical JSON files). The Goal-1b certified tournament that would have produced
a proper `tooling_tool_contract` aggregate scoreboard was never completed — no
aggregated scoreboard JSON was produced from those runs. The `scoreboard.json`
in that family is Phase-3 attribution data reused, not a new result.

No other family has scored tournament data. Scoreboards and scorecards for
these families do not exist and have not been fabricated.

## Featured reading path

1. `harness/decision_history.md` — Phase 0–7 history (the most complete narrative)
2. `families/attribution_guard_tournament/` — the one fully-scored example
3. `families/finalization_truth_family/` — adversarial review methodology
4. `harness/code/packet04_route_manifest.py` — self-documented variant routing
5. `harness/mlpcp_v3/code/lean_cockpit.py` — self-contained cockpit formatter
