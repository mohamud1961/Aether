# Aether-2 L1 Targeted Board Full Analysis

Run root analyzed: `<project_dir>/Downloads/harnesseng/tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z`

Source VM run root: `<vm_dir>/aether2_full_tournament/l1_targeted_20260615T142411Z`

Date analyzed: 2026-06-15

## Executive Conclusion

Doctrine answer:

- Aether-2 did not make GPT-5.4-mini behave like a consistently careful engineer across this board.
- The strongest positive result is still truthfulness: false-clean stayed at `0`.
- The dominant new failure is verifier collapse in the opposite direction: `verifier_clean` was `false` on every row with verifier metadata, including all `6` grader passes.
- The deepest harness defect is not just “strictness.” The verifier is treating harness/completion-contract text as task requirements and then marking those pseudo-requirements `unverifiable`, which makes clean resolution structurally impossible on many rows.
- A second harness defect is read-only verifier inspection rejecting harmless read commands such as `cat`, `test`, `ss`, `ldd`, and Python file reads during verifier rounds.
- A third defect is task completion tool-contract drift: the model frequently called `task_done` with unsupported fields like `requirements` and `limitations`, producing dispatch errors on `12` captured completion attempts.

Run validity:

- Valid enough for scoreable capability conclusions on the `10` scoreable rows.
- Invalid rows were correctly separated from capability score, but several invalid rows still contain meaningful model/harness evidence and are analyzed below.

Dominant root causes:

1. `verifier_prompt` + `verifier_evidence_classifier`
2. `completion_semantics` / `tool_contract_execution`
3. `service_monitoring` and semantic readiness proof on VM/QEMU tasks
4. Real model-side failure families still remain on reduction/selection and proxy-success tasks

Confidence:

- High for the false-blocking verifier conclusions.
- High for the task-done schema mismatch conclusion.
- Medium for some invalid-row causal interpretation because provider/grader/resource invalidity limits what can be concluded about capability.

Missing evidence:

- The referenced `reasoning_trace.json` artifacts were not present in the pulled slim bundle.
- The exported bundle contains raw tool logs and `aether2_result.json`, which were sufficient for action/state reconstruction, but not the full reasoning-trace layer.

## Authority Surface

- Harness line: `runner/aether2/`
- Run shape: targeted 14-row board
- Model route: GPT-5.4-mini on Azure/OpenAI, per worker handoff and row metadata
- Attempt count: one attempt per task
- Immutable result rows inspected: `14`
- Local inventory command result:
  - `row.json: 14`
  - `result_rows.jsonl: 14`
  - `scoreboard.md: 14`
  - `environment_contract.json: 14`
  - `grader_isolation_contract.json: 14`
  - `aether2_result.json: 13`
  - `service_evidence.json: 13`

## Scoreboard

| Metric | Count |
|---|---:|
| total rows | 14 |
| scoreable rows | 10 |
| pass | 6 |
| fail | 4 |
| invalid_resource_killed | 2 |
| invalid_grader | 1 |
| invalid_provider | 1 |
| false clean (`pass/fail` with `verifier_clean=true` but grader fail) | 0 |
| false blocked (`row_status=pass` with `verifier_clean=false`) | 6 |

Scoreable tasks:

- `pass`: `acl-permissions-inheritance`, `analyze-access-logs`, `attention-mil`, `build-pmars`, `broken-python`, `build-stp`
- `fail`: `assign-seats`, `build-cython-ext`, `qemu-startup`, `video-processing`

Invalid tasks:

- `invalid_resource_killed`: `break-filter-js-from-html`, `install-windows-3.11`
- `invalid_grader`: `broken-networking`
- `invalid_provider`: `extract-moves-from-video`

Verifier/grader matrix:

| Row class | Count |
|---|---:|
| grader pass + `verifier_clean=false` | 6 |
| grader fail + `verifier_clean=false` | 4 |
| invalid + `verifier_clean=false` | 3 |
| invalid + no verifier metadata | 1 |

Step/call ranges:

