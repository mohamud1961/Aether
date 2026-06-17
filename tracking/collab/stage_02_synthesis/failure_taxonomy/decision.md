# Failure Taxonomy Decision

Status: active Deep Synthesis second core artifact; Waves 01-03 accepted with warnings; Wave 04 packet-prepared

Opened: 2026-04-02

Artifact

- `failure_taxonomy`

Goal

- Build the second Deep Synthesis core artifact from the accepted mechanism spine so failure attribution starts from explicit mechanism inheritance rather than ad hoc failure anecdotes.

Current completed state

- `mechanism_map` is accepted through Wave 06 with carry-forward warnings.
- `failure_taxonomy` Wave 01 `execution_control_and_terminal_failures` is accepted with carry-forward warnings.
- `failure_taxonomy` Wave 02 `verification_completion_and_recovery_failures` is accepted with carry-forward warnings.
- `failure_taxonomy` Wave 03 `context_state_memory_workspace_failures` is accepted with carry-forward warnings.

Collaboration mode

- default serious-wave roster:
  - trajectory/failure analyst
  - codebase/source reconstruction analyst
  - literature/papers/docs analyst
  - informal/issues/postmortems analyst
- optional fifth:
  - eval/benchmark analyst
- bounded support sub-agents are standard when the wave is large
- Gemini and Claude are gate-time reviewers, not default parallel main lanes

Current judgment

- `failure_taxonomy` is now the active second core artifact.
- Failure work should inherit mechanism definitions from accepted `mechanism_map` waves rather than reinventing them.
- Wave 01 is accepted for governed carry-forward, but it does not complete `failure_taxonomy`.
- Wave 02 is accepted for governed carry-forward, but it does not complete `failure_taxonomy`.
- The Wave 02 eval/benchmark fifth lane was active because verifier, grader, replay, recovery, and benchmark-contract logic are central to the attribution question.
- Wave 03 is accepted for governed carry-forward with workspace/path drift as the strongest direct family and compaction/state-handoff claims kept bounded.
- The Wave 03 eval/benchmark fifth lane remained inactive and did not block acceptance.
- Wave 04 should now open on `tools_environment_coordination_and_long_horizon_failures`.
- The Wave 04 eval/benchmark fifth lane is inactive by default and should only be reactivated if benchmark time budgets, grader/tool contracts, replay requirements, or benchmark workspace assumptions become load-bearing.
- The artifact is not complete and no failure family is `decision_ready`.

Current carry-forward warnings

- Do not flatten model, harness, environment, and benchmark-blindness failure into one cause when evidence is mixed.
- BigAI remains `behavioral reconstruction` for mechanism linkage.
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` now exists; stale first-pass references to it as missing should not be treated as current state.
- Organizer routing is still weaker than direct path accounting because `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty.
- Timeout-heavy failure claims are still summary-routed and should not be promoted beyond `exploratory` without direct trajectory reads.
- Wave 01 benchmark-blindness claims remain bounded because the eval/benchmark fifth lane was not activated.
- Failure Taxonomy Wave 01 missing codebase support maps should be produced or explicitly retired before artifact closure:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_execution_failure_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/codebase_support_interrupt_cancellation_map.md`
- Wave 02 BigAI evidence remains `behavioral reconstruction`.
- Wave 02 benchmark-contract blindness remains bounded because several benchmark captures are contract/readme-level rather than grader implementation reads.
- Wave 02 cleanup-confirmed invalid completion is a subflag under false-completion/final-acceptance mismatch, not a separate promoted family.
- Wave 02 BigAI extraction verifier omission remains provisional because it may be a trace-format artifact.
- Wave 02 Gemini contradiction output was absent on disk; only GPT and Claude contradiction outputs were used for checklist stage.
- Wave 03 must not collapse context loss, stale memory, workspace drift, branch/path corruption, session persistence failure, and runtime memory pressure into one generic memory failure bucket.
- Mechanism Map Wave 04 A-Evolve workspace findings are source-backed, not trajectory-backed.
- Wave 03 post-compaction instruction loss remains `single-lane, informal-only`.
- Wave 03 support artifact debt remains open for prevalence and clustering:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_context_workspace_failure_matrix.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_support_memory_state_drift_cases.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_support_context_memory_failure_cluster.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_support_context_workspace_failure_cluster.md`
- Wave 04 must not collapse tool substrate failures, permission-policy/runtime mismatch, path/cwd failure, process lifecycle failure, delegation mismatch, and long-horizon timeout pressure into one generic coordination failure.
- Mechanism Map Wave 05 permission safety remains under-evidenced behaviorally.
- Mechanism Map Wave 06 role-separated orchestration remains source-strong and BigAI-behavior-rich, not universally trajectory-proven.

Next governed step

- run Failure Taxonomy Wave 04 `tools_environment_coordination_and_long_horizon_failures`
- use four main lanes by default: trajectory/failure, codebase/source reconstruction, literature/papers/docs, and informal/issues/postmortems
- reactivate eval only if benchmark time budgets, grader/tool contracts, replay requirements, or benchmark workspace assumptions become load-bearing during preflight
- keep Wave 01 benchmark-blindness pressure, timeout-heavy long-tail pressure, missing Wave 01 codebase support maps, and Wave 03 support-artifact debt in the support-track queue

Next artifact after completion

- `eval_implications`
