# Aether-2 Pre-Registered Predictions

Recorded 2026-06-11, BEFORE any Aether-2 build or run. Per AGENTS.md Experiment Discipline:
if a prediction fails, record the failed prediction — do not reinterpret the result as success.

Source of truth: `AETHER2_BUILD_SPEC.md` §15 (verbatim copy below).

1. **qemu-startup**: PASS in ≤ 12 model calls (was 30 at the cap in the prior architecture).
2. **extract-moves-from-video**: flip 0 → 1 (root causes were perception/memory/time-budget, all
   addressed in this design). Confidence: moderate — residual risk is OCR fidelity under 1 CPU /
   30-minute budget, which is task-hardness, not harness.
3. **install-windows-3.11**: flip 0 → 1 (needs sessions + setsid persistence + `wait`; all now
   present). Confidence: moderate.
4. **video-processing**: NO prediction — diagnose first (an environment-setup issue was flagged
   in a pause state for this task; root cause unknown, do not predict outcome until diagnosed).
5. **Cache hit ratio ≥ 80%**; **≤ 150k fresh input tokens per hard task**.

Sentinels named for the G3 calibration runs: qemu-startup green-check (regression sentinel for
the mirror/progress mechanisms), BFCL adapter board, non-TB generalization board (spec §11).
