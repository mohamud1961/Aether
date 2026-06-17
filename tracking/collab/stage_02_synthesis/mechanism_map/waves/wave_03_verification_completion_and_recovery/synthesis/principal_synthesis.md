# Mechanism Map Wave 03 Principal Synthesis

Status date: 2026-04-08

Wave

- `wave_03_verification_completion_and_recovery`

Overall judgment

- Wave 03 materially strengthens `mechanism_map`.
- The strongest supported conclusion is that `verification`, `completion`, and `recovery` should not be treated as one merged mechanism family.
- The wave supports multiple real mechanism families inside this domain.
- All three contradiction passes converged on `pass_with_warnings`, not on a block to synthesis.
- The wave does not support a strong positive claim that `restart` or `restart-safe resumability` is already a stable cross-family mechanism.
- BigAI remains `behavioral reconstruction`.
- The required Wave 03 repair pass has now landed substantive source dossiers, trajectory case studies, literature theme dossiers, and support-artifact repairs.
- Checklist adjudication accepted Wave 03 with carry-forward warnings.
- Wave 03 is now accepted at the wave level, but it is not artifact completion and no family is `decision_ready`.

What this wave resolved

- `completion proof` is visibly multi-family rather than monolithic.
  - DeepAgents shows in-run, artifact-backed postcondition proof in the `db-wal-recovery` slice, where the agent writes `/app/recovered.json` and then runs explicit validation commands checking `json_length`, `db_length`, `keys_ok`, and `match_db` in the same trajectory (`research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`).
  - KIRA shows a source-backed two-step completion gate plus iterative retest closure, not just single-shot completion assertion (`research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`, `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`).
  - A-Evolve clearly separates agent `DONE`, external verification, and rollback/versioning (`research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py`, `research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/terminal2.py`, `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`).
  - BigAI shows verifier-mediated closure and recovery loops in direct traces and local reconstruction, but only as `behavioral reconstruction` (`research/analysis/bigai_trace_layer/output/question_answers.json`, `research/analysis/bigai_trace_layer/output/exemplar_runs.json`).
- `cleanup confirmation` is part of completion in the strongest slices, not an afterthought.
  - BigAI `cancel-async-tasks` requires delivery-directory hygiene before the run is treated as complete (`research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`).
  - DeepAgents `cancel-async-tasks` explicitly validates cancellation cleanup in the same run (`research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`).
  - A-Evolve's versioning and rollback surfaces show recovery as controlled state management rather than ad hoc cleanup (`research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`).
- `verifier state`, `grader state`, and `overall run success` must remain separate.
  - BigAI reconstruction explicitly records cases where verifier `PASSED` still coexists with overall run failure (`research/analysis/bigai_trace_layer/output/question_answers.json`).
  - DeepAgents visible eval code separates hard correctness checks, replay/state checks, and judge-style grading (`research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py`, `research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py`, `research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py`, `research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py`).
- `restart` and `resumability` are real substrate concerns, but not yet promoted as stable behavioral mechanism families.
  - Source and docs show checkpoint, rollback, resume, and session infrastructure in DeepAgents, A-Evolve, and KiraClaw (`research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`, `research/sources/codebases/deepagents/libs/cli/deepagents_cli/sessions.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`, `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`).
  - Informal and issue evidence shows these surfaces remain operationally brittle (`research/sources/issues/src_iss_613424e145e5/artifact.txt`, `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`, `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`, `research/sources/issues/src_iss_da41417f5655/artifact.txt`, `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`).
  - Direct trajectory evidence in this wave is still too thin to promote `restart-safe resumability` beyond `exploratory`.

What changed because of contradiction review

- I am not carrying forward any cross-family ranking such as `BigAI > DeepAgents > KIRA` for false-completion defense. The current evidence identifies different families; it does not justify a stable ranking.
- I am not treating DeepAgents' `db-wal-recovery` proof path as a mirrored framework verifier. The strongest current hypothesis is narrower:
  - the proof surface in the visible trajectory is agent-authored inline verification riding on the DeepAgents execution substrate, not clearly a built-in task-specific verifier implemented in the mirrored framework source (`research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`).
