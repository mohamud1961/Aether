# Failure Taxonomy Cumulative Synthesis

Status: canonical cumulative state surface for `failure_taxonomy` as of 2026-04-11

Purpose

- This file is the canonical carry-forward control surface for `failure_taxonomy`.
- Update this file after each governed wave instead of treating long prose or memory as the inheritance surface.

Current artifact judgment

- `failure_taxonomy` is now the active second Deep Synthesis core artifact.
- Wave 01 `execution_control_and_terminal_failures` is accepted with carry-forward warnings.
- Wave 02 `verification_completion_and_recovery_failures` is accepted with carry-forward warnings.
- Wave 03 `context_state_memory_workspace_failures` is accepted with carry-forward warnings.
- Failure attribution must inherit the accepted `mechanism_map` spine rather than improvising new mechanism families silently.

Accepted claims

- Accepted from Wave 01 with warnings:
  - execution-control and terminal failures are real recurring failure families, but not decision-ready
  - failure attribution should default to `mixed` unless direct evidence isolates a single cause
  - terminal-grounding and repo-state drift is a real failure family
  - cancellation and process-lifecycle breakdown is a real failure family
  - false success from weak or misaligned acceptance is real but needs subfamily structure
  - timeout and stall pressure is real as a pressure cluster, but not yet direct per-run taxonomy
- Accepted from Wave 02 with warnings:
  - verifier or completion success signals can diverge from final benchmark acceptance
  - inline checks, verifier artifacts, replay/state graders, LLM judges, cleanup checks, and final reward are distinct attribution layers
  - recovery/resume failure includes state/index drift, non-terminal recovery limbo, and environment-state invalidation pressure
  - benchmark-contract blindness is real pressure but remains bounded without deeper grader implementation reads
  - cleanup-confirmed invalid completion remains a subflag under false-completion/final-acceptance mismatch rather than a separate high-confidence family
- Accepted from Wave 03 with warnings:
  - workspace/repo/branch/path drift is a real recurring failure family
  - stale or misleading state is a real failure surface distinct from raw context-window pressure
  - compaction/summarization should be modeled as an explicit state operator failure surface, but current prevalence remains bounded
  - session persistence and state handoff failures are real, but direct required-trajectory support is still thinner than source and informal support
  - runtime allocator-memory failures must remain distinct from coding-agent context/state failures

Contradiction register

- Wave 01 carry-forward tensions:
  - BigAI supplies rich behavioral evidence but remains no-source
  - timeout-heavy BigAI claims are summary-routed rather than direct per-run attribution
  - false-success pressure crosses harness completion protocol, verifier omission, and benchmark blindness
  - A-Evolve is source-strong but trajectory-thin in this wave
  - two codebase support maps are missing and should be repaired or explicitly retired before artifact closure
- Wave 02 opening tensions:
  - verifier omission, false completion, replay mismatch, cleanup-confirmed invalid completion, and recovery failure can be confused if lanes do not preserve layer boundaries
  - eval/benchmark evidence is load-bearing for Wave 02, so benchmark-contract claims should cite direct eval, verifier, grader, replay, or task-success paths where available
  - BigAI must remain behavioral reconstruction even when its runs are useful for false-completion or recovery-failure pressure
- Wave 02 principal tensions:
  - the Claude contradiction output references a Gemini gate that does not exist on disk for this wave, so only GPT and Claude contradiction outputs are carried forward
  - BigAI extraction verifier omission remains provisional because the visible omission may be a trace-format artifact
  - KIRA `db-wal-recovery` cwd invalidation remains single-run and mixed-cause
  - A-Evolve Wave 02 behavior remains source-backed but not trajectory-backed
- Wave 03 opening tensions:
  - context loss, stale memory, workspace drift, branch/path corruption, session persistence failure, and runtime memory pressure must not be collapsed into one family
  - Mechanism Map Wave 04 workspace and memory findings include source-backed capacity that may exceed trajectory-visible exercise
  - Wave 02 recovery/resume fragility may overlap with Wave 03 state/persistence failures and must be reconciled rather than duplicated
