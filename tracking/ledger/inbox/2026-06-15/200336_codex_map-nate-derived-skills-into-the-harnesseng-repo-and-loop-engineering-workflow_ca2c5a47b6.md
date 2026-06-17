# Raw Ledger Update

- recorded_at_utc: 2026-06-15T20:03:36.709185+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: Map Nate-derived skills into the HarnessEng repo and loop engineering workflow
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: ca2c5a47b691b79103e8743a2d722846a390f610c8e8f758a0af4bce66156bed
- commit_message: Add Nate-derived skill map for the loop workflow
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/200336_codex_map-nate-derived-skills-into-the-harnesseng-repo-and-loop-engineering-workflow_ca2c5a47b6.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: Map Nate-derived skills into the HarnessEng repo and loop engineering workflow
- event_type: implementation
- summary: Added a repo-local skill map under workflows/skills and linked it from the skills README. The new note maps explicit Nate skills and derived skill families to the Aether-2 loop surfaces, eval surfaces, synthesis docs, and workflow docs.
- observations: The repo already separates runtime/control code from workflow docs. Aether-2's loop is centered in harness/aether2/control/loop.py with orientation, context, verification, compaction, and Harbor wiring in runtime modules. Public workflow skills already live under workflows/skills, so the new mapping belongs there rather than inside runtime code.
- inference: The cleanest repo placement for Nate-derived skills is as workflow doctrine plus eval guardrails, not as hardcoded runtime behavior. That keeps the runtime generic while making the skill system explicit, searchable, and reviewable.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/workflows/skills/nate-derived-skill-map.md ; /Users/mohamud/Downloads/harnesseng/workflows/skills/README.md ; /Users/mohamud/Downloads/harnesseng/harness/aether2/control/loop.py ; /Users/mohamud/Downloads/harnesseng/harness/aether2/runtime/orientation.py ; /Users/mohamud/Downloads/harnesseng/harness/aether2/runtime/context.py ; /Users/mohamud/Downloads/harnesseng/harness/aether2/runtime/prompts.py ; /Users/mohamud/Downloads/harnesseng/harness/aether2/runtime/verify.py ; /Users/mohamud/Downloads/harnesseng/harness/aether2/runtime/compactor.py ; /Users/mohamud/Downloads/harnesseng/workflows/evals/README.md ; /Users/mohamud/Downloads/harnesseng/workflows/synthesis/README.md
- affected_components: workflows/skills, public workflow navigation, future skill-packaging decisions
- decision_change: Nate-derived skills should be treated as workflow notes and eval-backed operating patterns first, with runtime integration only where a real loop primitive already exists.
- unresolved_questions: Whether to add one or more actual skill files later, and whether the next step should be a skill pack, an eval pack, or both.
- confidence: 0.93
- commit_message: Add Nate-derived skill map for the loop workflow
```
