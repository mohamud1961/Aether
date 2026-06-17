# Raw Ledger Update

- recorded_at_utc: 2026-06-16T20:32:32.024305+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: correct public variant wording from snapshots to real implementations
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: b7e67ebb7368e8e697f101f7f302232b5fbc312c55b51807a494560a5b16961b
- commit_message: Clarify variants as real implementations, not snapshots
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/203232_codex_correct-public-variant-wording-from-snapshots-to-real-implementations_b7e67ebb73.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: correct public variant wording from snapshots to real implementations
- event_type: implementation
- summary: Replaced application-facing wording that described variants as code snapshots with wording that describes real variant implementations, full-line implementations, and scored decision surfaces where evidence exists.
- observations: Root README and variants README now distinguish real family-level variant code from frozen whole-harness reference lines without underselling variants as partial snapshots.
- inference: Public repo positioning now better matches the application story: real evals and real variants, with honest scoring gaps where data does not exist.
- evidence_paths: README.md; variants/README.md; docs/publication/public_evidence_index.md
- affected_components: public navigation; variant map; public evidence index
- decision_change: Public wording now uses real variant implementations/full-line implementations rather than code snapshots.
- unresolved_questions: .git remains read-only in this sandbox, so the wording fix is not staged or committed here.
- confidence: high
- commit_message: Clarify variants as real implementations, not snapshots
```