- Pass rows: `model_calls 8-19`, `steps 4-14`
- Fail rows: `model_calls 12-31`, `steps 6-28`
- Invalid rows with progress: `model_calls 15-34`, `steps 10-28`

## Task Table

| task id | result | final claim | verifier clean | grader/row truth | pass quality or failure class | first decisive step | owning component | confidence | generic eval/fix candidate |
|---|---|---|---|---|---|---|---|---|---|
| acl-permissions-inheritance | pass | correct ACL/shared-dir completion claim | false | pass | `robust` pass, false-blocked | step 5 completion path: dispatch-error `task_done`, then blockers remain unresolved on pseudo-requirements | `verifier_prompt`, `tool_contract_execution` | high | completion-schema sentinel + verifier clean-positive sentinel |
| analyze-access-logs | pass | report written and checked | false | pass | `robust` pass, false-blocked | step 6 completion path, same schema mismatch and pseudo-requirement pollution | `verifier_prompt`, `tool_contract_execution` | high | file-artifact clean-positive sentinel |
| assign-seats | fail | overclaimed success with extra pair | false | fail | primary `model_capability`, contributor `reduction_selection` | step 3 solver produced wrong answer family; step 5 self-check did not test exact expected set | `reduction_selection`, `completion_semantics` | high | combinatorial-output exact-set homolog |
| attention-mil | pass | implementation complete but float16 caveat remains | false | pass | `robust` pass, false-blocked | step 3 already runs dtype checks including float16, yet verifier still marks dtype support unverifiable | `verifier_evidence_classifier` | high | numeric-dtype clean-positive sentinel |
| build-pmars | pass | source build/install verified | false | pass | `robust` pass, false-blocked | verifier round tries a read-only inspection command and blocks it; discrepancy report still carries pseudo-requirements | `verifier_prompt`, `verification_read_only_violation`, `tool_contract_execution` | high | read-only verifier safe-read homolog |
| break-filter-js-from-html | invalid_resource_killed | overclaimed XSS bypass success | false | invalid, but semantic fail evidence exists | invalid; progress made, no pass evidence | step 2-3 boundary violations on file creation path; later benchmark test still fails to trigger alert | `tool_contract_execution`, `model_capability` | medium | browser/XSS artifact homolog with explicit semantic client check |
| broken-python | pass | repaired pip/system Python | false | pass | `robust` pass, false-blocked | step 9 repairs package files; step 10 proves install works, but completion still hits schema mismatch | `tool_contract_execution`, `verifier_prompt` | high | env/toolchain repair clean-positive sentinel |
| broken-networking | invalid_grader | overclaimed example.com reachability | false | invalid, with mixed evidence | invalid; partial progress only | step 3 DNS config changed, but later curl/urllib checks still fail; task_done still overclaims success | primary `grader_failure`, contributor `completion_semantics` | medium | network-reachability homolog with deterministic grader shell |
| build-stp | pass | STP built and fresh shell command works | false | pass | `robust` pass, false-blocked | step 14 completion path again shows schema mismatch despite strong independent evidence at step 13 | `tool_contract_execution`, `verifier_prompt` | high | binary-install clean-positive sentinel |
| build-cython-ext | fail | honest blocked-style summary with remaining blockers | false | fail | primary `model_capability`, contributor `completion_semantics` | step 6 upgrades NumPy and violates a visible invariant; later checks show extensions work but environment contract regresses | `reduction_selection`, `completion_semantics` | high | environment-preservation homolog |
| qemu-startup | fail | honest non-clean outcome | false | fail | primary `service_monitoring`/`model_capability` | step 3-8 prove telnet socket/activity but not semantic Alpine login/version readiness | `service_monitoring`, `verifier_evidence_classifier` | high | telnet/QEMU semantic readiness homolog |
| extract-moves-from-video | invalid_provider | no model progress | null | invalid | primary `provider_failure` | before first model work | `provider_failure` | high | provider-invalid sentinel |
| install-windows-3.11 | invalid_resource_killed | partial infra success but desktop not proven | false | invalid, with strong progress evidence | invalid; substantial progress before termination | step 14 starts job and gets VNC/QEMU alive, but later checks cannot prove desktop/QMP monitor semantics | `service_monitoring`, `completion_semantics`, `timeout_resource_failure` | high | VNC/QMP semantic readiness homolog |
| video-processing | fail | parseable output overclaimed as sufficient | false | fail | primary `completion_semantics`, contributor `proxy_target_success` | step 7 proves TOML exists and parses, but not that frame values are scalar ints in required ranges | `completion_semantics`, `verifier_evidence_classifier` | high | typed-artifact semantic-value homolog |

