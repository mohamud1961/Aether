# Attempts

Example run records from the final harness evaluation suite v1.

These are NOT benchmark leadership claims. They are evidence artifacts showing
what was tried, what passed, and what failed under the published eval surfaces.

## What is here

Two baseline-control run timestamps from 2026-05-30 (UTC):

- `final_harness_v1/20260530T154156Z/` — first control run
- `final_harness_v1/20260530T154755Z/` — second control run

Each run directory contains:

| file | description |
|------|-------------|
| `scoreboard.md` | Human-readable run scoreboard (clean, no host paths) |
| `scoreboard.json` | Machine-readable scoreboard JSON |
| `result_rows.jsonl` | Per-row grading results (host paths sanitized to `<workspace>`) |
| `run_summary.json` | Run metadata (host paths sanitized to `<workspace>`) |
| `result_rows_scoreboard.json` | Scoreboard derived from result rows |
| `contamination_review.json` | Contamination gate review results |
| `invalidity_report.json` | Invalidity classification results |
| `finalist_selection.md` | Finalist selection log |
| `recipe_manifest_snapshot.yaml` | Snapshot of the active recipe manifest at run time |

## Interpretation

- Both runs were `recipe_control` baseline runs — no recipe under evaluation
- `verdict: invalid` rows indicate the docker-based task execution environment
  was unavailable in the local run context (expected for control runs)
- All host paths in `result_rows.jsonl` and `run_summary.json` have been
  sanitized to `<workspace>` (original paths contained the Azure VM build path)
- These runs predate the pressure_family/ rename; internal references to
  old task_pack_ids may appear in result rows

## Not included

Raw model exchange traces, solver workspace artifacts, and private task run
directories are not redistributed here (they live under `tracking/` which is
gitignored in the public tree).
