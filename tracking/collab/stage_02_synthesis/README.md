# Stage 02 Synthesis

This directory holds collaboration workspaces for the synthesis phase.

Use it after raw research closeout to convert the source-organized corpus into mechanism-level project artifacts.

## Current stage state

- Deep Synthesis is active under the compressed `14`-wave model.
- Completed so far:
  - `mechanism_map` Wave 01 `exploratory_anchor`
  - `mechanism_map` Wave 02 `execution_control_and_terminal_grounding` as accepted with carry-forward warnings
- Continuous support work now includes:
  - `coverage_access`
  - `coverage_register`
  - dossiers and case studies

## Primary artifacts

- `deep_synthesis_plan/`
- `deep_synthesis_setup/`
- `deep_synthesis_wave_plan/`
- `coverage_register/`
- `coverage_access/`
- `adjudication/`
- `source_system_dossiers/`
- `trajectory_case_studies/`
- `informal_cluster_dossiers/`
- `eval_benchmark_dossiers/`
- `eval_implications/`
- `variant_family_seeds/`
- `mechanism_map/`
- `failure_taxonomy/`
- `red_team_review/`

## Recommended per-artifact layout

```text
tracking/collab/stage_02_synthesis/
  mechanism_map/
    brief.md
    decision.md
    waves/
      wave_02_execution_control_and_terminal_grounding/
        brief.md
        inputs/
        outputs/
        synthesis/
          principal_synthesis.md
        adjudication/
    outputs/                      # legacy compatibility for early flat waves
    synthesis/
      principal_synthesis.md
      cumulative_synthesis.md
```

## Operating rules

1. Start with synthesis prep, not immediate free-form synthesis.
2. Keep agent outputs separate until principal-agent synthesis.
3. Treat trajectories as a top-priority evidence class.
4. Include informal sources, but label them as informal where relevant.
5. If the synthesis result materially changes project direction, emit a `RAW_LEDGER_UPDATE` with evidence paths into this stage folder.
6. Do not auto-fill stub or placeholder docs just because they exist. The active `brief.md` and `decision.md` define the required outputs.
7. Before opening Deep Synthesis, the principal agent may create `deep_synthesis_plan/` to define full-corpus evidence policy, artifact order, multi-agent routing, and adversarial checkpoints.
8. Before opening Deep Synthesis execution, the principal agent may create `deep_synthesis_setup/` to define specialist roster, model-role mapping, prompt-pack requirements, task-packet structure, tracing rules, and the final approval boundary.
9. Every Deep Synthesis artifact must report `coverage_used`, `coverage_not_yet_used`, `evidence_classes_touched`, and `priority_sources_not_yet_read`.
10. Every Deep Synthesis artifact must begin with a mandatory preflight: scope confirmation, read order, critical sources, coverage risks, blind spots, and blockers.
11. Use `DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md` when the human owner is manually running blind-parallel specialists.
12. Use `DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md` for fresh-agent launch discipline, follow-up handling, wave-close rules, BigAI reconstruction discipline, and stage-exit requirements.
13. Use `DEEP_SYNTHESIS_HANDOFF_SCHEMA.md` whenever one Deep Synthesis artifact hands claims to the next.
14. Use `literature_dossiers/README.md` to keep formal-source analysis structured instead of flattening papers into one undifferentiated lane.
15. Use `source_system_dossiers/README.md`, `trajectory_case_studies/README.md`, `informal_cluster_dossiers/README.md`, and `eval_benchmark_dossiers/README.md` when a wave needs reusable depth artifacts beyond wave prose.
16. Use `DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md` when deciding whether a lane is actually wave-sufficient.
17. Use `DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md` when assigning the main-lane roster, support-sub-agent pattern, and gate-time Gemini/Claude use for a specific wave class.
18. Use `coverage_register/current_status.md` as the canonical coverage-control surface for what is actually completed versus still thin.
19. Use the adjudication layer intentionally:
    - `DEEP_SYNTHESIS_WAVE_AUDIT_CHECKLIST.md` after accepted waves
    - artifact-level checklists before accepting `mechanism_map` or `failure_taxonomy`
    - `DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md` as the stage or stage-exit audit gate
    - none of these are producer prompts for first-pass extraction
20. `coverage_used` must list concrete repo-local paths or path globs actually read in the current wave.
21. One wave is still the minimum execution unit: packet review, preflight, first-pass analysis, contradiction review, principal synthesis, handoff, then checklist adjudication.
22. A planned multi-wave sequence is allowed when it is explicitly defined in an approved wave plan. Ad hoc extra waves beyond that plan still require explicit approval.
23. Wave outputs are historical records. Accepted claims, contradictions, coverage frontier, open questions, and carried-forward warnings must be rolled into `cumulative_synthesis.md` after each accepted wave.
24. Gemini and Claude are now gate-time external reviewers rather than default parallel main lanes.
25. `coverage_access` is a continuous support track, not a universal blocker. It should overlap with new core Deep Synthesis waves whenever the active packet has enough honest evidence for its target domain.
26. `mechanism_map` and `failure_taxonomy` waves should be vertical domain waves, not source-only then trajectory-only horizontal passes.
