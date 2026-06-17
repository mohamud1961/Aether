You are a repo-access research synthesis agent working inside the harnesseng repository.

Goal

- Promote the best existing evidence into the top-level analysis so the project is not dependent on stranded subdirectory outputs.

Primary targets

- `research/analysis/failure_modes.md`
- `research/analysis/patterns.md`
- `research/analysis/lego_dimensions.md`

Evidence sources to use

- `research/analysis/bigai_trace_layer/output/`
- accepted bucket manifests and accepted bucket artifacts
- repaired local trajectory/codebase syntheses from the fresh readiness run
- `research/sources/codebases/langchain/` where it contributes concrete eval-design or evaluator-mechanism evidence
- `tracking/ledger/open_questions.md` where relevant

Tasks

1. Populate `failure_modes.md` with a real failure taxonomy.
2. Upgrade `patterns.md` from seed notes to evidence-backed patterns with citations.
3. Turn `lego_dimensions.md` into an evidence-backed map of:
   - which dimensions are well supported
   - which remain weak
   - which interactions matter most
4. Distinguish observed evidence from inference.
5. Explicitly note where evidence is still insufficient instead of smoothing over gaps.

Rules

- No filler prose.
- Every nontrivial claim must point to a repo-local evidence path.
- Do not pretend unresolved areas are settled.
- The output should be usable for mechanism mapping and next-phase block design.
