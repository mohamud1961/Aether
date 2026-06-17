DEEP_SYNTHESIS_CONTRADICTION_OUTPUT
- artifact: mechanism_map
- wave: wave_03_verification_completion_and_recovery
- role: contradiction analyst (external Claude gate reviewer)
- review_model: Claude Opus 4.6
- overall_verdict: pass_with_warnings

---

## Preflight

- preflight_scope_confirmed:
  - Confirmed this is a contradiction review of the five first-pass lane outputs for the Wave 03 vertical mechanism-domain pass on verification, completion proof, false-completion defense, cleanup confirmation, rollback, restart, resumability, and recovery.
  - All five main-lane outputs and all six support artifacts were read in full before producing this review.
  - The cumulative synthesis from accepted Waves 01-02 was read as the baseline for carry-forward judgment.
  - The coverage register was read and shows Wave 03 still marked "not started" despite first-pass outputs existing; this is a process bookkeeping issue, not a content blocker.

- preflight_planned_read_order:
  - 1. Coverage register and cumulative synthesis for baseline state.
  - 2. All five first-pass lane outputs in order: trajectory, codebase, literature, informal, eval.
  - 3. All six support artifacts: trajectory verification matrix, codebase verifier/recovery map, eval verifier/grader/replay matrix, literature verification cluster, informal recovery issue cluster.
  - 4. The wave brief for scope and contract conformance checking.

- preflight_critical_sources_selected:
  - All five lane outputs and all six support artifacts are the primary sources for this contradiction review.
  - The cumulative synthesis and coverage register are the baseline anchors.
  - The wave brief is the contract reference.

- preflight_coverage_risks:
  - This review depends entirely on what the lanes reported reading. Any evidence the lanes silently skipped is invisible to this pass.
  - The primary contradiction analyst file is empty, so this Claude review has no prior contradiction pass to build on or challenge.

- preflight_likely_blind_spots:
  - I cannot independently verify whether trajectory readings were complete or selective within each file.
  - I cannot assess whether paper text matched metadata unless a lane explicitly flagged it.
  - The Gemini gate review has not been produced yet, so I cannot cross-check against another external reviewer.

- preflight_blockers:
  - None. All five lane outputs are substantive and internally structured enough for honest contradiction review.

---

## Coverage Assessment

