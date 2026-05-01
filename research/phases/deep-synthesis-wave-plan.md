# Deep Synthesis Wave Plan

Date: 2026-04-07

Artifact

- `deep_synthesis_wave_plan`

Current judgment

- The earlier explicit 24-wave model was honest but too heavy.
- The upgraded Deep Synthesis model should now run as:
  - `14` core waves
  - `7` continuous support tracks
  - `4` main agents for serious `mechanism_map` and `failure_taxonomy` waves
  - optional `eval/benchmark` fifth main agent when the active wave is verifier, grader, replay, or benchmark heavy
  - bounded support sub-agents as standard lane infrastructure
- Coverage depth should no longer depend on wave prose alone.
- Speed should no longer depend only on adding more parallel main agents.

What changed after Wave 02 review

- Wave 02 proved that vertical mechanism waves work.
- Wave 02 also showed that:
  - source-depth coverage needs dedicated reusable artifacts, not just good wave synthesis
  - trajectory depth needs explicit case-study guarantees, not rhetorical coverage
  - papers and informal material must stay separated enough to avoid flattening evidence classes
  - `execution control` and `verification/completion/recovery` are separate enough to deserve different waves
  - support sub-agents are useful when kept bounded and explicitly cited
- The stage model is therefore upgraded from the older 24-wave layout to a compressed but deeper-support 14-wave layout.

Completed state at plan-upgrade time

- `mechanism_map` Wave 01 `exploratory_anchor` is complete and preserved as a legacy anchor wave.
- `mechanism_map` Wave 02 `execution_control_and_terminal_grounding` is accepted as:
  - `pass_with_warnings`
  - `wave accepted with carry-forward warnings`
- Formal paper access has materially improved:
  - `research/sources/papers/papers_text/review_summary.md` reports `200` readable papers
  - `194` are `clean`
  - `6` are `usable_with_caveats`
  - `0` are currently `ocr_needed`
  - `0` are currently `failed`
- This means paper access is no longer the main stage bottleneck.
- Remaining bottlenecks are excavation depth, route maps, and dossier reuse.

## Continuous support tracks

These are load-bearing support tracks, not decorative side folders.

1. `coverage_access`
   - role:
     - keeps the evidence corpus reachable and honestly routed
   - operating mode:
     - continuous support track, not 5 heavy serial core waves
   - gates:
     - `Gate A baseline_access_ready`
     - `Gate B final_coverage_closure`

2. `coverage_register`
   - role:
     - one explicit control surface for what is actually deeply covered versus still thin

3. `source_system_dossiers`
   - role:
     - dedicated architectural-depth dossiers for major systems

4. `trajectory_case_studies`
   - role:
     - explicit per-run and cross-run case studies with source linkage where visible

5. `literature_dossiers`
   - role:
     - anchor dossiers and theme dossiers for formal papers and docs

6. `informal_cluster_dossiers`
   - role:
     - structured issue, postmortem, and operator cluster coverage

7. `eval_benchmark_dossiers`
   - role:
     - benchmark contracts, verifier logic, grader logic, replay logic, and local eval hooks

Support-track rule

- A strong wave output is not enough on its own.
- Every serious wave must say:
  - which support tracks it depends on
  - which support tracks it updated
  - which unresolved support-track gaps still limit confidence

## Dedicated dossier set

Required first set:

- `KIRA`
- `deepagents`
- `a-evolve`
- `claw-code`
- `BigAI` as a behavioral dossier, not a fake source dossier

Second-tier dossiers when they materially shape a wave:

- `autoagent`
- grouped `src_cod_*` families

Excluded from the first set:

- `mempalace`
  - removed from Deep Synthesis source priority because it is not a good source for the target harness questions

## Coverage register rule

The coverage register is mandatory.

It should track at least:

- support-track status
- system-dossier status
- trajectory-case-study status
- formal-dossier status
- informal-cluster status
- eval-dossier status
- current accepted waves
- carry-forward warnings that still limit artifact completion

## Core wave order: 14 waves

### Mechanism Map

1. Wave 01 `exploratory_anchor`
   - status:
     - complete
   - note:
     - preserved legacy anchor, not artifact completion

