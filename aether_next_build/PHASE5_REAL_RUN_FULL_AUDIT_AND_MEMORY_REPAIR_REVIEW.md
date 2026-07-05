# Phase 5 Real Run Full Audit And Memory Repair Review

Generated: 2026-06-30

## Authority Surface

This audit is based on the actual local run artifacts and the uploaded memory-loop repair bundle, not on summary prose alone.

### Current local run evidence

- Build tree: `/Users/mohamud/Downloads/harnesseng/aether_next_build`
- Phase 5 result row file: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_results_20260630_001742.json`
- Phase 5 summary: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_phase5_summary.json`
- Phase 5 report: `/Users/mohamud/Downloads/harnesseng/aether_next_build/NARROW_REAL_TASK_REPORT.md`
- Final state report: `/Users/mohamud/Downloads/harnesseng/aether_next_build/FINAL_PHASE_1_TO_6_STATE.md`
- Traces:
  - `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_traces_20260630_001742/filter-js-from-html.trace.json`
  - `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_traces_20260630_001742/sparql-university.trace.json`
  - `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_traces_20260630_001742/openssl-selfsigned-cert.trace.json`
- Snapshots:
  - `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_snapshots_20260630_001742/filter-js-from-html/final/filter.py`
  - `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_snapshots_20260630_001742/sparql-university/final/university_graph.ttl`

### Uploaded repair evidence

- Repair zip: `/Users/mohamud/Downloads/aether_next_build_memory_loop_repair.zip`
- Repair audit: `/Users/mohamud/Downloads/aether_memory_loop_repair_audit.md`
- Scratch unpack used for audit: `/tmp/aether_memory_loop_repair_audit/aether_next_build`
- Zip SHA-256: `57301129dcadb7f1d97ca4fe3003a4505e56d38a9b26664a5de0713b5474b71e`

## Scoreboard And Validity

| task | status | reward | classifier | step | receipts | validation status |
|---|---:|---:|---|---:|---:|---|
| filter-js-from-html | incomplete | 0.0 | model_limit | 8 | 6 | valid failed row |
| sparql-university | incomplete | 0.0 | harness_context_failure | 8 | 3 | valid failed row |
| openssl-selfsigned-cert | incomplete | 0.0 | harness_context_failure | 8 | 8 | valid failed row |

Run configuration from current Phase 5 summary:

- `architect_mode=workbench`
- `effort=low`
- `max_steps=8`
- `run_timeout_s=30`

Interpretation: these are valid bounded diagnostic rows, not proof of final task-solving capability. They are enough to diagnose loop/control failures.

## Architect Audit

### Isolated architect eval

From `/Users/mohamud/Downloads/harnesseng/aether_next_build/architect_isolated_eval_phase2_summary.json`:

- 5.4-mini primary after focused repair: 5/5 parseable, warnings=0, rejected_items=0, query_memory_available=5/5.
- 5.3-codex comparison: 3/3 parseable, warnings=0, rejected_items=0, query_memory_available=3/3.

Verdict: architect parseability and isolated prompt/config generation were good after the token-cap repair.

### Real narrow-task architect behavior

In the real task traces, Workbench config did reach the solver. Evidence: every trace has `[solver_identity]`, `[action_schema]`, and `[config_realization]` prefix messages.

Common real-run configuration observations:

- `context_policy_mode`: `retrieval_augmented`
- `model_verifier_policy.enabled`: true
- `tools_visible_to_solver`: includes `query_memory`, `read_file`, `write_file`, `inspect_checks`, `run_check`, `query_artifact_history`, `inspect_diff`, `record_observation`, `register_candidate`, `run_experiment`
- `capabilities_realized`: `['filesystem']` for all three tasks
- `checks_compiled`: empty for all three tasks
- `checks_declared`: empty for all three tasks

Verdict: Workbench boot/config worked mechanically, but architect quality was mixed in real tasks.

Strong:

- task-specific success definitions existed;
- solver prompts were task-specific and verification-first;
- local verification limits were included;
- model verifier policy was configured.

Weak:

- all three real configs had empty check plans;
- OpenSSL selected only `filesystem`, even though the task requires shell/OpenSSL execution;
- memory guidance over-biased initial query_memory usage, especially SPARQL;
- kernel-internal tools like `run_experiment` were visible even when only filesystem capability was selected.

## Harness Configuration Audit

### What worked

- `architect_mode=workbench` reached the normal runner path.
- HarnessConfigIR was compiled into RuntimeConfigIR.
- Solver prompt was inserted and visible in `[solver_identity]`.
- Runtime action schema was visible in `[action_schema]`.
- Config realization included success definition, local verification limits, tool visibility, verifier policy, and context mode.

### What did not work well enough

- No task-specific checks were compiled or declared in the real rows.
- The solver was allowed to keep running memory/read loops with no verifier intervention.
- Reconfiguration did not recover missing process capability in OpenSSL. The trace recorded `reconfigure_validation` failure: `missing_bootstrap_substrate; missing_helper_tool_substrate`.
- Internal verifier was configured but did not fire in these real runs.

## Solver Step Reconstruction

