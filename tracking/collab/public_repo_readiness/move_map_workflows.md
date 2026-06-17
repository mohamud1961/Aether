# Move Map: Workflow / Skills / Methodology Layer

Discovery date: 2026-06-16
Agent: read-only discovery pass

---

## 1. Executive Summary

### State of the methodology layer

The `workflows/` directory is **substantially real**, not a skeleton. Every top-level
skill, orchestration page, template, and synthesis guide contains concrete procedure,
governing questions, step-by-step workflows, output contracts, and guardrails. No
single file in `workflows/` is a stub in the blank-placeholder sense. The weakest
surfaces are the three single-paragraph section READMEs (`evals/`, `case-studies/`,
`orchestration/`) — all of which are navigation entries rather than skills, and are
honest about that role.

### What is already in `workflows/`

- `loop-engineering.md` — real taxonomy with a public/private/future split; the
  definitive loop narrative for reviewers.
- `ai-native-engineering-showcase.md` — full methodology overview with concrete
  section structure.
- `skills/` — 20 files; 13 real skill docs with governing questions and step-by-step
  workflows; 7 deep-synthesis sub-skills; all structurally complete.
- `synthesis/synthesis-handbook.md` — real multi-section handbook.
- `templates/` — 6 real checklists (run-analysis-closeout, eval-first-slice,
  multi-thread-handoff, direct-port-provenance, adversarial-review-closeout,
  provenance-publication-review).
- `orchestration/README.md`, `evals/README.md`, `case-studies/README.md` — thin
  navigation stubs (1–3 paragraphs each), honest about their role.

### What is missing for the showcase

1. **`workflows/loop-engineering/`** (directory): the headline "loop engineering"
   section currently lives in a single `.md` file. The concrete loop evidence lives
   in `tracking/collab/aether2_build_orchestration/orchestration_ledger.md` and the
   run-analysis directories. Nothing in `workflows/` surfaces that real evidence.

2. **`workflows/prompts/`** (directory): the 15-file `prompts/` pack is the richest
   unplaced methodology gold — principal-agent, git-commit, synthesis-prep,
   deep-synthesis specialist family, contradiction analyst, checklist adjudicator.
   None of these are linked from `workflows/`. They are internal-path-contaminated
   (all 15 have `/Users/mohamud/Downloads/harnesseng` in line 3) and must be
   sanitized before publication.

3. **`workflows/orchestration/`** contains only a navigation stub. The real governed
   multi-agent model (`GOVERNED_MULTI_AGENT_OPERATING_MODEL.md`),
   `PRINCIPAL_AGENT_WORKFLOW.md`, and `SYNTHESIS_TEAM_SPEC.md` are at the repo root.
   None of those surface in `workflows/orchestration/`.

4. **`workflows/schemas/`** (directory) does not exist. Four root-level schema docs
   (`FAILURE_CARD_SCHEMA.md`, `MECHANISM_CARD_SCHEMA.md`,
   `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md`, `VARIANT_FAMILY_SEED_SCHEMA.md`) and
   `tracking/collab/TASK_PACKET_TEMPLATE.md` belong here.

5. **Loop evidence** (concrete artifacts): the `tracking/collab/` directories contain
   the most impressive real evidence for the methodology — a 154-line orchestration
   ledger with 32 worker dispatches, full failure taxonomy outputs from real runs, and
   hand-off chains. Nothing in `workflows/` links to or summarizes these in a
   public-safe way.

6. **`workflows/case-studies/`** is a 3-line stub. The real public case studies live
   in `docs/case-studies/` and the `tracking/collab/aether2_g5_run_analysis_20260613/`
   directories. A case study that tells the loop-engineering story from the
   orchestration ledger does not yet exist.

### Biggest gaps for the showcase

Priority 1 (blocks the headline story):
- No `workflows/loop-engineering/` folder with a concrete example walk-through
  that cites real evidence.
- Prompts are not surfaced anywhere public and are all path-contaminated.

Priority 2 (weakens the depth story):
- `workflows/orchestration/` has no real content; root governance docs are
  disconnected.
- Schemas live at the root with no pathway from `workflows/`.

Priority 3 (nice-to-have enrichment):
- `workflows/evals/` and `workflows/case-studies/` are navigation stubs with no
  skill content.

---

## 2. Move-Map Table

