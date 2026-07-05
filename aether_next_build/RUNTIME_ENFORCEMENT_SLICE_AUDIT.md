# Runtime Enforcement Slice Audit

Date: 2026-07-01

## Executive Conclusion

This slice moves Aether-Next in the intended direction: from prompt-only guidance toward compiler/runtime/verifier enforcement. The implemented behavior now catches three Stage 1 failure pressures in deterministic replay:

- filter false-clean is blocked or marked uncertain when adversarial proof is too thin;
- SPARQL repeated evidence-display commands are intercepted as no-progress;
- SPARQL queries using graph-absent predicates and lacking semantic execution are proof-contract failures.

This is not benchmark promotion evidence. It is mechanism evidence plus replay acceptance. The fresh VM rerun is being managed by a 5.4-mini worker and must be audited separately before any scored conclusion.

## Implemented Mechanisms

- `aether_next/proof_contract.py`: derives runtime proof-contract findings from architect-authored success/evidence/false-positive fields and ledger evidence.
- `aether_next/no_progress.py`: detects repeated evidence-display commands over unchanged targets and returns a structured soft block.
- `aether_next/kernel.py`: records no-progress control receipts during action dispatch and proof-contract receipts at submission.
- `aether_next/completion.py`: treats failed proof contracts and no-progress controls as completion blockers.
- `aether_next/context_compiler.py`: exposes no-progress and proof-contract status back into solver context.
- `aether_next/verifier_packets.py`: includes no-progress and proof-contract evidence in verifier packets.
- `aether_next/kernel_verifier.py`: persists full verifier bundles when `AETHER_VERIFIER_EVIDENCE_DIR` is set.
- `aether_next/runners/docker_runner.py`: adds a wall-clock timeout around `kernel.run()` so `run_timeout_s` bounds the model/kernel loop, not only Docker exec and grader subprocesses.
- `run_stage1_replay_acceptance.py`: deterministic replay acceptance for the Stage 1 failure pressures.

## Local Validation

Commands run from `/Users/mohamud/Downloads/harnesseng/aether_next_build`:

- `python3 -m pytest -q tests/test_runtime_enforcement.py tests/test_stage1_replay_acceptance.py`
  - result: `6 passed in 0.25s`
- `python3 -m compileall -q aether_next`
  - result: passed
- `python3 -m pytest -q --ignore=tests/test_docker_runner.py`
  - result: `227 passed in 4.47s`
- `python3 run_automatic_memory_diagnostic_eval.py --out-dir automatic_memory_diagnostic_eval_runtime_enforcement_timeoutfix`
  - result: 12/12 rows passed
- `python3 run_stage1_replay_acceptance.py --out-dir stage1_replay_acceptance_runtime_enforcement_timeoutfix`
  - result: passed
- `python3 run_verifier_prompt_replay_eval.py --out-dir verifier_prompt_replay_eval_runtime_enforcement_timeoutfix`
  - result: architect verifier prompt variant is evidence-bound/actionable and returns `needs_repair`

## Replay Acceptance

Evidence path: `/Users/mohamud/Downloads/harnesseng/aether_next_build/stage1_replay_acceptance_runtime_enforcement_timeoutfix/stage1_replay_acceptance.json`

Rows:

- `filter_false_clean`: passed. The proof contract emitted `insufficient_adversarial_sample_coverage`.
- `sparql_repeated_evidence_display`: passed. The no-progress controller soft-blocked the third repeated display of `university_graph.ttl`.
- `sparql_invented_predicates`: passed. The proof contract emitted `declared_query_terms_absent_from_graph` and `missing_semantic_query_execution`.

Interpretation: the harness can now turn prior Stage 1 traces into structured runtime consequences. It does not merely tell the solver not to repeat itself.

## Prior VM Rerun Audit

Evidence path: `/Users/mohamud/Downloads/harnesseng/aether_next_build/vm_goal_runs/20260701T_runtime_enforcement_stage1_py311/results.json`

Observed:

- Only one row finalized: `filter-js-from-html`.
- Result: reward `0.0`, status `incomplete`, kernel status `incomplete`, classifier `model_limit`.
- Official grader failed both visible tests: `test_filter_blocks_xss` and `test_clean_html_unchanged`.
- Final verifier returned `uncertain_missing_evidence`.
- The runner then started `sparql-university` and exceeded the intended wall-clock budget because `run_timeout_s` did not wrap the kernel/model loop.

Interpretation:

- Good: the filter task no longer false-cleans. It stayed incomplete and the verifier remained uncertain.
- Bad: the run exposed a runner boundary bug. Kernel execution could run past the run timeout.
- Fix: `docker_runner.py` now wraps `kernel.run()` with `_kernel_wall_timeout()`, writes a timeout row, and preserves partial trace evidence where available.

## Component Assessment

Architect:

- The architect now has a concrete enforcement target: success definition, evidence requirements, false-positive risks, and verifier prompt can compile into proof requirements.
- Current proof-contract compilation is intentionally narrow and generic. It is not a broad semantic theorem prover.

Solver:

- The solver is no longer trusted to self-regulate repeated evidence display. The runtime can intercept and force a different class of next action.
- Automatic memory still helps surface prior evidence, but no-progress control is the stronger mechanism for repeated display loops.

Verifier:

- Verifier packets now include proof-contract and no-progress evidence.
- Full evidence persistence is available: `verifier_packet.json`, `verifier_prompt.txt`, `raw_verifier_output.txt`, `parsed_verifier_result.json`, `active_findings_after.json`.

Runner:

- The prior VM run proved the need for kernel-level timeout enforcement.
- The timeout fix is validated locally by `test_kernel_wall_timeout_interrupts_long_kernel_section`.

## Current VM Status

Fresh Stage 1 VM rerun has been delegated to 5.4-mini worker `019f1e79-5649-7883-84e8-e09e94392977` (`Chandrasekhar`).

Requested VM actions:

- clean stale run-owned process/container from `20260701T_runtime_enforcement_stage1_py311`;
- sync timeout-fixed code to `/home/azureuser/harnesseng_vm/aether_next_build`;
- run VM preflight compile/tests/replay;
- rerun only `filter-js-from-html`, `sparql-university`, and `openssl-selfsigned-cert`;
- mirror artifacts back under `/Users/mohamud/Downloads/harnesseng/aether_next_build/vm_goal_runs/<new_run_id>`;
- hand off result rows, traces, verifier evidence, and live process/container status.

## Remaining Acceptance Work

The slice is not closed until the VM worker returns a terminal Stage 1 rerun handoff. The closeout audit must then answer:

- Did all three rows terminate rather than hang?
- Did any row get a true official grader reward?
- Did filter remain non-false-clean?
- Did SPARQL hit no-progress/proof-contract controls instead of repeated evidence display?
- Did OpenSSL retain execution capability and produce useful shell/OpenSSL evidence?
- Were verifier packets and persisted outputs present for no-progress, max-step, or success-candidate reasons?

