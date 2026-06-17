# Failure Taxonomy Wave 03 Principal Synthesis

Status: principal-complete; checklist-ready

Overall verdict: `pass_with_warnings`

Scope

- overall Deep Synthesis wave: Wave 09
- artifact: `failure_taxonomy`
- artifact-local wave: Wave 03 `context_state_memory_workspace_failures`
- evidence shape: four main lanes present (`trajectory`, `codebase`, `literature`, `informal`) plus GPT, Claude, and Gemini contradiction gates
- eval lane: inactive by packet default and not reactivated in this pass

## What This Wave Resolved

Wave 03 resolves that context, state, memory, workspace, branch, and session failures are real failure-taxonomy surfaces and should not be collapsed into one vague memory bucket.

The strongest supported family is:

- `workspace_repo_branch_path_drift`: `emerging`, high confidence
  - Core observation: required `git-multibranch` and `break-filter-js-from-html` runs repeatedly show repo ownership fixes, branch-state corrective churn, cwd/path mismatch, and wrong-path assumptions, especially in BigAI runs and in KIRA's explicit `/tests/filter.py` to `/app/filter.py` repair.
  - Evidence:
    - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
    - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
    - `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`
    - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
    - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_failure_analyst.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_workspace_persistence_map.md`

The second supported family is:

- `stale_or_misleading_memory_state`: `candidate`, medium-high confidence
  - Core observation: direct trajectories, source-backed memory/session systems, and informal issue clusters all show stale assumptions, missing expected state, degraded retrieval, or resume/index drift that mislead agents without necessarily causing a hard crash.
  - Evidence:
    - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{memory_runtime.py,memory_store.py,session_manager.py}`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/{state.py,store.py}`
    - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
    - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_issues_postmortems_analyst.md`

The third supported but still bounded family is:

- `context_compaction_or_state_operator_failure`: `candidate`, medium confidence
  - Core observation: source and formal evidence show compaction/summarization as explicit state operators; informal issues show compaction hang, trigger/accounting failure, and post-compaction degradation; direct required trajectories do not yet show a clean compaction-failure event in the same way they show path drift.
  - Evidence:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`
    - `research/sources/codebases/deepagents/libs/cli/tests/integration_tests/test_compact_resume.py`
    - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
    - `research/sources/papers/papers_text/2510.11967.txt`
    - `research/sources/issues/src_iss_15bd3d2d6a1d/artifact.txt`
    - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
    - `research/sources/issues/src_iss_b69884cd17d8/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_papers_docs_analyst.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_issues_postmortems_analyst.md`
  - Required caution: this family is real, but prevalence and subfamily confidence remain bounded until a direct trajectory compaction-failure search is done.

The fourth supported but thinner family is:

- `session_persistence_and_state_handoff_failure`: `candidate`, medium confidence
  - Core observation: source systems expose explicit state/session infrastructure and informal evidence shows stale indexes, parser failures, rewind nullification, and resume drift, but the required Wave 03 trajectory set contains only limited direct session-failure evidence.
  - Evidence:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
    - `research/sources/issues/src_iss_222a58240294/artifact.txt`
    - `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`
    - `research/sources/issues/src_iss_a1a5a26e92ab/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_context_state_failure_map.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_issues_postmortems_analyst.md`

Boundary rule retained:

- `runtime_allocator_memory_pressure_distinct_class`: boundary rule, high confidence
  - `custom-memory-heap-crash` remains a runtime allocator/lifecycle memory surface, not a coding-agent context-memory failure family for Wave 03.

## Principal Reconciliation

Wave 02 versus Wave 03 boundary:

- Wave 02 owns failures where the triggering event is verification, completion, replay, grader, cleanup, or recovery-control handling.
- Wave 03 owns failures where the triggering event is stale context, compaction/summarization, workspace/path/branch drift, or state/session corruption independent of verifier/completion control.
- Mixed cases should be cross-referenced, not duplicated. Example: a resume failure caused by stale session index belongs primarily to Wave 03; a recovery loop that fails because the verifier/recovery controller cannot correctly resume belongs primarily to Wave 02.

Post-compaction rule loss stays bounded:

- `post_compaction_instruction_loss` is not promoted as a standalone broad family yet.
- Principal decision: keep it as a `single-lane, informal-only` subfamily under `context_compaction_or_state_operator_failure`.
- Promotion criterion: direct trajectory or source-backed corroboration showing the rule/instruction loss mechanism rather than only issue testimony.

BigAI language stays strict:

- BigAI remains useful for behavioral pressure on drift, stale assumptions, and state handoff instability.
- BigAI does not support source-backed mechanism attribution.
- Every BigAI mechanism claim carried from Wave 03 remains tagged `behavioral reconstruction`.

A-Evolve stays source-strong, behavior-thin:

- A-Evolve workspace/versioning structure is useful for mechanism boundaries.
- Wave 03 does not have enough direct A-Evolve task-family behavior to use it for prevalence claims.

Read-accounting discrepancy resolved:

- `research/analysis/bigai_trace_layer/output/answered_questions.md` should be treated as directly used by the trajectory lane and not as a codebase-lane evidence anchor for promoted claims.
- The incorrect `research/sources/analysis/...` path has been normalized.

Deferred support artifacts ratified:

- The missing support artifacts
  - `trajectory_support_context_workspace_failure_matrix.md`
  - `trajectory_support_memory_state_drift_cases.md`
  - `literature_support_context_memory_failure_cluster.md`
  - `informal_support_context_workspace_failure_cluster.md`
  are accepted as carry-forward debt, not blockers for this principal pass.
- Rationale: no promoted claim in this synthesis depends uniquely on those files, but their absence limits prevalence precision and breadth accounting.

## Gate Reconciliation

Current on-disk gate state:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/contradiction_analyst.md`: `pass_with_warnings`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/contradiction_analyst__claude.md`: `pass_with_warnings`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/contradiction_analyst__gemini.md`: `pass_with_warnings`

