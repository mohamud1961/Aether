# Expanded Architect-Skill Loop Audit - 2026-06-30

## Scope

Goal iteration for the expanded Workbench loop:

- Original tasks: `filter-js-from-html`, `sparql-university`, `openssl-selfsigned-cert`
- Added tasks: `video-processing`, `install-windows-3.11`, `fix-git`, `gpt2-codegolf`
- Mode: `architect_mode=workbench`
- Variant: environment-aware Architect-as-skill + stable core tools + early no-progress verifier

## Implemented Repairs

- Added live environment probing before Workbench Architect runs.
  - Probe records command availability for `python`, `python3`, `git`, `openssl`, `ffmpeg`, `ffprobe`, QEMU, etc.
  - Probe records basic Python module availability for `pytest`, `cryptography`, and `rdflib`.
  - Probe guidance is inserted into architect request, solver prompt prefix, and `config_realization`.
- Strengthened Architect-as-skill contract.
  - Runtime manual now includes `architect_skill_spec` and environment-awareness rules.
  - Workbench Architect prompt now requires concrete typed checks and use of `envmap.environment_probe`.
- Made architect visible smoke checks actually compile into planned checks.
  - Added `RuntimeConfigIR.compiler_injected_checks`.
  - Compiler merges these checks into `EvalIndex`.
  - `visible_smoke_tests` now affect `planned_checks` and completion gate behavior.
- Added safe typed smoke checks:
  - `file_exists`
  - `file_size`
- Added earlier no-progress verifier trigger.
  - Repeated no-progress now calls the verifier before terminal max-steps so active findings can enter later solver context.
- Added Docker image preflight repair.
  - Runner now explicitly checks/pulls missing images with configurable timeouts.
  - Workspace seeding create/copy timeouts are configurable and inherit `run_timeout_s`.
- Added post-run grader-error status repair.
  - If official grader/reward capture fails or times out, result rows now use `status=grader_error` and preserve internal kernel status separately as `kernel_status`.
- Added env-aware Python smoke-check commands.
  - Compiler-generated Python checks now use the probed preferred Python interpreter.
  - If a live environment probe exists and no Python interpreter is available, Python-based smoke checks are rejected instead of compiling to a doomed `python3` command.

## Deterministic Validation

Commands run:

```text
python3 -m pytest -q tests/test_vnext_workbench_ir.py tests/test_vnext_configurability.py
python3 -m compileall -q aether_next
python3 -m pytest -q tests/test_docker_runner.py tests/test_vnext_workbench_ir.py tests/test_vnext_configurability.py
python3 -m pytest -q --ignore=tests/test_docker_runner.py
python3 run_verifier_only_eval.py --mode fake --out-dir verifier_only_eval_fake_architect_skill_check
python3 validate_verifier_only_eval.py verifier_only_eval_fake_architect_skill_check --report VERIFIER_ONLY_FAKE_ARCHITECT_SKILL_VALIDATION.md
```

Observed:

```text
34 passed
compileall passed
42 passed
209 passed
fake verifier validation ok=true
```

After Docker preflight/status/smoke-compiler follow-up fixes:

```text
python3 -m compileall -q aether_next
python3 -m pytest -q --ignore=tests/test_docker_runner.py
```

Observed:

```text
compileall passed
209 passed
```

## Seven-Task Run V1

Command:

```text
AETHER_MODEL_POLL_TIMEOUT_S=240 AETHER_MODEL_POLL_INTERVAL_S=5 AETHER_MODEL_VERIFIER_TIMEOUT_S=90 python3 run_pilot.py \
  --tasks filter-js-from-html,sparql-university,openssl-selfsigned-cert,video-processing,install-windows-3.11,fix-git,gpt2-codegolf \
  --architect-mode workbench \
  --effort low \
  --max-steps 60 \
  --run-timeout-s 900 \
  --trace-dir expanded_real_task_traces_20260630_architect_skill_loop_v1 \
  --snapshot-dir expanded_real_task_snapshots_20260630_architect_skill_loop_v1 \
  --out expanded_real_task_results_20260630_architect_skill_loop_v1.json
```