### Legend
- **needs-sanitization Y** = file requires editing before publication
- **replaces placeholder** = the move replaces an existing thin stub
- **private** = must NOT be published; listed for completeness

| Artifact | Current path | Proposed destination | Needs sanitization | Replaces placeholder | Notes |
|---|---|---|---|---|---|
| Governed multi-agent operating model | `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md` | `workflows/orchestration/governed-multi-agent-model.md` | Y (light: remove Azure VM lifecycle rules, terminal-workflow mentions, script paths; keep abstract role model) | Yes — replaces `workflows/orchestration/README.md` nav stub | Real doc; 450 lines; covers role hierarchy, collab modes, stage model. Eval name references in §"Stage 7" need to become generic. |
| Principal agent workflow | `PRINCIPAL_AGENT_WORKFLOW.md` | `workflows/orchestration/principal-agent-workflow.md` | N (clean — no private paths, no eval names) | No — adds to orchestration folder | Real doc; 180 lines; step-by-step operator guide for engaging the principal agent. Public-safe as-is. |
| Synthesis team spec | `SYNTHESIS_TEAM_SPEC.md` | `workflows/orchestration/synthesis-team-spec.md` | N (clean) | No | Real doc; 480 lines; per-artifact cell activation, run order, collaboration modes. Public-safe. |
| Synthesis prep checklist | `SYNTHESIS_PREP_CHECKLIST.md` | `workflows/synthesis/synthesis-prep-checklist.md` | N (clean) | No | Real doc; 134 lines; 10-section checklist with red-flag guard. Public-safe. |
| Failure card schema | `FAILURE_CARD_SCHEMA.md` | `workflows/schemas/failure-card.md` | N (clean) | No — folder does not exist | Real schema; 125 lines; complete field-level guidance. |
| Mechanism card schema | `MECHANISM_CARD_SCHEMA.md` | `workflows/schemas/mechanism-card.md` | N (clean) | No | Real schema; 131 lines; complete field-level guidance. |
| Trajectory / source case study template | `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md` | `workflows/schemas/trajectory-case-study.md` | N (clean) | No | Real template; 79 lines; 9-section CASE_STUDY block. |
| Variant family seed schema | `VARIANT_FAMILY_SEED_SCHEMA.md` | `workflows/schemas/variant-family-seed.md` | Y (light: check for terminal-workflow/eval vocabulary before publishing) | No | Confirm content is generic before promoting. |
| Task packet template | `tracking/collab/TASK_PACKET_TEMPLATE.md` | `workflows/schemas/task-packet.md` | N (clean — already generic) | No | Real template; 25-field TASK_PACKET struct. |
| Principal project agent prompt | `prompts/principal_project_agent_prompt.md` | `workflows/prompts/principal-project-agent.md` | Y (critical: line 3 has `/Users/mohamud/Downloads/harnesseng`; also `private calibration suite` reference at bottom; remove all private paths and eval-specific terms) | No — folder does not exist | Real prompt; 131 lines; collaboration-mode guidance, storage rules, escalation rules. Gold for showcase. |
| Git commit agent prompt | `prompts/git_commit_agent_prompt.md` | `workflows/prompts/git-commit-agent.md` | Y (critical: line 3 has private path; also `tracking/ledger/inbox/` internal path assumption; replace with generic `<project>/tracking/ledger/inbox/` or abstract it) | No | Real prompt; 111 lines; commit-slicing discipline with explicit output contract. |
| Synthesis prep agent prompt | `prompts/synthesis_prep_agent_prompt.md` | `workflows/prompts/synthesis-prep-agent.md` | Y (critical: line 3 private path; internal stage path references; replace with generic paths) | No | Real prompt; 89 lines; complete role spec. |
| Synthesis prep red-team agent prompt | `prompts/synthesis_prep_red_team_agent_prompt.md` | `workflows/prompts/synthesis-prep-red-team-agent.md` | Y (critical: line 3 private path) | No | Real prompt; red-team / adversarial review role. |
| Synthesis prep eval inventory agent prompt | `prompts/synthesis_prep_eval_inventory_agent_prompt.md` | `workflows/prompts/synthesis-prep-eval-inventory-agent.md` | Y (critical: line 3 private path) | No | Real prompt; eval-specific evidence specialist. |
| Deep synthesis shared policy prompt | `prompts/deep_synthesis_shared_policy_prompt.md` | `workflows/prompts/deep-synthesis-shared-policy.md` | Y (critical: line 3 private path; also `gpt54`/`Gemini`/`Claude` model-name mentions in gate-review section; abstract to `model-A`, `model-B` or remove specific names) | No | Real prompt; 149 lines; evidence-precedence rules, coverage reporting contract, extraction ceiling. Most re-usable deep synthesis doc. |
| Deep synthesis trajectory / failure analyst | `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md` | `workflows/prompts/deep-synthesis-trajectory-failure-analyst.md` | Y (critical: line 3 private path; output storage path is private) | No | Real prompt; 75 lines; complete role spec with output contract. |
| Deep synthesis codebase / source analyst | `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md` | `workflows/prompts/deep-synthesis-codebase-source-analyst.md` | Y (critical: line 3 private path) | No | Real prompt. |
| Deep synthesis eval / eval analyst | `prompts/deep_synthesis_eval_analyst_prompt.md` | `workflows/prompts/deep-synthesis-eval-analyst.md` | Y (critical: line 3 private path) | No | Real prompt. |
| Deep synthesis literature / docs analyst | `prompts/deep_synthesis_literature_papers_docs_analyst_prompt.md` | `workflows/prompts/deep-synthesis-literature-analyst.md` | Y (critical: line 3 private path) | No | Real prompt. |
| Deep synthesis informal / issues analyst | `prompts/deep_synthesis_informal_issues_postmortems_analyst_prompt.md` | `workflows/prompts/deep-synthesis-informal-analyst.md` | Y (critical: line 3 private path) | No | Real prompt. |
| Deep synthesis support sub-agent prompt | `prompts/deep_synthesis_support_subagent_prompt.md` | `workflows/prompts/deep-synthesis-support-subagent.md` | Y (critical: line 3 private path) | No | Real prompt; bounded support/matrix/inventory sub-role. |
| Deep synthesis contradiction analyst | `prompts/deep_synthesis_contradiction_analyst_prompt.md` | `workflows/prompts/deep-synthesis-contradiction-analyst.md` | Y (critical: line 3 private path) | No | Real prompt. |
| Deep synthesis checklist adjudicator | `prompts/deep_synthesis_checklist_adjudicator_prompt.md` | `workflows/prompts/deep-synthesis-checklist-adjudicator.md` | Y (critical: line 3 private path; also specific checklist internal paths) | No | Real prompt; 80 lines; adversarial audit gate with explicit verdict contract. |
| Deep synthesis eval implications role | `prompts/deep_synthesis_eval_implications_role_prompt.md` | `workflows/prompts/deep-synthesis-eval-implications.md` | Y (critical: line 3 private path) | No | Real prompt. |
| Deep synthesis variant pruning role | `prompts/deep_synthesis_variant_pruning_role_prompt.md` | `workflows/prompts/deep-synthesis-variant-pruning.md` | Y (critical: line 3 private path) | No | Real prompt. |
| Base system prompt | `prompts/base_system.md` | `workflows/prompts/base-system.md` | N (generic; two template variables `{task_instruction}` and `{env_snapshot}` only) | No | Real prompt; clean; 14 lines. |
| Analyze-agent-runs skill source | `tracking/collab/skills/analyze-agent-runs/SKILL.md` | `workflows/skills/analyze-agent-runs-full.md` (or merge into existing) | Y (light: `openai.yaml` agent config in same folder references OpenAI-specific infra; keep skill text only; references like `scripts/inventory_run.py` are fine) | Partial — existing `workflows/skills/analyze-agent-runs.md` is a clean public summary; the `tracking/collab/skills/` version is the longer full-spec version with 11-step workflow | The public `workflows/skills/analyze-agent-runs.md` is already publication-grade. The `tracking/collab/` version adds more implementation detail. Consider merging the richer step detail into the public version rather than publishing two. |
| Analyze-agent-runs failure taxonomy ref | `tracking/collab/skills/analyze-agent-runs/references/failure-taxonomy.md` | `workflows/skills/references/failure-taxonomy.md` | N (clean) | No | Real; 65 lines; component-mapping rule is the key additive piece. |
| Analyze-agent-runs evidence-and-causality ref | `tracking/collab/skills/analyze-agent-runs/references/evidence-and-causality.md` | `workflows/skills/references/evidence-and-causality.md` | N (clean) | No | Real; 67 lines. |
| Analyze-agent-runs trace-workflow ref | `tracking/collab/skills/analyze-agent-runs/references/trace-workflow.md` | `workflows/skills/references/trace-workflow.md` | N (clean) | No | Real; 70 lines; per-step field table is high-value. |
| Analyze-agent-runs output template ref | `tracking/collab/skills/analyze-agent-runs/references/output-template.md` | `workflows/skills/references/output-template.md` | N (clean) | No | Real; 56 lines. |
| Analyze-agent-runs fix-design ref | `tracking/collab/skills/analyze-agent-runs/references/fix-design.md` | `workflows/skills/references/fix-design.md` | N (clean — read next to verify) | No | Real (verified by README in SKILL.md). |
| AGENTS.md (methodology sections only) | `AGENTS.md` | `workflows/orchestration/codex-goal-governance.md` | Y (medium: strip Azure VM scripts, `terminal-workflow`, `tool-call composite` references; keep Goal governance, experiment discipline, eval-first reset rules as generic methodology) | No — adds to orchestration | The Goal governance, orchestrator handoff requirement, review-gate taxonomy, and experiment discipline sections are the gold. The eval-specific lines (169–170, 193) and mission header need generalization. |
| Aether-2 orchestration ledger | `tracking/collab/aether2_build_orchestration/orchestration_ledger.md` | `workflows/loop-engineering/orchestration-ledger-case-study.md` | Y (medium: strip worker thread IDs, Azure/VM model names like `gpt-5.5`/`gpt-5.4-mini`, internal thread handles; keep orchestration pattern, task-state table structure, decision-log practice) | No — needs new folder | The orchestration ledger (154 lines, 32 workers, status table) is the strongest concrete evidence of governed loop orchestration in the repo. Sanitized version belongs in `workflows/loop-engineering/`. |
| Hour-0 contracts | `tracking/collab/aether2_build_orchestration/hour0_contracts.md` | `workflows/loop-engineering/hour-zero-contracts-example.md` | Y (medium: strip model names, thread IDs; keep contract-freeze pattern) | No | Real artifact; demonstrates pre-execution contract discipline. |
| Decision log | `tracking/collab/aether2_build_orchestration/decision_log.md` | `workflows/loop-engineering/orchestration-decision-log-example.md` | Y (medium: strip private tool/provider names; keep decision taxonomy) | No | Real artifact; public-safe form shows how orchestration decisions are recorded. |
| G5 failure taxonomy | `tracking/collab/aether2_g5_run_analysis_20260613/failure_taxonomy.md` | `workflows/loop-engineering/run-analysis-example-failure-taxonomy.md` | Y (heavy: strip all task names, VM state, specific harness paths; keep the causal family analysis structure, evidence chain method, and competing-hypothesis rejection discipline) | No | Real artifact with full evidence chain (F1 through Fn families). The **structure** of the taxonomy is the showcase; the task-specific content is private. |
| G5 evidence inventory | `tracking/collab/aether2_g5_run_analysis_20260613/evidence_inventory.md` | `workflows/loop-engineering/run-analysis-example-evidence-inventory.md` | Y (heavy: same as above — strip all task/VM-specific content; keep the artifact-inventory table structure and provenance-assessment method) | No | Demonstrates the evidence-freeze-before-analysis discipline. |
| Pre-g1 completion handoff | `tracking/collab/aether2_build_orchestration/pre_g1_completion_handoff.md` | `workflows/loop-engineering/handoff-example-pre-milestone.md` | Y (medium: strip thread IDs, model names, specific script names; keep the handoff field structure and evidence discipline) | No | Real handoff; shows the multi-thread-handoff template in action. |
| Analyze-agent-runs `inventory_run.py` | `tracking/collab/skills/analyze-agent-runs/scripts/inventory_run.py` | `workflows/skills/scripts/inventory_run.py` | Y (light: check for hardcoded paths; tool is referenced from SKILL.md as an inventory aid) | No | Real script. |
| Deep synthesis execution protocol | `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md` | `workflows/synthesis/deep-synthesis-execution-protocol.md` | Y (medium: check for private corpus paths, model names, internal version strings) | No | Real doc; the execution protocol is load-bearing for the deep-synthesis family. |
| Deep synthesis multi-agent workflow guide | `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md` | `workflows/synthesis/deep-synthesis-multi-agent-guide.md` | Y (same as above) | No | Real doc. |
| **PRIVATE — do not publish** | `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` | — | — | — | Live campaign state; encodes active corpus coverage decisions. |
| **PRIVATE — do not publish** | `tracking/collab/stage_02_synthesis/adjudication/*.md` (checklist files) | — | — | — | Private audit checklists that encode private-eval-sensitive pass/fail criteria for specific corpus waves. |
| **PRIVATE — do not publish** | `tracking/collab/aether2_g5_run_analysis_20260613/task_findings.md` | — | — | — | Task-specific findings from private runs. |
| **PRIVATE — do not publish** | All `tracking/collab/**/runs/` directories | — | — | — | Raw run artifacts with eval-native evidence. |
| **PRIVATE — do not publish** | `tracking/ledger/` | — | — | — | Raw historian inbox and canonical ledger entries. |
| **PRIVATE — do not publish** | `research/synthesis/source_system_dossiers/` | — | — | — | Named external system dossiers; may contain private-eval-sensitive analysis. |