### filter-js-from-html

Result: `incomplete`, reward 0.0, classifier `model_limit`, step 8.

| step | label | actions | observations | assessment |
|---:|---|---|---|---|
| 0 | useful_setup but memory-first | `query_memory` | `a1:query`, 0 matches | Legit but unnecessary as first action on fresh task. |
| 1 | evidence_producing + useful_setup | `read_file /app/filter.py`, `write_file /app/filter.py` | read missing, write success | Best step. The solver created an artifact. |
| 2 | no_progress | `query_memory` | no observation recorded | Receipt-id collision likely hid observation. |
| 3 | partial progress but unrecorded | `query_memory`, `write_file /app/filter.py` | no observations recorded | The write may not have been recorded because repeated action IDs collided. |
| 4 | partial progress but unrecorded | `query_memory`, `write_file /app/filter.py` | no observations recorded | Same receipt-id collision risk. |
| 5 | useful signal | `request_reconfigure` | no observation | Parse failure/reconfigure path entered. |
| 6 | evidence_producing | `query_memory`, `read_file /app/filter.py` | read success, 1091 bytes | Retrieved artifact content, but query observation missing. |
| 7 | no_progress | `query_memory`, `read_file /app/filter.py` | no observations recorded | Repetition without state change. |

First decisive divergence: after step 1, the solver had a written artifact but the harness did not move it into a check/verifier/repair loop. It drifted into repeated memory/read/write/reconfigure behavior.

### sparql-university

Result: `incomplete`, reward 0.0, classifier `harness_context_failure`, step 8.

| step | label | actions | observations | assessment |
|---:|---|---|---|---|
| 0 | evidence_producing | `query_memory`, `read_file /app/university_graph.ttl` | query 0 matches, read success 10169 bytes | Read the right primary file. Initial memory query was unnecessary but harmless. |
| 1 | no_progress | `query_memory` | no observation recorded | Memory loop begins. |
| 2 | no_progress | `query_memory` | no observation recorded | Repeated memory call. |
| 3 | no_progress | `query_memory` | no observation recorded | Repeated memory call. |
| 4 | no_progress | `query_memory` | no observation recorded | Repeated memory call. |
| 5 | no_progress | `query_memory` | no observation recorded | Repeated memory call. |
| 6 | no_progress | `query_memory` | no observation recorded | Repeated memory call. |
| 7 | no_progress | `query_memory` | no observation recorded | Repeated memory call. |

First decisive divergence: step 1. After a successful read of the Turtle graph, context/prompt pushed the solver to query memory instead of preserving enough read evidence for it to write `solution.sparql`.

Critical finding: this was not proven to be “solver ignored useful memory.” The trace shows later memory calls produced no observations. The stronger diagnosis is harness/memory-loop design: repeated action IDs such as `a1` caused receipt IDs like `a1:query` to collide, and context did not include a `latest_file_reads` excerpt for the model to act on.

### openssl-selfsigned-cert

Result: `incomplete`, reward 0.0, classifier `harness_context_failure`, step 8.

| step | label | actions | observations | assessment |
|---:|---|---|---|---|
| 0 | evidence_producing | `query_memory`, read `ssl/server.key`, `ssl/server.crt`, `check_cert.py` | query 0 matches, all reads missing | Correctly established artifacts absent. |
| 1 | no_progress | `query_memory` | no observation recorded | Memory loop. |
| 2 | no_progress | `query_memory` | no observation recorded | Memory loop. |
| 3 | no_progress | `query_memory` | no observation recorded | Memory loop. |
| 4 | harmful/invalid | `query_memory`, `read_file /app` | no observation recorded | Reads directory as file; still no build action. |
| 5 | useful signal | `request_reconfigure` | reconfigure invalid later | Correctly noticed missing process execution capability. |
| 6 | evidence_producing | `query_memory` | 4 matches | Memory finally surfaced prior state. |
| 7 | useful diagnostic but not solution | `query_memory`, `run_experiment ls /app /app/ssl` | experiment success | Used kernel/internal experiment despite only filesystem capability. No artifacts built. |

First decisive divergence: architect/config selected only filesystem for a task requiring process/shell/OpenSSL. The solver recognized this at step 5, but reconfiguration failed.

## Verification Audit

### Isolated verifier

Yes, verification was called in isolated Phase 3 experiments.

Evidence:

- `/Users/mohamud/Downloads/harnesseng/aether_next_build/VERIFIER_ONLY_MODEL_EXPERIMENT_REPORT.md`
- `/Users/mohamud/Downloads/harnesseng/aether_next_build/verifier_only_model_phase3_summary.json`
- `/Users/mohamud/Downloads/harnesseng/aether_next_build/VERIFIER_ONLY_54MINI_VALIDATION.md`
- `/Users/mohamud/Downloads/harnesseng/aether_next_build/VERIFIER_ONLY_53CODEX_VALIDATION.md`

5.4-mini verifier-only result: 5/5 parsed, validation PASS, all rows evidence_bound/actionable.

### Real narrow tasks

No, internal verifier was not called in the real bounded Phase 5 rows.

Evidence from all three traces:

