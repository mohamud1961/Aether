# Raw Ledger Update

- recorded_at_utc: 2026-06-18T18:00:37+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: claude-sonnet-4-6
- task: stage0 — restore measurement validity for local custom-eval board (path resolution fix)
- event_type: bug_fix
- raw_block_type: RAW_LEDGER_UPDATE

```text
RAW_LEDGER_UPDATE
- actor: claude-sonnet-4-6
- task: stage0 — restore measurement validity for local custom-eval board
- event_type: bug_fix
- summary: Fixed path-resolution bug in run_custom_eval_board.py that caused invalid_launch
  for all rows whenever --output-root is a repo-relative path. Added regression test and
  model-route launch preflight.
- root_cause: stage_attempt_workspace() did not resolve output_root to absolute before
  deriving staged_pack_root, candidate_root, trace_path, and outputs_root.  When those
  paths were passed as cwd and argv to subprocess.run, Python resolved the relative argv
  script against the relative cwd and produced a duplicated path like
  `.../pack/grader/tracking/.../pack/grader/grade.py` that did not exist → OSError →
  invalid_launch for every row.
- fix: Added `output_root = output_root.resolve()` at the top of stage_attempt_workspace()
  (tools/run_custom_eval_board.py line ~338).  All derived paths are now absolute before
  any subprocess is launched.  Absolute --output-root paths are unaffected.
- files_changed:
  - tools/run_custom_eval_board.py (fix: output_root.resolve() in stage_attempt_workspace;
    added _preflight_model_route(); wired preflight into main())
  - tests/test_run_custom_eval_board.py (new test: test_repo_relative_output_root_does_not_cause_invalid_launch)
- before: all 7 rows on local_custom_eval_scoreable_core_v1.yaml returned invalid_launch
  when --output-root was a relative path (e.g. tracking/local_runs/...)
- after: all 7 rows return attempt_completed with real grader verdicts (failed/passed)
  for both relative and absolute --output-root paths
- evidence_paths:
  - verification run: repo-relative output-root, all 7 rows → attempt_completed/failed
  - pytest: 84 passed (0 failed), includes new regression test
- pytest_count: 84 passed
- confidence: high
- no_model_run_performed: true
```