## Disagreements And Inconsistencies

### False-blocked passes

All six grader passes remained `verifier_clean=false`:

- `acl-permissions-inheritance`
- `analyze-access-logs`
- `attention-mil`
- `build-pmars`
- `broken-python`
- `build-stp`

This is a complete collapse of the verifier clean signal on positive rows.

### Pseudo-requirement pollution

The last discrepancy report on `13` rows contains repeated harness/completion-contract bullets treated as task requirements:

- `Current working directory is /app ...` appeared unresolved on `13` rows.
- `Do not read or modify hidden verifier tests.` appeared unresolved on `11` rows.
- `For QEMU/telnet, verify an actual login/session command succeeds ...` appeared unresolved on `11` rows.
- `Do not read solution.sh.` appeared unresolved on `10` rows.
- Multiple generic completion-contract bullets about “strong checks,” “do not stop after plausible files/processes,” and “prove service/VM semantics” also appeared unresolved on `9-10` rows.

These are not benchmark task requirements. They are harness-side doctrine or evaluation instructions, and their presence in the requirement list explains why clean resolution is structurally blocked.

Primary evidence:

- `acl-permissions-inheritance`: `.../20260615T142412Z/acl-permissions-inheritance/row.json`
- `analyze-access-logs`: `.../20260615T142455Z/analyze-access-logs/row.json`
- `attention-mil`: `.../20260615T142640Z/attention-mil/row.json`
- `build-pmars`: `.../20260615T142759Z/build-pmars/row.json`

### Read-only verifier inspection blocks harmless reads

Verifier rounds rejected benign observational commands as `verification_read_only_violation`, for example:

- `assign-seats`: reading `/app/results.txt`
- `build-pmars`: `test -x`, `pmars`, `ldd`, `grep` readback
- `build-cython-ext`: import checks and `.so` listing
- `install-windows-3.11`: `ss -ltnp`, file existence, socket-connect probes

These commands are read-only checks that should have improved verifier confidence, not been blocked.

Primary evidence:

- `.../20260615T142759Z/build-pmars/artifacts/app/.aether2/raw_logs/run_command_85f7ea6a74f041c788f83253ef6f2a9c.json`
- `.../20260615T142549Z/assign-seats/artifacts/app/.aether2/raw_logs/run_command_e6ed92706c424b0c802abdcde0cf56c0.json`
- `.../20260615T143633Z/build-cython-ext/artifacts/app/.aether2/raw_logs/run_command_835261cb56bd41249a1bce2f391a19d0.json`
- `.../20260615T145057Z/install-windows-3.11/artifacts/app/.aether2/raw_logs/run_command_bea9884ca9da4a38b39c1d917d5069bc.json`

### Task completion schema drift

Captured completion calls frequently fail with:

- `ExecutionContext.task_done() got an unexpected keyword argument 'requirements'`
- `ExecutionContext.task_done() got an unexpected keyword argument 'limitations'`

Observed on `12` captured completion attempts across `10` tasks.

This is a real harness/tool-contract defect because the model is clearly being invited to provide richer completion payloads than the runtime accepts.

Primary evidence:

- `.../acl-permissions-inheritance/artifacts/app/.aether2/raw_logs/task_done_9d86e70b756c47df98989189cbb18a9b.json`
- `.../analyze-access-logs/artifacts/app/.aether2/raw_logs/task_done_d07e5724474740b691db53e191525161.json`
- `.../build-stp/artifacts/app/.aether2/raw_logs/task_done_e978c451c13041b39b8ac94d24776d6b.json`

