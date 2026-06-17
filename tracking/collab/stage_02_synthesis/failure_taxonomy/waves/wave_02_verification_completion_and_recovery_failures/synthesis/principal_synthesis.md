# Failure Taxonomy Wave 02 Principal Synthesis

Status: principal-complete; checklist-ready

Overall verdict: `pass_with_warnings`

Scope

- overall Deep Synthesis wave: Wave 08
- artifact: `failure_taxonomy`
- artifact-local wave: Wave 02 `verification_completion_and_recovery_failures`
- evidence shape: five main lanes present (`trajectory`, `codebase`, `literature`, `informal`, `eval`) plus GPT and Claude contradiction gates
- missing gate: no Gemini contradiction output exists on disk for this wave

## What This Wave Resolved

Wave 02 resolves that verification/completion/recovery failures are a real failure-taxonomy surface, not just a mechanism-map recap.

The strongest supported family is:

- `verifier_or_completion_success_signal_diverges_from_final_acceptance`: `emerging`, high confidence
  - Core observation: BigAI `cancel-async-tasks` run `98b7...` and deepagents `cancel-async-tasks` run `ca5a...` both show in-run verified/local-success signaling while final bundle artifacts fail `test_tasks_cancel_above_max_concurrent` with reward `0`.
  - Evidence:
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee.tar.gz`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf.tar.gz`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_failure_analyst.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_benchmark_analyst.md`

The second strong family is:

- `replay_grader_final_acceptance_mismatch`: `emerging`, high confidence
  - Core observation: inline checks, verifier artifacts, replay/state graders, LLM judges, and final reward are distinct layers; multiple Wave 02 outputs show that a positive or confident lower-layer signal is not equivalent to final task acceptance.
  - Evidence:
    - `research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`
    - `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`
    - `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`
    - `research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py`
    - `research/sources/codebases/deepagents/libs/evals/deepagents_harbor/langsmith.py`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_source_reconstruction_analyst.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_support_verifier_benchmark_contract_map.md`

The third supported family is:

- `recovery_resume_state_and_index_fragility`: `emerging`, medium confidence
  - Core observation: informal issue clusters repeatedly surface stale indexes, transcript/history reconstruction failures, stuck non-terminal states, and resume drift; KIRA `db-wal-recovery` adds a trajectory-level environment/cwd invalidation example.
  - Evidence:
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_issues_postmortems_analyst__followup_01.md`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2.tar.gz`

The fourth supported but thinner family is:

- `completion_pressure_without_sufficient_quality_or_similarity_gate`: `candidate`, medium confidence
  - Core observation: KIRA `extract-moves-from-video` shows completion pressure with final similarity failure; BigAI extraction shows no visible `finish_verification` event in the readable trace and final reward failure.
  - Evidence:
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd.tar.gz`
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`

## Principal Reconciliation

Do not promote `cleanup_confirmed_but_invalid_completion` as a separate high-confidence family yet.

- Reconciliation: Wave 02 evidence supports cleanup and local-check pressure, but the current direct evidence does not cleanly separate "cleanup-confirmed invalid completion" from the broader false-completion/final-acceptance mismatch family.
- Principal decision: treat cleanup as a subflag under `verifier_or_completion_success_signal_diverges_from_final_acceptance` for now.
- Required future criterion: split it into its own family only when a run shows a distinct cleanup/delivery hygiene gate passing while final correctness fails for a reason not reducible to ordinary local-check weakness.

Do not promote BigAI extraction verifier omission beyond provisional.

- Reconciliation: The absence of visible `finish_verification` in one BigAI extraction trajectory is useful pressure, but it could still be a trace-format or capture artifact.
- Principal decision: keep `BigAI verifier omission in extraction regime` as a provisional observation, not a promoted family.
- Required future criterion: promote only after another readable trajectory confirms the omission or the trace-format-artifact explanation is ruled out.

Keep benchmark-contract blindness capped.