- coverage_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_failure_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_source_reconstruction_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_papers_docs_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_issues_postmortems_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/eval_benchmark_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/eval_support_verifier_grader_replay_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_support_verification_cluster.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_support_recovery_issue_cluster.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/brief.md`

- coverage_not_yet_used:
  - Direct trajectory files, source files, papers, issues, and benchmarks were not independently re-read in this contradiction pass. Contradiction review is limited to cross-lane consistency, evidence-claim tracing, and coverage honesty checking, not primary source re-reading.

- evidence_classes_touched:
  - All evidence classes are touched indirectly through the lane outputs: trajectories, mirrored codebases, archived code captures, papers, docs, informal sources, issues, postmortems, benchmark captures, relevant local analysis, relevant local harness code, and support artifacts.

- priority_sources_not_yet_read:
  - Not applicable for this role. All lane outputs were read in full.

---

## Supported Findings

The following cross-lane claims are well-supported by multiple lanes with traceable evidence:

1. **Verification, completion, and recovery are not one merged mechanism family.** All five lanes independently converge on this. The trajectory lane identifies at least three behavioral families (DeepAgents self-audit, KIRA iterative-retest, BigAI verifier-mediated gating). The codebase lane identifies at least four source-backed families (KIRA two-step gate, DeepAgents checkpoint/resume, A-Evolve separated completion/evaluation/rollback, BigAI behavioral reconstruction). The literature lane shows formal support for multi-layered verification. The eval lane shows three distinct grading families in DeepAgents alone. The informal lane reinforces that completion-looking behavior and verified completion are distinct. Confidence: high. This is the wave's strongest cross-lane finding.

2. **Completion is at least three-layered.** This was already emerging in cumulative synthesis from Wave 02. Wave 03 strengthens it with direct source evidence from A-Evolve (solver `submit("DONE")` versus benchmark `container.run_verification` versus eval adapter), trajectory evidence from BigAI (verifier pass ≠ overall success), and eval evidence from DeepAgents (hard assertion versus soft efficiency versus LLM judge). All five lanes reinforce it. Confidence: high.

3. **Cleanup confirmation and delivery hygiene are load-bearing completion mechanisms, not secondary niceties.** The trajectory lane shows BigAI cancellation runs failing until delivery-directory cleanup is complete. The codebase lane shows A-Evolve rollback as version-controlled state management. The informal lane shows operational reports treating validation/review as part of completion. The eval lane shows tau2 using DB-state replay as a hard gate. The literature lane explicitly notes that cleanup confirmation is underrepresented in formal sources, which is itself an honest coverage signal. Confidence: high.

4. **Restart/resumability is empirically weaker than verification and cleanup.** The trajectory lane explicitly says restart and resumability remain under-evidenced. The codebase lane shows DeepAgents has strong checkpoint/resume infrastructure but the task-level completion path is source-light. The informal lane shows resume surfaces are operationally brittle (stale indexes, lost state, non-terminal crashes). The literature lane notes a tension between formally available resume substrate and empirically demonstrated restart safety. The eval lane confirms restart evidence is thinner than verification/replay. Confidence: high. All lanes agree on this gap.

5. **BigAI remains strictly behavioral reconstruction.** Every lane that touches BigAI explicitly labels it as behavioral reconstruction. No lane silently upgrades it. This is contract-compliant. Confidence: high.

6. **KIRA's false-completion defense is weaker in practice than its source design implies.** The trajectory lane shows KIRA extract-video completing with unresolved count contradictions. The codebase lane identifies this as a source-behavior mismatch. The informal lane uses it as contradiction pressure. The literature lane and eval lane do not independently challenge this finding. Confidence: high.

---

## Unsupported or Overclaimed Findings

1. **Cross-family ranking of false-completion defenses.** The trajectory lane claims BigAI is strongest, DeepAgents next, and KIRA weakest. This ranking is anchored in a narrow trajectory sample (three task families, with extraction evidence thin for two of the three families). The codebase lane does not independently validate the ranking — it confirms each family has distinct mechanisms but does not rank them. The eval lane shows DeepAgents has multiple grading families, but does not compare their false-completion defense against BigAI's observed behavior. The informal lane adds contradiction pressure but not ranking evidence. This ranking should be downgraded from a claim to a hypothesis. Confidence: medium, but presented with insufficient qualification in the trajectory output.

2. **DeepAgents' task-level completion proof is "simple."** The trajectory lane frames DeepAgents' db-wal-recovery postcondition checking as a "minimal-sufficient" or "simple" baseline against "prestige verifier stacks." But the eval lane shows DeepAgents actually has a rich, multi-family eval infrastructure including `TrajectoryScorer`, BFCL fresh-state replay, tau2 DB replay, and LLM-judge paths. The codebase lane confirms checkpoint/resume infrastructure is substantial. The framing of DeepAgents as the "simple baseline" against KIRA's "built-in gate" and BigAI's "prestige verifier" is reductive. DeepAgents may produce simple-looking trajectory behavior while having complex eval infrastructure underneath. This conflation of trajectory-visible simplicity with mechanism simplicity is a reconciliation failure.

3. **KIRA extract-video as a reusable mechanism-family pattern.** The trajectory lane flags this at medium confidence. But it rests on a single trajectory from a single task. The codebase lane shows KIRA has a source-backed two-step completion gate, but the extract-video failure is more likely a perception/OCR reliability problem than a systematic completion-gate mechanism failure. Elevating one hard-perception task failure into a "mechanism family pattern" risks over-reading a task-difficulty problem as an architecture problem. The informal lane's external-device false-completion issue is a different phenomenon (no target verification at all) rather than the same phenomenon (conflicting counts despite review).

4. **Formal literature "overrepresents" verifier architectures.** The literature lane claims this, and it may be true about the selected corpus. But the lane also explicitly notes that several candidate papers were unusable due to text/metadata mismatch, and multiple unread papers remain in the priority queue. It is premature to conclude the *formal literature in general* overrepresents verifiers when the reading was incomplete and several strong formal sources were excluded by capture quality, not by content irrelevance.

---

## Missing Evidence Classes

1. **Adaptive-rejection-sampler trajectories.** The wave brief explicitly names this verifier-heavy slice as a target. All five trajectory-reading lanes acknowledge it as unread. This is the single largest trajectory gap for a wave centered on verification, because this slice was specifically selected as a verifier-intensive case. The trajectory lane lists it as a priority unread source, and the eval lane notes BigAI verifier-heavy exemplars pointed to by `exemplar_runs.json` are still unread. This does not block the wave, but it weakens any claim about BigAI verifier-mediated recovery being "understood" at more than a surface behavioral level.

2. **DeepAgents eval subtree depth.** The eval lane read the main eval files, but explicitly acknowledges unread DeepAgents eval tests beyond the focused files. The codebase lane notes the same gap. This matters because DeepAgents' task-level completion proof is a central claim in the wave yet remains source-light on the exact verification pathways.

3. **Benchmark implementation code.** All three benchmark captures (SWE-bench Verified, ImpossibleBench, SlopCodeBench) were read at the contract/README level only. No grader implementation code was read. This is appropriate for a first pass, but the eval lane should be cautious about claims regarding "benchmark completion contracts" when only marketing/README surfaces were inspected.

4. **Broader KIRA runtime surfaces.** The codebase support map went deeper into KiraClaw than the main codebase lane output acknowledges. The support map found `session_manager.py` with explicit state transitions (`queued → running → completed → failed`), `run_log_store.py` for replay/persistence, and release verification scripts. These findings appear in the support artifact but are underutilized in the main codebase lane output, creating a visibility gap between what was read and what was promoted.

5. **Additional postmortems and informal sources.** The informal lane explicitly deferred `src_pmt_ca79e818d699`, `src_pmt_afc13590bd50`, and `anthropic_long_running_harness.md`. These are relevant to the wave's recovery/long-running questions but not blocking.

---

## Reconciliation Failures

1. **Trajectory-codebase reconciliation gap on DeepAgents task-level verification.** The trajectory lane shows strong artifact-backed verification checks in db-wal-recovery (JSON length, DB length, key checks, `match_db`). The codebase lane cannot find the source that produces those checks, calling it "source-light on task-specific completion proof." The eval lane shows DeepAgents has rich eval infrastructure. These three lanes each see a piece but do not reconcile them: Where does the verification script that runs inside the trajectory actually come from? Is it agent-generated inline code? Is it a task-harness fixture? Is it Deep Agents' eval infrastructure running at execution time? This is one of the most important open questions for this wave and none of the lanes attempt even a hypothesis.

2. **Codebase support versus codebase main on KiraClaw depth.** The codebase support verifier recovery map reads extensively into KiraClaw's `session_manager.py`, `run_log_store.py`, `engine.py`, `scheduler_runtime.py`, and desktop daemon/IPC surfaces. The main codebase lane output cites `terminus_kira.py` and the prompt template as its primary KIRA sources, with KiraClaw mentioned only as a broader runtime. The support artifact's findings about explicit state-machine transitions and release verification scripts are directly relevant to the wave's completion and recovery questions but are not visibly promoted into the main lane's mechanism claims.

3. **Literature-trajectory reconciliation on cleanup confirmation.** The literature lane correctly identifies that cleanup confirmation is underrepresented in formal sources but strong in direct evidence. The trajectory lane shows cleanup is load-bearing in BigAI cancellation. The informal lane shows that external-device completion without target proof is a known failure mode. But no lane attempts to explain *why* the formal literature gap exists — is it because cleanup confirmation is considered "mere engineering" by the academic community? Is it because cleanup is task-domain-specific and harder to formalize? This matters because the wave packet explicitly includes cleanup confirmation as a required case slice, and the formal gap should be characterized, not just flagged.

4. **Eval-trajectory reconciliation on verifier pass ≠ success.** The eval lane cites `question_answers.json` reporting 17 runs where BigAI verifier `PASSED` but overall run failed. The trajectory lane cites the same source. But neither lane explains *what makes those 17 runs fail despite passing verification.* Is it cleanup? Is it delivery hygiene? Is it a grader/external-evaluator mismatch? This is the core of the "completion is multi-layered" claim and it deserves more than a citation count.

---

## Coverage Blind Spots

1. **Video extraction task family is effectively a coverage hole.** DeepAgents `extract-moves-from-video` is an immediate cancellation abort. BigAI `extract-moves-from-video` is inconclusively cut off. Only KIRA `extract-moves-from-video` provides real completion evidence, and that evidence is the wave's primary false-completion case. This means the wave's third required task family is supported by exactly one usable trajectory, making cross-family claims about video extraction verification unusable at the family level.

2. **No trajectory or source evidence for true restart-safe resumption.** All lanes agree this is thin. But the wave brief lists "restart, resumability, and recovery discipline" as a required case slice. The current outputs can characterize the *absence* of evidence but cannot support positive mechanism claims about restart safety. This should be explicitly surfaced as a wave-level gap rather than left as lane-level observations.

3. **The organizer is empty.** The informal lane explicitly notes that `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` was empty on read. This means none of the lanes had organizer-based routing. This is a process gap that should be noted but does not invalidate the lane outputs since all lanes used direct source reading and wave brief guidance instead.

4. **Coverage register is stale.** The coverage register still says Wave 03 is "not started" even though all first-pass outputs exist. This needs updating before principal synthesis.

---

## Support Artifact Gaps

- All six planned support artifacts exist and are substantive.
- The trajectory support verification matrix is the strongest support artifact. It provides a run-by-run table that grounds most trajectory claims.
- The codebase support verifier recovery map is deep and reads more KiraClaw surface area than the main codebase lane output acknowledges. The principal synthesis should make use of KiraClaw's explicit state-machine transitions and release verification scripts.
- The eval support verifier grader replay matrix is well-structured and correctly distinguishes benchmark contracts from grader code from observed behavior.
- The literature support verification cluster is honest about yield, marking several papers as "caveated or lower-yield" rather than inflating coverage.
- The informal support recovery issue cluster correctly identifies six thematic clusters and explicitly flags one capture as unusable evidence.
- Two support artifacts planned in the wave brief are still missing: `trajectory_support_false_completion_cases.md` and `trajectory_support_recovery_restart_table.md`. Both were deferred by the trajectory lane with justification, but their absence weakens the wave's coverage on two of its four required case slices (false completion, and restart/recovery).

---

## Coverage Register Consistency

- The coverage register needs immediate update to reflect that Wave 03 first-pass lane outputs are drafted.
- The coverage register correctly preserves the BigAI behavioral reconstruction caveat and the repo-state-safe cleanup warning from Wave 02.
- The coverage register's first dossier set (KIRA, deepagents, a-evolve, claw-code, BigAI behavioral) is unchanged and still marked as incomplete. The wave brief requires dossier updates for these systems plus eval/informal dossiers, and none have been updated yet.

---

## Required Repairs Before Acceptance

1. **Reconcile the DeepAgents task-level verification source gap.** At least one lane must attempt a hypothesis about where the trajectory-visible verification checks originate (agent-generated inline code, task fixture, eval harness injection, or unseen source). Currently three lanes see the gap and none explain it. This is the strongest remaining reconciliation failure.

2. **Downgrade the cross-family false-completion ranking to a hypothesis.** The trajectory lane's ranking (BigAI > DeepAgents > KIRA) should be explicitly labeled as a hypothesis from narrow trajectory evidence rather than a supported wave-level claim. The eval lane's evidence about DeepAgents' rich infrastructure challenges the "simple baseline" framing.

3. **Update the coverage register.** Mark Wave 03 as "first-pass outputs drafted" with explicit lane-level status notes.

4. **Surface restart/resumability as a wave-level gap, not just lane-level observations.** All five lanes agree restart evidence is thin. The principal synthesis must explicitly say this wave cannot produce positive mechanism claims about restart safety, only characterize the absence and the formal/source availability of the substrate.

---

## Optional Pressure Tests

1. **Read `adaptive-rejection-sampler` trajectories.** This is the wave brief's named verifier-heavy target and remains entirely unread. Even a partial read would materially strengthen or challenge the BigAI behavioral reconstruction of verifier-mediated recovery.

2. **Trace DeepAgents eval paths from trajectory back to source.** Find where the db-wal-recovery verification script in the trajectory is generated or injected. This would close the strongest reconciliation failure.

3. **Read one additional BigAI `extract-moves-from-video` trajectory.** The current partial read provides no terminal verification marker. Even confirming the trajectory is truly inconclusively truncated versus simply unfinished would improve coverage honesty.

4. **Promote KiraClaw session-manager and release-verification findings.** The codebase support map already read these. They should appear in the main codebase lane output or at least be explicitly cited in principal synthesis.

5. **Attempt a hypothesis on the literature gap for cleanup confirmation.** Even a speculative hypothesis about why cleanup confirmation is formally underrepresented would help the principal synthesis characterize the gap rather than merely flag it.

---

## Gate Review Recommendations

1. **This wave is ready for principal synthesis with the required repairs above.** The core findings are well-supported across lanes, the coverage accounting is honest, and the support artifacts are substantive.

2. **Do NOT accept cross-family rankings or mechanism-family completeness claims at this stage.** The evidence supports mechanism-family *identification* but not *ranking* or *completeness*.

3. **The principal synthesis should explicitly frame restart/resumability as a deferred mechanism domain** where substrate exists in source and formal literature but empirical behavior evidence is too thin for promoted claims.

4. **Keep the false-completion story honest.** The wave has one strong false-completion case (KIRA extract-video), one category-different false-completion case (external-device completion without target proof from informal issues), and good trajectory evidence that verification prevents false completion in WAL and cancellation tasks. Do not inflate this into a general "false completion is solved by verifiers" claim; it is more accurately "false completion risk correlates with perception difficulty and proof-surface availability."

5. **The coverage register update is a hard prerequisite for principal synthesis**, not an optional cleanup step.

---

## Confidence Notes

- High-confidence findings: multi-family structure, multi-layered completion, cleanup as load-bearing, restart/resume gap, BigAI behavioral-reconstruction discipline.
- Medium-confidence concerns: DeepAgents "simple baseline" framing, cross-family ranking, KIRA extract-video as mechanism pattern versus task-difficulty artifact.
- The overall verdict of `pass_with_warnings` reflects that the lane outputs are honest, well-structured, and cover the required evidence classes, but have identifiable reconciliation failures and one overclaimed ranking that should be repaired before the wave is accepted at the principal synthesis level.

---

## Support Artifacts Used

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/trajectory_support_verification_matrix.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/codebase_support_verifier_recovery_map.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/eval_support_verifier_grader_replay_matrix.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/literature_support_verification_cluster.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/outputs/informal_support_recovery_issue_cluster.md`

## Support Artifacts Requested or Deferred

- `trajectory_support_false_completion_cases.md` — deferred by trajectory lane, creates wave-level gap on one of four required case slices
- `trajectory_support_recovery_restart_table.md` — deferred by trajectory lane, creates wave-level gap on one of four required case slices

## Coverage Register Updates Needed

- Mark Wave 03 as "first-pass outputs drafted, pending contradiction and principal synthesis."
- Update dossier status for all five required system dossiers and two required thematic dossiers.
- Keep organizer-empty caveat explicit.

## Required Dossier Updates

- `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
- `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
- `tracking/collab/stage_02_synthesis/eval_benchmark_dossiers/verification_completion_and_recovery.md`
- `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/verification_completion_and_recovery.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/checkpoint_restore_and_resumability.md`