- I am promoting KiraClaw recovery-state surfaces more explicitly than the main codebase lane did.
  - `session_manager.py` and `run_log_store.py` show explicit session-state transitions and persisted run logs relevant to recovery and replay, even though direct restart-safe trajectory proof is still thin (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`).
- I am not treating the KIRA `extract-moves-from-video` support-matrix row as a defended success case.
  - The support matrix is useful for inventory, but the direct trajectory and the main trajectory lane preserve unresolved count contradictions and interrupted OCR, so this slice stays false-completion pressure rather than completion-proof support (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`, `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_failure_analyst.md`).
- I am keeping the formal-literature gap on cleanup explicit rather than smoothing it away.
  - the formal slice is strong on verifier stacks, replay, and checkpoint substrate, but weak on cleanup confirmation as its own completion criterion (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_papers_docs_analyst.md`).
- I am not treating the current literature support cluster as a stable anchor list on its own.
  - Several paper IDs surfaced there were later judged unusable or mismatched by the main literature lane, so the main literature output outranks the support cluster until that cluster is reconciled (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_support_verification_cluster.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_papers_docs_analyst.md`).

Promoted mechanism cards

```text
MECHANISM_CARD
- mechanism_id: artifact_backed_postcondition_proof
- name: Artifact-Backed Postcondition Proof
- short_definition: Completion is established by directly checking produced artifacts or live postconditions against task requirements rather than only accepting a self-asserted finish signal.
- mechanism_family: completion_proof
- harness_area: verification
- location_in_harness: post-task verification step inside the main run loop or immediately after task output is produced
- operational_shape: The agent or harness runs explicit checks over artifacts, state, or outputs, and only treats the task as complete once those checks match the required target condition.
- problem_it_addresses: false completion from plausible-but-unverified outputs
- direct_observations:
  - DeepAgents `db-wal-recovery` writes `/app/recovered.json` and then runs explicit validation commands checking JSON length, DB length, key set, sorted order, and DB equality in the same run.
  - DeepAgents `cancel-async-tasks` validates concurrency and cleanup conditions directly in-run.
- inferred_behavior:
  - Minimal-sufficient completion proof is a real family in this corpus and should remain visible against heavier verifier stacks.
- evidence_paths:
  - /Users/mohamud/Downloads/harnesseng/research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt
  - /Users/mohamud/Downloads/harnesseng/research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt
  - /Users/mohamud/Downloads/harnesseng/tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md
- evidence_types:
  - trajectory
- source_families:
  - deepagents
- task_regimes_observed:
  - db recovery
  - async cancellation cleanup
- likely_failure_modes_addressed:
  - false completion
  - missing artifact validation
  - cleanup omitted from stop rule
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - The exact task-specific verification logic is not yet traced to a mirrored DeepAgents framework source path; in the visible trajectory it appears as inline agent-authored verification.
- interaction_notes:
  - Interacts strongly with external grader layers and cleanup confirmation; may be sufficient in narrow task regimes without a dedicated verifier role.
- likely_tradeoffs:
  - Can be brittle if the agent chooses the wrong postcondition to check.
  - May under-cover tasks where correctness is hard to encode with direct artifact checks.
- simplicity_note:
  - Minimal-sufficient and important to preserve.
- likely_eval_implications:
  - Test whether direct artifact/state checks outperform judge-heavy completion on false-completion-sensitive tasks.
- likely_variant_axes:
  - inline agent-authored checks vs harness-provided checks
  - artifact equality vs partial postcondition checks
- confidence:
  - high
- open_questions:
  - Where should these checks live in the local harness: execution loop, verification block, or external eval adapter?
```

