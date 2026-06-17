DEEP_SYNTHESIS_CONTRADICTION_OUTPUT
- artifact: failure_taxonomy / wave_03_context_state_memory_workspace_failures
- role: contradiction analyst (Claude gate reviewer)
- overall_verdict: pass_with_warnings

- preflight_scope_confirmed:
  - Confirmed this is a vertical failure-domain wave for context/state/memory/workspace failures, not a mechanism-map recap.
  - Confirmed all four required main lane outputs exist: trajectory, codebase/source-reconstruction, literature, and informal.
  - Confirmed two codebase support artifacts exist and were cited by the codebase lane.
  - Confirmed eval/benchmark fifth lane remains inactive; no blocker forced reactivation during lane execution.
  - Confirmed the anti-collapse rule (runtime allocator-memory vs coding-agent context/memory) is enforced across all four lanes.

- preflight_planned_read_order:
  - Wave brief, contradiction packet, output README, and dirty-worktree policy.
  - Decision document and cumulative synthesis.
  - Coverage register.
  - All four main-lane first-pass outputs.
  - Both codebase support artifacts.
  - Mechanism Map Wave 04 principal synthesis as upstream reconciliation anchor.
  - Wave 02 checklist adjudicator for boundary/overlap check.

- preflight_critical_sources_selected:
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/brief.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/contradiction_packet.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/README.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
  - tracking/collab/stage_02_synthesis/coverage_register/current_status.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_failure_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_source_reconstruction_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_papers_docs_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_issues_postmortems_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_context_state_failure_map.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_workspace_persistence_map.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md

- preflight_coverage_risks:
  - Four deferred support artifacts (trajectory support matrix, trajectory memory-state-drift cases, literature support cluster, informal support cluster) were not produced; lane outputs claim self-contained synthesis was sufficient.
  - BigAI trace layer `answered_questions.md` was listed as read by the trajectory lane but explicitly listed as not-yet-used by the codebase lane, creating a read-accounting discrepancy.
  - No lane ran a cross-run frequency matrix; all failure-incidence claims are qualitative.

- preflight_likely_blind_spots:
  - Wave 02 recovery/resume overlap with Wave 03 state/persistence: lanes acknowledge the boundary but do not produce an explicit reconciliation table.
  - db-wal-recovery and headless-terminal trajectories are referenced as carry-forward but not deeply re-read in the trajectory lane for Wave 03.
  - Post-compaction instruction loss is only supported by informal issue evidence and not corroborated at trajectory or codebase level.

- preflight_blockers: []

- coverage_used:
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/brief.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/contradiction_packet.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/README.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md
  - tracking/collab/stage_02_synthesis/coverage_register/current_status.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_failure_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_source_reconstruction_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_papers_docs_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_issues_postmortems_analyst.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_context_state_failure_map.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_workspace_persistence_map.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator.md

- coverage_not_yet_used:
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_context_workspace_failure_matrix.md (does not exist; deferred)
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_memory_state_drift_cases.md (does not exist; deferred)
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_support_context_memory_failure_cluster.md (does not exist; deferred)
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_support_context_workspace_failure_cluster.md (does not exist; deferred)
  - tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/eval_support_state_contract_map.md (fifth lane inactive)
  - Direct trajectory re-reads for db-wal-recovery and headless-terminal slices in Wave 03 failure context

- evidence_classes_touched:
  - trajectories (via trajectory lane output)
  - mirrored source code (via codebase lane output and support artifacts)
  - local harness code (via codebase lane output)
  - formal papers and docs (via literature lane output)
  - informal articles, issues, postmortems (via informal lane output)
  - wave governance/control surfaces
  - prior accepted synthesis (Mechanism Map Wave 04, Failure Taxonomy Waves 01-02)

- priority_sources_not_yet_read:
  - research/analysis/bigai_trace_layer/output/answered_questions.md (read/not-read discrepancy between lanes)
  - research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt (codebase lane did not read; trajectory lane did)
  - research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/schedule_store.py
  - research/sources/codebases/a-evolve/agent_evolve/engine/loop.py
  - Unread informal issues listed in informal lane priority queue

