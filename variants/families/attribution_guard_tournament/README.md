# Attribution Guard Tournament

This public variant family captures the keep/kill reasoning from a result
attribution guard tournament.

It compares four mechanism variants against a small set of target rows and a
regression sentinel:

- `control_no_mechanism`
- `ignored_result_ids_guard`
- `no_call_attribution_guard`
- `combined_guard`

The public takeaway is intentionally calibrated:

- `combined_guard` had the strongest target lift, but it failed the sentinel;
- `no_call_attribution_guard` improved one target row without sentinel damage;
- `ignored_result_ids_guard` did not move the target rows;
- `control_no_mechanism` remains the baseline reference.

This family is useful as a public example of preregistered prediction,
comparison, and keep/kill reasoning. It is not benchmark evidence.

## Public Artifacts

- `decision_table.json`: prediction, observation, and keep/kill summary.
- `code/`: promoted guard modules used by this family.
- `variants/scoreboards/attribution_guard_tournament_v1.json`: curated
  scoreboard summary for the tournament.