---

## 3. Loop Engineering Section

### What "loop engineering" means in this repo

The loop is:

```
run -> analyze -> hypothesize -> eval -> implement -> validate -> promote/kill
```

This is not an aspirational loop. The repo has real evidence for every stage.

### Real artifacts that document and evidence the loop

#### Methodology layer (already public-safe in `workflows/`)

- `workflows/loop-engineering.md` — taxonomy; the conceptual overview.
- `workflows/ai-native-engineering-showcase.md` — application-facing framing.
- `workflows/skills/loop-orchestrator.md` — the operator skill for bounded orchestration:
  governing question, loop shape, control-map discipline, hook/automation split.
- `workflows/skills/analyze-agent-runs.md` — the "analyze" step made into a reusable skill.
- `workflows/skills/eval-first-implementation-slice.md` — the "eval → implement" gate.
- `workflows/skills/code-review-closeout.md` — the review gate in the "validate" step.
- `workflows/skills/provenance-publication-review.md` — the "promote" publication gate.
- `workflows/templates/multi-thread-handoff.md` — handoff discipline in the loop.
- `workflows/templates/run-analysis-closeout-checklist.md` — the "analyze" step output form.

#### Evidence layer (real execution artifacts in `tracking/collab/`)

These documents evidence the loop actually running, not just described.

