# Phase 5 Rerun After Memory, Verifier, and Stable-Core Tool Repair

Date: 2026-06-30

## Executive Conclusion

This slice completed the deterministic repair work and ran the required narrow three-task rerun, then incorporated the requested `stable_core_tools` variant and reran the same three tasks again.

Outcome:

- Deterministic gates are green.
- Memory-loop repair is integrated.
- Workbench Architect no longer hard-hides stable core tools merely because it omits them.
- `run_command` is solver-visible in Workbench stable-core mode.
- `query_memory`, `query_artifact_history`, `inspect_diff`, `record_observation`, `inspect_checks`, and `run_check` remain visible.
- `register_candidate` and `run_experiment` are not exposed as normal solver-facing tools.
- Incomplete/max-step/no-progress paths now build model-verifier packets.
- Real stable-core rerun did call verifier on incomplete rows.
- Stable-core rerun did not improve the three-task score: `0/3` rewarded.

Do not promote this variant from these rows. It fixed one harness brittleness, but the live run exposed remaining loop-control, substrate-awareness, and verifier/actionability weaknesses.

## Evidence Paths

- Build tree: `/Users/mohamud/Downloads/harnesseng/aether_next_build`
- Memory repair source zip: `/Users/mohamud/Downloads/aether_next_build_memory_loop_repair.zip`
- Pre-repair Phase 5 rows: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_results_20260630_001742.json`
- Intermediate rerun before live verifier hook: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_results_20260630_024030.json`
- Intermediate traces: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_traces_20260630_024030/`
- Stable-core rerun rows: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_results_20260630_043152.json`
- Stable-core traces: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_traces_20260630_043152/`
- Stable-core final snapshots: `/Users/mohamud/Downloads/harnesseng/aether_next_build/narrow_real_task_snapshots_20260630_043152/`
- Stable-core verifier validation: `/Users/mohamud/Downloads/harnesseng/aether_next_build/VERIFIER_ONLY_FAKE_STABLE_TOOLS_VALIDATION.md`

## Source/Test Changes

Integrated memory-loop repair:

- Step-scoped receipt IDs for kernel-owned actions.
- `query_memory` no-new-evidence guidance.
- Prior `query_memory` receipts excluded from default evidence.
- `latest_file_reads` and `memory_loop_feedback` added to context.
- Runtime guidance changed so `query_memory` is not a mandatory first action.

Added verifier lifecycle hardening:

- Incomplete/max-step/no-progress/blocked paths invoke verifier when policy allows.
- Verifier packets include recent actions, latest file reads, memory-loop feedback, failed/empty checks, success definition, local verification limits, config realization, active findings, and changes since findings.
- `ModelHooks.verify()` added.
- Verifier packet is persisted before model call as `model_verifier_packet`.
- Verifier model failures/timeouts are recorded as `model_verifier_error` instead of crashing/hanging silently.
- Provider polling timeout can be controlled with `AETHER_MODEL_POLL_TIMEOUT_S`.

Added `stable_core_tools` variant:

- Workbench Architect `tool_policy` is now advisory for core tools.
- Compiler exposes stable core tools in Workbench path unless the environment/safety layer prevents them.
- `config_realization` records:
  - `tool_policy_mode = stable_core`
  - `architect_tool_selection_applied = false`
  - `architect_tool_guidance_recorded = true`
  - `tools_visible_to_solver`
  - `tools_runtime_allowed`
  - `tools_audit_separately = ["register_candidate", "run_experiment", "reconfigure"]`
- `register_candidate` and `run_experiment` are no longer accidentally exposed in the normal solver action schema.

Primary files changed:

- `aether_next/compiler.py`
- `aether_next/context_compiler.py`
- `aether_next/execution.py`
- `aether_next/integration_scenarios.py`
- `aether_next/kernel.py`
- `aether_next/kernel_actions.py`
- `aether_next/kernel_verifier.py`
- `aether_next/memory_query.py`
- `aether_next/model_hooks.py`
- `aether_next/providers/azure_model.py`
- `aether_next/run_adapter.py`
- `aether_next/runtime_manual.py`
- `aether_next/verifier_packets.py`
- `aether_next/workbench_compile.py`
- `aether_next/workbench_hooks.py`
- `tests/test_memory_loop_fixes.py`
- `tests/test_model_hooks.py`
- `tests/test_vnext_workbench_ir.py`
- `tests/test_vnext_configurability.py`
- `tests/test_vnext_memory_context_verifier.py`
- `tests/test_chatgpt_integration_scenarios.py`
- `tests/test_kernel.py`
- `tests/test_kernel_config.py`

## Exact Validation Commands

Memory repair gate:

```text
python3 -m pytest -q tests/test_memory_loop_fixes.py
python3 -m pytest -q --ignore=tests/test_docker_runner.py
python3 -m compileall -q aether_next
python3 run_verifier_only_eval.py --mode fake --out-dir verifier_only_eval_fake_memory_repair_check
python3 validate_verifier_only_eval.py verifier_only_eval_fake_memory_repair_check --report VERIFIER_ONLY_FAKE_MEMORY_REPAIR_VALIDATION.md
```

Observed:

```text
3 passed
195 passed
compileall passed
fake verifier validation ok=true
```

After verifier hook/timeout repair:

```text
python3 -m pytest -q tests/test_model_hooks.py tests/test_vnext_memory_context_verifier.py
python3 -m pytest -q --ignore=tests/test_docker_runner.py
python3 -m compileall -q aether_next
```

Observed:

```text
50 passed
202 passed
compileall passed
```

Stable-core gate:

```text
python3 -m pytest -q --ignore=tests/test_docker_runner.py
python3 -m compileall -q aether_next
python3 run_verifier_only_eval.py --mode fake --out-dir verifier_only_eval_fake_stable_tools_check
python3 validate_verifier_only_eval.py verifier_only_eval_fake_stable_tools_check --report VERIFIER_ONLY_FAKE_STABLE_TOOLS_VALIDATION.md
```

Observed:

```text
204 passed
compileall passed
VERIFIER_ONLY_FAKE_STABLE_TOOLS_VALIDATION.md: PASS
```

## Rerun Commands

Intermediate rerun before live verifier hook was wired:

```text
python3 run_pilot.py \
  --tasks filter-js-from-html,sparql-university,openssl-selfsigned-cert \
  --architect-mode workbench \
  --max-steps 30 \
  --run-timeout-s 300 \
  --trace-dir narrow_real_task_traces_20260630_024030 \
  --snapshot-dir narrow_real_task_snapshots_20260630_024030 \
  --out narrow_real_task_results_20260630_024030.json