### Instrumentation inconsistency

`finalize_reason=task_done` appears on many rows whose exported `tool_invocations` only show dispatch-error `task_done` attempts and no successful `task_done` envelope. Example:

- `analyze-access-logs`: `finalize_reason=task_done`, but exported tool invocations show only a dispatch-error `task_done`.
- `build-pmars`: exported tool invocations show both a dispatch-error and a successful `task_done`.

Interpretation: `UNCLEAR` whether successful completion calls are omitted from some exports or whether `finalize_reason` is being set by a different path.

Primary evidence:

- `.../analyze-access-logs/artifacts/aether2_result.json`
- `.../build-pmars/artifacts/aether2_result.json`

## Deep Dives

### Robust Pass: `analyze-access-logs`

Path:

- `.../20260615T142455Z/analyze-access-logs/row.json`
- `.../20260615T142455Z/analyze-access-logs/artifacts/aether2_result.json`

Observed journey:

1. Step 1 samples and parses the log.
2. Step 2 tries an initial Python script and gets a nonzero exit.
3. Step 3 repairs the script and writes the report.
4. Step 4-5 read back `/app/report.txt` and validate exact structure and values.

Assessment:

- `OBSERVED`: the model reacted to an early script failure with a repaired extraction.
- `OBSERVED`: later checks targeted the actual report contents, not just existence.
- `INFERRED`: this is a real careful-engineer loop and would likely generalize.

Pass quality: `robust`

Why verifier still blocked:

- The completion call hit the `task_done(requirements=...)` schema error.
- The discrepancy report still carried pseudo-requirements like `Do not read solution.sh`.

### Robust Pass: `build-stp`

Path:

- `.../20260615T143335Z/build-stp/row.json`
- `.../20260615T143335Z/build-stp/artifacts/aether2_result.json`

Observed journey:

1. Toolchain/dependency preflight found missing build tools.
2. The model installed them, attempted a build, hit build failures, inspected CMake and header issues, patched the code, and retried.
3. It created a wrapper in `/usr/local/bin/stp`.
4. It verified `stp` from a fresh `env -i PATH=...` shell using a real SMT input file.

Assessment:

- `OBSERVED`: this pass used representative external behavior, not a placeholder claim.
- `OBSERVED`: the fresh-shell check is strong independent evidence.

Pass quality: `robust`

Verifier failure mode:

- Same completion schema drift.
- Same pseudo-requirement pollution.

### Suspicious Pass / False-Blocked: `attention-mil`

Path:

- `.../20260615T142640Z/attention-mil/row.json`
- `.../20260615T142640Z/attention-mil/artifacts/aether2_result.json`

Observed journey:

1. The model reads the assignment file.
2. It writes the missing implementation.
3. It runs the provided script and then explicitly tests `torch.float16`, `torch.float32`, and `torch.float64`.

Grader truth:

- `OBSERVED`: verifier tail shows `11 passed`.

Verifier disagreement:

- `OBSERVED`: the final discrepancy report still emits `float16_unverified`.

Conclusion:

- This is not a weak pass. It is a false-block due to evidence-classifier failure.

### Suspicious Pass / False-Blocked: `build-pmars`

Path:

- `.../20260615T142759Z/build-pmars/row.json`
- `.../20260615T142759Z/build-pmars/artifacts/aether2_result.json`
- `.../20260615T142759Z/build-pmars/artifacts/app/.aether2/raw_logs/run_command_85f7ea6a74f041c788f83253ef6f2a9c.json`

Observed journey:

1. The model enables `deb-src`, inspects source/build files, and patches the Makefile.
2. It verifies the binary with a real `pmars` run and `ldd`.
3. The grader later passes all `4` checks.

Failure in harness interpretation:

- `OBSERVED`: the verifier tries to run a read-only inspection command and the harness rejects it as read-only-violating.
- `OBSERVED`: the final discrepancy report still lists generic harness bullets as unmet.

Conclusion:

- The model behaved correctly here.
- The harness prevented itself from seeing the final confirming evidence.

### Highest-Value Failure: `video-processing`

