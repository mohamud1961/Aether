# Raw Ledger Update

- recorded_at_utc: 2026-06-14T22:32:37.516868+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: convert Aether-2 fake-progress diagnosis into eval-first implementation fix plan
- event_type: decision
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: a97ddf16ac4cc5d376a8ca8cea442706bb549e7c50797128d631e886b8392636
- commit_message: HOLD - implementation plan and preregistration only; no mechanism code implemented
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-14/223237_codex_convert-aether-2-fake-progress-diagnosis-into-eval-first-implementation-fix-plan_a97ddf16ac.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: convert Aether-2 fake-progress diagnosis into eval-first implementation fix plan
- event_type: decision
- summary: Produced a complete implementation program covering model input, task-contract projection, evidence ledger/provenance, semantic no-progress, completion and blocked status, verifier strength and blockers, EnvContract v2, service/VM/job/session/long-build monitoring, compaction, instrumentation, runner/grader isolation, scheduling/resource attribution, and model routing. Added a staged 13-task diagnostic board: 10 core fake-progress tasks plus build-pmars, qemu-alpine-ssh, and compile-compcert for EnvMap/service/long-job coverage.
- observations: Live code review confirmed successful artifact writes/notes become weak evidence, new refs count as stronger evidence, any artifact change resets semantic no-progress, observations attach to the first unresolved line-derived requirement, and verifier cleanliness ignores computed evidence strength when verdict is satisfied. Recent decision traces also require parser repair and repair-round step capture.
- inference: Begin with trace reliability and custom homolog baselines, then isolate model-input, activity/evidence, provenance, no-progress, completion, verifier, environment, and service mechanisms before combinations. Verifier pessimism without grader-pass gains is not success.
- evidence_paths: tracking/collab/aether2_fake_progress_implementation_plan_20260614/IMPLEMENTATION_FIX_PLAN.md; tracking/collab/aether2_fake_progress_implementation_plan_20260614/TARGETED_BOARD.md; tracking/collab/aether2_fake_progress_analysis_20260614/older_vm_and_trace_rerun_fake_progress_analysis_20260614.md; tracking/collab/variant_hypothesis_backlog.md
- affected_components: runner/aether2/prompts.py; runner/aether2/context.py; runner/aether2/loop.py; runner/aether2/delta.py; runner/aether2/mirror.py; runner/aether2/tools.py; runner/aether2/verify.py; runner/aether2/orientation.py; runner/aether2/jobs.py; runner/aether2/sessions.py; runner/aether2/compactor.py; runner/aether2/receipts.py; tools/aether2_decision_trace.py; tools/run_aether2_g3_official.py; scheduling and result-row tooling
- decision_change: The next implementation goal should be Slice A only: repair trace parsing and repair-round capture, create/freeze custom homolog evals, establish baseline and ceiling rows, and do not implement behavior mechanisms until those proof surfaces pass.
- unresolved_questions: Whether structured task_done fields reduce tool-call reliability; how conservatively same-method evidence can be detected; EnvContract orientation latency budget; best bounded service survival window; whether task_blocked causes overuse; exact source of empty decision-trace parsing.
- confidence: high in component mapping and sequencing; medium in per-mechanism score ranges until custom homolog baselines exist.
- commit_message: HOLD - implementation plan and preregistration only; no mechanism code implemented
```