Evidence:

- Results: `/Users/mohamud/Downloads/harnesseng/aether_next_build/expanded_real_task_results_20260630_architect_skill_loop_v1.json`
- Traces: `/Users/mohamud/Downloads/harnesseng/aether_next_build/expanded_real_task_traces_20260630_architect_skill_loop_v1/`
- Snapshots: `/Users/mohamud/Downloads/harnesseng/aether_next_build/expanded_real_task_snapshots_20260630_architect_skill_loop_v1/`

Scoreboard:

| task | reward | status | classifier | grader |
|---|---:|---|---|---|
| `filter-js-from-html` | 0.0 | completed | none | `grader_timeout_after_900s` |
| `sparql-university` | 0.0 | incomplete | model_limit | 2 passed, 1 failed |
| `openssl-selfsigned-cert` | 1.0 | completed | none | 6 passed, 0 failed |
| `video-processing` | 0.0 | error | environment_runner_failure | no kernel receipts |
| `install-windows-3.11` | 0.0 | error | environment_runner_failure | no kernel receipts |
| `fix-git` | 0.0 | error | environment_runner_failure | no kernel receipts |
| `gpt2-codegolf` | 0.0 | error | environment_runner_failure | no kernel receipts |

Total: `1/7` rewarded.

## Task Findings

### filter-js-from-html

The architect emitted a content assertion that compiled and passed. The solver reached internal completion at step 13. The model verifier returned `completed`, and the kernel auto-submitted.

Official grader timed out after 900s, so this is not a real pass. This is a status/grader disagreement: internal completion was too weak for this row.

Primary issue: verifier/check insufficiency plus grader timeout handling. The row should not be treated as `completed` in promotion logic when `grader_error` exists.

### sparql-university

This improved from missing file to an actual attempted solution:

- `/app/solution.sparql` existed.
- The query ran without syntax error.
- Official grader passed file existence and run-without-error.
- Official grader failed semantic query results.

The loop still hit max steps. Early no-progress verifier fired at step 51 and again at terminal step 60. Verifier classified the row as `blocked_by_tooling`, but solver did not repair the semantic query result before budget ended.

Primary issue: semantic repair after verifier/check failure remains weak.

### openssl-selfsigned-cert

This passed fully:

- Reward `1.0`
- Grader passed 6/6
- Smoke checks included file existence and Python syntax.
- The previous `cryptography` dependency failure did not recur.

This is the first strong evidence that environment-aware architect guidance plus executable smoke checks improves the OpenSSL failure class.

### Expanded New Tasks

The four added tasks did not reach the kernel. All failed before traces/receipts:

```text
TimeoutExpired: Command '['docker', 'create', '<image>']' timed out after 300 seconds
```

After patching longer timeouts, explicit `docker pull alexgshaw/video-processing:20251031` remained stuck for over 10 minutes and then was interrupted, producing:

```text
error getting credentials - err: signal: interrupt, out: ``
```

Current blocker: Docker image acquisition/credential path for missing images. These rows are invalid environment rows, not solver/architect failures.

Follow-up runner repairs were added after this observation so future rows distinguish:

- missing/pull-failed images;
- seed/create/copy failures;
- kernel status;
- official grader/reward status.

## Current Status

- Harness repairs are implemented and deterministic gates are green.
- Real loop v1 produced one valid pass (`openssl-selfsigned-cert`), two valid failed rows, and four invalid environment rows.
- Expanded loop cannot continue to valid attempts for the four new tasks until Docker can pull or otherwise provide the images locally.

## Next Action

Resolve Docker image acquisition:

```text
docker pull alexgshaw/video-processing:20251031
docker pull alexgshaw/install-windows-3.11:20251031
docker pull alexgshaw/fix-git:20251031
docker pull alexgshaw/gpt2-codegolf:20251031
```

Then rerun only the four invalid tasks first. After they produce kernel traces, audit and repair generic failures. Then rerun the full seven-task set.

Do not claim expanded-task performance until all rows are valid grader-backed rows.