2. Wave 02 `execution_control_and_terminal_grounding`
   - status:
     - complete
   - verdict:
     - accepted with carry-forward warnings

3. Wave 03 `verification_completion_and_recovery`
   - purpose:
     - verification doctrine
     - false-completion prevention
     - cleanup confirmation
     - rollback and restart behavior
     - recovery and resumability

4. Wave 04 `context_state_memory_workspace`
   - purpose:
     - context management
     - state tracking
     - memory policy
     - workspace and artifact discipline

5. Wave 05 `tools_environment_permissions`
   - purpose:
     - tool gateway contracts
     - post-tool handling
     - environment substrate
     - sandbox and permissions

6. Wave 06 `planning_orchestration_and_interactions`
   - purpose:
     - planning structure
     - orchestration
     - subagents
     - monitoring
     - cross-domain interaction closeout

### Failure Taxonomy

7. Wave 01 `execution_control_and_terminal_failures`

8. Wave 02 `verification_completion_and_recovery_failures`

9. Wave 03 `context_state_memory_workspace_failures`

10. Wave 04 `tools_environment_coordination_and_long_horizon_failures`

### Eval Implications

11. Wave 01 `benchmark_contracts_and_risks`

12. Wave 02 `project_eval_architecture`

### Variant Family Seeds

13. Wave 01 `candidate_families_and_pruning`

14. Wave 02 `block_mapping_and_seed_closeout`

## Serious-wave agent model

Default for `mechanism_map` and `failure_taxonomy`:

- `trajectory/failure analyst`
- `codebase/source-reconstruction analyst`
- `literature/papers/docs analyst`
- `informal/issues/postmortems analyst`

Optional fifth main agent:

- `eval/benchmark analyst`
  - only when the wave is materially shaped by verifier, grader, replay, or benchmark logic

Support rule

- each main analyst may use bounded support sub-agents
- support sub-agents must:
  - do bounded context gathering or structuring tasks
  - save explicit support artifacts
  - never silently replace the main analyst’s synthesis

## Speed model

Deep Synthesis should move faster by changing where work happens, not by pretending depth is smaller than it is.

What should stay serial:

- contradiction review
- principal synthesis
- checklist adjudication
- final acceptance decisions

What should overlap aggressively:

- support-track updates
- dossier deepening
- trajectory-case-study extraction
- bounded support sub-agent work
- next-wave prep while the current wave is in contradiction or adjudication

Main bottlenecks now

- route finding and inventory work
- large-run matrix building
- source subsystem mapping
- paper and informal clustering
- trajectory-to-source linking

Speed fix

- keep core-wave count lower than the old 24-wave plan
- make support tracks load-bearing
- make bounded support sub-agents standard
- stop making each serious wave rediscover the corpus from scratch

## Coverage guarantees

Deep Synthesis should only count as truly deep if all of the following become explicit and reusable:

- architectural-depth system dossiers for the major systems
- trajectory-to-source case studies for serious mechanism and failure claims
- anchor and theme dossiers for formal sources
- cluster dossiers for informal sources
- eval and benchmark dossiers where evaluator logic materially affects claims
- explicit wave-level lane-closure judgments
- explicit artifact-level completion judgment separate from wave acceptance

## Current next move

- Treat `mechanism_map` Wave 02 as complete at the wave level.
- Carry forward its warnings explicitly.
- Keep `coverage_access` moving as a support track with baseline-access work continuing in parallel.
- Open:
  - `mechanism_map` Wave 03 `verification_completion_and_recovery`
- Require that Wave 03 packet explicitly names:
  - which support tracks it depends on
  - which dossiers it must update
  - what it can leave unfinished without blocking contradiction review

Success condition

- Deep Synthesis exits with:
  - accepted `mechanism_map`
  - accepted `failure_taxonomy`
  - accepted `eval_implications`
  - accepted `variant_family_seeds`
  - explicit coverage register
  - reusable dossiers and case studies
  - explicit carry-forward warnings and contradictions
- The next phase should inherit a deep, fast, honest synthesis surface instead of guesswork or wave-level vibes.