| Artifact | Path | Loop stage evidenced | Sanitization needed |
|---|---|---|---|
| Orchestration ledger (32-worker build) | `tracking/collab/aether2_build_orchestration/orchestration_ledger.md` | Orchestrate → implement → validate (G1 build, worker-dispatch wave, escape-hatch use, review-gate failure diagnosis) | Yes (model names, thread IDs, script paths) |
| Hour-0 contract freeze | `tracking/collab/aether2_build_orchestration/hour0_contracts.md` | Orchestrate (pre-execution discipline) | Yes (light) |
| Decision log | `tracking/collab/aether2_build_orchestration/decision_log.md` | Orchestrate (decision taxonomy) | Yes (light) |
| G5 evidence inventory | `tracking/collab/aether2_g5_run_analysis_20260613/evidence_inventory.md` | Run → Analyze (freeze the authority surface before concluding) | Yes (heavy — strip task/VM content; keep structure) |
| G5 failure taxonomy | `tracking/collab/aether2_g5_run_analysis_20260613/failure_taxonomy.md` | Analyze (causal family analysis, competing-hypothesis rejection) | Yes (heavy) |
| G5 outcome scoreboard | `tracking/collab/aether2_g5_run_analysis_20260613/outcome_scoreboard.md` | Analyze → Hypothesize (validity split, scoreable vs. invalid) | Yes (heavy) |
| G5 lane recommendation | `tracking/collab/aether2_g5_run_analysis_20260613/g5_lane_recommendation.md` | Hypothesize → Eval (next failure lane design after analysis) | Yes (heavy) |
| Full run analysis 2026-06-14 | `tracking/collab/aether2_run_analysis_20260614/full_run_analysis_20260614T213000Z.md` | Analyze (follow-on run cycle) | Yes (heavy) |
| G5 implementation plan | `tracking/collab/aether2_g5_implementation_orchestration_20260613/IMPLEMENTATION_PLAN.md` | Hypothesize → Implement (plan from analysis output) | Yes (medium) |
| G5 runner handoff | `tracking/collab/aether2_g5_implementation_orchestration_20260613/runner_team_handoff.md` | Implement (multi-thread worker handoff in practice) | Yes (medium) |
| Pre-G1 completion handoff | `tracking/collab/aether2_build_orchestration/pre_g1_completion_handoff.md` | Validate → Promote (milestone closeout discipline) | Yes (medium) |
| Local iteration loop 2026-04-06 | `tracking/collab/local_iteration_loop_2026-04-06/` | Run → Validate (local board runs, full-board 16-row cycle) | Private: contains raw run artifacts; summarize only |
| Eval suite v1 tournament orchestration | `tracking/collab/autonomous_loop/eval_suite_v1_tournament_orchestration/` | Full loop (tournament scripts show automated run → score → dispatch) | Private: contains Python bytecode and launch scripts; expose scripts only after audit |

