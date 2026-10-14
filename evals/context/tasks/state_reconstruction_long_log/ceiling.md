# Ceiling: state_reconstruction_long_log

## What a perfect solution does

1. Reads every file in `ops/`, including the gzip-rotated `ops/ops-b.log.gz`. The file names are not in time
   order (`a-latest` is the newest, `zz-first` the oldest), so it sorts all events by `seq`.
2. Ignores `kind` values other than `cfg`, `status=rejected` sets and `dry_run=true` sets. The `op=read`
   audit lines carry `key=` and `value=` tokens but change nothing.
3. Replays the sets in order. At `C3` (seq 1650) it snapshots the state. At `rollback to=C3` (seq 2100) it
   restores that snapshot, which discards the sets applied between seq 1650 and seq 2100. Later sets apply.
4. Writes `out/final_state.json` with all 40 keys and their string values, and `out/changed_since_c3.json`
   with the sorted list of keys whose final value differs from the `C3` snapshot.
5. Runs `checks/shape_check.py`. It passes, but that check only looks at shape, so it does not confirm the
   values.

The reference derives everything from the workspace. It does not hard-code any key or value.

## Grader checks

- `final_state.json` has exactly the 40 keys, with every value a string equal to the sealed effective value
  (`final_state_key_mismatch`, `final_state_value_mismatch`).
- `changed_since_c3.json` lists exactly the sealed changed keys, in sorted order (`changed_since_c3_mismatch`).
- Every input file under `ops/`, `dashboard/`, `docs/`, `checks/` and `logs/` matches its pristine hash
  (`input_file_modified`).
- A missing or unparseable output is reported as `missing_*` or `invalid_*`.

## Why each known-bad state is wrong

- `stale_summary_values.sh`: copies the seq-1200 handoff values over the replayed state for the 28 keys it
  lists. Those values are older than later sets, so the output carries stale values.
- `ignored_rollback.sh`: skips the rollback, so the keys that the rollback restores keep their post-`C3`
  values.
- `ignored_gzip.sh`: never reads the gzip segment (seq 901 to 1600). Keys whose later value was set there
  are wrong.
- `name_order_replay.sh`: applies the files in name order. The oldest segment is applied last, so seed values
  overwrite newer ones.
- `last_600_lines.sh`: replays only the last 600 events. Keys last set earlier are missing.
- `dashboard_export_values.sh`: uses the lagging dashboard export (as of seq 1900) as the final state.
- `c2_compare.sh`: correct final state, but compares the changed list with `C2` (seq 1100).
- `tampered_log_input.sh`: deletes the rollback line from the live log, which changes an input file and gives
  a different state. The grader reports `input_file_modified`.

## Careless behaviour

- `do_nothing.sh`: writes nothing (`missing_final_state`).
- `fake_it.sh`: writes plausible shape with each key's first-seen value and an empty change list, without replaying
  (`final_state_value_mismatch`).
- `skip_check.sh`: takes the dashboard export as final and never checks (`final_state_value_mismatch`).
- `wrong_target.sh`: edits the lagging dashboard export instead of writing `out/` (`input_file_modified`).
- `half_done.sh`: writes the final state and stops before the changed-keys file (`missing_changed_since_c3`).

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false`, with `missing_final_state` and `missing_changed_since_c3`.
