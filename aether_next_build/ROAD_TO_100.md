# ROAD TO 100 — Aether-Next execution plan

Written 2026-07-05 by Fable 5 (session 4). Source of truth for finishing the harness.
Resume rule: read this + `AETHER_NEXT_PROGRESS.md`, verify claims against code/tests, continue top-down.
Suite gate: `python3.11 -m pytest tests -q` must stay green after every slice. Never commit to master.

## State at time of writing

- HEAD `07c8a5d2`, branch `codex/canonical-aether-consolidation`, suite 345 passed.
- All audit root-causes from 12 runs fixed and committed (see AETHER_NEXT_PROGRESS.md "Batch5 audit execution").
- Docker is UP. Validation batch is being launched via a Haiku monitor agent.

## The ordered road (strike through as completed; record evidence refs)

1. ~~**Validation batch**~~ DONE — **3/3 OFFICIAL GRADER PASSES** (`local_goal_runs/20260705T201305Z_validation3/`):
   - headless-terminal: completed, reward 1.0, **8 steps** (was timeout/ungraded at 34) — prediction HIT
   - kv-store-grpc: reward 1.0, 22 steps (was timeout/ungraded at 49) — prediction HIT; internal solver_submit_stalemate (see below)
   - code-from-image: reward 1.0, **16 steps** (was 0.0 at 120 steps) — the VISION LANE converted an unreachable task — prediction EXCEEDED
   - Residual defect found via auto-persisted evidence bundles and FIXED (`d4367064`): the verifier asked the SOLVER to "provide the contents of /app/output.txt" (unsatisfiable — solver claims never enter the state-only packet); path-bearing prose missing-evidence requests now trigger the verifier's own read_file/perceive_artifact inspection within the same round. The kv/code-from-image internal stalemates should convert to internal `completed` on the next run.
   Original spec:
   `python3.11 run_pilot.py --tasks headless-terminal,kv-store-grpc,code-from-image --vision-deploy-env AZURE_OPENAI_GPT54_MINI_DEPLOYMENT --max-steps 40 --trace-dir local_goal_runs/<stamp>/traces --out local_goal_runs/<stamp>/results.json`
   Prediction (record hit/miss): headless PASS, kv PASS, code-from-image first genuine attempt (pass uncertain).
   Interpretation rules: graded_after_timeout rows are valid; verifier evidence bundles auto-persist under trace_dir.

2. ~~**Verifier economics slice**~~ DONE (`3eceeba6`): unchanged-packet memoization + changed-inputs-only checks, 3 tests. Original spec: (biggest efficiency lever; openssl burned 16 rounds on identical state)
   a. Unchanged-packet memoization: hash the state-only packet minus step/reason (`verifier_packets.packet_state_signature`); if identical to last judged signature and last verdict non-completed → skip the model call, record `model_verifier_skipped:unchanged_state` receipt, reuse verdict, count toward submit-stalemate.
   b. Changed-inputs-only check re-execution: in `kernel_turns.run_submit_turn`, skip re-running a planned check when no state_change receipt has occurred since its last execution; record `check_skipped_unchanged` receipt with the prior outcome (kv ran 117 check executions).
   Tests: memoized round produces no verify call; state change re-enables both; stalemate still fires.

3. ~~**Verifier-side vision parity**~~ DONE (`3eceeba6`): `perceive_artifact` inspection kind + guidance + tests. Original spec:: new inspection kind `perceive_artifact` in `verifier_inspector.py` → uses kernel/hooks `perceive_image` (available via `kernel_verifier._call_verify`'s access to hooks) on an image path; result labeled `model_transcription_not_ground_truth`. Without a vision model → explicit error row. Advertise in `model_prompts.py` inspector kinds. Test with stub vision hooks.

4. **Perceptual-class live proof** (after 1 lands): one run each
   `--tasks video-processing --vision-deploy-env ...` and `--tasks qemu-startup ...` (max-steps 60; budgets honor task.toml). Interpret: solver should sample frames via ffmpeg + inspect_artifact(vision); verifier should perceive frames itself (needs slice 3).

5. ~~**Step-budget expectations**~~ DONE (`e5f5e179`): architect `expected_steps` → config_realization → result-row `step_efficiency`. Original spec:: architect config optional `expected_steps` (int) in HarnessConfigIR (workbench_config parse + prompt mention); thread into result rows as `expected_steps` + `step_efficiency = step/expected`; no runtime enforcement (advisory metric only — never a gate).

6. **Size-cap closure** PARTIAL (`e855e05c` + follow-up): docker_runner 965→693 (DockerExecExecutor extracted), model_hooks 619→446 (model_parse.py), compiler 664→606 (compiler_prefix.py). Remaining over-cap: docker_runner 693 (run_tbench_task orchestration — split record assembly next), compiler 606 (split config_realization builder next). Original spec:: docker_runner 965 → split executor class into `runners/docker_exec_executor.py` (~250 LOC) and grader/reward resolution into `runners/grader_resolve.py`; compiler 664 → extract prefix-section builder into `compiler_prefix.py`; model_hooks 619 → extract solver/architect parse helpers into `model_parse.py`. Suite green after each move.

7. ~~**Repo hygiene**~~ DONE (`e5f5e179`): run/eval artifact dirs gitignored. Original spec:: add `.gitignore` entries under aether_next_build for `local_goal_runs/`, `deterministic_integration_eval_*/`, `component_eval_*/`, `architect_only_eval_*/`, `verifier_only_eval_*/`, `trace_verifier_replay_*/`, `DOCKER_ISOLATION_SMOKE_*.json` (already-tracked files stay tracked; new artifacts stop polluting status). Do NOT untrack existing evidence without an explicit decision.

8. **10–20 task diverse board** at fixed SHA (after 1–4): pick across classes — file/data (log-summary, gcode-to-text), git (fix-git, git-multibranch), query (sparql, regex-log), build (write-compressor, polyglot-c-py), service (nginx-request-logging, pypi-server), security (crack-7z-hash, vulnerable-secret), perception (code-from-image, video-processing), interactive (headless-terminal, qemu-startup), ML (train-fasttext). Record per-class pass rates + step efficiency. This produces the first honest capability %.

9. **Consolidation rename** `aether_next_build/aether_next` → `aether/` per CLAUDE.md target (last, after board is green): move package, update imports, keep `aether_next` shim for one release, update docs.

## Standing invariants (do not regress)
Fail-closed config; state-only verifier packet (forbidden-field assertion); no solver self-report authority; no task-name logic; advisory-only memory/no-progress; full outputs by handle; cache-stable prefix; architect_defect never laundered; grader external post-terminal only; every non-pass row classified with evidence.

## Known debts (tracked, not urgent)
- Wall-clock budget counts verifier model latency against the task budget (consider separate metering).
- fix-git watch item: prominent logging when solver edits deliverable-adjacent test/entry files.
- Old-line surfaces (`harness/aether2`, `pro_workspace_aether_next`) remain as reference; do not build on them.