#### How to organize in `workflows/loop-engineering/`

Recommended folder structure:

```
workflows/loop-engineering/
  README.md               # the headline story; link to the taxonomy page
  orchestration-ledger-case-study.md   # sanitized version of aether2_build_orchestration ledger
  hour-zero-contracts-example.md       # sanitized contract-freeze artifact
  run-analysis-case-study.md           # sanitized synthesis of g5 evidence inventory + failure taxonomy
  handoff-example.md                   # sanitized pre-g1 handoff
```

The case studies must not expose task names, raw result rows, VM addresses, or model
version strings. They should expose: the decision structure, the evidence-chain method,
the handoff field discipline, and the escape-hatch pattern.

---

## 4. Derived Skills List

Each skill below is grounded in real prompts, work products, or governance docs. Source
paths are the artifacts the skill is derived from or abstracted from.

### 4a. Deep Synthesis (family — already in `workflows/skills/`)

The 8-member family (`deep-synthesis*.md`) is already published and is real. The
source is the 15-file `prompts/` pack.

| Skill | Source paths |
|---|---|
| `deep-synthesis-coverage-access.md` | `prompts/deep_synthesis_shared_policy_prompt.md` (coverage section); `tracking/collab/stage_02_synthesis/coverage_register/` |
| `deep-synthesis-evidence-inventory.md` | `prompts/synthesis_prep_agent_prompt.md`; `prompts/deep_synthesis_shared_policy_prompt.md` |
| `deep-synthesis-mechanism-map.md` | `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`; `MECHANISM_CARD_SCHEMA.md` |
| `deep-synthesis-failure-taxonomy.md` | `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`; `FAILURE_CARD_SCHEMA.md`; `tracking/collab/aether2_g5_run_analysis_20260613/failure_taxonomy.md` |
| `deep-synthesis-source-system-dossiers.md` | `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md` |
| `deep-synthesis-trajectory-case-studies.md` | `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md`; `research/synthesis/trajectory_case_studies/` |
| `deep-synthesis-adjudication.md` | `prompts/deep_synthesis_checklist_adjudicator_prompt.md`; `tracking/collab/stage_02_synthesis/adjudication/` |
| `deep-synthesis-wave-closure.md` | `prompts/deep_synthesis_checklist_adjudicator_prompt.md` |

