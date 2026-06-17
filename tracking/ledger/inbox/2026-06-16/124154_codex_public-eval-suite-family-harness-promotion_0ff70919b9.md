# Raw Ledger Update

- recorded_at_utc: 2026-06-16T12:41:54.281499+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Codex
- task: public eval suite family/harness promotion
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 0ff70919b9b4f28c8859b5ed83477a4be6097d7c4867eb567acdb196d2f1909a
- commit_message: Add public eval family and harness summaries
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/124154_codex_public-eval-suite-family-harness-promotion_0ff70919b9.md

```text
RAW_LEDGER_UPDATE
- actor: Codex
- task: public eval suite family/harness promotion
- event_type: implementation
- summary: Added a public eval map with family-level summaries, a whole-harness overview, sanitized calibration lanes, and renamed adapted-pressure family summaries under eval_suite/.
- observations: Created family index and summary pages for the public smoke packs; added harness-wide, calibration, and adapted-pressure boards plus example scoreboards; updated publication navigation and the eval map contract; rewrote cautionary wording to avoid exact leak/overclaim phrases.
- inference: The public eval surface now reads as a structured system instead of a flat smoke list, while still keeping executable packs and private collab evidence separated.
- evidence_paths: eval_suite/families/index.json; eval_suite/boards/public_eval_harness_v1.json; eval_suite/boards/public_calibration_lanes_v1.json; eval_suite/boards/public_adapted_pressure_families_v1.json; eval_suite/schemas/public_eval_map_contract.md; docs/publication/public_evidence_index.md; docs/publication/publication_gap_list.md; tracking/collab/public_repo_readiness/public_eval_suite_family_harness_promotion_handoff.md
- affected_components: eval_suite public navigation; docs/publication indexes; public_repo_readiness handoff
- decision_change: Promote public-safe summary layers for family, harness, calibration, and adapted-pressure views; keep raw task packs and private collab registries private.
- unresolved_questions: Whether the next public slice should add a third runnable custom family or a more detailed harness-summary example.
- confidence: medium
- commit_message: Add public eval family and harness summaries
```