Path:

- `.../20260615T150017Z/video-processing/row.json`
- `.../20260615T150017Z/video-processing/artifacts/aether2_result.json`

Observed journey:

1. The model inspects the sample video and frame content.
2. It writes `jump_analyzer.py`.
3. The first run fails; it patches the file.
4. Step 7 produces parseable `output.toml`.
5. Step 9 calls `task_done` with a dispatch error first.

Grader truth:

- `OBSERVED`: hidden tests fail because `jump_takeoff_frame_number` and `jump_land_frame_number` are lists, not scalar ints.

First decisive divergence:

- Step 7: parseable TOML was treated as sufficient proof instead of validating the exact scalar/value contract.

Primary class:

- `completion_semantics`

Contributors:

- `proxy_target_success`
- `shape_or_existence_only`

Counterfactual:

- If the harness had demanded type/semantic checks instead of allowing “parseable TOML” to feel done, this row likely would not have closed.

### Highest-Value Failure: `assign-seats`

Path:

- `.../20260615T142549Z/assign-seats/row.json`
- `.../20260615T142549Z/assign-seats/artifacts/aether2_result.json`

Observed journey:

1. The model enumerates files and decodes clues/pickles.
2. It constructs a solver and writes `/app/results.txt`.
3. It reads back the output and performs a local consistency check.
4. Hidden tests reject an extra pair: `bob, frankie`.

First decisive divergence:

- Step 3: the solver locked onto an incorrect interpretation and the self-check never compared against the exact output contract.

Primary class:

- `model_capability`

Contributor:

- `reduction_selection`

Why this is not a harness false-clean:

- The row fails honestly.
- The verifier did not bless it as clean.

### Highest-Value Failure: `build-cython-ext`

Path:

- `.../20260615T143633Z/build-cython-ext/row.json`
- `.../20260615T143633Z/build-cython-ext/artifacts/aether2_result.json`
- `.../20260615T143633Z/build-cython-ext/artifacts/app/.aether2/raw_logs/run_command_835261cb56bd41249a1bce2f391a19d0.json`

Observed journey:

1. The model clones the repo and confirms NumPy `2.3.0`.
2. It patches source files and installs build tooling.
3. It upgrades pip/setuptools/wheel/cython and later runs with NumPy `2.4.6`.
4. Most repository tests pass, but hidden tests fail because the original NumPy version requirement was violated.

First decisive divergence:

- Step 6: the model chooses a broad environment upgrade path that breaks a visible invariant instead of repairing the narrow compatibility issue in place.

Primary class:

- `model_capability`

Contributors:

- `completion_semantics`
- `orientation_envcontract` only in the weak sense that the model did not preserve the visible environment contract

### Highest-Value Failure: `qemu-startup`

Path:

- `.../20260615T144230Z/qemu-startup/row.json`
- `.../20260615T144230Z/qemu-startup/artifacts/aether2_result.json`
- `.../20260615T144230Z/qemu-startup/artifacts/service_evidence.json`

Observed journey:

1. The model proves the QEMU binary exists and starts QEMU.
2. It gets a telnet listener on `:6665`.
3. It restarts QEMU as a job and polls.
4. The grader later shows the telnet transcript only captured `uname -r`, not the expected Alpine kernel string.

First decisive divergence:

- Step 3-8: port/telnet availability was treated as near-readiness without proving an authenticated session and semantic command output.

Primary class:

- `service_monitoring`

Contributors:

- `process_is_not_functionality`
- `completion_semantics`

This row matters because it is exactly the kind of service-semantic gap the harness claims to prevent.

### Invalid But Meaningful: `broken-networking`

Path:

- `.../20260615T143210Z/broken-networking/row.json`
- `.../20260615T143210Z/broken-networking/artifacts/aether2_result.json`

Observed journey:

1. The model inspects resolver state and confirms HTTPS failure.
2. It patches `nsswitch.conf` and `resolv.conf`.
3. DNS resolution improves.
4. Curl and urllib HTTPS checks still fail repeatedly.
5. The model still calls `task_done` claiming `example.com` is reachable.
6. The row is marked `invalid_grader`; grader shell/setup is visibly broken (`uv: command not found`, missing env activation).