### 4b. Run Analysis / Analyze-Agent-Runs (already in `workflows/skills/`)

Already published at `workflows/skills/analyze-agent-runs.md`. The richer full-spec
version is `tracking/collab/skills/analyze-agent-runs/SKILL.md`.

Source grounding:
- `tracking/collab/skills/analyze-agent-runs/SKILL.md`
- `tracking/collab/skills/analyze-agent-runs/references/` (5 reference docs)
- `tracking/collab/aether2_g5_run_analysis_20260613/` (real usage evidence)
- `tracking/collab/aether2_run_analysis_20260614/` and `aether2_run_analysis_20260615/` (two more real usage cycles)

**Gap**: the public skill is a clean summary. The `tracking/collab/skills/` version
has the richer 12-step workflow with per-step rules. Consider merging the most
operative steps (steps 6–9 on fake-progress, pass quality, failure analysis, and
harness component evaluation) into the public version.

### 4c. Loop Orchestrator (already in `workflows/skills/`)

Source grounding:
- `prompts/principal_project_agent_prompt.md` (principal-agent role spec)
- `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md` (operating model)
- `PRINCIPAL_AGENT_WORKFLOW.md` (engagement protocol)
- `AGENTS.md` §Codex Goal Governance (goal governance rules)
- `tracking/collab/aether2_build_orchestration/orchestration_ledger.md` (real usage evidence)

