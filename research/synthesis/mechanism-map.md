# Mechanism Map Principal Synthesis

Date: 2026-04-04

Artifact

- `mechanism_map`

Current judgment

- `mechanism_map` is not complete.
- The current completed run is accepted only as legacy `wave_01_exploratory_anchor`.
- Wave 01 is strong enough to preserve as a governed exploratory anchor because it surfaced real, reusable mechanism structure.
- Wave 01 is not strong enough to close the artifact because major paper, source, trajectory, and informal coverage families remain unread.
- The next governed move is `coverage_access`, not `mechanism_map` Wave 02.

Wave 01 anchor value

- Wave 01 produced real mechanism anchors rather than just notes.
- The strongest anchors are:
  - terminal realism and interrupt recovery
  - multi-layer completion gating
  - cleanup, restore, and repo hygiene as part of completion
  - behavior-level planner or executor or verifier separation in BigAI
  - visible tension between tool contract claims and backend reality
- Those anchors are detailed enough to improve later Deep Synthesis work, but not yet broad enough to serve as the final mechanism spine.

Why Wave 01 is not completion

- Formal paper coverage is still mostly metadata-level because `research/sources/papers/papers_text/` does not exist yet.
- `claw-code` is now first-class source scope but was not excavated in this legacy wave.
- Long-tail trajectory families such as `extract-moves-from-video` and `gpt2-codegolf` were not read deeply enough to prevent regime overfitting.
- Most informal, issues, and postmortems remain unread.
- Many `src_cod_*` captures were sampled, not traversed.

Accepted exploratory-anchor mechanism families

- `tool_gateway`
  - native or schema-bound tool invocation appears to matter materially in KIRA, DeepAgents, and the formal doc lane
- `execution_control`
  - PTY-backed shell control, interruptibility, and explicit command completion behavior are real recurring mechanisms
- `verification_or_completion`
  - internal verifier work, external grader artifacts, and final reward or test state must be reconciled rather than collapsed
- `state_and_recovery`
  - backup-first, restore-before-done, and state-safe verification are real mechanism families in stateful tasks
- `workspace_or_artifact_hygiene`
  - cleanup, repo hygiene, and delivery-state preservation belong inside the completion mechanism surface
- `workflow_role_separation`
  - BigAI presents a strong behavior-level planner or executor or verifier split, but it remains `behavioral reconstruction`

Interaction map status

- Wave 01 now has an explicit interaction analysis artifact at:
  - `tracking/collab/stage_02_synthesis/mechanism_map/outputs/interaction_analysis.md`
- The strongest interaction cluster is:
  - execution control × verification/completion × state/recovery

Contradiction status

- Wave 01 contradictions were not flattened away.
- The most important carried contradictions are:
  - BigAI role separation is behaviorally strong but source-opaque
  - DeepAgents sandbox claims and backend reality are in tension
  - internal verifier status and final task success are non-equivalent
  - KIRA visible verifier structure may be weaker, or merely less exposed in trace rendering

Wave verdict

- Contradiction review verdict:
  - `pass_with_warnings`
- Wave audit verdict:
  - `pass_with_warnings`

Next governed move

1. Preserve this run as `wave_01_exploratory_anchor`.
2. Keep `coverage_access` running as support.
3. Continue:
   - Wave 01 `formal_access_closure`
   - Wave 02 `source_system_promotion_and_map`
4. Reopen `mechanism_map` with Wave 02 `execution_control_and_terminal_grounding` under the vertical multi-agent model.