```

Stable-core rerun:

```text
AETHER_MODEL_POLL_TIMEOUT_S=240 AETHER_MODEL_POLL_INTERVAL_S=5 AETHER_MODEL_VERIFIER_TIMEOUT_S=60 python3 run_pilot.py \
  --tasks filter-js-from-html,sparql-university,openssl-selfsigned-cert \
  --architect-mode workbench \
  --effort low \
  --max-steps 30 \
  --run-timeout-s 300 \
  --trace-dir narrow_real_task_traces_20260630_043152 \
  --snapshot-dir narrow_real_task_snapshots_20260630_043152 \
  --out narrow_real_task_results_20260630_043152.json
```

## Scoreboard Comparison

| run | filter-js-from-html | sparql-university | openssl-selfsigned-cert | total |
|---|---:|---:|---:|---:|
| old Phase 5 `20260630_001742` | 0.0 incomplete/model_limit | 0.0 incomplete/harness_context_failure | 0.0 incomplete/harness_context_failure | 0/3 |
| pre-stable-core rerun `20260630_024030` | 0.0 completed/false-clean | 0.0 incomplete/harness_context_failure | 1.0 completed | 1/3 |
| stable-core rerun `20260630_043152` | 0.0 incomplete/model_limit | 0.0 incomplete/substrate_missing | 0.0 incomplete/harness_context_failure | 0/3 |

Official grader remains the authority. The stable-core rerun is not a performance improvement.

## Architect / Harness Config Audit

Stable-core tool visibility worked in all three traces:

- `filter-js-from-html`: architect/runtime capabilities `["filesystem", "shell"]`; action schema included `run_command`; `register_candidate` and `run_experiment` absent.
- `sparql-university`: architect/runtime capabilities `["filesystem", "shell"]`; action schema included `run_command`; `register_candidate` and `run_experiment` absent.
- `openssl-selfsigned-cert`: architect/runtime capabilities `["filesystem", "shell"]`; action schema included `run_command`; `register_candidate` and `run_experiment` absent.

`config_realization`/prefix evidence recorded:

- `architect_tool_selection_applied: false`
- `run_command` present in solver-visible tools.
- Internal experiment/candidate tools absent from `[action_schema]`.

The stable-core variant fixed the OpenSSL-style hard-tool-hiding failure class. It did not solve solver loop quality.

## Task Deep Dives

### filter-js-from-html

Result:

- Stable-core row: reward `0.0`
- Status: `incomplete`
- Classifier: `model_limit`
- Step: `30`
- Grader: timed out after `300s`

Architect behavior:

- Selected/realized shell and filesystem.
- No compiled check plan.
- Local verification limit noted that local checks cannot prove full XSS safety or exact formatting preservation.

Solver behavior:

- Used `run_command` at step 0 to inspect files.
- Wrote `filter.py` repeatedly.
- Used `query_memory` 11 times, `write_file` 16 times, `run_command` 3 times, `read_file` 3 times.
- Reached ready gate twice in trace steps 14 and 16, but final row still ended incomplete at max steps.

Verifier:

- Fired at max steps.
- Receipts include:
  - `step-30:model_verifier_packet:max_steps`
  - `step-30:model_verifier`
- Verdict: `uncertain_missing_evidence`.

Grader truth:

- Grader timed out after 300s. This row is not scoreable as a capability win.

Primary failure class:

- `model_capability` / `completion_semantics` contributor.
- The solver churned on artifact variants and never produced a grader-backed success.

### sparql-university

Result:

- Stable-core row: reward `0.0`
- Status: `incomplete`
- Classifier: `substrate_missing`
- Step: `30`
- Grader failed because `/app/solution.sparql` was missing.

Architect behavior:

- Stable-core exposed `run_command`.
- No compiled check plan.
- Local verification limits correctly noted that file inspection alone cannot prove query result correctness.

Solver behavior:

- Step 0 read `university_graph.ttl`.
- `latest_file_reads` appeared in context on 29 steps.
- Step 1 attempted a Python command to inspect graph terms, but it failed with `missing_capability`/exit 127 because `python` was unavailable in the container.
- After that, solver fell into repeated `query_memory` behavior: 28 `query_memory` receipts, 2 `read_file`, 2 `run_command`, 2 `query_artifact_history`.
- It never wrote `/app/solution.sparql`.

Verifier:

- Fired at no-progress/max-step boundary.
- Receipts include:
  - `step-30:model_verifier_packet:no_progress`
  - `step-30:model_verifier`
- Verdict: `uncertain_missing_evidence`.
- No active finding reached a later solver context because the verifier fired at terminal max step.

Grader truth:

- Official tests failed:
  - `test_sparql_file_exists`
  - `test_sparql_runs_without_error`
  - `test_sparql_query_results`
- Root visible symptom: `/app/solution.sparql` missing.

Primary failure class:

- `tool_contract_execution` / `substrate_missing`, with `no_progress_control` contributor.
- Stable core allowed shell, but the task environment lacked the exact `python` command the solver chose. The harness surfaced the failed command but did not force a strategy change or earlier verifier repair loop.

### openssl-selfsigned-cert

Result:

- Stable-core row: reward `0.0`
- Status: `incomplete`
- Classifier: `harness_context_failure`
- Step: `30`
- Official grader: 5 passed, 1 failed.

Architect behavior:

- Stable-core exposed shell and filesystem.
- No compiled check plan in the final stable-core row.
- Local verification limits mentioned file presence, permissions, cert metadata, and script output limitations.

Solver behavior:

- Used `run_command` heavily: 31 command receipts.
- Repeated workspace inspection across most steps.
- Final snapshot contains:
  - `ssl/server.key`
  - `ssl/server.crt`
  - `ssl/server.pem`
  - `ssl/verification.txt`
  - `ssl/openssl.cnf`
  - `check_cert.py`
- The final checker imports `cryptography`.

Verifier:

- Fired at max steps.
- Receipts include:
  - `step-30:model_verifier_packet:max_steps`
  - `step-30:model_verifier`
- Verdict: `completed`.

Grader truth:

- Official grader failed `test_python_verification_script`.
- Failure:
  - `ModuleNotFoundError: No module named 'cryptography'`
- The verifier gave a false clean: it judged the packet as completed even though the checker depended on a package absent from the grader/runtime environment.

Primary failure class:

- `verifier_evidence_classifier` and `tool_contract_execution`.
- The verifier did not catch that `check_cert.py` relied on an unavailable dependency. The solver also repeated inspection and failed to run the exact final checker under the grader-equivalent Python environment.

## Verifier / Grader Agreement

| task | verifier fired? | verifier verdict | grader/reward | agreement |
|---|---:|---|---|---|
| filter-js-from-html | yes | uncertain_missing_evidence | timeout, reward 0.0 | verifier cautious; grader invalid/failed |
| sparql-university | yes | uncertain_missing_evidence | failed missing file, reward 0.0 | verifier broadly aligned |
| openssl-selfsigned-cert | yes | completed | failed checker dependency, reward 0.0 | false clean |

The verifier lifecycle is now mechanically active, but verifier judgment is not yet reliable enough for promotion.

## Acceptance Questions

Does OpenSSL now have `run_command` available?

- Yes. Stable-core action schema includes `run_command`, and OpenSSL trace has 31 `run_command` receipts.

Does solver use shell/OpenSSL when appropriate?

- Partially. It used shell heavily and generated certificate artifacts, but it repeated inspection and produced a dependency-fragile `check_cert.py`.

Does SPARQL avoid repeated empty memory loops?

- No. The loop changed shape: query results were not empty, but repeated `query_memory` still dominated after a failed `python` command. This is still a no-progress loop.

Does latest_file_reads appear after TTL read?

- Yes. SPARQL had `latest_file_reads` in context on 29 steps after reading `university_graph.ttl`.

Does verifier fire on submit/no-progress/max-steps/blocked state?

- Yes for incomplete terminal rows in stable-core rerun. All three stable-core rows produced `model_verifier_packet` and `model_verifier` receipts at step 30.

Do active findings enter context?

- Not in the stable-core real rows. The verifier fired only at terminal max-step, so there was no subsequent solver turn to consume active findings. Deterministic tests prove active findings can enter context in a repair loop, but this real rerun did not exercise that loop after verifier output.

Are tool docs and runtime-callable tools identical?

- Deterministic tests assert equality between `tools_visible_to_solver` and `tools_runtime_allowed`.
- Stable-core traces show `run_command` present in `[action_schema]` and internal `register_candidate`/`run_experiment` absent.

## What Improved

- Workbench hard tool selection no longer cripples execution-capable tasks.
- Query/file-read evidence is visible in context.
- Verifier packets are actually emitted in real incomplete rows.
- Verifier model failures/timeouts are now evidence-bearing rather than silent hangs.
- Stable-core tests protect core tool visibility and internal tool non-exposure.

## What Remains Broken

- No-progress control is too weak: SPARQL kept querying memory after enough file evidence existed.
- Verifier repair loop is too late: verifier fired at terminal max step, so active findings did not get used for repair.
- Verifier classifier can be false-clean: OpenSSL verifier returned `completed` despite missing `cryptography`.
- Check-plan quality remains weak: stable-core rows had no useful compiled checks for SPARQL/OpenSSL final semantic validation.
- Solver can choose non-portable substrate commands (`python` instead of `python3`, `cryptography` dependency) without the harness forcing environment-aware repair.

## Recommended Next Slice

Do not run a broad board.

Next deterministic slice should target:

1. Earlier verifier/no-progress trigger before max step, with a repair turn budget.
2. Substrate-aware command feedback: failed `python` should suggest `python3`/available interpreter discovery or discourage repeated memory queries.
3. Verifier packet must include final artifact dependency/import checks when scripts are deliverables.
4. Add deterministic homologs:
   - repeated memory query after successful file read;
   - command missing but alternative interpreter available;
   - verifier false-clean on script importing missing dependency;
   - stable-core tools visible while internal experiment tools remain hidden.

Promotion status: kill/pause stable-core as a scoring variant for now; keep the stable-core mechanism as a harness safety fix, then repair no-progress/verifier timing before another narrow real rerun.