**Gap**: the public `loop-orchestrator.md` is shorter (113 lines) than the governance
docs that back it. The "control map", "worker policy", and "escape-hatch" concepts
in the orchestration ledger are more concrete than what the public skill describes.

### 4d. Planning / Briefing (not yet a named skill)

Derivable from:
- `prompts/principal_project_agent_prompt.md` §Operating Procedure and §Collaboration mode guidance
- `PRINCIPAL_AGENT_WORKFLOW.md` steps 1–4 (activate stage, frame task, create task packet, route specialists)
- `tracking/collab/TASK_PACKET_TEMPLATE.md`
- `tracking/collab/aether2_build_orchestration/hour0_contracts.md` (real example)

Proposed skill: `workflows/skills/task-briefing-and-planning.md`
- governing question: what is the objective, who may act, what evidence closes the loop?
- workflow: stage identification → task packet → collaboration-mode selection → specialist routing → escalation triggers
- output contract: TASK_PACKET struct + external-agent callout format

### 4e. Codegen / Implementation Slice (not yet a named skill)

Derivable from:
- `AGENTS.md` §Experiment Discipline and §Eval-First Reset Rules
- `workflows/skills/eval-first-implementation-slice.md` (already real — the eval-first gate)
- `tracking/collab/aether2_build_orchestration/orchestration_ledger.md` §Worker Policy

The implementation-slice skill already exists as `eval-first-implementation-slice.md`.
What does not exist yet: the **worker-facing** complement — how a worker receives a
contract-complete packet, implements one bounded slice, and produces the handoff. This
is evidenced by the 32 worker dispatches in the orchestration ledger.

Proposed skill: `workflows/skills/bounded-implementation-slice.md`
- governing question: can this slice be completed within the declared write scope with the evidence available?
- workflow: packet reception → contract review → write-scope confirmation → implementation → local test run → handoff production
- output contract: worker handoff format (from `AGENTS.md` §Orchestrator Handoff Requirement)

### 4f. Code Review Closeout (already in `workflows/skills/`)

Source grounding:
- `workflows/skills/code-review-closeout.md` (real; 94 lines)
- `workflows/skills/adversarial-code-review-closeout.md` (real; 46 lines; the manual fallback variant)
- `AGENTS.md` §Review Gates (the 4-level gate taxonomy: none, adversarial_only, codex_review_skill, +adversarial)
- `tracking/collab/aether2_build_orchestration/codex_review_reliability_handoff.md` (real evidence of review-gate failure diagnosis)

**Gap**: the 4-level gate taxonomy in `AGENTS.md` is more concrete than anything in
the public skill. Adding a "when to choose each gate" section to `code-review-closeout.md`
would make the skill noticeably stronger.

### 4g. Eval Design / Variant Governance (not yet a named skill)

Derivable from:
- `AGENTS.md` §Experiment Discipline (no variant without target eval, predicted delta, named sentinels)
- `AGENTS.md` §Eval-First Reset Rules
- `VARIANT_FAMILY_SEED_SCHEMA.md`
- `tracking/collab/variant_hypothesis_backlog.md`
- `variants/families/attribution_guard_tournament/decision_table.json`
- `variants/shared/decision_rubric.md`

Proposed skill: `workflows/skills/eval-design-and-variant-governance.md`
- governing question: what failure family are we targeting, and what evidence will make the keep/kill decision?
- workflow: failure classification → proper eval design (contract, fixture, grader, baselines, sentinels) → variant card creation → lane opening → keep/kill/iterate
- output contract: VARIANT_FAMILY_SEED struct; scoreboard row

### 4h. Provenance / Publication Review (already in `workflows/skills/`)

Source grounding:
- `workflows/skills/provenance-publication-review.md` (real; 72 lines)
- `workflows/templates/direct-port-provenance-review.md` (real; 30 lines)
- `docs/provenance/agent_runtime_adaptation_policy.md`
- `tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`
- `tracking/collab/public_repo_readiness/documentation_packaging_handoff.md`

Real and well-grounded. No gaps beyond the existing publication gap list.

