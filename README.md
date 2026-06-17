# HarnessEng

HarnessEng is an eval-first agentic harness workspace: a Python runtime, real
eval packs, variant families, research synthesis, and a public-readiness
workflow layer for running agent work as governed loops.

## Repository Map

- `harness/aether2/` is the active Python harness line.
- `eval_suite/` contains custom evals organized by capability family and
  whole-harness surface, including boards, result rows, scoreboards, and
  scorecard-style summaries where evidence exists.
- `variants/` contains mechanism-family and whole-harness variant surfaces,
  including real variant implementations, hypotheses, tournament records, and
  scoreboards/scorecards where runs were actually scored.
- `research/` contains promoted deep-synthesis outputs, run analyses,
  planning artifacts, reviews, mechanism maps, failure taxonomies, and case
  studies.
- `docs/` is the public documentation hub: architecture maps, publication
  boundaries, public evidence indexes, readiness commands, schemas, and
  reviewer-facing case studies.
- `workflows/` is the AI-native engineering operating layer: loop
  orchestration, skills, run operations, synthesis, planning, review,
  handoff, automation, and repair workflows.

## Eval And Variant Discipline

The project treats eval evidence as the promotion authority. A mechanism or
harness line is not considered improved because a trace looks convincing or a
plan is well written. It needs a task contract, grader or verifier, result
rows, and a scored decision surface.

Variants are organized at two levels:

- family-level variants compare competing mechanisms inside one capability
  family;
- whole-harness variants compare larger runtime stacks and orchestration
  routes.

Scoreboards and scorecards are included only where real scored data exists.
Missing score data is left explicit rather than filled with placeholder claims.

## AI-Native Engineering Layer

The `workflows/` folder is not a showcase folder. It is the operating system
for using agents effectively:

- orchestrator threads gather context and dispatch bounded work;
- specialist threads and subagents execute, analyze, review, or repair;
- every material worker hands evidence back to the orchestrator;
- maker/checker loops separate implementation from review;
- eval, review, and run-analysis skills decide whether to promote, kill, or
  rerun work;
- memory lives in files, ledgers, scoreboards, and handoffs so the loop can
  continue across sessions.

## Aether Runtime Capability Slices

The public tree includes Python-native Aether capability slices for the
agent-runtime features expected of a serious AI-native harness. These are owned
HarnessEng interfaces with public eval coverage and provenance boundaries:

- skills and bounded context loading;
- MCP-style registry/runtime contracts;
- subagent loading and structured handoffs;
- hooks, permissions, and visible denial ordering;
- tool/runtime surfaces used by the harness and eval packs.

See `docs/provenance/` for publication boundaries and `docs/publication/` for
the public evidence index.

## Start Here

1. Read `PUBLIC_REVIEWER_GUIDE.md` for the shortest hiring/reviewer narrative.
2. Run `make public-readiness` for the cold-start and public smoke path.
3. Read `docs/publication/public_evidence_index.md` for the shortest
   reviewer-friendly path.
4. Read `workflows/agentic-engineer-capability-map.md` for the AI-native
   engineering capability map.
5. Read `workflows/phases/README.md` and `workflows/use-cases/README.md` for
   the staged workflow and practical playbooks.
6. Read `workflows/loop-engineering/README.md` for the orchestration loop.
7. Read `eval_suite/README.md` and `variants/README.md` to inspect the scored
   eval and variant surfaces.
