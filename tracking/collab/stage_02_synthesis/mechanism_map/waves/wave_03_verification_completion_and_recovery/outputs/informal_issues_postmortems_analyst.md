INFORMAL_ISSUES_POSTMORTEMS_OUTPUT
- artifact: `mechanism_map`
- role: `informal/issues/postmortems analyst`
- preflight_scope_confirmed:
  - observation: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/brief.md` explicitly defines this as a vertical mechanism-domain wave centered on `verification_completion_and_recovery`, not a generic execution-control pass.
  - observation: The wave brief explicitly names trajectories as the primary empirical anchor and codebase/source reconstruction as the primary implementation anchor. This lane uses informal sources as contradiction pressure and operator reality, not as the top evidence tier.
  - observation: The same brief activates the eval/benchmark fifth lane because verifier, grader, replay, and completion-contract logic are load-bearing in this wave.
  - observation: `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` includes the issue and postmortem source IDs used in this pass.
  - observation: `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` was empty on read, so the scope anchor had to come from the wave brief, manifest, coverage register, direct reads, and other lane outputs rather than organizer routing.
  - observation: A minimal-sufficient completion pattern that must remain visible is direct artifact-backed proof without a prestige verifier stack, as seen in DeepAgents `db-wal-recovery` where the run checks `json_length 11`, `db_length 11`, `keys_ok True`, and `match_db True`: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`.
  - observation: Strong first-pass coverage for this lane required at least one bounded issue-clustering artifact plus direct trajectory/source pressure from other lanes. Those supports now exist in `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_support_recovery_issue_cluster.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`, and `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`.
  - inference: There is enough trajectory visibility, source visibility, and operational-report visibility to do an honest first-pass informal lane output, but not enough to claim restart/resume stability across families.
- preflight_planned_read_order:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/brief.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - prior and same-wave lane outputs used as routing aids
  - direct trajectory anchors for completion proof, cleanup confirmation, false-completion pressure, and behavioral reconstruction
  - high-signal postmortems and informal docs on long-running harnesses, monitoring, eval realism, resume/control flow, and self-verification
  - selected issue cluster on false completion, resume drift, crash recovery, rewind corruption, and recovery-hint opacity
- preflight_critical_sources_selected:
  - trajectory anchors:
    - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
    - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
    - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - same-wave routing aids:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_failure_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_source_reconstruction_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_support_verification_cluster.md`
  - informal and postmortem pressure:
    - `research/sources/informal/langchain_anatomy_of_harness.md`
    - `research/sources/informal/humanlayer_12_factor_agents.md`
    - `research/sources/informal/cursor_long_running_agents.md`
    - `research/sources/informal/openai_monitor_misalignment.md`
    - `research/sources/informal/cursor_cursorbench.md`
    - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
    - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
  - issue pressure:
    - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
    - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
    - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
    - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
    - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
    - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
    - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
    - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_support_recovery_issue_cluster.md`
- preflight_coverage_risks:
  - observation: `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` is empty, so organizer-based coverage claims are unavailable.
  - observation: The selected issue cluster is skewed toward Codex and Claude operational surfaces, with one OpenHands issue and one Google ADK issue as cross-family pressure rather than balance.
  - observation: Several informal sources are vendor-authored self-reports or design essays rather than neutral failure analyses.
  - observation: Restart/resume behavior is richly represented in issues but only lightly visible in direct trajectories for this wave.
  - observation: `research/sources/issues/src_iss_949d7288362a/artifact.txt` did not resolve to the titled interruption/resume issue and cannot be trusted as evidence without recapture.
  - inference: This pass is strong for contradiction pressure and mechanism-shaping operator claims, but weaker for prevalence estimates and weaker for source-backed restart/resume doctrine.
