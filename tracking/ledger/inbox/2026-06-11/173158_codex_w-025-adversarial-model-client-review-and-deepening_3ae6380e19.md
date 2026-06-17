# Raw Ledger Update

- recorded_at_utc: 2026-06-11T17:31:58.713048+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: W-025 adversarial model_client review and deepening
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 3ae6380e19b8847906e0a17a190db2c3fe0dcd7f767e9d61c59c9e1dba9c6e68
- commit_message: Strengthen Aether2 model client contract tests
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-11/173158_codex_w-025-adversarial-model-client-review-and-deepening_3ae6380e19.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: W-025 adversarial model_client review and deepening
- event_type: implementation
- summary: Strengthened the Aether-2 model-client contract tests and hardened response tool-call normalization.
- observations: Replaced no-model route stubs with real OpenAI route factory coverage; verified native tool schemas are passed through, transient ModelClientError statuses 429 and 503 retry with backoff, non-transient 400 errors are not swallowed, and TPM pacing is exercised via a real RollingTPMPacer-wrapped route.
- inference: The wrapper is thin but honest, and the remaining contract risk was under-proved test coverage rather than a code-path defect. A small normalization hardening now copies tool-call dicts out of the raw response.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/tests/test_aether2_model_client.py; /Users/mohamud/Downloads/harnesseng/runner/aether2/model_client.py; command: python3 -m pytest tests/test_aether2_model_client.py
- affected_components: runner/aether2/model_client.py; tests/test_aether2_model_client.py
- decision_change: Promoted the wrapper as contract-complete for the manifest row; no broader harness changes were needed.
- unresolved_questions: None in this scope.
- confidence: high
- commit_message: Strengthen Aether2 model client contract tests
```
