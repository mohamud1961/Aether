# Raw Ledger Update

- recorded_at_utc: 2026-06-16T19:32:57.490251+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Codex public-readiness continuation goal 019ed1d4-49e9-7790-9f96-6e12f6d3f02e
- task: Continue Opus public repo readiness reorg with family/whole-harness taxonomy for evals and variants; no new evals or variants.
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 15fbfccc83b4a37435702969c3309cba7529263f6360ac7a78d9a646f70e47b3
- commit_message: HOLD - git index write blocked by sandbox; intended slice subject is "Organize public evals and variants by family"
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/193257_codex-public-readiness-continuation-goal-019ed1d4-49e9-7790-9f96-6e12f6d3f02e_continue-opus-public-repo-readiness-reorg-with-family-whole-harness-taxonomy-for-evals-and-variants-no-new-evals-or-variants_15fbfccc83.md

```text
RAW_LEDGER_UPDATE
- actor: Codex public-readiness continuation goal 019ed1d4-49e9-7790-9f96-6e12f6d3f02e
- task: Continue Opus public repo readiness reorg with family/whole-harness taxonomy for evals and variants; no new evals or variants.
- event_type: implementation
- summary: Moved existing eval_suite packs out of public-facing custom/benchmark-derived taxonomy into eval_suite/families/<mechanism-family>/<pack>/ and eval_suite/whole_harness/; moved existing G2 verifier tasks under the homolog runtime-contract family; cleaned variants metadata labels from benchmark_derived_transfer_* to pressure_transfer_* without changing variant implementation code.
- observations: All eval family leaves now have a real eval marker: task_pack.json, task_pack.yaml, grader.py, grader/grade.py, or verifier.sh. Removed old taxonomy wrapper directories and the internal adapter-lanes note from eval_suite. Eval-suite high-risk scan found no host paths, public benchmark identifiers, hidden verifier assets, raw result_rows.jsonl, pyc files, reviewer_pack, hidden_assets, .aether2, or .tbench-testing. Curated docs/research scan was sanitized for host paths, temp paths, benchmark identifiers, and model-route labels. Variants still preserve model-route strings inside historical copied code snapshots to avoid altering real code.
- inference: The eval and variant public surface now follows the requested family/whole-harness organization and avoids fabricating new evals, variants, or scoreboards. The remaining raw research/analysis BigAI trace-layer diff is intentionally not part of the public curated slice because it is source-derived bulk intermediate data.
- evidence_paths: eval_suite/families/; eval_suite/whole_harness/; variants/families/; variants/harness/; docs/; research/case_studies/; research/methodology/; research/phases/; research/synthesis/
- affected_components: public eval suite layout, variant metadata labels, public-readiness docs/research curation
- decision_change: User instruction superseded earlier custom/benchmark-derived top-level layout; public evals and variants are now organized by mechanism family or whole-harness line instead.
- unresolved_questions: Git staging/commit is blocked in this session because .git/index.lock cannot be created under the current filesystem permission profile; a normal repo-write terminal must stage/commit the completed file changes. Existing raw research/analysis BigAI trace-layer modifications remain dirty and should not be promoted in the public curated commit without a separate decision.
- confidence: high for filesystem layout and scan results; medium for final publication status because commit could not be created from this sandbox.
- commit_message: HOLD - git index write blocked by sandbox; intended slice subject is "Organize public evals and variants by family"
```
