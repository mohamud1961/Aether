# Raw Ledger Update

- recorded_at_utc: 2026-06-11T17:32:28.826119+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: orchestrator
- task: Aether-2 model-client contract deepening and gate revalidation
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: c3bee35a232ec111f4734827dbd3e6827c6aad483ca06d935a23fa3f49795d37
- commit_message: HOLD - remaining Aether-2 run-critical contracts are still incomplete
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-11/173228_orchestrator_aether-2-model-client-contract-deepening-and-gate-revalidation_c3bee35a23.md

```text
RAW_LEDGER_UPDATE
- actor: orchestrator
- task: Aether-2 model-client contract deepening and gate revalidation
- event_type: implementation
- summary: Strengthened the Aether-2 model-client contract tests to prove native tool-call pass-through, retry on 429/5xx, immediate failure on non-transient errors, and TPM-pacer-enabled route machinery usage; re-ran the mechanical genericity gate.
- observations: tests/test_aether2_model_client.py now exercises route-based pacer wrapping through runner.model_client.make_model_client_from_route and checks non-transient status 400 is not retried; python3 tools/aether2_genericity_check.py exits 0 on the live tree.
- inference: the model-client wrapper can stay thin and honest as long as the route factory and tests prove pacer usage explicitly instead of assuming it.
- evidence_paths: tests/test_aether2_model_client.py; runner/aether2/model_client.py; runner/model_client.py; runner/kernel_tpm_pacer.py; tools/aether2_genericity_check.py
- affected_components: runner/aether2/model_client.py; tests/test_aether2_model_client.py; tools/aether2_genericity_check.py
- decision_change: Treat the model-client slice as contract-strong enough for integration review, but keep the broader build open until jobs/sessions and loop contracts are completed and the run plan exists.
- unresolved_questions: jobs.py, sessions.py, and loop.py are still missing; the live worker handoffs for those components remain pending.
- confidence: high
- commit_message: HOLD - remaining Aether-2 run-critical contracts are still incomplete
```