Interpretation:

- `OBSERVED`: this row contains genuine progress on DNS resolution.
- `OBSERVED`: end-to-end reachability was not actually proven.
- `INFERRED`: the model still overclaimed success.
- `OBSERVED`: grader invalidity means capability score should not use this row.

Primary class:

- `grader_failure`

Contributors:

- `completion_semantics`

### Invalid But Meaningful: `install-windows-3.11`

Path:

- `.../20260615T145057Z/install-windows-3.11/row.json`
- `.../20260615T145057Z/install-windows-3.11/artifacts/aether2_result.json`
- `.../20260615T145057Z/install-windows-3.11/artifacts/service_evidence.json`

Observed journey:

1. The model installs QEMU/VNC tools and writes launch scripts.
2. It eventually launches QEMU as a job.
3. Service evidence shows VNC listener `127.0.0.1:5901` alive, QEMU process running, and a long observation window (`557.59s`).
4. However, the verifier cannot prove desktop readiness and later tests fail because `/tmp/qemu-monitor.sock` is missing and Windows-key visual feedback is not established.

Interpretation:

- `OBSERVED`: substantial setup progress happened before invalid termination.
- `OBSERVED`: semantic desktop/QMP readiness was not proven.
- `INFERRED`: this is a useful service-readiness diagnostic despite being non-scoreable.

Primary class:

- `timeout_resource_failure`

Contributors:

- `service_monitoring`
- `completion_semantics`

### Invalid But Meaningful: `break-filter-js-from-html`

Path:

- `.../20260615T142956Z/break-filter-js-from-html/row.json`
- `.../20260615T142956Z/break-filter-js-from-html/artifacts/aether2_result.json`

Observed journey:

1. The model reads `filter.py` and visible tests.
2. It hits workspace-boundary violations while trying to create payload files.
3. It moves into an interactive session and continues.
4. Hidden tests still show that no alert fires after filtering.

Interpretation:

- `OBSERVED`: progress and iteration occurred before the invalid classification.
- `OBSERVED`: semantic success was not achieved.
- `UNCLEAR`: why the final row is `invalid_resource_killed` rather than an ordinary fail, because the visible verifier tail shows a normal failing test rather than an obvious kill event.

Primary class:

- `timeout_resource_failure`

Contributor:

- `tool_contract_execution`

Falsifier:

- A stronger runner-side invalidity artifact showing an actual kill event would move this from `UNCLEAR` to a pure resource-invalid interpretation.

### Pure Invalid: `extract-moves-from-video`

Path:

- `.../20260615T145009Z/extract-moves-from-video/row.json`

Observed:

- The row failed before model work with `ModelClientError('azure openai request failed with status 400')`.

Primary class:

- `provider_failure`

No capability inference should be drawn.

## Fake-Progress Analysis

### Onset 1: `video-processing`

Prior observation:

- The model had a script that emitted `output.toml` and passed a parse/shape check.

Next rationality trap:

- The visible state rewarded “script runs and TOML parses” over “frame numbers are scalar ints in allowed ranges.”

Trigger family:

- `proxy_target_success`
- `shape_or_existence_only`

Why it looked rational locally:

- The model had a plausible artifact and a passing local parse check.
- The harness did not surface a stronger missing-evidence requirement before completion.

### Onset 2: `qemu-startup`

Prior observation:

- QEMU listener on `:6665` was reachable and telnet socket activity existed.

Next rationality trap:

- Port/socket readiness looked close to task completion without requiring proof of an Alpine login and correct kernel output.

Trigger family:

- `process_is_not_functionality`

### Onset 3: `assign-seats`

Prior observation:

- The model had decoded clues and generated a seating solution.

Next rationality trap:

- A locally consistent output felt sufficient without an exact externally-grounded set comparison.

Trigger family:

- `candidate_lock_in`
- `partial_sample_generalization`

## Cross-Harness Findings

### Helpful

