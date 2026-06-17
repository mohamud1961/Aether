# Raw Ledger Update

- recorded_at_utc: 2026-06-06T12:01:29.524693+00:00
- source: agent_session
- cwd: /Users/mohamud/.codex/worktrees/c88e/harnesseng
- actor: codex
- task: fix the recovery command/path serialization bug in the model-led harness
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: bff25f4a42d5007cc0710fb839c72628e75fb5e0e020480a22888f0b9ea748ca
- commit_message: Harden recovery command-path serialization and bound failure fingerprints
- handoff_file: /Users/mohamud/.codex/worktrees/c88e/harnesseng/tracking/ledger/inbox/2026-06-06/120129_codex_fix-the-recovery-command-path-serialization-bug-in-the-model-led-harness_bff25f4a42.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: fix the recovery command/path serialization bug in the model-led harness
- event_type: implementation
- summary: Hardened command-path extraction and recovery fingerprinting so multiline heredoc commands no longer flow into artifact path normalization or bounded recovery cards.
- observations: runner/kernel_artifacts.py now extracts only bounded artifact path refs and skips unsafe command text before path resolution; runner/kernel_recovery.py now emits command digests/snippets instead of raw multiline commands in failure signatures; runner/kernel_state.py and runner/active_evidence_kernel.py now use the safer extractor; focused pytest run passed.
- inference: The Errno 36 failure mode was caused by raw command text being treated as a path candidate, not by the eval rows themselves.
- evidence_paths: runner/kernel_artifacts.py; runner/kernel_recovery.py; runner/kernel_state.py; runner/active_evidence_kernel.py; tests/test_kernel_artifacts.py; tests/test_active_evidence_kernel.py; tracking/collab/model_led_substrate_v1/workers/worker_recovery_command_path_serialization.md
- affected_components: artifact registry refresh; required-artifact validation; recovery signature generation; active evidence kernel command-path projection
- decision_change: Raw shell command text is no longer eligible to become an artifact path, and recovery cards now carry bounded command metadata instead of full command bodies.
- unresolved_questions: Whether future evals will require broader path extraction coverage for unusual path syntax such as spaces or non-POSIX separators.
- confidence: high
- commit_message: Harden recovery command-path serialization and bound failure fingerprints
```
