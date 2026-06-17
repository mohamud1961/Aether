# Raw Ledger Update

- recorded_at_utc: 2026-06-16T01:38:37.945819+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: public evidence index for reviewer-facing publication navigation
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 153e51ccefde4b6b3b9a59aec95c97bc3e9e984774a147a3f4011d5a20161c89
- commit_message: HOLD - add public evidence index and wire reviewer navigation
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/013837_codex_public-evidence-index-for-reviewer-facing-publication-navigation_153e51ccef.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: public evidence index for reviewer-facing publication navigation
- event_type: implementation
- summary: Added a compact public-safe evidence index and wired it into the top-level publication/navigation docs.
- observations: New `docs/publication/public_evidence_index.md` groups architecture, eval packs/scoreboards, direct TS-to-Python slices, workflow/Loop Engineering, provenance, and case studies. README, docs/README, docs/publication/README, docs/case-studies/README, and the AI-native showcase now point at the index. The publication gap list now marks the index as resolved.
- inference: A single reviewer entrypoint reduces the chance of missing clean public artifacts while keeping raw private surfaces out of the public story.
- evidence_paths: docs/publication/public_evidence_index.md; README.md; docs/README.md; docs/publication/README.md; docs/case-studies/README.md; docs/publication/publication_gap_list.md; workflows/ai-native-engineering-showcase.md; tracking/collab/public_repo_readiness/public_evidence_index_handoff.md
- affected_components: public documentation navigation; publication boundary docs; reviewer-facing evidence discoverability
- decision_change: The index item previously tracked in the publication gap list is now resolved and referenced directly from public docs.
- unresolved_questions: Whether the next publication slice should add a second public case study or a non-smoke eval family.
- confidence: high
- commit_message: HOLD - add public evidence index and wire reviewer navigation
```
