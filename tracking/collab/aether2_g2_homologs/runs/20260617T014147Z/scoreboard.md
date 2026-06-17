# G2 local-homolog scoreboard

Run timestamp: 20260617T014147Z

| homolog | row_status | classification_stage | scoreable | verifier_exit | verifier_clean | steps | model_calls | tokens_cached | tokens_fresh | wall_time_sec | loop_error |
|---|---|---|---|---|---|---|---|---|---|---|---|
| g2_01_file_artifact | pass | grader | True | 0 | False | 3 | 8 | 30336 | 10001 | 49.3 |  |
| g2_02_service_survives_exit | pass | grader | True | 0 | False | 4 | 9 | 41728 | 15475 | 66.1 |  |
| g2_03_interactive_session | invalid_environment | launch | False | None | None | None | None | None | None | 0.0 |  |
| g2_04_package_install | pass | grader | True | 0 | False | 3 | 8 | 31360 | 12192 | 42.7 |  |
| g2_05_long_running_job | pass | grader | True | 0 | False | 5 | 10 | 45952 | 14819 | 49.0 |  |

## Summary

- total_rows: 5
- scorable_rows: 4
- score_numerator: 4
- score_denominator: 4
- score: 1.0

| row_status | count |
|---|---|
| pass | 4 |
| fail | 0 |
| invalid_launch | 0 |
| invalid_environment | 1 |
| invalid_provider | 0 |
| invalid_resource_killed | 0 |
| invalid_grader | 0 |

## By Attempt

| attempt | pass | fail | invalid | total |
|---|---|---|---|---|
| unknown | 4 | 0 | 1 | 5 |