- Wave 03 principal tensions:
  - direct required trajectories show workspace/path drift more strongly than they show explicit compaction failure events
  - post-compaction instruction loss is currently single-lane informal-only and should not be overpromoted
  - A-Evolve remains source-strong but behavior-thin in this wave
  - support-artifact debt remains open for trajectory frequency and broader clustering
  - benchmark state-contract blindness remains bounded because eval stayed inactive
- Wave 04 opening tensions:
  - tool gateway mismatch, permission-policy/runtime mismatch, path/cwd failure, process lifecycle failure, delegation mismatch, planner-verifier coupling, and timeout-heavy long-horizon degradation must not be collapsed into one vague coordination family
  - BigAI timeout-heavy long-horizon claims remain partly summary-routed unless this wave reopens direct trajectory slices
  - permission safety and role-separated orchestration are still stronger at mechanism level than at direct failure-taxonomy prevalence level

Coverage frontier

- Wave 04 `tools_environment_coordination_and_long_horizon_failures` now needs first-pass lane outputs, contradiction review, principal synthesis, and checklist adjudication.
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` now exists; stale first-pass references to it as missing should be ignored.
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/brief.md` is the active next-wave packet.
- Organizer routing remains weaker than direct path accounting while `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` stays empty.
- Direct timeout-heavy BigAI trajectories remain a priority gap.
- Direct benchmark/eval contract reads remain a priority gap for stronger false-success attribution.
- Direct trajectory compaction-failure search remains a priority gap for stronger Wave 03 compaction attribution.
- Failure Taxonomy Wave 01 missing codebase support maps remain open unless later produced or explicitly retired:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_execution_failure_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_interrupt_cancellation_map.md`

Open questions

- Which execution-control failures are best explained as harness failures versus benchmark-blindness or environment failures?
- How much of false success is caused by verifier omission versus task-specific benchmark contract gaps?
- Which timeout-heavy failures are genuinely orchestration failures versus substrate or environment failures?
- Which false-success subfamily is dominant: verifier omission, benchmark blindness, or completion-policy weakness?
- Which cancellation failures are primarily harness implementation versus scenario/test design?
- Which completion failures are verifier omission versus external-grader mismatch versus replay/task-contract mismatch?
- Which recovery/resume failures are caused by missing durable state, cleanup policy, environment state drift, or weak recovery strategy?
- Is BigAI extraction verifier omission real, or a trace-format artifact?
- Does KIRA `db-wal-recovery` cwd invalidation reproduce beyond the single required run?
- Are BigAI and deepagents `cancel_above_max_concurrent` failures caused by the same semantic gap or different runtime/harness policies?
- Which failures are truly context/memory failures versus workspace/repo-state failures or environment failures?
- Which state/persistence failures are best treated as recovery/resume failures from Wave 02 versus first-class Wave 03 state/workspace failures?

Saturation status

- No current failure family should be treated as `decision_ready`.
- Wave 01 accepted promotions:
  - terminal-grounding and repo-state drift: `emerging`
  - cancellation and process-lifecycle breakdown: `emerging`
  - false success from weak or misaligned acceptance: `emerging`
  - timeout and stall pressure: `exploratory`
- Wave 02 principal status:
  - verifier or completion success signal diverges from final acceptance: `emerging`
  - replay/grader/final-acceptance mismatch: `emerging`
  - recovery/resume state and index fragility: `emerging`
  - completion pressure without sufficient quality/similarity gate: `candidate`
  - cleanup-confirmed invalid completion: `subflag`, not a separate family yet
  - BigAI extraction verifier omission: `provisional_observation`
- Wave 03 accepted status:
  - context compaction or state-operator failure: `candidate`
  - stale or misleading memory/state: `candidate`
  - workspace/repo/branch/path drift: `emerging`
  - session persistence and state handoff failure: `candidate`
  - runtime allocator-memory pressure: `boundary_rule`, must remain distinct from agent-context memory
- Wave 04 opening status:
  - tool gateway or substrate mismatch: `candidate`
  - cwd/workdir/path contract failure: `candidate`
  - permission-policy/runtime mismatch: `candidate`
  - process lifecycle and cancellation boundary failure: `candidate`
  - delegation or role-handoff breakdown: `candidate`
  - timeout-heavy long-horizon coordination degradation: `candidate`