- Invalid rows stayed separated from scoreable rows.
- Service evidence captured meaningful bounded-survival/process snapshots for QEMU/VNC tasks.
- False-clean stayed at zero.
- Several passes show the model can behave carefully when the loop surfaces the right evidence.

### Harmful

#### `verifier_prompt` / requirement extraction

- Harness doctrine text is entering the verifier requirement list and being judged as if it were part of the benchmark contract.

#### `verifier_evidence_classifier`

- Strong evidence can still be ignored, as in `attention-mil`.

#### `completion_semantics`

- The model still sees enough local reward to overclaim on rows like `assign-seats`, `broken-networking`, and `video-processing`.

#### `tool_contract_execution`

- `task_done` schema drift is real and widespread.
- Workspace-boundary checks sometimes block commands that are reasonable in context.

#### `verification_read_only_violation`

- The verifier cannot perform benign read checks that would improve confidence.

#### `instrumentation`

- Exported completion traces are inconsistent with `finalize_reason` on some rows.

## Prioritized Fix Plan

### 1. Separate benchmark requirements from harness doctrine in verifier input

- Generic failure class: `verifier_prompt`
- Owning component: verifier prompt / requirement projection
- Observed evidence: pseudo-requirements repeated across 13 rows
- Intended behavior change: only benchmark task requirements enter the requirement list; doctrine remains advisory context, not adjudicated checklist items
- Proving custom homolog: simple file/service task with rich doctrine wrapper; verifier must still return clean on a genuine pass
- Known-bad case: current targeted board behavior where all passes remain non-clean
- Ceiling case: robust pass row returns `verifier_clean=true`
- Regression sentinels: `acl-permissions-inheritance`, `analyze-access-logs`, `build-stp`, one fake-progress homolog
- Non-benchmarkification argument: this is about separating task contract from wrapper policy, not memorizing tasks
- Risk: overly aggressive filtering could hide real constraints
- Predicted impact: restore discriminative power to `verifier_clean`; reduce false-blocks from 6 toward 0
- Keep/kill criterion: keep only if genuine passes become clean while false-clean remains 0

### 2. Allow safe read-only verifier inspection commands

- Generic failure class: `verifier_evidence_classifier`
- Owning component: verifier read-only executor
- Observed evidence: blocked `cat`, `test`, `ss`, `ldd`, import checks, file reads
- Intended behavior change: permit a safe read-only command subset during verifier rounds
- Proving custom homolog: file-artifact task where verifier needs `cat`; binary-install task needing `ldd`; service task needing `ss` or socket connect
- Known-bad case: `build-pmars` and `assign-seats`
- Ceiling case: readback checks succeed without mutating workspace
- Regression sentinels: fake-progress tasks where verifier must still avoid mutating construction state
- Non-benchmarkification argument: safe observational commands are generic
- Risk: overly broad allowlist could reintroduce side-effectful checks
- Predicted impact: major reduction in false-blocks on already-correct rows
- Keep/kill criterion: keep only if safe-read homologs become clean and mutation safety tests still pass

### 3. Align `task_done` schema between prompt and runtime

- Generic failure class: `tool_contract_execution`
- Owning component: task completion tool schema / prompt
- Observed evidence: `unexpected keyword argument 'requirements'/'limitations'`
- Intended behavior change: either accept the richer fields or stop instructing the model to send them
- Proving custom homolog: file/task_done contract test where the model includes optional completion metadata
- Known-bad case: 12 dispatch-error completions on this board
- Ceiling case: completion payload accepted without dispatch error
- Regression sentinels: targeted pass rows and one blocked row
- Non-benchmarkification argument: pure tool-schema alignment
- Risk: silently accepting unused fields without logging could hide schema drift
- Predicted impact: fewer wasted turns, fewer suppressed verifier calls, cleaner completion traces
- Keep/kill criterion: keep only if dispatch-error completions drop to zero on the homolog and board rerun

### 4. Strengthen semantic-value checks for typed artifacts

