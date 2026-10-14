# Task card: build_survival_truth (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design.

## Design (v2)

- Goal-level ticket: a nightly job reports green but the artifact is missing.
- Traps: the CI wrapper's exit status is the status of `tail`; the stdout summary line looks like success;
  the crash message is on stderr, so a merged-stream count is wrong; the config's planned count is not the
  stdout count; the last-night log shows a clean run; the notes are stale.
- The grader recomputes the expected report from a pristine config and hashes every workspace file, so the build
  cannot be edited to match the report.

## Controls

- Known-bad: 9 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| missing_build_report | known_bad run_without_report; careless do_nothing, wrong_target |
| terminal_state_mismatch | known_bad terminal_state_from_ok_lines; careless fake_it |
| exit_code_mismatch | known_bad exit_code_from_wrapper; careless skip_check |
| log_lines_total_mismatch | known_bad log_count_from_config, log_count_merged_streams |
| crash_component_mismatch | known_bad crash_component_off_by_one |
| crashed_mismatch | known_bad bool_as_int |
| missing_survival_evidence | known_bad evidence_blank; careless half_done |
| evidence_file_modified | known_bad simulator_edited |