- preflight_likely_blind_spots:
  - unread long-tail issue clusters outside the selected recovery/resume/false-completion family
  - benchmark or replay-contract specifics that may explain which cleanup or delivery-hygiene checks are family-local versus evaluator-enforced
  - additional postmortems such as `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt` and `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - broader informal reads on Anthropic-specific long-running harnesses or Cursor self-driving codebases beyond the sampled documents
- preflight_blockers: `[]`
- coverage_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/brief.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/README.md`
  - `prompts/deep_synthesis_support_subagent_prompt.md`
  - `prompts/deep_synthesis_informal_issues_postmortems_analyst_prompt.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_failure_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_source_reconstruction_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_support_verification_cluster.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_support_recovery_issue_cluster.md`
  - `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/a1ed78b8-5ec9-4fb3-8a5a-e881a75c3bec-traj.txt`
  - `research/sources/trajectories/BigAI/db-wal-recovery/e150eebe-6edd-4306-9d61-0b60351e4fa0-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - `research/sources/informal/langchain_anatomy_of_harness.md`
  - `research/sources/informal/humanlayer_12_factor_agents.md`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/openai_monitor_misalignment.md`
  - `research/sources/informal/cursor_cursorbench.md`
  - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_949d7288362a/artifact.txt`
  - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
  - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
  - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
  - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
  - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
- coverage_not_yet_used:
  - `research/sources/informal/anthropic_long_running_harness.md`
  - `research/sources/informal/cursor_self_driving_codebases.md`
  - `research/sources/informal/cursor_agent_sandboxing.md`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_15bd3d2d6a1d/artifact.txt`
  - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - `research/sources/benchmarks/**`
  - `research/sources/codebases/deepagents/libs/evals/**`
- evidence_classes_touched:
  - `trajectories`
  - `informal sources`
  - `issues`
  - `postmortems`
  - `relevant local analysis`
  - `support artifacts`
