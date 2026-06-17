# Mechanism Map Decision

Status: active Deep Synthesis core artifact; Wave 01 through Wave 06 complete at the wave level, with carry-forward warnings on Waves 02, 03, 04, 05, and 06

Opened: 2026-04-02

Updated: 2026-04-10

Artifact

- `mechanism_map`

Current completed state

- Wave 01 `exploratory_anchor`
  - complete
  - preserved as legacy anchor only
- Wave 02 `execution_control_and_terminal_grounding`
  - complete at wave level
  - accepted with carry-forward warnings
- Wave 03 `verification_completion_and_recovery`
  - complete at wave level
  - accepted with carry-forward warnings
- Wave 04 `context_state_memory_workspace`
  - complete at wave level
  - accepted with carry-forward warnings
- Wave 05 `tools_environment_permissions`
  - complete at wave level
  - accepted with carry-forward warnings
- Wave 06 `planning_orchestration_and_interactions`
  - complete at wave level
  - accepted with carry-forward warnings

Current judgment

- `mechanism_map` remains the active first core artifact.
- Wave 02 established a real mechanism domain and should now be treated as accepted wave history, not as in-flight repair work.
- Wave 03 established a real verification/completion/recovery domain and should now be treated as accepted wave history with carry-forward warnings.
- Wave 04 established a real context/state/memory/workspace domain and should now be treated as accepted wave history with carry-forward warnings.
- Wave 05 established a real tools/environment/permissions domain and should now be treated as accepted wave history with carry-forward warnings.
- Wave 06 established a real planning/orchestration/interactions domain and should now be treated as accepted wave history with carry-forward warnings.
- `mechanism_map` is not artifact-complete.
- No current mechanism family is `decision_ready`.

Current carry-forward warnings

- BigAI remains `behavioral reconstruction`
- repo-state-safe cleanup remains less saturated than terminal control/cancellation
- archive-only `src_cod_*` pressure remains exploratory
- internal-verifier versus external-grader divergence is established but not fully causally explained
- restart/resumability remains under-evidenced behaviorally
- A-Evolve Wave 04 workspace findings are source-backed, not trajectory-backed
- richer source-visible memory capacity in DeepAgents and KIRA exceeds what the required Wave 04 trajectories visibly exercise
- robust permission safety remains under-evidenced behaviorally
- environment discovery remains exploratory
- A-Evolve Wave 05 findings are source-backed, not trajectory-backed
- `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md` is still missing
- explicit role-separated orchestration is strongest in BigAI behavioral evidence and should not yet be promoted as cross-family universal
- deepagents and a-evolve source-visible delegation capacity exceeds required-task trajectory exercise
- verifier optionality in BigAI remains causally unresolved

Next governed step

- open Failure Taxonomy Wave 01 `execution_control_and_terminal_failures`
- keep organizer repair, BigAI verifier-optionality pressure, long-tail trajectory pressure, HITL/delegation follow-up, and the missing `headless_terminal.md` case-study path in the support-track queue

Collaboration mode

- default serious-wave roster:
  - trajectory/failure
  - codebase/source reconstruction
  - literature/papers/docs
  - informal/issues/postmortems
- optional fifth:
  - eval/benchmark
- bounded support sub-agents are standard when the wave is large
- Gemini and Claude are gate-time reviewers, not default parallel main lanes