### 4i. Git Commit Slicing (not yet a named skill in `workflows/`)

Source grounding:
- `prompts/git_commit_agent_prompt.md` (real; 111 lines; complete commit-agent spec with output contract)

Proposed skill: `workflows/skills/git-commit-slicing.md`
- governing question: what is the smallest coherent commit that can be made from the current worktree?
- workflow: worktree inspection → commit-candidate clustering → intent verification → staging → commit message discipline → git handoff report
- output contract: GIT_AGENT_REPORT struct (already in the prompt)

The prompt is the source; the sanitized public skill version would drop the private
path reference and generalize the ledger inbox path.

### 4j. Handoff Writing (already in `workflows/templates/`)

The multi-thread-handoff template is real and complete. What does not exist: a
**skill** that explains *how* to produce a high-quality handoff (not just what fields
it needs). The evidence is the g5 runner/harness handoffs and the pre-G1 handoff.

Proposed skill: `workflows/skills/handoff-writing.md`
- governing question: can the receiving orchestrator act on this without reopening the full task?
- workflow: status determination → scope summary → evidence path listing → risk enumeration → next-action framing → delivery receipt
- grounded in: `workflows/templates/multi-thread-handoff.md`; `AGENTS.md` §Orchestrator Handoff Requirement; `tracking/collab/aether2_g5_implementation_orchestration_20260613/runner_team_handoff.md`

---

## 5. Open Questions

1. **Prompts folder name**: should the sanitized prompts land in `workflows/prompts/`
   (alongside skills and templates) or in a top-level `prompts/` folder that stays
   internal but links into `workflows/`? The current `prompts/` has no `workflows/`
   link; the simplest resolution is to publish sanitized copies inside `workflows/prompts/`
   while keeping the private originals under `prompts/`.

2. **Loop-engineering/ folder vs. case studies folder**: the `workflows/loop-engineering/`
   folder proposal overlaps with the `docs/case-studies/` folder that already holds
   two public case studies. Should loop-evidence case studies go in
   `docs/case-studies/` (which already has a public index) or in a new
   `workflows/loop-engineering/` folder? Recommend: put the **orchestration evidence**
   (ledger, hour-0 contracts, handoff examples) in `workflows/loop-engineering/` because
   they are methodology artifacts; put the **engineering outcome stories** (aether
   migration, manifest repair) in `docs/case-studies/` because they are product
   narratives.

3. **AGENTS.md publication**: `AGENTS.md` contains several sections that are genuine
   public methodology (Goal governance, experiment discipline, eval-first reset rules)
   alongside private-infra references (Azure VM scripts, terminal-workflow, tool-call composite). The
   question is whether to publish a sanitized derivative in `workflows/orchestration/`
   or to keep `AGENTS.md` private-only and ensure `workflows/` captures the
   abstracted principles. Recommend: publish a derivative titled
   `codex-goal-governance.md` that strips the eval and infra references.

4. **Synthesis protocol docs**: `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
   and `DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md` are real and potentially public,
   but they cross-reference private corpus paths and coverage-register state. Need
   a targeted read of both before promotion. Flag for a follow-up sanitization review.

5. **`analyze-agent-runs` consolidation**: the `tracking/collab/skills/` version is
   richer than the `workflows/skills/` version. Should the public version absorb the
   richer content (merging the 11-step workflow from the full SKILL.md into the
   public page) or should both exist as distinct tiers? Recommend merging — one
   authoritative public skill is better than two versions at different depths.

6. **Research synthesis artifacts**: `research/synthesis/failure-taxonomy.md`,
   `mechanism-map.md`, and the `trajectory_case_studies/` corpus are real and
   potentially showcaseable. However, they are from the Stage 2 synthesis work and
   may contain analysis of eval-specific trajectories. A targeted privacy audit
   is needed before any of these can be published or linked publicly.

7. **`eval_suite/` cross-links**: several skill docs reference `eval_suite/` paths
   that now have real content. The `workflows/evals/README.md` stub should be
   expanded with a concrete skill for "designing a public eval pack" (grounded in
   the `public_manifest_repair_smoke` and `homolog_contract_smoke` work). This is
   probably a one-session task.

---

*This file is a discovery-only artifact. No files were created, edited, or moved as
part of this discovery pass. All proposed moves require sanitization review and
explicit approval before execution.*