All three gate reviews support proceeding. The carry-forward limits that matter are:

- no direct required-trajectory compaction failure event yet
- no eval-lane evidence for benchmark state contracts
- no direct trajectory-level session persistence failure at strong prevalence depth
- cross-system prevalence statements must stay sampled and qualitative

## What Still Requires Another Wave

No Wave 03 family is `decision_ready`.

Carry forward:

- direct trajectory compaction-failure search is still missing
- Wave 02 and Wave 03 mixed recovery/persistence cases need later cross-wave cleanup if they begin to blur again
- A-Evolve remains source-backed and behavior-thin in this wave
- benchmark grader/workspace contract internals remain unread because eval stayed inactive
- BigAI source-level attribution remains unavailable
- support-artifact debt remains open for frequency and breadth accounting

Priority follow-ups:

- run a bounded trajectory inventory for visible compaction/state-loss events
- add a cross-wave support memo for Wave 02 recovery versus Wave 03 persistence boundaries if later waves keep reusing both
- reactivate eval only if benchmark path/state contracts become necessary to explain a promoted failure family

## Local Harness Implications

The local harness should treat state as multiple distinct carriers, not one generic memory blob.

Needed surfaces:

- explicit workspace/repo/branch/path state logging
- explicit state-store or checkpoint boundaries
- explicit compaction/summarization events and reinjection logs
- separation between runtime program-memory faults and agent context/state faults
- recovery logs that distinguish controller failure from stale state input

Current local harness limit:

- `blocks/context/*`, `runner/*`, and `evals/*` remain mostly interface or scaffold level for these failure families, so Wave 03 should inform implementation rather than claim the local harness already enforces the needed controls.

## Coverage Not Yet Used

- full benchmark grader/state-contract internals under `research/sources/benchmarks/**`
- broader unread paper/doc queue beyond the Wave 03 formal anchors
- extra BigAI sidecar artifacts outside the required `*-traj.txt` slices
- missing Wave 03 support artifact set for frequency clustering

## Support Track Updates

Support artifacts present:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_context_state_failure_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_workspace_persistence_map.md`

Support artifacts deferred with bounded impact:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_context_workspace_failure_matrix.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_memory_state_drift_cases.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_support_context_memory_failure_cluster.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_support_context_workspace_failure_cluster.md`

Control surfaces updated by this principal pass:

- update `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
- update `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- update `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
- update `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`

Next governed step:

- run Wave 03 checklist adjudication against this principal synthesis, all four lane outputs, and all three contradiction outputs