- support_artifact_gaps:
  - Four of seven reserved support artifacts from README.md were not produced.
  - Only codebase_support_context_state_failure_map.md and codebase_support_workspace_persistence_map.md exist.
  - Missing: trajectory_support_context_workspace_failure_matrix.md, trajectory_support_memory_state_drift_cases.md, literature_support_context_memory_failure_cluster.md, informal_support_context_workspace_failure_cluster.md, eval_support_state_contract_map.md.
  - Judgment: The four missing support artifacts (excluding the eval one, which is correctly inactive) are not structural blockers because lane outputs produced inline synthesis that covers the gap. However, they weaken reproducibility and future contradiction pressure. Mark as carry-forward debt.

- coverage_register_consistency:
  - The coverage register at status date 2026-04-10 still shows Wave 03 as `packet-prepared, not started`.
  - All four main-lane first-pass outputs now exist on disk, so the register is stale.
  - The register must be updated to reflect `in progress` with lane outputs present before principal synthesis.
  - No structural inconsistency between register carry-forward warnings and lane output claims.
  - The register accurately preserves BigAI behavioral-reconstruction status, A-Evolve source-only status, and runtime-memory anti-collapse across all wave entries.

## Supported findings

The following findings survive adversarial pressure and are carried forward as supported:

1. **Anti-collapse discipline is enforced.** All four lanes correctly separate context-window pressure, compaction/folding failure, stale/misleading memory, workspace/repo/branch/path drift, session persistence/resume-state drift, and runtime allocator-memory failures into distinct attribution buckets. No lane collapses these into a single "memory failure" family.
   - Confidence: high
   - Evidence: All four lane outputs explicitly maintain separate failure candidates/families and cite the brief's anti-collapse requirement. The trajectory lane (lines 174-178) separates five failure candidates. The codebase lane (Claims A through J) maps source-visible mechanisms to distinct failure pressures. The literature lane (FT-W03-LIT-01 through FT-W03-LIT-06) preserves formal evidence for bucket separation. The informal lane separates four finding clusters.

2. **Runtime allocator-memory is correctly separated.** All lanes converge on keeping `custom-memory-heap-crash` runtime SIGSEGV/allocator-lifecycle failures out of the coding-agent context/memory failure taxonomy.
   - Confidence: high
   - Evidence: Trajectory lane (lines 158-163), codebase lane Claim J, informal lane (no confusion with runtime memory), and support artifact attribution implications all enforce this boundary.

3. **BigAI is correctly bounded.** All four lanes keep BigAI mechanism claims at `behavioral reconstruction` status. No lane promotes BigAI beyond trajectory-behavioral evidence.
   - Confidence: high
   - Evidence: Trajectory lane (lines 166, 174, 177, 190), codebase lane (Claims I-J explicitly labeled `behavioral reconstruction`), literature lane (FT-W03-LIT-06, FT-W03-LIT-C03), informal lane (not applicable; informal lane does not make BigAI-specific mechanism claims).

4. **Compaction failure is a real failure surface.** Cross-lane evidence converges on compaction as a distinct failure family with at least two subfamilies: compaction-unavailable/hang and compaction-trigger-accounting-error.
   - Confidence: high for existence, medium for subfamily structure.
   - Evidence: Codebase lane (Claim A shows DeepAgents compaction offload warning when `file_path=None`; Claim D shows KIRA fallback to `current_screen[-1000:]`), informal lane (`ctx_compaction_failure_cluster` with 6 cited issues), literature lane (FT-W03-LIT-03 citing CAT and Context-Folding papers). Trajectory lane is weaker here; see unsupported findings below.