- Reconciliation: The eval lane materially improved this wave, but several benchmark captures remain README/contract-level rather than grader-implementation-level.
- Principal decision: `benchmark_contract_blindness` remains a real pressure surface, but not decision-ready and not high-confidence as an implementation-causal claim across all benchmark families.
- Required future criterion: direct grader implementation reads for the relevant `src_bnm_*` captures or equivalent verifier code.

Keep BigAI language strict.

- BigAI supports behavioral evidence for verifier loops, verifier-pass/final-fail divergence, and recovery pressure.
- BigAI does not support source-backed mechanism attribution.
- Every BigAI mechanism claim from this wave must remain tagged `behavioral reconstruction`.

## Gate Reconciliation

Current on-disk gate state:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/contradiction_analyst.md`: `pass_with_warnings`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/contradiction_analyst__claude.md`: `pass_with_warnings`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/contradiction_analyst__gemini.md`: absent

The Claude output references a Gemini gate and a prior blocked GPT state, but those references are not supported by the current on-disk Wave 02 output set provided to this principal pass. I therefore treat Claude's substantive warnings as useful, but I do not carry forward the statement that a Gemini contradiction output exists.

The missing informal support artifact has been explicitly retired for this wave:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_support_false_completion_recovery_cluster.md`

Rationale: the informal main output and follow-up already provide the relevant clustering, and no unique claim depends on the missing support file.

## What Still Requires Another Wave

No Wave 02 failure family is `decision_ready`.

Carry forward:

- Direct grader implementation depth remains incomplete for benchmark captures under `research/sources/benchmarks/src_bnm_*/`.
- The exact cause of the shared `cancel_above_max_concurrent` failure remains unresolved across BigAI and deepagents.
- KIRA `db-wal-recovery` cwd invalidation remains single-run and mixed-cause.
- A-Evolve Wave 02 behavior remains source-backed, not trajectory-backed.
- BigAI source-level attribution remains unavailable.
- BigAI extraction verifier omission remains provisional.
- Cleanup-confirmed invalid completion remains a subflag, not a separate family.

Priority follow-ups:

- Read the grader internals or mirrored verifier code behind the Wave 02 benchmark-contract captures.
- Add more extraction-family trajectories, especially BigAI and deepagents, to separate actual verifier omission from trace-format omission.
- Add another KIRA `db-wal-recovery` check to test reproducibility of cwd invalidation.
- Pin the exact failing assertion logic in `test_tasks_cancel_above_max_concurrent`.

## Local Harness Implications

The local harness should not treat completion as one boolean.

Required separate logged layers:

- inline/local self-checks
- explicit verifier artifacts
- replay/state grader result
- LLM judge or rubric result, if used
- cleanup/delivery hygiene check
- final reward / benchmark acceptance
- missing-artifact versus explicit-failure distinction

Current local harness risk:

- `blocks/verification/*`, `blocks/recovery/*`, `runner/evaluator.py`, and `evals/verification_eval.py` are described by the codebase lane as scaffold/stub-level for this wave's needs.
- That means the next implementation phase must avoid pretending the verification/recovery architecture is already enforced locally.

## Coverage Not Yet Used

- Full benchmark grader implementation repositories behind:
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/`
  - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/`
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/`
  - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1/`
  - `research/sources/benchmarks/src_bnm_facefeed2020/`
- Additional BigAI verifier-heavy task families outside the required packet, especially `adaptive-rejection-sampler`.
- Additional A-Evolve Wave 02 trajectory slices.
- More KIRA `db-wal-recovery` trajectories for cwd-invalidation reproducibility.

## Support Track Updates

Support artifacts present:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_false_completion_matrix.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/trajectory_support_recovery_failure_matrix.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_verifier_recovery_failure_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/codebase_support_completion_cleanup_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/literature_support_verification_recovery_failure_cluster.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/eval_support_verifier_benchmark_contract_map.md`

Retired support artifact:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/outputs/informal_support_false_completion_recovery_cluster.md`

Control surfaces updated by this principal pass:

- update `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
- update `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- update `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`

Next governed step:

- run Wave 02 checklist adjudication against this principal synthesis, all five lane outputs, GPT contradiction, and Claude contradiction
