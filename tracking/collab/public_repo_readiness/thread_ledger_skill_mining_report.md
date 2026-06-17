# Thread/Ledger Skill Mining Report

Status: sanitized skill-pattern summary

This report preserves the publication-safe conclusions from the original skill
mining pass while removing machine-local links and direct indexes into raw
private execution material.

## Executive Summary

The observed working style is governed AI-native engineering rather than
free-form chat iteration. The recurring pattern is:

1. define a bounded artifact with explicit scope and evidence requirements;
2. route the slice to a specific worker or role;
3. require separate outputs instead of a merged transcript;
4. close with synthesis, review, or both;
5. persist material outcomes while keeping raw ledger intake separate from the
   curated public story.

The biggest structural takeaway is that planning/orchestration and closeout
review are related but distinct skills. The workflow repeatedly separates:

- goal and slice definition;
- worker execution;
- evidence capture;
- adversarial or checklist closeout;
- publication-safe summarization.

## Observed Workflow Patterns

- Strategy and execution are deliberately separated.
- Worker prompts are bounded by scope, exclusions, and evidence outputs.
- Review is treated as a gate, not as optional polish.
- Scoreboards, verifiers, and result rows outrank prose summaries.
- Invalid environment/provider rows are separated from capability conclusions.
- Publication discipline is explicit: raw records stay private; curated
  summaries carry the public narrative.

## Skill Candidates

| Skill | Purpose | Public / Private | Generic / Specific | Priority |
|---|---|---|---|---|
| `orchestrator_goal_setting_and_planning` | Define bounded goals, route specialist slices, and keep scope/stop conditions coherent. | Public-safe | Generic | P0 |
| `codex_review_closeout` | Run code-review closeout and verify or reject findings against the real diff. | Public-safe | Generic | P0 |
| `code_review_and_checklist_closeout` | Perform adversarial or checklist review when a full code review helper is not the right gate. | Public-safe | Generic | P1 |
| `worker_handoff_writing` | Write bounded worker handoffs with final status, validation, blockers, and next action. | Public-safe | Generic | P0 |
| `evidence_inventory_and_synthesis_prep` | Build an evidence base before synthesis, with confidence and source typing. | Public-safe | Generic | P0 |
| `trace_causality_and_fake_progress_analysis` | Reconstruct decisive divergence and separate activity from semantic progress. | Public-safe | Generic | P0 |
| `eval_design_and_variant_governance` | Preregister evals, sentinels, baselines, ceilings, and keep/kill decisions. | Public-safe | Generic | P0 |
| `git_commit_slicing_and_handoff` | Turn coherent slices into explicit commit-ready handoffs. | Public-safe | Generic | P1 |
| `public_repo_curation_and_hiring_packaging` | Translate technical work into curated public evidence and hiring-friendly narratives. | Public-safe | Generic | P1 |
| `launch_integrity_and_rebaseline` | Repair invalid measurement surfaces before capability conclusions are trusted. | Private/internal | Specific | P0 |

## Public-Safe Case-Study Themes

Strong publication candidates:

- governed multi-agent orchestration;
- eval-first reset and rebaseline discipline;
- fake-progress detection;
- adversarial closeout;
- evidence-inventory-first synthesis.

Recommended curation rule:

- preserve the governing pattern and decision logic;
- redact raw thread, ledger, workspace, grader, and auth/session material;
- replace sensitive task specifics with family-level descriptions where needed.

## Private Material To Keep Out Of Publication

Do not publish verbatim:

- raw historian inbox files;
- raw thread dumps or session-state artifacts;
- hidden graders, answer keys, or eval-internal payloads;
- raw per-task workspaces or artifact bundles;
- provider/account configuration details;
- live planning folders that expose current campaign state.

The safe public substitute is a curated summary, a redacted excerpt, or an
anonymized pattern note.

## Hiring Framing

The strongest hiring signal is not “used lots of agents.” It is “ran agentic
engineering like an evidence-governed system.” The work shows:

- bounded delegation;
- explicit evidence hierarchies;
- adversarial closeout discipline;
- honest invalidation when measurement is broken;
- strong publication and privacy hygiene instincts.

## Next Actions

1. Turn the highest-value public-safe patterns into standalone workflow docs or
   skills.
2. Keep launch-integrity repair and similar measurement-critical operations in
   private/internal guides.
3. Publish curated case studies that show the method without exposing raw
   execution surfaces.
