# Scoreboards

Curated variant scoreboards and structured summaries.

## Honesty policy

This directory contains only real data. No scores or results have been fabricated.

The `attribution_guard_tournament_v1.json` is the only file that contains
actual per-variant tournament outcome counts from a controlled, certified run.

The YAML summaries (`whole_harness_stack_summary_v1.yaml`,
`model_led_substrate_v1.yaml`, `aether2_g5_harness_upgrade_v1.yaml`) are
structured summaries of harness posture and readiness, not scored eval results.
They do not imply benchmark promotion.

## Files

- `attribution_guard_tournament_v1.json` — real per-variant counts from the
  Phase-3 result-attribution guard tournament (prediction, target pass, sentinel
  pass, keep/kill). This is the only scored tournament aggregate in this directory.

- `whole_harness_stack_summary_v1.yaml` — structured summary of the frozen
  kernel/route stack posture. Captures the `sc_b_01` anchor status and the
  provisional-pre-family-completion freeze state. Not a scored eval result.

- `model_led_substrate_v1.yaml` — structured summary of the Phase-6 model-led
  substrate (Layer-2 audit + layered acceptance guard). Captures the adversarial
  review outcome and unit-test status. Not a scored eval result.

- `aether2_g5_harness_upgrade_v1.yaml` — structured summary of the Aether G5
  run analysis readiness snapshot. Captures H1–H8 hypothesis status.
  Not a benchmark promotion claim.

## What does NOT exist here (and why)

- A `tooling_tool_contract_certified_v2.json` scoreboard: the Goal-1b certified
  tooling tournament run directories exist privately but no aggregated scoreboard
  JSON was produced from them. It has not been fabricated.
- Scoreboards for `filesystem_target_selection_family`, `verifier_repair`,
  `dependency_config_environment`, `filesystem_open_workflow`, or
  `finalization_truth_family`: none of these families have completed a scored
  tournament on a certified backend.
