# Attribution Guard Tournament

Status: public-safe case study

This page shows a second public engineering shape for HarnessEng: a
preregistered keep/kill tournament that compares result-attribution guard
variants and records why the strongest target win was not promoted yet.

## Problem And Context

The public repo needed a concrete variant-planning example, not just a smoke
eval example.

This tournament shows how the project reasons about mechanism candidates when
the target rows improve but a regression sentinel does not cooperate.

## Engineering Loop Used

The public loop here was:

1. write the prediction first;
2. compare the control and candidate variants;
3. inspect target movement and sentinel behavior together;
4. keep the strongest follow-up candidate, but do not promote on target gain
   alone;
5. document the decision table in a public-safe summary.

## Public Artifacts Produced

- `variants/families/attribution_guard_tournament/README.md`
- `variants/families/attribution_guard_tournament/decision_table.json`
- `variants/scoreboards/attribution_guard_tournament_v1.json`

## Evidence Table

| Artifact | What it shows |
| --- | --- |
| `variants/families/attribution_guard_tournament/README.md` | Public narrative for the keep/kill reasoning and the calibrated outcome. |
| `variants/families/attribution_guard_tournament/decision_table.json` | Prediction summary, observed target/sentinel movement, and keep/kill decisions. |
| `variants/scoreboards/attribution_guard_tournament_v1.json` | Curated scoreboard summary with the same public-safe results. |

## Validation Summary

| Check | Result |
| --- | --- |
| Path existence checks for the new variant docs and JSON | passed |
| JSON parse checks | passed |
| `rg` sweeps for private path markers and overclaims | passed |
| `git diff --check` | passed |

## What Remains Out Of Scope

- external-suite leadership claims;
- production-readiness claims;
- raw trajectories, traces, or private ledgers;
- hidden grader logic or private fixtures;
- treating the target win as a promotion win when the sentinel did not pass.

## Public Evidence Links

- `docs/publication/public_evidence_index.md`
- `docs/publication/publication_gap_list.md`
- `variants/README.md`
- `variants/families/README.md`
- `variants/shared/README.md`