5. **Workspace/repo/branch/path drift is a real failure surface.** Cross-lane evidence supports workspace drift as strong in BigAI trajectories, with source-backed explanation in deepagents/KIRA/a-evolve showing why those families experience less drift.
   - Confidence: high for failure existence, medium for root-cause allocation.
   - Evidence: Trajectory lane (lines 122-153, cross-family comparison at lines 179-182), codebase lane (support artifacts showing source-visible workspace contracts), informal lane (`workspace_path_state_corruption_cluster` with 5 cited issues), literature lane (FT-W03-LIT-04).

6. **Mixed-cause attribution is preserved.** No lane claims single-cause failure attribution. The mixed model/harness/environment/benchmark-task-contract framing required by the brief and decision document is maintained.
   - Confidence: high
   - Evidence: Trajectory lane contradiction notes (lines 183-187), codebase lane mismatch analysis (lines 164-176), literature lane mechanism/failure support section (line 181), informal lane contradiction notes (contradiction_01 through contradiction_03).

## Unsupported or overclaimed findings

1. **Trajectory lane underclaims on compaction failure.** The trajectory lane lists `context_loss_or_compaction_failure` as a failure candidate (line 174) but admits this is `medium` confidence and `behavioral reconstruction` for BigAI, with no direct compaction-trigger event observed in any required trajectory. The informal and codebase lanes provide much stronger compaction evidence. This is not an overclaim—it is an underclaim that risks understating compaction failure prevalence in trajectory evidence.
   - Required repair: Trajectory lane should explicitly note that compaction failure was not directly observed in the required three task families (git-multibranch, break-filter, custom-memory-heap-crash) and that compaction pressure in the corpus comes primarily from informal and source lanes. This is honest; do not suppress it.

2. **Post-compaction instruction loss is single-lane evidence.** The informal lane promotes `post_compaction_instruction_loss_cluster` as warranting a dedicated subfamily (finding_id: `post_compaction_instruction_loss_cluster`). This finding is supported only by informal issue evidence (src_iss_d227a621da26, src_iss_b8d7092a954f) and one informal article (humanlayer_ace_fca.md). Neither the trajectory lane nor the codebase lane independently corroborates post-compaction rule loss.
   - Required repair: This finding should be labeled `single-lane, informal-only` with explicit note that trajectory and codebase corroboration is absent. It may be promoted to a candidate but should not be treated as a confirmed failure subfamily until at least one other lane provides independent evidence.

3. **Session persistence/resume-state drift boundary with Wave 02 is soft.** Three lanes acknowledge that Wave 02 recovery/resume fragility overlaps with Wave 03 state/persistence failures. However, none produces an explicit reconciliation of which specific findings belong to Wave 02 and which to Wave 03.
   - Required repair: Principal synthesis must produce a concrete boundary table showing which recovery/resume failures are Wave 02 carry-forward versus new Wave 03 state/persistence attribution. Without this, there is a risk of double-counting the same evidence across two waves.

4. **A-Evolve behavioral prevalence is overclaimed by negation.** The codebase lane correctly notes A-Evolve has `high` confidence for mechanism existence but `low` for behavioral prevalence (line 174). However, the support artifacts include A-Evolve in the system-map tables alongside fully trajectory-backed systems without a visible caveat column for behavioral prevalence.
   - Required repair: Support artifacts should flag which system rows have trajectory-backed behavioral evidence versus source-only mechanism evidence. This matters for failure-incidence claims downstream.

5. **Codebase lane Claim C confidence may be too generous.** DeepAgents compact/resume is supported at `medium` confidence, citing an integration test (`test_compact_resume.py`). Test-level evidence is weaker than production-behavior evidence for failure-attribution claim strength. The weakener note is present but the `medium` rating could be interpreted as stronger than warranted for a failure-taxonomy pass that is supposed to be behavior-anchored.
   - Required repair: Note in principal synthesis that DeepAgents compaction/resume capability is better documented as source-test-backed infrastructure than as direct behavioral failure evidence.

## Missing evidence classes