- `gate_decisions`: absent/empty
- no `verifier_packet` in trace
- no `model_verifier_result` receipt
- no active verifier findings

Reason: solver never reached a submit/success/failure candidate path that calls the verifier. It stopped by max-step/incomplete path. External grader was attempted after kernel completion and timed out at the bounded 30s setting, but that is not the internal verifier.

## Uploaded Memory-Loop Repair Review

The uploaded repair zip was unpacked and tested in `/tmp/aether_memory_loop_repair_audit/aether_next_build`.

### Independent validation run during this audit

- `python3 -m pytest -q tests/test_memory_loop_fixes.py` -> 3 passed
- `python3 -m pytest -q tests/test_memory_loop_fixes.py tests/test_chatgpt_broad_slice.py tests/test_chatgpt_integration_scenarios.py tests/test_vnext_memory_context_verifier.py` -> 48 passed
- `python3 -m pytest -q --ignore=tests/test_docker_runner.py` -> 195 passed
- `python3 -m compileall -q aether_next` -> passed
- fake verifier-only run + validator -> ok=true

### What the repair changes

- Step-scoped action receipts: `step-0:a1:query`, `step-1:a1:query`, etc.
- `query_memory` records `no_new_evidence` and guidance when empty/same.
- Previous `query_memory` receipts are excluded from normal memory hits unless explicitly requested.
- Context includes `latest_file_reads` with path/hash/bytes/excerpt.
- Context includes `memory_loop_feedback` after repeated empty/no-new-evidence queries.
- Stable prompt/manual guidance says query_memory is not a mandatory first action on fresh tasks.

### Review verdict

The repair is well targeted to the observed SPARQL memory-loop failure. It should be integrated as a source/test patch, not as a blind replacement of the current tree, because the zip omits many generated evidence directories present locally.

## Root Cause Map

| failure | primary class | component | evidence | confidence |
|---|---|---|---|---|
| SPARQL memory loop | no_progress_control / evidence_ledger | receipt IDs + context memory | repeated `a1 query_memory`; no later observations; no `solution.sparql` write | high |
| OpenSSL no build | prompt_task_contract + tool/config realization | architect capability selection | `capabilities_realized=['filesystem']`; task needs shell/OpenSSL; reconfigure invalid | high |
| Verifier not called live | completion_semantics / verifier lifecycle | kernel completion/verifier trigger | no verifier packet/result/gate decision in real traces | high |
| Filter incomplete | model_limit + no_progress_control | solver loop/check gating | wrote file then repeated memory/read/reconfigure, no checks/verifier | medium |
| Empty check plans | verifier/check realization | Workbench config/check compiler | `checks_compiled=[]`, `checks_declared=[]` in all traces | high |

## Plan

### Immediate next slice: integrate memory-loop repair

1. Back up current `aether_next_build` because it contains generated evidence not present in the uploaded zip.
2. Apply only source/test/doc changes from `/Users/mohamud/Downloads/aether_next_build_memory_loop_repair.zip`.
3. Preserve current run artifacts:
   - `narrow_real_task_traces_20260630_001742/`
   - `narrow_real_task_snapshots_20260630_001742/`
   - Phase 2/3/4/5 reports and verifier bundles.
4. Run:
   - `python3 -m pytest -q tests/test_memory_loop_fixes.py`
   - `python3 -m pytest -q --ignore=tests/test_docker_runner.py`
   - `python3 -m compileall -q aether_next`
   - fake verifier-only validation.

### Rerun exactly the three narrow tasks

Use the integrated repair and run only:

- `filter-js-from-html`
- `sparql-university`
- `openssl-selfsigned-cert`

Recommended run config:

- `architect_mode=workbench`
- `max_steps=24` or `30`
- `run_timeout_s` high enough for grader, but consider preserving the grader-timeout row behavior if grader hangs.
- trace/snapshot capture enabled.

Audit questions for rerun:

- Does SPARQL still call `query_memory` at step 0?
- After the Turtle read, does context include `latest_file_reads` with an excerpt?
- If repeated memory calls happen, does `memory_loop_feedback` appear?
- Does SPARQL write `solution.sparql`?
- Does OpenSSL architect select shell/run_command or recover via reconfigure?
- Does internal verifier get called on submit/failure/no-progress?

### Next fix lane after rerun

Do not jump to promotion. Based on current evidence, the next likely fixes are:

1. Add verifier-on-incomplete/no-progress packet path.
2. Improve architect capability selection so tasks requiring process execution select shell/run_command.
3. Make reconfiguration either actually recover missing substrate or stop presenting it as a recovery path.
4. Create non-empty safe check plans where visible smoke/check specs can be compiled.
5. Gate repeated empty `query_memory` turns after memory-loop feedback appears.

## Bottom Line

The uploaded memory-loop repair is real and tests green in isolation. It directly addresses the SPARQL trace failure. The current full harness still is not proven end-to-end: real narrow tasks failed, live verifier was not called, check plans were empty, and OpenSSL was misconfigured. The next correct action is to integrate the memory-loop repair carefully, rerun the same three tasks, and then diagnose the remaining failure classes from new traces.