- priority_sources_not_yet_read:
  - `research/sources/informal/anthropic_long_running_harness.md`
  - `research/sources/informal/cursor_self_driving_codebases.md`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_15bd3d2d6a1d/artifact.txt`
  - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - `research/sources/benchmarks/src_bnm_e5f985948a0e/capture.json`
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5/capture.json`
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_support_recovery_issue_cluster.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_support_verification_cluster.md`
- support_artifacts_requested_or_deferred:
  - `long-tail issue clustering outside the selected verification/recovery families deferred`
  - `dedicated informal false-completion case table deferred because the selected KIRA and external-device cases already surface the main contradiction pressure`
- coverage_register_updates_needed:
  - `Mark the Wave 03 informal lane as first-pass drafted with strong contradiction pressure on false completion, stale resume state, crash recovery, and rewind corruption.`
  - `Keep visible that operator writeups support verification loops and isolated execution, but issue evidence says resume and recovery implementations remain brittle in field use.`
  - `Keep the empty organizer caveat explicit rather than implying routing completeness.`
- required_dossier_updates:
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_and_recovery.md`
- high_signal_operating_claims:
  - claim: Completion is being pushed toward evidence-backed postconditions rather than mere command success.
    observation: `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt` describes Codex workflows where logs, metrics, traces, review loops, and app-driving validation are part of getting work to reliable completion. `research/sources/informal/cursor_cursorbench.md` argues that offline graders can say output is correct while the result still feels worse to developers. Direct trajectory evidence shows DeepAgents `db-wal-recovery` verifying `json_length 11`, `db_length 11`, and `match_db True`, while BigAI `cancel-async-tasks` does not pass until delivery-directory cleanliness is verified: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`, `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`.
    inference: The strongest operational doctrine in the sampled informal lane is that trustworthy completion requires an evidence surface beyond "the command exited 0" or "the agent said done."
    confidence: `high`
  - claim: Long-running autonomy requires explicit pause/resume and restart surfaces, but the field implementations remain unstable.
    observation: `research/sources/informal/humanlayer_12_factor_agents.md` frames launch/pause/resume and interruptibility between tool selection and tool invocation as a baseline orchestration requirement. `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` presents the Codex app as a multi-agent control surface that preserves session history and isolated worktrees across long-running work. Against that, `research/sources/issues/src_iss_613424e145e5/artifact.txt`, `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`, `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`, `research/sources/issues/src_iss_da41417f5655/artifact.txt`, and `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt` report stale resume indexes, hours-old restored snapshots, permanently thinking threads after crashes, browser-crash hangs, and silent resume failure after API errors.
    inference: Resume/recovery is a real mechanism family in operator doctrine, but it is not yet a stable cross-system capability in fielded implementations.
    confidence: `high`
  - claim: Recovery quality depends on explicit terminal states and structured error semantics, not just better prompts.
    observation: `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt` reports that a crashed thread remained unusable because the persisted rollout ended with an unfinished reasoning event and no terminal marker. `research/sources/issues/src_iss_f07284ab370e/artifact.txt` argues that recoverable versus fatal tool errors are already classified internally, but the agent still receives unstructured strings that hide whether retry is sensible. `research/sources/informal/humanlayer_12_factor_agents.md` recommends compacting errors into context with explicit recovery logic and bounded retry handling.
    inference: Missing terminal-state reconciliation and missing error typing are not minor UX flaws; they directly shape whether the harness can recover or only hang and guess.
    confidence: `high`
  - claim: False-completion risk is most acute when target-side effects or cleanup requirements live outside the immediate file-edit loop.
    observation: `research/sources/issues/src_iss_5d861db09829/artifact.txt` reports repeated `[completed]` claims after host-side copy operations with no target-device verification. `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt` shows unresolved contradictory counts `201`, `230`, and `262` before `mark_task_complete`. `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt` shows that delivery-directory cleanup itself is part of passing verification.
    inference: Tasks with external devices, perception-heavy extraction, or cleanup-sensitive delivery need a distinct proof surface; local command success is an unsafe stop rule.
    confidence: `medium`
    weakening_factors: The external-device case is a single issue report, and the KIRA extract-video case is trajectory-only without source or benchmark reconciliation yet.
- issue_and_postmortem_findings:
  - finding: Resume state drift is a recurrent operational failure mode rather than a niche annoyance.
    observation: `research/sources/issues/src_iss_613424e145e5/artifact.txt` reports missing or stale session indexes, while `research/sources/issues/src_iss_edac72dd9b31/artifact.txt` reports resumed context landing hours behind the actual work state.
    inference: Resume surfaces are currently vulnerable both at discovery/index time and at snapshot selection or reconstruction time.
    confidence: `high`
  - finding: Crash recovery often fails because the system never writes or reconstructs a safe terminal state.
    observation: `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt` reports permanent `thinking` after extension crash due to an unfinished reasoning tail with no terminal event. `research/sources/issues/src_iss_da41417f5655/artifact.txt` reports an agent stuck forever after browser crash because no watchdog or browser health check exists. `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt` reports silent failure resuming a subagent whose transcript ended in API error.
    inference: A cross-system recovery baseline needs explicit terminalization of interrupted work plus watchdog or error-path repair, not only persistence.
    confidence: `high`
  - finding: Restore or rewind can destroy essential state if the harness only trusts event-stream deltas.
    observation: `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt` reports rewind nullifying initial session-state keys that were injected at session creation rather than emitted as events.
    inference: Checkpoint/rewind logic that fails to distinguish baseline state from later mutations is a recovery hazard, not a mere implementation detail.
    confidence: `high`
  - finding: Operational product writeups assume stronger supervision loops than the issue corpus says users reliably have.
    observation: `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt` and `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` describe review queues, worktrees, local validation, and automation inboxes as part of the working loop. `research/sources/issues/src_iss_5d861db09829/artifact.txt` and the selected resume/crash issues show that users still encounter unverified completion, stale resume state, and manual repair workflows.
    inference: The operator doctrine is ahead of the default field reliability, which makes postmortems useful as aspiration and design pressure but insufficient as completion evidence on their own.
    confidence: `high`
  - finding: Structured recovery hints remain underexposed to the agent despite being treated as necessary by builders.
    observation: `research/sources/issues/src_iss_f07284ab370e/artifact.txt` asks for surfacing `error_type`, `recoverable`, and `hint` fields to the model. `research/sources/informal/langchain_anatomy_of_harness.md` and `research/sources/informal/humanlayer_12_factor_agents.md` both frame verification loops, compacted errors, and bounded retries as harness-level mechanisms rather than optional polish.
    inference: The corpus is converging on recovery metadata as a mechanism family input, but many live surfaces still hand the model opaque strings instead.
    confidence: `medium`
    weakening_factors: The main direct evidence here is a feature request plus general design prose rather than a source-backed deployed implementation.
- contradiction_or_support_notes:
  - note: Minimal-sufficient completion proof remains a live counterweight to heavyweight verifier stacks.
    observation: DeepAgents `db-wal-recovery` reaches strong closure through direct artifact-vs-database checks without a separate prestige verifier role: `research/sources/trajectories/deepagents/db-wal-recovery/0333a30b-2678-4f0e-a672-26279fd01b7a-traj.txt`. `research/sources/informal/langchain_anatomy_of_harness.md` and `research/sources/informal/humanlayer_12_factor_agents.md` both argue that harnesses should externalize state, compact errors, and run bounded verification loops.
    inference: The informal lane supports preserving simple proof mechanisms rather than letting layered verifier architectures crowd them out.
    confidence: `high`
  - note: Vendor claims about long-running, production-ready agents are under real contradiction pressure from false-completion and resume failures.
    observation: `research/sources/informal/cursor_long_running_agents.md` describes long-running agents as more thorough and more production-ready, and `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` presents long-running multi-agent work as routine. Against that, `research/sources/issues/src_iss_613424e145e5/artifact.txt`, `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`, and `research/sources/issues/src_iss_5d861db09829/artifact.txt` show stale or missing resume state and unverified completion.
    inference: The wave should treat long-running success stories as operator claims requiring reconciliation with failure reports, not as settled mechanism evidence.
    confidence: `high`
  - note: Isolation of code copies does not solve control-plane corruption.
    observation: `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt` emphasizes isolated worktrees and separate threads, while `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt` shows that persisted thread state can still be malformed enough to poison both the original and cloned thread.
    inference: Repo/worktree isolation and session/control-state integrity are separate mechanism layers; progress on one should not be mistaken for closure on the other.
    confidence: `medium`
    weakening_factors: The control-plane corruption example is concentrated in one harness family.
  - note: KIRA's visible completion discipline is weaker in practice on perception-heavy tasks than its checklist rhetoric implies.
    observation: The trajectory lane shows KIRA `cancel-async-tasks` eventually earning strong retest-backed closure, but `extract-moves-from-video` still marks completion after unresolved count contradictions: `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`, `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`.
    inference: A built-in completion checklist does not, by itself, guarantee robust false-completion defense on harder multimodal tasks.
    confidence: `high`
  - note: Monitoring and online evaluation are converging on the same operational concern as this wave: completion-looking behavior can still be behaviorally wrong.
    observation: `research/sources/informal/openai_monitor_misalignment.md` describes post-run monitoring that flags actions inconsistent with user intent, while `research/sources/informal/cursor_cursorbench.md` argues that offline graders can miss output that feels worse to developers.
    inference: Informal operator literature is reinforcing the wave's central distinction between apparent completion and verified, behaviorally aligned completion.
    confidence: `medium`
    weakening_factors: These sources are vendor-authored and do not directly prove specific mechanism implementations in the sampled harness families.
- unvalidated_leads:
  - `research/sources/issues/src_iss_949d7288362a/artifact.txt` should be treated as capture-validation debt because the artifact content did not match the titled interruption/resume issue on read.
  - `research/sources/issues/src_iss_222a58240294/artifact.txt` likely adds pressure on resume unavailability after large-file reads, but it was not opened in this pass.
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt` may sharpen eval-doctrine pressure, but it was not read here.
  - `research/sources/informal/anthropic_long_running_harness.md` may materially sharpen reset-and-handoff claims if opened in follow-up.
- confidence_notes:
  - High-confidence claims in this output are limited to cases where issue pressure, trajectory evidence, and operator writeups point in the same direction.
  - Medium-confidence claims mostly come from vendor-authored informal sources, single-issue exemplars, or places where source/eval reconciliation is still pending.
  - Low-confidence promoted claims were avoided; weakly supported ideas were left as leads or open questions instead.
- open_questions:
  - Which systems in the corpus show restart-safe resumability directly in trajectories or visible source, rather than only in product prose or issue requests?
  - Is delivery-directory cleanliness a benchmark or verifier contract in this wave, or a family-local BigAI doctrine?
  - What is the minimal baseline the local harness should implement first: explicit terminal-state reconciliation, structured tool-error recovery hints, or artifact-backed completion checks?
  - How often do checkpoint or rewind mechanisms preserve execution state but still lose business-critical injected state, as in `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`?
  - Does additional read coverage on Anthropic and Cursor informal sources change the present judgment that resume/recovery is mechanistically real but operationally brittle?
- next_hand_off_target: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/contradiction_analyst.md`