1. **No trajectory-level compaction failure observed.** No required trajectory in git-multibranch, break-filter-js-from-html, or custom-memory-heap-crash shows a visible compaction event, compaction trigger, or compaction failure. The trajectory lane's `context_loss_or_compaction_failure` candidate is extrapolated from BigAI behavioral rework churn, not direct compaction failure observation.
   - Impact: Compaction failure remains sourced from codebase implementations and informal issue reports. This is acceptable for failure taxonomy at candidate level but should be flagged as a trajectory evidence gap.

2. **No eval/benchmark evidence for state contracts.** The eval fifth lane is inactive. No lane independently examined benchmark grader or task-contract expectations about workspace state, session persistence, or context/memory invariants.
   - Impact: If benchmark-task contracts implicitly assume stable workspace state or context persistence, then benchmark-contract-gap failure attribution is invisible in this wave. This is acceptable per the brief's default eval-inactive policy, but the gap should be preserved as a carry-forward.

3. **No direct trajectory-level session persistence failure observed.** The trajectory lane's `session_persistence_and_state_handoff_failure` candidate (line 177) cites BigAI missing-file and cwd-mismatch signals as behavioral reconstruction. No required trajectory shows a direct session-restore, checkpoint-load, or history-resume failure event.
   - Impact: Session/persistence failure is supported by codebase source (deepagents StateBackend, KIRA SessionManager) and informal issue reports, but not by direct trajectory observation in the required slices.

## Reconciliation failures

1. **bigai_trace_layer read-accounting discrepancy.** The trajectory lane lists `research/analysis/bigai_trace_layer/output/answered_questions.md` as `coverage_used` (line 58). The codebase lane lists it as `coverage_not_yet_used` (line 75). This is a minor bookkeeping inconsistency, not a substantive contradiction—but it should be resolved before principal synthesis to maintain tracing integrity.
   - Required repair: Clarify in principal synthesis which lanes actually read vs. cited this artifact.

2. **Formal literature vs trajectory evidence gap on compaction.** Literature lane FT-W03-LIT-03 claims `medium` confidence that compaction failures should be attributed as context-state operator failures based on CAT and Context-Folding papers. The trajectory lane provides no direct compaction observation to corroborate this formal claim in the required task families.
   - This is not a contradiction; it is an honest gap. The formal evidence provides conceptual framing while direct behavioral prevalence in required trajectories is absent. Principal synthesis should preserve both signals without forcing premature reconciliation.

3. **Informal contradiction_02 (compaction as both mitigation and failure source) is not reconciled against trajectory evidence.** The informal lane's `contradiction_02` is well-supported by issue evidence, but neither the trajectory lane nor the codebase lane produced a behavioral instance where the same compaction operation both mitigated one problem and created another within a single run.
   - Required repair: This bidirectional role of compaction should remain as a carry-forward open question rather than a confirmed failure pattern until trajectory or codebase evidence demonstrates it in action.

4. **Wave 02 recovery/resume overlap.** All lanes acknowledge the overlap but none resolves it. The cumulative synthesis (line 54) explicitly flags this: "Wave 02 recovery/resume state fragility may overlap with Wave 03 state/persistence failures and must be reconciled rather than duplicated." The lanes do not produce the required reconciliation.
   - Required repair: Principal synthesis must produce an explicit boundary. Proposed principle: Wave 02 owns recovery/resume failures where the triggering event is a verification or completion action. Wave 03 owns state/persistence failures where the triggering event is context/state corruption, compaction failure, or workspace drift independent of verification. Mixed-cause cases should be cross-referenced, not duplicated.

## Coverage blind spots

1. **db-wal-recovery and headless-terminal are referenced but not re-read for Wave 03.** The trajectory lane lists these case studies as `support_artifacts_used` but does not include them in `preflight_critical_sources_selected` for direct Wave 03 trajectory re-read. They are carry-forward from earlier waves, not Wave 03 first-pass reads.
   - Impact: Low; these are ancillary to the primary git-multibranch/break-filter/custom-memory-heap-crash target set. But any Wave 03 claims that cite them should note they are carry-forward, not fresh Wave 03 analysis.

