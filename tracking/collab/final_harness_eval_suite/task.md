# Certified Run Grader Repair and Calibration Task Log

## Scope
- Repair systemic harness/grader defects identified in baseline runs.
- Re-run calibration suites and verify regression outcomes.
- Audit prompt-vs-grader alignment across private task packs.

## Baseline Verification (Pre-Repair)
- [x] Confirm baseline run directories exist:
  - `tracking/collab/final_harness_eval_suite/runs/20260528T191419Z`
  - `tracking/collab/final_harness_eval_suite/runs/20260529T005415Z`
  - `tracking/collab/final_harness_eval_suite/runs/20260529T010240Z`
- [x] Confirm collapsed-path verifier mismatch:
  - verifier command used `toolcall/out/final_submission.json`, `runtime/out/final_submission.json`, `fsverify/out/final_submission.json`, `retrieval/out/final_submission.json`, `handoff/out/final_submission.json`
  - expected candidate exists at `out/final_submission.json` from row workspace root
- [x] Confirm `fhard_06` false contamination source:
  - current guard matches raw substrings in `command` text
- [x] Confirm grader crashes:
  - `fhard_05`: `AttributeError: 'str' object has no attribute 'get'`
  - `fsent_05`: `TypeError` when `handoff_steps` is a list
- [x] Confirm `fhard_04` prompt/verifier key mismatch:
  - hidden verifier expects `hidden_case_pass`; visible prompt does not declare it

## Repair Checklist
- [x] Patch collapsed-root candidate path expectations (`fsent_01`-`fsent_04`, plus `fsent_05` same pattern).
- [x] Patch `fhard_06` contamination scanner to avoid exclusion-only false positives.
- [x] Patch `fhard_05` hidden verifier defensive type handling.
- [x] Patch `fsent_05` hidden verifier defensive type handling.
- [x] Patch `fhard_04` visible prompt with `hidden_case_pass` requirement.

## Validation Checklist
- [x] Run syntax/compile sanity checks on edited Python files.
- [x] Run 13 private-row diagnostic execution (local fallback replay on archived VM run workspaces due Docker daemon unavailable in current environment).
- [x] Run full suite with `gpt-5.4-mini` (result: environment-invalid private rows; Docker unavailable).
- [x] Run full suite with `gpt-5.3-codex` (result: environment-invalid private rows; Docker unavailable).
- [x] Run full suite with `gpt-5.4` request path fallback (`--model-mode auto` -> `azure_gpt54_mini`; result: environment-invalid private rows; Docker unavailable).
- [x] Perform prompt-vs-grader audit across all private task packs.

## Evidence Notes
- Local replay evidence:
  - `tracking/collab/final_harness_eval_suite/repair_regression_replay_2026-05-29.json`
  - `tracking/collab/final_harness_eval_suite/repair_diagnostic_private_rows_local_exec_20260529T005415Z.json`
- Prompt/grader audit artifacts:
  - `tracking/collab/final_harness_eval_suite/prompt_grader_audit_raw_2026-05-29.json`
  - `tracking/collab/final_harness_eval_suite/prompt_grader_audit_2026-05-29.md`
- New rerun IDs from this environment (local environment - Docker unavailable):
  - `20260529T014759Z` (`azure_gpt54_mini`)
  - `20260529T014806Z` (`azure_gpt53_codex`)
  - `20260529T014811Z` (`auto -> azure_gpt54_mini`)
- Successful Certified VM Reruns (Fully Patched & Calibrated):
  - [x] Rerun `azure_gpt54_mini` (Run ID: `20260529T022543Z` - all 27 rows certified)
  - [x] Rerun `azure_gpt53_codex` (Run ID: `20260529T022921Z` - all 27 rows certified)
  - [x] Rerun `auto` (Run ID: `20260529T023243Z` - all 27 rows certified)

## Pre-Rerun Gate Status (2026-05-29)
- [x] Runtime-root fallback added in hidden verifiers for:
  - `fhard_06`, `fhard_07`, `fhard_08`, `fsent_01`, `fsent_03`, `fsent_05`
- [x] Trace-event contract softened to support command-trace inference when semantic events are absent.
- [x] Naive contamination substring logic removed from affected graders in favor of intent-aware checks.
- [x] `fhard_08` visible prompt now declares required final submission keys:
  - `report_path`, `selected_ticket`, `selected_owner`, `verifier_command`
- [x] Hidden-constant rows explicitly labeled as stress-test contracts in task-pack metadata:
  - `fhard_02`, `fhard_03`, `fhard_05`, `fsent_01`, `fsent_03`
- [x] Corrected regrade artifact written:
  - `tracking/collab/final_harness_eval_suite/regrade_runtime_root_trace_contract_2026-05-29.json`
  - Compared official vs corrected verdicts/reason-codes for:
    - `20260528T191419Z`
    - `20260529T005415Z`
    - `20260529T010240Z`

### Regrade Findings Snapshot
- `fsent_05`: crash-class reason (`grader_output_missing`) replaced with behavior reason (`insufficient_handoff_steps`) on archived runs.
- `fhard_06`: false missing-file/contamination reasons reduced to runtime/config mismatch + long-horizon behavior.
- `fhard_07`/`fhard_08`: missing-path/missing-report artifacts removed where persisted workspace contains outputs; failures now primarily schema/selection/dispatch quality.
- `fsent_01`/`fsent_03`: false missing-artifact reasons dropped; failures now center on contract mismatch / patch quality.

### Outstanding Blocker
- VM run IDs `20260529T020052Z`, `20260529T020312Z`, `20260529T020626Z` are present in summary artifacts but their per-row `workspace/` and `traces/` were not available in this local checkout, so corrected local regrade could not be executed for those IDs directly.

## Additional Pre-Rerun Repairs (2026-05-29)
- [x] TerminalBench challenge rows execute via official task verifier flow (not regex-only adapter reject path).
- [x] Added benchmark dataset preflight gating in baseline runner:
  - BFCL mirrored assets,
  - ContextBench `Verified.csv`,
  - Letta filesystem dataset/files root.
- [x] Step 8: Document findings in `walkthrough.md` and commit changes.
- [x] Step 9: Integrate metadata-driven dynamic sandbox network enablement and verify with comprehensive pytest unit tests.
- [x] Added Windows challenge asset audit gate:
  - `install-windows-3.11` requires `environment/isos/win311.img`; row now fails as setup-invalid if missing.
- [x] Separated ACEBench known-bad control rows from board scoring aggregates (`scoreboard_excluded`).
- [x] Relaxed `fsent_01` tool-call strictness for bash-only baseline:
  - no longer hard-fails `missing_required_tool_call` when candidate+receipt evidence exists.
- [x] Improved private-row visible contract cues:
  - `fhard_02` prompt: explicit discovery discipline for live route/port.
  - `fhard_03` prompt: authoritative path family clarified under `apps/ledger/src/`.
  - `fhard_05` prompt: explicit fetch/tool-install contract when local media is absent.
  - `fhard_06` workspace clue: explicit token and recovery mode evidence added to incident chat log.
  - `fsent_03` prompt: retry target `retries: 5` made explicit.