```text
MECHANISM_CARD
- mechanism_id: layered_verifier_grader_replay_separation
- name: Layered Verifier / Grader / Replay Separation
- short_definition: Completion-related judgment is split across distinct layers such as in-run verifier state, external grading or replay logic, and final run acceptance.
- mechanism_family: layered_completion_adjudication
- harness_area: verification
- location_in_harness: verifier loop, benchmark adapter, replay/eval stack, and post-run adjudication
- operational_shape: The system distinguishes between what the agent claims, what a verifier checks, what replay or grading logic scores, and whether the run is finally accepted.
- problem_it_addresses: premature closure and hidden mismatch between local success signals and real task success
- direct_observations:
  - A-Evolve separates `submit(\"DONE\")` from benchmark verification and rollback/versioning.
  - DeepAgents eval code separates hard assertions, replay/state checks, and LLM-judge paths.
  - BigAI reconstruction records runs where verifier `PASSED` still coexists with overall failure.
- inferred_behavior:
  - This is a recurrent cross-family mechanism family and one of the strongest Wave 03 findings.
- evidence_paths:
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/terminal2.py
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/evals/tests/evals/utils.py
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline/evaluation.py
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/deepagents/libs/evals/tests/evals/llm_judge.py
  - /Users/mohamud/Downloads/harnesseng/research/analysis/bigai_trace_layer/output/question_answers.json
- evidence_types:
  - source_code
  - eval_code
  - trajectory
  - official_doc
- source_families:
  - a-evolve
  - deepagents
  - BigAI
- task_regimes_observed:
  - benchmark verification
  - db recovery
  - long-running verifier-mediated tasks
- likely_failure_modes_addressed:
  - false completion
  - verifier pass misread as final success
  - unreconciled grading layers
- failure_role:
  - mixed
- contradictory_or_complicating_evidence:
  - BigAI remains behavioral reconstruction.
  - Benchmark captures for some families are README-level contracts rather than full grader implementations.
- interaction_notes:
  - Interacts strongly with cleanup confirmation, replay determinism, and benchmark contracts.
- likely_tradeoffs:
  - More layers create more mismatch opportunities and can make failure attribution harder.
- simplicity_note:
  - Powerful but easy to over-bundle; preserve the difference between minimal proof, replay proof, and judge proof.
- likely_eval_implications:
  - Evaluate disagreement rates between in-run proof, external grader, and final acceptance.
- likely_variant_axes:
  - direct artifact verification only
  - replay/state-diff layer
  - LLM-judge layer
  - combined layered stack
- confidence:
  - high
- open_questions:
  - What explains the BigAI runs where verifier `PASSED` but the overall run still failed?
```

```text
MECHANISM_CARD
- mechanism_id: cleanup_and_delivery_hygiene_gate
- name: Cleanup And Delivery Hygiene Gate
- short_definition: Completion requires confirming cleanup, delivery-directory state, or rollback hygiene, not only functional correctness.
- mechanism_family: completion_with_cleanup_confirmation
- harness_area: verification
- location_in_harness: post-task verifier, recovery controller, workspace/delivery checker
- operational_shape: The harness or agent treats workspace cleanliness, restored state, or cleaned cancellation paths as part of the completion contract.
- problem_it_addresses: runs that appear correct functionally but leave the workspace or delivery state in an invalid form
- direct_observations:
  - BigAI `cancel-async-tasks` requires delivery-directory cleanup before successful completion.
  - DeepAgents `cancel-async-tasks` explicitly validates cleanup after cancellation and failure.
  - Informal and issue sources repeatedly report false completion when target-side state or recovery state is not actually reconciled.
- inferred_behavior:
  - Cleanup confirmation is a real mechanism family in practice even though it is weakly represented in the formal slice.
- evidence_paths:
  - /Users/mohamud/Downloads/harnesseng/research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt
  - /Users/mohamud/Downloads/harnesseng/research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt
  - /Users/mohamud/Downloads/harnesseng/research/sources/issues/src_iss_5d861db09829/artifact.txt
  - /Users/mohamud/Downloads/harnesseng/research/sources/issues/src_iss_f07284ab370e/artifact.txt
  - /Users/mohamud/Downloads/harnesseng/research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt
  - /Users/mohamud/Downloads/harnesseng/research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py
- evidence_types:
  - trajectory
  - informal_source
  - engineering_writeup
  - source_code
- source_families:
  - BigAI
  - deepagents
  - a-evolve
  - operator issue clusters
- task_regimes_observed:
  - cancellation cleanup
  - stateful recovery
  - delivery-sensitive completion
- likely_failure_modes_addressed:
  - dirty delivery state
  - false completion from host-side success only
  - rollback or cleanup drift
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - Formal literature in this wave underrepresents cleanup confirmation as an explicit completion doctrine.
  - Some observed failures may be task-specific rather than universal.
- interaction_notes:
  - Interacts with external grader contracts, rollback/versioning, and terminal-state reconciliation after crashes.
- likely_tradeoffs:
  - Adds extra stop checks and can slow task closeout.
  - Can be underspecified if cleanup criteria are implicit rather than explicit.
- simplicity_note:
  - Often minimal sufficient when encoded clearly; more complex verifier stacks are not the only way to defend against false completion.
- likely_eval_implications:
  - Build evals that distinguish functional success from workspace/delivery hygiene success.
- likely_variant_axes:
  - no cleanup gate
  - file/workspace hygiene gate
  - full rollback or state-restore gate
- confidence:
  - high
- open_questions:
  - Which cleanup criteria are benchmark-enforced, and which are family-local doctrine?
```

Candidate mechanism not yet promoted

- `checkpoint_resume_substrate`
  - Evidence is strong that substrate exists in source and formal docs.
  - Evidence is weak that safe restart/resume is already behaviorally demonstrated across families in this wave.
  - Keep this candidate `exploratory` and carry it forward rather than promoting it as a stable Wave 03 mechanism card.

Support-track updates

- Already present and usable:
  - `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_and_recovery.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` now reflects that Wave 03 has principal synthesis complete and remains pre-checklist rather than `not started`
- Newly added in the repair pass and now usable:
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/checkpoint_restore_and_resumability.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/db_wal_recovery.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
- Deferred but still useful:
  - `trajectory_support_false_completion_cases.md`
  - `trajectory_support_recovery_restart_table.md`

What still requires another wave or repair

- `restart` and `restart-safe resumability` remain under-evidenced behaviorally and should be carried forward as a thin family rather than over-promoted.
- `trajectory_support_verification_matrix.md` is now repaired and keeps KIRA `extract-moves-from-video` as contested completion pressure rather than defended success.
- `literature_support_verification_cluster.md` is now repaired and excludes unusable or mismatched paper IDs from the promoted anchor set.
- `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting must continue to outrank organizer-based routing until that control surface is repaired.
- The Wave 03 direct BigAI verifier story remains incomplete without the named verifier-heavy slice `adaptive-rejection-sampler`.
- The main codebase claims for KIRA should continue carrying forward the KiraClaw state-machine and persisted-run-log surfaces that were stronger in the support map than in the main lane output.

Local harness implications

- The local harness should keep three separate surfaces rather than collapsing them:
  - agent completion signal
  - verification block
  - external grader or eval adapter
- The first concrete local baseline to prioritize is not an LLM judge.
  - It is artifact-backed postcondition proof plus explicit cleanup confirmation in `blocks/verification/` and `blocks/recovery/`.
- Recovery work should prioritize:
  - explicit terminal-state reconciliation after interruption or crash
  - structured tool-error typing
  - durable session and replay state that does not corrupt injected baseline state
- Relevant local comparison paths:
  - `runner/agent.py`
  - `runner/evaluator.py`
  - `runner/logger.py`
  - `blocks/verification/checkpoint_verify.py`
  - `blocks/verification/double_confirm.py`
  - `blocks/recovery/rollback.py`
  - `blocks/recovery/remediation_inject.py`
  - `evals/verification_eval.py`

Coverage used

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/brief.md`
- all five main lane outputs under `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/`
- all three contradiction reviews:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/contradiction_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/contradiction_analyst__claude.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/contradiction_analyst__gemini.md`
- support artifacts:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/eval_support_verifier_grader_replay_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_support_verification_cluster.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_support_recovery_issue_cluster.md`
- carry-forward control:
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Coverage not yet used

- `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
- direct benchmark implementation code behind the captured ImpossibleBench and SlopCodeBench surfaces
- broader DeepAgents eval test coverage beyond the focused files already read
- additional BigAI `extract-moves-from-video` endings or other verifier-heavy slices

Priority sources not yet read

- `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
- `research/sources/benchmarks/src_bnm_e1cfa2bf78c9/artifact.txt`
- `research/sources/informal/anthropic_long_running_harness.md`
- `research/sources/issues/src_iss_222a58240294/artifact.txt`
- `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`

Principal decision

- Wave 03 principal synthesis is complete.
- Wave 03 has real mechanism progress and should be carried forward into `cumulative_synthesis.md`.
- Wave 03 is accepted at the wave level with carry-forward warnings.
- Next required step:
  - update artifact-level carry-forward surfaces to reflect accepted status
  - open the next planned `mechanism_map` wave: `context_state_memory_workspace`