- Generic failure class: `completion_semantics`
- Owning component: completion contract / verifier evidence classifier
- Observed evidence: `video-processing` closed on parseable TOML with wrong value types
- Intended behavior change: require type/semantic verification for final artifacts, not parseability alone
- Proving custom homolog: media-independent artifact task where output must contain scalar ints inside ranges
- Known-bad case: list-valued TOML that still parses
- Ceiling case: correct scalar/value type passes
- Regression sentinels: file artifact tasks, structured retrieval sentinel
- Non-benchmarkification argument: generic typed-output validation
- Risk: over-strict typing on legitimately polymorphic outputs
- Predicted impact: fewer proxy-success closures
- Keep/kill criterion: keep only if known-bad proxy artifacts fail while valid scalar artifacts pass

### 5. Add semantic service-readiness sentinels for telnet/VNC/QMP

- Generic failure class: `service_monitoring`
- Owning component: service monitoring + verifier evidence classifier
- Observed evidence: `qemu-startup` and `install-windows-3.11` proved ports/processes but not usable session semantics
- Intended behavior change: distinguish listener/process proof from actual session/monitor/desktop readiness
- Proving custom homolog: telnet login task, VNC desktop task, QMP socket task
- Known-bad case: open port with missing semantic response
- Ceiling case: successful login/desktop change/QMP command response
- Regression sentinels: non-service tasks should remain unaffected
- Non-benchmarkification argument: service semantic readiness is generic
- Risk: heavier checks may increase cost/time
- Predicted impact: better separation of genuine service readiness from port-open illusions
- Keep/kill criterion: keep only if semantic service homologs improve agreement without inflating invalids

## Confidence And Falsifiers

### Major conclusion: verifier clean signal is structurally broken

- Confidence: high
- Evidence: all 6 passes non-clean; pseudo-requirement counts across 13 rows; read-only verifier rejections
- Alternative explanation: the benchmark tasks really require these wrapper bullets as task requirements
- Falsifier: a rerun where the same verifier logic produces clean on several robust passes without changing row content

### Major conclusion: task completion tool schema drift is real

- Confidence: high
- Evidence: repeated raw-log dispatch errors for unsupported `task_done` fields
- Alternative explanation: those fields are intentionally ignored and harmless
- Falsifier: runtime source shows the fields are accepted on the live code path and the logged dispatch errors are stale or misattributed

### Major conclusion: invalid rows still contain useful progress evidence

- Confidence: medium-high
- Evidence: `install-windows-3.11` service evidence, `broken-networking` step trace, `break-filter-js-from-html` iteration logs
- Alternative explanation: these rows are too contaminated by invalidity to say anything useful
- Falsifier: stronger invalidity artifacts showing model work never reached the state implied by the local logs

## Evidence Appendix

Commands used:

- `python3 .../inventory_run.py .../l1_targeted_20260615T142411Z`
- local JSON extraction over `row.json`, `aether2_result.json`, and raw `.aether2/raw_logs/*.json`

Files inspected:

- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/progress.tsv`
- all `14` `row.json` files under the run root
- all `13` `aether2_result.json` files under the run root
- all available `service_evidence.json` files under the run root
- selected raw logs under `artifacts/app/.aether2/raw_logs/`

Notable exact evidence paths:

- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/20260615T142412Z/acl-permissions-inheritance/row.json`
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/20260615T142640Z/attention-mil/artifacts/aether2_result.json`
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/20260615T142759Z/build-pmars/artifacts/app/.aether2/raw_logs/run_command_85f7ea6a74f041c788f83253ef6f2a9c.json`
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/20260615T143633Z/build-cython-ext/artifacts/aether2_result.json`
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/20260615T144230Z/qemu-startup/artifacts/service_evidence.json`
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/20260615T145057Z/install-windows-3.11/artifacts/service_evidence.json`
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/20260615T150017Z/video-processing/artifacts/aether2_result.json`

Extraction limitations:

- No local `reasoning_trace.json` files were present in the pulled slim bundle.
- The exported completion traces are internally inconsistent on some rows (`finalize_reason=task_done` without visible successful `task_done` invocation), so completion-path claims beyond the logged envelopes are marked `UNCLEAR` where necessary.
