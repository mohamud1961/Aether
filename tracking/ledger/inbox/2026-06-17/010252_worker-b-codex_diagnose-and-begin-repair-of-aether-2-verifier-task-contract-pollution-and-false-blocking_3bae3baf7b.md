# Raw Ledger Update

- recorded_at_utc: 2026-06-17T01:02:52.061682+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Worker B / Codex
- task: diagnose and begin repair of Aether-2 verifier/task-contract pollution and false-blocking
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 3bae3baf7b2ecee27b3d7b24fce4501a293f94240cc74d3e0dbc5a5a93adf38b
- commit_message: Isolate verifier task contract from harness wrapper doctrine
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-17/010252_worker-b-codex_diagnose-and-begin-repair-of-aether-2-verifier-task-contract-pollution-and-false-blocking_3bae3baf7b.md

```text
RAW_LEDGER_UPDATE
- actor: Worker B / Codex
- task: diagnose and begin repair of Aether-2 verifier/task-contract pollution and false-blocking
- event_type: implementation
- summary: Added a focused task-contract projection in Aether-2 loop verification so harness wrapper doctrine is filtered out of stated requirements and fresh-context verifier task text while preserving real task constraints.
- observations: Existing extraction already skipped headings/separators/signoffs but preserved wrapper lines containing paths or negative wording. The false-block analysis identified repeated pseudo-requirements such as cwd /app, hidden verifier/solution access, task_done policy, and generic QEMU/VNC/service evidence doctrine. The patch filters generic harness-control lines during requirement extraction, sends the verifier a cleaned task contract, and keeps the executor-facing instruction unchanged.
- inference: This should reduce false-blocking from wrapper doctrine without weakening real constraint coverage; nearby verifier tests still flag a real uncovered do-not-modify constraint.
- evidence_paths: aether/control/loop.py; tests/test_aether2_loop.py; research/case_studies/aether2_run_analysis_20260615_l1_targeted.md; python3 -m pytest -q tests/test_aether2_loop.py::test_extract_stated_requirements_skips_boilerplate_wrapper_lines tests/test_aether2_loop.py::test_verifier_receives_task_contract_without_harness_wrapper_doctrine; python3 -m pytest -q tests/test_aether2_verify.py::test_verify_fresh_context_flags_uncovered_constraint_with_shape_only_evidence tests/test_aether2_verify.py::test_verify_fresh_context_strong_evidence_pass_resolves_clean tests/test_aether2_verify.py::test_verify_fresh_context_weak_self_confirming_evidence_stays_unresolved; python3 -m py_compile aether/control/loop.py tests/test_aether2_loop.py
- affected_components: aether/control/loop.py requirement extraction, completion contract task text, fresh-context verifier payload; tests/test_aether2_loop.py
- decision_change: Verifier task text now uses the extracted task-contract projection instead of the full executor instruction when the instruction contains harness wrapper doctrine.
- unresolved_questions: Needs integration with Worker A namespace/import/genericity slice and later certified homolog/board evidence to quantify false-block reduction on target rows. Read-only verifier inspection remains a separate proposed repair lane.
- confidence: medium-high for filtering observed wrapper pollution; medium for full false-block reduction until homolog/board rerun.
- commit_message: Isolate verifier task contract from harness wrapper doctrine
```
