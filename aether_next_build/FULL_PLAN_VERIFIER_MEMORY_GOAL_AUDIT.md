# Full Plan Verifier/Memory Goal Audit

Date: 2026-07-01

## Scope

This goal executed the eval-governed continuation plan for the Aether-Next configurable harness line:

- verifier replay A/B over prior real failure traces;
- automatic-memory policy diagnostic eval;
- completion-gate hardening from active verifier findings and automatic-memory repeat blocks;
- full local validation;
- admitted narrow real rerun attempt only after gates were green.

Out of scope: broad benchmark boards, performance promotion claims, and full benchmark runs.

## Phase Disposition

| Phase | Status | Evidence |
| --- | --- | --- |
| Trace verifier replay A/B, fake mode | pass | `trace_verifier_replay_ab_fake_v1/` |
| Trace verifier replay A/B, 5.4-mini model mode | pass | `trace_verifier_replay_ab_54mini_v1/trace_verifier_replay_ab.json`; `trace_verifier_replay_ab_54mini_v1/TRACE_VERIFIER_REPLAY_AB_REPORT.md` |
| Automatic-memory diagnostic variants | pass | `automatic_memory_diagnostic_eval_v2/automatic_memory_diagnostic_eval.json`; `automatic_memory_diagnostic_eval_v2/AUTOMATIC_MEMORY_DIAGNOSTIC_REPORT.md` |
| Completion hardening for verifier findings and memory repeat blocks | pass | `tests/test_completion.py`; `tests/test_memory_loop_fixes.py`; full pytest |
| Full local non-Docker gate | pass | `python3 -m pytest -q --ignore=tests/test_docker_runner.py` -> 219 passed |
| Narrow real rerun, three approved tasks | invalid due to environment/provider instability | attempted command below; no trace/result row emitted before provider hang and Docker health timeout |

## Implemented Repairs

### Trace Verifier Replay A/B

Added `run_trace_verifier_replay_ab.py`.

The replay reconstructs verifier packets from prior real traces and compares the generic verifier prompt against the architect-generated verifier prompt. Each task/variant writes:

- `verifier_packet.json`;
- `raw_output.json`;
- `parsed_result.json`;
- `active_findings_after.json`;
- `judgement.json`.

Model run summary:

- cases: 3;
- parseable/usable rows: 3;
- architect prompt improved specificity: 2/3;
- filter-js-from-html: neutral;
- sparql-university: improved;
- openssl-selfsigned-cert: improved.

Interpretation: architect-generated verifier prompts are useful, but not sufficient as a completion authority. They made SPARQL/OpenSSL feedback more specific, while filter-js remained evidence-limited.

### Automatic Memory Policy

Added `AutomaticMemoryPolicy` and runtime policy modes:

- `off`;
- `advisory`;
- `require_justification`;
- `soft_block_exact_repeat`.

Runtime behavior now records automatic-memory receipts before repeated tool dispatches. The stricter modes can block repeated reads/commands/checks when there is no repeat justification.

Diagnostic result:

- rows: 12;
- passed: 12;
- failed: 0.

Interpretation: the mechanism is testable and falsifiable. It can distinguish no-memory, advisory memory, repeat-without-justification, and justified-repeat cases without requiring the solver model to call `query_memory`.

### Completion Gate Hardening

Completion now blocks when:

- an active model-verifier finding has priority `blocking`;
- the latest receipt is a failed `automatic_memory_block`.

Focused tests and the full suite confirm completion cannot claim clean success while those evidence blockers remain active.

## Validation Commands

```bash
python3 -m compileall -q aether_next run_trace_verifier_replay_ab.py run_automatic_memory_diagnostic_eval.py run_verifier_prompt_replay_eval.py run_verifier_only_eval.py run_architect_only_eval.py
python3 run_trace_verifier_replay_ab.py --mode fake --out-dir trace_verifier_replay_ab_fake_v1
python3 run_trace_verifier_replay_ab.py --mode model --out-dir trace_verifier_replay_ab_54mini_v1
python3 run_automatic_memory_diagnostic_eval.py --out-dir automatic_memory_diagnostic_eval_v2
python3 -m pytest -q tests/test_completion.py tests/test_memory_loop_fixes.py tests/test_trace_verifier_replay_ab.py tests/test_automatic_memory_diagnostic_eval.py
python3 -m pytest -q tests/test_chatgpt_integration_scenarios.py::test_workbench_verifier_repair_loop_exercises_real_kernel_stack
python3 -m pytest -q --ignore=tests/test_docker_runner.py
```

Observed final local gate:

```text
219 passed in 89.12s
```

## Narrow Real Rerun Attempt

The three-task rerun was admitted only after the local/replay/diagnostic gates passed.

Attempted command:

```bash
AETHER_MODEL_POLL_TIMEOUT_S=240 AETHER_MODEL_POLL_INTERVAL_S=5 AETHER_MODEL_VERIFIER_TIMEOUT_S=90 python3 run_pilot.py \
  --tasks filter-js-from-html,sparql-university,openssl-selfsigned-cert \
  --architect-mode workbench \
  --effort medium \
  --max-steps 30 \
  --run-timeout-s 900 \
  --trace-dir narrow_real_task_traces_20260701_014257_auto_memory_goal \
  --snapshot-dir narrow_real_task_snapshots_20260701_014257_auto_memory_goal \
  --out narrow_real_task_results_20260701_014257_auto_memory_goal.json
```

Observed:

- Docker initially became reachable after `open -a Docker`: server version `29.0.1`.
- The runner started `filter-js-from-html`.
- No trace file or result JSON was emitted.
- The pilot process remained alive for roughly 20 minutes.
- Process inspection showed open HTTPS connections to the Azure endpoint and no active Docker child process.
- The pilot was terminated after the provider wait did not return.
- A follow-up Docker health check timed out:

```text
{'timeout': True, 'cmd': 'docker info', 'seconds': 15}
```

Disposition: invalid due to environment/provider instability. This is not a solver, architect, verifier, or benchmark result row.

## Current Claims

Supported by evidence:

- The local harness test suite is green after the new repairs.
- Verifier replay A/B can save raw output, parsed result, active finding, and judgement artifacts.
- Architect-generated verifier prompts improved replay feedback specificity on 2 of 3 prior failed traces.
- Automatic memory can be automatic, receipt-backed, and policy-controlled without making the solver call `query_memory`.
- Completion now respects active verifier findings and automatic-memory repeat blockers.

Not supported:

- No claim of benchmark improvement.
- No claim that the three real tasks improved under the new mechanism.
- No broad board or promotion claim.

## Next Action

Before another live real-task rerun:

1. Repair runner/provider timeout handling so stuck Azure calls produce a row-level `provider_timeout` instead of hanging the whole pilot.
2. Add early trace flushing at task start and after architect resolution so invalid runs still preserve partial evidence.
3. Add a short Docker health gate before each task, with a bounded timeout and explicit `invalid_due_to_environment` row on failure.
4. Rerun exactly the same three tasks only after those runtime safeguards are in place.