2. **Informal lane coverage is broad but shallow.** The informal lane read 19 issue artifacts and 6 informal/postmortem articles. This is good breadth. However, several issues in the priority-sources-not-yet-read queue (src_iss_949d7288362a, src_iss_6ba217fff208, src_iss_6e82661ad778, src_iss_819b6ec7ad57, src_iss_e88081f909bc) remain unread. The impact is bounded because the read set already provides convergent clusters.
   - Impact: Low for this wave; medium if later waves need fuller informal saturation.

3. **No cross-run frequency matrix.** All four lanes note the absence of quantitative failure-incidence data. The trajectory support matrix was explicitly deferred. This means all claims about failure prevalence are qualitative.
   - Impact: Medium. Qualitative claims are acceptable at `candidate` and `emerging` maturity levels, but quantitative prevalence should be a checklist item before any family reaches `decision_ready`.

4. **Codebase lane did not read BigAI second git-multibranch trajectory (baabd142).** The trajectory lane read both BigAI git-multibranch trajectories. The codebase lane read only `62d2bdf3`. The `baabd142` run shows repo-ownership drift that is relevant to workspace-persistence attribution.
   - Impact: Low for this wave; the trajectory lane covers the behavioral evidence. But if contradictions arise between lanes about BigAI workspace governance, this gap would need repair.

## Required repairs before acceptance

1. **Wave 02 / Wave 03 recovery-resume boundary.** Principal synthesis must produce an explicit boundary table or principle distinguishing Wave 02 recovery/resume failures from Wave 03 state/persistence failures. This is the single most important structural repair.

2. **Post-compaction instruction loss single-lane label.** The post-compaction instruction-loss finding must be labeled `single-lane, informal-only` until trajectory or codebase corroboration exists.

3. **bigai_trace_layer read-accounting.** Resolve the discrepancy between trajectory and codebase lanes on whether `answered_questions.md` was used.

4. **A-Evolve prevalence caveat in support artifacts.** Support artifact tables should flag entries without trajectory-backed behavioral prevalence.

5. **Coverage register update.** The coverage register must advance Wave 03 from `packet-prepared, not started` to `in progress` with lane outputs present and this contradiction review filed.

## Optional pressure tests

1. **Direct trajectory compaction replay.** A follow-up pass could scan all captured trajectories for visible compaction events (summarization triggers, context-window limit messages, history offload) to strengthen or weaken the compaction failure candidate with behavioral evidence.

2. **Cross-wave recovery-resume evidence audit.** A dedicated support artifact mapping all recovery/resume evidence between Waves 02 and 03 would sharpen the boundary required in repair #1.

3. **Eval fifth lane check.** A bounded eval-lane pass could check whether any benchmark grader or task contract explicitly assumes stable context/state across runs, strengthening or removing the benchmark-contract blind spot.

4. **Post-compaction rule-loss trajectory search.** A targeted search across all trajectory texts for keywords suggesting post-compaction rule/instruction loss would corroborate or weaken the informal-only finding.

## Gate review recommendations

1. **Do not block.** The four lane outputs collectively provide well-structured, evidence-cited, anti-collapse-aware failure attribution for the required domain. The gaps and unsupported claims are carry-forward warnings, not structural defects.

2. **Enforce required repairs before checklist.** The five required repairs above (especially the Wave 02/03 boundary) must land before checklist adjudication can accept this wave.

3. **Preserve eval-inactive status.** No evidence encountered in this review forces eval fifth-lane reactivation. If principal synthesis encounters benchmark-state-contract questions, that decision should be explicit rather than silent.

4. **Keep all families at `candidate` or `emerging`.** No Wave 03 family should be promoted to `decision_ready` based on first-pass lane evidence alone.

5. **Carry forward all four support artifact gaps.** The deferred support artifacts are not blockers, but they should be registered as carry-forward debt in the coverage register.

- confidence: medium-high overall. Lanes are structurally sound with honest uncertainty. Weakness is the absence of direct trajectory compaction failure evidence and the unresolved Wave 02/03 boundary.
