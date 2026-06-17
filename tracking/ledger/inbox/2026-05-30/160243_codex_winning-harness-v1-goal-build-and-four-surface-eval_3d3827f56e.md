# Raw Ledger Update

- recorded_at_utc: 2026-05-30T16:02:43.983487+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: winning_harness_v1_goal_build_and_four_surface_eval
- event_type: experiment
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 3d3827f56e8efa32ddd430539be826cd0287f992604b588dc8c9664827586d7f
- commit_message: HOLD - winning_harness_v1 eval bundle regressed across all required surfaces; needs targeted repair lane before promotion
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-05-30/160243_codex_winning-harness-v1-goal-build-and-four-surface-eval_3d3827f56e.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: winning_harness_v1_goal_build_and_four_surface_eval
- event_type: experiment
- summary: Implemented winning_harness_v1 route variant per synthesis spec, executed VM-certified eval bundle across family/private/benchmark/terminalbench surfaces, and collected scored artifacts.
- observations: |
    - Variant wiring completed in packet06 phase6 scope with winning_harness_v1 doctrine and runtime surface composition (service_contract_first_receipt_closure + lean_pty_loop + evidence_report_scaffold + closure_truth_gate + lean_autopsy).
    - VM run roots: private=20260530T155658Z, benchmark=20260530T155737Z, terminalbench=20260530T155809Z.
    - Family board totals: pass=0 fail=31 invalid=4 (35 total).
    - Private rows: pass=0 fail=13 invalid=0; dominant reason grader_output_missing.
    - Benchmark rows: pass=0 fail=12 invalid=0; dominant reasons bfcl_state_mismatch, acebench_wrong_output_format, contextbench_* mismatch/no_final_answer, letta_ground_truth_mismatch.
    - TerminalBench rows (ftb_challenge_extract_moves_from_video, ftb_challenge_install_windows_3_11): pass=0 fail=2 invalid=0, both terminalbench_verifier_failed.
- inference: |
    winning_harness_v1 as currently implemented is not promotable and regresses relative to prior paid baselines; failure profile is capability/output failure rather than environment invalidity.
- evidence_paths:
    - tracking/collab/final_harness_eval_suite/reviews/winning_harness_v1_goal_closeout_2026-05-30.md
    - tracking/collab/final_harness_eval_suite/reviews/winning_harness_v1_vm_eval_summary_2026-05-30.json
    - tracking/collab/final_harness_eval_suite/runs/20260530T155658Z/scoreboard.json
    - tracking/collab/final_harness_eval_suite/runs/20260530T155737Z/scoreboard.json
    - tracking/collab/final_harness_eval_suite/runs/20260530T155809Z/scoreboard.json
    - tracking/collab/eval_suite_v1_baseline/certified_runs/scoreboard.json
    - /private/tmp/winning_harness_v1_vm_eval/winning_harness_v1_vm_eval_summary_2026-05-30.json
    - /private/tmp/winning_harness_v1_vm_eval/family_scoreboard.json
    - /private/tmp/winning_harness_v1_vm_eval/20260530T155658Z_result_rows.jsonl
    - /private/tmp/winning_harness_v1_vm_eval/20260530T155737Z_result_rows.jsonl
    - /private/tmp/winning_harness_v1_vm_eval/20260530T155809Z_result_rows.jsonl
- affected_components:
    - blocks/orientation/phase6_doctrine.py
    - runner/packet04_route_manifest.py
    - tools/run_final_harness_eval_suite_baseline.py
    - scripts/run_winning_harness_v1_eval_bundle.sh
    - tracking/collab/final_harness_eval_suite/reviews/winning_harness_v1_goal_closeout_2026-05-30.md
- decision_change: HOLD winning_harness_v1 promotion pending targeted repair lane evidence.
- unresolved_questions:
    - Which minimal repair should be first: private grader-output-missing lane vs BFCL native call semantics lane?
    - Should winning_harness_v1 compose contract_classifier/native toolcall surfaces before next rerun?
- confidence: high
- commit_message: HOLD - winning_harness_v1 eval bundle regressed across all required surfaces; needs targeted repair lane before promotion
```
